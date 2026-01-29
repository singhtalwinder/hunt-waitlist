"""BambooHR job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob
from app.engines.http_client import create_http_client

logger = structlog.get_logger()


class BambooHRExtractor(BaseExtractor):
    """Extractor for BambooHR job boards."""

    # BambooHR embed API
    EMBED_API = "https://{company}.bamboohr.com/careers/list"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from BambooHR."""
        jobs = []

        # Try JSON if available
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from BambooHR JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Try API if we have identifier
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract from URL pattern
        match = re.search(r"([^.]+)\.bamboohr\.com", url)
        if match:
            company_id = match.group(1)
            api_jobs = await self._extract_from_api(company_id)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    async def _extract_from_api(self, company_id: str) -> list[ExtractedJob]:
        """Extract jobs using BambooHR careers API."""
        api_url = self.EMBED_API.format(company=company_id)

        try:
            async with create_http_client(json_accept=True) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()

            jobs = self._extract_from_json(data)
            logger.info(
                "Extracted from BambooHR API",
                company=company_id,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning(
                "BambooHR API extraction failed",
                company=company_id,
                error=str(e),
            )
            return []

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from BambooHR JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = data if isinstance(data, list) else data.get("result", [])

        for job_data in job_list:
            try:
                title = job_data.get("jobOpeningName") or job_data.get("title", "")
                if not title:
                    continue

                # Build location using base class helper
                location = self._build_location_from_parts(
                    city=job_data.get("city"),
                    state=job_data.get("state"),
                    country=job_data.get("country"),
                    fallback=job_data.get("location"),
                )

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("jobOpeningShareUrl") or job_data.get("url", ""),
                        location=location,
                        department=job_data.get("department") or job_data.get("departmentLabel"),
                        employment_type=job_data.get("employmentStatusLabel") or job_data.get("type"),
                        posted_at=job_data.get("datePosted") or job_data.get("createdDate"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract BambooHR job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from BambooHR HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # BambooHR job listing structure
        job_elements = soup.select(".BambooHR-ATS-Jobs-Item, .fab-ListItem, [data-job-id]")
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, .fab-ListItem-title, h3, h4")
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

                location_elem = elem.select_one(".fab-ListItem-subtitle, .location, [data-location]")
                location = self._clean_text(location_elem.get_text()) if location_elem else None

                dept_elem = elem.select_one(".department, [data-department]")
                department = self._clean_text(dept_elem.get_text()) if dept_elem else None

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url,
                        location=location,
                        department=department,
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse BambooHR element: {e}")

        logger.info("Extracted from BambooHR HTML", job_count=len(jobs))
        return jobs
