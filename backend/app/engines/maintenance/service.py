"""Maintenance Engine Service.

This service re-crawls companies to:
1. Verify existing jobs still exist on the ATS
2. Find new jobs that have been posted
3. Delist jobs that have been removed (set is_active=false, not delete)
4. Maintain accurate logs for all operations

Supports both:
- Standard ATS companies (Greenhouse, Lever, Ashby, Workable, etc.)
- Custom career pages (using Playwright + LLM extraction)
"""

import asyncio
from datetime import datetime
from typing import Optional, Set
from uuid import UUID

import structlog
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory, Company, Job, MaintenanceRun
from app.engines.crawl.rate_limiter import RateLimiter

logger = structlog.get_logger()

# ATS types that use standard API extraction
STANDARD_ATS_TYPES = {"greenhouse", "lever", "ashby", "workable", "bamboohr", "recruitee", "smartrecruiters", "jobvite"}

# Custom types that need Playwright
CUSTOM_ATS_TYPES = {"custom", "playwright"}


async def log_to_maintenance_run(
    db: AsyncSession,
    run_id: UUID,
    level: str,
    msg: str,
    current_step: Optional[str] = None,
    data: Optional[dict] = None,
) -> None:
    """Add a log entry to a maintenance run."""
    log_entry = {
        "ts": datetime.utcnow().isoformat(),
        "level": level,
        "msg": msg,
    }
    if data:
        log_entry["data"] = data

    await db.execute(text("""
        UPDATE maintenance_runs
        SET logs = logs || :log_entry::jsonb
        WHERE id = :run_id
    """), {"run_id": run_id, "log_entry": f"[{str(log_entry).replace(\"'\", '\"')}]"})
    
    if current_step:
        await db.execute(text("""
            UPDATE maintenance_runs SET current_step = :step WHERE id = :run_id
        """), {"run_id": run_id, "step": current_step})
    
    await db.commit()


async def check_if_cancelled(db: AsyncSession, run_id: UUID) -> bool:
    """Check if a maintenance run has been cancelled."""
    result = await db.execute(text("""
        SELECT status FROM maintenance_runs WHERE id = :run_id
    """), {"run_id": run_id})
    row = result.fetchone()
    return row and row[0] == "cancelled"


