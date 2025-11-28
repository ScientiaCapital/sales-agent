"""
Browserbase Team Scraper Service

Uses Browserbase browser automation to scrape team/about pages from JavaScript-heavy websites.
This is a fallback for when BeautifulSoup fails (client-side rendered content).

Performance: ~10-15 seconds per scrape (browser automation overhead)
Cost: Browserbase session pricing (check https://browserbase.com/pricing)
"""

import os
import logging
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


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
    """

    # ATL title keywords for filtering
    ATL_TITLES = [
        "ceo", "chief executive",
        "cto", "chief technology",
        "cfo", "chief financial",
        "coo", "chief operating",
        "president", "vp", "vice president",
        "founder", "co-founder", "owner",
        "director", "head of",
        "partner", "managing director"
    ]

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
        if not self.api_key or not self.project_id:
            logger.error("Browserbase not configured - cannot scrape")
            return []

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
            connect_url = data.get("connectUrl", f"wss://connect.browserbase.com?sessionId={session_id}&apiKey={self.api_key}")

            logger.info(f"Browserbase session created: {session_id}")
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
            # Team page paths to try
            team_paths = [
                "/team", "/about/team", "/our-team", "/leadership",
                "/about-us", "/about", "/company/team", "/people"
            ]

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
                for team_path in team_paths:
                    try:
                        # Construct full URL
                        base_url = website_url.rstrip('/')
                        team_url = f"{base_url}{team_path}"

                        logger.info(f"Navigating to: {team_url}")

                        # Navigate to team page
                        response = await page.goto(team_url, wait_until="networkidle", timeout=15000)

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
                            'section[class*="team"]'
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

                                # Validate and filter for ATL titles
                                if name and title and self._is_atl_title(title):
                                    contacts.append({
                                        "name": name.strip(),
                                        "title": title.strip(),
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

    def _is_atl_title(self, title: str) -> bool:
        """Check if title is Above The Line."""
        if not title:
            return False

        title_lower = title.lower()
        return any(keyword in title_lower for keyword in self.ATL_TITLES)


# Singleton instance
_browserbase_scraper: Optional[BrowserbaseTeamScraper] = None


async def get_browserbase_team_scraper() -> BrowserbaseTeamScraper:
    """Get or create Browserbase team scraper singleton."""
    global _browserbase_scraper
    if _browserbase_scraper is None:
        _browserbase_scraper = BrowserbaseTeamScraper()
    return _browserbase_scraper
