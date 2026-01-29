"""LLM-based fallback extractor using GPT-4.1."""

import hashlib
import json
from typing import Optional

import instructor
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.extract.base import BaseExtractor, ExtractedJob

settings = get_settings()
logger = structlog.get_logger()


class JobListing(BaseModel):
    """Job listing extracted by LLM."""

    title: str = Field(description="Job title")
    location: Optional[str] = Field(None, description="Job location or 'Remote'")
    department: Optional[str] = Field(None, description="Department or team name")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    url_path: Optional[str] = Field(None, description="Relative URL path to job posting, e.g., /jobs/123")


class ExtractedJobs(BaseModel):
    """List of extracted jobs."""

    jobs: list[JobListing] = Field(default_factory=list)


class LLMFallbackExtractor(BaseExtractor):
    """LLM-based extractor for unrecognized page structures."""

    def __init__(self):
        self._cache: dict[str, list[ExtractedJob]] = {}
        self._client = None
        
    @property
    def client(self):
        """Lazy-load the OpenAI client only when needed."""
        if self._client is None:
            self._client = instructor.from_openai(AsyncOpenAI())
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if LLM extraction is available (API key configured)."""
        api_key = settings.openai_api_key
        return bool(api_key and api_key not in ("", "sk-placeholder"))

    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """Extract jobs using LLM analysis."""
        # Skip if no API key configured
        if not self.is_available:
            logger.debug("LLM extraction skipped - no OpenAI API key configured")
            return []
        # Simplify HTML to reduce tokens
        simplified = self._simplify_html(html)

        # Check cache based on content hash
        content_hash = hashlib.md5(simplified.encode()).hexdigest()[:16]
        if content_hash in self._cache:
            logger.info("LLM extraction cache hit", hash=content_hash)
            return self._cache[content_hash]

        logger.info("Running LLM extraction", url=url, html_size=len(simplified))

        try:
            result = await self.client.chat.completions.create(
                model=settings.openai_model,
                response_model=ExtractedJobs,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a job listing extractor. Given HTML from a careers page, extract all job listings.

For each job, extract:
- title: The job title (required)
- location: Location if mentioned, or "Remote" if remote
- department: Department/team if mentioned
- employment_type: Full-time, Part-time, Contract, etc. if mentioned
- url_path: The relative URL path to the job posting (e.g., /jobs/123 or /careers/software-engineer)

Only extract actual job postings, not navigation items, headers, or other page elements.
If no jobs are found, return an empty list."""
                    },
                    {
                        "role": "user",
                        "content": f"Extract job listings from this HTML:\n\n{simplified}"
                    }
                ],
                max_tokens=4000,
            )

            jobs = []
            for job_listing in result.jobs:
                # Build full URL
                job_url = url
                if job_listing.url_path:
                    if job_listing.url_path.startswith("http"):
                        job_url = job_listing.url_path
                    elif job_listing.url_path.startswith("/"):
                        # Build absolute URL
                        from urllib.parse import urljoin
                        job_url = urljoin(url, job_listing.url_path)

                job = ExtractedJob(
                    title=job_listing.title,
                    source_url=job_url,
                    location=job_listing.location,
                    department=job_listing.department,
                    employment_type=job_listing.employment_type,
                )
                jobs.append(job)

            # Cache result
            self._cache[content_hash] = jobs

            logger.info("LLM extraction complete", job_count=len(jobs))
            return jobs

        except Exception as e:
            logger.error("LLM extraction failed", error=str(e))
            return []

    def _simplify_html(self, html: str, max_chars: int = 30000) -> str:
        """
        Simplify HTML to reduce token usage.

        Removes:
        - Scripts, styles, comments
        - Most attributes
        - Navigation, footer, header elements
        - Excess whitespace
        """
        from bs4 import BeautifulSoup, Comment

        soup = BeautifulSoup(html, "lxml")

        # Remove non-content elements
        for tag in soup.find_all(["script", "style", "noscript", "svg", "path", "img", "video", "audio", "iframe"]):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove navigation/header/footer
        for selector in ["nav", "header", "footer", ".nav", ".header", ".footer", ".cookie", ".banner", ".popup", ".modal"]:
            for elem in soup.select(selector):
                elem.decompose()

        # Remove most attributes but keep href, class for context
        for tag in soup.find_all(True):
            attrs_to_keep = {}
            if tag.get("href"):
                attrs_to_keep["href"] = tag["href"]
            if tag.get("class"):
                # Keep only class names that might be meaningful
                meaningful_classes = [
                    c for c in tag["class"]
                    if any(kw in c.lower() for kw in ["job", "position", "career", "role", "title", "location", "team", "department"])
                ]
                if meaningful_classes:
                    attrs_to_keep["class"] = meaningful_classes

            tag.attrs = attrs_to_keep

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Remove excessive blank lines
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        # Truncate if too long
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        return text

    def clear_cache(self):
        """Clear the extraction cache."""
        self._cache.clear()
