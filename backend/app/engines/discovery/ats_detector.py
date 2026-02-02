"""ATS type detection from URLs and page content."""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()

# Known ATS URL patterns
ATS_PATTERNS = {
    # Already implemented
    "greenhouse": [
        r"boards\.greenhouse\.io/([^/]+)",
        r"job-boards\.greenhouse\.io/([^/]+)",
        r"([^.]+)\.greenhouse\.io",
    ],
    "lever": [
        r"jobs\.lever\.co/([^/]+)",
        r"([^.]+)\.lever\.co",
    ],
    "ashby": [
        r"jobs\.ashbyhq\.com/([^/]+)",
        r"([^.]+)\.ashbyhq\.com",
    ],
    "workable": [
        r"apply\.workable\.com/([^/]+)",
        r"([^.]+)\.workable\.com",
    ],
    "workday": [
        r"([^.]+)\.wd\d+\.myworkdayjobs\.com",
        r"workday\.com",
    ],
    # New ATS platforms
    "bamboohr": [
        r"([^.]+)\.bamboohr\.com/careers",
        r"([^.]+)\.bamboohr\.com/jobs",
    ],
    "zoho_recruit": [
        r"careers\.zohorecruitcloud\.com/([^/]+)",
        r"([^.]+)\.zohorecruit\.com",
        r"recruit\.zoho\.com/([^/]+)",
    ],
    "bullhorn": [
        r"([^.]+)\.bullhornstaffing\.com",
        r"cls\d+\.bullhornstaffing\.com/([^/]+)",
    ],
    "gem": [
        r"jobs\.gem\.com/([^/]+)",
        r"([^.]+)\.gem\.com/careers",
    ],
    "jazzhr": [
        r"([^.]+)\.applytojob\.com",
        r"app\.jazz\.co/([^/]+)",
    ],
    "freshteam": [
        r"([^.]+)\.freshteam\.com/jobs",
        r"([^.]+)\.freshteam\.com",
    ],
    "recruitee": [
        r"([^.]+)\.recruitee\.com",
        r"careers\.recruitee\.com/([^/]+)",
    ],
    "pinpoint": [
        r"([^.]+)\.pinpointhq\.com",
        r"careers\.([^.]+)\.pinpointhq\.com",
    ],
    "pcrecruiter": [
        r"([^.]+)\.pcrecruiter\.net",
        r"jobs\.pcrecruiter\.net/([^/]+)",
    ],
    "recruitcrm": [
        r"([^.]+)\.recruitcrm\.io",
        r"portal\.recruitcrm\.io/([^/]+)",
    ],
    "manatal": [
        r"([^.]+)\.manatal\.com",
        r"jobs\.manatal\.com/([^/]+)",
    ],
    "recooty": [
        r"([^.]+)\.recooty\.com",
        r"jobs\.recooty\.com/([^/]+)",
    ],
    "successfactors": [
        r"([^.]+)\.successfactors\.com",
        r"careers\.([^.]+)\.successfactors\.eu",
        r"performancemanager\d*\.successfactors\.com/([^/]+)",
    ],
    "gohire": [
        r"([^.]+)\.gohire\.io",
        r"careers\.gohire\.io/([^/]+)",
    ],
    "folkshr": [
        r"([^.]+)\.folkshr\.com",
        r"careers\.folkshr\.com/([^/]+)",
    ],
    "boon": [
        r"([^.]+)\.goboon\.co",
        r"referrals\.goboon\.co/([^/]+)",
    ],
    "talentreef": [
        r"([^.]+)\.talentreef\.com",
        r"careers\.talentreef\.com/([^/]+)",
    ],
    "eddy": [
        r"([^.]+)\.eddy\.com/careers",
        r"careers\.eddy\.com/([^/]+)",
    ],
    "jobvite": [
        r"jobs\.jobvite\.com/([^/]+)",
        r"([^.]+)\.jobvite\.com",
    ],
    "icims": [
        r"careers-([^.]+)\.icims\.com",
        r"([^.]+)\.icims\.com",
    ],
    "smartrecruiters": [
        r"jobs\.smartrecruiters\.com/([^/]+)",
        r"([^.]+)\.smartrecruiters\.com",
    ],
    "rippling": [
        r"ats\.rippling\.com/([^/]+)",
        r"([^.]+)\.rippling\.com/jobs",
    ],
    "scalis": [
        r"([^.]+)\.scalis\.ai/jobs",
        r"scalis\.ai/([^/]+)",
    ],
    "paylocity": [
        r"recruiting\.paylocity\.com/recruiting/jobs/([^/]+)",
        r"([^.]+)\.paylocity\.com",
    ],
    "breezy": [
        r"([^.]+)\.breezy\.hr",
        r"breezy\.hr/p/([^/]+)",
    ],
    "personio": [
        r"([^.]+)\.jobs\.personio\.de",
        r"([^.]+)\.jobs\.personio\.com",
    ],
    "teamtailor": [
        r"([^.]+)\.teamtailor\.com",
        r"career\.([^.]+)\.com",  # Some use custom domains with teamtailor
    ],
    "wellfound": [
        r"wellfound\.com/company/([^/]+)",
        r"angel\.co/company/([^/]+)",  # Legacy AngelList
    ],
}

