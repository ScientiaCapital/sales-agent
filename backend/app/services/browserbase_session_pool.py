"""
Browserbase Session Pool - Managed pool of persistent browser sessions for LinkedIn scraping

CRITICAL: This pool implements anti-detection measures for LinkedIn scraping.
- Uses Browserbase's US residential proxies + CAPTCHA solving (Max plan)
- Note: advancedStealth requires Enterprise plan - we use proxies instead
- Maintains session reuse to reduce session creation overhead (7-15 seconds per session)
- Rotates sessions after max_uses to avoid detection patterns
- Thread-safe async queue for concurrent access

Architecture:
    1. Session Pool: Pre-warmed browser sessions ready for use
    2. Checkout/Checkin: Borrow and return sessions (like connection pooling)
    3. Auto-rotation: Sessions expire after max_uses or timeout
    4. Graceful cleanup: All sessions closed on shutdown

Usage:
    pool = await get_session_pool()

    # Get a session
    session = await pool.checkout()

    try:
        # Use session.connect_url with Playwright
        browser = await playwright.chromium.connect_over_cdp(session.connect_url)
        # ... scrape LinkedIn ...
    finally:
        # Return session to pool
        await pool.checkin(session)

Environment Variables:
    BROWSERBASE_API_KEY - API key for Browserbase
    BROWSERBASE_PROJECT_ID - Project ID for session creation
    LINKEDIN_COMPANY_MAX_SESSIONS - Max concurrent sessions (default: 25)
    LINKEDIN_SESSION_TIMEOUT_SEC - Session lifetime in seconds (default: 7200)
    LINKEDIN_SESSION_MAX_USES - Max companies per session (default: 15)
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
import httpx

# Load .env from project root
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

logger = logging.getLogger(__name__)


@dataclass
class BrowserbaseSession:
    """
    Represents a single Browserbase browser session.

    Attributes:
        session_id: Unique session ID from Browserbase API
        connect_url: WebSocket URL for Playwright CDP connection
        created_at: Timestamp when session was created
        usage_count: Number of companies scraped with this session
        last_used_at: Timestamp of last usage
        is_active: Whether session is currently in use
    """

    session_id: str
    connect_url: str
    created_at: float = field(default_factory=time.time)
    usage_count: int = 0
    last_used_at: float = field(default_factory=time.time)
    is_active: bool = False

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has exceeded timeout."""
        age = time.time() - self.created_at
        return age > timeout_seconds

    def should_rotate(self, max_uses: int) -> bool:
        """Check if session should be rotated (max uses reached)."""
        return self.usage_count >= max_uses

    def __repr__(self) -> str:
        age_minutes = int((time.time() - self.created_at) / 60)
        return (
            f"BrowserbaseSession(id={self.session_id[:8]}..., "
            f"uses={self.usage_count}, age={age_minutes}m, active={self.is_active})"
        )


