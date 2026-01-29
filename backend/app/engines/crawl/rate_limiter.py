"""Rate limiter for polite crawling."""

import asyncio
import time
from collections import defaultdict
from typing import Optional

import structlog

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class RateLimiter:
    """
    Domain-level rate limiter using token bucket algorithm.

    Ensures we don't overwhelm any single domain with requests.
    """

    def __init__(
        self,
        requests_per_second: Optional[float] = None,
        burst: int = 1,
    ):
        self.requests_per_second = requests_per_second or settings.crawl_rate_limit_per_domain
        self.interval = 1.0 / self.requests_per_second
        self.burst = burst

        # Track last request time per domain
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def wait(self, domain: str):
        """Wait until we can make a request to the domain."""
        async with self._locks[domain]:
            now = time.monotonic()
            last = self._last_request[domain]

            # Calculate wait time
            elapsed = now - last
            wait_time = self.interval - elapsed

            if wait_time > 0:
                logger.debug("Rate limiting", domain=domain, wait_time=f"{wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self._last_request[domain] = time.monotonic()

    def get_wait_time(self, domain: str) -> float:
        """Get the wait time before next request to domain."""
        now = time.monotonic()
        last = self._last_request[domain]
        elapsed = now - last
        wait_time = self.interval - elapsed
        return max(0, wait_time)

    def reset(self, domain: Optional[str] = None):
        """Reset rate limiter for a domain or all domains."""
        if domain:
            self._last_request.pop(domain, None)
        else:
            self._last_request.clear()


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter that adapts based on server responses.

    Backs off when seeing 429s or 5xx errors, speeds up on success.
    """

    def __init__(
        self,
        initial_rps: float = 1.0,
        min_rps: float = 0.1,
        max_rps: float = 5.0,
        backoff_factor: float = 0.5,
        speedup_factor: float = 1.1,
    ):
        super().__init__(requests_per_second=initial_rps)
        self.min_rps = min_rps
        self.max_rps = max_rps
        self.backoff_factor = backoff_factor
        self.speedup_factor = speedup_factor

        # Per-domain rate
        self._domain_rps: dict[str, float] = defaultdict(lambda: initial_rps)

    def record_success(self, domain: str):
        """Record successful request - slightly speed up."""
        current = self._domain_rps[domain]
        new_rps = min(current * self.speedup_factor, self.max_rps)
        self._domain_rps[domain] = new_rps

    def record_rate_limit(self, domain: str):
        """Record rate limit - back off."""
        current = self._domain_rps[domain]
        new_rps = max(current * self.backoff_factor, self.min_rps)
        self._domain_rps[domain] = new_rps
        logger.info(
            "Backing off",
            domain=domain,
            old_rps=f"{current:.2f}",
            new_rps=f"{new_rps:.2f}",
        )

    def record_error(self, domain: str):
        """Record server error - moderate backoff."""
        current = self._domain_rps[domain]
        new_rps = max(current * 0.75, self.min_rps)
        self._domain_rps[domain] = new_rps

    async def wait(self, domain: str):
        """Wait based on domain-specific rate."""
        async with self._locks[domain]:
            now = time.monotonic()
            last = self._last_request[domain]
            rps = self._domain_rps[domain]
            interval = 1.0 / rps

            elapsed = now - last
            wait_time = interval - elapsed

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            self._last_request[domain] = time.monotonic()