# HTML patterns for ATS detection
HTML_PATTERNS = {
    "greenhouse": [
        r"greenhouse\.io",
        r"grnhse_",
        r"greenhouse-job-board",
    ],
    "lever": [
        r"lever\.co",
        r"lever-jobs",
        r"LeverJobsContainer",
    ],
    "ashby": [
        r"ashbyhq\.com",
        r"ashby-job-posting",
    ],
    "workable": [
        r"workable\.com",
        r"whr-embed",
        r"workable-job-widget",
    ],
    "workday": [
        r"workday",
        r"wd-candidate",
    ],
    "bamboohr": [
        r"bamboohr\.com",
        r"BambooHR",
        r"bamboo-job-board",
    ],
    "zoho_recruit": [
        r"zohorecruit",
        r"zohorecruitcloud",
        r"zoho-recruit",
    ],
    "bullhorn": [
        r"bullhorn",
        r"bullhornstaffing",
    ],
    "gem": [
        r"gem\.com/jobs",
        r"gem-careers",
    ],
    "jazzhr": [
        r"jazzhr",
        r"applytojob\.com",
        r"jazz\.co",
    ],
    "freshteam": [
        r"freshteam",
        r"freshworks",
    ],
    "recruitee": [
        r"recruitee",
        r"recruitee-careers",
    ],
    "pinpoint": [
        r"pinpointhq",
        r"pinpoint-careers",
    ],
    "pcrecruiter": [
        r"pcrecruiter",
    ],
    "recruitcrm": [
        r"recruitcrm",
    ],
    "manatal": [
        r"manatal",
    ],
    "recooty": [
        r"recooty",
    ],
    "successfactors": [
        r"successfactors",
        r"SAP.*SuccessFactors",
    ],
    "gohire": [
        r"gohire",
    ],
    "folkshr": [
        r"folkshr",
        r"folks-careers",
    ],
    "boon": [
        r"goboon\.co",
        r"boon-referral",
    ],
    "talentreef": [
        r"talentreef",
    ],
    "eddy": [
        r"eddy\.com/careers",
    ],
    "jobvite": [
        r"jobvite",
    ],
    "icims": [
        r"icims",
    ],
    "smartrecruiters": [
        r"smartrecruiters",
    ],
    "rippling": [
        r"rippling\.com",
        r"ats\.rippling",
    ],
    "scalis": [
        r"scalis\.ai",
        r"scalis-careers",
    ],
    "paylocity": [
        r"paylocity",
        r"recruiting\.paylocity",
    ],
    "breezy": [
        r"breezy\.hr",
        r"breezyhr",
    ],
    "personio": [
        r"personio",
        r"jobs\.personio",
    ],
    "teamtailor": [
        r"teamtailor",
        r"career-page",
    ],
    "wellfound": [
        r"wellfound\.com",
        r"angel\.co",
    ],
}


