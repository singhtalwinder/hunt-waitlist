"""
Playwright-based extractor for custom career pages.

This extractor handles career pages that:
1. Require JavaScript rendering
2. Don't use a recognized ATS
3. Have non-standard HTML structures

Uses LLM to intelligently identify job content in rendered HTML.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import instructor
import structlog
from bs4 import BeautifulSoup, Comment
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.engines.extract.base import BaseExtractor, ExtractedJob
from app.engines.render.browser import BrowserPool, get_browser_pool

settings = get_settings()
logger = structlog.get_logger()


# ============================================================================
# LLM Extraction Models
# ============================================================================

class JobListingFromPage(BaseModel):
    """A job listing extracted from a careers page."""
    title: str = Field(description="The exact job title as shown on the page")
    url: Optional[str] = Field(None, description="URL or path to the job posting (e.g., /jobs/123 or full URL)")
    location: Optional[str] = Field(None, description="Job location if shown, or 'Remote' if remote")
    department: Optional[str] = Field(None, description="Department or team name if shown")


class JobListingsResult(BaseModel):
    """Result of extracting job listings from a page."""
    jobs: list[JobListingFromPage] = Field(default_factory=list)
    has_more_pages: bool = Field(default=False, description="True if there's pagination/more jobs")
    next_page_url: Optional[str] = Field(None, description="URL to next page if paginated")


class JobDescriptionResult(BaseModel):
    """Result of extracting a job description."""
    description: str = Field(description="The full job description text")
    requirements: list[str] = Field(default_factory=list, description="Key requirements/qualifications")
    responsibilities: list[str] = Field(default_factory=list, description="Key responsibilities")
    salary_range: Optional[str] = Field(None, description="Salary range if mentioned")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    posted_date: Optional[str] = Field(None, description="When the job was posted if shown")


class CareerPageSelector(BaseModel):
    """Identified selectors for extracting job content."""
    job_list_container: Optional[str] = Field(None, description="CSS selector for the container with job listings")
    job_item_selector: Optional[str] = Field(None, description="CSS selector for individual job items")
    job_title_selector: Optional[str] = Field(None, description="CSS selector for job title within item")
    job_link_selector: Optional[str] = Field(None, description="CSS selector for job link within item")
    pagination_selector: Optional[str] = Field(None, description="CSS selector for pagination/load more")


# ============================================================================
# HTML Simplification
# ============================================================================

def simplify_html_for_llm(html: str, max_chars: int = 50000, keep_structure: bool = True) -> str:
    """
    Simplify HTML for LLM processing while preserving job-relevant structure.
    
    This is more aggressive than the generic simplifier but keeps enough
    structure for the LLM to identify patterns.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Remove noise elements
    noise_tags = [
        "script", "style", "noscript", "svg", "path", "img", "video", 
        "audio", "iframe", "canvas", "map", "picture", "source"
    ]
    for tag in soup.find_all(noise_tags):
        tag.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove common noise containers
    noise_selectors = [
        "nav", "header", "footer", ".nav", ".header", ".footer",
        ".cookie", ".banner", ".popup", ".modal", ".sidebar",
        ".newsletter", ".subscribe", ".social", ".share",
        "[aria-hidden='true']", ".sr-only", ".visually-hidden"
    ]
    for selector in noise_selectors:
        for elem in soup.select(selector):
            elem.decompose()
    
    if keep_structure:
        # Keep minimal attributes that help identify job content
        for tag in soup.find_all(True):
            attrs_to_keep = {}
            
            # Keep href for links
            if tag.get("href"):
                href = tag["href"]
                # Only keep job-related links
                if any(kw in href.lower() for kw in ["job", "career", "position", "apply", "opening"]):
                    attrs_to_keep["href"] = href
            
            # Keep meaningful class names
            if tag.get("class"):
                meaningful = [
                    c for c in tag["class"]
                    if any(kw in c.lower() for kw in [
                        "job", "position", "career", "role", "vacancy", "opening",
                        "title", "location", "team", "department", "list", "card",
                        "item", "posting", "listing"
                    ])
                ]
                if meaningful:
                    attrs_to_keep["class"] = meaningful
            
            # Keep data attributes that might help
            for attr in list(tag.attrs.keys()):
                if attr.startswith("data-") and any(kw in attr.lower() for kw in ["job", "id", "title"]):
                    attrs_to_keep[attr] = tag[attr]
            
            tag.attrs = attrs_to_keep
        
        # Get simplified HTML
        result = str(soup)
    else:
        # Just get text with structure hints
        result = soup.get_text(separator="\n", strip=True)
    
    # Remove excessive whitespace
    result = re.sub(r'\n\s*\n', '\n\n', result)
    result = re.sub(r' +', ' ', result)
    
    # Truncate if needed
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[... content truncated ...]"
    
    return result


