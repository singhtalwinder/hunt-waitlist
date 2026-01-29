"""Greenhouse ATS job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob
from app.engines.http_client import create_http_client

logger = structlog.get_logger()


class GreenhouseExtractor(BaseExtractor):
    """Extractor for Greenhouse job boards."""

    # Greenhouse API endpoint pattern
    API_PATTERN = re.compile(r"boards\.greenhouse\.io/([^/]+)")
    EMBED_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Greenhouse board."""
        # Check if html is actually JSON from the API
        if html.strip().startswith("{"):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Greenhouse JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass
        
        # Try API call (if we got HTML instead of JSON)
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Try extracting board token from URL
        match = self.API_PATTERN.search(url)
        if match:
            board_token = match.group(1)
            api_jobs = await self._extract_from_api(board_token)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)
    
    def _extract_from_json(self, data: dict) -> list[ExtractedJob]:
        """Extract jobs from Greenhouse API JSON response."""
        jobs = []
        for job_data in data.get("jobs", []):
            job = ExtractedJob(
                title=job_data.get("title", ""),
                source_url=job_data.get("absolute_url", ""),
                location=self._parse_location(job_data.get("location", {})),
                department=self._parse_departments(job_data.get("departments", [])),
                posted_at=job_data.get("updated_at"),
            )
            jobs.append(job)
        return jobs

    async def _extract_from_api(self, board_token: str) -> list[ExtractedJob]:
        """Extract jobs using Greenhouse public API."""
        api_url = self.EMBED_API.format(board=board_token)

        try:
            async with create_http_client(json_accept=True) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()

            jobs = []
            for job_data in data.get("jobs", []):
                job = ExtractedJob(
                    title=job_data.get("title", ""),
                    source_url=job_data.get("absolute_url", ""),
                    location=self._parse_location(job_data.get("location", {})),
                    department=self._parse_departments(job_data.get("departments", [])),
                    posted_at=job_data.get("updated_at"),
                )
                jobs.append(job)

            logger.info(
                "Extracted from Greenhouse API",
                board=board_token,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "Greenhouse API extraction failed",
                board=board_token,
                error=str(e),
            )
            return []

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Greenhouse HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Try different Greenhouse HTML structures

        # Structure 1: Modern greenhouse board
        job_elements = soup.select(".opening")
        for elem in job_elements:
            job = self._parse_opening_element(elem, url)
            if job:
                jobs.append(job)

        if jobs:
            return jobs

        # Structure 2: Job cards
        job_cards = soup.select(".job-card, .job-post, [data-job-id]")
        for card in job_cards:
            job = self._parse_job_card(card, url)
            if job:
                jobs.append(job)

        if jobs:
            return jobs

        # Structure 3: Job links
        job_links = soup.select('a[href*="/jobs/"]')
        seen_urls = set()
        for link in job_links:
            href = link.get("href", "")
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = self._clean_text(link.get_text())
            if title and len(title) > 3:
                job_url = urljoin(url, href)
                jobs.append(ExtractedJob(title=title, source_url=job_url))

        # Structure 4: Embedded JSON-LD data (using base class method)
        json_ld_jobs = self._extract_json_ld(soup, url)
        if json_ld_jobs:
            jobs.extend(json_ld_jobs)

        return jobs

    def _parse_opening_element(self, elem, base_url: str) -> Optional[ExtractedJob]:
        """Parse a job opening element."""
        title_elem = elem.select_one("a")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        href = title_elem.get("href", "")
        job_url = urljoin(base_url, href) if href else None

        if not title or not job_url:
            return None

        location_elem = elem.select_one(".location")
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
        )

    def _parse_job_card(self, card, base_url: str) -> Optional[ExtractedJob]:
        """Parse a job card element."""
        title_elem = card.select_one("h2, h3, .job-title, [data-job-title]")
        if not title_elem:
            title_elem = card.select_one("a")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title:
            return None

        # Get URL
        link = card.select_one("a[href]")
        href = link.get("href", "") if link else ""
        job_url = urljoin(base_url, href) if href else base_url

        # Get location
        location_elem = card.select_one(".location, [data-location]")
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        # Get department
        dept_elem = card.select_one(".department, [data-department]")
        department = self._clean_text(dept_elem.get_text()) if dept_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
            department=department,
        )

    # NOTE: JSON-LD parsing methods are now inherited from BaseExtractor:
    # - _extract_json_ld()
    # - _job_from_json_ld()
    # - _parse_json_ld_location()
    # - _parse_json_ld_salary()

    def _parse_location(self, location_data) -> Optional[str]:
        """Parse location from API response."""
        if not location_data:
            return None
        if isinstance(location_data, str):
            return location_data
        if isinstance(location_data, dict):
            return location_data.get("name")
        return None

    def _parse_departments(self, departments: list) -> Optional[str]:
        """Parse departments from API response."""
        if not departments:
            return None
        names = [d.get("name") for d in departments if d.get("name")]
        return ", ".join(names) if names else None
