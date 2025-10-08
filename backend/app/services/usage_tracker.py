"""
Unified Usage Tracker for Multi-Provider API Call Monitoring

Provides comprehensive tracking and aggregation for all LLM providers
with Redis caching for real-time metrics and PostgreSQL for long-term analytics.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func as sql_func, and_, or_, text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging
from redis import asyncio as aioredis

from app.models.unified_api_call import APICallLog, ProviderType, OperationType

logger = logging.getLogger(__name__)


# Provider pricing (USD per million tokens or per request)
PROVIDER_PRICING = {
    ProviderType.CEREBRAS: {
        "model": "llama3.1-8b",
        "per_request": 0.000006,  # $0.000006 per request
        "type": "per_request"
    },
    ProviderType.ANTHROPIC: {
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},  # per 1M tokens
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "type": "per_token"
    },
    ProviderType.DEEPSEEK: {
        "deepseek-chat": {"input": 0.27, "output": 1.10},  # per 1M tokens
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
        "type": "per_token"
    },
    ProviderType.OPENROUTER: {
        # Model-specific pricing from OpenRouter
        "type": "per_token",
        "default": {"input": 0.50, "output": 1.50}  # Fallback pricing
    },
    ProviderType.OLLAMA: {
        "type": "free"  # Local inference
    }
}


class UsageTracker:
    """
    Unified usage tracker for multi-provider API calls.

    Features:
    - Async logging with <10ms write latency
    - Redis caching for real-time metrics (5min TTL, >90% hit rate)
    - Time-series aggregations (hourly, daily, monthly)
    - Cost analysis by provider/model/operation
    - Latency percentile calculations (p50, p95, p99)
    """

    REDIS_CACHE_KEY = "usage:realtime:last24h"
    REDIS_CACHE_TTL = 300  # 5 minutes

    def __init__(self, db: Session, redis_client: Optional[aioredis.Redis] = None):
        """
        Initialize usage tracker.

        Args:
            db: SQLAlchemy database session
            redis_client: Redis client for caching (optional)
        """
        self.db = db
        self.redis = redis_client
        self._cache_enabled = redis_client is not None

    @staticmethod
    def calculate_cost(
        provider: ProviderType,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> tuple[float, Optional[float], Optional[float]]:
        """
        Calculate API call cost based on provider pricing.

        Args:
            provider: LLM provider type
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Tuple of (total_cost_usd, input_cost_usd, output_cost_usd)
        """
        pricing = PROVIDER_PRICING.get(provider)
        if not pricing:
            return (0.0, None, None)

        if pricing["type"] == "free":
            return (0.0, 0.0, 0.0)

        if pricing["type"] == "per_request":
            return (pricing["per_request"], None, None)

        # Per-token pricing
        if provider == ProviderType.ANTHROPIC or provider == ProviderType.DEEPSEEK:
            model_pricing = pricing.get(model, {})
            if not model_pricing or "input" not in model_pricing:
                return (0.0, None, None)

            input_cost = (prompt_tokens / 1_000_000) * model_pricing["input"]
            output_cost = (completion_tokens / 1_000_000) * model_pricing["output"]
            total_cost = input_cost + output_cost

            return (round(total_cost, 8), round(input_cost, 8), round(output_cost, 8))

        if provider == ProviderType.OPENROUTER:
            # Use default pricing for OpenRouter
            default_pricing = pricing["default"]
            input_cost = (prompt_tokens / 1_000_000) * default_pricing["input"]
            output_cost = (completion_tokens / 1_000_000) * default_pricing["output"]
            total_cost = input_cost + output_cost

            return (round(total_cost, 8), round(input_cost, 8), round(output_cost, 8))

        return (0.0, None, None)

    async def log_api_call(
        self,
        provider: ProviderType,
        model: str,
        endpoint: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        operation_type: OperationType = OperationType.OTHER,
        cache_hit: bool = False,
        user_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> APICallLog:
        """
        Log an API call asynchronously with <10ms write latency.

        Args:
            provider: LLM provider type
            model: Model name
            endpoint: API endpoint
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            latency_ms: Response latency in milliseconds
            operation_type: Type of operation (qualification, research, etc.)
            cache_hit: Whether cached response was used
            user_id: User or system identifier
            success: Whether call succeeded
            error_message: Error details if call failed

        Returns:
            Created APICallLog instance
        """
        total_tokens = prompt_tokens + completion_tokens

        # Calculate cost
        cost_usd, input_cost, output_cost = self.calculate_cost(
            provider, model, prompt_tokens, completion_tokens
        )

        # Create log entry
        log_entry = APICallLog(
            provider=provider,
            model=model,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            user_id=user_id,
            operation_type=operation_type,
            success=success,
            error_message=error_message
        )

        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)

        # Invalidate Redis cache asynchronously (don't block)
        if self._cache_enabled and self.redis:
            try:
                await self.redis.delete(self.REDIS_CACHE_KEY)
            except Exception as e:
                logger.debug(f"Failed to invalidate Redis cache: {e}")

        logger.info(
            f"Logged API call: provider={provider.value}, model={model}, "
            f"cost=${cost_usd:.6f}, latency={latency_ms}ms"
        )

        return log_entry

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time usage metrics for last 24 hours with Redis caching.

        Cache hit rate target: >90%
        Query latency target: <10ms (cached), <100ms (uncached)

        Returns:
            Dict with total_cost, total_requests, by_provider, by_operation
        """
        # Try Redis cache first
        if self._cache_enabled and self.redis:
            try:
                cached = await self.redis.get(self.REDIS_CACHE_KEY)
                if cached:
                    logger.debug("Real-time metrics: Redis cache HIT")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")

        # Calculate from database
        logger.debug("Real-time metrics: Redis cache MISS, querying DB")
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

        # Aggregate queries
        stmt = select(
            sql_func.count(APICallLog.id).label("total_requests"),
            sql_func.sum(APICallLog.cost_usd).label("total_cost"),
            sql_func.avg(APICallLog.latency_ms).label("avg_latency"),
            APICallLog.provider,
        ).where(
            APICallLog.created_at >= twenty_four_hours_ago
        ).group_by(APICallLog.provider)

        results = self.db.execute(stmt).all()

        # Build metrics structure
        metrics = {
            "total_cost": 0.0,
            "total_requests": 0,
            "avg_latency_ms": 0.0,
            "by_provider": {},
            "by_operation": {},
            "cached_at": datetime.utcnow().isoformat()
        }

        for row in results:
            metrics["total_requests"] += row.total_requests
            metrics["total_cost"] += float(row.total_cost or 0.0)

            metrics["by_provider"][row.provider.value] = {
                "requests": row.total_requests,
                "cost_usd": float(row.total_cost or 0.0),
                "avg_latency_ms": int(row.avg_latency or 0)
            }

        # Calculate overall average latency
        if metrics["total_requests"] > 0:
            total_latency = sum(
                p["avg_latency_ms"] * p["requests"]
                for p in metrics["by_provider"].values()
            )
            metrics["avg_latency_ms"] = int(total_latency / metrics["total_requests"])

        # Get operation breakdown
        operation_stmt = select(
            sql_func.count(APICallLog.id).label("requests"),
            sql_func.sum(APICallLog.cost_usd).label("cost"),
            APICallLog.operation_type,
        ).where(
            APICallLog.created_at >= twenty_four_hours_ago
        ).group_by(APICallLog.operation_type)

        operation_results = self.db.execute(operation_stmt).all()

        for row in operation_results:
            metrics["by_operation"][row.operation_type.value] = {
                "requests": row.requests,
                "cost_usd": float(row.cost or 0.0)
            }

        # Cache in Redis
        if self._cache_enabled and self.redis:
            try:
                await self.redis.setex(
                    self.REDIS_CACHE_KEY,
                    self.REDIS_CACHE_TTL,
                    json.dumps(metrics)
                )
                logger.debug(f"Cached real-time metrics (TTL: {self.REDIS_CACHE_TTL}s)")
            except Exception as e:
                logger.warning(f"Failed to cache metrics in Redis: {e}")

        return metrics

    def get_aggregates(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str = "hour",
        provider: Optional[ProviderType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get time-series aggregations for usage analytics.

        Args:
            start_date: Start of date range
            end_date: End of date range
            interval: Aggregation interval ('hour', 'day', 'month')
            provider: Filter by specific provider (optional)

        Returns:
            List of aggregated metrics by time interval
        """
        # Validate interval
        if interval not in ["hour", "day", "month"]:
            raise ValueError("interval must be 'hour', 'day', or 'month'")

        # Build query with DATE_TRUNC
        trunc_func = text(f"DATE_TRUNC('{interval}', created_at)")

        stmt = select(
            trunc_func.label("period"),
            sql_func.count(APICallLog.id).label("total_requests"),
            sql_func.sum(APICallLog.cost_usd).label("total_cost"),
            sql_func.avg(APICallLog.latency_ms).label("avg_latency"),
            sql_func.sum(APICallLog.total_tokens).label("total_tokens"),
        ).where(
            and_(
                APICallLog.created_at >= start_date,
                APICallLog.created_at <= end_date
            )
        )

        if provider:
            stmt = stmt.where(APICallLog.provider == provider)

        stmt = stmt.group_by(text("period")).order_by(text("period"))

        results = self.db.execute(stmt).all()

        return [
            {
                "period": row.period.isoformat(),
                "total_requests": row.total_requests,
                "total_cost_usd": float(row.total_cost or 0.0),
                "avg_latency_ms": int(row.avg_latency or 0),
                "total_tokens": row.total_tokens or 0,
            }
            for row in results
        ]

    def get_cost_by_provider(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, float]:
        """
        Get total cost breakdown by provider.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict mapping provider name to total cost
        """
        stmt = select(
            APICallLog.provider,
            sql_func.sum(APICallLog.cost_usd).label("total_cost")
        ).where(
            and_(
                APICallLog.created_at >= start_date,
                APICallLog.created_at <= end_date
            )
        ).group_by(APICallLog.provider)

        results = self.db.execute(stmt).all()

        return {
            row.provider.value: float(row.total_cost or 0.0)
            for row in results
        }

    def get_latency_percentiles(
        self,
        start_date: datetime,
        end_date: datetime,
        provider: Optional[ProviderType] = None
    ) -> Dict[str, int]:
        """
        Calculate latency percentiles (p50, p95, p99) for performance monitoring.

        Args:
            start_date: Start of date range
            end_date: End of date range
            provider: Filter by specific provider (optional)

        Returns:
            Dict with p50, p95, p99 latency values in milliseconds
        """
        # Use PostgreSQL percentile_cont function
        conditions = [
            APICallLog.created_at >= start_date,
            APICallLog.created_at <= end_date
        ]

        if provider:
            conditions.append(APICallLog.provider == provider)

        stmt = select(
            sql_func.percentile_cont(0.50).within_group(APICallLog.latency_ms).label("p50"),
            sql_func.percentile_cont(0.95).within_group(APICallLog.latency_ms).label("p95"),
            sql_func.percentile_cont(0.99).within_group(APICallLog.latency_ms).label("p99"),
        ).where(and_(*conditions))

        result = self.db.execute(stmt).first()

        if not result:
            return {"p50": 0, "p95": 0, "p99": 0}

        return {
            "p50": int(result.p50 or 0),
            "p95": int(result.p95 or 0),
            "p99": int(result.p99 or 0),
        }

    def get_success_rate(
        self,
        start_date: datetime,
        end_date: datetime,
        provider: Optional[ProviderType] = None
    ) -> float:
        """
        Calculate API call success rate.

        Args:
            start_date: Start of date range
            end_date: End of date range
            provider: Filter by specific provider (optional)

        Returns:
            Success rate as percentage (0.0 to 100.0)
        """
        conditions = [
            APICallLog.created_at >= start_date,
            APICallLog.created_at <= end_date
        ]

        if provider:
            conditions.append(APICallLog.provider == provider)

        stmt = select(
            sql_func.count(APICallLog.id).label("total"),
            sql_func.sum(sql_func.cast(APICallLog.success, Integer)).label("successful")
        ).where(and_(*conditions))

        result = self.db.execute(stmt).first()

        if not result or result.total == 0:
            return 0.0

        success_rate = (result.successful / result.total) * 100
        return round(success_rate, 2)
