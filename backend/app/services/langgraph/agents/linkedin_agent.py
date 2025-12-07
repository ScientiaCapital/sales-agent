"""LinkedInAgent - Social selling automation via Browserbase + Playwright."""

import logging
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from ...browser.browserbase_client import BrowserbaseClient
from ...browser.linkedin_session import LinkedInSessionManager

logger = logging.getLogger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class ConnectionResult(BaseModel):
    """Result of a LinkedIn connection request."""

    success: bool
    profile_url: str
    message: str
    note_sent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    already_connected: bool = False


class MessageResult(BaseModel):
    """Result of a LinkedIn message."""

    success: bool
    profile_url: str
    message_content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class ReactionResult(BaseModel):
    """Result of a LinkedIn post reaction."""

    success: bool
    post_url: str
    reaction_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class CommentResult(BaseModel):
    """Result of a LinkedIn post comment."""

    success: bool
    post_url: str
    comment_text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class ProfileData(BaseModel):
    """Extracted LinkedIn profile data."""

    profile_url: str
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    current_company: Optional[str] = None
    current_title: Optional[str] = None
    connections: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Rate Limiting
# ============================================================================


class LinkedInRateLimiter:
    """
    Conservative rate limiting for LinkedIn to avoid bans.

    LinkedIn is VERY aggressive with bot detection - err on safe side.
    """

    DAILY_LIMITS = {
        "connections": 10,  # Very conservative
        "messages": 25,
        "profile_views": 50,
        "reactions": 30,
        "comments": 20,
    }

    def __init__(self):
        self._daily_counts: Dict[str, int] = {}
        self._reset_date: Optional[datetime] = None
        self._last_action_times: Dict[str, datetime] = {}

    def _check_daily_reset(self):
        """Reset daily counters if it's a new day."""
        now = datetime.utcnow()
        if not self._reset_date or now.date() > self._reset_date.date():
            self._daily_counts = {}
            self._reset_date = now
            logger.info("LinkedIn rate limiter: Daily counters reset")

    def can_perform_action(self, action_type: str) -> tuple[bool, Optional[str]]:
        """
        Check if we can perform this action type.

        Returns:
            (allowed, reason_if_not_allowed)
        """
        self._check_daily_reset()

        # Check daily limit
        current_count = self._daily_counts.get(action_type, 0)
        limit = self.DAILY_LIMITS.get(action_type, 100)

        if current_count >= limit:
            return False, f"Daily limit reached: {current_count}/{limit} {action_type}"

        # Check minimum time between actions (2-5 seconds)
        if action_type in self._last_action_times:
            last_time = self._last_action_times[action_type]
            elapsed = (datetime.utcnow() - last_time).total_seconds()

            min_delay = 2.0
            if elapsed < min_delay:
                return False, f"Too soon: wait {min_delay - elapsed:.1f}s"

        return True, None

    def record_action(self, action_type: str):
        """Record that an action was performed."""
        self._check_daily_reset()
        self._daily_counts[action_type] = self._daily_counts.get(action_type, 0) + 1
        self._last_action_times[action_type] = datetime.utcnow()

        count = self._daily_counts[action_type]
        limit = self.DAILY_LIMITS.get(action_type, 100)
        logger.info(f"LinkedIn action recorded: {action_type} ({count}/{limit} today)")

    def get_remaining(self, action_type: str) -> int:
        """Get remaining actions for today."""
        self._check_daily_reset()
        count = self._daily_counts.get(action_type, 0)
        limit = self.DAILY_LIMITS.get(action_type, 100)
        return max(0, limit - count)


# ============================================================================
# LinkedInAgent
# ============================================================================


