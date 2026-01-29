"""US location detection for discovered companies.

Determines if a company is US-based by analyzing:
- Explicit location strings
- Company website content (addresses, contact info)
- Domain TLD
- Known patterns
"""

import re
from typing import Optional, Tuple

import httpx
import structlog

logger = structlog.get_logger()


# US state names and abbreviations
US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}

US_STATE_ABBREVS = set(US_STATES.values())

# Major US cities (for quick detection)
US_CITIES = {
    "new york", "los angeles", "chicago", "houston", "phoenix", "philadelphia",
    "san antonio", "san diego", "dallas", "san jose", "austin", "jacksonville",
    "fort worth", "columbus", "charlotte", "san francisco", "indianapolis",
    "seattle", "denver", "boston", "el paso", "nashville", "detroit",
    "oklahoma city", "portland", "las vegas", "memphis", "louisville",
    "baltimore", "milwaukee", "albuquerque", "tucson", "fresno", "sacramento",
    "mesa", "atlanta", "kansas city", "colorado springs", "miami", "raleigh",
    "omaha", "long beach", "virginia beach", "oakland", "minneapolis", "tulsa",
    "arlington", "tampa", "new orleans", "cleveland", "pittsburgh", "cincinnati",
    # Tech hubs
    "palo alto", "mountain view", "menlo park", "cupertino", "sunnyvale",
    "redwood city", "santa clara", "fremont", "san mateo", "berkeley",
    "cambridge", "somerville", "brooklyn", "manhattan", "queens", "bronx",
    "santa monica", "venice", "pasadena", "burbank", "culver city",
    "boulder", "salt lake city", "provo", "ann arbor", "madison",
}

# Country indicators
US_INDICATORS = [
    "united states", "usa", "u.s.a.", "u.s.", "america",
]

NON_US_INDICATORS = [
    "united kingdom", "uk", "u.k.", "england", "london", "manchester",
    "germany", "berlin", "munich", "frankfurt",
    "france", "paris", "lyon",
    "canada", "toronto", "vancouver", "montreal",
    "australia", "sydney", "melbourne",
    "india", "bangalore", "mumbai", "delhi",
    "china", "beijing", "shanghai",
    "japan", "tokyo",
    "singapore",
    "israel", "tel aviv",
    "netherlands", "amsterdam",
    "sweden", "stockholm",
    "ireland", "dublin",
    "switzerland", "zurich",
]


