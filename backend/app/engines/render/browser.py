"""Playwright browser management for JavaScript rendering."""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


@dataclass
class RenderResult:
    """Result of rendering a page."""

    success: bool
    html: Optional[str] = None
    error: Optional[str] = None
    render_time_ms: int = 0
    screenshot: Optional[bytes] = None


class BrowserPool:
    """Pool of Playwright browser instances for rendering."""

    def __init__(
        self,
        max_contexts: int = 5,
        timeout_ms: int = 30000,
    ):
        self.max_contexts = max_contexts
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._semaphore = asyncio.Semaphore(max_contexts)
        self._started = False

    async def start(self):
        """Start the browser pool."""
        if self._started:
            return

        logger.info("Starting browser pool")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )
        self._started = True
        logger.info("Browser pool started")

    async def stop(self):
        """Stop the browser pool."""
        if not self._started:
            return

        logger.info("Stopping browser pool")
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._started = False
        logger.info("Browser pool stopped")

    async def render(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_for_network_idle: bool = True,
        take_screenshot: bool = False,
    ) -> RenderResult:
        """Render a page and return the HTML."""
        if not self._started:
            await self.start()

        start_time = time.monotonic()

        async with self._semaphore:
            context: Optional[BrowserContext] = None
            page: Optional[Page] = None

            try:
                # Create new context with custom settings
                context = await self._browser.new_context(
                    user_agent=settings.crawl_user_agent,
                    viewport={"width": 1920, "height": 1080},
                    java_script_enabled=True,
                )

                # Block unnecessary resources
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}",
                    lambda route: route.abort(),
                )
                await context.route(
                    "**/analytics**",
                    lambda route: route.abort(),
                )
                await context.route(
                    "**/tracking**",
                    lambda route: route.abort(),
                )

                page = await context.new_page()
                page.set_default_timeout(self.timeout_ms)

                # Navigate to page
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                if not response:
                    return RenderResult(
                        success=False,
                        error="No response received",
                    )

                # Wait for content to load
                if wait_for_network_idle:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        # Timeout on network idle is okay, continue
                        pass

                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=10000)
                    except Exception as e:
                        logger.warning(
                            "Selector not found",
                            url=url,
                            selector=wait_for_selector,
                            error=str(e),
                        )

                # Additional wait for dynamic content
                await self._wait_for_dynamic_content(page)

                # Get HTML content
                html = await page.content()

                # Optional screenshot
                screenshot = None
                if take_screenshot:
                    screenshot = await page.screenshot(full_page=True)

                render_time_ms = int((time.monotonic() - start_time) * 1000)

                return RenderResult(
                    success=True,
                    html=html,
                    render_time_ms=render_time_ms,
                    screenshot=screenshot,
                )

            except Exception as e:
                logger.error("Render error", url=url, error=str(e))
                render_time_ms = int((time.monotonic() - start_time) * 1000)
                return RenderResult(
                    success=False,
                    error=str(e),
                    render_time_ms=render_time_ms,
                )

            finally:
                if page:
                    await page.close()
                if context:
                    await context.close()

    async def _wait_for_dynamic_content(self, page: Page):
        """Wait for dynamic content to finish loading."""
        # Wait a short time for any remaining JavaScript
        await asyncio.sleep(1)

        # Check for common loading indicators and wait for them to disappear
        loading_selectors = [
            ".loading",
            ".spinner",
            "[data-loading]",
            ".skeleton",
        ]

        for selector in loading_selectors:
            try:
                # Wait for loading indicator to disappear
                await page.wait_for_selector(
                    selector,
                    state="hidden",
                    timeout=3000,
                )
            except Exception:
                # Selector not found or timeout - that's fine
                pass

        # Check if page height is stable (content finished loading)
        prev_height = 0
        stable_count = 0

        for _ in range(5):
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == prev_height:
                stable_count += 1
                if stable_count >= 2:
                    break
            else:
                stable_count = 0
            prev_height = current_height
            await asyncio.sleep(0.5)


# Global browser pool instance
_browser_pool: Optional[BrowserPool] = None


async def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance."""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
        await _browser_pool.start()
    return _browser_pool


async def cleanup_browser_pool():
    """Cleanup the global browser pool."""
    global _browser_pool
    if _browser_pool:
        await _browser_pool.stop()
        _browser_pool = None
