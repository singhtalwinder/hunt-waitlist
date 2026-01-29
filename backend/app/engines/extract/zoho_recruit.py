"""Zoho Recruit job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class ZohoRecruitExtractor(BaseExtractor):
    """Extractor for Zoho Recruit career portals."""

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Zoho Recruit."""
        jobs = []

        # Try JSON first
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from Zoho Recruit JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from Zoho Recruit JSON response."""
        jobs = []
        
        # Handle different response formats
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            job_list = data.get("data", []) or data.get("jobs", []) or data.get("Job_Openings", [])

        for job_data in job_list:
            try:
                title = (
                    job_data.get("Job_Opening_Name") or 
                    job_data.get("Posting_Title") or 
                    job_data.get("title", "")
                )
                if not title:
                    continue

                # Build location
                location_parts = []
                if job_data.get("City"):
                    location_parts.append(job_data["City"])
                if job_data.get("State"):
                    location_parts.append(job_data["State"])
                if job_data.get("Country"):
                    location_parts.append(job_data["Country"])
                location = ", ".join(location_parts) if location_parts else job_data.get("Location")

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_data.get("$apply_url") or job_data.get("url", ""),
                        location=location,
                        department=job_data.get("Department"),
                        employment_type=job_data.get("Job_Type"),
                        posted_at=job_data.get("Date_Opened") or job_data.get("Created_Time"),
                        description=job_data.get("Job_Description"),
                        salary=job_data.get("Salary"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract Zoho Recruit job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Zoho Recruit HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Zoho Recruit career portal structure
        job_elements = soup.select(
            ".zr-job-listing, .job-card, .career-job-item, "
            "[class*='job-opening'], [data-job-id]"
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

                location_elem = elem.select_one(".location, .job-location, [data-location]")
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
                logger.debug(f"Failed to parse Zoho Recruit element: {e}")

        logger.info("Extracted from Zoho Recruit HTML", job_count=len(jobs))
        return jobs
