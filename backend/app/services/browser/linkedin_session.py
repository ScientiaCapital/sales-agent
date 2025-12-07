"""LinkedIn session manager with persistent authentication."""

import logging
from typing import Optional
from datetime import datetime, timedelta

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from .browserbase_client import BrowserbaseClient

logger = logging.getLogger(__name__)


class LinkedInSessionManager:
    """
    Manages LinkedIn authentication and session persistence.

    Features:
    - Persistent login (stays authenticated between runs)
    - Session validation
    - Rate limit tracking
    """

    CONTEXT_NAME = "linkedin-session"

    def __init__(self, browserbase_client: BrowserbaseClient):
        self.client = browserbase_client
        self._is_authenticated = False
        self._last_activity: Optional[datetime] = None

    async def ensure_authenticated(self) -> Page:
        """
        Ensure we have an authenticated LinkedIn session.

        Returns:
            Page instance with active LinkedIn session
        """
        page = await self.client.new_page(
            context_name=self.CONTEXT_NAME,
            persist=True,
        )

        # Check if already logged in
        if await self._check_authentication(page):
            logger.info("LinkedIn session already authenticated")
            self._is_authenticated = True
            return page

        # Need to login
        logger.warning("LinkedIn session not authenticated - manual login required")
        logger.warning("Please login manually and save the session")

        await page.goto("https://www.linkedin.com/login")

        # Wait for manual login (in production, use credentials or OAuth)
        logger.info("Waiting for manual login... (60 seconds)")
        try:
            # Wait for navigation to feed (indicates successful login)
            await page.wait_for_url("**/feed/**", timeout=60000)
            self._is_authenticated = True

            # Save session state
            await self.client.save_context_state(self.CONTEXT_NAME)
            logger.info("LinkedIn session authenticated and saved")
        except PlaywrightTimeout:
            logger.error("Login timeout - authentication failed")
            raise Exception("LinkedIn authentication failed")

        return page

    async def _check_authentication(self, page: Page) -> bool:
        """Check if the current session is authenticated."""
        try:
            # Navigate to LinkedIn homepage
            await page.goto("https://www.linkedin.com", timeout=10000)

            # Wait a bit for redirects
            await self.client.realistic_delay(1000, 2000)

            # Check if we're on feed (logged in) or login page
            current_url = page.url

            if "/feed" in current_url or "/in/" in current_url:
                logger.debug("LinkedIn session is authenticated")
                return True

            if "/login" in current_url or "/uas/login" in current_url:
                logger.debug("LinkedIn session needs authentication")
                return False

            # Ambiguous - check for profile link
            profile_link = await page.query_selector('a[href*="/in/"]')
            return profile_link is not None

        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return False

    async def navigate_to_profile(self, page: Page, profile_url: str):
        """Navigate to a LinkedIn profile with realistic behavior."""
        logger.info(f"Navigating to profile: {profile_url}")

        await page.goto(profile_url, wait_until="domcontentloaded")
        await self.client.realistic_delay(1000, 2500)

        # Record activity
        self._last_activity = datetime.utcnow()

    async def is_rate_limited(self) -> bool:
        """
        Check if we should pause due to rate limiting.

        LinkedIn is aggressive - be conservative.
        """
        if not self._last_activity:
            return False

        # Enforce minimum 3 seconds between actions
        elapsed = (datetime.utcnow() - self._last_activity).total_seconds()
        if elapsed < 3:
            logger.warning(f"Rate limit: waiting {3 - elapsed:.1f}s")
            return True

        return False

    async def wait_if_rate_limited(self):
        """Wait if we're rate limited."""
        if not self._last_activity:
            return

        elapsed = (datetime.utcnow() - self._last_activity).total_seconds()
        if elapsed < 3:
            wait_time = 3 - elapsed
            logger.debug(f"Rate limit wait: {wait_time:.1f}s")
            import asyncio
            await asyncio.sleep(wait_time)

    async def close_session(self):
        """Close the LinkedIn session and save state."""
        await self.client.save_context_state(self.CONTEXT_NAME)
        logger.info("LinkedIn session closed and state saved")
