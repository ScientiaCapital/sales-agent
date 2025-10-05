"""
Redis Cache Manager for Lead Qualifications

Implements cache-aside pattern with graceful degradation and monitoring.
"""

from typing import Optional, Any
from redis import asyncio as aioredis
import json
import hashlib
import random
from datetime import timedelta
import logging
import os

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis cache manager implementing cache-aside pattern.
    
    Features:
    - Hash-based deterministic cache keys
    - 24-hour TTL with jitter to prevent cache stampede
    - Graceful degradation when Redis unavailable
    - Hit/miss/error rate tracking
    - Async operation for FastAPI integration
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize cache manager with Redis connection.
        
        Args:
            redis_url: Redis connection URL (default: from env or localhost)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[aioredis.Redis] = None
        self.default_ttl = timedelta(hours=24)
        self._connected = False
    
    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """
        Get Redis client with lazy initialization and connection pooling.
        
        Returns:
            Redis client or None if connection fails
        """
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # Test connection
                await self._redis.ping()
                self._connected = True
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self._connected = False
                return None
        return self._redis
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """
        Generate consistent hash-based cache key.
        
        Args:
            prefix: Key prefix (e.g., "lead_qual")
            **kwargs: Data to hash (company_name, industry, etc.)
        
        Returns:
            Cache key in format: prefix:md5_hash
        """
        # Normalize values: lowercase strings, sort dict for consistency
        normalized = {}
        for k, v in kwargs.items():
            if isinstance(v, str):
                normalized[k] = v.lower().strip()
            elif v is None:
                normalized[k] = ""
            else:
                normalized[k] = v
        
        # Create deterministic hash
        data = json.dumps(normalized, sort_keys=True)
        hash_val = hashlib.md5(data.encode()).hexdigest()
        return f"{prefix}:{hash_val}"
    
    def _get_ttl_with_jitter(self, base_ttl: timedelta) -> int:
        """
        Calculate TTL with random jitter to prevent cache stampede.
        
        Args:
            base_ttl: Base TTL (e.g., 24 hours)
        
        Returns:
            TTL in seconds with ±12.5% jitter (21-27 hours for 24h base)
        """
        base_seconds = int(base_ttl.total_seconds())
        jitter_range = int(base_seconds * 0.125)  # ±12.5%
        jitter = random.randint(-jitter_range, jitter_range)
        return base_seconds + jitter
    
    async def _increment_stat(self, stat_name: str):
        """
        Increment cache statistics counter.
        
        Args:
            stat_name: Counter name (hits, misses, errors)
        """
        try:
            redis = await self._get_redis()
            if redis:
                await redis.incr(f"cache:stats:{stat_name}")
        except Exception as e:
            # Don't fail on stats errors
            logger.debug(f"Failed to increment stat {stat_name}: {e}")
    
    async def get_cached_qualification(
        self, 
        company_name: str, 
        industry: Optional[str] = None
    ) -> Optional[dict]:
        """
        Retrieve cached lead qualification result.
        
        Args:
            company_name: Company name
            industry: Company industry (optional)
        
        Returns:
            Cached qualification data or None if cache miss/error
        """
        key = self._generate_key(
            "lead_qual", 
            company=company_name,
            industry=industry or ""
        )
        
        try:
            redis = await self._get_redis()
            if not redis:
                await self._increment_stat("errors")
                return None
            
            cached = await redis.get(key)
            if cached:
                await self._increment_stat("hits")
                logger.info(f"Cache HIT for {company_name}")
                return json.loads(cached)
            else:
                await self._increment_stat("misses")
                logger.info(f"Cache MISS for {company_name}")
                return None
                
        except Exception as e:
            await self._increment_stat("errors")
            logger.error(f"Cache read error for {company_name}: {e}")
            return None
    
    async def cache_qualification(
        self,
        company_name: str,
        industry: Optional[str],
        qualification_data: dict,
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Store lead qualification result in cache.
        
        Args:
            company_name: Company name
            industry: Company industry (optional)
            qualification_data: Qualification result to cache
            ttl: Time to live (default: 24h with jitter)
        
        Returns:
            True if cached successfully, False otherwise
        """
        key = self._generate_key(
            "lead_qual",
            company=company_name,
            industry=industry or ""
        )
        
        try:
            redis = await self._get_redis()
            if not redis:
                await self._increment_stat("errors")
                return False
            
            ttl_seconds = self._get_ttl_with_jitter(ttl or self.default_ttl)
            
            await redis.setex(
                key,
                ttl_seconds,
                json.dumps(qualification_data)
            )
            
            logger.info(f"Cached qualification for {company_name} (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            await self._increment_stat("errors")
            logger.error(f"Cache write error for {company_name}: {e}")
            return False
    
    async def invalidate_lead_cache(
        self, 
        company_name: str, 
        industry: Optional[str] = None
    ) -> bool:
        """
        Invalidate cached qualification for a specific lead.
        
        Args:
            company_name: Company name
            industry: Company industry (optional)
        
        Returns:
            True if invalidated successfully, False otherwise
        """
        key = self._generate_key(
            "lead_qual",
            company=company_name,
            industry=industry or ""
        )
        
        try:
            redis = await self._get_redis()
            if not redis:
                return False
            
            deleted = await redis.delete(key)
            if deleted:
                logger.info(f"Invalidated cache for {company_name}")
            return bool(deleted)
            
        except Exception as e:
            logger.error(f"Cache invalidation error for {company_name}: {e}")
            return False
    
    async def clear_all_qualifications(self) -> int:
        """
        Clear all cached qualification results (admin operation).
        
        Returns:
            Number of keys deleted
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return 0
            
            # Find all qualification cache keys
            keys = []
            async for key in redis.scan_iter(match="lead_qual:*"):
                keys.append(key)
            
            if keys:
                deleted = await redis.delete(*keys)
                logger.warning(f"Cleared {deleted} cached qualifications")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    async def get_cache_stats(self) -> dict:
        """
        Retrieve cache performance statistics.
        
        Returns:
            Dict with hits, misses, errors, hit_rate, total_operations
        """
        try:
            redis = await self._get_redis()
            if not redis:
                return {
                    "connected": False,
                    "hits": 0,
                    "misses": 0,
                    "errors": 0,
                    "hit_rate": 0.0,
                    "total_operations": 0
                }
            
            # Get all stat counters
            hits = int(await redis.get("cache:stats:hits") or 0)
            misses = int(await redis.get("cache:stats:misses") or 0)
            errors = int(await redis.get("cache:stats:errors") or 0)
            
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0.0
            
            return {
                "connected": self._connected,
                "hits": hits,
                "misses": misses,
                "errors": errors,
                "hit_rate": round(hit_rate, 2),
                "total_operations": total
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "connected": False,
                "hits": 0,
                "misses": 0,
                "errors": 0,
                "hit_rate": 0.0,
                "total_operations": 0,
                "error": str(e)
            }
    
    async def health_check(self) -> dict:
        """
        Check Redis connection health.
        
        Returns:
            Dict with status, latency_ms, and error info
        """
        import time
        
        try:
            redis = await self._get_redis()
            if not redis:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Connection failed"
                }
            
            start = time.time()
            await redis.ping()
            latency_ms = int((time.time() - start) * 1000)
            
            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }
    
    async def close(self):
        """Close Redis connection gracefully."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._redis = None
                self._connected = False
