"""HTTP crawler with polite crawling features."""

import asyncio
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
import structlog
from protego import Protego

from app.config import get_settings
from app.engines.crawl.rate_limiter import RateLimiter

settings = get_settings()
logger = structlog.get_logger()


class Crawler:
    """Polite HTTP crawler with rate limiting and robots.txt respect."""

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.user_agent = user_agent or settings.crawl_user_agent
        self.timeout = timeout or settings.crawl_timeout_seconds
        self.robots_cache: dict[str, RobotExclusionRulesParser] = {}

        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            },
        )

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    async def _get_robots_parser(self, url: str) -> Optional[Protego]:
        """Get or fetch robots.txt parser for a domain."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url in self.robots_cache:
            return self.robots_cache[robots_url]

        try:
            response = await self.client.get(robots_url)
            if response.status_code == 200:
                parser = Protego.parse(response.text)
                self.robots_cache[robots_url] = parser
                return parser
        except Exception as e:
            logger.debug("Failed to fetch robots.txt", url=robots_url, error=str(e))

        return None

    async def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        parser = await self._get_robots_parser(url)
        if parser is None:
            return True  # No robots.txt = allowed

        return parser.can_fetch(url, self.user_agent)

    async def fetch(
        self,
        url: str,
        check_robots: bool = True,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> Tuple[Optional[str], int]:
        """
        Fetch a URL with rate limiting and retries.

        Returns:
            Tuple of (html_content, status_code)
        """
        domain = self._get_domain(url)

        # Check robots.txt
        if check_robots and not await self.can_fetch(url):
            logger.warning("Blocked by robots.txt", url=url)
            return None, 403

        # Rate limit
        await self.rate_limiter.wait(domain)

        # Fetch with retries
        last_error = None
        for attempt in range(retry_count):
            try:
                response = await self.client.get(url)

                if response.status_code == 200:
                    return response.text, 200

                elif response.status_code == 429:
                    # Rate limited - back off
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        "Rate limited",
                        url=url,
                        retry_after=retry_after,
                        attempt=attempt,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                elif response.status_code >= 500:
                    # Server error - retry
                    logger.warning(
                        "Server error",
                        url=url,
                        status=response.status_code,
                        attempt=attempt,
                    )
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue

                else:
                    # Client error - don't retry
                    logger.warning(
                        "Client error",
                        url=url,
                        status=response.status_code,
                    )
                    return None, response.status_code

            except httpx.TimeoutException:
                logger.warning("Timeout", url=url, attempt=attempt)
                last_error = "timeout"
                await asyncio.sleep(retry_delay * (2**attempt))

            except httpx.RequestError as e:
                logger.warning("Request error", url=url, error=str(e), attempt=attempt)
                last_error = str(e)
                await asyncio.sleep(retry_delay * (2**attempt))

        logger.error("All retries failed", url=url, last_error=last_error)
        return None, 0

    async def fetch_multiple(
        self,
        urls: list[str],
        concurrency: int = 5,
    ) -> dict[str, Tuple[Optional[str], int]]:
        """Fetch multiple URLs with concurrency limit."""
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def fetch_with_semaphore(url: str):
            async with semaphore:
                html, status = await self.fetch(url)
                results[url] = (html, status)

        tasks = [fetch_with_semaphore(url) for url in urls]
        await asyncio.gather(*tasks)

        return results
