"""Render Engine - renders JavaScript-heavy pages with Playwright."""

import asyncio
import hashlib
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Company, CrawlSnapshot
from app.engines.render.browser import BrowserPool, RenderResult

logger = structlog.get_logger()


class RenderEngine:
    """Engine for rendering JavaScript-heavy pages."""

    def __init__(self, db: AsyncSession, browser_pool: Optional[BrowserPool] = None):
        self.db = db
        self._browser_pool = browser_pool
        self._owns_pool = browser_pool is None

    async def _get_browser_pool(self) -> BrowserPool:
        """Get or create browser pool."""
        if self._browser_pool is None:
            self._browser_pool = BrowserPool()
            await self._browser_pool.start()
        return self._browser_pool

    async def close(self):
        """Close browser pool if we own it."""
        if self._owns_pool and self._browser_pool:
            await self._browser_pool.stop()

    async def render_snapshot(
        self,
        snapshot_id: UUID,
        force: bool = False,
    ) -> Optional[CrawlSnapshot]:
        """Render a crawl snapshot if it needs JS rendering."""
        # Get snapshot
        result = await self.db.execute(
            select(CrawlSnapshot).where(CrawlSnapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            logger.warning("Snapshot not found", snapshot_id=str(snapshot_id))
            return None

        # Check if already rendered
        if snapshot.rendered and not force:
            logger.info("Snapshot already rendered", snapshot_id=str(snapshot_id))
            return snapshot

        # Check if rendering is needed
        if not force and not self._needs_rendering(snapshot.html_content or ""):
            logger.info("Rendering not needed", snapshot_id=str(snapshot_id))
            return snapshot

        logger.info("Rendering snapshot", snapshot_id=str(snapshot_id), url=snapshot.url)

        try:
            pool = await self._get_browser_pool()
            render_result = await pool.render(snapshot.url)

            if render_result.success and render_result.html:
                # Update snapshot with rendered content
                snapshot.html_content = render_result.html
                snapshot.html_hash = hashlib.sha256(render_result.html.encode()).hexdigest()
                snapshot.rendered = True
                snapshot.status_code = 200

                await self.db.commit()

                logger.info(
                    "Render complete",
                    snapshot_id=str(snapshot_id),
                    html_size=len(render_result.html),
                    render_time=f"{render_result.render_time_ms}ms",
                )

            else:
                logger.warning(
                    "Render failed",
                    snapshot_id=str(snapshot_id),
                    error=render_result.error,
                )

            return snapshot

        except Exception as e:
            logger.error("Render error", snapshot_id=str(snapshot_id), error=str(e))
            return None

    async def render_company(
        self,
        company_id: UUID,
        force: bool = False,
    ) -> Optional[CrawlSnapshot]:
        """Render the latest snapshot for a company."""
        # Get latest snapshot
        result = await self.db.execute(
            select(CrawlSnapshot)
            .where(CrawlSnapshot.company_id == company_id)
            .order_by(CrawlSnapshot.crawled_at.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            logger.warning("No snapshot found for company", company_id=str(company_id))
            return None

        return await self.render_snapshot(snapshot.id, force)

    def _needs_rendering(self, html: str) -> bool:
        """
        Detect if page needs JavaScript rendering.

        Returns True if:
        - Page uses React/Next.js/Vue/Angular
        - Job listings container is empty
        - Specific loading indicators present
        """
        html_lower = html.lower()

        # Check for JS frameworks that require rendering
        js_indicators = [
            "__next_data__",  # Next.js
            "__nuxt__",  # Nuxt.js
            "react-root",
            "ng-app",  # Angular
            "vue-app",
            'id="app"',  # Common Vue/React pattern
            "data-reactroot",
        ]

        for indicator in js_indicators:
            if indicator in html_lower:
                return True

        # Check for loading states
        loading_indicators = [
            "loading...",
            "please wait",
            "spinner",
            'class="loader"',
            'class="loading"',
        ]

        for indicator in loading_indicators:
            if indicator in html_lower:
                return True

        # Check for empty job containers (common patterns)
        empty_patterns = [
            '<div class="job-listings"></div>',
            '<div class="jobs-list"></div>',
            '<ul class="job-list"></ul>',
            "no jobs found",
        ]

        for pattern in empty_patterns:
            if pattern in html_lower:
                return True

        return False


async def render_company(company_id: str):
    """Render latest snapshot for a company (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = RenderEngine(db)
        try:
            await engine.render_company(UUID(company_id))
        finally:
            await engine.close()


async def render_unrendered_snapshots(limit: int = 50):
    """Render all unrendered snapshots (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        # Get unrendered snapshots
        result = await db.execute(
            select(CrawlSnapshot)
            .where(CrawlSnapshot.rendered == False)
            .order_by(CrawlSnapshot.crawled_at.desc())
            .limit(limit)
        )
        snapshots = result.scalars().all()

        if not snapshots:
            logger.info("No unrendered snapshots")
            return

        engine = RenderEngine(db)
        try:
            for snapshot in snapshots:
                await engine.render_snapshot(snapshot.id)
        finally:
            await engine.close()
