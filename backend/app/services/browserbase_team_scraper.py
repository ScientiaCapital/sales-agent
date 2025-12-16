"""
Browserbase Team Scraper Service

Uses Browserbase browser automation to scrape team/about pages from JavaScript-heavy websites.
This is a fallback for when BeautifulSoup fails (client-side rendered content).

IMPORTANT: Uses shared patterns from scraper_patterns.py to stay in sync with BeautifulSoup scraper.

Performance: ~10-15 seconds per scrape (browser automation overhead)
Cost: Browserbase session pricing (check https://browserbase.com/pricing)

Rate Limits (per project):
- Concurrency: Check project settings (default: 1-99 based on plan)
- Sessions: ~100/minute for API calls
- This scraper enforces MIN_DELAY_BETWEEN_SCRAPES to avoid rate limiting
"""

import os
import logging
import httpx
import asyncio
from typing import List, Dict, Optional
import time
from pathlib import Path

# Load .env from project root to ensure credentials are available
# override=True ensures .env values take precedence over shell env vars
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[3] / '.env'
if _env_path.exists():
    load_dotenv(_env_path, override=True)

# Import shared patterns and utilities - KEEPS BROWSERBASE IN SYNC WITH BEAUTIFULSOUP
from app.services.scraper_patterns import (
    TEAM_PAGE_PATTERNS,
    ATL_TITLE_KEYWORDS,
    GARBAGE_NAMES,
    TITLE_QUALIFIERS,
    is_atl_title,
    is_garbage_name,
    clean_title,
    split_concatenated_name,
)

logger = logging.getLogger(__name__)

# Rate limiting configuration (based on Browserbase pricing tiers)
# Free: 1 concurrent, 5/min | Developer: 25 concurrent, 25/min | Startup: 100 concurrent, 50/min
# Configure via env vars for your plan:
#   BROWSERBASE_MAX_CONCURRENT=10  (safe testing default)
#   BROWSERBASE_MIN_DELAY=1.0      (seconds between session creates)
MAX_CONCURRENT_SCRAPES = int(os.getenv("BROWSERBASE_MAX_CONCURRENT", "5"))  # safe testing limit
MIN_DELAY_BETWEEN_SCRAPES = float(os.getenv("BROWSERBASE_MIN_DELAY", "1.0"))  # seconds between scrapes
_last_scrape_time: float = 0.0
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the concurrency semaphore."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)
        logger.info(f"Browserbase concurrency limit set to {MAX_CONCURRENT_SCRAPES}")
    return _semaphore


def decode_cloudflare_email(encoded: str) -> Optional[str]:
    """
    Decode Cloudflare-protected email addresses.

    Cloudflare encodes emails using XOR with a key (first 2 hex chars).
    Example: data-cfemail="cda4a3aba28dfcbfa2a2aba1a1aee3aea2a0" -> info@1roofllc.com

    Args:
        encoded: The hex-encoded email string from data-cfemail attribute

    Returns:
        Decoded email address or None if decoding fails
    """
    if not encoded or len(encoded) < 4:
        return None
    try:
        # First 2 hex chars are the XOR key
        key = int(encoded[:2], 16)
        # Remaining chars are the encoded email
        decoded = ''.join([
            chr(int(encoded[i:i+2], 16) ^ key)
            for i in range(2, len(encoded), 2)
        ])
        # Validate it looks like an email
        if '@' in decoded and '.' in decoded:
            return decoded.lower()
        return None
    except (ValueError, IndexError) as e:
        logger.debug(f"Failed to decode Cloudflare email: {e}")
        return None


