"""Discovery source for Y Combinator companies.

Discovers companies from:
- YC Company Directory (ycombinator.com/companies)
- Work at a Startup (workatastartup.com)

These are startup companies, many of which may not post on major job boards.
"""

import json
import re
from typing import AsyncIterator, Optional
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class YCCompaniesSource(DiscoverySource):
    """Discover companies from Y Combinator directory."""
    
    def __init__(self, batch_filter: Optional[str] = None, status_filter: str = "Active"):
        """Initialize the YC source.
        
        Args:
            batch_filter: Optional YC batch to filter by (e.g., "W24", "S23")
            status_filter: Company status filter ("Active", "Inactive", "Acquired", "Public")
        """
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_domains: set[str] = set()
        self.batch_filter = batch_filter
        self.status_filter = status_filter
    
    @property
    def source_name(self) -> str:
        return "yc_directory"
    
    @property
    def source_description(self) -> str:
        return "Y Combinator portfolio companies"
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
    
    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Yield companies from YC sources."""
        # Discover from YC company directory
        async for company in self._discover_yc_directory():
            yield company
        
        # Discover from Work at a Startup
        async for company in self._discover_workatastartup():
            yield company
    
    async def _discover_yc_directory(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from YC's company directory."""
        try:
            # YC company directory - this page loads companies dynamically
            # We'll look for the embedded JSON data
            base_url = "https://www.ycombinator.com/companies"
            
            response = await self.http_client.get(base_url)
            if response.status_code != 200:
                logger.warning("Failed to fetch YC directory", status=response.status_code)
                return
            
            html = response.text
            
            # YC embeds company data in a script tag as JSON
            # Look for the Next.js data or similar embedded JSON
            patterns = [
                r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
                r'window\.__DATA__\s*=\s*({.+?});',
                r'"companies"\s*:\s*(\[.+?\])',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        async for company in self._parse_yc_data(data, base_url):
                            yield company
                        return  # Success, don't try other patterns
                    except json.JSONDecodeError:
                        continue
            
            # Fallback: extract from HTML structure
            async for company in self._extract_from_yc_html(html, base_url):
                yield company
                
        except Exception as e:
            logger.error("Error in YC directory discovery", error=str(e))
    
    async def _parse_yc_data(
        self,
        data: dict,
        source_url: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Parse YC company data from JSON."""
        companies = []
        
        # Navigate the data structure to find companies
        if isinstance(data, dict):
            if "props" in data:
                # Next.js structure
                props = data.get("props", {})
                page_props = props.get("pageProps", {})
                companies = page_props.get("companies", [])
            elif "companies" in data:
                companies = data["companies"]
        elif isinstance(data, list):
            companies = data
        
        for company_data in companies:
            try:
                # Filter by status if specified
                status = company_data.get("status", "Active")
                if self.status_filter and status != self.status_filter:
                    continue
                
                # Filter by batch if specified
                batch = company_data.get("batch", "")
                if self.batch_filter and self.batch_filter not in batch:
                    continue
                
                name = company_data.get("name", "")
                if not name:
                    continue
                
                # Extract relevant fields
                website = company_data.get("website", "") or company_data.get("url", "")
                
                # Extract location
                location = company_data.get("location", "") or company_data.get("city", "")
                country = None
                
                # Try to detect US companies
                if location:
                    us_indicators = [
                        "USA", "United States", ", US", ", CA", ", NY", 
                        ", TX", ", WA", ", MA", "San Francisco", "New York",
                        "Los Angeles", "Seattle", "Boston", "Austin", "Chicago",
                    ]
                    if any(ind in location for ind in us_indicators):
                        country = "US"
                
                company = DiscoveredCompany(
                    name=name,
                    website_url=website if website else None,
                    source=self.source_name,
                    source_url=source_url,
                    location=location,
                    country=country,
                    description=company_data.get("one_liner", "") or company_data.get("description", ""),
                    industry=company_data.get("industry", "") or ", ".join(company_data.get("tags", [])),
                    employee_count=company_data.get("team_size"),
                    funding_stage=batch,  # Use YC batch as funding stage indicator
                )
                
                if company.domain and company.domain not in self._discovered_domains:
                    self._discovered_domains.add(company.domain)
                    yield company
                elif not company.domain and website:
                    yield company
                    
            except Exception as e:
                logger.debug("Error parsing YC company data", error=str(e))
    
    async def _extract_from_yc_html(
        self,
        html: str,
        source_url: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Extract companies from YC directory HTML when JSON is not available."""
        # Look for company cards/links
        patterns = [
            # Company links
            r'href="/companies/([^"]+)"[^>]*>([^<]+)</a>',
            # Company cards with data
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    slug_or_url = match[0]
                    name = match[1].strip()
                    
                    if not name or len(name) < 2:
                        continue
                    
                    # Skip navigation/UI text
                    skip_words = ["view", "more", "see", "all", "companies", "jobs"]
                    if name.lower() in skip_words:
                        continue
                    
                    # If it's a slug, construct the YC company page URL
                    if not slug_or_url.startswith("http"):
                        company_page = f"https://www.ycombinator.com/companies/{slug_or_url}"
                        website = None
                    else:
                        company_page = None
                        website = slug_or_url
                    
                    company = DiscoveredCompany(
                        name=name,
                        website_url=website,
                        source=self.source_name,
                        source_url=company_page or source_url,
                    )
                    
                    if company.domain and company.domain not in self._discovered_domains:
                        self._discovered_domains.add(company.domain)
                        yield company
                        
                except Exception as e:
                    logger.debug("Error extracting YC company from HTML", error=str(e))
    
    async def _discover_workatastartup(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from Work at a Startup (YC's job board)."""
        try:
            # Work at a Startup lists jobs from YC companies
            base_url = "https://www.workatastartup.com"
            
            # The companies page lists all companies with jobs
            companies_url = f"{base_url}/companies"
            
            response = await self.http_client.get(companies_url)
            if response.status_code != 200:
                logger.warning(
                    "Failed to fetch Work at a Startup",
                    status=response.status_code,
                )
                return
            
            html = response.text
            
            # Try to find embedded JSON data
            json_match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
                html,
                re.DOTALL,
            )
            
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    props = data.get("props", {}).get("pageProps", {})
                    companies = props.get("companies", []) or props.get("startups", [])
                    
                    for company_data in companies:
                        try:
                            name = company_data.get("name", "")
                            if not name:
                                continue
                            
                            website = company_data.get("website", "")
                            slug = company_data.get("slug", "")
                            
                            # Build careers URL on workatastartup
                            careers_url = None
                            if slug:
                                careers_url = f"{base_url}/companies/{slug}"
                            
                            location = company_data.get("location", "")
                            country = None
                            if location:
                                us_indicators = [
                                    "USA", "US", ", CA", ", NY", ", TX",
                                    "San Francisco", "New York", "Remote",
                                ]
                                if any(ind in location for ind in us_indicators):
                                    country = "US"
                            
                            company = DiscoveredCompany(
                                name=name,
                                website_url=website if website else None,
                                careers_url=careers_url,
                                source=f"{self.source_name}_waas",
                                source_url=companies_url,
                                location=location,
                                country=country,
                                description=company_data.get("one_liner", ""),
                                employee_count=company_data.get("team_size"),
                                industry=company_data.get("industry", ""),
                            )
                            
                            if company.domain and company.domain not in self._discovered_domains:
                                self._discovered_domains.add(company.domain)
                                yield company
                                
                        except Exception as e:
                            logger.debug("Error parsing WAAS company", error=str(e))
                            
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse WAAS JSON", error=str(e))
            
            # Fallback: extract from HTML
            async for company in self._extract_from_waas_html(html, companies_url):
                yield company
                
        except Exception as e:
            logger.error("Error in Work at a Startup discovery", error=str(e))
    
    async def _extract_from_waas_html(
        self,
        html: str,
        source_url: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Extract companies from Work at a Startup HTML."""
        # Look for company links
        pattern = r'href="/companies/([^"]+)"[^>]*>([^<]*)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        for match in matches:
            try:
                slug = match[0]
                name = match[1].strip()
                
                if not name or len(name) < 2:
                    # Use slug as name
                    name = slug.replace("-", " ").title()
                
                # Skip UI elements
                if slug in ["", "jobs", "login", "signup"]:
                    continue
                
                company = DiscoveredCompany(
                    name=name,
                    careers_url=f"https://www.workatastartup.com/companies/{slug}",
                    source=f"{self.source_name}_waas",
                    source_url=source_url,
                )
                
                if company.domain and company.domain not in self._discovered_domains:
                    self._discovered_domains.add(company.domain)
                    yield company
                elif not company.domain:
                    yield company
                    
            except Exception as e:
                logger.debug("Error extracting WAAS company from HTML", error=str(e))
