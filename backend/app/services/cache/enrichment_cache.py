"""
Enrichment data caching for expensive LinkedIn scrapes.

LinkedIn scraping is the most expensive operation:
- Cost: ~$0.10 per profile (Browserbase)
- Latency: ~3000ms per scrape
- Rate limit: 100 scrapes/day

Caching saves:
- With 30% duplicate rate: $30/1000 leads
- With 50% duplicate rate: $50/1000 leads
- Plus 1.5-3 seconds per cache hit
"""

import hashlib
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import redis.asyncio as redis

from .base import CacheBase

logger = logging.getLogger(__name__)


class EnrichmentCache(CacheBase):
    """
    Cache for LinkedIn profile enrichment data.

    Cache duration: 7 days (profiles don't change frequently)
    """

    def __init__(self, redis_client: redis.Redis):
        super().__init__(
            redis_client=redis_client,
            prefix="linkedin",
            default_ttl=86400 * 7  # 7 days
        )

    @staticmethod
    def _normalize_linkedin_url(url: str) -> str:
        """
        Normalize LinkedIn URL for consistent cache keys.

        Handles variations like:
        - https://linkedin.com/in/johndoe
        - http://www.linkedin.com/in/johndoe/
        - linkedin.com/in/johndoe?utm_source=...

        Args:
            url: LinkedIn profile URL

        Returns:
            Normalized URL (lowercase, no trailing slash, no params)
        """
        parsed = urlparse(url)

        # Extract path (remove leading/trailing slashes)
        path = parsed.path.strip("/").lower()

        # Return just the path (no domain, no params)
        return path

    async def get_profile(
        self,
        linkedin_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LinkedIn profile data.

        Args:
            linkedin_url: LinkedIn profile URL

        Returns:
            Cached profile data or None
        """
        normalized_url = self._normalize_linkedin_url(linkedin_url)
        cached = await self.get(normalized_url, track=True)

        if cached:
            # Calculate savings from cache hit
            savings_usd = 0.10  # Browserbase scrape cost
            time_saved_ms = 3000  # Average scrape latency

            logger.info(
                f"🎯 LinkedIn Cache HIT: {normalized_url} "
                f"(saved ${savings_usd}, {time_saved_ms}ms)"
            )

        return cached

    async def set_profile(
        self,
        linkedin_url: str,
        profile_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache LinkedIn profile data.

        Args:
            linkedin_url: LinkedIn profile URL
            profile_data: Profile data to cache
            ttl: Optional custom TTL (default: 7 days)

        Returns:
            True if successful
        """
        normalized_url = self._normalize_linkedin_url(linkedin_url)

        # Add metadata to cached data
        enriched_data = {
            **profile_data,
            "cached_at": None,  # Will be added by serialization
            "source": "linkedin_browserbase",
            "cache_ttl_days": (ttl or self.default_ttl) / 86400
        }

        success = await self.set(normalized_url, enriched_data, ttl)

        if success:
            logger.info(
                f"💾 Cached LinkedIn profile: {normalized_url} "
                f"(TTL: {(ttl or self.default_ttl) / 86400} days)"
            )

        return success

    async def get_enrichment_stats(self) -> Dict[str, Any]:
        """
        Get detailed enrichment cache statistics with cost savings.

        Returns:
            Dict with stats including estimated savings
        """
        stats = await self.get_stats()

        # Calculate cost savings
        scrape_cost = 0.10  # Browserbase cost per scrape
        scrape_latency_s = 3.0  # Average scrape time

        estimated_savings_usd = stats["hits"] * scrape_cost
        time_saved_seconds = stats["hits"] * scrape_latency_s

        return {
            **stats,
            "estimated_savings_usd": estimated_savings_usd,
            "time_saved_seconds": time_saved_seconds,
            "avg_scrape_cost_usd": scrape_cost,
            "avg_scrape_latency_s": scrape_latency_s,
        }


# For backward compatibility / convenience
async def get_enrichment_cache() -> EnrichmentCache:
    """
    Get singleton enrichment cache instance.

    Returns:
        EnrichmentCache instance
    """
    from .base import get_redis_client
    redis_client = await get_redis_client()
    return EnrichmentCache(redis_client)
