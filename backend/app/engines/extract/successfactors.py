"""SAP SuccessFactors job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class SuccessFactorsExtractor(BaseExtractor):
    """Extractor for SAP SuccessFactors career sites."""

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from SAP SuccessFactors."""
        jobs = []

        # Try JSON first (OData response)
        if html.strip().startswith("{") or html.strip().startswith("["):
            try:
                data = json.loads(html)
                jobs = self._extract_from_json(data)
                if jobs:
                    logger.info("Extracted from SuccessFactors JSON", job_count=len(jobs))
                    return jobs
            except json.JSONDecodeError:
                pass

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)

    def _extract_from_json(self, data: dict | list) -> list[ExtractedJob]:
        """Extract jobs from SuccessFactors OData JSON response."""
        jobs = []
        
        # Handle OData response format
        job_list = []
        if isinstance(data, list):
            job_list = data
        elif isinstance(data, dict):
            # OData format uses 'd' wrapper
            d = data.get("d", data)
            job_list = d.get("results", []) or d.get("value", []) or d.get("JobRequisition", [])

        for job_data in job_list:
            try:
                title = (
                    job_data.get("jobReqLocale", {}).get("externalTitle") or
                    job_data.get("externalTitle") or 
                    job_data.get("jobTitle") or
                    job_data.get("title", "")
                )
                if not title:
                    continue

                # Handle location - can be nested
                location = None
                if job_data.get("location"):
                    loc = job_data["location"]
                    if isinstance(loc, dict):
                        location = loc.get("name") or loc.get("city")
                    else:
                        location = str(loc)
                elif job_data.get("locationObj"):
                    location = job_data["locationObj"].get("name")
                elif job_data.get("primaryLocation"):
                    location = job_data["primaryLocation"]

                # Handle department
                department = None
                if job_data.get("department"):
                    dept = job_data["department"]
                    if isinstance(dept, dict):
                        department = dept.get("name") or dept.get("externalName")
                    else:
                        department = str(dept)
                elif job_data.get("custDepartment"):
                    department = job_data["custDepartment"]

                # Get URL
                job_url = job_data.get("jobPostingUrl") or job_data.get("externalApplyUrl") or ""

                jobs.append(
                    ExtractedJob(
                        title=title,
                        source_url=job_url,
                        location=location,
                        department=department,
                        employment_type=job_data.get("employmentType") or job_data.get("jobType"),
                        posted_at=job_data.get("postingStartDate") or job_data.get("createdDateTime"),
                        description=job_data.get("externalJobDescription") or job_data.get("jobDescription"),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to extract SuccessFactors job: {e}")

        return jobs

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from SuccessFactors HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # SuccessFactors career site structure - multiple patterns
        job_elements = soup.select(
            ".jobTitleLink, .job-card, .job-listing, "
            "[class*='job-requisition'], [data-job-id], .jobResultItem, "
            "tr.jobList, .careerSiteJobRow"
        )
        
        for elem in job_elements:
            try:
                title_elem = elem.select_one("a, h2, h3, h4, .job-title, .jobTitle")
                if not title_elem:
                    # Element itself might be a link
                    if elem.name == "a":
                        title_elem = elem
                    else:
                        continue

                title = self._clean_text(title_elem.get_text())
                if not title:
                    continue

                href = title_elem.get("href", "") if title_elem.name == "a" else ""
                if not href:
                    link = elem.select_one("a[href]")
                    href = link.get("href", "") if link else ""
                
                job_url = urljoin(url, href) if href else url

                location_elem = elem.select_one(".location, .jobLocation, .job-location")
                location = self._clean_text(location_elem.get_text()) if location_elem else None

                dept_elem = elem.select_one(".department, .jobDepartment")
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
                logger.debug(f"Failed to parse SuccessFactors element: {e}")

        # Try embedded JSON data
        if not jobs:
            jobs = self._extract_from_embedded_json(soup, url)

        logger.info("Extracted from SuccessFactors HTML", job_count=len(jobs))
        return jobs

    def _extract_from_embedded_json(self, soup: BeautifulSoup, url: str) -> list[ExtractedJob]:
        """Extract jobs from embedded JSON in SuccessFactors pages."""
        jobs = []
        
        for script in soup.find_all("script"):
            if script.string:
                # Look for job data in Angular/React apps
                patterns = [
                    r'jobRequisitions\s*[=:]\s*(\[.*?\])',
                    r'"jobs"\s*:\s*(\[.*?\])',
                    r'requisitions\s*[=:]\s*(\[.*?\])',
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
