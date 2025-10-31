"""
Qualification score caching for repeated company lookups.

Same companies appear in multiple lead lists:
- Cost: $0.000006 per Cerebras call (cheap but adds up)
- Latency: 633ms average
- Change frequency: Low (company fundamentals change slowly)

Caching saves:
- With 20% duplicate rate: $0.012 per 10K leads
- With 50% duplicate rate: $0.030 per 10K leads
- Plus ~30 seconds per 100 cache hits
"""

import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis

from .base import CacheBase

logger = logging.getLogger(__name__)


class QualificationCache(CacheBase):
    """
    Cache for company qualification scores.

    Cache duration: 24 hours (company fundamentals change daily)
    """

    def __init__(self, redis_client: redis.Redis):
        super().__init__(
            redis_client=redis_client,
            prefix="qual",
            default_ttl=86400  # 24 hours
        )

    @staticmethod
    def _make_company_key(
        company_name: str,
        industry: Optional[str] = None
    ) -> str:
        """
        Create consistent cache key for company.

        Args:
            company_name: Company name
            industry: Optional industry (adds specificity)

        Returns:
            Normalized cache key
        """
        # Normalize company name: lowercase, remove punctuation
        normalized_name = company_name.lower().strip()
        normalized_name = "".join(c for c in normalized_name if c.isalnum() or c.isspace())
        normalized_name = " ".join(normalized_name.split())  # Collapse whitespace

        if industry:
            normalized_industry = industry.lower().strip()
            return f"{normalized_name}:{normalized_industry}"

        return normalized_name

    async def get_qualification(
        self,
        company_name: str,
        industry: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached qualification score.

        Args:
            company_name: Company name
            industry: Optional industry for cache specificity

        Returns:
            Cached qualification result or None
        """
        cache_key = self._make_company_key(company_name, industry)
        cached = await self.get(cache_key, track=True)

        if cached:
            # Calculate savings from cache hit
            savings_usd = 0.000006  # Cerebras qualification cost
            time_saved_ms = 633  # Average qualification latency

            logger.info(
                f"🎯 Qualification Cache HIT: {company_name} "
                f"(saved ${savings_usd}, {time_saved_ms}ms)"
            )

        return cached

    async def set_qualification(
        self,
        company_name: str,
        industry: Optional[str],
        qualification_result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache qualification result.

        Args:
            company_name: Company name
            industry: Optional industry
            qualification_result: Qualification data to cache
            ttl: Optional custom TTL (default: 24 hours)

        Returns:
            True if successful
        """
        cache_key = self._make_company_key(company_name, industry)

        # Add metadata
        enriched_result = {
            **qualification_result,
            "company_name": company_name,
            "industry": industry,
            "cache_ttl_hours": (ttl or self.default_ttl) / 3600
        }

        success = await self.set(cache_key, enriched_result, ttl)

        if success:
            logger.info(
                f"💾 Cached qualification: {company_name} "
                f"(TTL: {(ttl or self.default_ttl) / 3600} hours)"
            )

        return success

    async def get_qualification_stats(self) -> Dict[str, Any]:
        """
        Get detailed qualification cache statistics with savings.

        Returns:
            Dict with stats including estimated savings
        """
        stats = await self.get_stats()

        # Calculate cost savings
        cerebras_cost = 0.000006  # Cerebras qualification cost
        cerebras_latency_s = 0.633  # Average qualification time

        estimated_savings_usd = stats["hits"] * cerebras_cost
        time_saved_seconds = stats["hits"] * cerebras_latency_s

        return {
            **stats,
            "estimated_savings_usd": estimated_savings_usd,
            "time_saved_seconds": time_saved_seconds,
            "avg_qualification_cost_usd": cerebras_cost,
            "avg_qualification_latency_s": cerebras_latency_s,
        }


# For backward compatibility / convenience
async def get_qualification_cache() -> QualificationCache:
    """
    Get singleton qualification cache instance.

    Returns:
        QualificationCache instance
    """
    from .base import get_redis_client
    redis_client = await get_redis_client()
    return QualificationCache(redis_client)
