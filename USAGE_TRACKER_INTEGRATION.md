# Usage Tracker Integration Guide

## Overview

The unified `UsageTracker` provides comprehensive API call tracking across all LLM providers (Cerebras, OpenRouter, Ollama, Anthropic, DeepSeek) with real-time metrics, cost analysis, and performance monitoring.

## Architecture

```
┌─────────────────┐
│  ModelRouter /  │
│   LLMRouter     │
└────────┬────────┘
         │
         │ After each API call
         │
         ▼
┌─────────────────┐       ┌──────────────┐
│  UsageTracker   │◄─────►│ PostgreSQL   │
│                 │       │ api_call_logs│
└────────┬────────┘       └──────────────┘
         │
         │ Cache metrics
         │
         ▼
┌─────────────────┐
│     Redis       │
│  5-min cache    │
└─────────────────┘
```

## Quick Start

### 1. Import Dependencies

```python
from app.services.usage_tracker import UsageTracker
from app.models.unified_api_call import ProviderType, OperationType
from app.models.database import get_db
from app.core.cache import get_cache_manager
```

### 2. Initialize Tracker

```python
# In FastAPI endpoint
from fastapi import Depends
from sqlalchemy.orm import Session

@app.post("/api/qualify-lead")
async def qualify_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db)
):
    # Create tracker with Redis caching
    cache_manager = get_cache_manager()
    tracker = UsageTracker(db=db, redis_client=cache_manager._redis)

    # Your API call logic here...
```

### 3. Log API Calls

```python
# After successful API call
log_entry = await tracker.log_api_call(
    provider=ProviderType.CEREBRAS,
    model="llama3.1-8b",
    endpoint="/chat/completions",
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    latency_ms=response_time_ms,
    operation_type=OperationType.QUALIFICATION,
    cache_hit=False,
    user_id="user_123",  # Optional
    success=True
)
```

### 4. Handle Failures

```python
# After failed API call
try:
    response = cerebras_client.call()
except Exception as e:
    await tracker.log_api_call(
        provider=ProviderType.CEREBRAS,
        model="llama3.1-8b",
        endpoint="/chat/completions",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=int(time_elapsed * 1000),
        operation_type=OperationType.QUALIFICATION,
        success=False,
        error_message=str(e)
    )
    raise
```

## Integration Examples

### Example 1: ModelRouter Integration

```python
# backend/app/services/model_router.py

from app.services.usage_tracker import UsageTracker
from app.models.unified_api_call import ProviderType, OperationType
import time

class ModelRouter:
    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.tracker = UsageTracker(db=db, redis_client=redis_client)

    async def route_request(
        self,
        prompt: str,
        operation_type: OperationType = OperationType.OTHER,
        user_id: str = None
    ):
        """Route request to best provider and log usage"""

        # Select provider based on requirements
        provider = self._select_provider(operation_type)

        start_time = time.time()

        try:
            # Make API call
            response = await self._call_provider(provider, prompt)

            latency_ms = int((time.time() - start_time) * 1000)

            # Log successful call
            await self.tracker.log_api_call(
                provider=provider,
                model=response.model,
                endpoint=self._get_endpoint(provider),
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                latency_ms=latency_ms,
                operation_type=operation_type,
                user_id=user_id,
                success=True
            )

            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            # Log failed call
            await self.tracker.log_api_call(
                provider=provider,
                model=self._get_default_model(provider),
                endpoint=self._get_endpoint(provider),
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                operation_type=operation_type,
                user_id=user_id,
                success=False,
                error_message=str(e)
            )

            raise
```

### Example 2: Real-Time Metrics Dashboard Endpoint