class LinkedInAgent:
    """
    Social selling automation via Browserbase + Playwright.

    Features:
    - Send connection requests with personalized notes
    - Send direct messages to 1st-degree connections
    - React to posts (like, celebrate, support, etc)
    - Comment on posts
    - Scrape profile data using accessibility tree

    Safety:
    - Conservative rate limiting (10 connections/day max)
    - Realistic delays between actions (2-5 seconds)
    - Stealth mode to avoid bot detection
    - Persistent session (stays logged in)
    """

    def __init__(
        self,
        browserbase_client: Optional[BrowserbaseClient] = None,
    ):
        self.client = browserbase_client or BrowserbaseClient(stealth=True)
        self.session = LinkedInSessionManager(self.client)
        self.rate_limiter = LinkedInRateLimiter()

    async def __aenter__(self):
        """Async context manager."""
        await self.client.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.session.close_session()
        await self.client.close()

    # ========================================================================
    # Connection Requests
    # ========================================================================

    async def send_connection_request(
        self,
        profile_url: str,
        note: Optional[str] = None,
    ) -> ConnectionResult:
        """
        Send LinkedIn connection request with optional note.

        Args:
            profile_url: Full LinkedIn profile URL
            note: Optional personalized note (max 300 chars)

        Returns:
            ConnectionResult with success status
        """
        # Check rate limit
        allowed, reason = self.rate_limiter.can_perform_action("connections")
        if not allowed:
            return ConnectionResult(
                success=False,
                profile_url=profile_url,
                message=f"Rate limit: {reason}",
            )

        try:
            # Get authenticated page
            page = await self.session.ensure_authenticated()
            await self.session.wait_if_rate_limited()

            # Navigate to profile
            await self.session.navigate_to_profile(page, profile_url)

            # Look for Connect button
            connect_btn = await page.get_by_role("button", name="Connect").first

            if not connect_btn:
                # Check if already connected
                message_btn = await page.get_by_role("button", name="Message").first
                if message_btn:
                    return ConnectionResult(
                        success=True,
                        profile_url=profile_url,
                        message="Already connected",
                        already_connected=True,
                    )

                return ConnectionResult(
                    success=False,
                    profile_url=profile_url,
                    message="Connect button not found",
                )

            # Click Connect
            await connect_btn.click()
            await self.client.realistic_delay(500, 1000)

            # Add note if provided
            note_sent = None
            if note:
                # Look for "Add a note" button
                add_note_btn = await page.get_by_role("button", name="Add a note")
                if add_note_btn:
                    await add_note_btn.click()
                    await self.client.realistic_delay(300, 700)

                    # Type note (max 300 chars)
                    note_field = await page.get_by_label("Add a note")
                    if note_field:
                        note_trimmed = note[:300]
                        await note_field.fill(note_trimmed)
                        note_sent = note_trimmed
                        await self.client.realistic_delay(500, 1000)

            # Click Send
            send_btn = await page.get_by_role("button", name="Send")
            if send_btn:
                await send_btn.click()
                await self.client.realistic_delay(1000, 2000)

            # Record action
            self.rate_limiter.record_action("connections")

            return ConnectionResult(
                success=True,
                profile_url=profile_url,
                message="Connection request sent",
                note_sent=note_sent,
            )

        except Exception as e:
            logger.error(f"Connection request failed for {profile_url}: {e}")
            return ConnectionResult(
                success=False,
                profile_url=profile_url,
                message=f"Error: {str(e)}",
            )

    # ========================================================================
    # Messaging
    # ========================================================================

    async def send_message(
        self,
        profile_url: str,
        message: str,
    ) -> MessageResult:
        """
        Send direct message to 1st-degree connection.

        Args:
            profile_url: LinkedIn profile URL
            message: Message content

        Returns:
            MessageResult with success status
        """
        # Check rate limit
        allowed, reason = self.rate_limiter.can_perform_action("messages")
        if not allowed:
            return MessageResult(
                success=False,
                profile_url=profile_url,
                message_content=message,
                error=f"Rate limit: {reason}",
            )

        try:
            # Get authenticated page
            page = await self.session.ensure_authenticated()
            await self.session.wait_if_rate_limited()

            # Navigate to profile
            await self.session.navigate_to_profile(page, profile_url)

            # Click Message button
            message_btn = await page.get_by_role("button", name="Message").first
            if not message_btn:
                return MessageResult(
                    success=False,
                    profile_url=profile_url,
                    message_content=message,
                    error="Not connected - cannot message",
                )

            await message_btn.click()
            await self.client.realistic_delay(500, 1500)

            # Type message
            message_field = await page.get_by_role("textbox", name="Write a message")
            if not message_field:
                return MessageResult(
                    success=False,
                    profile_url=profile_url,
                    message_content=message,
                    error="Message field not found",
                )

            await message_field.fill(message)
            await self.client.realistic_delay(500, 1000)

            # Send
            send_btn = await page.get_by_role("button", name="Send")
            if send_btn:
                await send_btn.click()
                await self.client.realistic_delay(1000, 2000)

            # Record action
            self.rate_limiter.record_action("messages")

            return MessageResult(
                success=True,
                profile_url=profile_url,
                message_content=message,
            )

        except Exception as e:
            logger.error(f"Message send failed for {profile_url}: {e}")
            return MessageResult(
                success=False,
                profile_url=profile_url,
                message_content=message,
                error=str(e),
            )

    # ========================================================================
    # Post Interactions
    # ========================================================================

    async def react_to_post(
        self,
        post_url: str,
        reaction: Literal["like", "celebrate", "support", "love", "insightful", "curious"] = "like",
    ) -> ReactionResult:
        """
        React to a LinkedIn post.

        Args:
            post_url: Full LinkedIn post URL
            reaction: Reaction type

        Returns:
            ReactionResult with success status
        """
        # Check rate limit
        allowed, reason = self.rate_limiter.can_perform_action("reactions")
        if not allowed:
            return ReactionResult(
                success=False,
                post_url=post_url,
                reaction_type=reaction,
                error=f"Rate limit: {reason}",
            )

        try:
            page = await self.session.ensure_authenticated()
            await self.session.wait_if_rate_limited()

            # Navigate to post
            await page.goto(post_url)
            await self.client.realistic_delay(1000, 2000)

            # Find and click reaction button
            reaction_btn = await page.get_by_role("button", name=reaction.capitalize())

            if not reaction_btn:
                # Try generic like button
                like_btn = await page.get_by_role("button", name="Like")
                if like_btn:
                    await like_btn.click()
                else:
                    return ReactionResult(
                        success=False,
                        post_url=post_url,
                        reaction_type=reaction,
                        error="Reaction button not found",
                    )
            else:
                await reaction_btn.click()

            await self.client.realistic_delay(500, 1000)

            # Record action
            self.rate_limiter.record_action("reactions")

            return ReactionResult(
                success=True,
                post_url=post_url,
                reaction_type=reaction,
            )

        except Exception as e:
            logger.error(f"Post reaction failed for {post_url}: {e}")
            return ReactionResult(
                success=False,
                post_url=post_url,
                reaction_type=reaction,
                error=str(e),
            )

    async def comment_on_post(
        self,
        post_url: str,
        comment: str,
    ) -> CommentResult:
        """
        Add comment to LinkedIn post.

        Args:
            post_url: Full LinkedIn post URL
            comment: Comment text

        Returns:
            CommentResult with success status
        """
        # Check rate limit
        allowed, reason = self.rate_limiter.can_perform_action("comments")
        if not allowed:
            return CommentResult(
                success=False,
                post_url=post_url,
                comment_text=comment,
                error=f"Rate limit: {reason}",
            )

        try:
            page = await self.session.ensure_authenticated()
            await self.session.wait_if_rate_limited()

            # Navigate to post
            await page.goto(post_url)
            await self.client.realistic_delay(1000, 2000)

            # Find comment field
            comment_field = await page.get_by_role("textbox", name="Add a comment")
            if not comment_field:
                return CommentResult(
                    success=False,
                    post_url=post_url,
                    comment_text=comment,
                    error="Comment field not found",
                )

            # Click to focus
            await comment_field.click()
            await self.client.realistic_delay(300, 700)

            # Type comment
            await comment_field.fill(comment)
            await self.client.realistic_delay(500, 1000)

            # Post comment
            post_btn = await page.get_by_role("button", name="Post")
            if post_btn:
                await post_btn.click()
                await self.client.realistic_delay(1000, 2000)

            # Record action
            self.rate_limiter.record_action("comments")

            return CommentResult(
                success=True,
                post_url=post_url,
                comment_text=comment,
            )

        except Exception as e:
            logger.error(f"Post comment failed for {post_url}: {e}")
            return CommentResult(
                success=False,
                post_url=post_url,
                comment_text=comment,
                error=str(e),
            )

    # ========================================================================
    # Profile Scraping
    # ========================================================================

    async def scrape_profile(
        self,
        profile_url: str,
    ) -> ProfileData:
        """
        Extract profile data using accessibility tree.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            ProfileData with extracted information
        """
        try:
            page = await self.session.ensure_authenticated()
            await self.session.wait_if_rate_limited()

            # Navigate to profile
            await self.session.navigate_to_profile(page, profile_url)

            # Extract data using accessibility tree
            snapshot = await self.client.get_accessibility_snapshot(page)

            # Parse profile data
            data = ProfileData(profile_url=profile_url)

            # Extract name
            name_elem = await page.query_selector('h1')
            if name_elem:
                data.name = await name_elem.inner_text()

            # Extract headline
            headline_elem = await page.query_selector('div.text-body-medium')
            if headline_elem:
                data.headline = await headline_elem.inner_text()

            # Extract location
            location_elem = await page.query_selector('span.text-body-small')
            if location_elem:
                data.location = await location_elem.inner_text()

            # Extract about section
            about_elem = await page.query_selector('section[data-section="about"] div.inline-show-more-text')
            if about_elem:
                data.about = await about_elem.inner_text()

            # Record view
            self.rate_limiter.record_action("profile_views")

            return data

        except Exception as e:
            logger.error(f"Profile scrape failed for {profile_url}: {e}")
            return ProfileData(profile_url=profile_url)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_remaining_actions(self) -> Dict[str, int]:
        """Get remaining actions for today."""
        return {
            action: self.rate_limiter.get_remaining(action)
            for action in self.rate_limiter.DAILY_LIMITS.keys()
        }

    async def close(self):
        """Close agent and save session state."""
        await self.session.close_session()
        await self.client.close()
