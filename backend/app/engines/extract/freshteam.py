"""Freshteam job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class FreshteamExtractor(BaseExtractor):
    """Extractor for Freshteam job boards."""

    # Freshteam API endpoint pattern
    JOBS_API = "https://{domain}.freshteam.com/api/job_postings"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Freshteam."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Freshteam JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Try API if we have identifier
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract from URL pattern
        match = re.search(r"([^.]+)\.freshteam\.com", url)
        if match:
            domain = match.group(1)
            api_jobs = await self._extract_from_api(domain)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    async def _extract_from_api(self, domain: str) -> list[ExtractedJob]:
        """Extract jobs using Freshteam API."""
        api_url = self.JOBS_API.format(domain=domain)

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
                "Extracted from Freshteam API",
                domain=domain,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "Freshteam API extraction failed",
                domain=domain,
                error=str(e),
            )
            return []

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Freshteam JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("job_postings", []) or data.get("jobs", []) or data.get("data", [])

        for job_data in job_list:
            try:
                title = job_data.get("title") or job_data.get("name", "")
                if not title:
                    continue

                # Handle location
                location = None
                if job_data.get("location"):
                    loc = job_data["location"]
                    if isinstance(loc, dict):
                        location = loc.get("name") or loc.get("city")
                    else:
                        location = str(loc)
                elif job_data.get("branch"):
                    branch = job_data["branch"]
                    if isinstance(branch, dict):
                        location = branch.get("city") or branch.get("name")

                # Handle department
                department = None
                if job_data.get("department"):
                    dept = job_data["department"]
                    if isinstance(dept, dict):
                        department = dept.get("name")
                    else:
                        department = str(dept)

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("url") or job_data.get("apply_url", ""),
                        location=location,
                        department=department,
                        employment_type=job_data.get("type") or job_data.get("employment_type"),
                        posted_at=job_data.get("created_at") or job_data.get("published_at"),
                        description=job_data.get("description"),
                        remote=job_data.get("remote"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Freshteam job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Freshteam HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Freshteam career portal structure
        job_elements = soup.select(
            ".job-card, .job-listing, .job-item, "
            "[class*='job-posting'], [data-job-id]"
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

                location_elem = elem.select_one(".location, .job-location, .branch")
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
                logger.debug(f"Failed to parse Freshteam element: {e}")

        logger.info("Extracted from Freshteam HTML", job_count=len(jobs))
        return jobs
