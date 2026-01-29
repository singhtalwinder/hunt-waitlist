"""Discovery source for network-based company discovery.

Discovers companies by:
1. Crawling /customers, /portfolio, /partners pages of existing companies
2. Extracting outbound links to other company websites
3. Visiting those websites to find careers/jobs pages
4. Detecting ATS systems on those pages
"""

import asyncio
import re
from typing import AsyncIterator, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company
from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class NetworkCrawlerSource(DiscoverySource):
    """Discover companies by crawling network pages and following links."""
    
    # Pages to look for company listings (and their variants)
    DISCOVERY_PATHS = [
        # Homepage (often has logos/testimonials)
        "/",
        # Customers
        "/customers",
        "/customer",
        "/our-customers",
        "/customer-stories",
        "/customer-success",
        # Case studies
        "/case-studies",
        "/case-study",
        "/casestudies",
        "/success-stories",
        "/stories",
        # Testimonials
        "/testimonials",
        "/reviews",
        "/wall-of-love",
        # Examples/showcase
        "/examples",
        "/showcase",
        "/gallery",
        "/made-with",
        "/built-with",
        "/powered-by",
        # Clients
        "/clients",
        "/our-clients",
        # Partners
        "/partners",
        "/our-partners",
        "/partner",
        "/integrations",
        "/ecosystem",
        "/marketplace",
        # Portfolio (for VCs)
        "/portfolio",
        "/companies",
        "/startups",
        "/investments",
        # About pages (often have customer logos)
        "/about",
        "/about-us",
        "/company",
        # Who uses
        "/who-uses",
        "/who-uses-us",
        "/trusted-by",
        # Logos page
        "/logos",
        "/press",
        "/press-kit",
    ]
    
    # Career page paths to check
    CAREER_PATHS = [
        "/careers",
        "/jobs",
        "/join",
        "/join-us",
        "/work-with-us",
        "/hiring",
        "/career",
        "/about/careers",
        "/company/careers",
    ]
    
    # Domains to skip (not companies)
    SKIP_DOMAINS = {
        # Social media
        "twitter.com", "x.com", "facebook.com", "linkedin.com", "instagram.com",
        "youtube.com", "tiktok.com", "pinterest.com", "reddit.com", "threads.net",
        # Tech giants (too big)
        "google.com", "apple.com", "microsoft.com", "amazon.com", "meta.com",
        # Media/news
        "medium.com", "techcrunch.com", "forbes.com", "bloomberg.com",
        "reuters.com", "nytimes.com", "wsj.com", "wired.com", "theverge.com",
        "venturebeat.com", "crunchbase.com", "producthunt.com", "substack.com",
        # Dev tools (not hiring targets)
        "github.com", "gitlab.com", "bitbucket.org", "npmjs.com", "pypi.org",
        "stackoverflow.com", "developer.mozilla.org", "docs.google.com",
        # Cloud providers
        "cloudflare.com", "amazonaws.com", "azure.com", "cloud.google.com",
        "vercel.com", "netlify.com", "heroku.com", "fly.io",
        # Common SaaS (not targets)
        "slack.com", "zoom.us", "notion.so", "figma.com", "miro.com",
        "intercom.com", "hubspot.com", "salesforce.com", "zendesk.com",
        "stripe.com", "twilio.com", "sendgrid.com", "mailchimp.com",
        # Analytics/tracking
        "google-analytics.com", "segment.com", "amplitude.com", "mixpanel.com",
        # File sharing
        "dropbox.com", "box.com", "drive.google.com",
        # Common TLDs that aren't companies
        "wordpress.com", "squarespace.com", "wix.com", "webflow.io",
        "typeform.com", "calendly.com", "loom.com",
    }
    
    # ATS patterns to detect
    ATS_PATTERNS = [
        (r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', "greenhouse"),
        (r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', "lever"),
        (r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)', "ashby"),
        (r'apply\.workable\.com/([a-zA-Z0-9_-]+)', "workable"),
        (r'jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)', "smartrecruiters"),
        (r'jobs\.jobvite\.com/([a-zA-Z0-9_-]+)', "jobvite"),
        (r'([a-zA-Z0-9_-]+)\.bamboohr\.com/careers', "bamboohr"),
        (r'recruitee\.com/o/([a-zA-Z0-9_-]+)', "recruitee"),
    ]
    
    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        max_companies_to_crawl: int = 10000,  # Crawl all companies (no practical limit)
        max_discoveries_per_company: int = 100,  # Find up to 100 new companies per source
        company_concurrency: int = 10,  # Process 10 companies in parallel
        path_concurrency: int = 10,  # Check 10 paths in parallel per company
        force_recrawl: bool = False,  # If True, re-crawl all companies even if already crawled
    ):
        """Initialize the network crawler.
        
        Args:
            db: Database session to fetch existing companies
            max_companies_to_crawl: Max existing companies to crawl
            max_discoveries_per_company: Max new companies to find per source company
            company_concurrency: Number of companies to process in parallel
            path_concurrency: Number of paths to check in parallel per company
            force_recrawl: If True, re-crawl all companies (for manual full crawl)
        """
        self.db = db
        self.max_companies_to_crawl = max_companies_to_crawl
        self.max_discoveries_per_company = max_discoveries_per_company
        self.company_concurrency = company_concurrency
        self.path_concurrency = path_concurrency
        self.force_recrawl = force_recrawl
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_domains: Set[str] = set()
        self._existing_domains: Set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "network_crawler"
    
    @property
    def source_description(self) -> str:
        return "Companies discovered from customer/portfolio pages"
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
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
        """Discover companies from existing company pages with concurrent processing."""
        # Load existing domains to avoid duplicates
        await self._load_existing_domains()
        
        # Get companies to crawl
        companies_to_crawl = await self._get_companies_to_crawl()
        total_companies = len(companies_to_crawl)
        
        # Set progress tracking for UI
        self._progress_total = total_companies
        self._progress_current = 0
        
        if not companies_to_crawl:
            logger.warning("[network_crawler] No companies to crawl")
            return
        
        logger.info(f"[network_crawler] Will crawl {total_companies} companies with concurrency={self.company_concurrency}")
        
        total_found = 0
        companies_processed = 0
        
        # Process companies in batches with concurrency
        for batch_idx in range(0, len(companies_to_crawl), self.company_concurrency):
            batch = companies_to_crawl[batch_idx:batch_idx + self.company_concurrency]
            batch_num = batch_idx // self.company_concurrency + 1
            total_batches = (len(companies_to_crawl) + self.company_concurrency - 1) // self.company_concurrency
            
            logger.info(f"[network_crawler] Batch {batch_num}/{total_batches}: Processing {len(batch)} companies ({companies_processed}/{total_companies})")
            
            # Run concurrent crawls for this batch
            tasks = [self._crawl_single_company(c) for c in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update progress
            companies_processed += len(batch)
            self._progress_current = companies_processed
            
            # Collect company IDs to mark as crawled (must do DB ops outside gather)
            crawled_company_ids = []
            
            # Yield discovered companies from batch
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"[network_crawler] Batch error: {result}")
                    continue
                if isinstance(result, tuple) and len(result) == 2:
                    discovered_list, company_id = result
                    if company_id:
                        crawled_company_ids.append(company_id)
                    for company in discovered_list:
                        total_found += 1
                        ats_info = f" (ATS: {company.ats_type})" if company.ats_type else ""
                        logger.info(f"[network_crawler] → Discovered: {company.name} ({company.domain}){ats_info}")
                        yield company
            
            # Mark companies as crawled (safe: sequential DB ops after gather completes)
            if self.db and crawled_company_ids:
                await self._mark_companies_crawled(crawled_company_ids)
            
            logger.info(f"[network_crawler] Batch {batch_num} complete. {companies_processed}/{total_companies} crawled, {total_found} found")
        
        logger.info(f"[network_crawler] Discovery complete: {total_found} new companies from {total_companies} sources")
    
    async def _crawl_single_company(self, company: Dict) -> tuple[List[DiscoveredCompany], Optional[str]]:
        """Crawl a single company and return discovered companies.
        
        Returns:
            Tuple of (discovered_companies, company_id_to_mark_crawled)
            The company_id is returned so the caller can update the DB
            outside of the concurrent context (AsyncSession is not task-safe).
        """
        domain = company.get("domain")
        company_id = company.get("id")
        if not domain:
            return [], None
        
        # Note: We don't check if source company's domain is a duplicate - 
        # it's expected to be in our database. The dedup check is for DISCOVERED domains.
        
        discovered_companies = []
        
        try:
            # Find outbound links from their pages (with concurrent path checking)
            discovered_websites = await self._find_outbound_links(domain)
            
            if discovered_websites:
                logger.debug(f"[network_crawler] {domain}: Found {len(discovered_websites)} outbound links")
            
            # Check each discovered website for careers page
            found_count = 0
            for site in discovered_websites:
                if found_count >= self.max_discoveries_per_company:
                    break
                
                # Early dedup check
                if self.is_duplicate(site.get("domain", "")):
                    continue
                
                result = await self._check_for_careers(site)
                if result:
                    found_count += 1
                    discovered_companies.append(result)
        
        except Exception as e:
            logger.debug(f"[network_crawler] Error crawling {domain}: {e}")
        
        # Return the company_id so caller can mark it as crawled
        # (DB operations must happen outside concurrent gather() calls)
        return discovered_companies, company_id
    
    async def _mark_companies_crawled(self, company_ids: List[str]) -> None:
        """Mark companies as crawled for network discovery.
        
        This is called after asyncio.gather() completes to avoid
        concurrent access to the AsyncSession (which is not task-safe).
        
        Uses bulk UPDATE to avoid fetching ORM objects with lazy-loaded
        relationships, which can cause greenlet context issues.
        """
        from datetime import datetime
        
        try:
            # Use bulk UPDATE instead of fetching ORM objects to avoid
            # greenlet/lazy-loading issues with relationships
            await self.db.execute(
                update(Company)
                .where(Company.id.in_(company_ids))
                .values(last_crawled_for_network=datetime.utcnow())
            )
            # Don't commit here - let the orchestrator handle commits
        except Exception as e:
            logger.debug(f"[network_crawler] Error updating crawl timestamps: {e}")
    
    async def _load_existing_domains(self) -> None:
        """Load existing company domains from database."""
        if not self.db:
            return
        
        try:
            result = await self.db.execute(
                select(Company.domain)
                .where(Company.domain.isnot(None))
            )
            self._existing_domains = {row[0].lower() for row in result.fetchall() if row[0]}
            logger.info(f"Loaded {len(self._existing_domains)} existing domains")
        except Exception as e:
            logger.warning(f"Error loading existing domains: {e}")
    
    async def _get_companies_to_crawl(self) -> List[Dict]:
        """Get existing companies to crawl for outbound links.
        
        By default, only returns companies that have NEVER been crawled for network
        discovery. Use force_recrawl=True to re-crawl all companies.
        """
        if not self.db:
            return []
        
        try:
            query = (
                select(Company.id, Company.name, Company.domain, Company.website_url)
                .where(Company.domain.isnot(None))
                .where(Company.is_active == True)
            )
            
            if not self.force_recrawl:
                # Only crawl companies that have never been crawled
                query = query.where(Company.last_crawled_for_network.is_(None))
                logger.info("[network_crawler] Getting only uncrawled companies")
            else:
                logger.info("[network_crawler] Force recrawl enabled - getting all companies")
            
            query = query.order_by(Company.created_at.desc()).limit(self.max_companies_to_crawl)
            
            result = await self.db.execute(query)
            companies = [
                {"id": row[0], "name": row[1], "domain": row[2], "website_url": row[3]}
                for row in result.fetchall()
            ]
            
            logger.info(f"[network_crawler] Found {len(companies)} companies to crawl")
            return companies
            
        except Exception as e:
            logger.warning(f"Error fetching companies to crawl: {e}")
            return []
    
    async def _find_outbound_links(self, domain: str) -> List[Dict]:
        """Find outbound links from a company's pages with concurrent path checking."""
        discovered = []
        base_url = f"https://{domain}"
        
        async def check_path(path: str) -> List[tuple]:
            """Check a single path and return found links."""
            try:
                url = f"{base_url}{path}"
                response = await self.http_client.get(url, timeout=5.0)  # Reduced timeout
                
                if response.status_code != 200:
                    return []
                
                return self._extract_outbound_links(response.text, domain)
            except Exception:
                return []
        
        # Check paths in parallel batches
        all_links = []
        for i in range(0, len(self.DISCOVERY_PATHS), self.path_concurrency):
            batch = self.DISCOVERY_PATHS[i:i + self.path_concurrency]
            results = await asyncio.gather(*[check_path(p) for p in batch])
            for links in results:
                all_links.extend(links)
        
        # Deduplicate and filter
        seen = set()
        for link_domain, link_url in all_links:
            if link_domain in seen:
                continue
            if link_domain in self._discovered_domains:
                continue
            if link_domain in self._existing_domains:
                continue
            
            seen.add(link_domain)
            self._discovered_domains.add(link_domain)
            discovered.append({
                "domain": link_domain,
                "website_url": link_url,
                "source_url": base_url,
            })
        
        return discovered
    
    def _extract_outbound_links(self, html: str, source_domain: str) -> List[tuple]:
        """Extract outbound links from HTML, returning (domain, url) tuples."""
        links = []
        
        # Find all href links
        pattern = r'href=["\']?(https?://(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})(?:/[^"\'>\s]*)?)["\']?'
        
        for match in re.finditer(pattern, html, re.IGNORECASE):
            try:
                url = match.group(1)
                domain = match.group(2).lower()
                
                # Clean domain
                if domain.startswith("www."):
                    domain = domain[4:]
                
                # Skip if it's the source domain
                if domain == source_domain or domain == f"www.{source_domain}":
                    continue
                
                # Skip non-company domains
                if domain in self.SKIP_DOMAINS:
                    continue
                
                # Skip common non-company patterns
                if any(skip in domain for skip in [".gov", ".edu", ".org", "cdn.", "static.", "api.", "docs."]):
                    continue
                
                # Skip if domain is too short or looks invalid
                if len(domain) < 4 or "." not in domain:
                    continue
                
                links.append((domain, url))
                
            except Exception:
                continue
        
        return links
    
    async def _check_for_careers(self, site: Dict) -> Optional[DiscoveredCompany]:
        """Check if a website has a careers page and detect ATS."""
        domain = site["domain"]
        base_url = f"https://{domain}"
        
        logger.debug(f"    Checking {domain} for careers page...")
        
        # First check the homepage for ATS embeds or career links
        try:
            response = await self.http_client.get(base_url, timeout=10.0)
            if response.status_code == 200:
                html = response.text
                
                # Check for embedded ATS
                ats_info = self._detect_ats(html)
                if ats_info:
                    logger.debug(f"    → Found ATS on homepage: {ats_info['type']}")
                    return DiscoveredCompany(
                        name=self._domain_to_name(domain),
                        domain=domain,
                        website_url=base_url,
                        careers_url=ats_info["url"],
                        source=self.source_name,
                        source_url=site["source_url"],
                        ats_type=ats_info["type"],
                        ats_identifier=ats_info["identifier"],
                    )
                
                # Look for career link in homepage
                career_link = self._find_career_link(html, base_url)
                if career_link:
                    logger.debug(f"    → Found career link: {career_link[:50]}...")
                    # Follow the career link
                    careers_result = await self._check_careers_page(career_link, site)
                    if careers_result:
                        return careers_result
        except httpx.TimeoutException:
            logger.debug(f"    → Homepage timeout")
        except Exception as e:
            logger.debug(f"    → Homepage error: {type(e).__name__}")
        
        # Try common career paths directly
        for path in self.CAREER_PATHS[:5]:  # Only try first 5 to be fast
            try:
                url = f"{base_url}{path}"
                response = await self.http_client.get(url, timeout=8.0)
                
                if response.status_code == 200:
                    html = response.text
                    
                    # Check for ATS
                    ats_info = self._detect_ats(html)
                    if ats_info:
                        logger.debug(f"    → Found ATS at {path}: {ats_info['type']}")
                        return DiscoveredCompany(
                            name=self._domain_to_name(domain),
                            domain=domain,
                            website_url=base_url,
                            careers_url=ats_info["url"],
                            source=self.source_name,
                            source_url=site["source_url"],
                            ats_type=ats_info["type"],
                            ats_identifier=ats_info["identifier"],
                        )
                    
                    # Check if it looks like a careers page
                    if self._looks_like_careers_page(html):
                        logger.debug(f"    → Found careers page at {path}")
                        return DiscoveredCompany(
                            name=self._domain_to_name(domain),
                            domain=domain,
                            website_url=base_url,
                            careers_url=url,
                            source=self.source_name,
                            source_url=site["source_url"],
                        )
                        
            except Exception:
                continue
        
        logger.debug(f"    → No careers page found")
        return None
    
    async def _check_careers_page(self, url: str, site: Dict) -> Optional[DiscoveredCompany]:
        """Check a specific careers page URL."""
        try:
            response = await self.http_client.get(url, timeout=10.0)
            if response.status_code != 200:
                return None
            
            html = response.text
            domain = site["domain"]
            base_url = f"https://{domain}"
            
            # Check for ATS
            ats_info = self._detect_ats(html)
            if ats_info:
                return DiscoveredCompany(
                    name=self._domain_to_name(domain),
                    domain=domain,
                    website_url=base_url,
                    careers_url=ats_info["url"],
                    source=self.source_name,
                    source_url=site["source_url"],
                    ats_type=ats_info["type"],
                    ats_identifier=ats_info["identifier"],
                )
            
            # It's a careers page without detected ATS
            if self._looks_like_careers_page(html):
                return DiscoveredCompany(
                    name=self._domain_to_name(domain),
                    domain=domain,
                    website_url=base_url,
                    careers_url=url,
                    source=self.source_name,
                    source_url=site["source_url"],
                )
                
        except Exception as e:
            logger.debug(f"Error checking careers page {url}: {e}")
        
        return None
    
    def _detect_ats(self, html: str) -> Optional[Dict]:
        """Detect ATS system in HTML content."""
        for pattern, ats_type in self.ATS_PATTERNS:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                identifier = match.group(1)
                
                # Skip common false positives
                if identifier.lower() in {"embed", "js", "api", "static", "assets", "www"}:
                    continue
                
                url = self._build_ats_url(ats_type, identifier)
                return {
                    "type": ats_type,
                    "identifier": identifier,
                    "url": url,
                }
        
        return None
    
    def _build_ats_url(self, ats_type: str, identifier: str) -> str:
        """Build full ATS board URL."""
        urls = {
            "greenhouse": f"https://boards.greenhouse.io/{identifier}",
            "lever": f"https://jobs.lever.co/{identifier}",
            "ashby": f"https://jobs.ashbyhq.com/{identifier}",
            "workable": f"https://apply.workable.com/{identifier}",
            "smartrecruiters": f"https://jobs.smartrecruiters.com/{identifier}",
            "jobvite": f"https://jobs.jobvite.com/{identifier}",
            "bamboohr": f"https://{identifier}.bamboohr.com/careers",
            "recruitee": f"https://recruitee.com/o/{identifier}",
        }
        return urls.get(ats_type, f"https://{identifier}")
    
    def _find_career_link(self, html: str, base_url: str) -> Optional[str]:
        """Find a careers/jobs link in HTML."""
        patterns = [
            r'href=["\']([^"\']*(?:/careers|/jobs|/join-us|/hiring)[^"\']*)["\']',
            r'href=["\']([^"\']+)["\'][^>]*>(?:[^<]*(?:Careers|Jobs|Join Us|We\'re Hiring)[^<]*)</a>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                link = match.group(1)
                if link.startswith("http"):
                    return link
                elif link.startswith("/"):
                    return urljoin(base_url, link)
                else:
                    return urljoin(base_url + "/", link)
        
        return None
    
    def _looks_like_careers_page(self, html: str) -> bool:
        """Check if HTML looks like a careers/jobs page."""
        html_lower = html.lower()
        
        # Must have job-related keywords
        job_keywords = ["job", "career", "position", "opening", "hiring", "apply"]
        keyword_count = sum(1 for kw in job_keywords if kw in html_lower)
        
        # Must have role-related keywords
        role_keywords = ["engineer", "developer", "designer", "manager", "analyst", "sales", "marketing"]
        role_count = sum(1 for kw in role_keywords if kw in html_lower)
        
        return keyword_count >= 2 and role_count >= 1
    
    def _domain_to_name(self, domain: str) -> str:
        """Convert domain to company name."""
        name = domain.split(".")[0]
        name = name.replace("-", " ").replace("_", " ")
        return name.title()