class MaintenanceEngine:
    """Engine for verifying and maintaining job listings."""

    def __init__(self, db: AsyncSession, rate_limiter: Optional[RateLimiter] = None):
        self.db = db
        self.rate_limiter = rate_limiter or RateLimiter()

    async def close(self):
        """Close engine resources."""
        pass

    async def create_maintenance_run(
        self,
        run_type: str = "full",
        ats_type: Optional[str] = None,
    ) -> MaintenanceRun:
        """Create a new maintenance run for tracking."""
        run = MaintenanceRun(
            run_type=run_type,
            ats_type=ats_type,
            status="running",
            current_step="Initializing...",
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def run_maintenance(
        self,
        ats_type: Optional[str] = None,
        company_id: Optional[UUID] = None,
        limit: int = 100,
        run_id: Optional[UUID] = None,
        include_custom: bool = True,
    ) -> dict:
        """
        Run maintenance on companies to verify jobs.
        
        Args:
            ats_type: Filter by ATS type (e.g., "greenhouse", "lever", "custom")
            company_id: Run maintenance on a specific company only
            limit: Maximum number of companies to check
            run_id: Optional existing MaintenanceRun ID for logging
            include_custom: Include custom/Playwright companies (default True)
            
        Returns:
            dict with maintenance statistics
        """
        from app.engines.crawl.crawler import Crawler
        from app.engines.crawl.service import CrawlEngine
        
        results = {
            "companies_checked": 0,
            "jobs_verified": 0,
            "jobs_new": 0,
            "jobs_delisted": 0,
            "jobs_unchanged": 0,
            "errors": 0,
            "cancelled": False,
        }
        
        # Create run if not provided
        run = None
        if run_id:
            result = await self.db.execute(
                select(MaintenanceRun).where(MaintenanceRun.id == run_id)
            )
            run = result.scalar_one_or_none()
        
        if not run:
            run = await self.create_maintenance_run(
                run_type="ats_type" if ats_type else ("company" if company_id else "full"),
                ats_type=ats_type,
            )
            run_id = run.id
        
        try:
            # Build query for companies to check
            if company_id:
                # Single company
                query = select(Company).where(Company.id == company_id)
            else:
                # Multiple companies based on filters
                # Include both ATS and custom companies
                query = (
                    select(Company)
                    .where(Company.is_active == True)
                    .where(Company.careers_url.isnot(None))
                )
                
                if ats_type:
                    # Filter by specific ATS type (including "custom")
                    query = query.where(Company.ats_type == ats_type)
                elif include_custom:
                    # Include all companies with ATS or custom type
                    query = query.where(
                        (Company.ats_type.isnot(None)) | 
                        (Company.ats_type.in_(CUSTOM_ATS_TYPES))
                    )
                else:
                    # Only standard ATS
                    query = query.where(Company.ats_type.in_(STANDARD_ATS_TYPES))
                
                # Prioritize companies that haven't been maintained recently
                query = (
                    query
                    .order_by(text("last_maintenance_at NULLS FIRST"))
                    .limit(limit)
                )
            
            result = await self.db.execute(query)
            companies = result.scalars().all()
            total_companies = len(companies)
            
            if not companies:
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    "No companies to maintain",
                    current_step="Completed - no companies",
                )
                run.status = "completed"
                run.completed_at = datetime.utcnow()
                await self.db.commit()
                return results
            
            await log_to_maintenance_run(
                self.db, run_id, "info",
                f"Starting maintenance for {total_companies} companies",
                current_step=f"Checking 0/{total_companies}",
                data={"total": total_companies, "ats_type": ats_type},
            )
            
            # Process each company
            for i, company in enumerate(companies):
                # Check for cancellation
                if await check_if_cancelled(self.db, run_id):
                    results["cancelled"] = True
                    await log_to_maintenance_run(
                        self.db, run_id, "warn",
                        "Maintenance cancelled by user",
                        current_step="Cancelled",
                    )
                    break
                
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"Checking {company.name}...",
                    current_step=f"Checking {i+1}/{total_companies}: {company.name}",
                )
                
                try:
                    # Route to appropriate handler based on ATS type
                    if company.ats_type in CUSTOM_ATS_TYPES:
                        company_result = await self._maintain_custom_company(company, run_id)
                    elif company.ats_type in STANDARD_ATS_TYPES:
                        company_result = await self._maintain_company(company, run_id)
                    else:
                        # Unknown ATS type - try standard first, fallback to custom
                        company_result = await self._maintain_company(company, run_id)
                        if company_result.get("error") and "fetch failed" in str(company_result.get("error", "")).lower():
                            # Retry with custom handler
                            company_result = await self._maintain_custom_company(company, run_id)
                    
                    results["companies_checked"] += 1
                    results["jobs_verified"] += company_result.get("verified", 0)
                    results["jobs_new"] += company_result.get("new", 0)
                    results["jobs_delisted"] += company_result.get("delisted", 0)
                    results["jobs_unchanged"] += company_result.get("unchanged", 0)
                    
                    if company_result.get("error"):
                        results["errors"] += 1
                    
                    # Update run stats
                    run.companies_checked = results["companies_checked"]
                    run.jobs_verified = results["jobs_verified"]
                    run.jobs_new = results["jobs_new"]
                    run.jobs_delisted = results["jobs_delisted"]
                    run.jobs_unchanged = results["jobs_unchanged"]
                    run.errors = results["errors"]
                    await self.db.commit()
                    
                except Exception as e:
                    logger.error(f"Maintenance error for {company.name}: {e}")
                    results["errors"] += 1
                    await log_to_maintenance_run(
                        self.db, run_id, "error",
                        f"Error maintaining {company.name}: {str(e)[:100]}",
                        data={"company": company.name, "error": str(e)[:200]},
                    )
            
            # Finalize run
            if not results["cancelled"]:
                run.status = "completed"
                run.current_step = None
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"Maintenance complete: {results['companies_checked']} companies, "
                    f"{results['jobs_new']} new, {results['jobs_delisted']} delisted",
                    data=results,
                )
            else:
                run.status = "cancelled"
            
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Maintenance run failed: {e}")
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            raise
        
        return results

    async def _maintain_company(
        self,
        company: Company,
        run_id: UUID,
    ) -> dict:
        """
        Maintain a single company's job listings.
        
        This method:
        1. Re-crawls the company's ATS to get current jobs
        2. Compares with existing jobs in our database
        3. Delists jobs that no longer exist
        4. Adds new jobs that were discovered
        5. Updates last_verified_at for existing jobs
        
        Returns:
            dict with stats: verified, new, delisted, unchanged, error
        """
        from app.engines.crawl.crawler import Crawler
        from app.engines.extract.greenhouse import GreenhouseExtractor
        from app.engines.extract.lever import LeverExtractor
        from app.engines.extract.ashby import AshbyExtractor
        from app.engines.extract.workable import WorkableExtractor
        from app.engines.extract.generic import GenericExtractor
        from app.engines.normalize.service import NormalizationEngine
        
        result = {
            "verified": 0,
            "new": 0,
            "delisted": 0,
            "unchanged": 0,
            "error": None,
        }
        
        if not company.careers_url:
            result["error"] = "No careers URL"
            return result
        
        # Get the URL to fetch based on ATS type
        fetch_url = self._get_ats_url(company)
        
        try:
            # Fetch current jobs from the ATS
            crawler = Crawler(rate_limiter=self.rate_limiter)
            try:
                html, status_code = await crawler.fetch(fetch_url)
            finally:
                await crawler.close()
            
            if not html or status_code not in (200, 201):
                result["error"] = f"Fetch failed (status: {status_code})"
                await log_to_maintenance_run(
                    self.db, run_id, "warn",
                    f"{company.name}: fetch failed (status {status_code})",
                    data={"company": company.name, "url": fetch_url, "status": status_code},
                )
                return result
            
            # Extract jobs from the HTML/JSON response
            extractors = {
                "greenhouse": GreenhouseExtractor(),
                "lever": LeverExtractor(),
                "ashby": AshbyExtractor(),
                "workable": WorkableExtractor(),
            }
            
            extractor = extractors.get(company.ats_type, GenericExtractor())
            
            raw_jobs = await extractor.extract(
                html=html,
                url=fetch_url,
                company_identifier=company.ats_identifier,
            )
            
            # Get current job URLs from the ATS
            current_job_urls: Set[str] = set()
            for job in raw_jobs:
                if job.source_url:
                    # Normalize URL for comparison
                    current_job_urls.add(self._normalize_url(job.source_url))
            
            # Get our existing active jobs for this company
            existing_jobs_result = await self.db.execute(
                select(Job)
                .where(Job.company_id == company.id)
                .where(Job.is_active == True)
            )
            existing_jobs = existing_jobs_result.scalars().all()
            existing_job_urls: Set[str] = {
                self._normalize_url(job.source_url) for job in existing_jobs
            }
            
            # Find jobs to delist (in our DB but not on ATS anymore)
            jobs_to_delist = existing_job_urls - current_job_urls
            
            # Find new jobs (on ATS but not in our DB)
            new_job_urls = current_job_urls - existing_job_urls
            
            # Jobs that still exist (verify them)
            verified_urls = existing_job_urls & current_job_urls
            
            # Delist jobs that are no longer on the ATS
            if jobs_to_delist:
                for job in existing_jobs:
                    normalized_url = self._normalize_url(job.source_url)
                    if normalized_url in jobs_to_delist:
                        job.is_active = False
                        job.delisted_at = datetime.utcnow()
                        job.delist_reason = "removed_from_ats"
                        result["delisted"] += 1
                
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: delisted {result['delisted']} jobs no longer on ATS",
                    data={
                        "company": company.name,
                        "delisted": result["delisted"],
                        "sample_urls": list(jobs_to_delist)[:3],
                    },
                )
            
            # Update last_verified_at for jobs that still exist
            for job in existing_jobs:
                normalized_url = self._normalize_url(job.source_url)
                if normalized_url in verified_urls:
                    job.last_verified_at = datetime.utcnow()
                    result["verified"] += 1
            
            # Add new jobs
            if new_job_urls:
                normalize_engine = NormalizationEngine(self.db)
                
                for raw_job in raw_jobs:
                    if raw_job.source_url and self._normalize_url(raw_job.source_url) in new_job_urls:
                        try:
                            job = await normalize_engine.normalize_and_save(
                                raw_job=raw_job,
                                company_id=company.id,
                                snapshot_id=None,
                            )
                            if job:
                                result["new"] += 1
                        except Exception as e:
                            logger.debug(f"Failed to add new job: {e}")
                
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: added {result['new']} new jobs",
                    data={
                        "company": company.name,
                        "new_jobs": result["new"],
                    },
                )
            
            # Jobs that stayed the same (not new, not delisted, but verified)
            result["unchanged"] = result["verified"]
            
            # Update company's last_maintenance_at
            company.last_maintenance_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Log summary
            if result["delisted"] > 0 or result["new"] > 0:
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: +{result['new']} new, -{result['delisted']} delisted, {result['verified']} verified",
                    data=result,
                )
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Maintenance failed for {company.name}: {e}")
        
        return result

    async def _maintain_custom_company(
        self,
        company: Company,
        run_id: UUID,
    ) -> dict:
        """
        Maintain a custom company's job listings using Playwright.
        
        For companies without a recognized ATS, we use Playwright to render
        the career page and LLM to extract job listings.
        
        Returns:
            dict with stats: verified, new, delisted, unchanged, error
        """
        from app.engines.extract.playwright_extractor import PlaywrightExtractor
        from app.engines.render.browser import get_browser_pool
        from app.engines.normalize.service import NormalizationEngine
        
        result = {
            "verified": 0,
            "new": 0,
            "delisted": 0,
            "unchanged": 0,
            "error": None,
        }
        
        if not company.careers_url:
            result["error"] = "No careers URL"
            return result
        
        try:
            # Get browser pool and extractor
            browser_pool = await get_browser_pool()
            extractor = PlaywrightExtractor(browser_pool)
            
            # Extract jobs using Playwright + LLM
            await log_to_maintenance_run(
                self.db, run_id, "info",
                f"{company.name}: Using Playwright to extract jobs",
                data={"company": company.name, "url": company.careers_url},
            )
            
            raw_jobs = await extractor.extract_with_render(company.careers_url)
            
            if not raw_jobs:
                await log_to_maintenance_run(
                    self.db, run_id, "warn",
                    f"{company.name}: No jobs extracted from custom page",
                    data={"company": company.name},
                )
                # Check if all existing jobs should be delisted
                existing_jobs_result = await self.db.execute(
                    select(Job)
                    .where(Job.company_id == company.id)
                    .where(Job.is_active == True)
                )
                existing_jobs = existing_jobs_result.scalars().all()
                
                # Don't delist all jobs if extraction failed - might be a transient error
                # Just mark company as checked
                company.last_maintenance_at = datetime.utcnow()
                await self.db.commit()
                return result
            
            # Get current job URLs/titles from the extraction
            current_jobs: Set[str] = set()
            for job in raw_jobs:
                # Use title + source_url hash for matching custom jobs
                key = self._normalize_custom_job_key(job.title, getattr(job, 'source_url', None))
                current_jobs.add(key)
            
            # Get our existing active jobs for this company
            existing_jobs_result = await self.db.execute(
                select(Job)
                .where(Job.company_id == company.id)
                .where(Job.is_active == True)
            )
            existing_jobs = existing_jobs_result.scalars().all()
            existing_job_keys: Set[str] = {
                self._normalize_custom_job_key(job.title, job.source_url) 
                for job in existing_jobs
            }
            
            # Find jobs to delist
            jobs_to_delist = existing_job_keys - current_jobs
            
            # Find new jobs
            new_job_keys = current_jobs - existing_job_keys
            
            # Jobs that still exist
            verified_keys = existing_job_keys & current_jobs
            
            # Delist jobs that are no longer found
            if jobs_to_delist:
                for job in existing_jobs:
                    key = self._normalize_custom_job_key(job.title, job.source_url)
                    if key in jobs_to_delist:
                        job.is_active = False
                        job.delisted_at = datetime.utcnow()
                        job.delist_reason = "removed_from_ats"
                        result["delisted"] += 1
                
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: delisted {result['delisted']} jobs no longer found",
                    data={"company": company.name, "delisted": result["delisted"]},
                )
            
            # Update last_verified_at for jobs that still exist
            for job in existing_jobs:
                key = self._normalize_custom_job_key(job.title, job.source_url)
                if key in verified_keys:
                    job.last_verified_at = datetime.utcnow()
                    result["verified"] += 1
            
            # Add new jobs
            if new_job_keys:
                normalize_engine = NormalizationEngine(self.db)
                
                for raw_job in raw_jobs:
                    key = self._normalize_custom_job_key(raw_job.title, getattr(raw_job, 'source_url', None))
                    if key in new_job_keys:
                        try:
                            job = await normalize_engine.normalize_and_save(
                                raw_job=raw_job,
                                company_id=company.id,
                                snapshot_id=None,
                            )
                            if job:
                                result["new"] += 1
                        except Exception as e:
                            logger.debug(f"Failed to add new job: {e}")
                
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: added {result['new']} new jobs",
                    data={"company": company.name, "new_jobs": result["new"]},
                )
            
            result["unchanged"] = result["verified"]
            
            # Update company's last_maintenance_at
            company.last_maintenance_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Log summary
            if result["delisted"] > 0 or result["new"] > 0:
                await log_to_maintenance_run(
                    self.db, run_id, "info",
                    f"{company.name}: +{result['new']} new, -{result['delisted']} delisted, {result['verified']} verified (custom)",
                    data=result,
                )
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Custom maintenance failed for {company.name}: {e}")
            await log_to_maintenance_run(
                self.db, run_id, "error",
                f"{company.name}: Custom maintenance error: {str(e)[:100]}",
                data={"company": company.name, "error": str(e)[:200]},
            )
        
        return result

    def _normalize_custom_job_key(self, title: str, source_url: Optional[str]) -> str:
        """Create a normalized key for matching custom jobs.
        
        For custom pages, we may not have stable URLs, so we match by title.
        """
        if source_url:
            # If we have a URL, use it (normalized)
            return self._normalize_url(source_url)
        
        # Otherwise use normalized title
        if not title:
            return ""
        return title.lower().strip()

    def _get_ats_url(self, company: Company) -> str:
        """Get the best URL to fetch based on ATS type."""
        if company.ats_type == "greenhouse" and company.ats_identifier:
            return f"https://boards-api.greenhouse.io/v1/boards/{company.ats_identifier}/jobs"
        
        if company.ats_type == "ashby" and company.ats_identifier:
            return f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_identifier}"
        
        if company.ats_type == "lever" and company.ats_identifier:
            return f"https://jobs.lever.co/{company.ats_identifier}?mode=json"
        
        if company.ats_type == "workable" and company.ats_identifier:
            return f"https://apply.workable.com/api/v1/widget/accounts/{company.ats_identifier}"
        
        return company.careers_url

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison."""
        if not url:
            return ""
        
        # Remove trailing slashes
        url = url.rstrip("/")
        
        # Remove common tracking parameters
        import re
        url = re.sub(r'\?.*$', '', url)
        
        # Lowercase for comparison
        return url.lower()


async def get_maintenance_stats(db: AsyncSession) -> dict:
    """Get maintenance statistics for the admin UI."""
    # Jobs pending verification (not verified in last 7 days)
    # Include both standard ATS and custom companies
    pending_result = await db.execute(text("""
        SELECT COUNT(*) FROM jobs j
        JOIN companies c ON j.company_id = c.id
        WHERE j.is_active = true
          AND c.is_active = true
          AND c.careers_url IS NOT NULL
          AND (j.last_verified_at IS NULL OR j.last_verified_at < NOW() - INTERVAL '7 days')
    """))
    jobs_pending_verification = pending_result.scalar() or 0
    
    # Jobs verified recently (last 24 hours)
    verified_result = await db.execute(text("""
        SELECT COUNT(*) FROM jobs
        WHERE last_verified_at > NOW() - INTERVAL '24 hours'
    """))
    jobs_verified_24h = verified_result.scalar() or 0
    
    # Jobs delisted recently (last 7 days)
    delisted_result = await db.execute(text("""
        SELECT COUNT(*) FROM jobs
        WHERE is_active = false
          AND delisted_at > NOW() - INTERVAL '7 days'
    """))
    jobs_delisted_7d = delisted_result.scalar() or 0
    
    # Companies pending maintenance (include custom pages)
    companies_pending_result = await db.execute(text("""
        SELECT COUNT(*) FROM companies
        WHERE is_active = true
          AND careers_url IS NOT NULL
          AND (last_maintenance_at IS NULL OR last_maintenance_at < NOW() - INTERVAL '7 days')
    """))
    companies_pending_maintenance = companies_pending_result.scalar() or 0
    
    # Companies maintained recently (last 24 hours)
    companies_maintained_result = await db.execute(text("""
        SELECT COUNT(*) FROM companies
        WHERE last_maintenance_at > NOW() - INTERVAL '24 hours'
    """))
    companies_maintained_24h = companies_maintained_result.scalar() or 0
    
    # Stats by ATS type (include custom and companies without ATS type)
    ats_stats_result = await db.execute(text("""
        SELECT 
            COALESCE(c.ats_type, 'unknown') as ats_type,
            COUNT(DISTINCT c.id) as companies,
            COUNT(j.id) FILTER (WHERE j.is_active = true) as active_jobs,
            COUNT(j.id) FILTER (
                WHERE j.is_active = true 
                AND (j.last_verified_at IS NULL OR j.last_verified_at < NOW() - INTERVAL '7 days')
            ) as pending_verification
        FROM companies c
        LEFT JOIN jobs j ON j.company_id = c.id
        WHERE c.is_active = true
          AND c.careers_url IS NOT NULL
        GROUP BY COALESCE(c.ats_type, 'unknown')
        ORDER BY companies DESC
    """))
    by_ats = [
        {
            "ats_type": row[0],
            "companies": row[1],
            "active_jobs": row[2] or 0,
            "pending_verification": row[3] or 0,
        }
        for row in ats_stats_result.fetchall()
    ]
    
    return {
        "jobs_pending_verification": jobs_pending_verification,
        "jobs_verified_24h": jobs_verified_24h,
        "jobs_delisted_7d": jobs_delisted_7d,
        "companies_pending_maintenance": companies_pending_maintenance,
        "companies_maintained_24h": companies_maintained_24h,
        "by_ats": by_ats,
    }
