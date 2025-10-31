"""
Metrics API endpoints.

Provides REST API for querying metrics data, including:
- Agent execution metrics
- Cost tracking by provider
- System performance metrics
- Business KPIs
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.services.metrics_service import MetricsService
from app.schemas.metrics import (
    MetricsSummaryResponse,
    AgentMetricResponse,
    ProviderCostMetrics,
    SystemMetricResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummaryResponse, status_code=200)
async def get_metrics_summary(
    start_date: Optional[datetime] = Query(
        None,
        description="Start date for metrics (ISO 8601). Defaults to 7 days ago."
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="End date for metrics (ISO 8601). Defaults to now."
    ),
    db: Session = Depends(get_db)
) -> MetricsSummaryResponse:
    """
    Get comprehensive metrics summary for dashboard.

    Returns aggregated metrics across all categories:
    - API performance (request count, response times, error rates)
    - Agent performance (execution count, latency, success rate)
    - Cost tracking (total cost, breakdown by provider)
    - Business metrics (leads processed, qualification rate)

    **Performance**: Cached for 5 minutes for efficiency.

    **Example**:
    ```
    GET /api/v1/metrics/summary?start_date=2025-10-23T00:00:00Z&end_date=2025-10-30T23:59:59Z
    ```
    """
    try:
        # Default date range: last 7 days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()

        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date"
            )

        # Get summary from service
        service = MetricsService(db)
        summary = service.get_metrics_summary(start_date, end_date)

        return MetricsSummaryResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching metrics summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve metrics summary"
        )


@router.get("/agents", response_model=List[AgentMetricResponse], status_code=200)
async def get_agent_metrics(
    start_date: Optional[datetime] = Query(
        None,
        description="Start date for metrics (ISO 8601). Defaults to 7 days ago."
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="End date for metrics (ISO 8601). Defaults to now."
    ),
    agent_type: Optional[str] = Query(
        None,
        description="Filter by specific agent type (e.g., 'qualification', 'enrichment')"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return"
    ),
    db: Session = Depends(get_db)
) -> List[AgentMetricResponse]:
    """
    Get agent execution metrics with optional filtering.

    Returns detailed metrics for agent executions:
    - Execution counts (total, successful, failed)
    - Latency statistics (avg, min, max)
    - Cost tracking (total, average per execution)
    - Success rate

    **Grouping**: Results are grouped by agent_type and date.

    **Example**:
    ```
    GET /api/v1/metrics/agents?agent_type=qualification&start_date=2025-10-23T00:00:00Z
    ```
    """
    try:
        # Default date range: last 7 days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()

        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date"
            )

        # Get metrics from service
        service = MetricsService(db)
        metrics = service.get_agent_metrics(start_date, end_date, agent_type)

        # Apply limit
        metrics = metrics[:limit]

        return [AgentMetricResponse(**m) for m in metrics]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve agent metrics"
        )


@router.get("/costs", response_model=List[ProviderCostMetrics], status_code=200)
async def get_cost_metrics(
    start_date: Optional[datetime] = Query(
        None,
        description="Start date for metrics (ISO 8601). Defaults to 7 days ago."
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="End date for metrics (ISO 8601). Defaults to now."
    ),
    provider: Optional[str] = Query(
        None,
        description="Filter by specific provider (cerebras, claude, deepseek, ollama)"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return"
    ),
    db: Session = Depends(get_db)
) -> List[ProviderCostMetrics]:
    """
    Get cost metrics by AI provider.

    Returns detailed cost tracking:
    - API calls per provider
    - Token usage (input + output)
    - Total cost in USD
    - Average latency

    **Grouping**: Results are grouped by provider and date.

    **Use Case**: Monitor cost distribution across providers to validate
    80/20 split (RunPod 80%, Cerebras 20%) for cost optimization.

    **Example**:
    ```
    GET /api/v1/metrics/costs?provider=cerebras&start_date=2025-10-23T00:00:00Z
    ```
    """
    try:
        # Default date range: last 7 days
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()

        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before end_date"
            )

        # Get metrics from service
        service = MetricsService(db)
        metrics = service.get_cost_by_provider(start_date, end_date)

        # Filter by provider if specified
        if provider:
            metrics = [m for m in metrics if m["provider"] == provider.lower()]

        # Apply limit
        metrics = metrics[:limit]

        return [ProviderCostMetrics(**m) for m in metrics]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cost metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cost metrics"
        )


@router.post("/track", status_code=201)
async def track_metric(
    metric_name: str = Query(..., description="Name of the metric to track"),
    metric_value: float = Query(..., description="Numeric value of the metric"),
    metric_unit: str = Query(..., description="Unit of measurement (ms, %, count, etc.)"),
    category: str = Query(..., description="Category (performance, error, resource, business)"),
    subcategory: Optional[str] = Query(None, description="Optional subcategory"),
    agent_type: Optional[str] = Query(None, description="Agent type if agent-specific"),
    endpoint: Optional[str] = Query(None, description="Endpoint path if endpoint-specific"),
    db: Session = Depends(get_db)
):
    """
    Track a custom system metric.

    **Use Case**: Allow application code to track custom business metrics
    that aren't automatically captured by middleware.

    **Example**:
    ```
    POST /api/v1/metrics/track?metric_name=lead_import_throughput&metric_value=75.5&metric_unit=leads_per_second&category=business
    ```
    """
    try:
        service = MetricsService(db)
        metric = service.track_system_metric(
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            category=category,
            subcategory=subcategory,
            agent_type=agent_type,
            endpoint=endpoint
        )

        return {
            "message": "Metric tracked successfully",
            "metric_id": metric.id,
            "recorded_at": metric.recorded_at
        }

    except Exception as e:
        logger.error(f"Error tracking metric: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to track metric"
        )


@router.get("/cache", status_code=200)
async def get_cache_metrics():
    """
    Get Redis cache performance metrics and ROI calculations.

    Returns detailed statistics for all cache types:
    - **EnrichmentCache**: LinkedIn profile caching (saves $0.10 + 3s per hit)
    - **QualificationCache**: Company qualification caching (saves $0.000006 + 633ms per hit)

    Metrics include:
    - Hit/miss counts and hit rate percentage
    - Estimated cost savings in USD
    - Time saved in seconds
    - Number of cached items

    **Use Case**: Monitor cache effectiveness and validate ROI from caching strategy.
    With typical duplicate rates (20-50%), caching can save $30-50 per 1000 leads.

    **Example**:
    ```
    GET /api/v1/metrics/cache
    ```

    **Response**:
    ```json
    {
      "enrichment_cache": {
        "cached_items": 150,
        "hits": 45,
        "misses": 105,
        "hit_rate_pct": 30.0,
        "estimated_savings_usd": 4.50,
        "time_saved_seconds": 135.0
      },
      "qualification_cache": {
        "cached_items": 200,
        "hits": 80,
        "misses": 120,
        "hit_rate_pct": 40.0,
        "estimated_savings_usd": 0.00048,
        "time_saved_seconds": 50.64
      },
      "total_savings_usd": 4.50048,
      "total_time_saved_seconds": 185.64
    }
    ```
    """
    try:
        from app.services.cache.enrichment_cache import get_enrichment_cache
        from app.services.cache.qualification_cache import get_qualification_cache

        # Get both cache instances
        enrichment_cache = await get_enrichment_cache()
        qualification_cache = await get_qualification_cache()

        # Fetch stats from both caches
        enrichment_stats = await enrichment_cache.get_enrichment_stats()
        qualification_stats = await qualification_cache.get_qualification_stats()

        # Calculate totals
        total_savings_usd = (
            enrichment_stats["estimated_savings_usd"] +
            qualification_stats["estimated_savings_usd"]
        )
        total_time_saved_seconds = (
            enrichment_stats["time_saved_seconds"] +
            qualification_stats["time_saved_seconds"]
        )

        return {
            "enrichment_cache": enrichment_stats,
            "qualification_cache": qualification_stats,
            "total_savings_usd": round(total_savings_usd, 5),
            "total_time_saved_seconds": round(total_time_saved_seconds, 2),
            "cache_enabled": True
        }

    except Exception as e:
        logger.error(f"Error fetching cache metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cache metrics: {str(e)}"
        )
