"""Discovery source for GitHub organizations.

Discovers companies by finding active GitHub organizations that:
- Have a website in their profile
- Are located in the US
- Have recent activity (commits in the last 6 months)

This finds tech companies that may not be on traditional job boards.
"""

import os
import re
from datetime import datetime, timedelta
from typing import AsyncIterator, Optional

import httpx
import structlog

from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class GitHubOrgsSource(DiscoverySource):
    """Discover companies from GitHub organizations."""
    
    # US cities and states for filtering
    US_LOCATIONS = [
        # Major cities
        "san francisco", "new york", "los angeles", "seattle", "boston",
        "austin", "chicago", "denver", "miami", "atlanta", "portland",
        "san diego", "phoenix", "dallas", "houston", "philadelphia",
        "washington", "dc", "brooklyn", "manhattan", "oakland",
        "palo alto", "mountain view", "menlo park", "cupertino", "sunnyvale",
        "redwood city", "san jose", "santa clara", "fremont",
        # States
        "california", "new york", "texas", "washington", "massachusetts",
        "colorado", "florida", "georgia", "oregon", "illinois",
        "pennsylvania", "north carolina", "virginia", "arizona",
        # State abbreviations
        ", ca", ", ny", ", tx", ", wa", ", ma", ", co", ", fl", ", ga",
        ", or", ", il", ", pa", ", nc", ", va", ", az",
        # Country indicators
        "usa", "united states", "u.s.a", "u.s.",
    ]
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        min_repos: int = 3,
        min_members: int = 5,
        require_website: bool = True,
    ):
        """Initialize the GitHub source.
        
        Args:
            github_token: GitHub API token for higher rate limits
            min_repos: Minimum number of public repos
            min_members: Minimum number of public members
            require_website: Only include orgs with a website
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.min_repos = min_repos
        self.min_members = min_members
        self.require_website = require_website
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_domains: set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "github_orgs"
    
    @property
    def source_description(self) -> str:
        return "Tech companies discovered from GitHub organizations"
    
    async def initialize(self) -> None:
        """Initialize HTTP client with GitHub API headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "HuntBot/1.0 Company Discovery",
        }
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers=headers,
        )
    
    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Yield companies from GitHub organizations."""
        # Search for organizations in US tech hubs
        search_queries = [
            "location:San Francisco type:org",
            "location:New York type:org",
            "location:Seattle type:org",
            "location:Austin type:org",
            "location:Boston type:org",
            "location:Los Angeles type:org",
            "location:Denver type:org",
            "location:Chicago type:org",
            "location:USA type:org",
            "location:California type:org",
        ]
        
        for query in search_queries:
            try:
                async for company in self._search_orgs(query):
                    yield company
            except Exception as e:
                logger.warning("Error in GitHub org search", query=query, error=str(e))
        
        # Also search for recently created organizations
        async for company in self._discover_recent_orgs():
            yield company
    
    async def _search_orgs(self, query: str) -> AsyncIterator[DiscoveredCompany]:
        """Search GitHub for organizations matching query."""
        page = 1
        per_page = 30
        max_pages = 10  # Limit to avoid rate limiting
        
        while page <= max_pages:
            try:
                url = "https://api.github.com/search/users"
                params = {
                    "q": query,
                    "per_page": per_page,
                    "page": page,
                    "sort": "followers",
                    "order": "desc",
                }
                
                response = await self.http_client.get(url, params=params)
                
                # Check rate limiting
                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        logger.warning("GitHub rate limit reached")
                        return
                
                if response.status_code != 200:
                    logger.warning(
                        "GitHub search failed",
                        status=response.status_code,
                        query=query,
                    )
                    return
                
                data = response.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                for org_data in items:
                    if org_data.get("type") != "Organization":
                        continue
                    
                    async for company in self._process_org(org_data):
                        yield company
                
                # Check if there are more pages
                total_count = data.get("total_count", 0)
                if page * per_page >= total_count:
                    break
                
                page += 1
                
            except Exception as e:
                logger.warning("Error searching GitHub orgs", query=query, error=str(e))
                break
    
    async def _process_org(self, org_data: dict) -> AsyncIterator[DiscoveredCompany]:
        """Process a GitHub organization and yield if it meets criteria."""
        try:
            login = org_data.get("login", "")
            
            # Fetch full org details
            org_url = f"https://api.github.com/orgs/{login}"
            response = await self.http_client.get(org_url)
            
            if response.status_code != 200:
                return
            
            org_details = response.json()
            
            # Check minimum requirements
            public_repos = org_details.get("public_repos", 0)
            if public_repos < self.min_repos:
                return
            
            # Check for website
            website = org_details.get("blog", "") or ""
            if self.require_website and not website:
                return
            
            # Ensure website starts with http
            if website and not website.startswith("http"):
                website = f"https://{website}"
            
            # Skip non-company organizations
            name = org_details.get("name") or login
            description = (org_details.get("description", "") or "").lower()
            
            # Skip educational institutions
            edu_keywords = ["university", "college", "school", "lab", "research", "academic", "edu"]
            if any(kw in name.lower() or kw in description for kw in edu_keywords):
                return
            if website and ".edu" in website:
                return
            
            # Skip non-profits, government, sports, etc.
            skip_keywords = [
                "foundation", "non-profit", "nonprofit", "charity",
                "government", "city of", "county", "state of",
                "giants", "49ers", "warriors", "athletics", "sports", "team",
                "pride", "parade", "festival", "event",
                "church", "temple", "mosque", "synagogue", "religious",
                "museum", "library", "archive",
            ]
            if any(kw in name.lower() or kw in description for kw in skip_keywords):
                return
            
            # Skip if domain is github.com or github.io (not a real company website)
            if website:
                if "github.com" in website or "github.io" in website:
                    return
            
            # Check location
            location = org_details.get("location", "") or ""
            country = None
            
            if location:
                location_lower = location.lower()
                for us_loc in self.US_LOCATIONS:
                    if us_loc in location_lower:
                        country = "US"
                        break
            
            company = DiscoveredCompany(
                name=name,
                website_url=website,
                source=self.source_name,
                source_url=org_details.get("html_url", f"https://github.com/{login}"),
                location=location,
                country=country,
                description=org_details.get("description", ""),
                employee_count=org_details.get("public_members_count"),
            )
            
            # Dedupe by domain
            if company.domain and company.domain not in self._discovered_domains:
                self._discovered_domains.add(company.domain)
                yield company
            elif not company.domain and website:
                yield company
                
        except Exception as e:
            logger.debug("Error processing GitHub org", org=org_data.get("login"), error=str(e))
    
    async def _discover_recent_orgs(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover recently created organizations."""
        # Search for orgs created in the last 6 months
        six_months_ago = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        query = f"type:org created:>{six_months_ago}"
        
        try:
            async for company in self._search_orgs(query):
                yield company
        except Exception as e:
            logger.warning("Error discovering recent orgs", error=str(e))
    
    async def _check_org_activity(self, login: str) -> bool:
        """Check if an organization has recent activity."""
        try:
            # Get recent events
            url = f"https://api.github.com/orgs/{login}/events"
            response = await self.http_client.get(url, params={"per_page": 10})
            
            if response.status_code != 200:
                return False
            
            events = response.json()
            if not events:
                return False
            
            # Check if there's activity in the last 6 months
            six_months_ago = datetime.utcnow() - timedelta(days=180)
            
            for event in events:
                created_at = event.get("created_at", "")
                if created_at:
                    try:
                        event_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if event_date.replace(tzinfo=None) > six_months_ago:
                            return True
                    except ValueError:
                        continue
            
            return False
            
        except Exception:
            return False
