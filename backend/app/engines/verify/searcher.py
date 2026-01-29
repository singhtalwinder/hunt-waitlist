"""Direct job board scraping for real-time verification using Playwright."""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import structlog
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

logger = structlog.get_logger()


@dataclass
class SearchResult:
    """Result from searching for a job on a board."""

    found: bool
    confidence: float  # 0-1, how confident we are in the result
    listing_url: Optional[str] = None
    result_count: int = 0


class JobBoardScraper:
    """Direct scraper for job boards using Playwright."""

    def __init__(self, min_delay: Optional[float] = None):
        """Initialize the scraper.

        Args:
            min_delay: Minimum seconds between requests to same domain.
        """
        from app.config import get_settings

        self._playwright = None
        self._browser: Optional[Browser] = None
        # Rate limiting: track last request time per domain
        self._last_request: dict[str, float] = {}

        settings = get_settings()
        self._min_delay = min_delay or settings.verification_request_delay

    async def _get_browser(self) -> Browser:
        """Get or create the browser instance."""
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )
        return self._browser

    async def close(self) -> None:
        """Close the browser and playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _rate_limit(self, domain: str) -> None:
        """Enforce rate limiting for a domain."""
        import time

        now = time.time()
        last = self._last_request.get(domain, 0)
        wait_time = self._min_delay - (now - last)

        if wait_time > 0:
            logger.debug("Rate limiting", domain=domain, wait_seconds=wait_time)
            await asyncio.sleep(wait_time)

        self._last_request[domain] = time.time()

    async def _create_stealth_page(self) -> Page:
        """Create a new page with stealth settings."""
        browser = await self._get_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )

        page = await context.new_page()

        # Add stealth scripts
        await page.add_init_script("""
            // Override webdriver detection
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        return page

    async def search_job_on_board(
        self,
        company: str,
        title: str,
        board: str,
    ) -> SearchResult:
        """Search for a job on a specific board.

        Args:
            company: Company name.
            title: Job title.
            board: Board name (linkedin, indeed).

        Returns:
            SearchResult with found status and confidence.
        """
        if board == "linkedin":
            return await self._search_linkedin(company, title)
        elif board == "indeed":
            return await self._search_indeed(company, title)
        else:
            logger.warning("Unsupported board", board=board)
            return SearchResult(found=False, confidence=0.0)

    async def _search_linkedin(self, company: str, title: str) -> SearchResult:
        """Search LinkedIn Jobs for a specific job directly."""
        # Use direct LinkedIn public jobs search
        return await self._search_linkedin_direct(company, title)

    async def _search_linkedin_direct(self, company: str, title: str) -> SearchResult:
        """Search LinkedIn Jobs directly (backup method)."""
        await self._rate_limit("linkedin.com")

        # Build public jobs search URL (works without login)
        # Include both company and title in keywords for better matching
        keywords = quote_plus(f"{company} {title}")
        url = f"https://www.linkedin.com/jobs/search?keywords={keywords}&location=United%20States&trk=public_jobs_jobs-search-bar_search-submit"

        logger.debug("Searching LinkedIn directly", company=company, title=title, url=url)

        page = await self._create_stealth_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Check if we got redirected to login
            if "authwall" in page.url or "login" in page.url:
                logger.debug("LinkedIn: Redirected to login", company=company)
                return SearchResult(found=False, confidence=0.5, result_count=0)

            # Wait for job cards to load (or timeout)
            try:
                await page.wait_for_selector(
                    ".jobs-search__results-list, .base-card, .job-search-card, .base-search-card",
                    timeout=10000
                )
            except PlaywrightTimeout:
                # No results found
                logger.debug("LinkedIn: No job cards found", company=company, title=title)
                return SearchResult(found=False, confidence=0.9, result_count=0)

            # Get job cards - selectors for public jobs page
            cards = await page.query_selector_all(
                ".base-card, .base-search-card, .job-search-card"
            )

            if not cards:
                return SearchResult(found=False, confidence=0.9, result_count=0)

            # Check each card for a match
            company_lower = company.lower()
            title_words = set(self._extract_significant_words(title.lower()))

            for card in cards[:20]:  # Check first 20 results
                try:
                    # Get company name from card (h4 or subtitle class)
                    company_el = await card.query_selector(
                        "h4, .base-search-card__subtitle, .job-search-card__subtitle"
                    )
                    card_company = (await company_el.text_content()).strip().lower() if company_el else ""

                    # Get job title from card (h3 or title class)
                    title_el = await card.query_selector(
                        "h3, .base-search-card__title, .job-search-card__title"
                    )
                    card_title = (await title_el.text_content()).strip().lower() if title_el else ""

                    # Check company match
                    if not self._fuzzy_company_match(company_lower, card_company):
                        continue

                    # Check title match
                    card_title_words = set(self._extract_significant_words(card_title))
                    if not title_words:
                        continue

                    overlap = len(title_words & card_title_words) / len(title_words)
                    if overlap >= 0.5:
                        # Found a match!
                        link_el = await card.query_selector("a")
                        link = await link_el.get_attribute("href") if link_el else None

                        logger.info(
                            "LinkedIn: Found matching job",
                            company=company,
                            title=title,
                            card_company=card_company,
                            card_title=card_title,
                        )

                        return SearchResult(
                            found=True,
                            confidence=0.85,
                            listing_url=link,
                            result_count=len(cards),
                        )

                except Exception as e:
                    logger.debug("Error parsing LinkedIn card", error=str(e))
                    continue

            # No match found in results
            return SearchResult(
                found=False,
                confidence=0.8,
                result_count=len(cards),
            )

        except PlaywrightTimeout:
            logger.warning("LinkedIn search timeout", company=company, title=title)
            return SearchResult(found=False, confidence=0.5, result_count=0)
        except Exception as e:
            logger.error("LinkedIn search error", error=str(e), company=company, title=title)
            return SearchResult(found=False, confidence=0.3, result_count=0)
        finally:
            await page.context.close()

    async def _search_indeed(self, company: str, title: str) -> SearchResult:
        """Search Indeed for a specific job via Bing."""
        # Use Bing search with site:indeed.com for reliable results
        return await self._search_via_bing(company, title, "indeed.com")

    async def _search_indeed_direct(self, company: str, title: str) -> SearchResult:
        """Search Indeed directly (backup method)."""
        await self._rate_limit("indeed.com")

        # Build search URL
        query = quote_plus(f"{title}")
        company_query = quote_plus(company)
        url = f"https://www.indeed.com/jobs?q={query}&l=United+States&fromage=14"

        logger.debug("Searching Indeed", company=company, title=title, url=url)

        page = await self._create_stealth_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for job cards
            try:
                await page.wait_for_selector(
                    ".job_seen_beacon, .jobsearch-ResultsList, .tapItem",
                    timeout=10000
                )
            except PlaywrightTimeout:
                logger.debug("Indeed: No job cards found", company=company, title=title)
                return SearchResult(found=False, confidence=0.9, result_count=0)

            # Get job cards
            cards = await page.query_selector_all(
                ".job_seen_beacon, .tapItem, [data-jk]"
            )

            if not cards:
                return SearchResult(found=False, confidence=0.9, result_count=0)

            company_lower = company.lower()
            title_words = set(self._extract_significant_words(title.lower()))

            for card in cards[:15]:  # Check first 15 results
                try:
                    # Get company name
                    company_el = await card.query_selector(
                        "[data-testid='company-name'], .companyName, .company"
                    )
                    card_company = (await company_el.text_content()).strip().lower() if company_el else ""

                    # Get job title
                    title_el = await card.query_selector(
                        "[data-testid='jobTitle'], .jobTitle, h2.jobTitle a, .title"
                    )
                    card_title = (await title_el.text_content()).strip().lower() if title_el else ""

                    # Check company match
                    if not self._fuzzy_company_match(company_lower, card_company):
                        continue

                    # Check title match
                    card_title_words = set(self._extract_significant_words(card_title))
                    if not title_words:
                        continue

                    overlap = len(title_words & card_title_words) / len(title_words)
                    if overlap >= 0.5:
                        # Found a match!
                        link_el = await card.query_selector("a[data-jk], a.jcs-JobTitle")
                        link = None
                        if link_el:
                            href = await link_el.get_attribute("href")
                            if href:
                                link = f"https://www.indeed.com{href}" if href.startswith("/") else href

                        logger.info(
                            "Indeed: Found matching job",
                            company=company,
                            title=title,
                            card_company=card_company,
                            card_title=card_title,
                        )

                        return SearchResult(
                            found=True,
                            confidence=0.85,
                            listing_url=link,
                            result_count=len(cards),
                        )

                except Exception as e:
                    logger.debug("Error parsing Indeed card", error=str(e))
                    continue

            # No match found
            return SearchResult(
                found=False,
                confidence=0.8,
                result_count=len(cards),
            )

        except PlaywrightTimeout:
            logger.warning("Indeed search timeout", company=company, title=title)
            return SearchResult(found=False, confidence=0.5, result_count=0)
        except Exception as e:
            logger.error("Indeed search error", error=str(e), company=company, title=title)
            return SearchResult(found=False, confidence=0.3, result_count=0)
        finally:
            await page.context.close()

    def _fuzzy_company_match(self, expected: str, actual: str) -> bool:
        """Check if company names match (fuzzy)."""
        expected = self._normalize_company(expected)
        actual = self._normalize_company(actual)

        # Exact match
        if expected == actual:
            return True

        # One contains the other
        if expected in actual or actual in expected:
            return True

        # Check word overlap
        expected_words = set(expected.split())
        actual_words = set(actual.split())

        if not expected_words:
            return False

        overlap = len(expected_words & actual_words) / len(expected_words)
        return overlap >= 0.5

    def _normalize_company(self, name: str) -> str:
        """Normalize company name for comparison."""
        name = name.lower()
        # Remove common suffixes
        name = re.sub(r"\s*(inc\.?|corp\.?|llc|ltd\.?|co\.?|company|technologies|labs?)\s*$", "", name)
        # Remove punctuation
        name = re.sub(r"[^\w\s]", "", name)
        return name.strip()

    def _slugify_company(self, name: str) -> str:
        """Convert company name to LinkedIn slug format."""
        # Lowercase and normalize
        slug = name.lower().strip()
        # Remove common suffixes
        slug = re.sub(r"\s*(inc\.?|corp\.?|llc|ltd\.?|co\.?|company)\s*$", "", slug)
        # Replace spaces with nothing (LinkedIn uses no separator)
        slug = re.sub(r"\s+", "", slug)
        # Remove special characters except hyphens
        slug = re.sub(r"[^\w-]", "", slug)
        return slug

    async def _search_via_bing(self, company: str, title: str, site: str) -> SearchResult:
        """Search for a job via Bing with site: operator."""
        await self._rate_limit("bing.com")

        # Build Bing search query
        query = f'{company} {title} site:{site}'
        url = f"https://www.bing.com/search?q={quote_plus(query)}"

        logger.debug("Searching via Bing", company=company, title=title, site=site, url=url)

        page = await self._create_stealth_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # Wait for results

            # Get search result links - Bing selectors
            results = await page.query_selector_all("#b_results .b_algo h2 a, .b_algo a")
            
            result_count = len(results)
            logger.debug("Bing search results", count=result_count, company=company, title=title)

            if result_count == 0:
                return SearchResult(found=False, confidence=0.85, result_count=0)

            # Check if any result matches
            company_lower = company.lower()
            title_words = set(self._extract_significant_words(title.lower()))

            for result in results[:10]:
                href = await result.get_attribute("href") or ""
                text = (await result.text_content() or "").lower()
                
                # Must be from the target site
                if site not in href:
                    continue

                # Check if company appears in the result
                company_in_text = company_lower in text or any(
                    word in text for word in company_lower.split() if len(word) > 3
                )
                
                # Check if significant title words appear (looser matching)
                matching_words = sum(1 for word in title_words if word in text)
                title_match = matching_words >= max(1, len(title_words) * 0.3) if title_words else False

                if company_in_text and title_match:
                    logger.info(
                        "Bing: Found matching job listing",
                        company=company,
                        title=title,
                        href=href,
                    )
                    return SearchResult(
                        found=True,
                        confidence=0.85,
                        listing_url=href,
                        result_count=result_count,
                    )

            return SearchResult(found=False, confidence=0.75, result_count=result_count)

        except PlaywrightTimeout:
            logger.warning("Bing search timeout", company=company, title=title)
            return SearchResult(found=False, confidence=0.4, result_count=0)
        except Exception as e:
            logger.error("Bing search error", error=str(e), company=company, title=title)
            return SearchResult(found=False, confidence=0.3, result_count=0)
        finally:
            await page.context.close()

    async def _search_via_duckduckgo(self, company: str, title: str, site: str) -> SearchResult:
        """Search for a job via DuckDuckGo with site: operator."""
        await self._rate_limit("duckduckgo.com")

        # Build DuckDuckGo search query - use regular version (not HTML)
        query = f'{company} {title} site:{site}'
        url = f"https://duckduckgo.com/?q={quote_plus(query)}"

        logger.debug("Searching via DuckDuckGo", company=company, title=title, site=site, url=url)

        page = await self._create_stealth_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for results to load
            try:
                await page.wait_for_selector("[data-testid='result'], .react-results--main, article", timeout=10000)
            except PlaywrightTimeout:
                logger.debug("DuckDuckGo: No results selector found", company=company, title=title)

            await asyncio.sleep(1)  # Brief wait for JS to finish

            # Get all heading links (h2 a elements are the result titles)
            results = await page.query_selector_all("article h2 a, [data-testid='result-title-a'], h2 a")
            
            result_count = len(results)
            logger.debug("DuckDuckGo search results", count=result_count, company=company, title=title)

            if result_count == 0:
                # Try alternate selector
                results = await page.query_selector_all("a[href*='" + site.split('/')[0] + "']")
                result_count = len(results)
                logger.debug("DuckDuckGo alternate selector", count=result_count)

            if result_count == 0:
                return SearchResult(found=False, confidence=0.85, result_count=0)

            # Check if any result looks like a job listing
            company_lower = company.lower()
            title_words = set(self._extract_significant_words(title.lower()))

            for result in results[:15]:
                href = await result.get_attribute("href") or ""
                text = (await result.text_content() or "").lower()
                
                # Must be from the target site
                if site.split('/')[0] not in href:
                    continue

                # Check if company appears in the result
                company_in_text = company_lower in text or any(
                    word in text for word in company_lower.split() if len(word) > 3
                )
                
                # Check if significant title words appear
                matching_words = sum(1 for word in title_words if word in text)
                title_match = matching_words >= len(title_words) * 0.3 if title_words else False

                if company_in_text and title_match:
                    logger.info(
                        "DuckDuckGo: Found matching job listing",
                        company=company,
                        title=title,
                        href=href,
                        text=text[:100],
                    )
                    return SearchResult(
                        found=True,
                        confidence=0.85,
                        listing_url=href if href.startswith("http") else None,
                        result_count=result_count,
                    )

            # Results found but no clear match - log what we saw
            logger.debug("DuckDuckGo: No matching result", company=company, title=title, 
                        sample_texts=[await r.text_content() for r in results[:3]])
            return SearchResult(
                found=False,
                confidence=0.75,
                result_count=result_count,
            )

        except PlaywrightTimeout:
            logger.warning("DuckDuckGo search timeout", company=company, title=title)
            return SearchResult(found=False, confidence=0.4, result_count=0)
        except Exception as e:
            logger.error("DuckDuckGo search error", error=str(e), company=company, title=title)
            return SearchResult(found=False, confidence=0.3, result_count=0)
        finally:
            await page.context.close()

    async def _search_via_google(self, company: str, title: str, site: str) -> SearchResult:
        """Search for a job via Google with site: operator."""
        await self._rate_limit("google.com")

        # Build Google search query
        # Use quotes for exact phrase matching
        query = f'"{company}" "{title}" site:{site}'
        url = f"https://www.google.com/search?q={quote_plus(query)}"

        logger.debug("Searching via Google", company=company, title=title, site=site, url=url)

        page = await self._create_stealth_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Check for CAPTCHA
            content = await page.content()
            if "captcha" in content.lower() or "unusual traffic" in content.lower():
                logger.warning("Google CAPTCHA detected", company=company, title=title)
                return SearchResult(found=False, confidence=0.3, result_count=0)

            # Wait for results
            try:
                await page.wait_for_selector("#search, .g, [data-hveid]", timeout=10000)
            except PlaywrightTimeout:
                logger.debug("Google: No search results found", company=company, title=title)
                return SearchResult(found=False, confidence=0.8, result_count=0)

            # Get search result links
            results = await page.query_selector_all("#search a[href*='" + site + "']")
            
            if not results:
                # Try alternate selector
                results = await page.query_selector_all(f"a[href*='{site}']")

            result_count = len(results)
            logger.debug("Google search results", count=result_count, company=company, title=title)

            if result_count == 0:
                return SearchResult(found=False, confidence=0.85, result_count=0)

            # Check if any result looks like a job listing
            for result in results[:5]:
                href = await result.get_attribute("href") or ""
                text = (await result.text_content() or "").lower()
                
                # Skip non-job URLs
                if "/jobs/" not in href and "/job/" not in href:
                    continue

                # Check if company and title words appear
                company_lower = company.lower()
                title_words = self._extract_significant_words(title.lower())
                
                # Simple check: does the result mention our company?
                if company_lower in text or any(word in text for word in company_lower.split()):
                    # Found a potential match
                    logger.info(
                        "Google: Found potential job listing",
                        company=company,
                        title=title,
                        href=href,
                    )
                    return SearchResult(
                        found=True,
                        confidence=0.8,
                        listing_url=href,
                        result_count=result_count,
                    )

            # Results found but no clear match
            return SearchResult(
                found=False,
                confidence=0.7,
                result_count=result_count,
            )

        except PlaywrightTimeout:
            logger.warning("Google search timeout", company=company, title=title)
            return SearchResult(found=False, confidence=0.4, result_count=0)
        except Exception as e:
            logger.error("Google search error", error=str(e), company=company, title=title)
            return SearchResult(found=False, confidence=0.3, result_count=0)
        finally:
            await page.context.close()

    def _extract_significant_words(self, text: str) -> list[str]:
        """Extract significant words from text for matching."""
        stop_words = {
            "a", "an", "the", "and", "or", "at", "in", "on", "for", "to", "of",
            "is", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "do", "does", "did", "will", "would", "could", "should",
            "may", "might", "must", "shall", "can", "need", "we", "you", "our",
            "your", "their", "this", "that", "with", "from", "by", "as", "about",
            "job", "position", "role", "opportunity", "career", "hiring", "apply",
            "now", "remote", "hybrid", "onsite", "full", "time", "part",
        }
        words = re.findall(r"\b[a-z]+\b", text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]


# Backward compatibility alias
GoogleSearcher = JobBoardScraper
