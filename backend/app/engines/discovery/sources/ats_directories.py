"""Discovery source for ATS customer directories.

Discovers companies from:
- Greenhouse customer showcase
- Lever customer testimonials
- Ashby customer directory

These companies definitely have ATS-based career pages.
"""

import asyncio
import re
from typing import AsyncIterator, List, Optional

import httpx
import structlog

from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class ATSDirectoriesSource(DiscoverySource):
    """Discover companies from ATS provider customer pages."""
    
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_domains: set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "ats_directories"
    
    @property
    def source_description(self) -> str:
        return "Companies discovered from Greenhouse, Lever, and Ashby customer pages"
    
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
        """Yield companies from ATS directories."""
        # Discover from each ATS
        async for company in self._discover_greenhouse():
            yield company
        
        async for company in self._discover_lever():
            yield company
        
        async for company in self._discover_ashby():
            yield company
    
    async def _discover_greenhouse(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from Greenhouse customer pages."""
        try:
            # Greenhouse showcases customers on their website
            # We can find companies by looking at their public job boards
            greenhouse_sources = [
                "https://www.greenhouse.io/customers",
                "https://www.greenhouse.io/customer-stories",
            ]
            
            for url in greenhouse_sources:
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    html = response.text
                    async for company in self._extract_companies_from_html(
                        html, "greenhouse", url
                    ):
                        yield company
                        
                except Exception as e:
                    logger.warning("Error fetching Greenhouse page", url=url, error=str(e))
            
            # Also try to find Greenhouse job boards directly
            # Pattern: boards.greenhouse.io/{company}
            async for company in self._discover_greenhouse_boards():
                yield company
                
        except Exception as e:
            logger.error("Error in Greenhouse discovery", error=str(e))
    
    async def _discover_greenhouse_boards(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies by finding Greenhouse job board URLs."""
        discovered_boards = set()
        
        # Method 1: Try to fetch the Greenhouse sitemap
        logger.info("Fetching Greenhouse sitemap...")
        try:
            sitemap_urls = [
                "https://boards.greenhouse.io/sitemap.xml",
                "https://boards.greenhouse.io/robots.txt",
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = await self.http_client.get(sitemap_url)
                    if response.status_code == 200:
                        content = response.text
                        # Extract board names from sitemap or robots.txt
                        board_pattern = r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)'
                        matches = re.findall(board_pattern, content)
                        for board in matches:
                            if board.lower() not in ['sitemap', 'robots', 'api', 'embed']:
                                discovered_boards.add(board.lower())
                        logger.info(f"Found {len(discovered_boards)} boards from {sitemap_url}")
                except Exception as e:
                    logger.debug(f"Could not fetch {sitemap_url}: {e}")
        except Exception as e:
            logger.warning("Error fetching Greenhouse sitemap", error=str(e))
        
        # Method 2: Scrape job aggregators that list Greenhouse boards
        logger.info("Scraping job aggregator references...")
        try:
            # These pages often list many Greenhouse job boards
            aggregator_urls = [
                "https://www.builtinnyc.com/companies",
                "https://www.builtinsf.com/companies", 
                "https://www.builtinla.com/companies",
                "https://www.builtinboston.com/companies",
                "https://www.builtinaustin.com/companies",
                "https://www.builtinseattle.com/companies",
                "https://www.builtincolorado.com/companies",
                "https://www.builtinchicago.com/companies",
            ]
            
            for url in aggregator_urls:
                try:
                    response = await self.http_client.get(url, timeout=15.0)
                    if response.status_code == 200:
                        content = response.text
                        # Find all Greenhouse board references
                        board_pattern = r'(?:boards\.greenhouse\.io|greenhouse\.io/embed/job_board/js)/([a-zA-Z0-9_-]+)'
                        matches = re.findall(board_pattern, content, re.IGNORECASE)
                        for board in matches:
                            discovered_boards.add(board.lower())
                except Exception as e:
                    logger.debug(f"Could not fetch {url}: {e}")
        except Exception as e:
            logger.warning("Error scraping aggregators", error=str(e))
        
        # Method 3: Known boards as fallback (existing list + expanded)
        known_boards = [
            # Developer tools & infrastructure
            "airtable", "notion", "figma", "linear", "vercel", "supabase",
            "railway", "planetscale", "prisma", "temporal", "dagster",
            "prefect", "airbyte", "dbt-labs", "fivetran", "census",
            "hightouch", "rudderstack", "segment", "amplitude", "mixpanel",
            "posthog", "heap", "fullstory", "hotjar", "maze",
            "retool", "appsmith", "tooljet", "budibase", "nocodb",
            # Productivity & collaboration
            "loom", "miro", "pitch", "coda", "rows", "clickup",
            "height", "shortcut", "asana", "monday", "smartsheet",
            # Sales & CRM
            "attio", "affinity", "copper", "close", "outreach",
            "salesloft", "gong", "chorus", "clari", "aviso",
            "apollo-io", "zoominfo", "lusha", "clearbit", "clay",
            # Fintech & HR
            "ramp", "brex", "mercury", "gusto", "rippling",
            "deel", "remote", "oyster", "papaya-global", "lattice",
            "culture-amp", "15five", "lever", "greenhouse",
            # AI & ML companies
            "anthropic", "openai", "cohere", "huggingface", "stability-ai",
            "runway", "jasper", "copy-ai", "writer", "grammarly",
            "replit", "sourcegraph", "tabnine", "cursor", "codeium",
            # Expanded list - more startups
            "webflow", "framer", "bubble", "glide", "adalo",
            "zapier", "make", "tray", "workato", "pipedream",
            "datadog", "newrelic", "splunk", "elastic", "grafana",
            "snowflake", "databricks", "confluent", "cockroachlabs", "timescale",
            "hashicorp", "pulumi", "terraform", "vault", "consul",
            "stripe", "plaid", "marqeta", "unit", "treasury-prime",
            "twilio", "sendgrid", "mailchimp", "klaviyo", "customer-io",
            "auth0", "okta", "onelogin", "jumpcloud", "tailscale",
            "cloudflare", "fastly", "akamai", "netlify", "fly",
            "github", "gitlab", "bitbucket", "codecov", "snyk",
            "sentry", "rollbar", "bugsnag", "logrocket", "smartbear",
            "pagerduty", "opsgenie", "victorops", "incident-io", "firehydrant",
            "launchdarkly", "split", "optimizely", "statsig", "eppo",
            "contentful", "sanity", "strapi", "hygraph", "storyblok",
            "algolia", "typesense", "meilisearch", "pinecone", "weaviate",
            "neon", "supabase", "planetscale", "fauna", "xata",
            "vercel", "netlify", "render", "railway", "fly-io",
            "docker", "kubernetes", "rancher", "portainer", "mirantis",
        ]
        
        for board in known_boards:
            discovered_boards.add(board.lower())
        
        logger.info(f"Total Greenhouse boards to check: {len(discovered_boards)}")
        
        # Verify boards in parallel batches for speed
        async for company in self._verify_boards_parallel(
            list(discovered_boards), 
            "greenhouse",
            "https://boards.greenhouse.io",
        ):
            yield company
    
    async def _verify_boards_parallel(
        self,
        board_names: List[str],
        ats_type: str,
        base_url: str,
        batch_size: int = 20,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Verify multiple boards in parallel for speed."""
        
        async def check_board(board_name: str) -> Optional[DiscoveredCompany]:
            """Check if a board exists and return company if valid."""
            try:
                careers_url = f"{base_url}/{board_name}"
                response = await self.http_client.head(careers_url, timeout=10.0)
                
                if response.status_code != 200:
                    return None
                
                name = board_name.replace("-", " ").replace("_", " ").title()
                
                return DiscoveredCompany(
                    name=name,
                    careers_url=careers_url,
                    source=f"{self.source_name}_{ats_type}",
                    source_url=careers_url,
                    ats_type=ats_type,
                    ats_identifier=board_name,
                )
            except Exception:
                return None
        
        # Process in batches
        for i in range(0, len(board_names), batch_size):
            batch = board_names[i:i + batch_size]
            
            # Run batch in parallel
            results = await asyncio.gather(
                *[check_board(name) for name in batch],
                return_exceptions=True,
            )
            
            for result in results:
                if isinstance(result, DiscoveredCompany):
                    if result.domain and result.domain not in self._discovered_domains:
                        self._discovered_domains.add(result.domain)
                        yield result
                    elif not result.domain:
                        yield result
    
    async def _discover_lever(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from Lever customer pages."""
        try:
            lever_sources = [
                "https://www.lever.co/customers",
                "https://www.lever.co/customers/all",
            ]
            
            for url in lever_sources:
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    html = response.text
                    async for company in self._extract_companies_from_html(
                        html, "lever", url
                    ):
                        yield company
                        
                except Exception as e:
                    logger.warning("Error fetching Lever page", url=url, error=str(e))
            
            # Known Lever customers
            known_lever = [
                "netflix", "spotify", "coinbase", "lyft", "doordash",
                "instacart", "robinhood", "chime", "plaid", "marqeta",
                "affirm", "klarna", "afterpay", "zip", "sezzle",
                "carta", "capchase", "pipe", "clearco", "parker",
                "vanta", "drata", "secureframe", "launchdarkly", "split",
                "optimizely", "contentful", "sanity", "strapi", "ghost",
                "webflow", "framer", "bubble", "glide", "adalo",
                "zapier", "make", "n8n", "tray", "workato",
            ]
            
            for company_name in known_lever:
                try:
                    careers_url = f"https://jobs.lever.co/{company_name}"
                    
                    try:
                        response = await self.http_client.head(careers_url)
                        if response.status_code != 200:
                            continue
                    except Exception:
                        continue
                    
                    name = company_name.replace("-", " ").replace("_", " ").title()
                    
                    company = DiscoveredCompany(
                        name=name,
                        careers_url=careers_url,
                        source=f"{self.source_name}_lever",
                        source_url=careers_url,
                        ats_type="lever",
                        ats_identifier=company_name,
                    )
                    
                    if company.domain and company.domain not in self._discovered_domains:
                        self._discovered_domains.add(company.domain)
                        yield company
                    elif not company.domain:
                        yield company
                        
                except Exception as e:
                    logger.debug("Error checking Lever board", company=company_name, error=str(e))
                    
        except Exception as e:
            logger.error("Error in Lever discovery", error=str(e))
    
    async def _discover_ashby(self) -> AsyncIterator[DiscoveredCompany]:
        """Discover companies from Ashby customer pages."""
        try:
            # Ashby customer directory
            ashby_sources = [
                "https://www.ashbyhq.com/customers",
            ]
            
            for url in ashby_sources:
                try:
                    response = await self.http_client.get(url)
                    if response.status_code != 200:
                        continue
                    
                    html = response.text
                    async for company in self._extract_companies_from_html(
                        html, "ashby", url
                    ):
                        yield company
                        
                except Exception as e:
                    logger.warning("Error fetching Ashby page", url=url, error=str(e))
            
            # Known Ashby customers (many are startups/scaleups)
            known_ashby = [
                "notion", "ramp", "figma", "vercel", "linear",
                "loom", "retool", "airtable", "coda", "pitch",
                "miro", "mercury", "brex", "gusto", "lattice",
                "rippling", "deel", "remote", "oyster", "vanta",
                "drata", "snyk", "lacework", "wiz", "orca-security",
                "anthropic", "cohere", "stability-ai", "hugging-face", "replicate",
                "runway", "jasper", "copy-ai", "writer", "grammarly",
                "replit", "gitpod", "codespaces", "sourcegraph", "tabnine",
                "supabase", "planetscale", "neon", "cockroach-labs", "timescale",
                "dbt-labs", "fivetran", "airbyte", "dagster", "prefect",
            ]
            
            for company_name in known_ashby:
                try:
                    careers_url = f"https://jobs.ashbyhq.com/{company_name}"
                    
                    try:
                        response = await self.http_client.head(careers_url)
                        if response.status_code != 200:
                            continue
                    except Exception:
                        continue
                    
                    name = company_name.replace("-", " ").replace("_", " ").title()
                    
                    company = DiscoveredCompany(
                        name=name,
                        careers_url=careers_url,
                        source=f"{self.source_name}_ashby",
                        source_url=careers_url,
                        ats_type="ashby",
                        ats_identifier=company_name,
                    )
                    
                    if company.domain and company.domain not in self._discovered_domains:
                        self._discovered_domains.add(company.domain)
                        yield company
                    elif not company.domain:
                        yield company
                        
                except Exception as e:
                    logger.debug("Error checking Ashby board", company=company_name, error=str(e))
                    
        except Exception as e:
            logger.error("Error in Ashby discovery", error=str(e))
    
    async def _extract_companies_from_html(
        self,
        html: str,
        ats_type: str,
        source_url: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Extract company information from HTML content."""
        # Look for company links and names
        patterns = [
            # Links to job boards
            r'href="(https?://(?:boards\.greenhouse\.io|jobs\.lever\.co|jobs\.ashbyhq\.com)/([^/"]+))"',
            # Company website links
            r'href="(https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-z]{2,})/?)"[^>]*>([^<]+)</a>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    if len(match) >= 2:
                        url = match[0]
                        identifier = match[1]
                        name = match[2] if len(match) > 2 else identifier
                        
                        # Skip common non-company URLs
                        skip_domains = [
                            "twitter.com", "facebook.com", "linkedin.com",
                            "github.com", "youtube.com", "instagram.com",
                            "google.com", "apple.com", "microsoft.com",
                        ]
                        if any(skip in url.lower() for skip in skip_domains):
                            continue
                        
                        # Determine if this is a job board URL
                        careers_url = None
                        detected_ats = None
                        detected_identifier = None
                        
                        if "greenhouse.io" in url:
                            careers_url = url
                            detected_ats = "greenhouse"
                            detected_identifier = identifier
                        elif "lever.co" in url:
                            careers_url = url
                            detected_ats = "lever"
                            detected_identifier = identifier
                        elif "ashbyhq.com" in url:
                            careers_url = url
                            detected_ats = "ashby"
                            detected_identifier = identifier
                        
                        company = DiscoveredCompany(
                            name=name.strip() if isinstance(name, str) else identifier,
                            website_url=url if not careers_url else None,
                            careers_url=careers_url,
                            source=f"{self.source_name}_{ats_type}",
                            source_url=source_url,
                            ats_type=detected_ats or ats_type,
                            ats_identifier=detected_identifier,
                        )
                        
                        if company.domain and company.domain not in self._discovered_domains:
                            self._discovered_domains.add(company.domain)
                            yield company
                            
                except Exception as e:
                    logger.debug("Error extracting company from match", error=str(e))
