"""Discovery source for job aggregator websites.

Scrapes job aggregators to find companies with ATS-based career pages:
- Indeed company pages
- Glassdoor company pages  
- BuiltIn city sites
- Wellfound (AngelList) startup jobs
- Hacker News Who's Hiring threads
"""

import asyncio
import re
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class JobAggregatorsSource(DiscoverySource):
    """Discover companies by scraping job aggregator sites."""
    
    def __init__(self, max_pages_per_source: int = 50):
        self.max_pages_per_source = max_pages_per_source
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_domains: Set[str] = set()
        self._discovered_ats_ids: Set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "job_aggregators"
    
    @property
    def source_description(self) -> str:
        return "Companies discovered from Indeed, Glassdoor, BuiltIn, Wellfound, and HN"
    
    async def initialize(self) -> None:
        """Initialize HTTP client with browser-like headers."""
        self.http_client = httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )
    
    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Yield companies from all job aggregator sources."""
        
        # Run all sources - ordered by effectiveness
        sources = [
            ("remotive", self._discover_from_remotive()),
            ("weworkremotely", self._discover_from_weworkremotely()),
            ("remote_ok", self._discover_from_remote_ok()),
            ("hn_hiring", self._discover_from_hn_hiring()),
            ("workatastartup", self._discover_from_workatastartup()),
            ("techstars", self._discover_from_techstars()),
            ("ycombinator_jobs", self._discover_from_yc_jobs()),
            ("crunchboard", self._discover_from_crunchboard()),
        ]
        
        for source_name, source_gen in sources:
            logger.info(f"Scraping {source_name}...")
            count = 0
            try:
                async for company in source_gen:
                    # Deduplicate by ATS identifier
                    ats_key = f"{company.ats_type}:{company.ats_identifier}"
                    if ats_key in self._discovered_ats_ids:
                        continue
                    
                    if company.ats_identifier:
                        self._discovered_ats_ids.add(ats_key)
                    
                    count += 1
                    yield company
                    
            except Exception as e:
                logger.error(f"Error in {source_name} discovery", error=str(e))
            
            logger.info(f"Found {count} companies from {source_name}")
    
    async def _discover_from_builtin(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape BuiltIn city sites for tech companies."""
        
        # BuiltIn has city-specific sites with company directories
        builtin_sites = [
            ("https://www.builtinnyc.com", "New York"),
            ("https://www.builtinsf.com", "San Francisco"),
            ("https://www.builtinla.com", "Los Angeles"),
            ("https://www.builtinboston.com", "Boston"),
            ("https://www.builtinaustin.com", "Austin"),
            ("https://www.builtinseattle.com", "Seattle"),
            ("https://www.builtincolorado.com", "Colorado"),
            ("https://www.builtinchicago.com", "Chicago"),
            ("https://www.builtin.com", "USA"),
        ]
        
        for base_url, location in builtin_sites:
            try:
                # Scrape company directory pages
                for page in range(1, min(self.max_pages_per_source, 20) + 1):
                    url = f"{base_url}/companies?page={page}"
                    
                    try:
                        response = await self.http_client.get(url)
                        if response.status_code != 200:
                            break
                        
                        html = response.text
                        
                        # Extract ATS board URLs from the page
                        async for company in self._extract_ats_from_html(html, f"builtin_{location.lower().replace(' ', '_')}"):
                            if company.location is None:
                                company.location = location
                            yield company
                        
                        # Check if there's a next page
                        if 'class="pagination"' not in html and '"next"' not in html:
                            break
                            
                        # Rate limit
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.debug(f"Error fetching {url}: {e}")
                        break
                        
            except Exception as e:
                logger.warning(f"Error scraping {base_url}", error=str(e))
    
    async def _discover_from_wellfound(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Wellfound (AngelList) for startup companies."""
        
        # Wellfound has a jobs page with many startups
        try:
            # They have JSON API endpoints
            roles = ["software-engineer", "product-manager", "designer", "data-scientist", "devops"]
            
            for role in roles:
                for page in range(1, min(self.max_pages_per_source, 10) + 1):
                    url = f"https://wellfound.com/role/{role}?page={page}"
                    
                    try:
                        response = await self.http_client.get(url)
                        if response.status_code != 200:
                            break
                        
                        html = response.text
                        
                        # Extract company links and career URLs
                        async for company in self._extract_ats_from_html(html, "wellfound"):
                            yield company
                        
                        # Rate limit
                        await asyncio.sleep(1.5)
                        
                    except Exception as e:
                        logger.debug(f"Error fetching {url}: {e}")
                        break
                        
        except Exception as e:
            logger.warning("Error scraping Wellfound", error=str(e))
    
    async def _discover_from_hn_hiring(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Hacker News Who's Hiring threads."""
        
        try:
            # Get recent "Who's Hiring" threads from HN
            # These are posted monthly with format "Ask HN: Who is hiring? (Month Year)"
            
            # Use HN Algolia API to find recent hiring threads
            search_url = "https://hn.algolia.com/api/v1/search_by_date?query=who%20is%20hiring&tags=ask_hn&hitsPerPage=5"
            
            try:
                response = await self.http_client.get(search_url)
                if response.status_code != 200:
                    return
                
                data = response.json()
                
                for hit in data.get("hits", []):
                    story_id = hit.get("objectID")
                    if not story_id:
                        continue
                    
                    # Fetch the full thread
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    
                    try:
                        item_response = await self.http_client.get(item_url)
                        if item_response.status_code != 200:
                            continue
                        
                        item_data = item_response.json()
                        kids = item_data.get("kids", [])[:200]  # Limit to first 200 comments
                        
                        # Fetch comments in batches
                        for i in range(0, len(kids), 20):
                            batch = kids[i:i+20]
                            
                            tasks = [
                                self._fetch_hn_comment(kid_id)
                                for kid_id in batch
                            ]
                            
                            comments = await asyncio.gather(*tasks, return_exceptions=True)
                            
                            for comment in comments:
                                if isinstance(comment, str):
                                    async for company in self._extract_ats_from_html(comment, "hn_hiring"):
                                        yield company
                            
                            await asyncio.sleep(0.5)
                            
                    except Exception as e:
                        logger.debug(f"Error fetching HN thread {story_id}: {e}")
                        
            except Exception as e:
                logger.warning("Error searching HN", error=str(e))
                
        except Exception as e:
            logger.warning("Error in HN hiring discovery", error=str(e))
    
    async def _fetch_hn_comment(self, comment_id: int) -> Optional[str]:
        """Fetch a single HN comment."""
        try:
            url = f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
            response = await self.http_client.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
        except Exception:
            pass
        return None
    
    async def _discover_from_indeed(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Indeed for company career pages."""
        
        # Indeed has company pages that often link to ATS boards
        # We search for tech jobs and extract company career URLs
        
        search_terms = [
            "software engineer startup",
            "product manager tech",
            "data scientist",
            "backend developer",
            "frontend developer react",
            "devops engineer",
            "machine learning engineer",
        ]
        
        for term in search_terms:
            try:
                # Search Indeed
                url = f"https://www.indeed.com/jobs?q={term.replace(' ', '+')}&l=United+States&sort=date"
                
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    html = response.text
                    
                    # Extract ATS URLs from job listings
                    async for company in self._extract_ats_from_html(html, "indeed"):
                        yield company
                    
                    # Rate limit to avoid blocking
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.debug(f"Error searching Indeed for '{term}': {e}")
                    
            except Exception as e:
                logger.warning(f"Error in Indeed search", error=str(e))
    
    async def _discover_from_remotive(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Remotive for remote-friendly companies."""
        
        try:
            # Remotive lists remote jobs with company info
            categories = ["software-dev", "product", "design", "data"]
            
            for category in categories:
                url = f"https://remotive.com/remote-jobs/{category}"
                
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    html = response.text
                    
                    async for company in self._extract_ats_from_html(html, "remotive"):
                        yield company
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.debug(f"Error fetching Remotive {category}: {e}")
                    
        except Exception as e:
            logger.warning("Error in Remotive discovery", error=str(e))
    
    async def _discover_from_weworkremotely(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape We Work Remotely for companies."""
        try:
            categories = [
                "remote-jobs/full-stack-programming",
                "remote-jobs/front-end-programming", 
                "remote-jobs/back-end-programming",
                "remote-jobs/devops-sysadmin",
                "remote-jobs/product",
                "remote-jobs/design",
                "remote-jobs/data",
            ]
            
            for category in categories:
                url = f"https://weworkremotely.com/{category}"
                
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    async for company in self._extract_ats_from_html(response.text, "weworkremotely"):
                        yield company
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.debug(f"Error fetching WWR {category}: {e}")
                    
        except Exception as e:
            logger.warning("Error in We Work Remotely discovery", error=str(e))
    
    async def _discover_from_remote_ok(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Remote OK for companies."""
        try:
            url = "https://remoteok.com/remote-dev-jobs"
            
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    async for company in self._extract_ats_from_html(response.text, "remote_ok"):
                        yield company
                        
            except Exception as e:
                logger.debug(f"Error fetching Remote OK: {e}")
                
        except Exception as e:
            logger.warning("Error in Remote OK discovery", error=str(e))
    
    async def _discover_from_workatastartup(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Work at a Startup (YC) for companies."""
        try:
            # Work at a Startup is YC's job board
            url = "https://www.workatastartup.com/jobs"
            
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    html = response.text
                    
                    # Extract company cards with career links
                    async for company in self._extract_ats_from_html(html, "workatastartup"):
                        yield company
                    
                    # Also look for YC company data in embedded JSON
                    json_pattern = r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>'
                    matches = re.findall(json_pattern, html, re.DOTALL)
                    
                    for match in matches:
                        try:
                            import json
                            data = json.loads(match)
                            
                            # Extract companies from the state
                            companies = data.get("companies", {}).get("items", [])
                            for co in companies:
                                website = co.get("website")
                                if not website:
                                    continue
                                
                                # Check if they have an ATS career page
                                careers_url = co.get("jobsUrl") or co.get("careersUrl")
                                if not careers_url:
                                    continue
                                
                                ats_type, ats_id = self._detect_ats_from_url(careers_url)
                                
                                if ats_type:
                                    yield DiscoveredCompany(
                                        name=co.get("name", "Unknown"),
                                        domain=urlparse(website).netloc.replace("www.", ""),
                                        website_url=website,
                                        careers_url=careers_url,
                                        source=f"{self.source_name}_workatastartup",
                                        ats_type=ats_type,
                                        ats_identifier=ats_id,
                                        country="US",
                                    )
                                    
                        except Exception:
                            pass
                            
            except Exception as e:
                logger.debug(f"Error fetching Work at a Startup: {e}")
                
        except Exception as e:
            logger.warning("Error in Work at a Startup discovery", error=str(e))
    
    async def _discover_from_techstars(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from Techstars portfolio."""
        try:
            # Techstars has a companies page
            url = "https://www.techstars.com/portfolio"
            
            try:
                response = await self.http_client.get(url, timeout=30.0)
                if response.status_code == 200:
                    async for company in self._extract_ats_from_html(response.text, "techstars"):
                        yield company
                        
            except Exception as e:
                logger.debug(f"Error fetching Techstars: {e}")
                
        except Exception as e:
            logger.warning("Error in Techstars discovery", error=str(e))
    
    async def _discover_from_yc_jobs(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Y Combinator's job board API."""
        try:
            # YC has a public API for their companies
            url = "https://api.ycombinator.com/v0.1/companies"
            
            try:
                headers = {
                    "Accept": "application/json",
                }
                response = await self.http_client.get(url, headers=headers)
                
                if response.status_code == 200:
                    try:
                        companies = response.json()
                        
                        for co in companies[:500]:  # Limit to first 500
                            website = co.get("website")
                            if not website:
                                continue
                            
                            # Look for jobs URL
                            jobs_url = co.get("jobsUrl") or co.get("jobs_url")
                            if not jobs_url:
                                continue
                            
                            ats_type, ats_id = self._detect_ats_from_url(jobs_url)
                            
                            if ats_type:
                                name = co.get("name", "Unknown")
                                
                                yield DiscoveredCompany(
                                    name=name,
                                    domain=urlparse(website).netloc.replace("www.", ""),
                                    website_url=website,
                                    careers_url=jobs_url,
                                    source=f"{self.source_name}_yc",
                                    description=co.get("one_liner") or co.get("long_description"),
                                    industry=co.get("industries", [None])[0] if co.get("industries") else None,
                                    ats_type=ats_type,
                                    ats_identifier=ats_id,
                                    country="US",
                                )
                                
                    except Exception as e:
                        logger.debug(f"Error parsing YC API response: {e}")
                        
            except Exception as e:
                logger.debug(f"Error fetching YC API: {e}")
                
        except Exception as e:
            logger.warning("Error in YC jobs discovery", error=str(e))
    
    async def _discover_from_crunchboard(self) -> AsyncIterator[DiscoveredCompany]:
        """Scrape Crunchbase's job board (Crunchboard)."""
        try:
            url = "https://www.crunchboard.com/jobs"
            
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    async for company in self._extract_ats_from_html(response.text, "crunchboard"):
                        yield company
                        
            except Exception as e:
                logger.debug(f"Error fetching Crunchboard: {e}")
                
        except Exception as e:
            logger.warning("Error in Crunchboard discovery", error=str(e))
    
    def _detect_ats_from_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Detect ATS type and identifier from a URL."""
        if not url:
            return None, None
            
        url_lower = url.lower()
        
        # Greenhouse
        if "boards.greenhouse.io" in url_lower or "greenhouse.io" in url_lower:
            match = re.search(r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', url)
            if match:
                return "greenhouse", match.group(1)
        
        # Lever
        if "jobs.lever.co" in url_lower:
            match = re.search(r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', url)
            if match:
                return "lever", match.group(1)
        
        # Ashby
        if "jobs.ashbyhq.com" in url_lower:
            match = re.search(r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)', url)
            if match:
                return "ashby", match.group(1)
        
        # Workable
        if "apply.workable.com" in url_lower:
            match = re.search(r'apply\.workable\.com/([a-zA-Z0-9_-]+)', url)
            if match:
                return "workable", match.group(1)
        
        return None, None
    
    async def _extract_ats_from_html(
        self, 
        html: str, 
        source: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Extract ATS board URLs from HTML content."""
        
        # Patterns for different ATS providers
        ats_patterns = {
            "greenhouse": [
                r'href=["\']?(https?://boards\.greenhouse\.io/([a-zA-Z0-9_-]+))["\'\s>]',
                r'href=["\']?(https?://[a-zA-Z0-9_-]+\.greenhouse\.io/([a-zA-Z0-9_-]+)?)["\'\s>]',
                r'(boards\.greenhouse\.io/([a-zA-Z0-9_-]+))',
            ],
            "lever": [
                r'href=["\']?(https?://jobs\.lever\.co/([a-zA-Z0-9_-]+))["\'\s>/]',
                r'(jobs\.lever\.co/([a-zA-Z0-9_-]+))',
            ],
            "ashby": [
                r'href=["\']?(https?://jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+))["\'\s>/]',
                r'(jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+))',
            ],
            "workday": [
                r'href=["\']?(https?://[a-zA-Z0-9_-]+\.wd\d+\.myworkdayjobs\.com/[a-zA-Z0-9_/-]+)["\'\s>]',
            ],
            "workable": [
                r'href=["\']?(https?://apply\.workable\.com/([a-zA-Z0-9_-]+))["\'\s>/]',
                r'(apply\.workable\.com/([a-zA-Z0-9_-]+))',
            ],
            "bamboohr": [
                r'href=["\']?(https?://([a-zA-Z0-9_-]+)\.bamboohr\.com/jobs)["\'\s>/]',
            ],
            "recruitee": [
                r'href=["\']?(https?://([a-zA-Z0-9_-]+)\.recruitee\.com)["\'\s>/]',
            ],
            "breezy": [
                r'href=["\']?(https?://([a-zA-Z0-9_-]+)\.breezy\.hr)["\'\s>/]',
            ],
            "smartrecruiters": [
                r'href=["\']?(https?://jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+))["\'\s>/]',
            ],
            "jobvite": [
                r'href=["\']?(https?://jobs\.jobvite\.com/([a-zA-Z0-9_-]+))["\'\s>/]',
            ],
        }
        
        seen_in_page: Set[str] = set()
        
        for ats_type, patterns in ats_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                
                for match in matches:
                    if isinstance(match, tuple):
                        url = match[0]
                        identifier = match[1] if len(match) > 1 else None
                    else:
                        url = match
                        identifier = None
                    
                    # Clean up URL
                    if not url.startswith("http"):
                        url = f"https://{url}"
                    
                    # Extract identifier from URL if not captured
                    if not identifier:
                        identifier = self._extract_identifier(url, ats_type)
                    
                    if not identifier:
                        continue
                    
                    # Skip common non-company identifiers
                    skip_ids = {
                        "embed", "jobs", "api", "static", "assets", "cdn",
                        "www", "app", "admin", "login", "signup", "careers",
                    }
                    if identifier.lower() in skip_ids:
                        continue
                    
                    # Deduplicate within page
                    key = f"{ats_type}:{identifier}"
                    if key in seen_in_page:
                        continue
                    seen_in_page.add(key)
                    
                    # Create company name from identifier
                    name = identifier.replace("-", " ").replace("_", " ").title()
                    
                    # Use captured URL if it's already a valid ATS URL, otherwise build it
                    # This prevents duplication like https://jobs.ashbyhq.com/https://jobs.ashbyhq.com/...
                    if self._is_valid_ats_url(url, ats_type):
                        careers_url = url
                    else:
                        careers_url = self._build_careers_url(ats_type, identifier)
                    
                    yield DiscoveredCompany(
                        name=name,
                        careers_url=careers_url,
                        source=f"{self.source_name}_{source}",
                        source_url=url,
                        ats_type=ats_type,
                        ats_identifier=identifier,
                        country="US",  # These aggregators focus on US
                    )
    
    def _extract_identifier(self, url: str, ats_type: str) -> Optional[str]:
        """Extract company identifier from ATS URL."""
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]
            
            if ats_type == "greenhouse":
                if "boards.greenhouse.io" in parsed.netloc:
                    return path_parts[0] if path_parts else None
            elif ats_type == "lever":
                if "jobs.lever.co" in parsed.netloc:
                    return path_parts[0] if path_parts else None
            elif ats_type == "ashby":
                if "jobs.ashbyhq.com" in parsed.netloc:
                    return path_parts[0] if path_parts else None
            elif ats_type == "workable":
                if "apply.workable.com" in parsed.netloc:
                    return path_parts[0] if path_parts else None
            elif ats_type in ["bamboohr", "recruitee", "breezy"]:
                # These use subdomains
                subdomain = parsed.netloc.split(".")[0]
                if subdomain not in ["www", "jobs", "careers"]:
                    return subdomain
            elif ats_type == "smartrecruiters":
                if "jobs.smartrecruiters.com" in parsed.netloc:
                    return path_parts[0] if path_parts else None
            elif ats_type == "jobvite":
                if "jobs.jobvite.com" in parsed.netloc:
                    return path_parts[0] if path_parts else None
                    
        except Exception:
            pass
        return None
    
    def _is_valid_ats_url(self, url: str, ats_type: str) -> bool:
        """Check if URL is already a valid ATS URL (not needing rebuilding)."""
        if not url or not url.startswith("http"):
            return False
        
        # Check for duplicated URLs (the bug we're fixing)
        if url.count("http") > 1:
            return False
        
        ats_domains = {
            "greenhouse": "boards.greenhouse.io",
            "lever": "jobs.lever.co",
            "ashby": "jobs.ashbyhq.com",
            "workable": "apply.workable.com",
            "smartrecruiters": "jobs.smartrecruiters.com",
            "jobvite": "jobs.jobvite.com",
        }
        
        expected_domain = ats_domains.get(ats_type)
        if expected_domain and expected_domain in url:
            return True
        
        return False
    
    def _build_careers_url(self, ats_type: str, identifier: str) -> str:
        """Build the careers URL for an ATS board."""
        # Ensure identifier doesn't already contain a full URL
        if identifier and identifier.startswith("http"):
            # Extract just the identifier portion
            from urllib.parse import urlparse
            parsed = urlparse(identifier)
            path_parts = [p for p in parsed.path.split("/") if p]
            identifier = path_parts[0] if path_parts else identifier
        
        urls = {
            "greenhouse": f"https://boards.greenhouse.io/{identifier}",
            "lever": f"https://jobs.lever.co/{identifier}",
            "ashby": f"https://jobs.ashbyhq.com/{identifier}",
            "workable": f"https://apply.workable.com/{identifier}",
            "bamboohr": f"https://{identifier}.bamboohr.com/jobs",
            "recruitee": f"https://{identifier}.recruitee.com",
            "breezy": f"https://{identifier}.breezy.hr",
            "smartrecruiters": f"https://jobs.smartrecruiters.com/{identifier}",
            "jobvite": f"https://jobs.jobvite.com/{identifier}",
        }
        return urls.get(ats_type, f"https://{identifier}")
