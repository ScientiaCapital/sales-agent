"""
Base cache infrastructure for Redis-backed caching.

Provides:
- Redis client singleton
- Base cache class with common operations
- Cache hit/miss tracking
- TTL management
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Global Redis client (singleton)
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create global Redis client.

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            encoding="utf-8"
        )
        logger.info(f"✅ Initialized Redis cache client: {redis_url}")

    return _redis_client


class CacheBase:
    """
    Base class for all cache implementations.

    Provides common caching patterns:
    - get/set with TTL
    - hit/miss tracking
    - key hashing
    - JSON serialization
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str,
        default_ttl: int = 86400
    ):
        """
        Initialize cache.

        Args:
            redis_client: Redis client instance
            prefix: Cache key prefix (e.g., "linkedin", "qual")
            default_ttl: Default TTL in seconds (default: 24 hours)
        """
        self.redis = redis_client
        self.prefix = prefix
        self.default_ttl = default_ttl

        # Tracking keys for hits/misses
        self.hits_key = f"cache:hits:{prefix}"
        self.misses_key = f"cache:misses:{prefix}"

    def _make_key(self, identifier: str) -> str:
        """
        Create cache key from identifier.

        Args:
            identifier: Unique identifier (e.g., URL, company name)

        Returns:
            Cache key: "{prefix}:{hash}"
        """
        # Hash long identifiers for consistent key length
        if len(identifier) > 100:
            identifier = hashlib.md5(identifier.encode()).hexdigest()

        return f"{self.prefix}:{identifier}"

    async def get(
        self,
        identifier: str,
        track: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached data.

        Args:
            identifier: Cache identifier
            track: Whether to track hit/miss stats

        Returns:
            Cached data dict or None if miss
        """
        key = self._make_key(identifier)
        cached = await self.redis.get(key)

        if cached:
            if track:
                await self.redis.incr(self.hits_key)
                logger.debug(f"🎯 Cache HIT: {self.prefix}:{identifier[:50]}")
            return json.loads(cached)

        if track:
            await self.redis.incr(self.misses_key)
            logger.debug(f"❌ Cache MISS: {self.prefix}:{identifier[:50]}")

        return None

    async def set(
        self,
        identifier: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set cached data with TTL.

        Args:
            identifier: Cache identifier
            data: Data to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default: self.default_ttl)

        Returns:
            True if successful
        """
        key = self._make_key(identifier)
        ttl = ttl or self.default_ttl

        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(data)
            )
            logger.debug(f"💾 Cached: {self.prefix}:{identifier[:50]} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache {key}: {e}")
            return False

    async def delete(self, identifier: str) -> bool:
        """
        Delete cached data.

        Args:
            identifier: Cache identifier

        Returns:
            True if deleted
        """
        key = self._make_key(identifier)
        deleted = await self.redis.delete(key)
        return deleted > 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, hit_rate, etc.
        """
        hits = int(await self.redis.get(self.hits_key) or 0)
        misses = int(await self.redis.get(self.misses_key) or 0)
        total = hits + misses

        # Count cached keys
        pattern = f"{self.prefix}:*"
        cached_keys = await self.redis.keys(pattern)

        return {
            "prefix": self.prefix,
            "cached_items": len(cached_keys),
            "hits": hits,
            "misses": misses,
            "total_requests": total,
            "hit_rate_pct": (hits / total * 100) if total > 0 else 0,
        }

    async def clear_stats(self):
        """Clear hit/miss tracking stats."""
        await self.redis.delete(self.hits_key)
        await self.redis.delete(self.misses_key)
        logger.info(f"Cleared stats for cache: {self.prefix}")

    async def clear_all(self):
        """Clear all cached data for this prefix."""
        pattern = f"{self.prefix}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
        await self.clear_stats()
        logger.info(f"Cleared all cached data for: {self.prefix}")
