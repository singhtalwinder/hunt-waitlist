"""Ashby ATS job extractor."""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import structlog
from bs4 import BeautifulSoup

from app.engines.extract.base import BaseExtractor, ExtractedJob
from app.engines.http_client import create_http_client

logger = structlog.get_logger()


class AshbyExtractor(BaseExtractor):
    """Extractor for Ashby job boards."""

    # Ashby URL pattern
    URL_PATTERN = re.compile(r"jobs\.ashbyhq\.com/([^/]+)")

    # Ashby API endpoint
    API_URL = "https://jobs.ashbyhq.com/api/non-user-graphql"

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs from Ashby board."""
        # Check if html is actually JSON from posting-api
        if html.strip().startswith("{"):
            try:
                data = json.loads(html)
                jobs = self._extract_from_posting_api(data, company_identifier)
                if jobs:
                    return jobs
            except json.JSONDecodeError:
                pass
        
        # Try GraphQL API (most reliable)
        if company_identifier:
            api_jobs = await self._extract_from_api(company_identifier)
            if api_jobs:
                return api_jobs

        # Extract identifier from URL
        match = self.URL_PATTERN.search(url)
        if match:
            identifier = match.group(1)
            api_jobs = await self._extract_from_api(identifier)
            if api_jobs:
                return api_jobs

        # Fall back to HTML parsing
        return self._extract_from_html(html, url)
    
    def _extract_from_posting_api(self, data: dict, org_slug: str = None) -> list[ExtractedJob]:
        """Extract jobs from Ashby posting-api response."""
        jobs = []
        
        # Handle the posting-api format: {"jobs": [...]}
        job_list = data.get("jobs", [])
        
        for job_data in job_list:
            job_id = job_data.get("id", "")
            title = job_data.get("title", "")
            
            if not title:
                continue
            
            # Build job URL
            if org_slug:
                job_url = f"https://jobs.ashbyhq.com/{org_slug}/{job_id}"
            else:
                job_url = f"https://jobs.ashbyhq.com/job/{job_id}"
            
            # Extract location from nested structure
            location = None
            location_data = job_data.get("location")
            if isinstance(location_data, dict):
                location = location_data.get("name")
            elif isinstance(location_data, str):
                location = location_data
            
            # Extract department/team (use `or {}` to handle None values)
            team_data = job_data.get("team")
            department = team_data.get("name") if isinstance(team_data, dict) else None
            
            job = ExtractedJob(
                title=title,
                source_url=job_url,
                location=location,
                department=department,
                employment_type=job_data.get("employmentType"),
                posted_at=job_data.get("publishedAt"),
            )
            jobs.append(job)
        
        if jobs:
            logger.info("Extracted from Ashby posting-api", job_count=len(jobs))
        
        return jobs

    async def _extract_from_api(self, org_slug: str) -> list[ExtractedJob]:
        """Extract jobs using Ashby GraphQL API."""
        query = """
        query JobBoardWithSearch($organizationHostedJobsPageName: String!) {
            jobBoard: jobBoardWithSearch(
                organizationHostedJobsPageName: $organizationHostedJobsPageName
            ) {
                jobPostings {
                    id
                    title
                    locationName
                    teamName
                    employmentType
                    compensationTierSummary
                    publishedDate
                }
            }
        }
        """

        try:
            async with create_http_client(json_accept=True) as client:
                response = await client.post(
                    self.API_URL,
                    json={
                        "operationName": "JobBoardWithSearch",
                        "variables": {"organizationHostedJobsPageName": org_slug},
                        "query": query,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            # Use `or {}` to handle None values
            job_board = (data.get("data") or {}).get("jobBoard") or {}
            postings = job_board.get("jobPostings") or []

            jobs = []
            for posting in postings:
                job_url = f"https://jobs.ashbyhq.com/{org_slug}/{posting['id']}"

                job = ExtractedJob(
                    title=posting.get("title", ""),
                    source_url=job_url,
                    location=posting.get("locationName"),
                    department=posting.get("teamName"),
                    employment_type=posting.get("employmentType"),
                    salary=posting.get("compensationTierSummary"),
                    posted_at=posting.get("publishedDate"),
                )
                jobs.append(job)

            logger.info(
                "Extracted from Ashby API",
                org=org_slug,
                job_count=len(jobs),
            )
            return jobs

        except Exception as e:
            logger.warning("Ashby API extraction failed", org=org_slug, error=str(e))
            return []

    def _extract_from_html(self, html: str, url: str) -> list[ExtractedJob]:
        """Extract jobs from Ashby HTML page."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # Look for Next.js data
        next_data = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_data:
            try:
                data = json.loads(next_data.string)
                # Use `or {}` to handle None values
                page_props = (data.get("props") or {}).get("pageProps") or {}
                job_postings = page_props.get("jobPostings") or []

                for posting in job_postings:
                    job = ExtractedJob(
                        title=posting.get("title", ""),
                        source_url=urljoin(url, f"/{posting.get('id', '')}"),
                        location=posting.get("locationName"),
                        department=posting.get("teamName"),
                        employment_type=posting.get("employmentType"),
                    )
                    jobs.append(job)

                if jobs:
                    logger.info("Extracted from Ashby __NEXT_DATA__", job_count=len(jobs))
                    return jobs

            except json.JSONDecodeError:
                pass

        # Parse HTML structure
        # Structure 1: Job posting cards
        job_cards = soup.select('[class*="JobPosting"], [class*="job-posting"]')
        for card in job_cards:
            job = self._parse_job_card(card, url)
            if job:
                jobs.append(job)

        if jobs:
            return jobs

        # Structure 2: Links to job postings
        # Ashby uses UUIDs in job URLs
        job_links = soup.select('a[href*="ashbyhq.com"]')
        seen_urls = set()

        for link in job_links:
            href = link.get("href", "")
            # Match UUID pattern in URL
            if re.search(r"/[a-f0-9-]{36}/?$", href) and href not in seen_urls:
                seen_urls.add(href)
                title = self._clean_text(link.get_text())
                if title and len(title) > 3:
                    jobs.append(ExtractedJob(title=title, source_url=href))

        # Structure 3: Job list items
        list_items = soup.select("li a, div a")
        for item in list_items:
            href = item.get("href", "")
            if re.search(r"/[a-f0-9-]{36}/?$", href) and href not in seen_urls:
                seen_urls.add(href)
                title = self._clean_text(item.get_text())
                if title and len(title) > 5 and not title.lower().startswith(("view", "apply", "see")):
                    job_url = urljoin(url, href) if not href.startswith("http") else href
                    jobs.append(ExtractedJob(title=title, source_url=job_url))

        return jobs

    def _parse_job_card(self, card, base_url: str) -> Optional[ExtractedJob]:
        """Parse a job card element."""
        title_elem = card.select_one("h3, h4, [class*='title']")
        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title:
            return None

        link = card.select_one("a[href]")
        href = link.get("href", "") if link else ""
        job_url = urljoin(base_url, href) if href else base_url

        location_elem = card.select_one("[class*='location']")
        location = self._clean_text(location_elem.get_text()) if location_elem else None

        team_elem = card.select_one("[class*='team'], [class*='department']")
        department = self._clean_text(team_elem.get_text()) if team_elem else None

        return ExtractedJob(
            title=title,
            source_url=job_url,
            location=location,
            department=department,
        )
