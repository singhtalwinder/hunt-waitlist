"""Pinpoint ATS job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class PinpointExtractor(BaseExtractor):
    """Extractor for Pinpoint ATS job boards."""

    # Pinpoint API endpoint
    JOBS_API = "https://{subdomain}.pinpointhq.com/api/v1/jobs"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Pinpoint."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Pinpoint JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Try API if we have identifier
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract from URL pattern
        match = re.search(r"([^.]+)\.pinpointhq\.com", url)
        if match:
            subdomain = match.group(1)
            api_jobs = await self._extract_from_api(subdomain)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    async def _extract_from_api(self, subdomain: str) -> list[ExtractedJob]:
        """Extract jobs using Pinpoint API (public endpoint)."""
        # Pinpoint has a public jobs endpoint
        api_url = f"https://{subdomain}.pinpointhq.com/postings.json"

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
                "Extracted from Pinpoint API",
                subdomain=subdomain,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "Pinpoint API extraction failed",
                subdomain=subdomain,
                error=str(e),
            )
            return []

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Pinpoint JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("data", []) or data.get("jobs", []) or data.get("postings", [])

        for job_data in job_list:
            try:
                # Handle nested attributes from JSON API spec
                attrs = job_data.get("attributes", job_data)
                
                title = attrs.get("title") or attrs.get("name", "")
                if not title:
                    continue

                # Handle location
                location = attrs.get("location") or attrs.get("location_name")
                if not location and attrs.get("locations"):
                    locations = attrs.get("locations", [])
                    if locations:
                        location = ", ".join(str(loc.get("name", loc)) for loc in locations[:3])

                # Handle department
                department = attrs.get("department") or attrs.get("department_name")
                if not department and attrs.get("team"):
                    department = attrs.get("team")

                # Get URL
                job_url = attrs.get("url") or attrs.get("apply_url")
                if not job_url and job_data.get("links"):
                    job_url = job_data["links"].get("self")

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url or "",
                        location=location,
                        department=department,
                        employment_type=attrs.get("employment_type") or attrs.get("type"),
                        posted_at=attrs.get("published_at") or attrs.get("created_at"),
                        description=attrs.get("description"),
                        remote=attrs.get("remote"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Pinpoint job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Pinpoint HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Pinpoint career portal structure
        job_elements = soup.select(
            ".job-card, .job-listing, .posting-card, "
            "[class*='job-item'], [data-job-id], [data-posting-id]"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title, .posting-title")
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

                dept_elem = elem.select_one(".department, .team, .job-department")
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
                logger.debug(f"Failed to parse Pinpoint element: {e}")

        logger.info("Extracted from Pinpoint HTML", job_count=len(jobs))
        return jobs
