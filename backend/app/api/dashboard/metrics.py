"""
Dashboard Metrics Module
=========================
Core metrics endpoints for executive summary and combined stats.

Endpoints:
- GET /metrics - Executive summary KPIs
- GET /combined-stats - Combined pipeline stats from multiple sources

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .shared import (
    get_supabase,
    fetch_close_opportunities_filtered,
    POST_PIVOT_DATE,
    FISCAL_QUARTERS,
    ESTIMATED_COST_PER_LEAD,
    ESTIMATED_QUALIFICATION_TIME_MS,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class QuarterlyMetrics(BaseModel):
    """Metrics for a specific fiscal quarter."""
    quarter: str  # e.g., "Q3 2025"
    won_deals: int
    won_value: float
    lost_deals: int
    lost_value: float


class MetricsSummary(BaseModel):
    """Executive summary metrics."""
    total_leads: int
    qualified_leads: int
    meetings_booked: int
    opportunities: int
    won_deals: int
    lost_deals: int
    qualification_rate: float
    meeting_conversion_rate: float
    opportunity_conversion_rate: float
    win_rate: float
    avg_qualification_time_ms: float
    total_cost_usd: float
    cost_per_lead: float
    total_revenue: float
    avg_deal_size: float
    period_start: str
    period_end: str
    # Quarterly breakdown (Q3 + Q4)
    quarterly: Optional[Dict[str, QuarterlyMetrics]] = None
    # Post-pivot totals (Sep 9 onwards)
    post_pivot: Optional[Dict[str, Any]] = None
    # NEW: Executive Dashboard KPIs
    icp_fit_count: int  # Platinum + Gold tier companies
    atl_contacts: int  # Above-the-line decision makers
    call_ready: int  # Contacts with phone numbers
    outreach_sent: int  # Emails/SMS sent today


class CombinedStatsResponse(BaseModel):
    """Combined pipeline stats from multiple sources."""
    total_contractors: int
    sales_agent_count: int
    dealer_scraper_estimate: int
    total_contacts: int
    atl_contacts: int
    btl_contacts: int
    oem_certifications: int
    data_sources: Dict[str, Any]
    updated_at: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/metrics", response_model=MetricsSummary)
async def get_metrics():
    """
    Get executive summary metrics from Supabase.
    """
    try:
        supabase = get_supabase()

        # Get company counts by stage (using correct column names)
        companies = supabase.table("dim_companies").select(
            "company_id, icp_tier, current_stage"
        ).execute()
        total_leads = len(companies.data) if companies.data else 0

        # Count by tier
        tier_counts = {}
        stage_counts = {"COLD": 0, "WARM": 0, "HOT": 0}
        for c in (companies.data or []):
            tier = c.get("icp_tier") or "UNKNOWN"
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            stage = c.get("current_stage") or "COLD"
            if stage in stage_counts:
                stage_counts[stage] += 1

        # Qualified = SILVER or better
        qualified = tier_counts.get("PLATINUM", 0) + tier_counts.get("GOLD", 0) + tier_counts.get("SILVER", 0)

        # Get contacts count (using correct column: is_atl instead of contact_type)
        contacts = supabase.table("dim_contacts").select(
            "contact_id, is_atl, email, phone"
        ).execute()

        # NEW: Executive Dashboard KPIs
        # ICP Fit Count (Platinum + Gold tier companies)
        icp_fit_count = tier_counts.get("PLATINUM", 0) + tier_counts.get("GOLD", 0)

        # ATL Contacts (Above-the-line decision makers)
        atl_contacts = len([c for c in (contacts.data or []) if c.get("is_atl")])

        # Call Ready (contacts with phone numbers)
        call_ready = len([c for c in (contacts.data or []) if c.get("phone")])

        # Outreach Sent (emails/SMS sent today)
        # Query fact_close_activities for today's outreach
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        outreach_sent = 0
        try:
            outreach_response = supabase.table("fact_close_activities").select(
                "id", count="exact"
            ).in_("activity_type", ["Email", "SMS"]).gte(
                "activity_date", today_start.isoformat()
            ).execute()
            outreach_sent = outreach_response.count or 0
        except Exception as outreach_err:
            logger.debug(f"Could not fetch outreach count: {outreach_err}")

        # Calculate rates
        qualification_rate = qualified / total_leads if total_leads > 0 else 0

        # Get REAL deal metrics directly from Close CRM API
        # Fetches: (1) Post-pivot data (Sep 9 onwards), (2) Q3 + Q4 quarterly breakdown
        quarterly_data = {}
        post_pivot_data = {}

        try:
            # === POST-PIVOT DATA (Sep 9, 2025 onwards) ===
            _, won_agg = fetch_close_opportunities_filtered(
                status_type="won",
                date_won_gte=POST_PIVOT_DATE,
                aggregate_only=True
            )
            won_deals = won_agg.get("total_results", 0)
            total_revenue = won_agg.get("total_value_annualized", 0)

            _, lost_agg = fetch_close_opportunities_filtered(
                status_type="lost",
                date_lost_gte=POST_PIVOT_DATE,
                aggregate_only=True
            )
            lost_deals = lost_agg.get("total_results", 0)

            _, active_agg = fetch_close_opportunities_filtered(
                status_type="active",
                aggregate_only=True
            )
            open_opps = active_agg.get("total_results", 0)

            opportunities = won_deals + lost_deals + open_opps
            meetings_booked = opportunities

            avg_deal_size = total_revenue / won_deals if won_deals > 0 else 0
            total_closed = won_deals + lost_deals
            win_rate = won_deals / total_closed if total_closed > 0 else 0
            meeting_conversion = opportunities / total_leads if total_leads > 0 else 0
            opp_conversion = won_deals / opportunities if opportunities > 0 else 0

            post_pivot_data = {
                "start_date": POST_PIVOT_DATE,
                "won_deals": won_deals,
                "won_value": total_revenue,
                "lost_deals": lost_deals,
                "lost_value": lost_agg.get("total_value_annualized", 0),
                "active_deals": open_opps,
            }

            # === QUARTERLY DATA (Q3 + Q4 2025) ===
            for qtr_key, qtr_def in FISCAL_QUARTERS.items():
                _, q_won = fetch_close_opportunities_filtered(
                    status_type="won",
                    date_won_gte=qtr_def["start"],
                    date_won_lte=qtr_def["end"],
                    aggregate_only=True
                )
                _, q_lost = fetch_close_opportunities_filtered(
                    status_type="lost",
                    date_lost_gte=qtr_def["start"],
                    date_lost_lte=qtr_def["end"],
                    aggregate_only=True
                )
                quarterly_data[qtr_key] = QuarterlyMetrics(
                    quarter=qtr_def["label"],
                    won_deals=q_won.get("total_results", 0),
                    won_value=q_won.get("total_value_annualized", 0),
                    lost_deals=q_lost.get("total_results", 0),
                    lost_value=q_lost.get("total_value_annualized", 0),
                )

        except Exception as opp_err:
            logger.warning(f"Could not fetch Close opportunities from API: {opp_err}")
            meetings_booked = 0
            opportunities = 0
            won_deals = 0
            lost_deals = 0
            total_revenue = 0
            avg_deal_size = 0
            win_rate = 0
            meeting_conversion = 0
            opp_conversion = 0

        # Cost estimates (configurable via env vars - real cost tracking TBD)
        cost_per_lead = ESTIMATED_COST_PER_LEAD
        total_cost = total_leads * cost_per_lead

        # Try to get actual avg qualification time from audit logs
        avg_qual_time = ESTIMATED_QUALIFICATION_TIME_MS
        try:
            qual_logs = supabase.table("lead_audit_log").select(
                "latency_ms"
            ).eq("event_type", "lead_qualified").not_.is_("latency_ms", "null").limit(100).execute()
            if qual_logs.data and len(qual_logs.data) > 0:
                latencies = [r["latency_ms"] for r in qual_logs.data if r.get("latency_ms")]
                if latencies:
                    avg_qual_time = sum(latencies) / len(latencies)
        except Exception as qual_err:
            logger.debug(f"Could not fetch qualification times from audit: {qual_err}")

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        return MetricsSummary(
            total_leads=total_leads,
            qualified_leads=qualified,
            meetings_booked=meetings_booked,
            opportunities=opportunities,
            won_deals=won_deals,
            lost_deals=lost_deals,
            qualification_rate=qualification_rate,
            meeting_conversion_rate=meeting_conversion,
            opportunity_conversion_rate=opp_conversion,
            win_rate=win_rate,
            avg_qualification_time_ms=avg_qual_time,
            total_cost_usd=total_cost,
            cost_per_lead=cost_per_lead,
            total_revenue=total_revenue,
            avg_deal_size=avg_deal_size,
            period_start=week_ago.isoformat(),
            period_end=now.isoformat(),
            # Quarterly breakdown (Q3 + Q4 2025)
            quarterly=quarterly_data if quarterly_data else None,
            # Post-pivot totals (Sep 9, 2025 onwards)
            post_pivot=post_pivot_data if post_pivot_data else None,
            # NEW: Executive Dashboard KPIs
            icp_fit_count=icp_fit_count,
            atl_contacts=atl_contacts,
            call_ready=call_ready,
            outreach_sent=outreach_sent,
        )

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard metrics")


@router.get("/combined-stats", response_model=CombinedStatsResponse)
async def get_combined_stats():
    """
    Get combined pipeline stats from both sales-agent and dealer-scraper projects.
    """
    try:
        supabase = get_supabase()

        # Get all companies
        companies = supabase.table("dim_companies").select(
            "company_id, company_name, source"
        ).execute()
        total_companies = len(companies.data or [])

        # Count by source
        sales_agent_count = len([c for c in (companies.data or []) if c.get("source") == "sales-agent"])
        dealer_scraper_count = len([c for c in (companies.data or []) if c.get("source") == "dealer-scraper"])

        # Get contacts
        contacts = supabase.table("dim_contacts").select(
            "contact_id, is_atl"
        ).execute()
        total_contacts = len(contacts.data or [])
        atl_contacts = len([c for c in (contacts.data or []) if c.get("is_atl")])
        btl_contacts = total_contacts - atl_contacts

        # Count OEM certifications (distinct OEM brands)
        companies_with_oems = supabase.table("dim_companies").select(
            "oem_brands"
        ).not_.is_("oem_brands", "null").execute()

        unique_oems = set()
        for company in (companies_with_oems.data or []):
            oem_list = company.get("oem_brands") or []
            if isinstance(oem_list, list):
                unique_oems.update(oem_list)
        oem_certifications = len(unique_oems)

        now = datetime.now(timezone.utc)

        return CombinedStatsResponse(
            total_contractors=total_companies,
            sales_agent_count=sales_agent_count,
            dealer_scraper_estimate=dealer_scraper_count,
            total_contacts=total_contacts,
            atl_contacts=atl_contacts,
            btl_contacts=btl_contacts,
            oem_certifications=oem_certifications,
            data_sources={
                "sales_agent": {
                    "description": "Enriched leads from manual discovery",
                    "count": sales_agent_count
                },
                "dealer_scraper": {
                    "description": "Deep scraped contractor data",
                    "count": dealer_scraper_count
                }
            },
            updated_at=now.isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching combined stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch combined stats")
