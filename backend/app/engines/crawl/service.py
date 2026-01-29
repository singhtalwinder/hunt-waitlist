"""Crawl Engine - main crawling service."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse
from uuid import UUID

import structlog
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import Company, CrawlSnapshot
from app.engines.crawl.crawler import Crawler
from app.engines.crawl.rate_limiter import RateLimiter
from app.engines.discovery.ats_detector import (
    detect_ats_from_url,
    detect_ats_from_html,
    extract_identifier_from_html,
)

settings = get_settings()
logger = structlog.get_logger()


class CrawlEngine:
    """Engine for crawling company career pages."""

    def __init__(self, db: AsyncSession, rate_limiter: Optional[RateLimiter] = None):
        self.db = db
        self.rate_limiter = rate_limiter or RateLimiter()
        self.crawler = Crawler(rate_limiter=self.rate_limiter)

    async def close(self):
        """Close crawler resources."""
        await self.crawler.close()

    async def crawl_company(self, company_id: UUID) -> dict:
        """Crawl a single company's career page.
        
        Returns:
            dict with keys:
                - status: "success", "skipped", or "error"
                - snapshot: CrawlSnapshot if successful
                - error: error message if failed
                - reason: reason code for failure
        """
        # Get company
        result = await self.db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

        if not company:
            logger.warning("Company not found", company_id=str(company_id))
            return {"status": "error", "error": "Company not found", "reason": "not_found"}

        if not company.careers_url:
            logger.warning("Company has no careers URL", company=company.name)
            return {"status": "error", "error": "No careers URL", "reason": "no_careers_url"}

        # If company has no ATS type, try to discover it first
        if not company.ats_type:
            await self._discover_ats(company)
            await self.db.commit()
            await self.db.refresh(company)

        # Determine the best URL to fetch based on ATS type
        fetch_url = self._get_ats_url(company)
        logger.info("Crawling company", company=company.name, url=fetch_url)

        try:
            # Crawl the page or API
            html, status_code = await self.crawler.fetch(fetch_url)

            if not html:
                # If we got a 404 and company has ATS configured, try to rediscover
                if status_code == 404 and company.ats_type and company.ats_identifier:
                    logger.info(
                        "ATS API returned 404, attempting to rediscover identifier",
                        company=company.name,
                        ats_type=company.ats_type,
                        old_identifier=company.ats_identifier,
                    )
                    
                    # Try to rediscover the ATS from the careers page
                    rediscovered = await self._rediscover_ats_identifier(company)
                    
                    if rediscovered:
                        await self.db.commit()
                        await self.db.refresh(company)
                        
                        # Retry with the new identifier
                        fetch_url = self._get_ats_url(company)
                        logger.info(
                            "Retrying with rediscovered identifier",
                            company=company.name,
                            new_identifier=company.ats_identifier,
                            new_url=fetch_url,
                        )
                        html, status_code = await self.crawler.fetch(fetch_url)
                        
                        if html:
                            # Success - continue with normal flow below
                            pass
                        else:
                            error_msg = f"Failed to fetch after rediscovery (status: {status_code})"
                            logger.warning(
                                "Still failed after rediscovery",
                                company=company.name,
                                status_code=status_code,
                            )
                            return {"status": "error", "error": error_msg, "reason": "fetch_failed_after_rediscovery", "status_code": status_code}
                    else:
                        error_msg = f"Failed to fetch (status: {status_code}) and could not rediscover ATS"
                        logger.warning(
                            "Failed to fetch and rediscover ATS",
                            company=company.name,
                            status_code=status_code,
                        )
                        return {"status": "error", "error": error_msg, "reason": "fetch_failed", "status_code": status_code}
                else:
                    error_msg = f"Failed to fetch (status: {status_code})"
                    logger.warning(
                        "Failed to fetch page",
                        company=company.name,
                        status_code=status_code,
                    )
                    return {"status": "error", "error": error_msg, "reason": "fetch_failed", "status_code": status_code}

            # Calculate hash for change detection
            html_hash = hashlib.sha256(html.encode()).hexdigest()

            # Check if content changed
            last_snapshot = await self.db.execute(
                select(CrawlSnapshot)
                .where(CrawlSnapshot.company_id == company_id)
                .order_by(CrawlSnapshot.crawled_at.desc())
                .limit(1)
            )
            last = last_snapshot.scalar_one_or_none()

            if last and last.html_hash == html_hash:
                logger.info("No changes detected", company=company.name)
                # Update last_crawled_at but don't create new snapshot
                company.last_crawled_at = datetime.utcnow()
                await self.db.commit()
                return {"status": "success", "snapshot": last, "unchanged": True}

            # Create new snapshot
            snapshot = CrawlSnapshot(
                company_id=company.id,
                url=fetch_url,
                html_hash=html_hash,
                html_content=html,
                status_code=status_code,
                rendered=False,
            )
            self.db.add(snapshot)

            # Update company
            company.last_crawled_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(snapshot)

            logger.info(
                "Crawl complete",
                company=company.name,
                snapshot_id=str(snapshot.id),
                html_size=len(html),
            )

            # Trigger extraction for the new snapshot
            jobs_extracted = await self._extract_jobs(company, snapshot)

            return {"status": "success", "snapshot": snapshot, "jobs_extracted": jobs_extracted}

        except Exception as e:
            logger.error("Crawl failed", company=company.name, error=str(e))
            return {"status": "error", "error": str(e), "reason": "exception"}

    # Mapping of ATS types to their canonical job board URL formats
    ATS_CAREERS_URL_TEMPLATES = {
        "greenhouse": "https://boards.greenhouse.io/{identifier}",
        "ashby": "https://jobs.ashbyhq.com/{identifier}",
        "lever": "https://jobs.lever.co/{identifier}",
        "workable": "https://apply.workable.com/{identifier}",
        "recruitee": "https://{identifier}.recruitee.com",
        "bamboohr": "https://{identifier}.bamboohr.com/careers",
        "smartrecruiters": "https://jobs.smartrecruiters.com/{identifier}",
        "jobvite": "https://jobs.jobvite.com/{identifier}",
    }

    def _update_careers_url_for_ats(self, company: Company, new_identifier: str) -> None:
        """Update the careers URL to match the new ATS identifier.
        
        This ensures the careers_url stays in sync when we rediscover
        a new identifier for a company.
        """
        if company.ats_type in self.ATS_CAREERS_URL_TEMPLATES:
            new_url = self.ATS_CAREERS_URL_TEMPLATES[company.ats_type].format(
                identifier=new_identifier
            )
            logger.info(
                "Updating careers URL for rediscovered identifier",
                company=company.name,
                old_url=company.careers_url,
                new_url=new_url,
            )
            company.careers_url = new_url

    def _get_ats_url(self, company: Company) -> str:
        """Get the best URL to fetch based on ATS type."""
        # For ATS with known APIs, use the API instead of HTML page
        if company.ats_type == "greenhouse" and company.ats_identifier:
            return f"https://boards-api.greenhouse.io/v1/boards/{company.ats_identifier}/jobs"
        
        if company.ats_type == "ashby" and company.ats_identifier:
            return f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_identifier}"
        
        # For Lever, use the Lever API with JSON mode
        if company.ats_type == "lever" and company.ats_identifier:
            return f"https://jobs.lever.co/{company.ats_identifier}?mode=json"
        
        # For Workable, use the widget API
        if company.ats_type == "workable" and company.ats_identifier:
            return f"https://apply.workable.com/api/v1/widget/accounts/{company.ats_identifier}"
        
        # For all others (including ATS without identifier), use the careers page
        return company.careers_url

    async def _discover_ats(self, company: Company) -> Tuple[Optional[str], Optional[str]]:
        """
        Discover the ATS type for a company by crawling their careers page.
        
        This method:
        1. Fetches the careers page
        2. Analyzes HTML for embedded ATS patterns
        3. Follows job links to detect ATS redirects
        4. Updates the company record with discovered ATS
        
        Returns:
            Tuple of (ats_type, ats_identifier)
        """
        if not company.careers_url:
            return None, None

        logger.info("Discovering ATS for company", company=company.name)

        try:
            # Fetch the careers page
            html, status_code = await self.crawler.fetch(company.careers_url)
            
            if not html or status_code != 200:
                logger.warning(
                    "Failed to fetch careers page for ATS discovery",
                    company=company.name,
                    status_code=status_code,
                )
                return None, None

            # Step 1: Check if the URL itself indicates an ATS
            ats_type, ats_identifier = detect_ats_from_url(company.careers_url)
            if ats_type:
                company.ats_type = ats_type
                company.ats_identifier = ats_identifier
                logger.info(
                    "ATS discovered from URL",
                    company=company.name,
                    ats_type=ats_type,
                    ats_identifier=ats_identifier,
                )
                return ats_type, ats_identifier

            # Step 2: Analyze the HTML content for ATS patterns
            ats_type = detect_ats_from_html(html)
            if ats_type:
                ats_identifier = extract_identifier_from_html(html, ats_type)
                company.ats_type = ats_type
                company.ats_identifier = ats_identifier
                logger.info(
                    "ATS discovered from HTML patterns",
                    company=company.name,
                    ats_type=ats_type,
                    ats_identifier=ats_identifier,
                )
                return ats_type, ats_identifier

            # Step 3: Parse HTML and look for job links
            soup = BeautifulSoup(html, "lxml")
            job_links = self._find_job_links(soup, company.careers_url)

            if job_links:
                # Follow the first few job links to detect ATS
                for job_link in job_links[:3]:  # Check up to 3 job links
                    ats_type, ats_identifier = await self._detect_ats_from_redirect(job_link)
                    if ats_type:
                        company.ats_type = ats_type
                        company.ats_identifier = ats_identifier
                        logger.info(
                            "ATS discovered from job link redirect",
                            company=company.name,
                            ats_type=ats_type,
                            ats_identifier=ats_identifier,
                            job_link=job_link,
                        )
                        return ats_type, ats_identifier

            # Step 4: Check for embedded iframes
            ats_type, ats_identifier = self._check_embedded_iframes(soup)
            if ats_type:
                company.ats_type = ats_type
                company.ats_identifier = ats_identifier
                logger.info(
                    "ATS discovered from embedded iframe",
                    company=company.name,
                    ats_type=ats_type,
                    ats_identifier=ats_identifier,
                )
                return ats_type, ats_identifier

            # Step 5: Check for embedded scripts (like Ashby embed)
            ats_type, ats_identifier = self._check_embedded_scripts(soup)
            if ats_type:
                company.ats_type = ats_type
                company.ats_identifier = ats_identifier
                logger.info(
                    "ATS discovered from embedded script",
                    company=company.name,
                    ats_type=ats_type,
                    ats_identifier=ats_identifier,
                )
                return ats_type, ats_identifier

            logger.info("No ATS discovered", company=company.name)
            return None, None

        except Exception as e:
            logger.error(
                "ATS discovery failed",
                company=company.name,
                error=str(e),
            )
            return None, None

    def _find_job_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find potential job listing links on a careers page."""
        job_links = []
        
        # Common patterns for job links
        link_patterns = [
            'a[href*="/job"]',
            'a[href*="/position"]',
            'a[href*="/opening"]',
            'a[href*="/career"]',
            'a[href*="/apply"]',
            'a[href*="greenhouse"]',
            'a[href*="lever"]',
            'a[href*="ashby"]',
            'a[href*="workable"]',
            'a[href*="bamboohr"]',
            'a[href*="jobvite"]',
            'a[href*="icims"]',
            'a[href*="smartrecruiters"]',
            'a[href*="recruitee"]',
        ]
        
        seen_urls = set()
        for pattern in link_patterns:
            for link in soup.select(pattern):
                href = link.get("href", "")
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                
                full_url = urljoin(base_url, href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    job_links.append(full_url)

        return job_links[:10]  # Limit to 10 links

    async def _detect_ats_from_redirect(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Follow a URL and detect ATS from the final redirect destination."""
        try:
            # Use HEAD request to get final URL without downloading content
            response = await self.crawler.client.head(url, follow_redirects=True)
            final_url = str(response.url)
            
            # Check the final URL for ATS patterns
            ats_type, ats_identifier = detect_ats_from_url(final_url)
            if ats_type:
                return ats_type, ats_identifier
            
            # If HEAD didn't work well, try GET on the final URL
            if response.status_code != 200:
                html, _ = await self.crawler.fetch(url)
                if html:
                    ats_type = detect_ats_from_html(html)
                    if ats_type:
                        ats_identifier = extract_identifier_from_html(html, ats_type)
                        return ats_type, ats_identifier
                        
        except Exception as e:
            logger.debug(f"Failed to detect ATS from redirect: {e}")
        
        return None, None

    def _check_embedded_iframes(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """Check for ATS embedded via iframes."""
        iframes = soup.find_all("iframe")
        
        for iframe in iframes:
            src = iframe.get("src", "")
            if src:
                ats_type, ats_identifier = detect_ats_from_url(src)
                if ats_type:
                    return ats_type, ats_identifier
        
        return None, None

    def _check_embedded_scripts(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """Check for ATS embedded via script tags.
        
        Many ATS providers offer embed scripts that companies include on their
        careers pages. These scripts often contain the company identifier in the URL.
        
        Examples:
        - Ashby: <script src="https://jobs.ashbyhq.com/company-name/embed">
        - Greenhouse: <script src="https://boards.greenhouse.io/embed/job_board/js?for=company">
        - Lever: <script src="https://jobs.lever.co/company/embed">
        - Workable: <script src="https://www.workable.com/integrations/embed/company">
        """
        scripts = soup.find_all("script")
        
        # Script src patterns for various ATS
        embed_patterns = [
            # Ashby embed patterns
            (r'jobs\.ashbyhq\.com/([^/]+)/embed', "ashby"),
            (r'jobs\.ashbyhq\.com/([^/"\']+)', "ashby"),
            # Greenhouse embed patterns
            (r'boards\.greenhouse\.io/embed/job_board[^"\']*for=([^&"\']+)', "greenhouse"),
            (r'boards\.greenhouse\.io/([^/"\']+)', "greenhouse"),
            (r'boards-api\.greenhouse\.io/v1/boards/([^/"\']+)', "greenhouse"),
            # Lever embed patterns
            (r'jobs\.lever\.co/([^/"\']+)/embed', "lever"),
            (r'jobs\.lever\.co/([^/"\']+)', "lever"),
            # Workable embed patterns
            (r'apply\.workable\.com/([^/"\']+)', "workable"),
            (r'workable\.com/integrations/embed/([^/"\']+)', "workable"),
            # Recruitee embed patterns
            (r'([^./]+)\.recruitee\.com', "recruitee"),
            # BambooHR embed patterns
            (r'([^./]+)\.bamboohr\.com', "bamboohr"),
            # SmartRecruiters embed patterns
            (r'jobs\.smartrecruiters\.com/([^/"\']+)', "smartrecruiters"),
            # Jobvite embed patterns
            (r'jobs\.jobvite\.com/([^/"\']+)', "jobvite"),
        ]
        
        for script in scripts:
            src = script.get("src", "")
            if src:
                # Check specific embed patterns first
                for pattern, ats_type in embed_patterns:
                    match = re.search(pattern, src, re.IGNORECASE)
                    if match:
                        return ats_type, match.group(1)
                
                # Fall back to generic URL detection
                ats_type, ats_identifier = detect_ats_from_url(src)
                if ats_type:
                    return ats_type, ats_identifier
            
            # Also check inline script content for embedded config
            script_content = script.string or ""
            if script_content:
                for pattern, ats_type in embed_patterns:
                    match = re.search(pattern, script_content, re.IGNORECASE)
                    if match:
                        return ats_type, match.group(1)
        
        return None, None

    async def _rediscover_ats_identifier(self, company: Company) -> bool:
        """
        Re-discover the ATS identifier when the current one fails (e.g., 404).
        
        This is called when the ATS API returns 404, suggesting the identifier
        may be incorrect. We re-crawl the careers page to find the correct one.
        
        Returns:
            True if a new identifier was found and updated, False otherwise.
        """
        if not company.careers_url:
            return False

        logger.info(
            "Rediscovering ATS identifier",
            company=company.name,
            current_ats_type=company.ats_type,
            current_identifier=company.ats_identifier,
        )

        try:
            # Fetch the careers page
            html, status_code = await self.crawler.fetch(company.careers_url)
            
            if not html or status_code != 200:
                logger.warning(
                    "Failed to fetch careers page for ATS rediscovery",
                    company=company.name,
                    status_code=status_code,
                )
                return False

            soup = BeautifulSoup(html, "lxml")
            
            # Step 1: Check for embedded scripts
            ats_type, ats_identifier = self._check_embedded_scripts(soup)
            if ats_type == company.ats_type and ats_identifier and ats_identifier != company.ats_identifier:
                logger.info(
                    "Found new identifier from embedded script",
                    company=company.name,
                    old_identifier=company.ats_identifier,
                    new_identifier=ats_identifier,
                )
                company.ats_identifier = ats_identifier
                self._update_careers_url_for_ats(company, ats_identifier)
                return True

            # Step 2: Check for embedded iframes
            ats_type, ats_identifier = self._check_embedded_iframes(soup)
            if ats_type == company.ats_type and ats_identifier and ats_identifier != company.ats_identifier:
                logger.info(
                    "Found new identifier from iframe",
                    company=company.name,
                    old_identifier=company.ats_identifier,
                    new_identifier=ats_identifier,
                )
                company.ats_identifier = ats_identifier
                self._update_careers_url_for_ats(company, ats_identifier)
                return True

            # Step 3: Try to extract identifier from HTML patterns
            new_identifier = extract_identifier_from_html(html, company.ats_type)
            if new_identifier and new_identifier != company.ats_identifier:
                logger.info(
                    "Found new identifier from HTML patterns",
                    company=company.name,
                    old_identifier=company.ats_identifier,
                    new_identifier=new_identifier,
                )
                company.ats_identifier = new_identifier
                self._update_careers_url_for_ats(company, new_identifier)
                return True

            # Step 4: Follow job links to detect ATS from redirects
            job_links = self._find_job_links(soup, company.careers_url)
            for job_link in job_links[:3]:
                ats_type, ats_identifier = await self._detect_ats_from_redirect(job_link)
                if ats_type == company.ats_type and ats_identifier and ats_identifier != company.ats_identifier:
                    logger.info(
                        "Found new identifier from job link redirect",
                        company=company.name,
                        old_identifier=company.ats_identifier,
                        new_identifier=ats_identifier,
                        job_link=job_link,
                    )
                    company.ats_identifier = ats_identifier
                    return True

            logger.warning(
                "Could not rediscover ATS identifier",
                company=company.name,
                ats_type=company.ats_type,
            )
            return False

        except Exception as e:
            logger.error(
                "ATS rediscovery failed",
                company=company.name,
                error=str(e),
            )
            return False

    # NOTE: ATS identifier extraction is now handled by the consolidated
    # extract_identifier_from_html() function in discovery/ats_detector.py

    async def _extract_jobs(self, company: Company, snapshot: CrawlSnapshot) -> int:
        """Extract jobs from a crawl snapshot.
        
        Returns:
            Number of jobs saved
        """
        from app.engines.extract.greenhouse import GreenhouseExtractor
        from app.engines.extract.lever import LeverExtractor
        from app.engines.extract.ashby import AshbyExtractor
        from app.engines.extract.workable import WorkableExtractor
        from app.engines.extract.generic import GenericExtractor
        from app.engines.normalize.service import NormalizationEngine
        
        try:
            # Choose extractor based on ATS type
            extractors = {
                "greenhouse": GreenhouseExtractor(),
                "lever": LeverExtractor(),
                "workable": WorkableExtractor(),
                "ashby": AshbyExtractor(),
            }
            
            extractor = extractors.get(company.ats_type, GenericExtractor())
            
            # Extract raw jobs
            raw_jobs = await extractor.extract(
                html=snapshot.html_content,
                url=snapshot.url,
                company_identifier=company.ats_identifier,
            )
            
            logger.info(
                "Extraction complete",
                company=company.name,
                raw_job_count=len(raw_jobs),
            )
            
            if not raw_jobs:
                return 0
            
            # Normalize and save jobs
            normalize_engine = NormalizationEngine(self.db)
            saved_count = 0
            
            for raw_job in raw_jobs:
                try:
                    job = await normalize_engine.normalize_and_save(
                        raw_job=raw_job,
                        company_id=company.id,
                        snapshot_id=snapshot.id,
                    )
                    if job:
                        saved_count += 1
                except Exception as e:
                    logger.error(
                        "Failed to normalize job",
                        title=raw_job.title,
                        error=str(e),
                    )
            
            await self.db.commit()
            
            logger.info(
                "Jobs saved",
                company=company.name,
                saved_count=saved_count,
            )
            
            return saved_count
            
        except Exception as e:
            logger.error("Extraction failed", company=company.name, error=str(e))
            return 0

    async def crawl_companies(
        self,
        company_ids: list[UUID],
        concurrency: int = 5,
    ) -> dict:
        """Crawl multiple companies with concurrency limit."""
        from app.db import async_session_factory
        
        semaphore = asyncio.Semaphore(concurrency)
        results = {"success": 0, "failed": 0, "unchanged": 0}

        async def crawl_with_semaphore(company_id: UUID):
            async with semaphore:
                # Use a separate db session for each company to avoid concurrency issues
                async with async_session_factory() as db:
                    engine = CrawlEngine(db, self.rate_limiter)
                    try:
                        result = await engine.crawl_company(company_id)
                        if result.get("status") == "success":
                            results["success"] += 1
                        else:
                            results["failed"] += 1
                    except Exception as e:
                        logger.error("Crawl error", company_id=str(company_id), error=str(e))
                        results["failed"] += 1

        tasks = [crawl_with_semaphore(cid) for cid in company_ids]
        await asyncio.gather(*tasks)

        return results

    async def crawl_by_ats_type(
        self,
        ats_type: str,
        limit: int = 100,
        concurrency: int = 5,
    ) -> dict:
        """Crawl all companies of a specific ATS type."""
        result = await self.db.execute(
            select(Company.id)
            .where(Company.ats_type == ats_type)
            .where(Company.is_active == True)
            .where(Company.careers_url.isnot(None))
            .order_by(Company.crawl_priority.desc())
            .limit(limit)
        )
        company_ids = [row[0] for row in result.fetchall()]

        logger.info(f"Crawling {len(company_ids)} {ats_type} companies")

        return await self.crawl_companies(company_ids, concurrency)


async def crawl_company(company_id: str):
    """Crawl a single company (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        engine = CrawlEngine(db)
        try:
            await engine.crawl_company(UUID(company_id))
        finally:
            await engine.close()


async def discover_ats_for_companies(limit: int = 100, concurrency: int = 5):
    """
    Discover ATS for companies that don't have one detected.
    
    This function crawls careers pages and follows job links to detect
    what ATS platform each company uses.
    """
    from app.db import async_session_factory

    async with async_session_factory() as db:
        # Get companies without ATS type
        result = await db.execute(
            select(Company)
            .where(Company.ats_type.is_(None))
            .where(Company.careers_url.isnot(None))
            .where(Company.is_active == True)
            .limit(limit)
        )
        companies = result.scalars().all()

        if not companies:
            logger.info("No companies without ATS found")
            return {"discovered": 0, "failed": 0}

        logger.info(f"Discovering ATS for {len(companies)} companies")

        rate_limiter = RateLimiter()
        semaphore = asyncio.Semaphore(concurrency)
        results = {"discovered": 0, "failed": 0}

        async def discover_single(company: Company):
            async with semaphore:
                async with async_session_factory() as session:
                    engine = CrawlEngine(session, rate_limiter)
                    try:
                        # Refresh company in this session
                        stmt = select(Company).where(Company.id == company.id)
                        result = await session.execute(stmt)
                        comp = result.scalar_one_or_none()
                        
                        if comp and not comp.ats_type:
                            ats_type, _ = await engine._discover_ats(comp)
                            await session.commit()
                            
                            if ats_type:
                                results["discovered"] += 1
                            else:
                                results["failed"] += 1
                    except Exception as e:
                        logger.error(f"Discovery failed for {company.name}: {e}")
                        results["failed"] += 1
                    finally:
                        await engine.close()

        tasks = [discover_single(comp) for comp in companies]
        await asyncio.gather(*tasks)

        logger.info("ATS discovery complete", **results)
        return results


async def crawl_all_companies():
    """Crawl all active companies (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        # Get all active companies
        result = await db.execute(
            select(Company.id)
            .where(Company.is_active == True)
            .where(Company.careers_url.isnot(None))
            .order_by(Company.crawl_priority.desc())
        )
        company_ids = [row[0] for row in result.fetchall()]

        engine = CrawlEngine(db)
        try:
            results = await engine.crawl_companies(company_ids, concurrency=10)
            logger.info("Crawl all complete", **results)
        finally:
            await engine.close()
