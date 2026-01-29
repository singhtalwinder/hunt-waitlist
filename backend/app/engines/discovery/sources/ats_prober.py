"""Direct ATS board probing with domain verification.

This source probes company names directly against ATS URLs to find job boards
faster than crawling websites. It verifies matches by extracting the company
domain from the ATS page and comparing it to our records.
"""

import asyncio
import re
from typing import AsyncIterator, Dict, List, Optional, Set, Tuple

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company
from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class ATSProberSource(DiscoverySource):
    """Probe company names against ATS URLs with domain verification."""
    
    # ATS URL templates and domain extraction patterns
    ATS_CONFIG = {
        "greenhouse": {
            "url": "https://boards.greenhouse.io/{slug}",
            "domain_patterns": [
                r'href="https?://(?:www\.)?([^/"]+)"[^>]*>.*?(?:website|visit|company)',
                r'"company_website":\s*"https?://(?:www\.)?([^/"]+)"',
                r'<a[^>]+href="https?://(?:www\.)?([a-z0-9-]+\.[a-z]{2,})"[^>]*class="[^"]*company',
            ],
        },
        "lever": {
            "url": "https://jobs.lever.co/{slug}",
            "domain_patterns": [
                r'"websiteUrl":\s*"https?://(?:www\.)?([^/"]+)"',
                r'href="https?://(?:www\.)?([^/"]+)"[^>]*>.*?website',
            ],
        },
        "ashby": {
            "url": "https://jobs.ashbyhq.com/{slug}",
            "domain_patterns": [
                r'"website":\s*"https?://(?:www\.)?([^/"]+)"',
                r'"companyWebsite":\s*"https?://(?:www\.)?([^/"]+)"',
            ],
        },
        "workable": {
            "url": "https://apply.workable.com/{slug}",
            "domain_patterns": [
                r'"website":\s*"https?://(?:www\.)?([^/"]+)"',
            ],
        },
        "smartrecruiters": {
            "url": "https://jobs.smartrecruiters.com/{slug}",
            "domain_patterns": [
                r'"companyUrl":\s*"https?://(?:www\.)?([^/"]+)"',
            ],
        },
        "recruitee": {
            "url": "https://{slug}.recruitee.com",
            "domain_patterns": [
                r'"website":\s*"https?://(?:www\.)?([^/"]+)"',
            ],
        },
        "bamboohr": {
            "url": "https://{slug}.bamboohr.com/careers",
            "domain_patterns": [],  # BambooHR doesn't usually show company website
        },
        "jobvite": {
            "url": "https://jobs.jobvite.com/{slug}",
            "domain_patterns": [
                r'"companyWebsite":\s*"https?://(?:www\.)?([^/"]+)"',
            ],
        },
    }
    
    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        concurrency: int = 20,
        limit: int = 500,  # Max companies to probe per run
    ):
        self.db = db
        self.concurrency = concurrency
        self.limit = limit
        self.http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def source_name(self) -> str:
        return "ats_prober"
    
    @property
    def source_description(self) -> str:
        return "Direct ATS board probing with domain verification"
    
    async def initialize(self) -> None:
        self.http_client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
    
    async def cleanup(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
    
    def _company_to_slugs(self, name: str, domain: str) -> List[str]:
        """Generate possible ATS slugs from company name/domain."""
        slugs = set()
        
        # From domain (e.g., "acme.com" -> "acme")
        if domain:
            base = domain.split('.')[0].lower()
            slugs.add(base)
            slugs.add(base.replace('-', ''))
            slugs.add(base.replace('_', ''))
        
        # From name (e.g., "Acme Corp" -> "acme", "acmecorp", "acme-corp")
        if name:
            clean = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
            words = clean.split()
            if words:
                slugs.add(''.join(words))  # acmecorp
                slugs.add('-'.join(words))  # acme-corp
                slugs.add(words[0])  # acme
        
        return list(slugs)
    
    def _extract_domain_from_page(self, html: str, ats_type: str) -> Optional[str]:
        """Extract company domain from ATS page HTML."""
        config = self.ATS_CONFIG.get(ats_type, {})
        patterns = config.get("domain_patterns", [])
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                domain = match.group(1).lower()
                if domain and '.' in domain:
                    return domain
        
        return None
    
    def _domains_match(self, our_domain: str, ats_domain: str) -> bool:
        """Check if two domains match (handles www, subdomains)."""
        if not our_domain or not ats_domain:
            return False
        
        # Normalize
        our = our_domain.lower().replace('www.', '')
        ats = ats_domain.lower().replace('www.', '')
        
        # Exact match
        if our == ats:
            return True
        
        # One is subdomain of other
        if our.endswith('.' + ats) or ats.endswith('.' + our):
            return True
        
        # Base domain match (acme.com vs acme.io)
        our_base = our.split('.')[0]
        ats_base = ats.split('.')[0]
        if our_base == ats_base and len(our_base) > 3:
            return True
        
        return False
    
    async def _probe_and_verify(
        self,
        company_id: str,
        company_domain: str,
        slug: str,
        ats_type: str,
    ) -> Optional[Tuple[str, str, str]]:
        """Probe ATS URL and verify domain match.
        
        Returns (company_id, ats_type, ats_identifier) if verified.
        """
        config = self.ATS_CONFIG.get(ats_type)
        if not config:
            return None
        
        url = config["url"].format(slug=slug)
        
        try:
            # First, HEAD request to check if exists
            head_response = await self.http_client.head(url)
            if head_response.status_code != 200:
                return None
            
            # If no domain patterns, we can't verify - skip
            if not config.get("domain_patterns"):
                logger.debug(f"[ats_prober] Skipping {ats_type}/{slug} - no domain verification")
                return None
            
            # Fetch full page to extract domain
            response = await self.http_client.get(url)
            if response.status_code != 200:
                return None
            
            html = response.text
            ats_domain = self._extract_domain_from_page(html, ats_type)
            
            if not ats_domain:
                logger.debug(f"[ats_prober] No domain extracted from {ats_type}/{slug}")
                return None
            
            # Verify domain matches
            if self._domains_match(company_domain, ats_domain):
                logger.info(f"[ats_prober] ✓ Verified: {company_domain} == {ats_domain} on {ats_type}/{slug}")
                return (company_id, ats_type, slug)
            else:
                logger.debug(f"[ats_prober] ✗ Mismatch: {company_domain} != {ats_domain} for {ats_type}/{slug}")
                return None
                
        except Exception as e:
            logger.debug(f"[ats_prober] Probe error for {ats_type}/{slug}: {e}")
            return None
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Probe companies without ATS and update their records if verified.
        
        Note: This source updates companies directly in DB rather than yielding
        DiscoveredCompany objects, since we're enriching existing records.
        """
        if not self.db:
            logger.warning("[ats_prober] No database session provided")
            return
        
        # Get companies without ATS detection
        result = await self.db.execute(
            select(Company.id, Company.name, Company.domain)
            .where(Company.is_active == True)
            .where(Company.ats_type.is_(None))
            .where(Company.domain.isnot(None))
            .limit(self.limit)
        )
        companies = result.fetchall()
        
        logger.info(f"[ats_prober] Probing {len(companies)} companies against {len(self.ATS_CONFIG)} ATS types")
        
        # Generate all probe tasks: (company_id, company_domain, slug, ats_type)
        tasks = []
        for company_id, name, domain in companies:
            slugs = self._company_to_slugs(name or "", domain or "")
            for slug in slugs:
                for ats_type in self.ATS_CONFIG.keys():
                    tasks.append((str(company_id), domain, slug, ats_type))
        
        logger.info(f"[ats_prober] Total probes to run: {len(tasks)}")
        
        # Track which companies we've already found ATS for
        found_companies: Set[str] = set()
        verified_count = 0
        
        # Process in batches
        for i in range(0, len(tasks), self.concurrency):
            batch = tasks[i:i + self.concurrency]
            
            # Filter out companies we've already found
            batch = [(cid, dom, slug, ats) for cid, dom, slug, ats in batch 
                     if cid not in found_companies]
            
            if not batch:
                continue
            
            results = await asyncio.gather(
                *[self._probe_and_verify(cid, dom, slug, ats) for cid, dom, slug, ats in batch],
                return_exceptions=True
            )
            
            for result in results:
                if isinstance(result, tuple):
                    company_id, ats_type, ats_identifier = result
                    found_companies.add(company_id)
                    verified_count += 1
                    
                    # Update company directly in DB
                    try:
                        await self.db.execute(
                            update(Company)
                            .where(Company.id == company_id)
                            .values(
                                ats_type=ats_type,
                                ats_identifier=ats_identifier,
                                careers_url=self.ATS_CONFIG[ats_type]["url"].format(slug=ats_identifier)
                            )
                        )
                    except Exception as e:
                        logger.warning(f"[ats_prober] Error updating company {company_id}: {e}")
            
            # Commit periodically
            if verified_count > 0 and verified_count % 10 == 0:
                try:
                    await self.db.commit()
                    logger.info(f"[ats_prober] Progress: {i + len(batch)}/{len(tasks)} probed, {verified_count} verified")
                except Exception as e:
                    logger.warning(f"[ats_prober] Commit error: {e}")
                    await self.db.rollback()
        
        # Final commit
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
        
        logger.info(f"[ats_prober] Complete: {verified_count} companies updated with verified ATS")
        
        # This source updates companies directly rather than yielding discoveries
        return
        yield  # Makes this an async generator
