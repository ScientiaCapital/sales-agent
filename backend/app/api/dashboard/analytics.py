"""
Dashboard Analytics Module
===========================
Funnel metrics and conversion rate analytics for sales pipeline visibility.

Endpoints:
- GET /funnel-metrics - Get sales funnel with lead counts and conversion rates per stage
- GET /conversion-rates - Get stage-to-stage conversion rates

Author: Claude + Tim
Date: Dec 26, 2025
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from .shared import get_supabase

logger = logging.getLogger(__name__)

# ============================================================================
# Response Models
# ============================================================================

class FunnelStage(BaseModel):
    """Single stage in the sales funnel."""
    name: str = Field(..., description="Stage name (imported, qualified, enriched, etc.)")
    count: int = Field(..., description="Number of leads in this stage")
    value_usd: Optional[float] = Field(None, description="Total pipeline value at this stage")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate from previous stage")
    avg_days_in_stage: Optional[float] = Field(None, description="Average days leads spend in stage")


class FunnelMetricsResponse(BaseModel):
    """Complete funnel visualization data."""
    stages: List[FunnelStage]
    total_leads: int
    total_pipeline_value: float
    overall_conversion_rate: float  # First stage to last stage
    period: str  # "7d", "30d", "mtd", "qtd"
    generated_at: datetime


class ConversionRatesResponse(BaseModel):
    """Stage-to-stage conversion rates."""
    lead_to_qualified: float
    qualified_to_meeting: float
    meeting_to_opportunity: float
    opportunity_to_won: float
    overall_win_rate: float
    period: str


class DealsByStage(BaseModel):
    """Deals grouped by opportunity stage."""
    stage: str = Field(..., description="Pipeline stage name")
    count: int = Field(..., description="Number of deals in this stage")
    total_value: float = Field(..., description="Total value of deals in stage")
    avg_deal_size: float = Field(..., description="Average deal size")
    weighted_value: float = Field(..., description="Value weighted by probability (value * probability)")


class PipelineHealthResponse(BaseModel):
    """Overall pipeline health metrics."""
    deals_by_stage: List[DealsByStage]
    total_pipeline_value: float = Field(..., description="Sum of all deal values")
    weighted_pipeline_value: float = Field(..., description="Sum of probability-weighted values")
    average_deal_size: float = Field(..., description="Average deal size across pipeline")
    deals_at_risk: int = Field(..., description="Stale deals with no activity in 14 days")
    avg_days_to_close: float = Field(..., description="Average days from creation to close")
    period: str = Field(..., description="Analysis period (7d, 30d, mtd, qtd)")
    generated_at: datetime


class RevenueForecastResponse(BaseModel):
    """Revenue forecast by expected close date."""
    current_month: float = Field(..., description="Sum of deals expected to close this month")
    next_month: float = Field(..., description="Sum of deals expected to close next month")
    quarter_total: float = Field(..., description="Sum of all deals expected in quarter")
    weighted_forecast: float = Field(..., description="Probability-weighted forecast total")
    high_confidence_deals: int = Field(..., description="Deals with >70% probability")
    at_risk_deals: int = Field(..., description="Deals with <30% probability")
    period: str = Field(..., description="Forecast period (current quarter)")


# ============================================================================
# Trend Analysis Response Models
# ============================================================================

class DataPoint(BaseModel):
    """Single data point in a time series."""
    date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    value: float = Field(..., description="Metric value for this date")


class TrendMetric(BaseModel):
    """Time series for a single metric."""
    metric_name: str = Field(..., description="Name of the metric")
    data_points: List[DataPoint] = Field(..., description="Time series data points")
    current_value: float = Field(..., description="Value for current period")
    previous_value: float = Field(..., description="Value for previous period")
    change_percent: float = Field(..., description="Percentage change from previous")
    trend_direction: str = Field(..., description="Trend direction: 'up', 'down', or 'flat'")


class ActivityTrendsResponse(BaseModel):
    """Activity metrics over time."""
    calls: TrendMetric = Field(..., description="Call activity trend")
    emails: TrendMetric = Field(..., description="Email activity trend")
    meetings: TrendMetric = Field(..., description="Meeting activity trend")
    total_activities: TrendMetric = Field(..., description="Total activities trend")
    period: str = Field(..., description="Analysis period (7d, 30d, 90d)")
    granularity: str = Field(..., description="Time bucket: day, week, or month")
    generated_at: datetime


class ConversionTrendsResponse(BaseModel):
    """Conversion rate trends over time."""
    lead_to_qualified: TrendMetric = Field(..., description="Lead to qualified conversion trend")
    qualified_to_opportunity: TrendMetric = Field(..., description="Qualified to opportunity trend")
    opportunity_to_won: TrendMetric = Field(..., description="Opportunity to won trend")
    period: str = Field(..., description="Analysis period")
    granularity: str = Field(..., description="Time bucket: day, week, or month")
    generated_at: datetime


class PeriodComparisonResponse(BaseModel):
    """Period-over-period comparison."""
    current_period: dict = Field(..., description="Metrics for current period")
    previous_period: dict = Field(..., description="Metrics for previous period")
    changes: dict = Field(..., description="Percentage changes between periods")
    period_type: str = Field(..., description="Comparison type: week, month, or quarter")


# ============================================================================
# Stage Configuration
# ============================================================================

# Ordered stages for funnel calculation
STAGE_ORDER = ['imported', 'qualified', 'enriched', 'contacted', 'meeting_booked', 'opportunity', 'won']

# Stage display names for UI
STAGE_DISPLAY_NAMES = {
    'imported': 'Imported',
    'qualified': 'Qualified',
    'enriched': 'Enriched',
    'contacted': 'Contacted',
    'meeting_booked': 'Meeting Booked',
    'opportunity': 'Opportunity',
    'won': 'Won'
}


# ============================================================================
# Router
# ============================================================================

router = APIRouter(tags=["analytics"])


def get_period_start(period: str) -> datetime:
    """Get the start datetime for a given period."""
    now = datetime.now(timezone.utc)

    if period == "7d":
        return now - timedelta(days=7)
    elif period == "30d":
        return now - timedelta(days=30)
    elif period == "mtd":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "qtd":
        # Quarter-to-date: Q1 starts Jan, Q2 starts Apr, Q3 starts Jul, Q4 starts Oct
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        return now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Default to 7 days
        return now - timedelta(days=7)


@router.get("/funnel-metrics", response_model=FunnelMetricsResponse)
async def get_funnel_metrics(
    period: str = Query("7d", description="Time period: 7d, 30d, mtd, qtd"),
):
    """
    Get sales funnel metrics with lead counts and conversion rates per stage.

    Uses lead_current_state for performance, falls back to dim_companies.
    Calculates stage-to-stage conversion rates.
    """
    try:
        supabase = get_supabase()
        period_start = get_period_start(period)

        # Try to use lead_current_state first (optimized view)
        stage_counts = {}
        total_leads = 0

        try:
            # Query lead_current_state grouped by current_stage
            result = supabase.table("lead_current_state").select(
                "current_stage, lead_id"
            ).gte("last_activity_at", period_start.isoformat()).execute()

            # Count leads per stage
            for row in (result.data or []):
                stage = row.get("current_stage") or "imported"
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
                total_leads += 1

        except Exception as e:
            logger.warning(f"lead_current_state query failed, falling back to dim_companies: {e}")

            # Fallback to dim_companies
            result = supabase.table("dim_companies").select(
                "company_id, current_stage, updated_at"
            ).gte("updated_at", period_start.isoformat()).execute()

            for row in (result.data or []):
                stage = row.get("current_stage") or "imported"
                # Map legacy stages to new stage names if needed
                if stage.upper() in ["COLD", "WARM", "HOT"]:
                    stage = "imported" if stage.upper() == "COLD" else "qualified" if stage.upper() == "WARM" else "meeting_booked"
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
                total_leads += 1

        # Query fact_opportunities for pipeline values
        stage_values = {}
        try:
            opp_result = supabase.table("fact_opportunities").select(
                "stage, value_usd"
            ).execute()

            for row in (opp_result.data or []):
                stage = row.get("stage") or "opportunity"
                value = row.get("value_usd") or 0
                stage_values[stage] = stage_values.get(stage, 0) + value
        except Exception as e:
            logger.debug(f"fact_opportunities query failed (table may not exist): {e}")

        # Build funnel stages in order
        stages = []
        prev_count = None
        total_pipeline_value = 0.0

        for stage_name in STAGE_ORDER:
            count = stage_counts.get(stage_name, 0)
            value = stage_values.get(stage_name, 0.0)
            total_pipeline_value += value

            # Calculate conversion rate from previous stage
            conversion_rate = None
            if prev_count is not None and prev_count > 0:
                conversion_rate = count / prev_count
            elif prev_count is None and count > 0:
                conversion_rate = 1.0  # First stage has 100% "conversion" (entry)

            stages.append(FunnelStage(
                name=STAGE_DISPLAY_NAMES.get(stage_name, stage_name),
                count=count,
                value_usd=value if value > 0 else None,
                conversion_rate=conversion_rate,
                avg_days_in_stage=None  # TODO: Calculate from activity timestamps
            ))

            prev_count = count

        # Calculate overall conversion rate (first stage to last stage)
        first_stage_count = stage_counts.get(STAGE_ORDER[0], 0)
        last_stage_count = stage_counts.get(STAGE_ORDER[-1], 0)
        overall_conversion_rate = last_stage_count / first_stage_count if first_stage_count > 0 else 0.0

        return FunnelMetricsResponse(
            stages=stages,
            total_leads=total_leads,
            total_pipeline_value=total_pipeline_value,
            overall_conversion_rate=overall_conversion_rate,
            period=period,
            generated_at=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Error fetching funnel metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch funnel metrics")


@router.get("/conversion-rates", response_model=ConversionRatesResponse)
async def get_conversion_rates(
    period: str = Query("7d", description="Time period: 7d, 30d, mtd, qtd"),
):
    """
    Get stage-to-stage conversion rates.

    Returns key conversion metrics for sales pipeline analysis:
    - Lead to Qualified (ICP scoring success)
    - Qualified to Meeting (outreach effectiveness)
    - Meeting to Opportunity (pitch success)
    - Opportunity to Won (close rate)
    - Overall Win Rate (end-to-end conversion)
    """
    try:
        supabase = get_supabase()
        period_start = get_period_start(period)

        # Get stage counts
        stage_counts = {stage: 0 for stage in STAGE_ORDER}

        try:
            # Try lead_current_state first
            result = supabase.table("lead_current_state").select(
                "current_stage"
            ).gte("last_activity_at", period_start.isoformat()).execute()

            for row in (result.data or []):
                stage = row.get("current_stage") or "imported"
                if stage in stage_counts:
                    stage_counts[stage] += 1

        except Exception as e:
            logger.warning(f"lead_current_state query failed, falling back to dim_companies: {e}")

            # Fallback to dim_companies
            result = supabase.table("dim_companies").select(
                "current_stage"
            ).gte("updated_at", period_start.isoformat()).execute()

            for row in (result.data or []):
                stage = row.get("current_stage") or "imported"
                # Map legacy stages
                if stage.upper() in ["COLD", "WARM", "HOT"]:
                    stage = "imported" if stage.upper() == "COLD" else "qualified" if stage.upper() == "WARM" else "meeting_booked"
                if stage in stage_counts:
                    stage_counts[stage] += 1

        # Calculate cumulative counts (leads at or past each stage)
        cumulative = {}
        running_total = 0
        for stage in reversed(STAGE_ORDER):
            running_total += stage_counts[stage]
            cumulative[stage] = running_total

        # Calculate conversion rates
        def safe_rate(numerator: int, denominator: int) -> float:
            """Calculate rate safely, returning 0 if denominator is 0."""
            return numerator / denominator if denominator > 0 else 0.0

        # Lead to Qualified: qualified+ / imported+
        lead_to_qualified = safe_rate(
            cumulative.get('qualified', 0),
            cumulative.get('imported', 0)
        )

        # Qualified to Meeting: meeting_booked+ / qualified+
        qualified_to_meeting = safe_rate(
            cumulative.get('meeting_booked', 0),
            cumulative.get('qualified', 0)
        )

        # Meeting to Opportunity: opportunity+ / meeting_booked+
        meeting_to_opportunity = safe_rate(
            cumulative.get('opportunity', 0),
            cumulative.get('meeting_booked', 0)
        )

        # Opportunity to Won: won / opportunity+
        opportunity_to_won = safe_rate(
            stage_counts.get('won', 0),
            cumulative.get('opportunity', 0)
        )

        # Overall Win Rate: won / imported+
        overall_win_rate = safe_rate(
            stage_counts.get('won', 0),
            cumulative.get('imported', 0)
        )

        return ConversionRatesResponse(
            lead_to_qualified=lead_to_qualified,
            qualified_to_meeting=qualified_to_meeting,
            meeting_to_opportunity=meeting_to_opportunity,
            opportunity_to_won=opportunity_to_won,
            overall_win_rate=overall_win_rate,
            period=period
        )

    except Exception as e:
        logger.error(f"Error fetching conversion rates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch conversion rates")


@router.get("/pipeline-health", response_model=PipelineHealthResponse)
async def get_pipeline_health(
    period: str = Query("30d", description="Analysis period: 7d, 30d, mtd, qtd"),
):
    """
    Get pipeline health metrics with deals by stage and risk indicators.

    Uses crm_opportunities (CloseOpportunity) table for deal data.
    Identifies at-risk deals based on last activity date (no activity in 14 days).
    Calculates weighted values using probability field.
    """
    try:
        supabase = get_supabase()
        period_start = get_period_start(period)
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(days=14)

        # Query opportunities from crm_opportunities table
        stage_data: dict = {}  # stage -> {count, total_value, weighted_value, deals}
        total_deals = 0
        total_pipeline_value = 0.0
        weighted_pipeline_value = 0.0
        deals_at_risk = 0
        closed_deals_days: list = []

        try:
            # Query crm_opportunities (CloseOpportunity model)
            result = supabase.table("crm_opportunities").select(
                "id, stage, amount, probability, expected_close_date, actual_close_date, created_at, updated_at"
            ).neq("stage", "lost").execute()

            for row in (result.data or []):
                stage = row.get("stage") or "unknown"
                amount = float(row.get("amount") or 0)
                probability = float(row.get("probability") or 0)

                # Normalize probability to 0-1 range if needed
                if probability > 1:
                    probability = probability / 100.0

                # Initialize stage data if not present
                if stage not in stage_data:
                    stage_data[stage] = {
                        "count": 0,
                        "total_value": 0.0,
                        "weighted_value": 0.0,
                    }

                # Accumulate stage metrics
                stage_data[stage]["count"] += 1
                stage_data[stage]["total_value"] += amount
                stage_data[stage]["weighted_value"] += amount * probability

                total_deals += 1
                total_pipeline_value += amount
                weighted_pipeline_value += amount * probability

                # Check for at-risk deals (no activity in 14 days)
                updated_at_str = row.get("updated_at")
                if updated_at_str:
                    try:
                        # Parse ISO datetime
                        if isinstance(updated_at_str, str):
                            updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                        else:
                            updated_at = updated_at_str
                        if updated_at < stale_threshold:
                            deals_at_risk += 1
                    except Exception:
                        pass

                # Calculate days to close for closed deals
                actual_close = row.get("actual_close_date")
                created_at_str = row.get("created_at")
                if actual_close and created_at_str:
                    try:
                        if isinstance(actual_close, str):
                            close_date = datetime.fromisoformat(actual_close.replace('Z', '+00:00'))
                        else:
                            close_date = actual_close
                        if isinstance(created_at_str, str):
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        else:
                            created_at = created_at_str
                        days_to_close = (close_date - created_at).days
                        if days_to_close >= 0:
                            closed_deals_days.append(days_to_close)
                    except Exception:
                        pass

        except Exception as e:
            logger.warning(f"crm_opportunities query failed, trying fact_opportunities: {e}")

            # Fallback to fact_opportunities if available
            try:
                result = supabase.table("fact_opportunities").select(
                    "stage, value_usd, probability, updated_at"
                ).execute()

                for row in (result.data or []):
                    stage = row.get("stage") or "unknown"
                    amount = float(row.get("value_usd") or 0)
                    probability = float(row.get("probability") or 0.5)

                    if probability > 1:
                        probability = probability / 100.0

                    if stage not in stage_data:
                        stage_data[stage] = {"count": 0, "total_value": 0.0, "weighted_value": 0.0}

                    stage_data[stage]["count"] += 1
                    stage_data[stage]["total_value"] += amount
                    stage_data[stage]["weighted_value"] += amount * probability

                    total_deals += 1
                    total_pipeline_value += amount
                    weighted_pipeline_value += amount * probability

            except Exception as e2:
                logger.debug(f"fact_opportunities query also failed: {e2}")

        # Build deals by stage response
        deals_by_stage = []
        for stage, data in stage_data.items():
            avg_deal_size = data["total_value"] / data["count"] if data["count"] > 0 else 0.0
            deals_by_stage.append(DealsByStage(
                stage=stage,
                count=data["count"],
                total_value=data["total_value"],
                avg_deal_size=avg_deal_size,
                weighted_value=data["weighted_value"]
            ))

        # Sort by total_value descending
        deals_by_stage.sort(key=lambda x: x.total_value, reverse=True)

        # Calculate average days to close
        avg_days_to_close = sum(closed_deals_days) / len(closed_deals_days) if closed_deals_days else 0.0

        # Calculate overall average deal size
        average_deal_size = total_pipeline_value / total_deals if total_deals > 0 else 0.0

        return PipelineHealthResponse(
            deals_by_stage=deals_by_stage,
            total_pipeline_value=total_pipeline_value,
            weighted_pipeline_value=weighted_pipeline_value,
            average_deal_size=average_deal_size,
            deals_at_risk=deals_at_risk,
            avg_days_to_close=avg_days_to_close,
            period=period,
            generated_at=now
        )

    except Exception as e:
        logger.error(f"Error fetching pipeline health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch pipeline health")


@router.get("/revenue-forecast", response_model=RevenueForecastResponse)
async def get_revenue_forecast():
    """
    Get revenue forecast based on expected close dates and probabilities.

    Aggregates opportunities by expected_close_date month.
    Calculates weighted forecast using probability field.
    Identifies high confidence (>70%) and at-risk (<30%) deals.
    """
    try:
        supabase = get_supabase()
        now = datetime.now(timezone.utc)

        # Define month boundaries
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            next_month_start = current_month_start.replace(year=now.year + 1, month=1)
        else:
            next_month_start = current_month_start.replace(month=now.month + 1)

        if next_month_start.month == 12:
            month_after_next = next_month_start.replace(year=next_month_start.year + 1, month=1)
        else:
            month_after_next = next_month_start.replace(month=next_month_start.month + 1)

        # Calculate quarter boundaries
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        quarter_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        if quarter_month + 3 > 12:
            quarter_end = quarter_start.replace(year=now.year + 1, month=(quarter_month + 3) - 12)
        else:
            quarter_end = quarter_start.replace(month=quarter_month + 3)

        # Initialize metrics
        current_month_value = 0.0
        next_month_value = 0.0
        quarter_total = 0.0
        weighted_forecast = 0.0
        high_confidence_deals = 0
        at_risk_deals = 0

        try:
            # Query crm_opportunities excluding lost deals
            result = supabase.table("crm_opportunities").select(
                "amount, probability, expected_close_date, stage"
            ).neq("stage", "lost").execute()

            for row in (result.data or []):
                amount = float(row.get("amount") or 0)
                probability = float(row.get("probability") or 0)

                # Normalize probability
                if probability > 1:
                    probability = probability / 100.0

                expected_close_str = row.get("expected_close_date")
                expected_close = None
                if expected_close_str:
                    try:
                        if isinstance(expected_close_str, str):
                            expected_close = datetime.fromisoformat(expected_close_str.replace('Z', '+00:00'))
                        else:
                            expected_close = expected_close_str
                    except Exception:
                        pass

                # Accumulate weighted forecast
                weighted_forecast += amount * probability

                # Count by confidence level
                if probability > 0.7:
                    high_confidence_deals += 1
                elif probability < 0.3:
                    at_risk_deals += 1

                # Bucket by expected close date
                if expected_close:
                    # Current month
                    if current_month_start <= expected_close < next_month_start:
                        current_month_value += amount
                    # Next month
                    elif next_month_start <= expected_close < month_after_next:
                        next_month_value += amount

                    # Quarter total
                    if quarter_start <= expected_close < quarter_end:
                        quarter_total += amount

        except Exception as e:
            logger.warning(f"crm_opportunities query failed, trying fact_opportunities: {e}")

            try:
                result = supabase.table("fact_opportunities").select(
                    "value_usd, probability, expected_close_date, stage"
                ).execute()

                for row in (result.data or []):
                    if row.get("stage") == "lost":
                        continue

                    amount = float(row.get("value_usd") or 0)
                    probability = float(row.get("probability") or 0.5)

                    if probability > 1:
                        probability = probability / 100.0

                    weighted_forecast += amount * probability

                    if probability > 0.7:
                        high_confidence_deals += 1
                    elif probability < 0.3:
                        at_risk_deals += 1

            except Exception as e2:
                logger.debug(f"fact_opportunities query also failed: {e2}")

        # Determine period string (current quarter)
        quarter_num = ((now.month - 1) // 3) + 1
        period = f"Q{quarter_num} {now.year}"

        return RevenueForecastResponse(
            current_month=current_month_value,
            next_month=next_month_value,
            quarter_total=quarter_total,
            weighted_forecast=weighted_forecast,
            high_confidence_deals=high_confidence_deals,
            at_risk_deals=at_risk_deals,
            period=period
        )

    except Exception as e:
        logger.error(f"Error fetching revenue forecast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch revenue forecast")


# ============================================================================
# Trend Analysis Helpers
# ============================================================================

def get_date_range_for_period(period: str) -> tuple[datetime, datetime]:
    """Get start and end datetime for a period string."""
    now = datetime.now(timezone.utc)
    if period == "7d":
        return now - timedelta(days=7), now
    elif period == "30d":
        return now - timedelta(days=30), now
    elif period == "90d":
        return now - timedelta(days=90), now
    else:
        return now - timedelta(days=30), now


def get_previous_period_range(period: str) -> tuple[datetime, datetime]:
    """Get start and end datetime for the previous equivalent period."""
    now = datetime.now(timezone.utc)
    if period == "7d":
        return now - timedelta(days=14), now - timedelta(days=7)
    elif period == "30d":
        return now - timedelta(days=60), now - timedelta(days=30)
    elif period == "90d":
        return now - timedelta(days=180), now - timedelta(days=90)
    else:
        return now - timedelta(days=60), now - timedelta(days=30)


def get_period_type_ranges(period_type: str) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """Get current and previous period date ranges for week/month/quarter."""
    now = datetime.now(timezone.utc)

    if period_type == "week":
        # Current week (Mon-Sun)
        days_since_monday = now.weekday()
        current_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        # Previous week
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start

    elif period_type == "month":
        # Current month
        current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        # Previous month
        if now.month == 1:
            previous_start = current_start.replace(year=now.year - 1, month=12)
        else:
            previous_start = current_start.replace(month=now.month - 1)
        previous_end = current_start

    elif period_type == "quarter":
        # Current quarter
        quarter_month = ((now.month - 1) // 3) * 3 + 1
        current_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        # Previous quarter
        if quarter_month == 1:
            previous_start = current_start.replace(year=now.year - 1, month=10)
        else:
            previous_start = current_start.replace(month=quarter_month - 3)
        previous_end = current_start

    else:
        # Default to week
        days_since_monday = now.weekday()
        current_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        current_end = now
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start

    return (current_start, current_end), (previous_start, previous_end)


def calculate_trend_direction(current: float, previous: float, threshold: float = 0.05) -> str:
    """Determine trend direction based on percentage change."""
    if previous == 0:
        return "up" if current > 0 else "flat"
    change = (current - previous) / previous
    if change > threshold:
        return "up"
    elif change < -threshold:
        return "down"
    else:
        return "flat"


def calculate_change_percent(current: float, previous: float) -> float:
    """Calculate percentage change between two values."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100.0