def detect_us_from_location(location: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Detect if a location string indicates a US location.
    
    Returns:
        Tuple of (is_us, normalized_location)
    """
    if not location:
        return False, None
    
    location_lower = location.lower().strip()
    
    # Check for explicit non-US indicators first
    for indicator in NON_US_INDICATORS:
        if indicator in location_lower:
            return False, None
    
    # Check for explicit US indicators
    for indicator in US_INDICATORS:
        if indicator in location_lower:
            return True, location
    
    # Check for US cities
    for city in US_CITIES:
        if city in location_lower:
            return True, location
    
    # Check for US states
    for state_name, abbrev in US_STATES.items():
        if state_name in location_lower:
            return True, location
        # Check for state abbreviation (with comma separator)
        if f", {abbrev.lower()}" in location_lower or f",{abbrev.lower()}" in location_lower:
            return True, location
    
    # Check for state abbreviations at the end (e.g., "San Francisco, CA")
    state_pattern = r",\s*([A-Z]{2})(?:\s|$|\d)"
    match = re.search(state_pattern, location)
    if match and match.group(1) in US_STATE_ABBREVS:
        return True, location
    
    # Check for ZIP code pattern
    zip_pattern = r"\b\d{5}(?:-\d{4})?\b"
    if re.search(zip_pattern, location):
        return True, location
    
    # "Remote" could be anywhere, but often US-based companies
    # We'll mark as unknown rather than assuming
    if location_lower == "remote":
        return False, location
    
    return False, location


async def detect_us_from_website(
    http_client: httpx.AsyncClient,
    website_url: str,
) -> Tuple[bool, Optional[str]]:
    """Detect if a company is US-based by analyzing their website.
    
    Args:
        http_client: Async HTTP client
        website_url: Company website URL
        
    Returns:
        Tuple of (is_us, detected_location)
    """
    try:
        # Fetch the homepage
        response = await http_client.get(website_url, timeout=10.0)
        if response.status_code != 200:
            return False, None
        
        html = response.text
        
        # Try to find location in common places
        location = await _extract_location_from_html(html)
        if location:
            is_us, normalized = detect_us_from_location(location)
            if is_us:
                return True, normalized
        
        # Try to fetch contact/about page
        contact_paths = ["/contact", "/about", "/about-us", "/company"]
        for path in contact_paths:
            try:
                contact_url = website_url.rstrip("/") + path
                response = await http_client.get(contact_url, timeout=5.0)
                if response.status_code == 200:
                    location = await _extract_location_from_html(response.text)
                    if location:
                        is_us, normalized = detect_us_from_location(location)
                        if is_us:
                            return True, normalized
            except Exception:
                continue
        
        return False, None
        
    except Exception as e:
        logger.debug("Error detecting US location from website", url=website_url, error=str(e))
        return False, None


async def _extract_location_from_html(html: str) -> Optional[str]:
    """Extract location information from HTML content."""
    # Look for address-related patterns
    patterns = [
        # Address in footer
        r'<address[^>]*>([^<]+)</address>',
        # Address with class
        r'class="[^"]*address[^"]*"[^>]*>([^<]+)<',
        # Location in contact section
        r'(?:location|headquarters|office|address)[:\s]+([^<\n]+)',
        # Schema.org address
        r'"addressLocality":\s*"([^"]+)"',
        r'"addressRegion":\s*"([^"]+)"',
        # Common address patterns
        r'\b(\d{1,5}\s+[A-Za-z0-9\s,]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up the location string
            location = re.sub(r'\s+', ' ', location)
            if len(location) > 5 and len(location) < 200:
                return location
    
    return None


def detect_us_from_domain(domain: Optional[str]) -> bool:
    """Check if a domain TLD suggests US location.
    
    Note: This is a weak signal - many US companies use .com, .io, etc.
    """
    if not domain:
        return False
    
    # .us TLD is a strong indicator
    if domain.endswith(".us"):
        return True
    
    # State-specific domains
    state_tlds = [f".{abbrev.lower()}.us" for abbrev in US_STATE_ABBREVS]
    for tld in state_tlds:
        if domain.endswith(tld):
            return True
    
    return False


class USLocationDetector:
    """Service class for detecting US companies."""
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """Initialize the detector.
        
        Args:
            http_client: Optional HTTP client (will create one if not provided)
        """
        self._http_client = http_client
        self._own_client = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
            )
            self._own_client = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._own_client and self._http_client:
            await self._http_client.aclose()
        return False
    
    async def is_us_company(
        self,
        location: Optional[str] = None,
        website_url: Optional[str] = None,
        domain: Optional[str] = None,
        check_website: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Determine if a company is US-based.
        
        Checks in order:
        1. Explicit location string
        2. Domain TLD
        3. Website content (if check_website is True)
        
        Args:
            location: Location string if available
            website_url: Company website URL
            domain: Company domain
            check_website: Whether to fetch and analyze website
            
        Returns:
            Tuple of (is_us, detected_location)
        """
        # Check explicit location first
        if location:
            is_us, normalized = detect_us_from_location(location)
            if is_us:
                return True, normalized
        
        # Check domain TLD
        if domain and detect_us_from_domain(domain):
            return True, "US (from domain)"
        
        # Check website content
        if check_website and website_url and self._http_client:
            is_us, detected = await detect_us_from_website(self._http_client, website_url)
            if is_us:
                return True, detected
        
        return False, None
