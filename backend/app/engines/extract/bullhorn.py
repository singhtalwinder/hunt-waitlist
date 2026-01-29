"""Bullhorn ATS job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class BullhornExtractor(BaseExtractor):
    """Extractor for Bullhorn job boards."""

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Bullhorn."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Bullhorn JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Bullhorn JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("data", []) or data.get("jobs", []) or data.get("results", [])

        for job_data in job_list:
            try:
                title = job_data.get("title") or job_data.get("publicDescription", "")
                if not title:
                    continue

                # Build location from address
                location = None
                address = job_data.get("address") or {}
                if isinstance(address, dict):
                    location_parts = [
                        address.get("city"),
                        address.get("state"),
                        address.get("countryName") or address.get("country"),
                    ]
                    location = ", ".join(p for p in location_parts if p)
                elif isinstance(address, str):
                    location = address

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("publicUrl") or job_data.get("url", ""),
                        location=location,
                        department=job_data.get("categories", {}).get("data", [{}])[0].get("name") if job_data.get("categories") else None,
                        employment_type=job_data.get("employmentType"),
                        posted_at=job_data.get("dateLastPublished") or job_data.get("dateAdded"),
                        description=job_data.get("publicDescription"),
                        salary=self._extract_salary(json.dumps(job_data)) if job_data.get("salary") else None,
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Bullhorn job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Bullhorn HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Bullhorn career portal structure
        job_elements = soup.select(
            ".job-card, .job-listing, .jobResultItem, "
            "[class*='job-row'], [data-job-id], .job-tile"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title, .jobTitle")
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

                location_elem = elem.select_one(".location, .job-location, .jobLocation")
                location = self._clean_text(location_elem.get_text()) if location_elem else None

                dept_elem = elem.select_one(".category, .job-category, .jobCategory")
                department = self._clean_text(dept_elem.get_text()) if dept_elem else None

                type_elem = elem.select_one(".job-type, .employmentType")
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
                logger.debug(f"Failed to parse Bullhorn element: {e}")

        logger.info("Extracted from Bullhorn HTML", job_count=len(jobs))
        return jobs