def detect_ats_from_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Detect ATS type and identifier from URL pattern."""
    # Invalid identifiers that should be treated as "no identifier found"
    INVALID_IDENTIFIERS = {
        'embed', 'job_board', 'js', 'css', 'api', 'jobs', 'undefined',
        '${boardtoken}', '${ghslug}', '${board_token}',
    }
    
    for ats_type, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                identifier = match.group(1) if match.groups() else None
                # Skip invalid identifiers - return ats_type but no identifier
                if identifier and identifier.lower() in INVALID_IDENTIFIERS:
                    identifier = None
                return ats_type, identifier

    return None, None


def detect_ats_from_html(html: str) -> Optional[str]:
    """Detect ATS type from HTML content."""
    html_lower = html.lower()

    for ats_type, patterns in HTML_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, html_lower):
                return ats_type

    return None


async def detect_ats_type(
    client: httpx.AsyncClient,
    url: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Detect ATS type from URL and optionally page content."""
    # First try URL-based detection
    ats_type, identifier = detect_ats_from_url(url)

    if ats_type:
        return ats_type, identifier

    # If not detected from URL, try fetching the page
    try:
        response = await client.get(url)
        response.raise_for_status()

        html = response.text
        ats_type = detect_ats_from_html(html)

        # Try to extract identifier from page
        if ats_type:
            # Look for embedded config or data attributes
            identifier = extract_identifier_from_html(html, ats_type)

        return ats_type, identifier

    except Exception as e:
        logger.warning("Failed to fetch page for ATS detection", url=url, error=str(e))
        return None, None


