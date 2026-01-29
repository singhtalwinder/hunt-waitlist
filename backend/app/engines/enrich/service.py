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
            
            # Route to appropriate enrichment method
            if company.ats_type == "greenhouse":
                return await self._enrich_greenhouse(job, company, client)
            elif company.ats_type == "lever":
                return await self._enrich_lever(job, company, client)
            elif company.ats_type == "ashby":
                return await self._enrich_ashby(job, company, client)
            elif company.ats_type == "workable":
                return await self._enrich_workable(job, company, client)
            else:
                return await self._enrich_generic(job, client)
                
        except Exception as e:
            logger.debug(f"Failed to enrich job {job.id}: {e}")
            return False

    async def _enrich_greenhouse(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Greenhouse API."""
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
            if resp.status_code != 200:
                return False
            
            html = resp.text
            
            # Extract description from the posting body
            # Lever uses specific div classes for job content
            desc_match = re.search(
                r'<div[^>]*class="[^"]*posting-description[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL | re.IGNORECASE
            )
            if desc_match:
                content = desc_match.group(1)
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
        # Ashby job URLs can contain the job ID
        if not job.source_url:
            return False
        
        # Try to get job details from Ashby API
        # First, try the job board API with job listing endpoint
        try:
            # Get all jobs and find matching one
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_identifier}"
            resp = await client.get(api_url)
            
            if resp.status_code != 200:
                return False
            
            data = resp.json()
            jobs_data = data.get("jobs", [])
            
            # Find matching job by URL
            for jd in jobs_data:
                job_url = jd.get("jobUrl") or jd.get("applyUrl", "")
                if job_url and job_url in job.source_url or job.source_url in job_url:
                    # Found matching job
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
            
            return False
            
        except Exception as e:
            logger.debug(f"Ashby enrichment failed: {e}")
            return False

    async def _enrich_workable(
        self, job: Job, company: Company, client: httpx.AsyncClient
    ) -> bool:
        """Enrich from Workable v2 API."""
        if not job.source_url or not company.ats_identifier:
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
            if resp.status_code != 200:
                return False
            
            html = resp.text
            
            # Try to find job description in common patterns
            patterns = [
                r'<div[^>]*class="[^"]*job-description[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                r'<article[^>]*>(.*?)</article>',
                r'"description"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in patterns:
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
    ) -> dict:
        """Enrich jobs that are missing descriptions in continuous batches.
        
        Processes jobs in batches and keeps checking for new jobs until none remain.
        This ensures jobs added during processing are also picked up.
        
        Args:
            ats_type: Optional ATS type filter
            limit: Optional total limit (None = no limit, process all)
            concurrency: Max concurrent enrichment operations per batch
            batch_size: Number of jobs to fetch per batch
        """
        from app.db import async_session_factory
        
        results = {"success": 0, "failed": 0, "batches": 0}
        total_processed = 0
        
        while True:
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
                )
                
                if ats_type:
                    query = query.where(Company.ats_type == ats_type)
                
                query = query.limit(fetch_limit)
                
                result = await db.execute(query)
                jobs_to_enrich = result.fetchall()
            
            # No more jobs to enrich - we're done
            if not jobs_to_enrich:
                logger.info("No more jobs to enrich")
                break
            
            results["batches"] += 1
            logger.info(f"Enrichment batch {results['batches']}: processing {len(jobs_to_enrich)} jobs")
            
            semaphore = asyncio.Semaphore(concurrency)
            batch_success = 0
            batch_failed = 0
            
            async def enrich_with_semaphore(job: Job, company: Company):
                nonlocal batch_success, batch_failed
                async with semaphore:
                    # Use separate session for each job
                    async with async_session_factory() as db:
                        # Re-fetch job in this session
                        result = await db.execute(select(Job).where(Job.id == job.id))
                        job_in_session = result.scalar_one_or_none()
                        
                        if not job_in_session:
                            batch_failed += 1
                            return
                        
                        # Skip if already enriched (race condition protection)
                        if job_in_session.description:
                            return
                        
                        service = JobEnrichmentService(db)
                        try:
                            success = await service.enrich_job(job_in_session, company)
                            if success:
                                await db.commit()
                                batch_success += 1
                            else:
                                batch_failed += 1
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
