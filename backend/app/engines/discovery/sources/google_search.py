"""Google Search discovery source - find ATS boards and new companies.

This source uses Google Custom Search API to:
1. Find ATS boards for companies (fallback when probing fails)
2. Discover new companies by funding/industry/hiring signals

IMPORTANT: This source is MANUAL ONLY - it costs money (~$5 per 1000 queries)
and should only be triggered via the admin UI, not scheduled.
"""

import asyncio
import re
from typing import AsyncIterator, List, Optional, Set

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company
from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


class GoogleSearchSource(DiscoverySource):
    """Discover companies and ATS boards via Google Search API."""
    
    GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"
    
    # ATS site patterns to search
    ATS_SITES = {
        "greenhouse": "boards.greenhouse.io",
        "lever": "jobs.lever.co",
        "ashby": "jobs.ashbyhq.com",
        "workable": "apply.workable.com",
        "smartrecruiters": "jobs.smartrecruiters.com",
    }
    
    # Default discovery queries to find new companies
    DISCOVERY_QUERIES = [
        # Funding-based
        '"Series A" careers hiring software',
        '"Series B" careers hiring engineer',
        '"seed round" startup careers',
        '"raised" "million" careers tech startup',
        # YC batches
        '"YC W24" careers',
        '"YC S24" careers',
        '"YC W23" careers',
        # Industry-based
        'AI startup careers hiring -linkedin -indeed',
        'fintech startup careers hiring -linkedin -indeed',
        'developer tools startup careers -linkedin -indeed',
        'B2B SaaS startup careers hiring -linkedin -indeed',
    ]
    
    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        api_key: Optional[str] = None,
        cx: Optional[str] = None,  # Custom Search Engine ID
        mode: str = "both",  # "ats_fallback", "discovery", or "both"
        custom_queries: Optional[List[str]] = None,
        ats_fallback_limit: int = 50,
    ):
        self.db = db
        self.api_key = api_key or settings.google_api_key
        self.cx = cx or settings.google_cx
        self.mode = mode
        self.custom_queries = custom_queries
        self.ats_fallback_limit = ats_fallback_limit
        self.http_client: Optional[httpx.AsyncClient] = None
        self._existing_domains: Set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "google_search"
    
    @property
    def source_description(self) -> str:
        return "Companies discovered via Google Search (manual only)"
    
    async def initialize(self) -> None:
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def cleanup(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
    
    async def _search(self, query: str, num: int = 10) -> List[dict]:
        """Execute Google Custom Search query."""
        if not self.api_key or not self.cx:
            logger.warning("[google_search] API key or CX not configured")
            return []
        
        try:
            response = await self.http_client.get(
                self.GOOGLE_API_URL,
                params={
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "num": min(num, 10),  # Max 10 per request
                },
            )
            
            if response.status_code == 429:
                logger.warning("[google_search] API rate limited")
                await asyncio.sleep(60)
                return []
            
            if response.status_code != 200:
                logger.warning(f"[google_search] API error: {response.status_code}")
                return []
            
            data = response.json()
            return data.get("items", [])
            
        except Exception as e:
            logger.error(f"[google_search] Search error: {e}")
            return []
    
    async def _load_existing_domains(self) -> None:
        """Load existing domains to avoid duplicates."""
        if not self.db:
            return
        result = await self.db.execute(
            select(Company.domain).where(Company.domain.isnot(None))
        )
        self._existing_domains = {row[0].lower() for row in result.fetchall() if row[0]}
        logger.info(f"[google_search] Loaded {len(self._existing_domains)} existing domains")
    
    async def _find_ats_for_company(
        self, 
        company_name: str, 
        company_domain: str
    ) -> Optional[DiscoveredCompany]:
        """Search Google for company's ATS board."""
        for ats_type, ats_site in self.ATS_SITES.items():
            query = f'site:{ats_site} "{company_name}"'
            results = await self._search(query, num=3)
            
            for item in results:
                url = item.get("link", "")
                title = item.get("title", "")
                
                # Extract slug from URL
                match = re.search(rf'{ats_site}/([a-zA-Z0-9_-]+)', url)
                if match:
                    slug = match.group(1)
                    
                    # Verify it's the right company by checking title contains company name
                    if company_name.lower() in title.lower():
                        logger.info(f"[google_search] Found ATS: {company_name} -> {ats_type}/{slug}")
                        return DiscoveredCompany(
                            name=company_name,
                            domain=company_domain,
                            careers_url=url,
                            source=self.source_name,
                            source_url=url,
                            ats_type=ats_type,
                            ats_identifier=slug,
                        )
            
            # Rate limit between ATS types
            await asyncio.sleep(0.5)
        
        return None
    
    async def _discover_new_companies(self) -> AsyncIterator[DiscoveredCompany]:
        """Search for new companies via discovery queries."""
        queries = self.custom_queries or self.DISCOVERY_QUERIES
        
        for query in queries:
            logger.info(f"[google_search] Query: {query}")
            results = await self._search(query, num=10)
            
            for item in results:
                url = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                
                # Skip if it's a job board/aggregator
                skip_domains = [
                    "linkedin.com", "indeed.com", "glassdoor.com", 
                    "monster.com", "ziprecruiter.com", "wellfound.com"
                ]
                if any(d in url.lower() for d in skip_domains):
                    continue
                
                # Extract domain from URL
                match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                if not match:
                    continue
                
                domain = match.group(1).lower()
                
                # Skip if already exists or duplicate
                if domain in self._existing_domains:
                    continue
                if self.is_duplicate(domain):
                    continue
                
                # Check if URL looks like a careers page
                is_careers = any(p in url.lower() for p in ['/careers', '/jobs', '/join', '/hiring'])
                
                # Try to detect ATS from URL
                ats_type, ats_id = None, None
                for at, site in self.ATS_SITES.items():
                    if site in url:
                        ats_type = at
                        slug_match = re.search(rf'{site}/([a-zA-Z0-9_-]+)', url)
                        ats_id = slug_match.group(1) if slug_match else None
                        break
                
                # Extract company name from title
                name = title.split(" - ")[0].split(" | ")[0].strip()
                if len(name) > 50:
                    name = name[:50]
                
                self._existing_domains.add(domain)
                
                yield DiscoveredCompany(
                    name=name,
                    domain=domain,
                    website_url=f"https://{domain}",
                    careers_url=url if is_careers or ats_type else None,
                    source=self.source_name,
                    source_url=url,
                    ats_type=ats_type,
                    ats_identifier=ats_id,
                    description=snippet[:500] if snippet else None,
                )
            
            # Rate limit between queries
            await asyncio.sleep(1)
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Run Google-based discovery."""
        if not self.api_key or not self.cx:
            logger.error("[google_search] Google API key or CX not configured. Set GOOGLE_API_KEY and GOOGLE_CX.")
            return
        
        await self._load_existing_domains()
        
        # Mode 1: ATS Fallback - find ATS for companies without it
        if self.mode in ["ats_fallback", "both"]:
            if self.db:
                result = await self.db.execute(
                    select(Company.name, Company.domain)
                    .where(Company.is_active == True)
                    .where(Company.ats_type.is_(None))
                    .where(Company.domain.isnot(None))
                    .limit(self.ats_fallback_limit)
                )
                companies = result.fetchall()
                
                logger.info(f"[google_search] ATS fallback for {len(companies)} companies")
                
                for name, domain in companies:
                    result = await self._find_ats_for_company(name or "", domain or "")
                    if result:
                        yield result
                    await asyncio.sleep(1)  # Rate limit
        
        # Mode 2: Discovery - find new companies
        if self.mode in ["discovery", "both"]:
            logger.info("[google_search] Starting new company discovery")
            async for company in self._discover_new_companies():
                yield company
