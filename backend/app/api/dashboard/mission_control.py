"""
Dashboard Mission Control Module
=================================
Mission control stats endpoint for the Contractor Hunter Dashboard.

Endpoints:
- GET /mission-control - All stats needed for the MissionControl arcade dashboard

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .shared import get_supabase, fetch_close_opportunities_filtered, POST_PIVOT_DATE

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class MissionControlStatsResponse(BaseModel):
    """Stats for the MissionControl arcade dashboard."""
    totalLeads: int
    totalContacts: int
    atlContacts: int
    enrichedLeads: int
    platinumLeads: int
    goldLeads: int
    silverLeads: int
    bronzeLeads: int
    hotLeads: int
    leadsWithPhone: int
    leadsWithEmail: int
    leadsAddedToday: int
    leadsAddedThisWeek: int


class TradeVerticalsResponse(BaseModel):
    """Trade vertical counts."""
    hvac: int
    solar: int
    electrical: int
    plumbing: int
    roofing: int
    generator: int
    battery: int
    lowVoltage: int
    fireSafety: int


class MissionControlFullResponse(BaseModel):
    """Full response for MissionControl dashboard."""
    stats: MissionControlStatsResponse
    trades: TradeVerticalsResponse
    activityLog: List[Dict[str, Any]]
    pipelineValue: float
    dealsCount: int
    winRate: float
    avgDealSize: float
    updatedAt: str


# ============================================================================
# Endpoint
# ============================================================================

@router.get("/mission-control", response_model=MissionControlFullResponse)
async def get_mission_control_stats():
    """
    Get all stats needed for the MissionControl arcade dashboard.

    This endpoint provides the same data as direct Supabase queries,
    but uses the service key so the frontend doesn't need credentials.
    """
    try:
        supabase = get_supabase()

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Fetch companies
        companies_result = supabase.table("dim_companies").select(
            "company_id, company_name, icp_tier, icp_score, phone, domain, "
            "services_offered, oem_brands, trade_count, ai_enriched_at, created_at"
        ).execute()
        companies = companies_result.data or []

        # Fetch contacts
        contacts_result = supabase.table("dim_contacts").select(
            "contact_id, company_id, is_atl, email, phone"
        ).execute()
        contacts = contacts_result.data or []

        # Build contact lookup
        contact_by_company: Dict[str, Dict[str, bool]] = {}
        for contact in contacts:
            cid = contact.get("company_id")
            if cid:
                if cid not in contact_by_company:
                    contact_by_company[cid] = {"hasEmail": False, "hasPhone": False, "isAtl": False}
                if contact.get("email"):
                    contact_by_company[cid]["hasEmail"] = True
                if contact.get("phone"):
                    contact_by_company[cid]["hasPhone"] = True
                if contact.get("is_atl"):
                    contact_by_company[cid]["isAtl"] = True

        # Calculate HOT leads (ATL contact with both email AND phone)
        hot_count = 0
        for company in companies:
            cid = company.get("company_id")
            contact_info = contact_by_company.get(cid, {})
            if contact_info.get("isAtl") and contact_info.get("hasEmail") and contact_info.get("hasPhone"):
                hot_count += 1

        # Count ICP tiers
        tier_counts = {"PLATINUM": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0}
        for c in companies:
            tier = c.get("icp_tier")
            if tier in tier_counts:
                tier_counts[tier] += 1

        # Count enriched
        enriched_count = len([c for c in companies if c.get("ai_enriched_at")])

        # Count with phone (company phone)
        with_phone = len([c for c in companies if c.get("phone")])

        # Count with email (contacts with email)
        with_email = len([cid for cid, info in contact_by_company.items() if info.get("hasEmail")])

        # Count today and this week
        today_count = 0
        week_count = 0
        for c in companies:
            created = c.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created_dt >= today_start:
                        today_count += 1
                    if created_dt >= week_start:
                        week_count += 1
                except (ValueError, TypeError):
                    pass

        # Trade verticals detection
        def services_check(services: list, keywords: list) -> bool:
            if not services:
                return False
            lower_services = [str(s).lower() for s in services]
            return any(kw in svc for kw in keywords for svc in lower_services)

        def oem_check(oems: list, keywords: list) -> bool:
            if not oems:
                return False
            lower_oems = [str(o).lower() for o in oems]
            return any(kw in oem for kw in keywords for oem in lower_oems)

        trades = {
            "hvac": 0, "solar": 0, "electrical": 0, "plumbing": 0,
            "roofing": 0, "generator": 0, "battery": 0, "lowVoltage": 0, "fireSafety": 0
        }

        for c in companies:
            services = c.get("services_offered") or []
            oems = c.get("oem_brands") or []

            if services_check(services, ["hvac", "heating", "cooling", "air conditioning"]):
                trades["hvac"] += 1
            if services_check(services, ["solar", "pv", "photovoltaic"]) or oem_check(oems, ["enphase", "solaredge", "sma"]):
                trades["solar"] += 1
            if services_check(services, ["electrical", "electrician"]):
                trades["electrical"] += 1
            if services_check(services, ["plumbing", "plumber"]):
                trades["plumbing"] += 1
            if services_check(services, ["roofing", "roof"]):
                trades["roofing"] += 1
            if services_check(services, ["generator", "backup power"]) or oem_check(oems, ["generac", "kohler", "cummins"]):
                trades["generator"] += 1
            if services_check(services, ["battery", "storage"]) or oem_check(oems, ["powerwall", "enphase battery", "pwrcell"]):
                trades["battery"] += 1
            if services_check(services, ["low voltage", "security", "alarm", "access control", "surveillance"]):
                trades["lowVoltage"] += 1
            if services_check(services, ["fire", "sprinkler", "suppression", "fire alarm"]):
                trades["fireSafety"] += 1

        # Fetch activity from lead_audit_log
        activity_log = []
        try:
            audit_result = supabase.table("lead_audit_log").select(
                "id, event_type, company_name, created_at, details"
            ).order("created_at", desc=True).limit(15).execute()

            event_type_map = {
                "enrichment_complete": ("ENRICHED", "enrichment"),
                "lead_qualified": ("QUALIFIED", "success"),
                "lead_created": ("NEW LEAD", "discovery"),
                "contact_added": ("CONTACT", "agent"),
            }

            for log in (audit_result.data or []):
                event_type = log.get("event_type", "system")
                label, log_type = event_type_map.get(event_type, (event_type.upper(), "system"))
                activity_log.append({
                    "id": log.get("id"),
                    "text": f"{label}: {log.get('company_name', 'Unknown')}",
                    "type": log_type,
                    "timestamp": log.get("created_at", "")[:19].replace("T", " ")
                })
        except Exception as audit_err:
            logger.warning(f"Could not fetch audit log: {audit_err}")

        # Get pipeline metrics from Close CRM
        pipeline_value = 0.0
        deals_count = 0
        win_rate = 0.0
        avg_deal_size = 15000.0  # Default

        try:
            _, active_agg = fetch_close_opportunities_filtered(
                status_type="active",
                aggregate_only=True
            )
            pipeline_value = active_agg.get("total_value_annualized", 0)
            deals_count = active_agg.get("total_results", 0)

            _, won_agg = fetch_close_opportunities_filtered(
                status_type="won",
                date_won_gte=POST_PIVOT_DATE,
                aggregate_only=True
            )
            _, lost_agg = fetch_close_opportunities_filtered(
                status_type="lost",
                date_lost_gte=POST_PIVOT_DATE,
                aggregate_only=True
            )

            won_count = won_agg.get("total_results", 0)
            lost_count = lost_agg.get("total_results", 0)
            total_closed = won_count + lost_count

            if total_closed > 0:
                win_rate = (won_count / total_closed) * 100

            won_value = won_agg.get("total_value_annualized", 0)
            if won_count > 0:
                avg_deal_size = won_value / won_count
        except Exception as close_err:
            logger.warning(f"Could not fetch Close CRM data: {close_err}")

        return MissionControlFullResponse(
            stats=MissionControlStatsResponse(
                totalLeads=len(companies),
                totalContacts=len(contacts),
                atlContacts=len([c for c in contacts if c.get("is_atl")]),
                enrichedLeads=enriched_count,
                platinumLeads=tier_counts["PLATINUM"],
                goldLeads=tier_counts["GOLD"],
                silverLeads=tier_counts["SILVER"],
                bronzeLeads=tier_counts["BRONZE"],
                hotLeads=hot_count,
                leadsWithPhone=with_phone,
                leadsWithEmail=with_email,
                leadsAddedToday=today_count,
                leadsAddedThisWeek=week_count
            ),
            trades=TradeVerticalsResponse(**trades),
            activityLog=activity_log,
            pipelineValue=pipeline_value,
            dealsCount=deals_count,
            winRate=win_rate,
            avgDealSize=avg_deal_size,
            updatedAt=now.isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching mission control stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch mission control stats")
