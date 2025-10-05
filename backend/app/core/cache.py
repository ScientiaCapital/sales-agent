"""
Redis Cache Dependency Injection

Provides FastAPI dependency for cache manager instances.
"""

from typing import AsyncGenerator
from app.services.cache_manager import CacheManager
import os

# Global cache manager instance (singleton pattern)
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """
    Get or create global CacheManager instance.
    
    Returns:
        CacheManager singleton instance
    """
    global _cache_manager
    if _cache_manager is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _cache_manager = CacheManager(redis_url=redis_url)
    return _cache_manager


async def get_cache() -> AsyncGenerator[CacheManager, None]:
    """
    FastAPI dependency for cache manager.
    
    Yields:
        CacheManager instance
    
    Example:
        @app.get("/example")
        async def endpoint(cache: CacheManager = Depends(get_cache)):
            cached_data = await cache.get_cached_qualification(...)
    """
    cache = get_cache_manager()
    try:
        yield cache
    finally:
        # Connection cleanup handled by CacheManager
        pass


async def close_cache():
    """
    Close global cache manager connection.
    
    Call this on application shutdown.
    """
    global _cache_manager
    if _cache_manager:
        await _cache_manager.close()
        _cache_manager = None