class BrowserbaseTeamScraper:
    """
    Scrapes team/about pages using Browserbase browser automation.

    Use this when:
    - Website uses React/Vue/Angular (client-side rendering)
    - BeautifulSoup returns no results (JavaScript-rendered content)
    - Team page requires interaction (e.g., "Load More" buttons)

    Browserbase API Reference:
    - Sessions API: https://docs.browserbase.com/api-reference/sessions
    - Extensions: Can add custom scrapers as extensions

    NOTE: Uses shared patterns from scraper_patterns.py for consistency with BeautifulSoup scraper.
    """

    def __init__(self):
        self.api_key = os.getenv("BROWSERBASE_API_KEY")
        self.project_id = os.getenv("BROWSERBASE_PROJECT_ID")
        self.base_url = "https://api.browserbase.com/v1"
        self.timeout = 30.0  # Browser sessions can take time

        if not self.api_key or not self.project_id:
            logger.warning("Browserbase credentials not configured - fallback scraping disabled")

    async def scrape_team_page(
        self,
        website_url: str
    ) -> List[Dict[str, str]]:
        """
        Scrape team/about page using Browserbase automation.

        Args:
            website_url: Company website URL (e.g., "https://acme.com")

        Returns:
            List of ATL contacts: [{"name": str, "title": str, "email": Optional[str]}]
        """
        global _last_scrape_time

        if not self.api_key or not self.project_id:
            logger.error("Browserbase not configured - cannot scrape")
            return []

        # Use semaphore for safe concurrent limit (default: 5)
        semaphore = _get_semaphore()
        async with semaphore:
            # Rate limiting: ensure minimum delay between scrapes
            if MIN_DELAY_BETWEEN_SCRAPES > 0:
                elapsed = time.time() - _last_scrape_time
                if elapsed < MIN_DELAY_BETWEEN_SCRAPES:
                    wait_time = MIN_DELAY_BETWEEN_SCRAPES - elapsed
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s before Browserbase scrape")
                    await asyncio.sleep(wait_time)
                _last_scrape_time = time.time()

            try:
                logger.info(f"Starting Browserbase team scraping for: {website_url}")

                # Step 1: Create Browserbase session
                session_id, connect_url = await self._create_session()

                # Step 2: Navigate to team page and scrape
                team_contacts = await self._scrape_with_session(session_id, website_url, connect_url)

                # Step 3: Close session
                await self._close_session(session_id)

                logger.info(
                    f"Browserbase scraping completed: {website_url} "
                    f"({len(team_contacts)} ATL contacts found)"
                )

                return team_contacts

            except Exception as e:
                logger.error(f"Browserbase scraping failed for {website_url}: {e}", exc_info=True)
                return []

    async def scrape_single_url(self, url: str) -> List[Dict[str, str]]:
        """
        Scrape a SINGLE known URL directly - no URL discovery.

        Use this when you already know the exact team page URL (e.g., from BeautifulSoup).

        Args:
            url: The exact URL to scrape (e.g., "https://acme.com/about-us")

        Returns:
            List of ATL contacts found.
        """
        global _last_scrape_time

        if not self.api_key or not self.project_id:
            logger.error("Browserbase not configured - cannot scrape")
            return []

        semaphore = _get_semaphore()
        async with semaphore:
            # Rate limiting
            if MIN_DELAY_BETWEEN_SCRAPES > 0:
                elapsed = time.time() - _last_scrape_time
                if elapsed < MIN_DELAY_BETWEEN_SCRAPES:
                    wait_time = MIN_DELAY_BETWEEN_SCRAPES - elapsed
                    logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                _last_scrape_time = time.time()

            try:
                logger.info(f"Browserbase scraping single URL: {url}")

                session_id, connect_url = await self._create_session()
                contacts = await self._scrape_single_url_with_session(session_id, url, connect_url)
                await self._close_session(session_id)

                logger.info(f"Browserbase single URL complete: {url} ({len(contacts)} contacts)")
                return contacts

            except Exception as e:
                logger.error(f"Browserbase scraping failed for {url}: {e}", exc_info=True)
                return []

    async def _scrape_single_url_with_session(
        self,
        session_id: str,
        url: str,
        connect_url: str
    ) -> List[Dict[str, str]]:
        """Scrape a single URL directly without trying multiple patterns."""
        from playwright.async_api import async_playwright

        contacts = []

        try:
            async with async_playwright() as p:
                logger.info(f"Connecting to Browserbase session: {session_id}")
                browser = await p.chromium.connect_over_cdp(connect_url)

                contexts = browser.contexts
                if not contexts:
                    logger.error("No browser contexts available")
                    return []

                context = contexts[0]
                pages = context.pages
                page = pages[0] if pages else await context.new_page()

                # Navigate to the exact URL
                logger.info(f"Navigating to: {url}")
                response = await page.goto(url, wait_until="networkidle", timeout=15000)

                if not response or response.status >= 400:
                    logger.warning(f"Page not accessible: {url} (status: {response.status if response else 'None'})")
                    await browser.close()
                    return []

                logger.info(f"Successfully loaded: {url}")

                # Wait for JS to render
                await page.wait_for_timeout(3000)

                # Extract team members
                team_cards = await page.query_selector_all(
                    'div[class*="team"], div[class*="member"], '
                    'div[class*="person"], article[class*="team"], '
                    'section[class*="team"], div[class*="staff"], '
                    'div[class*="leadership"], div[class*="executive"]'
                )

                for card in team_cards:
                    try:
                        name_element = await card.query_selector(
                            'h2, h3, h4, strong, [class*="name"], [class*="Name"]'
                        )
                        name = await name_element.inner_text() if name_element else None

                        title_element = await card.query_selector(
                            'p, span[class*="title"], div[class*="role"], '
                            '[class*="position"], [class*="job"]'
                        )
                        title = await title_element.inner_text() if title_element else None

                        # Try standard mailto: links first
                        email_element = await card.query_selector('a[href^="mailto:"]')
                        email = None
                        if email_element:
                            href = await email_element.get_attribute('href')
                            email = href.replace('mailto:', '') if href else None

                        # Try Cloudflare-protected emails if no mailto found
                        if not email:
                            cf_email_element = await card.query_selector('[data-cfemail]')
                            if cf_email_element:
                                cf_encoded = await cf_email_element.get_attribute('data-cfemail')
                                if cf_encoded:
                                    email = decode_cloudflare_email(cf_encoded)
                                    if email:
                                        logger.debug(f"Decoded Cloudflare email: {email}")

                        # Clean using shared utilities
                        if name:
                            name = name.strip()
                            fixed_name, extracted_title = split_concatenated_name(name)
                            if extracted_title:
                                name = fixed_name
                                if not title:
                                    title = extracted_title

                        if title:
                            title = clean_title(title.strip())

                        if is_garbage_name(name):
                            continue

                        if name and title and is_atl_title(title):
                            contacts.append({
                                "name": name,
                                "title": title,
                                "email": email
                            })
                            logger.info(f"Found ATL contact: {name} ({title})")

                    except Exception as card_error:
                        logger.debug(f"Error extracting card: {card_error}")

                # Fallback: Extract emails from entire page if no team card contacts found
                if not contacts:
                    logger.debug("No team cards found, scanning entire page for emails")
                    seen_emails = set()

                    # Method 1: Standard mailto links
                    mailto_links = await page.query_selector_all('a[href^="mailto:"]')
                    for mailto_el in mailto_links:
                        try:
                            href = await mailto_el.get_attribute('href')
                            if href:
                                email = href.replace('mailto:', '').split('?')[0].strip().lower()
                                if email and '@' in email and email not in seen_emails:
                                    # Filter out generic/info emails for ATL, but still capture
                                    seen_emails.add(email)
                                    contacts.append({
                                        "name": None,
                                        "title": None,
                                        "email": email,
                                        "source": "page_mailto_scan"
                                    })
                                    logger.info(f"Found mailto email on page: {email}")
                        except Exception as mail_err:
                            logger.debug(f"Error extracting mailto: {mail_err}")

                    # Method 2: Cloudflare-encoded emails (if JS didn't decode them)
                    cf_email_elements = await page.query_selector_all('[data-cfemail]')
                    for cf_el in cf_email_elements:
                        try:
                            cf_encoded = await cf_el.get_attribute('data-cfemail')
                            if cf_encoded:
                                decoded_email = decode_cloudflare_email(cf_encoded)
                                if decoded_email and decoded_email not in seen_emails:
                                    seen_emails.add(decoded_email)
                                    contacts.append({
                                        "name": None,
                                        "title": None,
                                        "email": decoded_email,
                                        "source": "cloudflare_page_scan"
                                    })
                                    logger.info(f"Found Cloudflare email on page: {decoded_email}")
                        except Exception as cf_err:
                            logger.debug(f"Error extracting CF email: {cf_err}")

                await browser.close()
                return contacts

        except Exception as e:
            logger.error(f"Browserbase single URL scraping failed: {e}", exc_info=True)
            return []

    async def _create_session(self) -> tuple:
        """
        Create a new Browserbase browser session.

        Returns:
            Tuple of (session_id, connect_url)
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/sessions",
                headers={
                    "x-bb-api-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "projectId": self.project_id
                }
            )

            response.raise_for_status()
            data = response.json()
            session_id = data["id"]
            connect_url = data.get("connectUrl")
            if not connect_url:
                # SECURITY: Never construct URL with API key - it would appear in logs
                raise ValueError(f"Browserbase API did not return connectUrl for session {session_id[:8]}...")

            logger.info(f"Browserbase session created: {session_id[:8]}...")
            return session_id, connect_url

    async def _scrape_with_session(
        self,
        session_id: str,
        website_url: str,
        connect_url: str
    ) -> List[Dict[str, str]]:
        """
        Use Browserbase session to scrape team page via Playwright.

        Connects to Browserbase CDP endpoint and navigates to team/about pages.
        """
        from playwright.async_api import async_playwright

        contacts = []

        try:
            # Use shared TEAM_PAGE_PATTERNS from scraper_patterns.py
            # Prioritize first 10 most common patterns for efficiency
            team_paths = TEAM_PAGE_PATTERNS[:10]

            async with async_playwright() as p:
                # Connect to Browserbase session via CDP using the API-provided connect URL
                logger.info(f"Connecting to Browserbase session: {session_id}")
                browser = await p.chromium.connect_over_cdp(connect_url)

                # Get default context and page
                contexts = browser.contexts
                if not contexts:
                    logger.error("No browser contexts available")
                    return []

                context = contexts[0]
                pages = context.pages

                if not pages:
                    page = await context.new_page()
                else:
                    page = pages[0]

                # Try each team page path
                # Smart early exit: stop after 2 successful page loads with no team cards
                # Most sites that have team info will have it on /about-us or /about
                successful_loads_without_contacts = 0
                MAX_EMPTY_PAGES = 2  # Stop after 2 pages load but have no team content

                for team_path in team_paths:
                    try:
                        # Construct full URL
                        base_url = website_url.rstrip('/')
                        team_url = f"{base_url}{team_path}"

                        logger.info(f"Navigating to: {team_url}")

                        # Navigate to team page
                        # Reduced timeout from 15s to 8s - most pages load in <5s
                        response = await page.goto(team_url, wait_until="networkidle", timeout=8000)

                        # Check if page loaded successfully
                        if not response or response.status >= 400:
                            logger.info(f"Team page not found: {team_url} (status: {response.status if response else 'None'})")
                            continue

                        logger.info(f"Successfully loaded team page: {team_url}")

                        # Wait for content to render (JavaScript pages need time)
                        await page.wait_for_timeout(2000)

                        # Extract team members using multiple selectors
                        # Pattern 1: Common team member cards
                        team_cards = await page.query_selector_all(
                            'div[class*="team"], div[class*="member"], '
                            'div[class*="person"], article[class*="team"], '
                            'section[class*="team"], div[class*="staff"], '
                            'div[class*="leadership"], div[class*="executive"]'
                        )

                        for card in team_cards:
                            try:
                                # Extract name (usually in h2, h3, h4, or strong tags)
                                name_element = await card.query_selector(
                                    'h2, h3, h4, strong, [class*="name"], [class*="Name"]'
                                )
                                name = await name_element.inner_text() if name_element else None

                                # Extract title/role
                                title_element = await card.query_selector(
                                    'p, span[class*="title"], div[class*="role"], '
                                    '[class*="position"], [class*="job"]'
                                )
                                title = await title_element.inner_text() if title_element else None

                                # Extract email if available
                                email_element = await card.query_selector('a[href^="mailto:"]')
                                email = None
                                if email_element:
                                    href = await email_element.get_attribute('href')
                                    email = href.replace('mailto:', '') if href else None

                                # Clean name and title using shared utilities
                                if name:
                                    name = name.strip()
                                    # Check for concatenated name+title
                                    fixed_name, extracted_title = split_concatenated_name(name)
                                    if extracted_title:
                                        name = fixed_name
                                        if not title:
                                            title = extracted_title

                                if title:
                                    title = clean_title(title.strip())

                                # Validate: skip garbage names
                                if is_garbage_name(name):
                                    logger.debug(f"Skipping garbage name: {name}")
                                    continue

                                # Validate and filter for ATL titles using shared utility
                                if name and title and is_atl_title(title):
                                    contacts.append({
                                        "name": name,
                                        "title": title,
                                        "email": email
                                    })
                                    logger.info(f"Found ATL contact: {name} ({title})")

                            except Exception as card_error:
                                logger.debug(f"Error extracting card data: {card_error}")
                                continue

                        # If we found contacts, stop searching
                        if contacts:
                            logger.info(f"Found {len(contacts)} ATL contacts on {team_url}")
                            break
                        else:
                            # Page loaded but no team cards - count it
                            successful_loads_without_contacts += 1
                            if successful_loads_without_contacts >= MAX_EMPTY_PAGES:
                                logger.info(
                                    f"Early exit: {successful_loads_without_contacts} pages loaded "
                                    f"without team cards - site likely has no team page"
                                )
                                break

                    except Exception as nav_error:
                        logger.debug(f"Failed to load {team_url}: {nav_error}")
                        continue

                # Close browser connection
                await browser.close()

                return contacts

        except Exception as e:
            logger.error(f"Browserbase Playwright scraping failed: {e}", exc_info=True)
            return []

    async def _close_session(self, session_id: str):
        """Close Browserbase session."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sessions/{session_id}/stop",
                    headers={
                        "x-bb-api-key": self.api_key
                    }
                )
                response.raise_for_status()
                logger.info(f"Browserbase session closed: {session_id}")
        except Exception as e:
            logger.error(f"Failed to close Browserbase session {session_id}: {e}")


# Singleton instance
_browserbase_scraper: Optional[BrowserbaseTeamScraper] = None


async def get_browserbase_team_scraper() -> BrowserbaseTeamScraper:
    """Get or create Browserbase team scraper singleton."""
    global _browserbase_scraper
    if _browserbase_scraper is None:
        _browserbase_scraper = BrowserbaseTeamScraper()
    return _browserbase_scraper