```python
# backend/app/api/usage.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.core.cache import get_cache_manager
from app.services.usage_tracker import UsageTracker

router = APIRouter(prefix="/api/usage", tags=["usage"])

@router.get("/metrics/realtime")
async def get_realtime_metrics(
    db: Session = Depends(get_db)
):
    """
    Get real-time usage metrics for last 24 hours.

    Cache hit rate target: >90%
    Response time: <10ms (cached), <100ms (uncached)
    """
    cache_manager = get_cache_manager()
    tracker = UsageTracker(db=db, redis_client=cache_manager._redis)

    metrics = await tracker.get_real_time_metrics()

    return {
        "success": True,
        "data": metrics
    }

@router.get("/metrics/aggregates")
async def get_usage_aggregates(
    days: int = 7,
    interval: str = "day",
    provider: str = None,
    db: Session = Depends(get_db)
):
    """
    Get time-series aggregations.

    Args:
        days: Number of days to aggregate (default: 7)
        interval: 'hour', 'day', or 'month'
        provider: Filter by provider (cerebras, anthropic, etc.)
    """
    from datetime import datetime, timedelta
    from app.models.unified_api_call import ProviderType

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    tracker = UsageTracker(db=db)

    provider_enum = None
    if provider:
        provider_enum = ProviderType(provider)

    aggregates = tracker.get_aggregates(
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        provider=provider_enum
    )

    return {
        "success": True,
        "data": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "interval": interval,
            "provider": provider,
            "aggregates": aggregates
        }
    }

@router.get("/costs/by-provider")
async def get_cost_breakdown(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get cost breakdown by provider for last N days"""
    from datetime import datetime, timedelta

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    tracker = UsageTracker(db=db)

    cost_breakdown = tracker.get_cost_by_provider(
        start_date=start_date,
        end_date=end_date
    )

    total_cost = sum(cost_breakdown.values())

    return {
        "success": True,
        "data": {
            "total_cost_usd": total_cost,
            "by_provider": cost_breakdown,
            "period_days": days
        }
    }

@router.get("/performance/latency")
async def get_latency_metrics(
    days: int = 7,
    provider: str = None,
    db: Session = Depends(get_db)
):
    """Get latency percentiles (p50, p95, p99)"""
    from datetime import datetime, timedelta
    from app.models.unified_api_call import ProviderType

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    tracker = UsageTracker(db=db)

    provider_enum = None
    if provider:
        provider_enum = ProviderType(provider)

    percentiles = tracker.get_latency_percentiles(
        start_date=start_date,
        end_date=end_date,
        provider=provider_enum
    )

    success_rate = tracker.get_success_rate(
        start_date=start_date,
        end_date=end_date,
        provider=provider_enum
    )

    return {
        "success": True,
        "data": {
            "latency_percentiles_ms": percentiles,
            "success_rate_percent": success_rate,
            "period_days": days,
            "provider": provider
        }
    }
```

### Example 3: Background Job Cost Monitoring

```python
# backend/app/tasks/monitoring_tasks.py

from celery import Task
from app.celery_app import celery_app
from app.models.database import SessionLocal
from app.services.usage_tracker import UsageTracker
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="monitor_api_costs")
def monitor_api_costs():
    """
    Daily task to monitor API costs and alert if thresholds exceeded.

    Schedule: Daily at 9 AM UTC
    """
    db = SessionLocal()
    tracker = UsageTracker(db=db)

    try:
        # Check last 24 hours
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=24)

        # Get cost breakdown
        costs = tracker.get_cost_by_provider(
            start_date=start_date,
            end_date=end_date
        )

        total_cost = sum(costs.values())

        # Alert thresholds
        DAILY_COST_THRESHOLD = 50.00  # $50/day

        if total_cost > DAILY_COST_THRESHOLD:
            logger.warning(
                f"API costs exceeded threshold: ${total_cost:.2f} > ${DAILY_COST_THRESHOLD:.2f}"
            )
            # Send alert (email, Slack, etc.)
            # send_cost_alert(total_cost, costs)

        logger.info(f"Daily API costs: ${total_cost:.4f}")

        return {
            "success": True,
            "total_cost": total_cost,
            "by_provider": costs
        }

    except Exception as e:
        logger.error(f"Cost monitoring failed: {e}")
        raise
    finally:
        db.close()
```

## Cost Calculation Reference

### Provider Pricing Models

