"""
Dashboard Close CRM Sync Module
================================
Close CRM integration endpoints for outreach metrics, lifecycle funnel, and trifecta scoring.

Endpoints:
- GET /outreach - Outreach metrics from Close CRM
- GET /lifecycle - Lead lifecycle funnel
- GET /trifecta - Trifecta detection statistics

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from .shared import get_supabase, fetch_close_opportunities_filtered, POST_PIVOT_DATE

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class OutreachMetricsData(BaseModel):
    """Outreach channel metrics."""
    total: int
    count_7d: int
    count_mtd: int
    outbound: Optional[int] = 0
    inbound: Optional[int] = 0
    sent: Optional[int] = 0
    received: Optional[int] = 0
    scheduled: Optional[int] = 0
    completed: Optional[int] = 0
    avg_duration: Optional[float] = 0


class OutreachResponse(BaseModel):
    """Outreach metrics response."""
    metrics: Dict[str, OutreachMetricsData]
    summary: Dict[str, Any]
    period: str
    data_source: str
    updated_at: str


class LifecycleStage(BaseModel):
    """Lifecycle funnel stage."""
    name: str
    count: int
    value: float
    color: str
    conversion_rate: Optional[float] = None


class LifecycleResponse(BaseModel):
    """Lifecycle funnel response."""
    stages: List[LifecycleStage]
    total_leads: int
    period: str


class TrifectaStatsResponse(BaseModel):
    """Trifecta detection statistics."""
    unicorn_count: int
    partial_trifecta_count: int
    multi_oem_count: int
    score_distribution: Dict[str, int]
    top_unicorns: List[Dict[str, Any]]
    energy_breakdown: Dict[str, int]
    updated_at: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/outreach", response_model=OutreachResponse)
async def get_outreach_metrics(
    period: str = Query(default="7d", description="Period: 7d or mtd")
):
    """
    Get outreach metrics from close_activities table.
    """
    try:
        supabase = get_supabase()
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Query all activities
        activities = supabase.table("close_activities").select(
            "activity_type, direction, activity_date, duration_seconds, status"
        ).execute()

        # Initialize counters
        metrics_data = {
            "calls": {"total": 0, "7d": 0, "mtd": 0, "outbound": 0, "inbound": 0, "duration_sum": 0, "duration_count": 0},
            "emails": {"total": 0, "7d": 0, "mtd": 0, "sent": 0, "received": 0},
            "sms": {"total": 0, "7d": 0, "mtd": 0, "sent": 0, "received": 0},
            "meetings": {"total": 0, "7d": 0, "mtd": 0, "scheduled": 0, "completed": 0},
        }

        for activity in (activities.data or []):
            atype = (activity.get("activity_type") or "").lower()
            direction = (activity.get("direction") or "").lower()
            status = (activity.get("status") or "").lower()
            activity_date = activity.get("activity_date")

            # Parse date for period filtering
            is_7d = False
            is_mtd = False
            if activity_date:
                try:
                    dt = datetime.fromisoformat(activity_date.replace("Z", "+00:00"))
                    is_7d = dt >= week_ago
                    is_mtd = dt >= month_start
                except (ValueError, TypeError):
                    pass

            # Categorize by type
            if "call" in atype:
                metrics_data["calls"]["total"] += 1
                if is_7d:
                    metrics_data["calls"]["7d"] += 1
                if is_mtd:
                    metrics_data["calls"]["mtd"] += 1
                if direction == "outbound":
                    metrics_data["calls"]["outbound"] += 1
                elif direction == "inbound":
                    metrics_data["calls"]["inbound"] += 1
                if activity.get("duration_seconds"):
                    metrics_data["calls"]["duration_sum"] += activity["duration_seconds"]
                    metrics_data["calls"]["duration_count"] += 1

            elif "email" in atype:
                metrics_data["emails"]["total"] += 1
                if is_7d:
                    metrics_data["emails"]["7d"] += 1
                if is_mtd:
                    metrics_data["emails"]["mtd"] += 1
                if direction == "outbound" or "sent" in status:
                    metrics_data["emails"]["sent"] += 1
                elif direction == "inbound" or "received" in status:
                    metrics_data["emails"]["received"] += 1

            elif "sms" in atype:
                metrics_data["sms"]["total"] += 1
                if is_7d:
                    metrics_data["sms"]["7d"] += 1
                if is_mtd:
                    metrics_data["sms"]["mtd"] += 1
                if direction == "outbound":
                    metrics_data["sms"]["sent"] += 1
                elif direction == "inbound":
                    metrics_data["sms"]["received"] += 1

            elif "meeting" in atype:
                metrics_data["meetings"]["total"] += 1
                if is_7d:
                    metrics_data["meetings"]["7d"] += 1
                if is_mtd:
                    metrics_data["meetings"]["mtd"] += 1
                if "scheduled" in status:
                    metrics_data["meetings"]["scheduled"] += 1
                elif "completed" in status or "done" in status:
                    metrics_data["meetings"]["completed"] += 1

        # Calculate average call duration
        avg_call_duration = 0.0
        if metrics_data["calls"]["duration_count"] > 0:
            avg_call_duration = metrics_data["calls"]["duration_sum"] / metrics_data["calls"]["duration_count"]

        # Build response
        total_outreach = (
            metrics_data["calls"]["total"] +
            metrics_data["emails"]["total"] +
            metrics_data["sms"]["total"]
        )
        total_7d = (
            metrics_data["calls"]["7d"] +
            metrics_data["emails"]["7d"] +
            metrics_data["sms"]["7d"]
        )

        return OutreachResponse(
            metrics={
                "calls": OutreachMetricsData(
                    total=metrics_data["calls"]["total"],
                    count_7d=metrics_data["calls"]["7d"],
                    count_mtd=metrics_data["calls"]["mtd"],
                    outbound=metrics_data["calls"]["outbound"],
                    inbound=metrics_data["calls"]["inbound"],
                    avg_duration=avg_call_duration
                ),
                "emails": OutreachMetricsData(
                    total=metrics_data["emails"]["total"],
                    count_7d=metrics_data["emails"]["7d"],
                    count_mtd=metrics_data["emails"]["mtd"],
                    sent=metrics_data["emails"]["sent"],
                    received=metrics_data["emails"]["received"]
                ),
                "sms": OutreachMetricsData(
                    total=metrics_data["sms"]["total"],
                    count_7d=metrics_data["sms"]["7d"],
                    count_mtd=metrics_data["sms"]["mtd"],
                    sent=metrics_data["sms"]["sent"],
                    received=metrics_data["sms"]["received"]
                ),
                "meetings": OutreachMetricsData(
                    total=metrics_data["meetings"]["total"],
                    count_7d=metrics_data["meetings"]["7d"],
                    count_mtd=metrics_data["meetings"]["mtd"],
                    scheduled=metrics_data["meetings"]["scheduled"],
                    completed=metrics_data["meetings"]["completed"]
                )
            },
            summary={
                "total_outreach": total_outreach,
                "total_7d": total_7d,
                "meetings_booked": metrics_data["meetings"]["total"],
                "response_rate": round(
                    100 * metrics_data["emails"]["received"] / max(metrics_data["emails"]["sent"], 1), 1
                )
            },
            period=period,
            data_source="close_activities",
            updated_at=now.isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching outreach metrics: {e}", exc_info=True)
        # Return zeros on error instead of mock data
        now = datetime.now(timezone.utc)
        return OutreachResponse(
            metrics={
                "calls": OutreachMetricsData(total=0, count_7d=0, count_mtd=0),
                "emails": OutreachMetricsData(total=0, count_7d=0, count_mtd=0),
                "sms": OutreachMetricsData(total=0, count_7d=0, count_mtd=0),
                "meetings": OutreachMetricsData(total=0, count_7d=0, count_mtd=0),
            },
            summary={
                "total_outreach": 0,
                "total_7d": 0,
                "meetings_booked": 0,
                "response_rate": 0.0
            },
            period=period,
            data_source="error_fallback",
            updated_at=now.isoformat()
        )


@router.get("/lifecycle", response_model=LifecycleResponse)
async def get_lifecycle_funnel(
    period: str = Query(default="7d", description="Period: 7d or mtd")
):
    """
    Get lead lifecycle funnel data using REAL Close CRM data.
    """
    try:
        supabase = get_supabase()

        companies = supabase.table("dim_companies").select(
            "company_id, current_stage, icp_tier"
        ).execute()

        stage_counts = {"COLD": 0, "WARM": 0, "HOT": 0}
        tier_counts = {"PLATINUM": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0}

        for c in (companies.data or []):
            stage = c.get("current_stage") or "COLD"
            tier = c.get("icp_tier") or "UNKNOWN"
            if stage in stage_counts:
                stage_counts[stage] += 1
            if tier in tier_counts:
                tier_counts[tier] += 1

        total = len(companies.data or [])
        qualified = tier_counts["PLATINUM"] + tier_counts["GOLD"] + tier_counts["SILVER"]

        # Get REAL opportunity/deal data directly from Close CRM API (post-pivot only)
        # Uses server-side filtering for efficiency
        won_count = 0
        won_value = 0
        opp_count = 0
        opp_value = 0
        try:
            pivot_cutoff = POST_PIVOT_DATE  # "2025-09-09" - post-pivot start date

            # Fetch won deals - use aggregate_only for efficiency
            _, won_agg = fetch_close_opportunities_filtered(
                status_type="won",
                date_won_gte=pivot_cutoff,
                aggregate_only=True
            )
            won_count = won_agg.get("total_results", 0)
            won_value = won_agg.get("total_value_annualized", 0)

            # Fetch lost deals - aggregate only (large count, skip pagination!)
            _, lost_agg = fetch_close_opportunities_filtered(
                status_type="lost",
                date_lost_gte=pivot_cutoff,
                aggregate_only=True
            )
            lost_count = lost_agg.get("total_results", 0)
            lost_value = lost_agg.get("total_value_annualized", 0)

            # Fetch active opportunities - aggregate only
            _, active_agg = fetch_close_opportunities_filtered(
                status_type="active",
                aggregate_only=True
            )
            active_count = active_agg.get("total_results", 0)
            active_value = active_agg.get("total_value_annualized", 0)

            opp_count = won_count + lost_count + active_count
            opp_value = won_value + lost_value + active_value

        except Exception as opp_err:
            logger.warning(f"Could not fetch Close opportunities from API for lifecycle: {opp_err}")
            # Fallback to zeros (no mock data)
            opp_count = 0
            won_count = 0
            won_value = 0

        # Calculate conversion rates from real data
        meeting_to_opp = opp_count / stage_counts["HOT"] if stage_counts["HOT"] > 0 else 0
        opp_to_won = won_count / opp_count if opp_count > 0 else 0

        stages = [
            LifecycleStage(
                name="New Leads",
                count=total,
                value=total * 100,  # Nominal value per lead
                color="#E3F2FD",
                conversion_rate=1.0
            ),
            LifecycleStage(
                name="Qualified",
                count=qualified,
                value=qualified * 500,  # Nominal qualified lead value
                color="#BBDEFB",
                conversion_rate=qualified / total if total > 0 else 0
            ),
            LifecycleStage(
                name="Meeting Set",
                count=stage_counts["HOT"],
                value=stage_counts["HOT"] * 5000,  # Nominal meeting value
                color="#90CAF9",
                conversion_rate=stage_counts["HOT"] / qualified if qualified > 0 else 0
            ),
            LifecycleStage(
                name="Opportunity",
                count=opp_count,
                value=opp_value,  # REAL pipeline value from Close
                color="#64B5F6",
                conversion_rate=meeting_to_opp
            ),
            LifecycleStage(
                name="Won",
                count=won_count,
                value=won_value,  # REAL won revenue from Close
                color="#2196F3",
                conversion_rate=opp_to_won
            )
        ]

        return LifecycleResponse(
            stages=stages,
            total_leads=total,
            period=period
        )

    except Exception as e:
        logger.error(f"Error fetching lifecycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch lifecycle data")


@router.get("/trifecta", response_model=TrifectaStatsResponse)
async def get_trifecta_stats():
    """
    Get Trifecta detection statistics.
    Identifies UNICORN contractors (Solar + Generator + Battery).
    """
    try:
        from app.services.trifecta_scoring import calculate_trifecta_score

        supabase = get_supabase()

        # Get all companies with OEM data
        companies = supabase.table("dim_companies").select(
            "company_id, company_name, oem_brands, services_offered, states_served"
        ).not_.is_("oem_brands", "null").execute()

        # Get contacts for quality scoring
        contacts = supabase.table("dim_contacts").select(
            "company_id, is_atl, email, phone"
        ).execute()

        # Build contact lookup
        contact_map = {}
        for c in (contacts.data or []):
            cid = c.get("company_id")
            if cid:
                if cid not in contact_map:
                    contact_map[cid] = {"has_atl": False, "has_email": False, "has_phone": False}
                if c.get("is_atl"):
                    contact_map[cid]["has_atl"] = True
                if c.get("email"):
                    contact_map[cid]["has_email"] = True
                if c.get("phone"):
                    contact_map[cid]["has_phone"] = True

        # Score all companies
        unicorns = []
        partial_trifecta = []
        multi_oem = []
        score_tiers = {"UNICORN": 0, "PLATINUM": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "LEAD": 0}
        energy_types = {"solar": 0, "generator": 0, "battery": 0}

        for company in (companies.data or []):
            company_id = company.get("company_id")
            company_name = company.get("company_name") or "Unknown"
            oem_brands = company.get("oem_brands") or []
            services_offered = company.get("services_offered") or []
            states_served = company.get("states_served") or []

            # Get contact quality
            contact_info = contact_map.get(company_id, {})

            # Calculate score
            score = calculate_trifecta_score(
                company_name=company_name,
                oem_brands=oem_brands,
                services_offered=services_offered,
                states_served=states_served,
                has_atl_contact=contact_info.get("has_atl", False),
                has_email=contact_info.get("has_email", False),
                has_direct_phone=contact_info.get("has_phone", False)
            )

            # Collect stats
            score_tiers[score.tier] += 1

            if score.has_solar:
                energy_types["solar"] += 1
            if score.has_generator:
                energy_types["generator"] += 1
            if score.has_battery:
                energy_types["battery"] += 1

            if score.is_unicorn:
                unicorns.append({
                    "company_id": str(company_id),
                    "company_name": company_name,
                    "score": score.total,
                    "oem_count": len(oem_brands),
                    "trades": score.trades_detected
                })

            if score.is_partial_trifecta:
                partial_trifecta.append(company_name)

            if len(oem_brands) >= 3:
                multi_oem.append(company_name)

        # Sort unicorns by score
        unicorns.sort(key=lambda x: x["score"], reverse=True)

        now = datetime.now(timezone.utc)

        return TrifectaStatsResponse(
            unicorn_count=len(unicorns),
            partial_trifecta_count=len(partial_trifecta),
            multi_oem_count=len(multi_oem),
            score_distribution=score_tiers,
            top_unicorns=unicorns[:10],
            energy_breakdown=energy_types,
            updated_at=now.isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching trifecta stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch trifecta stats")
