"""
Apollo.io CRM Integration

Implements API key authentication and contact enrichment for Apollo.io
using the v1 API.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import httpx
import logging
import json

from app.services.crm.base import (
    CRMProvider,
    Contact,
    CRMCredentials,
    SyncResult,
    WebhookEvent,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMNetworkError,
)

logger = logging.getLogger(__name__)


class ApolloProvider(CRMProvider):
    """
    Apollo.io integration using API key authentication.

    Features:
    - API key authentication (X-Api-Key header)
    - Contact enrichment from email
    - Person data retrieval by Apollo ID
    - Redis-based rate limiting (600 req/hour per endpoint)
    - Rich data mapping (title, company, LinkedIn, phone, location)
    """

    BASE_URL = "https://api.apollo.io/api/v1"

    # Rate limits: 600 requests per hour per endpoint
    RATE_LIMIT_HOURLY = 600

    def __init__(
        self,
        credentials: CRMCredentials,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize Apollo provider.

        Args:
            credentials: CRM credentials with encrypted API key
            redis_client: Redis client for rate limiting (optional)
        """
        super().__init__(credentials)
        self.redis = redis_client

        # Decrypt API key from credentials
        self.api_key = None
        if credentials.api_key:
            self.api_key = self.decrypt_credential(credentials.api_key)
        elif credentials.access_token:
            # Fallback: some configs might store API key as access_token
            self.api_key = self.decrypt_credential(credentials.access_token)

        if not self.api_key:
            raise CRMValidationError("Apollo API key is required")

    async def authenticate(self) -> bool:
        """
        Verify authentication by making a test API call.

        Returns:
            True if authenticated successfully

        Raises:
            CRMAuthenticationError: If authentication fails
        """
        try:
            # Test auth with a simple person match (using Apollo's demo email)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/people/match",
                    headers={
                        "X-Api-Key": self.api_key,
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                    },
                    params={"email": "test@apollo.io"},  # Test call
                    timeout=30.0
                )

                if response.status_code == 401:
                    raise CRMAuthenticationError("Invalid Apollo API key")
                elif response.status_code == 403:
                    data = response.json() if response.text else {}
                    message = data.get("message", "Access forbidden - check API key permissions")
                    raise CRMAuthenticationError(message)
                elif response.status_code >= 400:
                    raise CRMAuthenticationError(f"Authentication failed: {response.status_code}")

                logger.info("Apollo authentication successful")
                return True

        except httpx.HTTPError as e:
            logger.error(f"Apollo authentication network error: {e}")
            raise CRMNetworkError(f"Network error during authentication: {e}")

    async def refresh_access_token(self) -> str:
        """
        Apollo uses API key authentication (no token refresh needed).

        Returns:
            The current API key
        """
        logger.info("Apollo uses API key authentication - no token refresh needed")
        return self.api_key

    def _map_apollo_to_contact(self, person: Dict[str, Any]) -> Contact:
        """
        Map Apollo person response to unified Contact model.

        Args:
            person: Apollo person object from API response

        Returns:
            Contact with enriched data
        """
        # Extract organization data
        org = person.get("organization", {}) or {}

        # Build location string
        location_parts = [
            person.get("city"),
            person.get("state"),
            person.get("country")
        ]
        location = ", ".join([p for p in location_parts if p])

        # Get first phone number if available
        phone_numbers = person.get("phone_numbers", [])
        phone = phone_numbers[0].get("raw_number") if phone_numbers else None

        return Contact(
            external_id=person.get("id"),
            email=person.get("email"),
            first_name=person.get("first_name"),
            last_name=person.get("last_name"),
            title=person.get("title"),
            company=org.get("name"),
            company_website=org.get("website_url"),
            industry=org.get("industry"),
            company_size=str(org.get("estimated_num_employees")) if org.get("estimated_num_employees") else None,
            phone=phone,
            linkedin_url=person.get("linkedin_url"),
            location=location if location else None,
            custom_fields={
                "apollo_person_id": person.get("id"),
                "apollo_org_id": org.get("id"),
                "email_status": person.get("email_status"),
                "headline": person.get("headline"),
                "photo_url": person.get("photo_url"),
                "twitter_url": person.get("twitter_url"),
                "github_url": person.get("github_url"),
                "facebook_url": person.get("facebook_url"),
                "employment_history": person.get("employment_history", []),
                "raw_apollo_data": person  # Store full response for reference
            }
        )

    async def get_contact(self, contact_id: str) -> Contact:
        """
        Retrieve a contact by Apollo person ID.

        Args:
            contact_id: Apollo person ID

        Returns:
            Contact object with person data

        Raises:
            CRMNotFoundError: If person not found
            CRMRateLimitError: If rate limit exceeded
        """
        try:
            await self._check_rate_limit()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/people/match",
                    headers={
                        "X-Api-Key": self.api_key,
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                    },
                    params={"id": contact_id},
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 404:
                    raise CRMNotFoundError(f"Person {contact_id} not found in Apollo")
                elif response.status_code == 429:
                    data = response.json()
                    raise CRMRateLimitError(data.get("message", "Rate limit exceeded"))
                elif response.status_code >= 400:
                    raise CRMNetworkError(f"Apollo API error: {response.status_code}")

                person = response.json()
                return self._map_apollo_to_contact(person)

        except httpx.HTTPError as e:
            logger.error(f"Network error getting contact {contact_id}: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def create_contact(self, contact: Contact) -> Contact:
        """
        Apollo is read-only intelligence platform - contact creation not supported.

        Raises:
            CRMValidationError: Always, as operation is not supported
        """
        raise CRMValidationError(
            "Apollo is a read-only intelligence platform. "
            "Contact creation not supported. Use HubSpot or other CRM for CRUD operations."
        )

    async def update_contact(self, contact_id: str, contact: Contact) -> Contact:
        """
        Apollo is read-only intelligence platform - contact updates not supported.

        Raises:
            CRMValidationError: Always, as operation is not supported
        """
        raise CRMValidationError(
            "Apollo is a read-only intelligence platform. "
            "Contact updates not supported. Use HubSpot or other CRM for CRUD operations."
        )

    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Enrich contact data using email address (Apollo's primary use case).

        Args:
            email: Email address to enrich

        Returns:
            Dict with enriched contact data and Apollo person object

        Raises:
            CRMNotFoundError: If email not found
            CRMRateLimitError: If rate limit exceeded
        """
        try:
            await self._check_rate_limit()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/people/match",
                    headers={
                        "X-Api-Key": self.api_key,
                        "Content-Type": "application/json",
                        "Cache-Control": "no-cache",
                    },
                    params={
                        "email": email,
                        # "reveal_phone_number": "false",  # Costs extra credits
                        # "reveal_personal_emails": "false"  # Costs extra credits
                    },
                    timeout=30.0
                )

                await self._update_rate_limit(response)

                if response.status_code == 404:
                    logger.info(f"Email {email} not found in Apollo")
                    return None
                elif response.status_code == 429:
                    data = response.json()
                    raise CRMRateLimitError(data.get("message", "Rate limit exceeded"))
                elif response.status_code >= 400:
                    logger.error(f"Apollo enrichment error: {response.status_code}")
                    return None

                person = response.json()
                contact = self._map_apollo_to_contact(person)

                return {
                    "contact": contact.dict(),
                    "apollo_person": person,
                    "enrichment_date": datetime.utcnow().isoformat()
                }

        except httpx.HTTPError as e:
            logger.error(f"Network error enriching {email}: {e}")
            raise CRMNetworkError(f"Network error: {e}")

    async def sync_contacts(
        self,
        direction: str = "import",
        filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        One-way import from Apollo search (export not supported).

        Args:
            direction: Must be "import" (Apollo is read-only)
            filters: Search filters for Apollo people search API

        Returns:
            SyncResult with import metrics

        Raises:
            CRMValidationError: If direction is not "import"
        """
        if direction != "import":
            raise CRMValidationError(
                f"Apollo only supports 'import' direction (read-only platform). Got: {direction}"
            )

        # TODO: Implement Apollo people search API integration
        # This would use /api/v1/mixed_people/search endpoint
        # For now, return empty result
        logger.warning("Apollo sync_contacts not yet fully implemented - returning empty result")

        return SyncResult(
            contacts_created=0,
            contacts_updated=0,
            contacts_failed=0,
            total_processed=0,
            sync_direction=direction
        )

    async def get_updated_contacts(self, since: datetime) -> List[Contact]:
        """
        Apollo doesn't support update tracking (no webhooks/changelog).

        Returns:
            Empty list (not supported)
        """
        logger.info("Apollo doesn't support update tracking - returning empty list")
        return []

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Apollo webhook signature verification.

        Note: Apollo webhook support is limited - may not be available on all plans.

        Returns:
            False (webhook verification not yet implemented)
        """
        logger.warning("Apollo webhook verification not implemented")
        return False

    async def handle_webhook(self, event: WebhookEvent) -> None:
        """
        Handle Apollo webhook events.

        Note: Apollo webhook support is limited.
        """
        logger.info(f"Apollo webhook event received (not yet processed): {event.event_type}")
        pass

    async def _check_rate_limit(self) -> None:
        """
        Check if rate limit allows making a request.

        Raises:
            CRMRateLimitError: If rate limit exceeded
        """
        if not self.redis:
            return  # No Redis, skip rate limiting

        try:
            # Check requests in last hour
            key = f"apollo:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H')}"
            current_count = await self.redis.get(key)

            if current_count and int(current_count) >= self.RATE_LIMIT_HOURLY:
                raise CRMRateLimitError(
                    f"Apollo rate limit exceeded: {self.RATE_LIMIT_HOURLY} requests/hour"
                )

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Don't block requests if Redis fails

    async def _update_rate_limit(self, response: httpx.Response) -> None:
        """
        Update rate limit counters based on API response.

        Args:
            response: HTTP response from Apollo API
        """
        if not self.redis:
            return

        try:
            # Increment hourly counter
            key = f"apollo:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H')}"
            await self.redis.incr(key)
            await self.redis.expire(key, 3600)  # Expire after 1 hour

            # Apollo doesn't return rate limit headers, so we track client-side
            logger.debug(f"Apollo rate limit updated for key: {key}")

        except Exception as e:
            logger.warning(f"Failed to update rate limit: {e}")

    async def check_rate_limit(self) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Dict with rate limit information
        """
        if not self.redis:
            return {
                "rate_limit_enabled": False,
                "message": "Rate limiting disabled (no Redis)"
            }

        try:
            key = f"apollo:rate_limit:{datetime.utcnow().strftime('%Y-%m-%d:%H')}"
            current_count = await self.redis.get(key)
            count = int(current_count) if current_count else 0

            return {
                "rate_limit_enabled": True,
                "hourly_limit": self.RATE_LIMIT_HOURLY,
                "requests_used": count,
                "requests_remaining": max(0, self.RATE_LIMIT_HOURLY - count),
                "reset_time": datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            }

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return {
                "rate_limit_enabled": True,
                "error": str(e)
            }
