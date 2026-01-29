"""Lever ATS job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob
from app.engines.http_client import create_http_client

logger = structlog.get_logger()


class LeverExtractor(BaseExtractor):
    """Extractor for Lever job boards."""

    # Lever URL pattern
    URL_PATTERN = re.compile(r"jobs\.lever\.co/([^/]+)")

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Lever board."""
        # Check if html is actually JSON from ?mode=json
        if html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data, company_identifier)
                if jobs:
                    logger.info("Extracted from Lever JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass
        
        # Extract from HTML (Lever renders server-side)
        jobs = self._extract_from_html(html, url)

        if jobs:
            return jobs

        # Try fetching the page with API-like request
        if company_identifier:
            api_jobs = await self._extract_via_request(company_identifier)
            if api_jobs:
                return api_jobs

        return jobs
    
    def _extract_from_json(self, data: list, company_identifier: str = None) -> list[ExtractedJob]:
        """Extract jobs from Lever JSON API response."""
        jobs = []
        for job_data in data:
            title = job_data.get("text", "")
            if not title:
                continue
            
            # Build job URL
            job_id = job_data.get("id", "")
            if company_identifier:
                job_url = f"https://jobs.lever.co/{company_identifier}/{job_id}"
            else:
                job_url = job_data.get("hostedUrl", job_data.get("applyUrl", ""))
            
            # Extract categories (use `or {}` to handle None values)
            categories = job_data.get("categories") or {}
            location = categories.get("location")
            department = categories.get("department") or categories.get("team")
            commitment = categories.get("commitment")
            
            job = ExtractedJob(
                title=title,
                source_url=job_url,
                location=location,
                department=department,
                employment_type=commitment,
                description=job_data.get("descriptionPlain"),
            )
            jobs.append(job)
        
        return jobs

    async def _extract_via_request(self, company: str) -> list[ExtractedJob]:
        """Fetch and extract jobs from Lever."""
        url = f"https://jobs.lever.co/{company}"

        try:
            async with create_http_client() as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._extract_from_html(response.text, url)

        except Exception as e:
            logger.warning("Lever request failed", company=company, error=str(e))
            return []

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Lever HTML."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Structure 1: Standard Lever postings list
        postings = soup.select(".posting")
        for posting in postings:
            job = self._parse_posting(posting, url)
            if job:
                jobs.append(job)

        if jobs:
            logger.info("Extracted from Lever HTML", job_count=len(jobs))
            return jobs

        # Structure 2: Job cards
        cards = soup.select(".job-card, [data-qa='posting-name']")
        for card in cards:
            job = self._parse_job_card(card, url)
            if job:
                jobs.append(job)

        if jobs:
            return jobs

        # Structure 3: JSON-LD (using base class method)
        json_ld_jobs = self._extract_json_ld(soup, url)
        if json_ld_jobs:
            jobs.extend(json_ld_jobs)
            return jobs

        # Structure 4: Links to job postings
        job_links = soup.select('a[href*="/jobs.lever.co/"]')
        seen_urls = set()

        for link in job_links:
            href = link.get("href", "")
            # Skip category/team pages
            if "/jobs.lever.co/" in href and href not in seen_urls:
                # Check if it's a job posting (has UUID-like path)
                if re.search(r"/[a-f0-9-]{36}/?$", href):
                    seen_urls.add(href)
                    title = self._clean_text(link.get_text())
                    if title and len(title) > 3:
                        jobs.append(ExtractedJob(title=title, source_url=href))

        return jobs

    def _parse_posting(self, posting, base_url: str) -> Optional[ExtractedJob]:
        """Parse a Lever posting element."""
        # Title
        title_elem = posting.select_one(".posting-title h5, .posting-title a, [data-qa='posting-name']")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title:
            return None

        # URL
        link = posting.select_one("a.posting-title, a[data-qa='posting-name']")
        if not link:
            link = posting.select_one("a[href]")

        href = link.get("href", "") if link else ""
        job_url = urljoin(base_url, href) if href else base_url

        # Location
        location_elem = posting.select_one(".posting-categories .location, .location, [data-qa='posting-location']")
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        # Department
        dept_elem = posting.select_one(".posting-categories .department, .department, [data-qa='posting-department']")
        department = self._clean_text(dept_elem.get_text()) if dept_elem else None

        # Work type (commitment)
        commitment_elem = posting.select_one(".posting-categories .commitment, .commitment, [data-qa='posting-commitment']")
        employment_type = self._clean_text(commitment_elem.get_text()) if commitment_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
            department=department,
            employment_type=employment_type,
        )

    def _parse_job_card(self, card, base_url: str) -> Optional[ExtractedJob]:
        """Parse a job card element."""
        title_elem = card.select_one("h5, h4, h3, .title, [data-qa='posting-name']")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title:
            return None

        link = card.select_one("a[href]")
        href = link.get("href", "") if link else ""
        job_url = urljoin(base_url, href) if href else base_url

        location_elem = card.select_one(".location, [data-qa='posting-location']")
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
        )

    # NOTE: JSON-LD parsing methods are now inherited from BaseExtractor:
    # - _extract_json_ld()
    # - _parse_json_ld_recursive()
    # - _job_from_json_ld()
    # - _parse_json_ld_location()
    # - _parse_json_ld_salary()
