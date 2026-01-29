"""SmartRecruiters job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class SmartRecruitersExtractor(BaseExtractor):
    """Extractor for SmartRecruiters job boards."""

    # SmartRecruiters public API
    JOBS_API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from SmartRecruiters."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from SmartRecruiters JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Try API if we have identifier
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract from URL pattern
        match = re.search(r"jobs\.smartrecruiters\.com/([^/]+)", url)
        if match:
            company = match.group(1)
            api_jobs = await self._extract_from_api(company)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    async def _extract_from_api(self, company: str) -> list[ExtractedJob]:
        """Extract jobs using SmartRecruiters public API."""
        api_url = self.JOBS_API.format(company=company)

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
                "Extracted from SmartRecruiters API",
                company=company,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "SmartRecruiters API extraction failed",
                company=company,
                error=str(e),
            )
            return []

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from SmartRecruiters JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("content", []) or data.get("postings", []) or data.get("jobs", [])

        for job_data in job_list:
            try:
                title = job_data.get("name") or job_data.get("title", "")
                if not title:
                    continue

                # Handle location
                location = None
                loc_data = job_data.get("location")
                if loc_data:
                    if isinstance(loc_data, dict):
                        location_parts = [
                            loc_data.get("city"),
                            loc_data.get("region"),
                            loc_data.get("country"),
                        ]
                        location = ", ".join(p for p in location_parts if p)
                    else:
                        location = str(loc_data)

                # Handle department
                department = None
                if job_data.get("department"):
                    dept = job_data["department"]
                    if isinstance(dept, dict):
                        department = dept.get("label") or dept.get("name")
                    else:
                        department = str(dept)

                # Get URL
                job_url = job_data.get("applyUrl") or job_data.get("url")
                if not job_url and job_data.get("ref"):
                    job_url = job_data["ref"]

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url or "",
                        location=location,
                        department=department,
                        employment_type=job_data.get("typeOfEmployment") or job_data.get("type"),
                        posted_at=job_data.get("releasedDate") or job_data.get("createdOn"),
                        description=job_data.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text") if job_data.get("jobAd") else None,
                        remote=job_data.get("remote"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract SmartRecruiters job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from SmartRecruiters HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # SmartRecruiters career site structure
        job_elements = soup.select(
            ".job-card, .opening, .js-openings-load, "
            "[class*='job-item'], [data-job-id], .job-listing"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title, .opening-title")
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

                type_elem = elem.select_one(".job-type, .type")
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
                logger.debug(f"Failed to parse SmartRecruiters element: {e}")

        logger.info("Extracted from SmartRecruiters HTML", job_count=len(jobs))
        return jobs