class BrowserbaseSessionPool:
    """
    Thread-safe pool of Browserbase browser sessions with stealth mode.

    Key Features:
        - Pre-warmed sessions ready for immediate use
        - Automatic session rotation after max_uses
        - Timeout-based session expiration
        - Concurrent access control with semaphore
        - Graceful cleanup on shutdown

    LinkedIn Stealth Configuration:
        - advancedStealth: True (bypasses bot detection)
        - blockAds: True (faster page loads)
        - solveCaptchas: True (automatic CAPTCHA solving)
        - fingerprint: Randomized browser fingerprints
        - proxies: US residential proxies (California)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        max_sessions: int = 25,
        session_timeout_sec: int = 7200,
        session_max_uses: int = 15,
    ):
        """
        Initialize session pool.

        Args:
            api_key: Browserbase API key (defaults to BROWSERBASE_API_KEY env var)
            project_id: Browserbase project ID (defaults to BROWSERBASE_PROJECT_ID env var)
            max_sessions: Maximum concurrent sessions (default: 25)
            session_timeout_sec: Session lifetime in seconds (default: 7200 = 2 hours)
            session_max_uses: Max companies per session before rotation (default: 15)
        """
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.base_url = "https://api.browserbase.com/v1"

        if not self.api_key or not self.project_id:
            raise ValueError(
                "Browserbase credentials required. Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID"
            )

        # Pool configuration
        self.max_sessions = int(os.getenv("LINKEDIN_COMPANY_MAX_SESSIONS", max_sessions))
        self.session_timeout_sec = int(
            os.getenv("LINKEDIN_SESSION_TIMEOUT_SEC", session_timeout_sec)
        )
        self.session_max_uses = int(
            os.getenv("LINKEDIN_SESSION_MAX_USES", session_max_uses)
        )

        # Session tracking
        self._sessions: Dict[str, BrowserbaseSession] = {}  # session_id -> session
        self._available_queue: asyncio.Queue = asyncio.Queue()  # Available sessions
        self._semaphore = asyncio.Semaphore(self.max_sessions)  # Concurrency limit
        self._lock = asyncio.Lock()  # Thread-safe session management
        self._closed = False

        logger.info(
            f"BrowserbaseSessionPool initialized: "
            f"max_sessions={self.max_sessions}, "
            f"timeout={self.session_timeout_sec}s, "
            f"max_uses={self.session_max_uses}"
        )

    async def warm_up(self, count: int = 5) -> None:
        """
        Pre-create sessions for faster first requests.

        Args:
            count: Number of sessions to pre-create (default: 5)

        Note: Session creation takes ~7-15 seconds each. Consider warming up
        a small number initially and letting the pool grow on-demand.
        """
        if self._closed:
            raise RuntimeError("Session pool is closed")

        logger.info(f"Warming up session pool with {count} sessions...")
        start_time = time.time()

        tasks = [self._create_session() for _ in range(count)]
        sessions = await asyncio.gather(*tasks, return_exceptions=True)

        successful = 0
        for result in sessions:
            if isinstance(result, BrowserbaseSession):
                successful += 1
                await self._available_queue.put(result)
            else:
                logger.error(f"Warm-up session creation failed: {result}")

        elapsed = time.time() - start_time
        logger.info(
            f"Session pool warm-up complete: {successful}/{count} sessions "
            f"created in {elapsed:.1f}s"
        )

    async def checkout(self) -> BrowserbaseSession:
        """
        Get a session from the pool (blocking if none available).

        Returns:
            BrowserbaseSession ready for use

        Raises:
            RuntimeError: If pool is closed

        Note: Always checkin the session when done (use try/finally).
        """
        if self._closed:
            raise RuntimeError("Session pool is closed")

        # Wait for concurrency slot
        await self._semaphore.acquire()

        try:
            # Try to get existing session from queue (non-blocking)
            try:
                session = self._available_queue.get_nowait()

                # Check if session is expired or should rotate
                if session.is_expired(self.session_timeout_sec) or session.should_rotate(
                    self.session_max_uses
                ):
                    logger.info(f"Session expired/rotated: {session}")
                    await self._close_session(session.session_id)

                    # Create new session as replacement
                    session = await self._create_session()

            except asyncio.QueueEmpty:
                # No available sessions, create new one
                logger.info("No available sessions, creating new session...")
                session = await self._create_session()

            # Mark session as active
            async with self._lock:
                session.is_active = True
                session.last_used_at = time.time()
                self._sessions[session.session_id] = session

            logger.info(f"Session checked out: {session}")
            return session

        except Exception as e:
            # Release semaphore on error
            self._semaphore.release()
            raise e

    async def checkin(self, session: BrowserbaseSession) -> None:
        """
        Return a session to the pool.

        Args:
            session: Session to return

        Note: Automatically closes sessions that have exceeded max_uses or timeout.
        """
        if self._closed:
            logger.warning("Attempted checkin to closed pool, closing session")
            await self._close_session(session.session_id)
            self._semaphore.release()
            return

        async with self._lock:
            session.is_active = False
            session.usage_count += 1
            session.last_used_at = time.time()

            # Check if session should be retired
            if session.is_expired(self.session_timeout_sec) or session.should_rotate(
                self.session_max_uses
            ):
                logger.info(f"Retiring session: {session}")
                await self._close_session(session.session_id)
            else:
                # Return to pool for reuse
                await self._available_queue.put(session)
                logger.info(f"Session checked in: {session}")

        # Release concurrency slot
        self._semaphore.release()

    async def close_all(self) -> None:
        """
        Close all sessions and shutdown the pool.

        Call this on application shutdown to cleanup resources.
        """
        logger.info("Closing all Browserbase sessions...")
        self._closed = True

        async with self._lock:
            # Close all tracked sessions
            close_tasks = [
                self._close_session(session_id)
                for session_id in list(self._sessions.keys())
            ]
            await asyncio.gather(*close_tasks, return_exceptions=True)

            # Clear pool state
            self._sessions.clear()
            while not self._available_queue.empty():
                try:
                    self._available_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        logger.info(f"Session pool closed (max_sessions={self.max_sessions})")

    async def get_pool_stats(self) -> Dict[str, any]:
        """
        Get current pool statistics.

        Returns:
            Dict with pool metrics (total, active, available, etc.)
        """
        async with self._lock:
            total_sessions = len(self._sessions)
            active_sessions = sum(1 for s in self._sessions.values() if s.is_active)
            available_sessions = self._available_queue.qsize()

            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "available_sessions": available_sessions,
                "max_sessions": self.max_sessions,
                "pool_utilization": (
                    f"{(active_sessions / self.max_sessions * 100):.1f}%"
                    if self.max_sessions > 0
                    else "0%"
                ),
                "session_timeout_sec": self.session_timeout_sec,
                "session_max_uses": self.session_max_uses,
            }

    async def _create_session(self, retries: int = 3) -> BrowserbaseSession:
        """
        Create a new Browserbase session with stealth configuration.

        Args:
            retries: Number of retry attempts on failure (default: 3)

        Returns:
            BrowserbaseSession ready for use

        Raises:
            Exception: If session creation fails after all retries
        """
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Creating Browserbase session (attempt {attempt}/{retries})...")

                # Stealth session configuration for LinkedIn scraping
                # Based on Browserbase API docs (Dec 2024):
                # - timeout: 60-21600 seconds (NOT milliseconds)
                # - browserSettings: advancedStealth requires Enterprise plan
                # - fingerprint/viewport: auto-generated, not configurable
                # - proxies: boolean true OR array with geolocation (works on all plans)
                #
                # NOTE: advancedStealth is ENTERPRISE ONLY - we use proxies + solveCaptchas instead
                session_config = {
                    "projectId": self.project_id,
                    "timeout": min(self.session_timeout_sec, 21600),  # Max 6 hours (seconds)
                    "keepAlive": True,
                    "browserSettings": {
                        # Automatic CAPTCHA solving (available on all paid plans)
                        "solveCaptchas": True,
                    },
                    # US residential proxies with geolocation (works on Max plan)
                    # This provides IP rotation which helps with LinkedIn detection
                    "proxies": [
                        {
                            "type": "browserbase",
                            "geolocation": {"country": "US", "state": "CA"},
                        }
                    ],
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/sessions",
                        headers={
                            "x-bb-api-key": self.api_key,
                            "Content-Type": "application/json",
                        },
                        json=session_config,
                    )

                    response.raise_for_status()
                    data = response.json()

                    session_id = data["id"]
                    connect_url = data.get("connectUrl")
                    if not connect_url:
                        # SECURITY: Never construct URL with API key - it would appear in logs
                        raise ValueError(
                            f"Browserbase API did not return connectUrl for session {session_id[:8]}..."
                        )

                    session = BrowserbaseSession(
                        session_id=session_id, connect_url=connect_url
                    )

                    logger.info(f"Browserbase session created: {session}")
                    return session

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Session creation attempt {attempt}/{retries} failed: {e}"
                )

                if attempt < retries:
                    # Exponential backoff
                    wait_time = 2**attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)

        # All retries failed
        raise Exception(f"Failed to create Browserbase session after {retries} attempts: {last_error}")

    async def _close_session(self, session_id: str) -> None:
        """
        Close a Browserbase session.

        Args:
            session_id: Session ID to close
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sessions/{session_id}/stop",
                    headers={"x-bb-api-key": self.api_key},
                )
                response.raise_for_status()
                logger.info(f"Browserbase session closed: {session_id[:8]}...")

            # Remove from tracking
            async with self._lock:
                self._sessions.pop(session_id, None)

        except Exception as e:
            logger.error(f"Failed to close Browserbase session {session_id[:8]}...: {e}")


# Singleton instance
_session_pool: Optional[BrowserbaseSessionPool] = None
_pool_lock = asyncio.Lock()


async def get_session_pool() -> BrowserbaseSessionPool:
    """
    Get or create the global Browserbase session pool singleton.

    Returns:
        BrowserbaseSessionPool instance

    Note: Pool is created lazily on first access.
    """
    global _session_pool

    if _session_pool is None:
        async with _pool_lock:
            # Double-check after acquiring lock
            if _session_pool is None:
                _session_pool = BrowserbaseSessionPool()
                logger.info("Global BrowserbaseSessionPool initialized")

    return _session_pool


async def close_session_pool() -> None:
    """
    Close the global session pool.

    Call this on application shutdown to cleanup resources.
    """
    global _session_pool

    if _session_pool is not None:
        await _session_pool.close_all()
        _session_pool = None
        logger.info("Global BrowserbaseSessionPool closed")
