"""
Battle Cards API Service

Provides competitive intelligence from the Coperniq Battle Cards API.
Used during sales conversations for real-time competitor positioning.

API: Coperniq Battle Cards (coperniq-battle-cards.vercel.app)
Rate Limits: None (internal service)
"""

import os
import httpx
from typing import Dict, Any, Optional, List

from app.core.logging import setup_logging
from app.core.exceptions import (
    MissingAPIKeyError,
    APIAuthenticationError,
    APIConnectionError,
    APITimeoutError,
)
from app.services.circuit_breaker_registry import get_circuit_breaker
from app.services.circuit_breaker import CircuitBreakerError

logger = setup_logging(__name__)


class BattleCardsAPIService:
    """
    Service for accessing Coperniq Battle Cards competitive intelligence.

    Features:
    - Competitor data with killer questions and value props
    - Objection handlers for common sales objections
    - AI feature comparisons for differentiation
    - Full-text search across all content
    """

    DEFAULT_BASE_URL = "https://coperniq-battle-cards.vercel.app/api/v1"
    TIMEOUT = 10  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize Battle Cards API service.

        Args:
            api_key: Battle Cards API key (reads from env if not provided)
            base_url: API base URL (uses default if not provided)

        Raises:
            MissingAPIKeyError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("BATTLE_CARDS_API_KEY")
        self.base_url = base_url or os.getenv(
            "BATTLE_CARDS_API_URL",
            self.DEFAULT_BASE_URL
        )

        if not self.api_key:
            raise MissingAPIKeyError(
                "BATTLE_CARDS_API_KEY environment variable not set",
                context={"api_key": "BATTLE_CARDS_API_KEY"}
            )

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.TIMEOUT,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }
        )

        self._circuit_breaker = get_circuit_breaker("battle_cards")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an API request with error handling."""
        try:
            if method == "GET":
                response = await self.client.get(endpoint)
            elif method == "POST":
                response = await self.client.post(endpoint, json=json_data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code == 401:
                raise APIAuthenticationError(
                    "Battle Cards API authentication failed",
                    context={"status_code": 401}
                )

            response.raise_for_status()
            return response.json()

        except httpx.ConnectError as e:
            raise APIConnectionError(
                f"Failed to connect to Battle Cards API: {str(e)}",
                context={"endpoint": endpoint}
            )
        except httpx.TimeoutException as e:
            raise APITimeoutError(
                f"Battle Cards API request timed out: {str(e)}",
                context={"endpoint": endpoint, "timeout": self.TIMEOUT}
            )

    async def get_all_competitors(
        self,
        target_market: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all competitors with optional filtering.

        Args:
            target_market: Filter by target market (e.g., "solar", "commercial")
            limit: Maximum number of results (default: 50)

        Returns:
            List of competitor objects
        """
        params = []
        if target_market:
            params.append(f"target_market={target_market}")
        if limit != 50:
            params.append(f"limit={limit}")

        endpoint = "/competitors"
        if params:
            endpoint += "?" + "&".join(params)

        try:
            result = await self._circuit_breaker.call(
                self._make_request, "GET", endpoint
            )
            return result.get("data", {}).get("competitors", [])
        except CircuitBreakerError:
            logger.warning("Battle Cards circuit breaker open")
            return []

    async def get_competitor(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single competitor by ID.

        Args:
            competitor_id: Competitor ID (e.g., "servicetitan", "procore")

        Returns:
            Competitor object or None if not found
        """
        try:
            result = await self._circuit_breaker.call(
                self._make_request, "GET", f"/competitors/{competitor_id}"
            )
            return result.get("data", {}).get("competitor")
        except CircuitBreakerError:
            logger.warning("Battle Cards circuit breaker open")
            return None
        except Exception as e:
            if "404" in str(e):
                return None
            raise

    async def get_objections(self) -> List[Dict[str, Any]]:
        """
        Get all objection handlers.

        Returns:
            List of objection handler objects
        """
        try:
            result = await self._circuit_breaker.call(
                self._make_request, "GET", "/objections"
            )
            return result.get("data", {}).get("objections", [])
        except CircuitBreakerError:
            logger.warning("Battle Cards circuit breaker open")
            return []

    async def get_ai_features(self) -> Dict[str, Any]:
        """
        Get AI features and ecosystem advantage.

        Returns:
            Dict with features list and ecosystem object
        """
        try:
            result = await self._circuit_breaker.call(
                self._make_request, "GET", "/ai-features"
            )
            return result.get("data", {})
        except CircuitBreakerError:
            logger.warning("Battle Cards circuit breaker open")
            return {}

    async def search(
        self,
        query: str,
        types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across all battle card content.

        Args:
            query: Search query string
            types: Filter by type (competitors, objections, ai_features)
            limit: Maximum results (default: 10)

        Returns:
            List of search result objects
        """
        payload = {
            "query": query,
            "limit": limit
        }
        if types:
            payload["types"] = types

        try:
            result = await self._circuit_breaker.call(
                self._make_request, "POST", "/search", payload
            )
            return result.get("data", {}).get("results", [])
        except CircuitBreakerError:
            logger.warning("Battle Cards circuit breaker open")
            return []

    async def get_competitor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a competitor by name (case-insensitive search).

        Args:
            name: Competitor name (e.g., "ServiceTitan", "procore")

        Returns:
            Competitor object or None if not found
        """
        # First try direct ID lookup (names often match IDs)
        competitor_id = name.lower().replace(" ", "")
        result = await self.get_competitor(competitor_id)
        if result:
            return result

        # Fall back to search
        search_results = await self.search(name, types=["competitors"], limit=1)
        if search_results:
            comp_id = search_results[0].get("id")
            if comp_id:
                return await self.get_competitor(comp_id)

        return None

    async def health_check(self) -> bool:
        """
        Check if the Battle Cards API is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            result = await self._make_request("GET", "/health")
            return result.get("data", {}).get("status") == "healthy"
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
