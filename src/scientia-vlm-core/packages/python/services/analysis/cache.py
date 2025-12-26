"""
Analysis cache using Supabase.

Provides caching for VLM analysis results to avoid redundant API calls.
Cache key is SHA-256 hash of image content.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from supabase import Client, create_client

logger = logging.getLogger(__name__)


def hash_image(image_base64: str) -> str:
    """Generate SHA-256 hash of image content.

    Args:
        image_base64: Base64-encoded image data

    Returns:
        64-character hex string (SHA-256 hash)
    """
    return hashlib.sha256(image_base64.encode()).hexdigest()


class AnalysisCache:
    """Supabase-backed cache for analysis results.

    Provides get/set operations with graceful degradation on errors.
    Cache entries expire after 7 days by default.
    """

    TABLE_NAME = "analysis_cache"
    DEFAULT_TTL_DAYS = 7

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        """Initialize cache with Supabase credentials.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
            ttl_days: Cache TTL in days (default 7)

        Raises:
            ValueError: If URL or key is empty
        """
        if not supabase_url or not supabase_url.strip():
            raise ValueError("Supabase URL is required")
        if not supabase_key or not supabase_key.strip():
            raise ValueError("Supabase key is required")

        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.ttl_days = ttl_days
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Lazy-initialize Supabase client."""
        if self._client is None:
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    async def get(self, image_hash: str) -> dict[str, Any] | None:
        """Retrieve cached analysis result.

        Args:
            image_hash: SHA-256 hash of image content

        Returns:
            Cached result dict or None if not found/error
        """
        try:
            response = (
                self.client.table(self.TABLE_NAME)
                .select("result, model_used")
                .eq("image_hash", image_hash)
                .single()
                .execute()
            )

            if response.data:
                return response.data.get("result")

            return None

        except Exception as e:
            # Graceful degradation - log and return None
            logger.warning(f"Cache get failed for hash {image_hash[:8]}...: {e}")
            return None

    async def set(
        self,
        image_hash: str,
        result: dict[str, Any],
        model: str,
        trade: str | None = None,
        confidence: float | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        """Store analysis result in cache.

        Args:
            image_hash: SHA-256 hash of image content
            result: Analysis result dict
            model: Model used for analysis
            trade: Trade type (optional)
            confidence: Confidence score (optional)
            cost_usd: API cost in USD
        """
        try:
            now = datetime.now(UTC)
            expires_at = now + timedelta(days=self.ttl_days)

            data = {
                "image_hash": image_hash,
                "result": result,
                "model_used": model,
                "trade": trade,
                "confidence": confidence,
                "cost_usd": cost_usd,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }

            self.client.table(self.TABLE_NAME).upsert(data).execute()

        except Exception as e:
            # Graceful degradation - log and continue
            logger.warning(f"Cache set failed for hash {image_hash[:8]}...: {e}")
