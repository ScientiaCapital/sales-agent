"""
ApolloRateLimitedService - Apollo.io with Built-in Rate Limiting

Wraps ApolloService to enforce rate limits BEFORE every API call.
Prevents token/credit burning by checking limits proactively.

This is the ONLY way Apollo should be called in batch processing.

Features:
- Pre-flight rate limit checks (minute/hour/day)
- Automatic backoff when limits approached
- Credit budget enforcement
- Distributed tracking via Redis

Usage:
    # WRONG - direct Apollo calls can burn credits
    # apollo = ApolloService()
    # await apollo.enrich_contact(...)

    # RIGHT - rate-limited wrapper
    apollo = ApolloRateLimitedService()
    result = await apollo.enrich_contact_safe(...)  # Checks limits first

Environment Variables:
    APOLLO_RATE_LIMIT_HOURLY: Requests per hour (default: 200)
    APOLLO_RATE_LIMIT_DAILY: Requests per day (default: 2000)
    APOLLO_DAILY_CREDIT_BUDGET: Max credits per day (default: 500)
    REDIS_URL: Redis connection for distributed tracking
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from functools import wraps

from app.core.logging import setup_logging
from app.core.exceptions import APIRateLimitError, ValidationError
from app.services.apollo import ApolloService
from app.services.batch_rate_limiter import (
    BatchRateLimiter,
    RateLimitConfig,
    ApolloRateLimitConfig,
    create_rate_limiter,
)
from app.services.crm.base import Contact

logger = setup_logging(__name__)


class ApolloRateLimitedService:
    """
    Rate-limited wrapper for ApolloService.

    ALWAYS use this instead of ApolloService directly for batch operations.
    Enforces rate limits and credit budgets before every API call.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limiter: Optional[BatchRateLimiter] = None,
        auto_wait: bool = True,
        max_wait_seconds: float = 120,
    ):
        """
        Initialize rate-limited Apollo service.

        Args:
            api_key: Apollo API key (optional, uses env var)
            rate_limiter: Shared BatchRateLimiter (creates one if not provided)
            auto_wait: If True, wait for rate limit to clear (default: True)
            max_wait_seconds: Maximum time to wait for rate limit (default: 120s)
        """
        self._apollo = ApolloService(api_key=api_key)
        self._rate_limiter = rate_limiter or create_rate_limiter()
        self._auto_wait = auto_wait
        self._max_wait = max_wait_seconds

        # Track local usage for logging
        self._session_calls = 0
        self._session_credits = 0
        self._session_start = datetime.utcnow()

        logger.info(
            "ApolloRateLimitedService initialized - "
            f"auto_wait={auto_wait}, max_wait={max_wait_seconds}s"
        )

    async def _check_rate_limit(
        self,
        endpoint: Optional[str] = None,
        credits_needed: int = 1,
    ) -> bool:
        """
        Check rate limit before making API call.

        Args:
            endpoint: Endpoint name for specific limits
            credits_needed: Credits this call will consume

        Returns:
            True if allowed, raises if not and auto_wait=False

        Raises:
            APIRateLimitError: If rate limited and auto_wait=False
        """
        # Check if we can make the call
        can_proceed = await self._rate_limiter.can_use_apollo(
            endpoint=endpoint,
            check_credits=True,
        )

        if can_proceed:
            return True

        # Get current status for error message
        usage = await self._rate_limiter.get_apollo_usage()
        remaining = await self._rate_limiter.get_apollo_remaining()

        if self._auto_wait:
            logger.warning(
                f"Apollo rate limit reached, waiting... "
                f"(minute: {remaining['minute']}, hour: {remaining['hour']}, "
                f"day: {remaining['day']}, credits: {remaining['credits']})"
            )

            # Wait for rate limit to clear
            allowed = await self._rate_limiter.wait_for_apollo_rate_limit(
                endpoint=endpoint,
                max_wait_seconds=self._max_wait,
            )

            if allowed:
                return True

            # Still rate limited after waiting
            raise APIRateLimitError(
                f"Apollo rate limit exceeded after waiting {self._max_wait}s. "
                f"Daily: {usage.requests_this_day}/{self._rate_limiter.config.apollo.requests_per_day}, "
                f"Credits: {usage.credits_used_today}/{self._rate_limiter.config.apollo.daily_credit_budget}",
                context={
                    "usage": usage.to_dict(),
                    "remaining": remaining,
                    "waited_seconds": self._max_wait,
                }
            )
        else:
            raise APIRateLimitError(
                f"Apollo rate limit exceeded. "
                f"Minute: {usage.requests_this_minute}, Hour: {usage.requests_this_hour}, "
                f"Day: {usage.requests_this_day}, Credits: {usage.credits_used_today}",
                context={
                    "usage": usage.to_dict(),
                    "remaining": remaining,
                }
            )

    async def _record_usage(self, credits: int = 1) -> None:
        """Record usage after successful API call."""
        await self._rate_limiter.record_apollo_usage(credits=credits)
        self._session_calls += 1
        self._session_credits += credits

    # ========== Safe API Methods ==========

    async def enrich_contact_safe(
        self,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        domain: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        reveal_personal_email: bool = False,
        reveal_phone: bool = False,
    ) -> Contact:
        """
        Rate-limited contact enrichment.

        Checks rate limits BEFORE making API call. If at limit:
        - auto_wait=True: Waits up to max_wait_seconds
        - auto_wait=False: Raises APIRateLimitError immediately

        Args:
            Same as ApolloService.enrich_contact()

        Returns:
            Enriched Contact object

        Raises:
            APIRateLimitError: If rate limited (and auto_wait timeout exceeded)
        """
        # Pre-flight rate limit check
        credits_needed = 1
        if reveal_personal_email:
            credits_needed += 1
        if reveal_phone:
            credits_needed += 1

        await self._check_rate_limit(endpoint="people_match", credits_needed=credits_needed)

        # Make the actual API call
        result = await self._apollo.enrich_contact(
            email=email,
            first_name=first_name,
            last_name=last_name,
            domain=domain,
            linkedin_url=linkedin_url,
            reveal_personal_email=reveal_personal_email,
            reveal_phone=reveal_phone,
        )

        # Record successful usage
        await self._record_usage(credits=credits_needed)

        return result

    async def enrich_company_safe(self, domain: str) -> Dict[str, Any]:
        """
        Rate-limited company enrichment.

        Args:
            domain: Company domain

        Returns:
            Enriched company data

        Raises:
            APIRateLimitError: If rate limited
        """
        await self._check_rate_limit(endpoint="organizations_enrich", credits_needed=0)

        result = await self._apollo.enrich_company(domain=domain)

        # Company enrichment is typically free (no credits)
        await self._record_usage(credits=0)

        return result

    async def search_company_contacts_safe(
        self,
        domain: str,
        job_titles: Optional[List[str]] = None,
        max_results: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Rate-limited company contact search.

        Args:
            domain: Company domain
            job_titles: Optional title filters
            max_results: Max results to return

        Returns:
            List of contact dicts

        Raises:
            APIRateLimitError: If rate limited
        """
        await self._check_rate_limit(endpoint="people_search", credits_needed=0)

        result = await self._apollo.search_company_contacts(
            domain=domain,
            job_titles=job_titles,
            max_results=max_results,
        )

        # Search is typically free
        await self._record_usage(credits=0)

        return result

    async def search_and_enrich_contacts_safe(
        self,
        domain: str,
        job_titles: Optional[List[str]] = None,
        max_results: int = 10,
        reveal_emails: bool = True,
        reveal_phones: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Rate-limited search + enrich workflow.

        This is the most expensive operation - searches then enriches each contact.
        Credits: ~1 per contact enriched.

        Args:
            domain: Company domain
            job_titles: Optional title filters
            max_results: Max contacts to enrich (controls credit spend)
            reveal_emails: Get real emails (costs credits)
            reveal_phones: Get phone numbers (costs additional credits)

        Returns:
            List of enriched contact dicts

        Raises:
            APIRateLimitError: If rate limited
        """
        # Check if we have enough budget for all potential enrichments
        credits_per_contact = 1 + (1 if reveal_phones else 0)
        max_credits_needed = max_results * credits_per_contact

        # Check remaining credits
        remaining = await self._rate_limiter.get_apollo_remaining()
        if remaining["credits"] < max_credits_needed:
            logger.warning(
                f"Reducing max_results from {max_results} to {remaining['credits'] // credits_per_contact} "
                f"due to credit budget (remaining: {remaining['credits']})"
            )
            max_results = max(1, remaining["credits"] // credits_per_contact)

        await self._check_rate_limit(endpoint="people_search", credits_needed=0)

        result = await self._apollo.search_and_enrich_contacts(
            domain=domain,
            job_titles=job_titles,
            max_results=max_results,
            reveal_emails=reveal_emails,
            reveal_phones=reveal_phones,
        )

        # Record credits for each enriched contact
        enriched_count = len([c for c in result if c.get("email_verified")])
        credits_used = enriched_count * credits_per_contact
        await self._record_usage(credits=credits_used)

        return result

    async def bulk_enrich_contacts_safe(
        self,
        contacts: List[Dict[str, str]],
        reveal_personal_emails: bool = False,
    ) -> List[Contact]:
        """
        Rate-limited bulk enrichment.

        Args:
            contacts: List of contact dicts (max 10)
            reveal_personal_emails: Get personal emails

        Returns:
            List of enriched Contact objects

        Raises:
            APIRateLimitError: If rate limited
            ValidationError: If more than 10 contacts
        """
        if len(contacts) > 10:
            raise ValidationError("Bulk enrichment limited to 10 contacts")

        credits_needed = len(contacts)
        if reveal_personal_emails:
            credits_needed *= 2

        await self._check_rate_limit(endpoint="bulk_enrich", credits_needed=credits_needed)

        result = await self._apollo.bulk_enrich_contacts(
            contacts=contacts,
            reveal_personal_emails=reveal_personal_emails,
        )

        await self._record_usage(credits=credits_needed)

        return result

    # ========== Status and Health ==========

    async def get_usage_status(self) -> Dict[str, Any]:
        """
        Get current usage status.

        Returns:
            Dictionary with usage stats and limits
        """
        usage = await self._rate_limiter.get_apollo_usage()
        remaining = await self._rate_limiter.get_apollo_remaining()
        config = self._rate_limiter.config.apollo

        return {
            "session": {
                "calls": self._session_calls,
                "credits": self._session_credits,
                "started_at": self._session_start.isoformat(),
            },
            "current": usage.to_dict(),
            "remaining": remaining,
            "limits": {
                "requests_per_minute": config.requests_per_minute,
                "requests_per_hour": config.requests_per_hour,
                "requests_per_day": config.requests_per_day,
                "daily_credit_budget": config.daily_credit_budget,
            },
            "can_proceed": await self._rate_limiter.can_use_apollo(),
        }

    async def get_remaining_capacity(self) -> Dict[str, int]:
        """Get remaining capacity for planning batch size."""
        return await self._rate_limiter.get_apollo_remaining()

    async def close(self) -> None:
        """Close connections."""
        await self._apollo.close()
        logger.info(
            f"ApolloRateLimitedService closed - "
            f"session stats: {self._session_calls} calls, {self._session_credits} credits"
        )


# ========== Factory Function ==========

def create_apollo_service(
    api_key: Optional[str] = None,
    rate_limiter: Optional[BatchRateLimiter] = None,
    auto_wait: bool = True,
) -> ApolloRateLimitedService:
    """
    Factory function to create a rate-limited Apollo service.

    This is the recommended way to create an Apollo service for batch processing.

    Args:
        api_key: Apollo API key (optional, uses env var)
        rate_limiter: Shared rate limiter (creates one if not provided)
        auto_wait: Wait for rate limits to clear (default: True)

    Returns:
        Configured ApolloRateLimitedService instance
    """
    return ApolloRateLimitedService(
        api_key=api_key,
        rate_limiter=rate_limiter,
        auto_wait=auto_wait,
    )


# ========== Decorator for existing code migration ==========

def rate_limited_apollo(func):
    """
    Decorator to add rate limiting to existing Apollo calls.

    Usage:
        @rate_limited_apollo
        async def my_enrichment_function():
            apollo = ApolloService()
            return await apollo.enrich_contact(...)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        rate_limiter = create_rate_limiter()

        # Check rate limit before proceeding
        if not await rate_limiter.can_use_apollo():
            usage = await rate_limiter.get_apollo_usage()
            raise APIRateLimitError(
                f"Apollo rate limit exceeded before {func.__name__}",
                context={"usage": usage.to_dict()}
            )

        # Execute the function
        result = await func(*args, **kwargs)

        # Record usage (assume 1 credit)
        await rate_limiter.record_apollo_usage(credits=1)

        return result

    return wrapper
