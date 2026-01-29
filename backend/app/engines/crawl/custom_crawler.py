"""
Custom Crawler Service - handles companies without recognized ATS.

This service crawls companies using Playwright and LLM-based extraction
for career pages that don't use a standard ATS system.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Company, Job
from app.engines.extract.playwright_extractor import (
    PlaywrightExtractor,
    extract_description_from_page,
)
from app.engines.render.browser import BrowserPool, get_browser_pool

logger = structlog.get_logger()


class CustomCrawlerService:
    """
    Service for crawling custom career pages.
    
    Handles companies where:
    - ATS detection failed after max attempts
    - ATS type is explicitly set to 'custom' or 'playwright'
    - Manual intervention is needed
    """
    
    def __init__(
        self,
        db: AsyncSession,
        browser_pool: Optional[BrowserPool] = None,
    ):
        self.db = db
        self._browser_pool = browser_pool
        self._extractor: Optional[PlaywrightExtractor] = None
    
    async def get_browser_pool(self) -> BrowserPool:
        """Get or create browser pool."""
        if self._browser_pool is None:
            self._browser_pool = await get_browser_pool()
        return self._browser_pool
    
    async def get_extractor(self) -> PlaywrightExtractor:
        """Get or create extractor."""
        if self._extractor is None:
            pool = await self.get_browser_pool()
            self._extractor = PlaywrightExtractor(pool)
        return self._extractor
    
    async def close(self):
        """Close resources."""
        # Browser pool is shared, don't close it
        pass
    
    async def mark_exhausted_as_custom(self, max_attempts: int = 3) -> int:
        """
        Mark companies with exhausted ATS detection attempts as 'custom'.
        
        This allows them to be crawled with the Playwright extractor.
        
        Returns:
            Number of companies marked
        """
        result = await self.db.execute(text('''
            UPDATE companies
            SET ats_type = 'custom'
            WHERE is_active = true
            AND ats_type IS NULL
            AND ats_detection_attempts >= :max_attempts
            RETURNING id
        '''), {"max_attempts": max_attempts})
        
        updated = result.fetchall()
        await self.db.commit()
        
        count = len(updated)
        if count > 0:
            logger.info("Marked exhausted companies as custom", count=count)
        
        return count
    
    async def crawl_custom_companies(
        self,
        limit: int = 50,
        concurrency: int = 3,
    ) -> dict:
        """
        Crawl companies with ats_type = 'custom'.
        
        Uses Playwright to render their career pages and LLM to extract jobs.
        
        Args:
            limit: Max companies to crawl
            concurrency: Number of concurrent crawls (limited for browser resources)
            
        Returns:
            Dict with crawl statistics
        """
        # Find custom companies that need crawling
        result = await self.db.execute(text('''
            SELECT id, name, domain, careers_url, website_url
            FROM companies
            WHERE is_active = true
            AND ats_type = 'custom'
            AND (crawl_attempts IS NULL OR crawl_attempts = 0)
            ORDER BY created_at DESC
            LIMIT :limit
        '''), {"limit": limit})
        
        companies = result.fetchall()
        
        if not companies:
            logger.info("No custom companies to crawl")
            return {"processed": 0, "jobs_found": 0, "errors": 0}
        
        logger.info("Starting custom crawl", company_count=len(companies))
        
        stats = {"processed": 0, "jobs_found": 0, "errors": 0}
        semaphore = asyncio.Semaphore(concurrency)
        
        async def crawl_one(company_row):
            async with semaphore:
                try:
                    jobs = await self._crawl_company(
                        company_id=company_row.id,
                        name=company_row.name,
                        careers_url=company_row.careers_url,
                        website_url=company_row.website_url,
                        domain=company_row.domain,
                    )
                    stats["processed"] += 1
                    stats["jobs_found"] += jobs
                except Exception as e:
                    logger.error(
                        "Custom crawl failed",
                        company=company_row.name,
                        error=str(e),
                    )
                    stats["errors"] += 1
        
        tasks = [crawl_one(c) for c in companies]
        await asyncio.gather(*tasks)
        
        logger.info("Custom crawl complete", **stats)
        return stats
    
    async def _crawl_company(
        self,
        company_id: UUID,
        name: str,
        careers_url: Optional[str],
        website_url: Optional[str],
        domain: Optional[str],
    ) -> int:
        """
        Crawl a single custom company.
        
        Returns:
            Number of jobs found
        """
        extractor = await self.get_extractor()
        
        # Determine URL to crawl
        url = careers_url or website_url
        if not url and domain:
            # Try common careers paths
            for path in ["/careers", "/jobs", "/careers/"]:
                url = f"https://{domain}{path}"
                break
        
        if not url:
            logger.warning("No URL for company", company=name)
            # Still mark as crawled
            await self._update_crawl_status(company_id, 0)
            return 0
        
        logger.info("Crawling custom company", company=name, url=url)
        
        # Extract jobs
        jobs = await extractor.extract_with_render(url)
        
        if jobs:
            # Save jobs to database
            from app.db import async_session_factory
            
            async with async_session_factory() as session:
                for job in jobs:
                    # Check if job already exists
                    existing = await session.execute(text('''
                        SELECT id FROM jobs 
                        WHERE company_id = :company_id 
                        AND (source_url = :url OR title = :title)
                    '''), {
                        "company_id": company_id,
                        "url": job.source_url,
                        "title": job.title,
                    })
                    
                    if existing.scalar_one_or_none():
                        continue
                    
                    # Insert new job
                    await session.execute(text('''
                        INSERT INTO jobs (
                            company_id, title, source_url, location,
                            department, created_at, is_active
                        ) VALUES (
                            :company_id, :title, :url, :location,
                            :department, NOW(), true
                        )
                    '''), {
                        "company_id": company_id,
                        "title": job.title,
                        "url": job.source_url,
                        "location": job.location,
                        "department": job.department,
                    })
                
                await session.commit()
            
            logger.info("Saved jobs from custom crawl", company=name, count=len(jobs))
        
        # Update company crawl status
        await self._update_crawl_status(company_id, len(jobs))
        
        # Update careers_url if we found a working one
        if jobs and not careers_url:
            await self.db.execute(text('''
                UPDATE companies
                SET careers_url = :url
                WHERE id = :id
            '''), {"id": company_id, "url": url})
            await self.db.commit()
        
        return len(jobs)
    
    async def _update_crawl_status(self, company_id: UUID, jobs_found: int):
        """Update company after crawl."""
        await self.db.execute(text('''
            UPDATE companies
            SET crawl_attempts = COALESCE(crawl_attempts, 0) + 1,
                last_crawled_at = NOW()
            WHERE id = :id
        '''), {"id": company_id})
        await self.db.commit()
    
    async def enrich_custom_jobs(
        self,
        limit: int = 100,
        concurrency: int = 3,
    ) -> dict:
        """
        Enrich jobs from custom companies.
        
        Uses Playwright to render job pages and LLM to extract descriptions.
        
        Args:
            limit: Max jobs to enrich
            concurrency: Number of concurrent enrichments
            
        Returns:
            Dict with enrichment statistics
        """
        # Find custom company jobs missing descriptions
        result = await self.db.execute(text('''
            SELECT j.id, j.source_url, c.name as company_name
            FROM jobs j
            JOIN companies c ON j.company_id = c.id
            WHERE j.is_active = true
            AND c.ats_type = 'custom'
            AND (j.description IS NULL OR j.description = '')
            AND j.source_url IS NOT NULL
            ORDER BY j.created_at DESC
            LIMIT :limit
        '''), {"limit": limit})
        
        jobs = result.fetchall()
        
        if not jobs:
            logger.info("No custom jobs to enrich")
            return {"processed": 0, "success": 0, "failed": 0}
        
        logger.info("Starting custom job enrichment", job_count=len(jobs))
        
        stats = {"processed": 0, "success": 0, "failed": 0}
        semaphore = asyncio.Semaphore(concurrency)
        pool = await self.get_browser_pool()
        
        async def enrich_one(job_row):
            async with semaphore:
                try:
                    description = await extract_description_from_page(
                        job_row.source_url,
                        browser_pool=pool,
                        render=True,
                    )
                    
                    if description and len(description) > 50:
                        await self.db.execute(text('''
                            UPDATE jobs
                            SET description = :desc
                            WHERE id = :id
                        '''), {"id": job_row.id, "desc": description[:10000]})
                        await self.db.commit()
                        
                        stats["success"] += 1
                        logger.debug(
                            "Enriched custom job",
                            company=job_row.company_name,
                            desc_length=len(description),
                        )
                    else:
                        stats["failed"] += 1
                        
                    stats["processed"] += 1
                    
                except Exception as e:
                    logger.warning(
                        "Custom enrichment failed",
                        url=job_row.source_url,
                        error=str(e),
                    )
                    stats["failed"] += 1
                    stats["processed"] += 1
        
        tasks = [enrich_one(j) for j in jobs]
        await asyncio.gather(*tasks)
        
        logger.info("Custom enrichment complete", **stats)
        return stats


# ============================================================================
# Service Functions
# ============================================================================

async def crawl_custom_companies(
    limit: int = 50,
    mark_exhausted: bool = True,
) -> dict:
    """
    Crawl companies with custom career pages.
    
    Convenience function that handles session lifecycle.
    
    Args:
        limit: Max companies to crawl
        mark_exhausted: If True, first mark exhausted ATS detection as 'custom'
        
    Returns:
        Dict with crawl statistics
    """
    from app.db import async_session_factory
    
    async with async_session_factory() as db:
        service = CustomCrawlerService(db)
        
        try:
            # Optionally mark exhausted companies as custom
            if mark_exhausted:
                marked = await service.mark_exhausted_as_custom()
                if marked > 0:
                    logger.info("Marked exhausted as custom", count=marked)
            
            # Crawl custom companies
            return await service.crawl_custom_companies(limit=limit)
            
        finally:
            await service.close()


async def enrich_custom_jobs(limit: int = 100) -> dict:
    """
    Enrich jobs from custom companies.
    
    Convenience function that handles session lifecycle.
    """
    from app.db import async_session_factory
    
    async with async_session_factory() as db:
        service = CustomCrawlerService(db)
        
        try:
            return await service.enrich_custom_jobs(limit=limit)
        finally:
            await service.close()
