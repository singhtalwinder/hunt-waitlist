"""Manatal job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class ManatalExtractor(BaseExtractor):
    """Extractor for Manatal career pages."""

    # Manatal Career Page API
    CAREER_API = "https://api.manatal.com/open/v3/career-page/{company}/jobs"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Manatal."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Manatal JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Try API if we have identifier
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract company from URL
        match = re.search(r"([^.]+)\.manatal\.com", url)
        if match:
            company = match.group(1)
            api_jobs = await self._extract_from_api(company)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    async def _extract_from_api(self, company: str) -> list[ExtractedJob]:
        """Extract jobs using Manatal Career Page API."""
        api_url = self.CAREER_API.format(company=company)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    api_url,
                    headers={"Accept": "application/json"},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

            jobs = self._extract_from_json(data)
            logger.info(
                "Extracted from Manatal API",
                company=company,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "Manatal API extraction failed",
                company=company,
                error=str(e),
            )
            return []

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Manatal JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("results", []) or data.get("jobs", []) or data.get("data", [])

        for job_data in job_list:
            try:
                title = job_data.get("position_name") or job_data.get("title", "")
                if not title:
                    continue

                # Handle location
                location = job_data.get("location_name") or job_data.get("location")
                if not location and job_data.get("locations"):
                    locations = job_data.get("locations", [])
                    if locations:
                        location = ", ".join(
                            loc.get("name", str(loc)) if isinstance(loc, dict) else str(loc)
                            for loc in locations[:3]
                        )

                # Handle department
                department = job_data.get("department_name") or job_data.get("department")
                if isinstance(department, dict):
                    department = department.get("name")

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("apply_url") or job_data.get("url", ""),
                        location=location,
                        department=department,
                        employment_type=job_data.get("employment_type") or job_data.get("job_type"),
                        posted_at=job_data.get("published_date") or job_data.get("created_at"),
                        description=job_data.get("description"),
                        remote=job_data.get("is_remote"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Manatal job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Manatal HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Manatal career page structure
        job_elements = soup.select(
            ".job-card, .job-listing, .position-card, "
            "[class*='job-item'], [data-job-id]"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title, .position-name")
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

                dept_elem = elem.select_one(".department")
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
                logger.debug(f"Failed to parse Manatal element: {e}")

        logger.info("Extracted from Manatal HTML", job_count=len(jobs))
        return jobs
