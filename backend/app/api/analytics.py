"""
Analytics API endpoint for AI cost tracking.

Provides comprehensive cost analytics including:
- Total cost and request metrics
- Breakdown by agent, lead, and provider
- Cache hit statistics with savings
- Time-series data for visualization
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from app.models.database import get_db
from app.models.ai_cost_tracking import AICostTracking
from app.models.lead import Lead
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Pydantic schemas for response
from pydantic import BaseModel, Field


class AgentCostBreakdown(BaseModel):
    """Cost breakdown for a single agent."""
    agent_type: str
    agent_mode: Optional[str] = None
    total_requests: int
    total_cost_usd: float
    avg_cost_per_request: float
    avg_latency_ms: float
    primary_provider: str
    primary_model: str


class LeadCostBreakdown(BaseModel):
    """Cost breakdown for a single lead."""
    lead_id: int
    company_name: str
    total_cost_usd: float
    total_requests: int
    agents_used: List[str]


class CacheStats(BaseModel):
    """Cache hit statistics."""
    total_requests: int
    cache_hits: int
    cache_hit_rate: float
    estimated_savings_usd: float


class TimeSeriesPoint(BaseModel):
    """Single point in time series."""
    date: str
    total_cost_usd: float
    total_requests: int


class AICostAnalyticsResponse(BaseModel):
    """Response model for AI cost analytics."""
    total_cost_usd: float
    total_requests: int
    by_agent: List[AgentCostBreakdown]
    by_lead: List[LeadCostBreakdown]
    cache_stats: CacheStats
    time_series: List[TimeSeriesPoint]


@router.get("/ai-costs", response_model=AICostAnalyticsResponse)
async def get_ai_cost_analytics(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    lead_id: Optional[int] = Query(None, description="Filter by lead ID"),
    db: Session = Depends(get_db)
) -> AICostAnalyticsResponse:
    """
    Get comprehensive AI cost analytics with optional filters.

    Query Parameters:
    - agent_type: Filter by specific agent (e.g., "qualification", "enrichment")
    - start_date: Filter by start date (ISO 8601 format)
    - end_date: Filter by end date (ISO 8601 format)
    - lead_id: Filter by specific lead ID

    Returns:
    - Total cost and request count
    - Breakdown by agent type with performance metrics
    - Breakdown by lead with company names
    - Cache hit statistics with estimated savings
    - Daily time-series data for visualization
    """
    try:
        # Build base query with filters
        filters = []

        if agent_type:
            filters.append(AICostTracking.agent_type == agent_type)

        if start_date:
            filters.append(AICostTracking.timestamp >= start_date)

        if end_date:
            filters.append(AICostTracking.timestamp <= end_date)

        if lead_id:
            filters.append(AICostTracking.lead_id == lead_id)

        # Get total cost and requests
        total_query = db.query(
            func.sum(AICostTracking.cost_usd).label("total_cost"),
            func.count(AICostTracking.id).label("total_requests")
        )

        if filters:
            total_query = total_query.filter(and_(*filters))

        total_result = total_query.first()
        total_cost = float(total_result.total_cost or Decimal("0.0"))
        total_requests = total_result.total_requests or 0

        # Get breakdown by agent
        agent_breakdown = _get_agent_breakdown(db, filters)

        # Get breakdown by lead
        lead_breakdown = _get_lead_breakdown(db, filters)

        # Get cache statistics
        cache_stats = _get_cache_statistics(db, filters)

        # Get time series data
        time_series = _get_time_series(db, filters)

        logger.info(
            f"Analytics generated: total_cost=${total_cost:.6f}, "
            f"requests={total_requests}, agents={len(agent_breakdown)}, "
            f"leads={len(lead_breakdown)}"
        )

        return AICostAnalyticsResponse(
            total_cost_usd=round(total_cost, 6),
            total_requests=total_requests,
            by_agent=agent_breakdown,
            by_lead=lead_breakdown,
            cache_stats=cache_stats,
            time_series=time_series
        )

    except Exception as e:
        logger.error(f"Failed to generate analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate analytics: {str(e)}")


def _get_agent_breakdown(db: Session, filters: List) -> List[AgentCostBreakdown]:
    """Get cost breakdown by agent type."""
    query = db.query(
        AICostTracking.agent_type,
        AICostTracking.agent_mode,
        func.count(AICostTracking.id).label("total_requests"),
        func.sum(AICostTracking.cost_usd).label("total_cost"),
        func.avg(AICostTracking.cost_usd).label("avg_cost"),
        func.avg(AICostTracking.latency_ms).label("avg_latency")
    ).group_by(
        AICostTracking.agent_type,
        AICostTracking.agent_mode
    )

    if filters:
        query = query.filter(and_(*filters))

    results = query.all()

    breakdown = []
    for row in results:
        # Get primary provider and model (most used)
        provider_query = db.query(
            AICostTracking.provider,
            AICostTracking.model,
            func.count(AICostTracking.id).label("usage_count")
        ).filter(
            AICostTracking.agent_type == row.agent_type
        ).group_by(
            AICostTracking.provider,
            AICostTracking.model
        ).order_by(
            func.count(AICostTracking.id).desc()
        ).first()

        if provider_query:
            primary_provider = provider_query.provider
            primary_model = provider_query.model
        else:
            primary_provider = "unknown"
            primary_model = "unknown"

        breakdown.append(AgentCostBreakdown(
            agent_type=row.agent_type,
            agent_mode=row.agent_mode,
            total_requests=row.total_requests,
            total_cost_usd=round(float(row.total_cost or Decimal("0.0")), 6),
            avg_cost_per_request=round(float(row.avg_cost or Decimal("0.0")), 8),
            avg_latency_ms=round(float(row.avg_latency or 0), 2),
            primary_provider=primary_provider,
            primary_model=primary_model
        ))

    # Sort by total cost descending
    breakdown.sort(key=lambda x: x.total_cost_usd, reverse=True)

    return breakdown


def _get_lead_breakdown(db: Session, filters: List) -> List[LeadCostBreakdown]:
    """Get cost breakdown by lead."""
    # Join with leads table to get company names
    query = db.query(
        AICostTracking.lead_id,
        Lead.company_name,
        func.count(AICostTracking.id).label("total_requests"),
        func.sum(AICostTracking.cost_usd).label("total_cost")
    ).join(
        Lead, AICostTracking.lead_id == Lead.id
    ).filter(
        AICostTracking.lead_id.isnot(None)
    ).group_by(
        AICostTracking.lead_id,
        Lead.company_name
    )

    if filters:
        query = query.filter(and_(*filters))

    results = query.all()

    breakdown = []
    for row in results:
        # Get unique agents used for this lead
        agents_query = db.query(
            AICostTracking.agent_type.distinct()
        ).filter(
            AICostTracking.lead_id == row.lead_id
        )

        if filters:
            agents_query = agents_query.filter(and_(*filters))

        agents_used = [agent[0] for agent in agents_query.all()]

        breakdown.append(LeadCostBreakdown(
            lead_id=row.lead_id,
            company_name=row.company_name,
            total_cost_usd=round(float(row.total_cost or Decimal("0.0")), 6),
            total_requests=row.total_requests,
            agents_used=agents_used
        ))

    # Sort by total cost descending
    breakdown.sort(key=lambda x: x.total_cost_usd, reverse=True)

    return breakdown


def _get_cache_statistics(db: Session, filters: List) -> CacheStats:
    """Get cache hit statistics with estimated savings."""
    # Get total requests and cache hits
    query = db.query(
        func.count(AICostTracking.id).label("total_requests"),
        func.sum(case((AICostTracking.cache_hit == True, 1), else_=0)).label("cache_hits")
    )

    if filters:
        query = query.filter(and_(*filters))

    result = query.first()

    total_requests = result.total_requests or 0
    cache_hits = int(result.cache_hits or 0)

    # Calculate cache hit rate
    cache_hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0

    # Estimate savings: get average cost of non-cached requests
    avg_cost_query = db.query(
        func.avg(AICostTracking.cost_usd).label("avg_cost")
    ).filter(
        AICostTracking.cache_hit == False
    )

    if filters:
        avg_cost_query = avg_cost_query.filter(and_(*filters))

    avg_cost_result = avg_cost_query.first()
    avg_cost_per_request = float(avg_cost_result.avg_cost or Decimal("0.0"))

    # Estimated savings = cache_hits * avg_cost_per_request
    estimated_savings = cache_hits * avg_cost_per_request

    return CacheStats(
        total_requests=total_requests,
        cache_hits=cache_hits,
        cache_hit_rate=round(cache_hit_rate, 4),
        estimated_savings_usd=round(estimated_savings, 6)
    )


def _get_time_series(db: Session, filters: List) -> List[TimeSeriesPoint]:
    """Get daily time-series data."""
    # Get date range for time series
    # If no date filters, use last 30 days
    date_filter_exists = any(
        hasattr(f, "left") and hasattr(f.left, "key") and f.left.key == "timestamp"
        for f in filters
    )

    if not date_filter_exists:
        # Default to last 30 days
        start_date = datetime.utcnow() - timedelta(days=30)
        filters.append(AICostTracking.timestamp >= start_date)

    # PostgreSQL date_trunc for daily grouping
    query = db.query(
        func.date_trunc('day', AICostTracking.timestamp).label("date"),
        func.sum(AICostTracking.cost_usd).label("total_cost"),
        func.count(AICostTracking.id).label("total_requests")
    ).group_by(
        func.date_trunc('day', AICostTracking.timestamp)
    ).order_by(
        func.date_trunc('day', AICostTracking.timestamp)
    )

    if filters:
        query = query.filter(and_(*filters))

    results = query.all()

    time_series = []
    for row in results:
        # Convert datetime to date string
        date_str = row.date.date().isoformat() if row.date else None

        if date_str:
            time_series.append(TimeSeriesPoint(
                date=date_str,
                total_cost_usd=round(float(row.total_cost or Decimal("0.0")), 6),
                total_requests=row.total_requests
            ))

    return time_series