def extract_main_content(html: str) -> str:
    """
    Extract the main content area of a page, removing chrome/navigation.
    
    Useful for job description pages where we want just the job content.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Try to find main content area
    main_selectors = [
        "main", "article", "[role='main']", 
        ".main-content", ".content", "#content",
        ".job-description", ".job-content", ".posting-content"
    ]
    
    for selector in main_selectors:
        main = soup.select_one(selector)
        if main:
            return str(main)
    
    # Fallback: return body
    body = soup.find("body")
    return str(body) if body else html


# ============================================================================
# Playwright Extractor
# ============================================================================

class PlaywrightExtractor(BaseExtractor):
    """
    Extractor for custom career pages using Playwright and LLM.
    
    This handles career pages that don't use a recognized ATS system.
    It renders the page with Playwright, then uses LLM to intelligently
    identify and extract job listings.
    """
    
    def __init__(self, browser_pool: Optional[BrowserPool] = None):
        self._browser_pool = browser_pool
        self._client: Optional[instructor.Instructor] = None
        self._cache: dict[str, JobListingsResult] = {}
    
    @property
    def client(self) -> instructor.Instructor:
        """Lazy-load the OpenAI instructor client."""
        if self._client is None:
            self._client = instructor.from_openai(AsyncOpenAI())
        return self._client
    
    async def get_browser_pool(self) -> BrowserPool:
        """Get browser pool, creating if needed."""
        if self._browser_pool is None:
            self._browser_pool = await get_browser_pool()
        return self._browser_pool
    
    async def extract(
        self,
        html: str,
        url: str,
        company_identifier: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """
        Extract jobs from pre-rendered HTML.
        
        If html is empty/minimal, will render with Playwright first.
        """
        # Check if we need to render
        if not html or len(html) < 500:
            render_result = await self._render_page(url)
            if render_result:
                html = render_result
        
        return await self._extract_with_llm(html, url)
    
    async def extract_with_render(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
    ) -> list[ExtractedJob]:
        """
        Render page with Playwright and extract jobs.
        
        This is the main entry point for custom career page extraction.
        """
        logger.info("Playwright extraction starting", url=url)
        
        # Render the page
        html = await self._render_page(url, wait_for_selector)
        if not html:
            logger.warning("Failed to render page", url=url)
            return []
        
        # Extract jobs using LLM
        jobs = await self._extract_with_llm(html, url)
        
        logger.info("Playwright extraction complete", url=url, jobs_found=len(jobs))
        return jobs
    
    async def _render_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
    ) -> Optional[str]:
        """Render a page with Playwright."""
        try:
            pool = await self.get_browser_pool()
            result = await pool.render(
                url,
                wait_for_selector=wait_for_selector,
                wait_for_network_idle=True,
            )
            
            if result.success:
                return result.html
            else:
                logger.warning("Render failed", url=url, error=result.error)
                return None
                
        except Exception as e:
            logger.error("Render error", url=url, error=str(e))
            return None
    
    async def _extract_with_llm(
        self,
        html: str,
        url: str,
    ) -> list[ExtractedJob]:
        """Use LLM to extract job listings from HTML."""
        # Check cache
        content_hash = hashlib.md5(html.encode()).hexdigest()[:16]
        if content_hash in self._cache:
            cached = self._cache[content_hash]
            return self._convert_to_extracted_jobs(cached, url)
        
        # Simplify HTML for LLM
        simplified = simplify_html_for_llm(html, max_chars=40000, keep_structure=True)
        
        try:
            result = await self.client.chat.completions.create(
                model=settings.openai_model,
                response_model=JobListingsResult,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting job listings from career pages.

Given HTML from a company's careers/jobs page, identify ALL job postings listed.

For each job, extract:
- title: The exact job title (required)
- url: The URL or path to view/apply for the job (look for href in links)
- location: Job location if shown
- department: Department/team if shown

IMPORTANT:
- Only extract actual job postings, not navigation links or page elements
- Look for repeated patterns that indicate job listings (lists, cards, rows)
- Preserve exact titles as shown on the page
- URLs can be relative paths (/jobs/123) or full URLs

Also detect if there's pagination (more pages of jobs to load).

Return an empty jobs list if no job postings are found on this page."""
                    },
                    {
                        "role": "user",
                        "content": f"Extract job listings from this careers page HTML:\n\n{simplified}"
                    }
                ],
                max_tokens=4000,
            )
            
            # Cache result
            self._cache[content_hash] = result
            
            return self._convert_to_extracted_jobs(result, url)
            
        except Exception as e:
            logger.error("LLM extraction failed", url=url, error=str(e))
            return []
    
    def _convert_to_extracted_jobs(
        self,
        result: JobListingsResult,
        base_url: str,
    ) -> list[ExtractedJob]:
        """Convert LLM result to ExtractedJob list."""
        jobs = []
        seen_urls = set()
        
        for job in result.jobs:
            # Build full URL
            if job.url:
                if job.url.startswith("http"):
                    full_url = job.url
                elif job.url.startswith("/"):
                    full_url = urljoin(base_url, job.url)
                else:
                    full_url = urljoin(base_url, "/" + job.url)
            else:
                full_url = base_url
            
            # Deduplicate
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            jobs.append(ExtractedJob(
                title=job.title,
                source_url=full_url,
                location=job.location,
                department=job.department,
            ))
        
        return jobs
    
    async def extract_job_description(
        self,
        url: str,
        render: bool = True,
    ) -> Optional[JobDescriptionResult]:
        """
        Extract full job description from a job posting page.
        
        Args:
            url: URL of the job posting
            render: Whether to render with Playwright (default True)
            
        Returns:
            JobDescriptionResult with description and structured data
        """
        logger.info("Extracting job description", url=url)
        
        # Get page content
        if render:
            html = await self._render_page(url)
            if not html:
                return None
        else:
            # Use httpx for simple fetch
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    html = resp.text
            except Exception as e:
                logger.error("Failed to fetch page", url=url, error=str(e))
                return None
        
        # Extract main content area
        main_content = extract_main_content(html)
        simplified = simplify_html_for_llm(main_content, max_chars=30000, keep_structure=False)
        
        try:
            result = await self.client.chat.completions.create(
                model=settings.openai_model,
                response_model=JobDescriptionResult,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting job descriptions from job posting pages.

Extract the complete job description including:
- description: The full job description text (comprehensive, including all sections)
- requirements: Key requirements/qualifications as a list
- responsibilities: Key responsibilities as a list
- salary_range: Salary range if mentioned anywhere
- employment_type: Full-time, Part-time, Contract, etc.
- posted_date: When the job was posted if visible

For the description, include ALL relevant content:
- About the role
- What you'll do
- What we're looking for
- Benefits
- About the company (brief mention)

Do NOT include:
- Navigation elements
- Legal boilerplate
- Cookie notices
- Social share buttons"""
                    },
                    {
                        "role": "user",
                        "content": f"Extract the job description from this page content:\n\n{simplified}"
                    }
                ],
                max_tokens=4000,
            )
            
            return result
            
        except Exception as e:
            logger.error("LLM description extraction failed", url=url, error=str(e))
            return None


# ============================================================================
# Service Functions
# ============================================================================

async def extract_jobs_from_custom_page(
    url: str,
    browser_pool: Optional[BrowserPool] = None,
) -> list[ExtractedJob]:
    """
    Extract jobs from a custom careers page.
    
    Convenience function that handles browser pool lifecycle.
    """
    extractor = PlaywrightExtractor(browser_pool)
    return await extractor.extract_with_render(url)


async def extract_description_from_page(
    url: str,
    browser_pool: Optional[BrowserPool] = None,
    render: bool = True,
) -> Optional[str]:
    """
    Extract job description from a job posting page.
    
    Returns plain text description or None if extraction failed.
    """
    extractor = PlaywrightExtractor(browser_pool)
    result = await extractor.extract_job_description(url, render=render)
    
    if result:
        return result.description
    return None