| Provider | Model | Pricing Type | Rate |
|----------|-------|--------------|------|
| Cerebras | llama3.1-8b | Per request | $0.000006/request |
| Anthropic | claude-3-sonnet | Per token | $3/M input, $15/M output |
| Anthropic | claude-3-haiku | Per token | $0.25/M input, $1.25/M output |
| DeepSeek | deepseek-chat | Per token | $0.27/M input, $1.10/M output |
| DeepSeek | deepseek-reasoner | Per token | $0.55/M input, $2.19/M output |
| OpenRouter | * (default) | Per token | $0.50/M input, $1.50/M output |
| Ollama | * (local) | Free | $0 |

### Updating Pricing

To update pricing, edit `PROVIDER_PRICING` dict in `backend/app/services/usage_tracker.py`:

```python
PROVIDER_PRICING = {
    ProviderType.CEREBRAS: {
        "model": "llama3.1-8b",
        "per_request": 0.000006,  # Update this value
        "type": "per_request"
    },
    # ... other providers
}
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Write latency | <10ms | Async logging with no blocking |
| Query latency (cached) | <10ms | Redis cache hit |
| Query latency (uncached) | <100ms | PostgreSQL aggregation |
| Cache hit rate | >90% | Real-time metrics caching |
| Cost accuracy | <1% error | Within provider billing tolerance |

## Database Migration

Run the migration to create the `api_call_logs` table:

```bash
cd backend
./venv/bin/python -m alembic upgrade head
```

Migration file: `backend/alembic/versions/010_add_unified_api_call_tracking.py`

**Note**: The migration automatically migrates existing `cerebras_api_calls` data to the new unified table.

## Redis Cache Keys

| Key | TTL | Contents |
|-----|-----|----------|
| `usage:realtime:last24h` | 5 min | Real-time metrics for last 24 hours |

## Monitoring Queries

### Top 10 Most Expensive Operations

```sql
SELECT
    operation_type,
    provider,
    COUNT(*) as total_calls,
    SUM(cost_usd) as total_cost,
    AVG(latency_ms) as avg_latency
FROM api_call_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY operation_type, provider
ORDER BY total_cost DESC
LIMIT 10;
```

### Daily Cost Trends

```sql
SELECT
    DATE_TRUNC('day', created_at) as day,
    provider,
    SUM(cost_usd) as daily_cost,
    COUNT(*) as daily_requests
FROM api_call_logs
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY day, provider
ORDER BY day DESC, daily_cost DESC;
```

### Error Rate by Provider

```sql
SELECT
    provider,
    COUNT(*) as total_calls,
    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_calls,
    ROUND(100.0 * SUM(CASE WHEN success = false THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate_percent
FROM api_call_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY provider
ORDER BY error_rate_percent DESC;
```

## Troubleshooting

### High Write Latency (>10ms)

1. Check database connection pool settings
2. Verify Redis is available for cache invalidation
3. Consider batching writes in high-volume scenarios

### Low Cache Hit Rate (<90%)

1. Increase Redis cache TTL (current: 5 minutes)
2. Check Redis memory limits
3. Verify cache key generation logic

### Inaccurate Cost Calculations

1. Verify provider pricing in `PROVIDER_PRICING` dict
2. Check token count accuracy from provider responses
3. Compare with provider billing statements

### Migration Errors

If migration fails due to missing `pgvector` module:

```bash
cd backend
./venv/bin/pip install pgvector
./venv/bin/python -m alembic upgrade head
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/metrics/realtime` | GET | Last 24h metrics (cached) |
| `/api/usage/metrics/aggregates` | GET | Time-series aggregations |
| `/api/usage/costs/by-provider` | GET | Cost breakdown by provider |
| `/api/usage/performance/latency` | GET | Latency percentiles + success rate |

## Next Steps

1. Add usage tracking to all LLM provider calls in `ModelRouter` and `LLMRouter`
2. Create frontend dashboard for real-time metrics visualization
3. Set up alerts for cost thresholds and error rates
4. Implement usage-based rate limiting per user/operation
5. Add export functionality for billing reports

## Support

For issues or questions:
- Check logs in `backend/app/services/usage_tracker.py`
- Review unit tests in `backend/tests/test_usage_tracker.py`
- Consult CLAUDE.md for project-specific guidelines
