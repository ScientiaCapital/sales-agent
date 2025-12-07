"""Browserbase cloud browser client with Playwright integration."""

import asyncio
import os
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserbaseClient:
    """
    Cloud browser automation via Browserbase + Playwright.

    Features:
    - Persistent authentication contexts (stays logged into LinkedIn)
    - Stealth mode to avoid bot detection
    - Accessibility tree navigation (no VLM needed)
    - Realistic delays and user simulation
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        stealth: bool = True,
    ):
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.stealth = stealth

        if not self.api_key:
            raise ValueError("BROWSERBASE_API_KEY not found in environment")

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def initialize(self):
        """Initialize Playwright and browser connection."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

            # Connect to Browserbase cloud browser
            connect_url = self._get_connect_url()
            self._browser = await self._playwright.chromium.connect_over_cdp(connect_url)

            logger.info(f"Connected to Browserbase browser (stealth={self.stealth})")

    async def close(self):
        """Close all contexts and browser connection."""
        for context in self._contexts.values():
            await context.close()
        self._contexts.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _get_connect_url(self) -> str:
        """Build Browserbase WebSocket connection URL."""
        base_url = "wss://connect.browserbase.com"
        params = [
            f"apiKey={self.api_key}",
        ]

        if self.project_id:
            params.append(f"projectId={self.project_id}")

        if self.stealth:
            params.append("enableProxy=true")
            params.append("advancedStealth=true")

        return f"{base_url}?{'&'.join(params)}"

    async def get_or_create_context(
        self,
        context_name: str = "default",
        persist: bool = True,
    ) -> BrowserContext:
        """
        Get or create a persistent browser context.

        Args:
            context_name: Unique name for this context (e.g., "linkedin-session")
            persist: Whether to persist cookies/storage between sessions

        Returns:
            Browser context (maintains login state if persist=True)
        """
        if context_name in self._contexts:
            return self._contexts[context_name]

        if not self._browser:
            await self.initialize()

        # Create new context with persistence
        context_options = {
            "accept_downloads": True,
            "user_agent": self._get_realistic_user_agent(),
        }

        if persist:
            # Store context data in persistent storage
            storage_path = f".browserbase_storage/{context_name}"
            os.makedirs(storage_path, exist_ok=True)
            context_options["storage_state"] = f"{storage_path}/state.json"

        context = await self._browser.new_context(**context_options)
        self._contexts[context_name] = context

        logger.info(f"Created browser context: {context_name} (persist={persist})")
        return context

    async def new_page(
        self,
        context_name: str = "default",
        persist: bool = True,
    ) -> Page:
        """
        Create a new page in the specified context.

        Args:
            context_name: Name of the browser context
            persist: Whether this context should persist

        Returns:
            New page instance
        """
        context = await self.get_or_create_context(context_name, persist)
        page = await context.new_page()

        # Add realistic viewport
        await page.set_viewport_size({"width": 1920, "height": 1080})

        return page

    async def realistic_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Add realistic human-like delay."""
        import random
        delay_ms = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay_ms / 1000)

    def _get_realistic_user_agent(self) -> str:
        """Get realistic user agent string."""
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def save_context_state(self, context_name: str = "default"):
        """Manually save context state (cookies, localStorage, etc)."""
        if context_name not in self._contexts:
            logger.warning(f"Context {context_name} not found, cannot save state")
            return

        context = self._contexts[context_name]
        storage_path = f".browserbase_storage/{context_name}"
        os.makedirs(storage_path, exist_ok=True)

        state = await context.storage_state()
        import json
        with open(f"{storage_path}/state.json", "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved context state: {context_name}")

    async def get_accessibility_snapshot(self, page: Page) -> Dict[str, Any]:
        """
        Get accessibility tree snapshot for AI navigation.

        This provides structured element references without needing VLM.
        """
        snapshot = await page.accessibility.snapshot()
        return snapshot or {}
