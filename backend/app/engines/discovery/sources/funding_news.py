"""Discovery source for funding news and announcements.

Discovers companies from:
- TechCrunch funding news
- VentureBeat
- Crunchbase news (free tier)
- Other startup news RSS feeds

Companies that just raised funding are likely hiring.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import AsyncIterator, List, Optional

import httpx
import structlog

from app.engines.discovery.sources.base import DiscoveredCompany, DiscoverySource

logger = structlog.get_logger()


class FundingNewsSource(DiscoverySource):
    """Discover companies from funding news and announcements."""
    
    # RSS feeds for startup funding news
    RSS_FEEDS = [
        # TechCrunch
        {
            "url": "https://techcrunch.com/category/startups/feed/",
            "name": "TechCrunch Startups",
        },
        {
            "url": "https://techcrunch.com/tag/funding/feed/",
            "name": "TechCrunch Funding",
        },
        # VentureBeat
        {
            "url": "https://venturebeat.com/category/business/funding/feed/",
            "name": "VentureBeat Funding",
        },
        # Crunchbase News
        {
            "url": "https://news.crunchbase.com/feed/",
            "name": "Crunchbase News",
        },
        # SaaStr
        {
            "url": "https://www.saastr.com/feed/",
            "name": "SaaStr",
        },
        # First Round Review
        {
            "url": "https://review.firstround.com/feed.xml",
            "name": "First Round Review",
        },
    ]
    
    # Funding-related keywords
    FUNDING_KEYWORDS = [
        "raises", "raised", "funding", "series a", "series b", "series c",
        "series d", "seed round", "seed funding", "million", "billion",
        "investment", "invested", "venture", "capital", "fundraise",
        "financing", "valuation", "unicorn", "backed", "led by",
    ]
    
    def __init__(
        self,
        max_age_days: int = 30,
        custom_feeds: Optional[List[dict]] = None,
    ):
        """Initialize the funding news source.
        
        Args:
            max_age_days: Only process articles from the last N days
            custom_feeds: Additional RSS feeds to include
        """
        self.max_age_days = max_age_days
        self.custom_feeds = custom_feeds or []
        self.http_client: Optional[httpx.AsyncClient] = None
        self._discovered_companies: set[str] = set()
    
    @property
    def source_name(self) -> str:
        return "funding_news"
    
    @property
    def source_description(self) -> str:
        return "Companies discovered from funding news and announcements"
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
    
    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def discover(self) -> AsyncIterator[DiscoveredCompany]:
        """Yield companies from funding news."""
        all_feeds = self.RSS_FEEDS + self.custom_feeds
        
        for feed_info in all_feeds:
            try:
                async for company in self._process_feed(feed_info):
                    yield company
            except Exception as e:
                logger.warning(
                    "Error processing RSS feed",
                    feed=feed_info.get("name"),
                    error=str(e),
                )
    
    async def _process_feed(self, feed_info: dict) -> AsyncIterator[DiscoveredCompany]:
        """Process an RSS feed for funding announcements."""
        url = feed_info.get("url", "")
        feed_name = feed_info.get("name", url)
        
        try:
            response = await self.http_client.get(url)
            if response.status_code != 200:
                logger.warning("Failed to fetch RSS feed", feed=feed_name, status=response.status_code)
                return
            
            content = response.text
            
            # Parse RSS/Atom feed
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                logger.warning("Failed to parse RSS feed", feed=feed_name, error=str(e))
                return
            
            # Handle both RSS and Atom feeds
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            
            for item in items:
                try:
                    async for company in self._process_item(item, feed_name):
                        yield company
                except Exception as e:
                    logger.debug("Error processing feed item", error=str(e))
                    
        except Exception as e:
            logger.warning("Error fetching RSS feed", feed=feed_name, error=str(e))
    
    async def _process_item(
        self,
        item: ET.Element,
        feed_name: str,
    ) -> AsyncIterator[DiscoveredCompany]:
        """Process a single RSS item for company mentions."""
        # Get item details
        title = self._get_text(item, "title") or self._get_text(
            item, "{http://www.w3.org/2005/Atom}title"
        )
        description = (
            self._get_text(item, "description")
            or self._get_text(item, "content:encoded")
            or self._get_text(item, "{http://www.w3.org/2005/Atom}content")
            or self._get_text(item, "{http://www.w3.org/2005/Atom}summary")
        )
        link = self._get_text(item, "link") or self._get_attr(
            item, "{http://www.w3.org/2005/Atom}link", "href"
        )
        pub_date = self._get_text(item, "pubDate") or self._get_text(
            item, "{http://www.w3.org/2005/Atom}published"
        )
        
        # Check if article is recent enough
        if pub_date and not self._is_recent(pub_date):
            return
        
        # Check if this is a funding-related article
        content = f"{title} {description}".lower()
        if not any(keyword in content for keyword in self.FUNDING_KEYWORDS):
            return
        
        # Extract company names from title and description
        companies = self._extract_companies_from_text(title, description)
        
        for company_info in companies:
            name = company_info.get("name", "")
            
            # Skip if already discovered
            if name.lower() in self._discovered_companies:
                continue
            
            self._discovered_companies.add(name.lower())
            
            # Try to determine funding stage
            funding_stage = self._extract_funding_stage(content)
            
            company = DiscoveredCompany(
                name=name,
                website_url=company_info.get("website"),
                source=f"{self.source_name}_{feed_name.lower().replace(' ', '_')}",
                source_url=link,
                description=self._truncate(description, 500) if description else None,
                funding_stage=funding_stage,
                country="US",  # Most funding news is US-focused
            )
            
            yield company
    
    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """Get text content of a child element."""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None
    
    def _get_attr(self, element: ET.Element, tag: str, attr: str) -> Optional[str]:
        """Get attribute value of a child element."""
        child = element.find(tag)
        if child is not None:
            return child.get(attr)
        return None
    
    def _is_recent(self, date_str: str) -> bool:
        """Check if a date string is within the max age."""
        try:
            # Try common date formats
            formats = [
                "%a, %d %b %Y %H:%M:%S %z",  # RFC 822
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
            ]
            
            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_str.strip(), fmt)
                    cutoff = datetime.now(parsed.tzinfo) - timedelta(days=self.max_age_days)
                    return parsed > cutoff
                except ValueError:
                    continue
            
            # If we can't parse, assume it's recent
            return True
            
        except Exception:
            return True
    
    def _extract_companies_from_text(
        self,
        title: Optional[str],
        description: Optional[str],
    ) -> List[dict]:
        """Extract company names and websites from text."""
        companies = []
        text = f"{title or ''} {description or ''}"
        
        # More strict patterns - require funding context
        patterns = [
            # "Company raises $X million" - most reliable pattern
            r"([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)?)\s+(?:raises?|raised|secures?|secured|closes?|closed)\s+\$\d+",
            # "$X million for Company" - another reliable pattern
            r"\$\d+(?:\.\d+)?\s*(?:million|billion|M|B)\s+(?:for|to|into)\s+([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)?)",
        ]
        
        found_names = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.strip()
                
                # Skip if too short or too long
                if len(name) < 3 or len(name) > 40:
                    continue
                
                # Must start with uppercase
                if not name[0].isupper():
                    continue
                
                # Skip common words and phrases that aren't company names
                skip_words = {
                    "the", "a", "an", "this", "that", "these", "those",
                    "series", "round", "seed", "funding", "million", "billion",
                    "startup", "company", "venture", "capital", "investment",
                    "today", "monday", "tuesday", "wednesday", "thursday",
                    "friday", "saturday", "sunday", "announces", "raises",
                    "has", "will", "can", "could", "would", "should",
                    "last", "next", "first", "second", "third",
                    "year", "month", "week", "day", "time",
                    "new", "old", "big", "small", "more", "less",
                    "all", "some", "any", "most", "many", "few",
                    "now", "then", "here", "there", "just", "only",
                    "also", "even", "still", "already", "yet",
                    "net", "gross", "total", "average", "median",
                    "stakes", "shares", "equity", "stock", "bond",
                }
                if name.lower() in skip_words:
                    continue
                
                # Skip two-word phrases that are likely not company names
                if ' ' in name:
                    words = name.lower().split()
                    if any(w in skip_words for w in words):
                        continue
                
                # Skip if already found
                if name.lower() in found_names:
                    continue
                
                found_names.add(name.lower())
                companies.append({"name": name})
        
        # Also look for URLs in the text
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-z]{2,})'
        url_matches = re.findall(url_pattern, text)
        
        for domain in url_matches:
            # Skip news/social domains
            skip_domains = {
                "techcrunch.com", "venturebeat.com", "crunchbase.com",
                "twitter.com", "linkedin.com", "facebook.com", "youtube.com",
            }
            if domain.lower() in skip_domains:
                continue
            
            # Add if not already found
            name = domain.split(".")[0].title()
            if name.lower() not in found_names:
                found_names.add(name.lower())
                companies.append({
                    "name": name,
                    "website": f"https://{domain}",
                })
        
        return companies
    
    def _extract_funding_stage(self, text: str) -> Optional[str]:
        """Extract funding stage from text."""
        text_lower = text.lower()
        
        stages = [
            ("series d", "Series D"),
            ("series c", "Series C"),
            ("series b", "Series B"),
            ("series a", "Series A"),
            ("seed round", "Seed"),
            ("seed funding", "Seed"),
            ("pre-seed", "Pre-Seed"),
        ]
        
        for keyword, stage in stages:
            if keyword in text_lower:
                return stage
        
        return None
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        text = text.strip()
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."
