"""JazzHR job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class JazzHRExtractor(BaseExtractor):
    """Extractor for JazzHR job boards."""

    # JazzHR API endpoint
    JOBS_API = "https://api.resumatorapi.com/v1/jobs"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from JazzHR."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data, url)
                if jobs:
                    logger.info("Extracted from JazzHR JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    def _extract_from_json(self, data: dict | list, base_url: str) -> list[ExtractedJob]:
        """Extract jobs from JazzHR JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("jobs", []) or data.get("data", [])

        for job_data in job_list:
            try:
                title = job_data.get("title") or job_data.get("job_title", "")
                if not title:
                    continue

                # Build location using base class helper
                location = self._build_location_from_parts(
                    city=job_data.get("city"),
                    state=job_data.get("state"),
                    country=job_data.get("country"),
                )

                # Get URL
                job_url = job_data.get("board_url") or job_data.get("url")
                if not job_url and job_data.get("id"):
                    job_url = f"{base_url}/{job_data['id']}"

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url or base_url,
                        location=location,
                        department=job_data.get("department"),
                        employment_type=job_data.get("type") or job_data.get("employment_type"),
                        posted_at=job_data.get("open_date") or job_data.get("created_at"),
                        description=job_data.get("description") or job_data.get("job_description"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract JazzHR job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from JazzHR HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # JazzHR career portal structure
        job_elements = soup.select(
            ".resumator-job, .job-listing, .jazzhr-job, "
            "[class*='job-card'], [data-job-id]"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title")
                if not title_elem:
                    continue

                title = self._clean_text(title_elem.get_text())
                if not title:
                    continue

                href = title_elem.get("href", "") if title_elem.name == "a" else ""
                if not href:
                    link = elem.select_one("a[href]")
                    href = link.get("href", "") if link else ""
                
                job_url = urljoin(url, href) if href else url

                location_elem = elem.select_one(".location, .job-location")
                location = self._clean_text(location_elem.get_text()) if location_elem else None

                dept_elem = elem.select_one(".department, .job-department")
                department = self._clean_text(dept_elem.get_text()) if dept_elem else None

                type_elem = elem.select_one(".job-type, .employment-type")
                employment_type = self._clean_text(type_elem.get_text()) if type_elem else None

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url,
                        location=location,
                        department=department,
                        employment_type=employment_type,
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse JazzHR element: {e}")

        # Also try to find jobs in embedded script data
        if not jobs:
            jobs = self._extract_from_embedded_json(soup, url)

        logger.info("Extracted from JazzHR HTML", job_count=len(jobs))
        return jobs

    def _extract_from_embedded_json(self, soup: BeautifulSoup, url: str) -> list[ExtractedJob]:
        """Extract jobs from embedded JSON in scripts."""
        jobs = []
        
        for script in soup.find_all("script"):
            if script.string:
                # Look for job data in script
                match = re.search(r'jobs\s*[=:]\s*(\[.*?\])', script.string, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        jobs.extend(self._extract_from_json(data, url))
                    except json.JSONDecodeError:
                        continue

        return jobs
