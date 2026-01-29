"""Generic job extractor for unknown page structures."""

import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob

logger = structlog.get_logger()


class GenericExtractor(BaseExtractor):
    """Generic extractor for unknown page structures."""

    # Common job-related CSS selectors
    JOB_SELECTORS = [
        # Standard class names
        ".job", ".job-listing", ".job-post", ".job-card",
        ".career", ".opening", ".position", ".vacancy",
        # Data attributes
        "[data-job]", "[data-job-id]", "[data-posting]",
        # List items
        ".jobs-list li", ".careers-list li", ".openings-list li",
        # Table rows
        ".jobs-table tr", "table.jobs tr",
    ]

    # Selectors to avoid (not jobs)
    EXCLUDE_SELECTORS = [
        "nav", "footer", "header", ".nav", ".footer", ".header",
        ".sidebar", ".menu", ".cookie", ".banner", ".popup",
    ]

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs using generic patterns."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Remove noise elements
        for selector in self.EXCLUDE_SELECTORS:
            for elem in soup.select(selector):
                elem.decompose()

        # Try JSON-LD first (using base class method)
        json_ld_jobs = self._extract_json_ld(soup, url)
        if json_ld_jobs:
            logger.info("Extracted from JSON-LD", job_count=len(json_ld_jobs))
            return json_ld_jobs

        # Try common job selectors
        for selector in self.JOB_SELECTORS:
            elements = soup.select(selector)
            for elem in elements:
                job = self._parse_job_element(elem, url)
                if job:
                    jobs.append(job)

            if jobs:
                logger.info(
                    "Extracted with selector",
                    selector=selector,
                    job_count=len(jobs),
                )
                return jobs

        # Try extracting from links
        jobs = self._extract_from_links(soup, url)
        if jobs:
            logger.info("Extracted from links", job_count=len(jobs))
            return jobs

        # Try extracting from page structure
        jobs = self._extract_from_structure(soup, url)
        if jobs:
            logger.info("Extracted from structure", job_count=len(jobs))

        return jobs

    # NOTE: JSON-LD extraction methods are now inherited from BaseExtractor:
    # - _extract_json_ld()
    # - _parse_json_ld_recursive()
    # - _job_from_json_ld()
    # - _parse_json_ld_location()
    # - _parse_json_ld_salary()

    def _parse_job_element(self, elem, base_url: str) -> Optional[ExtractedJob]:
        """Parse a potential job element."""
        # Find title
        title_elem = elem.select_one("h1, h2, h3, h4, .title, [class*='title']")
        if not title_elem:
            # Try the first link
            title_elem = elem.select_one("a")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title or len(title) < 5:
            return None

        # Find URL
        link = elem.select_one("a[href]")
        href = link.get("href", "") if link else ""
        job_url = urljoin(base_url, href) if href else base_url

        # Find location
        location_elem = elem.select_one(
            ".location, [class*='location'], [data-location]"
        )
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        # Find department
        dept_elem = elem.select_one(
            ".department, [class*='department'], [class*='team']"
        )
        department = self._clean_text(dept_elem.get_text()) if dept_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
            department=department,
        )

    def _extract_from_links(self, soup: BeautifulSoup, base_url: str) -> list[ExtractedJob]:
        """Extract jobs from links on the page."""
        jobs = []
        seen_urls = set()

        # Job-related URL patterns
        job_patterns = [
            r"/jobs?/",
            r"/careers?/",
            r"/positions?/",
            r"/openings?/",
            r"/opportunities/",
            r"/apply/",
        ]

        links = soup.select("a[href]")
        for link in links:
            href = link.get("href", "")
            if not href or href.startswith("#"):
                continue

            # Check if URL looks like a job posting
            is_job_url = any(re.search(p, href, re.IGNORECASE) for p in job_patterns)
            if not is_job_url:
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = self._clean_text(link.get_text())
            if title and len(title) > 5 and not self._is_navigation_text(title):
                jobs.append(ExtractedJob(title=title, source_url=full_url))

        return jobs

    def _extract_from_structure(self, soup: BeautifulSoup, base_url: str) -> list[ExtractedJob]:
        """Extract jobs by analyzing page structure."""
        jobs = []

        # Find repeated elements that look like job listings
        # Group elements by their structure signature
        candidates = soup.select("div, article, section, li")

        element_groups = {}
        for elem in candidates:
            # Create a signature based on class names and child structure
            classes = " ".join(sorted(elem.get("class", [])))
            children = [child.name for child in elem.children if hasattr(child, "name")]
            signature = f"{classes}|{','.join(children[:5])}"

            if signature not in element_groups:
                element_groups[signature] = []
            element_groups[signature].append(elem)

        # Find groups with multiple similar elements (likely job listings)
        for signature, elements in element_groups.items():
            if len(elements) >= 3:  # At least 3 similar elements
                for elem in elements:
                    job = self._parse_job_element(elem, base_url)
                    if job:
                        jobs.append(job)

                if jobs:
                    return jobs

        return jobs

    def _is_navigation_text(self, text: str) -> bool:
        """Check if text is navigation/UI text rather than a job title."""
        nav_patterns = [
            r"^view\s+(all|more|job)",
            r"^see\s+(all|more)",
            r"^apply\s+now",
            r"^learn\s+more",
            r"^read\s+more",
            r"^click\s+here",
            r"^back\s+to",
            r"^home$",
            r"^about$",
            r"^contact$",
            r"^careers?$",
            r"^jobs?$",
        ]

        text_lower = text.lower().strip()
        return any(re.match(p, text_lower) for p in nav_patterns)
