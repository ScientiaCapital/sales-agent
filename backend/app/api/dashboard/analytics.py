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