def extract_identifier_from_html(html: str, ats_type: str) -> Optional[str]:
    """
    Extract company identifier from HTML based on ATS type.
    
    This is the canonical function for extracting ATS identifiers from HTML content.
    Used by both discovery and crawl engines.
    
    Checks for:
    - Data attributes (e.g., data-board-token)
    - Embedded script URLs (e.g., script src containing ATS domain)
    - Inline JavaScript config
    - Direct URLs in the page
    """
    # Invalid greenhouse identifiers that should be skipped
    INVALID_GH_SLUGS = {'embed', 'job_board', 'js', 'css', 'api', 'jobs', 
                        '${boardToken}', '${ghSlug}', '${board_token}', 'undefined'}
    
    if ats_type == "greenhouse":
        # Look for greenhouse board token in various locations
        # Pattern 1: data-board-token attribute (most reliable)
        match = re.search(r'data-board-token="([^"]+)"', html)
        if match and match.group(1) not in INVALID_GH_SLUGS:
            return match.group(1)
        
        # Pattern 2: Greenhouse script settings
        match = re.search(r"Grnhse\.Settings\.boardToken\s*=\s*['\"]([^'\"]+)['\"]", html)
        if match and match.group(1) not in INVALID_GH_SLUGS:
            return match.group(1)
        
        # Pattern 3: for= parameter in embed URL (common)
        match = re.search(r'boards\.greenhouse\.io/embed/job_board[^"\']*[?&]for=([^&"\'#\s]+)', html)
        if match and match.group(1) not in INVALID_GH_SLUGS:
            return match.group(1)
        
        # Pattern 4: boardToken in JavaScript (various formats)
        for pattern in [
            r'boardToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'"board_token"\s*:\s*"([^"]+)"',
            r"'board_token'\s*:\s*'([^']+)'",
            r'board:\s*["\']([^"\']+)["\']',
        ]:
            match = re.search(pattern, html)
            if match and match.group(1) not in INVALID_GH_SLUGS:
                return match.group(1)
        
        # Pattern 5: From API URL (reliable - has actual board slug)
        match = re.search(r'boards-api\.greenhouse\.io/v1/boards/([^/"\'?#\s]+)', html)
        if match and match.group(1) not in INVALID_GH_SLUGS:
            return match.group(1)
        
        # Pattern 6: Direct board URL (NOT embed URLs) - e.g., boards.greenhouse.io/companyname
        for m in re.finditer(r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', html):
            slug = m.group(1).lower()
            if slug not in INVALID_GH_SLUGS and len(slug) > 2:
                return m.group(1)
        
        # Pattern 7: iframe src with greenhouse URL
        match = re.search(r'<iframe[^>]+src="[^"]*boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', html)
        if match and match.group(1).lower() not in INVALID_GH_SLUGS:
            return match.group(1)
        
        # Return None if only "embed" pattern found - don't use it
        return None

    elif ats_type == "lever":
        # Look for lever site ID
        match = re.search(r'data-lever-site="([^"]+)"', html)
        if match:
            return match.group(1)
        # From embed script
        match = re.search(r'jobs\.lever\.co/([^/"\']+)/embed', html)
        if match:
            return match.group(1)
        # From URL in page
        match = re.search(r"jobs\.lever\.co/([^/\"']+)", html)
        if match:
            return match.group(1)

    elif ats_type == "ashby":
        # Look for ashby job board ID in various patterns
        # Pattern 1: Embed script like <script src="https://jobs.ashbyhq.com/company.name/embed">
        match = re.search(r'jobs\.ashbyhq\.com/([^/\"\']+)/embed', html)
        if match:
            return match.group(1)
        # Pattern 2: Direct URL pattern
        match = re.search(r"jobs\.ashbyhq\.com/([^/\"']+)", html)
        if match:
            return match.group(1)
        # Pattern 3: API URL in script
        match = re.search(r'api\.ashbyhq\.com/posting-api/job-board/([^/\"\']+)', html)
        if match:
            return match.group(1)

    elif ats_type == "workable":
        # From embed script or URL
        match = re.search(r'apply\.workable\.com/([^/"\']+)', html)
        if match:
            return match.group(1)
        # From workable integration embed
        match = re.search(r'workable\.com/integrations/embed/([^/"\']+)', html)
        if match:
            return match.group(1)
        # From subdomain in script data
        match = re.search(r'"subdomain"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)

    elif ats_type == "recruitee":
        # From embedded script or URL
        match = re.search(r'([^./]+)\.recruitee\.com', html)
        if match:
            return match.group(1)

    elif ats_type == "bamboohr":
        match = re.search(r'([^./]+)\.bamboohr\.com', html)
        if match:
            return match.group(1)

    elif ats_type == "smartrecruiters":
        match = re.search(r'jobs\.smartrecruiters\.com/([^/"\']+)', html)
        if match:
            return match.group(1)

    elif ats_type == "jobvite":
        match = re.search(r'jobs\.jobvite\.com/([^/"\']+)', html)
        if match:
            return match.group(1)

    elif ats_type == "icims":
        match = re.search(r'careers-([^.]+)\.icims\.com', html)
        if match:
            return match.group(1)
        match = re.search(r'([^./]+)\.icims\.com', html)
        if match:
            return match.group(1)

    return None


def _is_valid_careers_url_for_domain(careers_url: str, company_domain: str) -> bool:
    """
    Check if a careers URL is valid for a given company domain.
    
    Valid cases:
    1. Same domain or subdomain (e.g., careers.company.com for company.com)
    2. Known ATS platforms (greenhouse.io, lever.co, etc.)
    3. URL contains the company name/domain as identifier
    
    Invalid cases:
    - Careers URL pointing to a completely different company's domain
    """
    parsed = urlparse(careers_url)
    careers_host = parsed.netloc.lower()
    company_domain = company_domain.lower()
    
    # Extract the base domain (without subdomains) for comparison
    # e.g., "www.company.com" -> "company.com"
    company_parts = company_domain.split(".")
    if len(company_parts) >= 2:
        company_base = ".".join(company_parts[-2:])  # company.com
    else:
        company_base = company_domain
    
    careers_parts = careers_host.split(".")
    if len(careers_parts) >= 2:
        careers_base = ".".join(careers_parts[-2:])
    else:
        careers_base = careers_host
    
    # Case 1: Same domain or subdomain
    if company_base == careers_base:
        return True
    
    # Case 2: Known ATS platforms - these are always valid
    ats_domains = [
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "workable.com",
        "myworkdayjobs.com",
        "bamboohr.com",
        "zohorecruit.com",
        "zohorecruitcloud.com",
        "bullhornstaffing.com",
        "gem.com",
        "applytojob.com",
        "jazz.co",
        "freshteam.com",
        "recruitee.com",
        "pinpointhq.com",
        "pcrecruiter.net",
        "recruitcrm.io",
        "manatal.com",
        "recooty.com",
        "successfactors.com",
        "successfactors.eu",
        "gohire.io",
        "folkshr.com",
        "goboon.co",
        "talentreef.com",
        "eddy.com",
        "jobvite.com",
        "icims.com",
        "smartrecruiters.com",
        "rippling.com",
        "scalis.ai",
        "paylocity.com",
        "breezy.hr",
        "personio.de",
        "personio.com",
        "teamtailor.com",
        "wellfound.com",
        "angel.co",
    ]
    
    for ats_domain in ats_domains:
        if careers_host.endswith(ats_domain):
            return True
    
    # Case 3: Check if company name appears in the careers URL path/subdomain
    # Extract company name from domain (e.g., "bankinfosecurity" from "bankinfosecurity.asia")
    company_name = company_parts[0] if company_parts else company_domain
    
    # Check if company name is in the careers URL (subdomain or path)
    if company_name in careers_host or company_name in parsed.path.lower():
        return True
    
    # Invalid: careers URL points to a different company
    return False


async def get_careers_url(
    client: httpx.AsyncClient,
    domain: str,
) -> Optional[str]:
    """Try to find the careers page URL for a domain."""
    # Common careers page paths
    paths = [
        "/careers",
        "/jobs",
        "/careers/",
        "/jobs/",
        "/join-us",
        "/join",
        "/work-with-us",
        "/about/careers",
        "/company/careers",
    ]

    base_url = f"https://{domain}"

    for path in paths:
        try:
            url = f"{base_url}{path}"
            response = await client.head(url, follow_redirects=True)

            if response.status_code == 200:
                # Check if redirected to an ATS
                final_url = str(response.url)
                ats_type, _ = detect_ats_from_url(final_url)

                if ats_type:
                    # Validate that the ATS URL is for this company
                    if _is_valid_careers_url_for_domain(final_url, domain):
                        return final_url
                    else:
                        logger.debug(
                            "Skipping careers URL - belongs to different company",
                            domain=domain,
                            careers_url=final_url,
                        )
                        continue

                # Otherwise return the careers page (same domain)
                return final_url

        except Exception:
            continue

    # Try fetching the homepage and looking for careers links
    try:
        response = await client.get(base_url)
        if response.status_code == 200:
            html = response.text

            # Look for careers links
            patterns = [
                r'href="([^"]*(?:careers|jobs)[^"]*)"',
                r"href='([^']*(?:careers|jobs)[^']*)'",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if match.startswith("http"):
                        # Validate external URLs belong to this company
                        if _is_valid_careers_url_for_domain(match, domain):
                            return match
                        else:
                            logger.debug(
                                "Skipping external careers URL - belongs to different company",
                                domain=domain,
                                careers_url=match,
                            )
                            continue
                    elif match.startswith("/"):
                        # Relative URLs are always valid (same domain)
                        return f"{base_url}{match}"

    except Exception:
        pass

    return None
