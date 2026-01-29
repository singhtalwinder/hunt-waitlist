"""Jobvite job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class JobviteExtractor(BaseExtractor):
    """Extractor for Jobvite job boards."""

    # Jobvite API pattern
    JOBS_API = "https://jobs.jobvite.com/{company}/jobs"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Jobvite."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Jobvite JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Jobvite JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("jobs", []) or data.get("requisitions", []) or data.get("data", [])

        for job_data in job_list:
            try:
                title = job_data.get("title") or job_data.get("jobTitle", "")
                if not title:
                    continue

                # Build location
                location = job_data.get("location")
                if not location:
                    location_parts = []
                    if job_data.get("city"):
                        location_parts.append(job_data["city"])
                    if job_data.get("state"):
                        location_parts.append(job_data["state"])
                    if job_data.get("country"):
                        location_parts.append(job_data["country"])
                    location = ", ".join(location_parts) if location_parts else None

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("detailUrl") or job_data.get("applyUrl") or job_data.get("url", ""),
                        location=location,
                        department=job_data.get("category") or job_data.get("department"),
                        employment_type=job_data.get("type") or job_data.get("employmentType"),
                        posted_at=job_data.get("datePosted") or job_data.get("date"),
                        description=job_data.get("description") or job_data.get("briefDescription"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Jobvite job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Jobvite HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Jobvite career site structure - multiple patterns
        job_elements = soup.select(
            ".jv-job-list-item, .jv-job-card, .job-listing, "
            "[class*='requisition'], [data-job-id], .job-row, table.jv-job-list tr"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .jv-job-list-name, .job-title")
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

                location_elem = elem.select_one(".jv-job-list-location, .location, .job-location")
                location = self._clean_text(location_elem.get_text()) if location_elem else None

                dept_elem = elem.select_one(".jv-job-list-category, .category, .department")
                department = self._clean_text(dept_elem.get_text()) if dept_elem else None

                type_elem = elem.select_one(".jv-job-list-type, .job-type")
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
                logger.debug(f"Failed to parse Jobvite element: {e}")

        # Also check for embedded JSON
        if not jobs:
            jobs = self._extract_from_embedded_json(soup, url)

        logger.info("Extracted from Jobvite HTML", job_count=len(jobs))
        return jobs

    def _extract_from_embedded_json(self, soup: BeautifulSoup, url: str) -> list[ExtractedJob]:
        """Extract jobs from embedded JSON in Jobvite pages."""
        jobs = []
        
        for script in soup.find_all("script"):
            if script.string:
                # Look for job data in script
                patterns = [
                    r'jobList\s*[=:]\s*(\[.*?\])',
                    r'"requisitions"\s*:\s*(\[.*?\])',
                    r'jvJobs\s*[=:]\s*(\[.*?\])',
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            jobs.extend(self._extract_from_json(data))
                        except json.JSONDecodeError:
                            continue

        return jobs
