"""
VLM Response Cache

Caches Vision Language Model (VLM) responses for screenshots to avoid
redundant expensive API calls. Uses SHA256 hash of screenshot binary as key.

Features:
- 24-hour TTL (86400 seconds) for VLM responses
- SHA256 hashing of screenshot binary for deterministic keys
- Hit/miss tracking via CacheBase
- Redis-backed storage for persistence across processes
"""

import hashlib
from typing import Optional, Dict, Any
import redis.asyncio as redis

from .base import CacheBase


class VLMCache(CacheBase):
    """
    Cache for Vision Language Model (VLM) responses.

    Caches extracted contact data from screenshots to avoid re-processing
    identical images. Uses SHA256 hash of screenshot binary as cache key.

    Default TTL: 24 hours (86400 seconds)
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl: int = 86400  # 24 hours
    ):
        """
        Initialize VLM cache.

        Args:
            redis_client: Redis client instance
            default_ttl: TTL in seconds (default: 24 hours)
        """
        super().__init__(
            redis_client=redis_client,
            prefix="vlm",
            default_ttl=default_ttl
        )

    def _hash_screenshot(self, screenshot_data: bytes) -> str:
        """
        Compute SHA256 hash of screenshot binary.

        Args:
            screenshot_data: Screenshot binary data

        Returns:
            SHA256 hex digest (64 characters)
        """
        return hashlib.sha256(screenshot_data).hexdigest()

    async def get_vlm_response(
        self,
        screenshot_data: bytes,
        track: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached VLM response for screenshot.

        Args:
            screenshot_data: Screenshot binary data
            track: Whether to track cache hit/miss stats

        Returns:
            Cached VLM response dict or None if cache miss

        Example response:
            {
                "contacts": [
                    {
                        "name": "John Doe",
                        "title": "CEO",
                        "email": "john@example.com"
                    }
                ],
                "confidence": 0.95,
                "source_url": "https://example.com/team"
            }
        """
        screenshot_hash = self._hash_screenshot(screenshot_data)
        return await self.get(identifier=screenshot_hash, track=track)

    async def set_vlm_response(
        self,
        screenshot_data: bytes,
        vlm_response: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache VLM response for screenshot.

        Args:
            screenshot_data: Screenshot binary data
            vlm_response: VLM response dict to cache
            ttl: Optional custom TTL (default: 24 hours)

        Returns:
            True if successfully cached

        Example:
            await cache.set_vlm_response(
                screenshot_data=screenshot_bytes,
                vlm_response={
                    "contacts": [...],
                    "confidence": 0.95
                }
            )
        """
        screenshot_hash = self._hash_screenshot(screenshot_data)
        return await self.set(
            identifier=screenshot_hash,
            data=vlm_response,
            ttl=ttl
        )

    async def delete_vlm_response(self, screenshot_data: bytes) -> bool:
        """
        Delete cached VLM response for screenshot.

        Args:
            screenshot_data: Screenshot binary data

        Returns:
            True if deleted
        """
        screenshot_hash = self._hash_screenshot(screenshot_data)
        return await self.delete(identifier=screenshot_hash)


# Convenience function for quick access
async def get_vlm_cache(redis_client: redis.Redis) -> VLMCache:
    """
    Get VLM cache instance.

    Args:
        redis_client: Redis client

    Returns:
        VLMCache instance
    """
    return VLMCache(redis_client=redis_client)
