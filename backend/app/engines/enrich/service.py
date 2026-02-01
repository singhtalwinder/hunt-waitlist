"""Job Enrichment Service - fetches full job details from source URLs."""

import asyncio
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Job, Company
from app.engines.http_client import ManagedHttpClient

logger = structlog.get_logger()


class JobEnrichmentService:
    """Service to enrich jobs with descriptions and accurate posted dates."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._http = ManagedHttpClient(timeout=15.0, json_accept=True)

    async def _get_client(self) -> httpx.AsyncClient:
        return await self._http.get_client()

    async def close(self):
        await self._http.close()

    async def enrich_job(self, job: Job, company: Company) -> bool:
        """Fetch and update job description and posted_at from source."""
        try:
            client = await self._get_client()
            success = False
            
            # Try ATS-specific enrichment first
            if company.ats_type == "greenhouse":
                success = await self._enrich_greenhouse(job, company, client)
            elif company.ats_type == "lever":
                success = await self._enrich_lever(job, company, client)
            elif company.ats_type == "ashby":
                success = await self._enrich_ashby(job, company, client)
            elif company.ats_type == "workable":
                success = await self._enrich_workable(job, company, client)
            
            # Fallback to generic enrichment if specific method failed
            # (but not if job was delisted - that's a valid outcome)
            if not success and job.is_active and not job.description:
                success = await self._enrich_generic(job, client)
            
            return success
                
        except Exception as e:
            logger.debug(f"Failed to enrich job {job.id}: {e}")
            return False

    async def _enrich_greenhouse(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Greenhouse API."""
        # Skip if no ATS identifier - can't call the API
        if not company.ats_identifier:
            logger.debug(f"No ats_identifier for company {company.id}, skipping greenhouse enrichment")
            return False
        
        url = job.source_url or ""
        
        # Extract job ID from various URL patterns:
        # 1. /jobs/1234567
        # 2. ?gh_jid=1234567
        # 3. /careers/1234567?gh_jid=1234567
        job_id = None
        
        # Try gh_jid query parameter first (most reliable)
        match = re.search(r'[?&]gh_jid=(\d+)', url)
        if match:
            job_id = match.group(1)
        
        # Try /jobs/ID pattern
        if not job_id:
            match = re.search(r'/jobs/(\d+)', url)
            if match:
                job_id = match.group(1)
        
        # Try /careers/ID pattern (some company sites)
        if not job_id:
            match = re.search(r'/careers/(\d+)', url)
            if match:
                job_id = match.group(1)
        
        if not job_id:
            logger.debug(f"No job ID found in URL: {url}")
            return False
        
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company.ats_identifier}/jobs/{job_id}"
        
        try:
            resp = await client.get(api_url)
            if resp.status_code == 404:
                # Job no longer exists on ATS - mark as delisted
                logger.debug(f"Greenhouse API 404 for {api_url} - marking job as delisted")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True  # Return True so we commit the delist
            if resp.status_code != 200:
                logger.debug(f"Greenhouse API {resp.status_code} for {api_url}")
                return False
            
            data = resp.json()
            
            # Extract description (HTML content)
            content = data.get("content", "")
            if content:
                # Strip HTML tags for plain text
                plain_text = re.sub(r'<[^>]+>', ' ', content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                job.description = plain_text[:10000]  # Limit length
            
            # Extract posted date
            updated_at = data.get("updated_at")
            if updated_at:
                try:
                    job.posted_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except:
                    pass
            
            return bool(job.description)
            
        except Exception as e:
            logger.debug(f"Greenhouse enrichment failed: {e}")
            return False

    async def _enrich_lever(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Lever job page."""
        # Lever job URLs are like https://jobs.lever.co/company/uuid
        if not job.source_url or "lever.co" not in job.source_url:
            return False
        
        try:
            resp = await client.get(job.source_url)
            if resp.status_code == 404:
                # Job no longer exists - mark as delisted
                logger.debug(f"Lever 404 for {job.source_url} - marking job as delisted")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True
            if resp.status_code != 200:
                return False
            
            html = resp.text
            
            # Try JSON-LD structured data first (current Lever format)
            # Look for "description" : "..." in the JSON-LD script
            desc_match = re.search(
                r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"|"description"\s*:\s*"([^"]*(?:<[^>]+>[^"]*)*)"',
                html, re.DOTALL
            )
            if desc_match:
                content = desc_match.group(1) or desc_match.group(2) or ""
                # Unescape JSON string
                content = content.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                # Strip HTML tags
                plain_text = re.sub(r'<[^>]+>', ' ', content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                if len(plain_text) > 50:
                    job.description = plain_text[:10000]
            
            # Fallback: try old posting-description class
            if not job.description:
                old_desc_match = re.search(
                    r'<div[^>]*class="[^"]*posting-description[^"]*"[^>]*>(.*?)</div>',
                    html, re.DOTALL | re.IGNORECASE
                )
                if old_desc_match:
                    content = old_desc_match.group(1)
                    plain_text = re.sub(r'<[^>]+>', ' ', content)
                    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                    if len(plain_text) > 50:
                        job.description = plain_text[:10000]
            
            # Look for posted date in meta tags or structured data
            date_match = re.search(r'"datePosted"\s*:\s*"([^"]+)"', html)
            if date_match:
                try:
                    job.posted_at = datetime.fromisoformat(date_match.group(1).replace("Z", "+00:00"))
                except:
                    pass
            
            return bool(job.description)
            
        except Exception as e:
            logger.debug(f"Lever enrichment failed: {e}")
            return False

    async def _enrich_ashby(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Ashby job API."""
        if not job.source_url:
            return False
        
        # Skip if no ATS identifier - needed for API fallback
        if not company.ats_identifier:
            logger.debug(f"No ats_identifier for company {company.id}, skipping ashby enrichment")
            return False
        
        # Extract job ID from URL - Ashby URLs are like:
        # https://jobs.ashbyhq.com/company/abc123-uuid-here
        job_id = None
        match = re.search(r'jobs\.ashbyhq\.com/[^/]+/([a-f0-9-]+)', job.source_url)
        if match:
            job_id = match.group(1)
        
        if not job_id:
            logger.debug(f"No job ID found in Ashby URL: {job.source_url}")
            return False
        
        try:
            # Try the individual job endpoint first (faster than fetching all jobs)
            job_api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_identifier}/posting/{job_id}"
            resp = await client.get(job_api_url)
            
            if resp.status_code == 200:
                jd = resp.json()
                desc = jd.get("descriptionHtml") or jd.get("description", "")
                if desc:
                    plain_text = re.sub(r'<[^>]+>', ' ', desc)
                    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                    job.description = plain_text[:10000]
                
                posted = jd.get("publishedAt") or jd.get("createdAt")
                if posted:
                    try:
                        job.posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                    except:
                        pass
                
                return bool(job.description)
            
            if resp.status_code == 404:
                # Job no longer exists - mark as delisted
                logger.debug(f"Ashby API 404 for job {job_id} - marking as delisted")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True
            
            # Fallback: try fetching all jobs if individual endpoint failed
            # But limit search time with early exit
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_identifier}"
            resp = await client.get(api_url)
            
            if resp.status_code == 404:
                # Company job board no longer exists
                logger.debug(f"Ashby job board not found for {company.ats_identifier}")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True
            
            if resp.status_code != 200:
                logger.debug(f"Ashby API {resp.status_code} for {api_url}")
                return False
            
            data = resp.json()
            jobs_data = data.get("jobs", [])
            
            # Find matching job by ID (much faster than URL matching)
            for jd in jobs_data:
                jd_id = jd.get("id", "")
                if jd_id and jd_id == job_id:
                    desc = jd.get("descriptionHtml") or jd.get("description", "")
                    if desc:
                        plain_text = re.sub(r'<[^>]+>', ' ', desc)
                        plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                        job.description = plain_text[:10000]
                    
                    posted = jd.get("publishedAt") or jd.get("createdAt")
                    if posted:
                        try:
                            job.posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                        except:
                            pass
                    
                    return bool(job.description)
            
            # Job ID not found in listing - likely delisted
            logger.debug(f"Ashby job {job_id} not found in listing - marking as delisted")
            job.is_active = False
            job.delisted_at = datetime.utcnow()
            job.delist_reason = "removed_from_ats"
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Ashby enrichment timeout for job {job_id}")
            return False
        except Exception as e:
            logger.debug(f"Ashby enrichment failed for job {job_id}: {e}")
            return False

    async def _enrich_workable(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Workable v2 API."""
        if not job.source_url:
            return False
        
        if not company.ats_identifier:
            logger.debug(f"No ats_identifier for company {company.id}, skipping workable enrichment")
            return False
        
        try:
            # Extract shortcode from job URL
            # URLs are like: https://apply.workable.com/j/3B788DEB41
            # or: https://apply.workable.com/company-name/j/3B788DEB41
            shortcode = None
            match = re.search(r'/j/([A-Za-z0-9]+)', job.source_url)
            if match:
                shortcode = match.group(1)
            
            if not shortcode:
                logger.debug(f"No shortcode found in Workable URL: {job.source_url}")
                return False
            
            # Use the v2 API endpoint which returns full job details including description
            api_url = f"https://apply.workable.com/api/v2/accounts/{company.ats_identifier}/jobs/{shortcode}"
            
            resp = await client.get(api_url)
            if resp.status_code == 404:
                # Job no longer exists - mark as delisted
                logger.debug(f"Workable API 404 for {api_url} - marking job as delisted")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True
            if resp.status_code != 200:
                logger.debug(f"Workable API {resp.status_code} for {api_url}")
                return False
            
            data = resp.json()
            
            # Extract description (HTML content)
            desc = data.get("description", "")
            if desc:
                plain_text = re.sub(r'<[^>]+>', ' ', desc)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                job.description = plain_text[:10000]
            
            # Extract posted date
            published = data.get("published")
            if published:
                try:
                    job.posted_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except:
                    pass
            
            return bool(job.description)
            
        except Exception as e:
            logger.debug(f"Workable enrichment failed: {e}")
            return False

    async def _enrich_generic(self, job: Job, client: httpx.AsyncClient) -> bool:
        """Generic enrichment from job page HTML."""
        if not job.source_url:
            return False
        
        try:
            resp = await client.get(job.source_url)
            if resp.status_code == 404:
                # Job page no longer exists - mark as delisted
                logger.debug(f"Generic 404 for {job.source_url} - marking job as delisted")
                job.is_active = False
                job.delisted_at = datetime.utcnow()
                job.delist_reason = "removed_from_ats"
                return True
            if resp.status_code != 200:
                return False
            
            html = resp.text
            
            # Try JSON-LD structured data first (most reliable)
            # Match "description" : "..." allowing for HTML content
            json_desc_match = re.search(
                r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"|"description"\s*:\s*"([^"]*(?:<[^>]+>[^"]*)*)"',
                html, re.DOTALL
            )
            if json_desc_match:
                content = json_desc_match.group(1) or json_desc_match.group(2) or ""
                # Decode HTML entities and unescape JSON
                import html as html_module
                content = html_module.unescape(content)
                content = content.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
                # Strip HTML tags
                plain_text = re.sub(r'<[^>]+>', ' ', content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                if len(plain_text) > 100:
                    job.description = plain_text[:10000]
            
            # Fallback: Try HTML element patterns
            if not job.description:
                html_patterns = [
                    r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*jobDescription[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*posting-description[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                    r'<section[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</section>',
                    r'<article[^>]*>(.*?)</article>',
                ]
                
                for pattern in html_patterns:
                    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                    if match:
                        content = match.group(1)
                        plain_text = re.sub(r'<[^>]+>', ' ', content)
                        plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                        if len(plain_text) > 100:
                            job.description = plain_text[:10000]
                            break
            
            # Try to find posted date
            date_patterns = [
                r'"datePosted"\s*:\s*"([^"]+)"',
                r'Posted:\s*(\d{4}-\d{2}-\d{2})',
                r'posted[^>]*>([^<]+\d{4})',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    try:
                        from dateutil import parser
                        job.posted_at = parser.parse(match.group(1))
                        break
                    except:
                        pass
            
            return bool(job.description)
            
        except Exception as e:
            logger.debug(f"Generic enrichment failed: {e}")
            return False

    async def enrich_jobs_batch(
        self,
        ats_type: Optional[str] = None,
        limit: Optional[int] = None,
        concurrency: int = 10,
        batch_size: int = 500,
        run_id: Optional[UUID] = None,
    ) -> dict:
        """Enrich jobs that are missing descriptions in continuous batches.
        
        Processes jobs in batches and keeps checking for new jobs until none remain.
        This ensures jobs added during processing are also picked up.
        
        Args:
            ats_type: Optional ATS type filter
            limit: Optional total limit (None = no limit, process all)
            concurrency: Max concurrent enrichment operations per batch
            batch_size: Number of jobs to fetch per batch
            run_id: Optional pipeline run ID for progress logging
        """
        from app.db import async_session_factory
        from app.engines.pipeline.run_logger import log_to_run, check_if_cancelled
        
        results = {"success": 0, "failed": 0, "batches": 0, "cancelled": False}
        total_processed = 0
        
        while True:
            # Check for cancellation
            if run_id:
                async with async_session_factory() as db:
                    if await check_if_cancelled(db, run_id):
                        results["cancelled"] = True
                        logger.info("Enrichment cancelled by user")
                        break
            
            # Check if we've hit the total limit
            if limit is not None and total_processed >= limit:
                break
            
            # Calculate how many to fetch this batch
            fetch_limit = batch_size
            if limit is not None:
                fetch_limit = min(batch_size, limit - total_processed)
            
            # Fetch next batch of jobs needing enrichment
            async with async_session_factory() as db:
                query = (
                    select(Job, Company)
                    .join(Company, Job.company_id == Company.id)
                    .where(Job.description.is_(None) | (Job.description == ""))
                    .where(Job.is_active == True)
                )
                
                if ats_type:
                    query = query.where(Company.ats_type == ats_type)
                
                query = query.limit(fetch_limit)
                
                result = await db.execute(query)
                jobs_to_enrich = result.fetchall()
            
            # No more jobs to enrich - we're done
            if not jobs_to_enrich:
                logger.info(f"No more jobs to enrich for {ats_type or 'all ATS types'}")
                if run_id:
                    async with async_session_factory() as db:
                        await log_to_run(
                            db, run_id, "info",
                            f"No jobs found needing enrichment for {ats_type or 'all ATS types'}",
                            current_step="No jobs to enrich"
                        )
                break
            
            results["batches"] += 1
            logger.info(f"Enrichment batch {results['batches']}: processing {len(jobs_to_enrich)} jobs")
            
            # Log batch start
            if run_id:
                async with async_session_factory() as db:
                    await log_to_run(
                        db, run_id, "info",
                        f"Starting batch {results['batches']}: {len(jobs_to_enrich)} jobs",
                        current_step=f"Batch {results['batches']}: 0/{len(jobs_to_enrich)}",
                        progress_count=results["success"],
                        failed_count=results["failed"]
                    )
            
            semaphore = asyncio.Semaphore(concurrency)
            batch_success = 0
            batch_failed = 0
            batch_processed = 0
            
            async def enrich_with_semaphore(job: Job, company: Company):
                nonlocal batch_success, batch_failed, batch_processed
                async with semaphore:
                    # Use separate session for each job
                    async with async_session_factory() as db:
                        # Re-fetch job in this session
                        result = await db.execute(select(Job).where(Job.id == job.id))
                        job_in_session = result.scalar_one_or_none()
                        
                        if not job_in_session:
                            batch_failed += 1
                            batch_processed += 1
                            return
                        
                        # Skip if already enriched (race condition protection)
                        if job_in_session.description:
                            batch_processed += 1
                            return
                        
                        service = JobEnrichmentService(db)
                        try:
                            success = await service.enrich_job(job_in_session, company)
                            if success:
                                await db.commit()
                                batch_success += 1
                            else:
                                batch_failed += 1
                            batch_processed += 1
                        finally:
                            await service.close()
            
            tasks = [enrich_with_semaphore(job, company) for job, company in jobs_to_enrich]
            await asyncio.gather(*tasks)
            
            results["success"] += batch_success
            results["failed"] += batch_failed
            total_processed += len(jobs_to_enrich)
            
            logger.info(
                f"Batch {results['batches']} complete: {batch_success} success, {batch_failed} failed. "
                f"Total: {results['success']} success, {results['failed']} failed"
            )
            
            # Log batch completion to pipeline run
            if run_id:
                async with async_session_factory() as db:
                    await log_to_run(
                        db, run_id, "info",
                        f"Batch {results['batches']} complete: {batch_success} success, {batch_failed} failed",
                        current_step=f"Batch {results['batches']} complete",
                        progress_count=results["success"],
                        failed_count=results["failed"],
                        data={"batch": results["batches"], "batch_success": batch_success, "batch_failed": batch_failed}
                    )
        
        logger.info(f"Enrichment complete: {results['batches']} batches, {results['success']} success, {results['failed']} failed")
        return results


async def enrich_jobs_without_descriptions(
    limit: Optional[int] = None,
    company_id: Optional[str] = None,
    ats_type: Optional[str] = None,
    batch_size: int = 100,
) -> int:
    """Enrich jobs that are missing descriptions in continuous batches.
    
    This is the main entry point for the enrichment task. Processes jobs in
    batches and keeps checking for new jobs until none remain.
    
    Args:
        limit: Optional maximum number of jobs to enrich (None = no limit)
        company_id: Optional - only enrich jobs from this company
        ats_type: Optional - only enrich jobs from companies with this ATS type
        batch_size: Number of jobs to process per batch
        
    Returns:
        Number of jobs successfully enriched
    """
    from app.db import async_session_factory
    
    enriched_count = 0
    total_processed = 0
    batch_num = 0
    
    while True:
        # Check if we've hit the total limit
        if limit is not None and total_processed >= limit:
            break
        
        # Calculate how many to fetch this batch
        fetch_limit = batch_size
        if limit is not None:
            fetch_limit = min(batch_size, limit - total_processed)
        
        async with async_session_factory() as db:
            # Build query for jobs needing enrichment
            query = (
                select(Job, Company)
                .join(Company, Job.company_id == Company.id)
                .where(Job.description.is_(None) | (Job.description == ""))
            )
            
            if company_id:
                query = query.where(Job.company_id == UUID(company_id))
            
            if ats_type:
                query = query.where(Company.ats_type == ats_type)
            
            query = query.limit(fetch_limit)
            
            result = await db.execute(query)
            jobs_to_enrich = result.fetchall()
            
            if not jobs_to_enrich:
                logger.info("No more jobs to enrich")
                break
            
            batch_num += 1
            logger.info(f"Enrichment batch {batch_num}: processing {len(jobs_to_enrich)} jobs")
            
            service = JobEnrichmentService(db)
            batch_enriched = 0
            
            try:
                for job, company in jobs_to_enrich:
                    try:
                        # Skip if already enriched (race condition protection)
                        if job.description:
                            continue
                        
                        success = await service.enrich_job(job, company)
                        if success:
                            batch_enriched += 1
                            enriched_count += 1
                            # Commit each successful enrichment
                            await db.commit()
                    except Exception as e:
                        logger.warning(f"Failed to enrich job {job.id}: {e}")
                        await db.rollback()
            finally:
                await service.close()
            
            total_processed += len(jobs_to_enrich)
            logger.info(f"Batch {batch_num} complete: {batch_enriched} enriched. Total: {enriched_count}")
    
    logger.info(f"Enrichment complete: {batch_num} batches, {enriched_count} jobs enriched")
    return enriched_count