def date_to_bucket(dt: datetime, granularity: str) -> str:
    """Convert datetime to bucket string based on granularity."""
    if granularity == "day":
        return dt.strftime("%Y-%m-%d")
    elif granularity == "week":
        # ISO week start (Monday)
        week_start = dt - timedelta(days=dt.weekday())
        return week_start.strftime("%Y-%m-%d")
    elif granularity == "month":
        return dt.strftime("%Y-%m-01")
    else:
        return dt.strftime("%Y-%m-%d")


def generate_date_buckets(start: datetime, end: datetime, granularity: str) -> List[str]:
    """Generate all date buckets between start and end."""
    buckets = []
    current = start

    if granularity == "day":
        while current <= end:
            buckets.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
    elif granularity == "week":
        # Align to Monday
        current = current - timedelta(days=current.weekday())
        while current <= end:
            buckets.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=7)
    elif granularity == "month":
        current = current.replace(day=1)
        while current <= end:
            buckets.append(current.strftime("%Y-%m-01"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    return buckets


def build_trend_metric(
    metric_name: str,
    data_by_bucket: dict,
    all_buckets: List[str],
    current_total: float,
    previous_total: float
) -> TrendMetric:
    """Build a TrendMetric from bucketed data."""
    data_points = [
        DataPoint(date=bucket, value=data_by_bucket.get(bucket, 0.0))
        for bucket in all_buckets
    ]

    return TrendMetric(
        metric_name=metric_name,
        data_points=data_points,
        current_value=current_total,
        previous_value=previous_total,
        change_percent=calculate_change_percent(current_total, previous_total),
        trend_direction=calculate_trend_direction(current_total, previous_total)
    )


# ============================================================================
# Trend Analysis Endpoints
# ============================================================================

@router.get("/activity-trends", response_model=ActivityTrendsResponse)
async def get_activity_trends(
    period: str = Query("30d", description="Time period: 7d, 30d, 90d"),
    granularity: str = Query("day", description="Aggregation: day, week, month"),
):
    """
    Get activity metrics as time series for trend visualization.

    Aggregates fact_activities by activity_type and date bucket.
    Calculates period-over-period change percentages.
    Returns time series data for calls, emails, meetings, and total activities.
    """
    try:
        supabase = get_supabase()
        now = datetime.now(timezone.utc)

        # Get current and previous period ranges
        current_start, current_end = get_date_range_for_period(period)
        previous_start, previous_end = get_previous_period_range(period)

        # Generate all buckets for the current period
        all_buckets = generate_date_buckets(current_start, current_end, granularity)

        # Initialize data structures for activity types
        activity_types = ["call", "email", "meeting"]
        current_data = {atype: {} for atype in activity_types}
        current_totals = {atype: 0.0 for atype in activity_types}
        previous_totals = {atype: 0.0 for atype in activity_types}

        try:
            # Query fact_activities for current period
            result = supabase.table("fact_activities").select(
                "activity_type, activity_date, activity_id"
            ).gte("activity_date", current_start.isoformat()).lte("activity_date", current_end.isoformat()).execute()

            for row in (result.data or []):
                atype = (row.get("activity_type") or "").lower()
                activity_date_str = row.get("activity_date")

                if atype not in activity_types:
                    continue

                if activity_date_str:
                    try:
                        if isinstance(activity_date_str, str):
                            activity_date = datetime.fromisoformat(activity_date_str.replace('Z', '+00:00'))
                        else:
                            activity_date = activity_date_str

                        bucket = date_to_bucket(activity_date, granularity)
                        current_data[atype][bucket] = current_data[atype].get(bucket, 0) + 1
                        current_totals[atype] += 1
                    except Exception:
                        pass

            # Query fact_activities for previous period
            prev_result = supabase.table("fact_activities").select(
                "activity_type, activity_id"
            ).gte("activity_date", previous_start.isoformat()).lt("activity_date", previous_end.isoformat()).execute()

            for row in (prev_result.data or []):
                atype = (row.get("activity_type") or "").lower()
                if atype in activity_types:
                    previous_totals[atype] += 1

        except Exception as e:
            logger.warning(f"fact_activities query failed: {e}")
            # Return empty trend data if table doesn't exist

        # Build total activities data
        total_current_data = {}
        total_current = 0.0
        total_previous = 0.0

        for bucket in all_buckets:
            bucket_total = sum(current_data[atype].get(bucket, 0) for atype in activity_types)
            total_current_data[bucket] = bucket_total

        total_current = sum(current_totals.values())
        total_previous = sum(previous_totals.values())

        # Build TrendMetric for each activity type
        calls_trend = build_trend_metric(
            "calls", current_data.get("call", {}), all_buckets,
            current_totals.get("call", 0), previous_totals.get("call", 0)
        )
        emails_trend = build_trend_metric(
            "emails", current_data.get("email", {}), all_buckets,
            current_totals.get("email", 0), previous_totals.get("email", 0)
        )
        meetings_trend = build_trend_metric(
            "meetings", current_data.get("meeting", {}), all_buckets,
            current_totals.get("meeting", 0), previous_totals.get("meeting", 0)
        )
        total_trend = build_trend_metric(
            "total_activities", total_current_data, all_buckets,
            total_current, total_previous
        )

        return ActivityTrendsResponse(
            calls=calls_trend,
            emails=emails_trend,
            meetings=meetings_trend,
            total_activities=total_trend,
            period=period,
            granularity=granularity,
            generated_at=now
        )

    except Exception as e:
        logger.error(f"Error fetching activity trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch activity trends")


@router.get("/period-comparison", response_model=PeriodComparisonResponse)
async def get_period_comparison(
    period_type: str = Query("week", description="Comparison type: week, month, quarter"),
):
    """
    Compare current period metrics against previous period.

    Calculates percentage changes for key metrics:
    - total_activities, leads_created, opportunities_created
    - meetings_booked, deals_won, revenue
    """
    try:
        supabase = get_supabase()

        # Get date ranges for current and previous periods
        (current_start, current_end), (previous_start, previous_end) = get_period_type_ranges(period_type)

        # Initialize metrics
        current_metrics = {
            "total_activities": 0,
            "leads_created": 0,
            "opportunities_created": 0,
            "meetings_booked": 0,
            "deals_won": 0,
            "revenue": 0.0
        }
        previous_metrics = {
            "total_activities": 0,
            "leads_created": 0,
            "opportunities_created": 0,
            "meetings_booked": 0,
            "deals_won": 0,
            "revenue": 0.0
        }

        # Query activities
        try:
            # Current period activities
            current_activities = supabase.table("fact_activities").select(
                "activity_type"
            ).gte("activity_date", current_start.isoformat()).lte("activity_date", current_end.isoformat()).execute()

            for row in (current_activities.data or []):
                current_metrics["total_activities"] += 1
                if (row.get("activity_type") or "").lower() == "meeting":
                    current_metrics["meetings_booked"] += 1

            # Previous period activities
            prev_activities = supabase.table("fact_activities").select(
                "activity_type"
            ).gte("activity_date", previous_start.isoformat()).lt("activity_date", previous_end.isoformat()).execute()

            for row in (prev_activities.data or []):
                previous_metrics["total_activities"] += 1
                if (row.get("activity_type") or "").lower() == "meeting":
                    previous_metrics["meetings_booked"] += 1

        except Exception as e:
            logger.debug(f"fact_activities query failed: {e}")

        # Query leads (dim_companies)
        try:
            # Current period leads
            current_leads = supabase.table("dim_companies").select(
                "company_id"
            ).gte("created_at", current_start.isoformat()).lte("created_at", current_end.isoformat()).execute()
            current_metrics["leads_created"] = len(current_leads.data or [])

            # Previous period leads
            prev_leads = supabase.table("dim_companies").select(
                "company_id"
            ).gte("created_at", previous_start.isoformat()).lt("created_at", previous_end.isoformat()).execute()
            previous_metrics["leads_created"] = len(prev_leads.data or [])

        except Exception as e:
            logger.debug(f"dim_companies query failed: {e}")

        # Query opportunities
        try:
            # Current period opportunities created
            current_opps = supabase.table("crm_opportunities").select(
                "id, stage, amount"
            ).gte("created_at", current_start.isoformat()).lte("created_at", current_end.isoformat()).execute()

            for row in (current_opps.data or []):
                current_metrics["opportunities_created"] += 1
                if row.get("stage") == "won":
                    current_metrics["deals_won"] += 1
                    current_metrics["revenue"] += float(row.get("amount") or 0)

            # Previous period opportunities
            prev_opps = supabase.table("crm_opportunities").select(
                "id, stage, amount"
            ).gte("created_at", previous_start.isoformat()).lt("created_at", previous_end.isoformat()).execute()

            for row in (prev_opps.data or []):
                previous_metrics["opportunities_created"] += 1
                if row.get("stage") == "won":
                    previous_metrics["deals_won"] += 1
                    previous_metrics["revenue"] += float(row.get("amount") or 0)

        except Exception as e:
            logger.debug(f"crm_opportunities query failed: {e}")

            # Fallback to fact_opportunities
            try:
                current_opps = supabase.table("fact_opportunities").select(
                    "opportunity_id, stage, value_usd"
                ).gte("created_at", current_start.isoformat()).lte("created_at", current_end.isoformat()).execute()

                for row in (current_opps.data or []):
                    current_metrics["opportunities_created"] += 1
                    if row.get("stage") == "won":
                        current_metrics["deals_won"] += 1
                        current_metrics["revenue"] += float(row.get("value_usd") or 0)

                prev_opps = supabase.table("fact_opportunities").select(
                    "opportunity_id, stage, value_usd"
                ).gte("created_at", previous_start.isoformat()).lt("created_at", previous_end.isoformat()).execute()

                for row in (prev_opps.data or []):
                    previous_metrics["opportunities_created"] += 1
                    if row.get("stage") == "won":
                        previous_metrics["deals_won"] += 1
                        previous_metrics["revenue"] += float(row.get("value_usd") or 0)

            except Exception as e2:
                logger.debug(f"fact_opportunities query also failed: {e2}")

        # Calculate percentage changes
        changes = {}
        for key in current_metrics:
            changes[key] = calculate_change_percent(
                float(current_metrics[key]),
                float(previous_metrics[key])
            )

        return PeriodComparisonResponse(
            current_period=current_metrics,
            previous_period=previous_metrics,
            changes=changes,
            period_type=period_type
        )

    except Exception as e:
        logger.error(f"Error fetching period comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch period comparison")
