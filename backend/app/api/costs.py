"""
Cost Reporting API

Endpoints for cost analysis, budget monitoring, and usage export.

Features:
- Cost summary with provider breakdown
- Flexible cost breakdown (by provider/model/user/operation)
- Time-series usage data for charts
- Budget utilization monitoring
- CSV/JSON export with streaming
"""

import os
import csv
import json
import io
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text

from app.models.database import get_db
from app.models.usage_tracker import APICallLog, ProviderType, OperationType
from app.services.usage_tracker import UsageTracker
from app.schemas.costs import (
    CostSummaryResponse,
    CostBreakdownResponse,
    CostBreakdownItem,
    UsageTimeseriesResponse,
    UsageTimeSeriesPoint,
    BudgetStatusResponse,
    ProviderCostBreakdown,
    CostTrendPoint
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/costs", tags=["costs"])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_redis_client():
    """Get Redis client (optional dependency)"""
    try:
        import aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return aioredis.from_url(redis_url)
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return None


async def calculate_budget_status(
    daily_spend: float,
    monthly_spend: float,
    daily_budget: float,
    monthly_budget: float
) -> tuple[float, float, str]:
    """
    Calculate budget utilization and determine threshold status.

    Args:
        daily_spend: Today's spend in USD
        monthly_spend: Month-to-date spend in USD
        daily_budget: Daily budget limit
        monthly_budget: Monthly budget limit

    Returns:
        Tuple of (daily_utilization_percent, monthly_utilization_percent, threshold_status)
    """
    daily_util = (daily_spend / daily_budget * 100) if daily_budget > 0 else 0
    monthly_util = (monthly_spend / monthly_budget * 100) if monthly_budget > 0 else 0

    # Determine threshold status based on higher utilization
    max_util = max(daily_util, monthly_util)

    if max_util >= 100:
        status = "BLOCKED"
    elif max_util >= 95:
        status = "CRITICAL"
    elif max_util >= 80:
        status = "WARNING"
    else:
        status = "OK"

    return daily_util, monthly_util, status


# ============================================================================
# COST SUMMARY ENDPOINT
# ============================================================================

@router.get("/summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to include in summary"),
    db: Session = Depends(get_db)
) -> CostSummaryResponse:
    """
    Get cost summary for the last N days with provider breakdown.

    Returns:
    - Total cost and request count
    - Average cost per request
    - Cost breakdown by provider with percentages
    - Daily cost trend time series

    Query Parameters:
    - days: Number of days to include (default: 7, max: 90)
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()

        tracker = UsageTracker(db=db, redis_client=None)

        # Get provider breakdown
        provider_costs = tracker.get_cost_by_provider(start_date, end_date)

        # Calculate totals
        total_cost = sum(provider_costs.values())
        total_requests = db.query(func.count(APICallLog.id)).filter(
            and_(
                APICallLog.created_at >= start_date,
                APICallLog.created_at <= end_date
            )
        ).scalar() or 0

        avg_cost_per_request = (total_cost / total_requests) if total_requests > 0 else 0.0

        # Build provider breakdown with percentages
        provider_breakdown = [
            ProviderCostBreakdown(
                provider=provider,
                total_cost_usd=cost,
                total_requests=db.query(func.count(APICallLog.id)).filter(
                    and_(
                        APICallLog.provider == ProviderType(provider),
                        APICallLog.created_at >= start_date,
                        APICallLog.created_at <= end_date
                    )
                ).scalar() or 0,
                percentage=round((cost / total_cost * 100) if total_cost > 0 else 0.0, 2)
            )
            for provider, cost in provider_costs.items()
        ]

        # Sort by cost descending
        provider_breakdown.sort(key=lambda x: x.total_cost_usd, reverse=True)

        # Get daily cost trend
        daily_aggregates = tracker.get_aggregates(
            start_date=start_date,
            end_date=end_date,
            interval="day"
        )

        cost_trend = [
            CostTrendPoint(
                date=point["period"].split("T")[0],
                cost_usd=point["total_cost_usd"],
                requests=point["total_requests"]
            )
            for point in daily_aggregates
        ]

        logger.info(f"Cost summary generated: {days} days, ${total_cost:.6f}, {total_requests} requests")

        return CostSummaryResponse(
            total_cost_usd=round(total_cost, 6),
            total_requests=total_requests,
            avg_cost_per_request=round(avg_cost_per_request, 8),
            provider_breakdown=provider_breakdown,
            cost_trend=cost_trend,
            period_days=days
        )

    except Exception as e:
        logger.error(f"Failed to generate cost summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate cost summary: {str(e)}")


# ============================================================================
# COST BREAKDOWN ENDPOINT
# ============================================================================

@router.get("/breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    group_by: str = Query("provider", regex="^(provider|model|operation)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
) -> CostBreakdownResponse:
    """
    Get cost breakdown grouped by provider, model, or operation.

    Returns breakdown with:
    - Group name
    - Total cost and requests
    - Percentage of total cost

    Query Parameters:
    - group_by: Dimension to group by (provider, model, operation)
    - start_date: Start date (optional, defaults to 30 days ago)
    - end_date: End date (optional, defaults to now)
    """
    try:
        # Default date range
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Build query based on group_by parameter
        if group_by == "provider":
            group_field = APICallLog.provider
        elif group_by == "model":
            group_field = APICallLog.model
        else:  # operation
            group_field = APICallLog.operation_type

        # Aggregate query
        results = db.query(
            group_field.label("group_name"),
            func.sum(APICallLog.cost_usd).label("total_cost"),
            func.count(APICallLog.id).label("total_requests")
        ).filter(
            and_(
                APICallLog.created_at >= start_date,
                APICallLog.created_at <= end_date
            )
        ).group_by(group_field).all()

        # Calculate totals
        total_cost = sum(row.total_cost or 0.0 for row in results)
        total_requests = sum(row.total_requests for row in results)

        # Build breakdown items
        breakdown = [
            CostBreakdownItem(
                group_name=str(row.group_name.value if hasattr(row.group_name, 'value') else row.group_name),
                total_cost_usd=round(float(row.total_cost or 0.0), 6),
                total_requests=row.total_requests,
                percentage_of_total=round((float(row.total_cost or 0.0) / total_cost * 100) if total_cost > 0 else 0.0, 2)
            )
            for row in results
        ]

        # Sort by cost descending
        breakdown.sort(key=lambda x: x.total_cost_usd, reverse=True)

        logger.info(f"Cost breakdown by {group_by}: {len(breakdown)} groups, ${total_cost:.6f}")

        return CostBreakdownResponse(
            group_by=group_by,
            breakdown=breakdown,
            total_cost_usd=round(total_cost, 6),
            total_requests=total_requests
        )

    except Exception as e:
        logger.error(f"Failed to generate cost breakdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate cost breakdown: {str(e)}")


# ============================================================================
# USAGE TIME SERIES ENDPOINT
# ============================================================================

@router.get("/usage", response_model=UsageTimeseriesResponse)
async def get_usage_timeseries(
    start_date: datetime = Query(..., description="Start date for time series"),
    end_date: datetime = Query(..., description="End date for time series"),
    interval: str = Query("daily", regex="^(hourly|daily|monthly)$"),
    db: Session = Depends(get_db)
) -> UsageTimeseriesResponse:
    """
    Get time-series usage data for chart visualization.

    Returns time series with:
    - Timestamp
    - Total cost and requests
    - Average latency
    - Provider-specific costs

    Query Parameters:
    - start_date: Start date (ISO 8601 format)
    - end_date: End date (ISO 8601 format)
    - interval: Time interval (hourly, daily, monthly)
    """
    try:
        tracker = UsageTracker(db=db, redis_client=None)

        # Map interval to tracker format
        interval_map = {"hourly": "hour", "daily": "day", "monthly": "month"}
        tracker_interval = interval_map[interval]

        # Get aggregates for all providers combined
        aggregates = tracker.get_aggregates(
            start_date=start_date,
            end_date=end_date,
            interval=tracker_interval
        )

        # Get provider-specific costs for each time period
        data_points = []
        for aggregate in aggregates:
            period_start = datetime.fromisoformat(aggregate["period"])

            # Calculate period end based on interval
            if tracker_interval == "hour":
                period_end = period_start + timedelta(hours=1)
            elif tracker_interval == "day":
                period_end = period_start + timedelta(days=1)
            else:  # month
                # Approximate month end
                period_end = period_start + timedelta(days=30)

            # Get provider costs for this period
            provider_costs_dict = tracker.get_cost_by_provider(period_start, period_end)

            data_points.append(
                UsageTimeSeriesPoint(
                    timestamp=aggregate["period"],
                    total_cost_usd=aggregate["total_cost_usd"],
                    total_requests=aggregate["total_requests"],
                    avg_latency_ms=aggregate["avg_latency_ms"],
                    provider_costs=provider_costs_dict
                )
            )

        logger.info(f"Usage time series generated: {len(data_points)} data points, interval={interval}")

        return UsageTimeseriesResponse(
            interval=interval,
            data_points=data_points,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to generate usage time series: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate usage time series: {str(e)}")


# ============================================================================
# BUDGET STATUS ENDPOINT
# ============================================================================

@router.get("/budget/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    db: Session = Depends(get_db)
) -> BudgetStatusResponse:
    """
    Get current budget utilization status.

    Returns:
    - Daily and monthly budget limits
    - Current spend and utilization percentages
    - Threshold status (OK, WARNING, CRITICAL, BLOCKED)
    - Current routing strategy

    Budget limits are configured via environment variables:
    - DAILY_BUDGET_USD (default: $10.00)
    - MONTHLY_BUDGET_USD (default: $300.00)
    """
    try:
        # Get budget limits from environment
        daily_budget = float(os.getenv("DAILY_BUDGET_USD", "10.0"))
        monthly_budget = float(os.getenv("MONTHLY_BUDGET_USD", "300.0"))

        # Calculate today's spend
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.utcnow()

        daily_spend = db.query(func.sum(APICallLog.cost_usd)).filter(
            and_(
                APICallLog.created_at >= today_start,
                APICallLog.created_at <= today_end
            )
        ).scalar() or 0.0

        # Calculate month-to-date spend
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = datetime.utcnow()

        monthly_spend = db.query(func.sum(APICallLog.cost_usd)).filter(
            and_(
                APICallLog.created_at >= month_start,
                APICallLog.created_at <= month_end
            )
        ).scalar() or 0.0

        # Calculate utilization and status
        daily_util, monthly_util, threshold_status = await calculate_budget_status(
            daily_spend=daily_spend,
            monthly_spend=monthly_spend,
            daily_budget=daily_budget,
            monthly_budget=monthly_budget
        )

        # Determine current strategy (simplified - could be enhanced with actual strategy detection)
        current_strategy = "standard"
        if threshold_status in ["CRITICAL", "BLOCKED"]:
            current_strategy = "cost-optimized"

        logger.info(
            f"Budget status: daily={daily_util:.2f}%, monthly={monthly_util:.2f}%, status={threshold_status}"
        )

        return BudgetStatusResponse(
            daily_budget_usd=daily_budget,
            daily_spend_usd=round(daily_spend, 6),
            daily_utilization_percent=round(daily_util, 2),
            monthly_budget_usd=monthly_budget,
            monthly_spend_usd=round(monthly_spend, 6),
            monthly_utilization_percent=round(monthly_util, 2),
            threshold_status=threshold_status,
            current_strategy=current_strategy
        )

    except Exception as e:
        logger.error(f"Failed to get budget status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get budget status: {str(e)}")


# ============================================================================
# EXPORT ENDPOINT
# ============================================================================

@router.get("/export")
async def export_costs(
    format: str = Query("csv", regex="^(csv|json)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Export cost data as CSV or JSON.

    CSV columns:
    - timestamp, provider, model, operation_type, cost_usd,
      prompt_tokens, completion_tokens, latency_ms, success

    Query Parameters:
    - format: Export format (csv or json)
    - start_date: Start date (optional, defaults to 30 days ago)
    - end_date: End date (optional, defaults to now)
    """
    try:
        # Default date range
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Query all cost records in date range
        records = db.query(APICallLog).filter(
            and_(
                APICallLog.created_at >= start_date,
                APICallLog.created_at <= end_date
            )
        ).order_by(APICallLog.created_at.desc()).all()

        logger.info(f"Exporting {len(records)} cost records as {format}")

        if format == "csv":
            # Generate CSV
            output = io.StringIO()
            fieldnames = [
                "timestamp", "provider", "model", "operation_type", "cost_usd",
                "prompt_tokens", "completion_tokens", "latency_ms", "success"
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for record in records:
                writer.writerow({
                    "timestamp": record.created_at.isoformat(),
                    "provider": record.provider.value,
                    "model": record.model,
                    "operation_type": record.operation_type.value,
                    "cost_usd": record.cost_usd,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "latency_ms": record.latency_ms,
                    "success": record.success
                })

            # Prepare streaming response
            output.seek(0)
            filename = f"cost-report-{datetime.utcnow().strftime('%Y%m%d')}.csv"

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        else:  # json
            # Generate JSON
            data = [
                {
                    "timestamp": record.created_at.isoformat(),
                    "provider": record.provider.value,
                    "model": record.model,
                    "operation_type": record.operation_type.value,
                    "cost_usd": record.cost_usd,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "latency_ms": record.latency_ms,
                    "success": record.success
                }
                for record in records
            ]

            filename = f"cost-report-{datetime.utcnow().strftime('%Y%m%d')}.json"

            return StreamingResponse(
                iter([json.dumps(data, indent=2)]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

    except Exception as e:
        logger.error(f"Failed to export costs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export costs: {str(e)}")
