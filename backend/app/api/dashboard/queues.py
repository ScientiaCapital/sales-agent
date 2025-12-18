"""
Dashboard Queues Module
========================
Work queue management endpoints: ICP queue, attention queue, activity feed, imports.

Endpoints:
- GET /icp-queue - ICP leads by smart views
- GET /attention - Leads needing attention
- GET /activity - Recent activity feed
- GET /workqueue - BDR work queue
- GET /imports - Recent import history

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from .shared import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class Lead(BaseModel):
    """Lead for ICP queue."""
    id: str
    company_name: str
    domain: Optional[str] = None
    close_lead_id: Optional[str] = None
    close_lead_url: Optional[str] = None
    status: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    smart_view: str
    quarter: str
    priority: int
    color: str
    days_since_activity: int
    is_untouched: bool


class SmartView(BaseModel):
    """Smart view grouping."""
    name: str
    color: str
    priority: int
    leads: List[Lead]
    total: int
    untouched: int


class AETotals(BaseModel):
    """AE totals."""
    active_count: int
    active_value: float
    won_count: int
    won_value: float
    lost_count: int
    lost_value: float


class AETracking(BaseModel):
    """AE pipeline tracking."""
    name: str
    active: List[Dict[str, Any]]
    won: List[Dict[str, Any]]
    lost: List[Dict[str, Any]]
    totals: AETotals


class ICPQueueResponse(BaseModel):
    """ICP Queue response."""
    smart_views: Dict[str, SmartView]
    untouched_leads: List[Lead]
    ae_tracking: Dict[str, AETracking]
    summary: Dict[str, Any]
    philosophy: str
    data_source: str
    # NEW: Executive Dashboard data
    tier_breakdown: Dict[str, int]  # PLATINUM, GOLD, SILVER, BRONZE, UNSCORED
    state_breakdown: Dict[str, int]  # TX: 65, NJ: 50, FL: 43, etc.


class ActivityItem(BaseModel):
    """Activity feed item."""
    id: str
    type: str
    title: str
    description: str
    timestamp: str
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    icon: str
    color: str


class ActivityResponse(BaseModel):
    """Activity feed response."""
    activities: List[ActivityItem]
    total: int
    period_hours: int


class AttentionItem(BaseModel):
    """Item needing attention."""
    id: str
    company_name: str
    reason: str
    priority: str
    days_stale: int
    last_activity: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class AttentionResponse(BaseModel):
    """Attention queue response."""
    items: List[AttentionItem]
    total: int
    urgent_count: int


class WorkQueueItem(BaseModel):
    """BDR work queue item."""
    id: str
    company_name: str
    task_type: str
    priority: int
    due_date: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    close_lead_url: Optional[str] = None
    # Executive Dashboard fields
    state: Optional[str] = None
    lead_score: Optional[int] = None
    icp_tier: Optional[str] = None
    website: Optional[str] = None
    contact_title: Optional[str] = None


class WorkQueueResponse(BaseModel):
    """BDR work queue response."""
    tasks: List[WorkQueueItem]
    total: int
    by_priority: Dict[str, int]


class ImportRecord(BaseModel):
    """Import history record."""
    id: str
    filename: str
    status: str
    total_rows: int
    processed: int
    errors: int
    created_at: str


class ImportHistoryResponse(BaseModel):
    """Import history response."""
    imports: List[ImportRecord]
    total: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/icp-queue", response_model=ICPQueueResponse)
async def get_icp_queue(
    days_threshold: int = Query(default=7, description="Days for untouched threshold"),
    limit: int = Query(default=10, description="Leads per smart view"),
    include_customers: bool = Query(default=False, description="Include existing customers")
):
    """
    Get ICP queue organized by smart views.
    Excludes customers and do_not_contact by default.
    """
    # Stages to exclude from GTM views
    EXCLUDED_STAGES = ["customer", "do_not_contact"]

    try:
        supabase = get_supabase()

        # Get companies with Close CRM fields and state for geographic analysis
        query = supabase.table("dim_companies").select(
            "company_id, company_name, domain, phone, state, icp_tier, icp_score, current_stage, updated_at, close_lead_id"
        )

        if not include_customers:
            query = query.not_.in_("current_stage", EXCLUDED_STAGES)

        companies = query.execute()

        contacts = supabase.table("dim_contacts").select(
            "contact_id, company_id, full_name, email, phone, is_atl"
        ).execute()

        # Build contact lookup
        contact_map = {}
        for c in (contacts.data or []):
            cid = c.get("company_id")
            if cid:
                if cid not in contact_map:
                    contact_map[cid] = []
                contact_map[cid].append(c)

        # Define smart views
        smart_views = {
            "platinum_gold": SmartView(
                name="PLATINUM/GOLD",
                color="#FFD700",
                priority=1,
                leads=[],
                total=0,
                untouched=0
            ),
            "hot_leads": SmartView(
                name="🔥 HOT Leads",
                color="#FF4444",
                priority=2,
                leads=[],
                total=0,
                untouched=0
            ),
            "with_phone": SmartView(
                name="Has Direct Phone",
                color="#4CAF50",
                priority=3,
                leads=[],
                total=0,
                untouched=0
            ),
            "silver_tier": SmartView(
                name="SILVER Tier",
                color="#C0C0C0",
                priority=4,
                leads=[],
                total=0,
                untouched=0
            ),
            "needs_enrichment": SmartView(
                name="Needs Enrichment",
                color="#9C27B0",
                priority=5,
                leads=[],
                total=0,
                untouched=0
            )
        }

        untouched_leads = []
        now = datetime.now(timezone.utc)
        quarter_map = {"Q3": 0, "Q4": 0, "PPL": 0}

        # NEW: Track tier breakdown and state breakdown for Executive Dashboard
        tier_breakdown = {
            "PLATINUM": 0,
            "GOLD": 0,
            "SILVER": 0,
            "BRONZE": 0,
            "UNSCORED": 0
        }
        state_counts = {}

        for company in (companies.data or []):
            company_name = company.get("company_name") or ""
            cid = company.get("company_id")
            tier = company.get("icp_tier") or "UNKNOWN"
            stage = company.get("current_stage") or "COLD"
            updated = company.get("updated_at")
            domain = company.get("domain")
            state = company.get("state")
            close_lead_id = company.get("close_lead_id")
            # Build Close CRM URL from lead_id
            close_lead_url = f"https://app.close.com/lead/{close_lead_id}/" if close_lead_id else None

            # Track tier breakdown
            if tier in tier_breakdown:
                tier_breakdown[tier] += 1
            else:
                tier_breakdown["UNSCORED"] += 1

            # Track state breakdown
            if state:
                state_counts[state] = state_counts.get(state, 0) + 1

            # Calculate days since update
            days_since = 999
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    days_since = (now - updated_dt).days
                except (ValueError, TypeError):
                    pass

            is_untouched = days_since > days_threshold

            # Get contact info (ATL contact)
            company_contacts = contact_map.get(cid, [])
            atl_contact = next((c for c in company_contacts if c.get("is_atl")), None)

            lead = Lead(
                id=str(cid),
                company_name=company_name or "Unknown",
                domain=domain,
                close_lead_id=close_lead_id,
                close_lead_url=close_lead_url,
                status=stage,
                contact_name=atl_contact.get("full_name") if atl_contact else None,
                contact_phone=atl_contact.get("phone") if atl_contact else company.get("phone"),
                contact_email=atl_contact.get("email") if atl_contact else None,
                smart_view=tier,
                quarter="Q4",
                priority=1 if tier in ["PLATINUM", "GOLD"] else 2 if tier == "SILVER" else 3,
                color="#FFD700" if tier == "PLATINUM" else "#C0C0C0" if tier == "SILVER" else "#CD7F32",
                days_since_activity=days_since,
                is_untouched=is_untouched
            )

            # Categorize into smart views
            if tier in ["PLATINUM", "GOLD"]:
                smart_views["platinum_gold"].leads.append(lead)
                smart_views["platinum_gold"].total += 1
                if is_untouched:
                    smart_views["platinum_gold"].untouched += 1
                    untouched_leads.append(lead)
                quarter_map["Q4"] += 1

            if stage == "HOT":
                smart_views["hot_leads"].leads.append(lead)
                smart_views["hot_leads"].total += 1
                if is_untouched:
                    smart_views["hot_leads"].untouched += 1

            if atl_contact and atl_contact.get("phone"):
                smart_views["with_phone"].leads.append(lead)
                smart_views["with_phone"].total += 1
                if is_untouched:
                    smart_views["with_phone"].untouched += 1

            if tier == "SILVER":
                smart_views["silver_tier"].leads.append(lead)
                smart_views["silver_tier"].total += 1
                if is_untouched:
                    smart_views["silver_tier"].untouched += 1
                quarter_map["Q3"] += 1

            if tier in ["BRONZE", "UNKNOWN"]:
                smart_views["needs_enrichment"].leads.append(lead)
                smart_views["needs_enrichment"].total += 1
                quarter_map["PPL"] += 1

        # Sort untouched by days since activity
        untouched_leads.sort(key=lambda x: x.days_since_activity, reverse=True)

        # Limit leads per view
        for view in smart_views.values():
            view.leads = view.leads[:limit]

        # Sort state breakdown by count (descending) for horizontal bar chart
        state_breakdown = dict(sorted(state_counts.items(), key=lambda x: x[1], reverse=True))

        return ICPQueueResponse(
            smart_views=smart_views,
            untouched_leads=untouched_leads[:15],
            ae_tracking={
                "Tim": AETracking(
                    name="Tim Kipper",
                    active=[],
                    won=[],
                    lost=[],
                    totals=AETotals(
                        active_count=smart_views["hot_leads"].total,
                        active_value=smart_views["hot_leads"].total * 15000,
                        won_count=0,
                        won_value=0,
                        lost_count=0,
                        lost_value=0
                    )
                )
            },
            summary={
                "total_leads": len(companies.data or []),
                "untouched_count": len(untouched_leads),
                "by_quarter": quarter_map
            },
            philosophy="Never Lost, Always Aware",
            data_source="Supabase",
            # NEW: Executive Dashboard data
            tier_breakdown=tier_breakdown,
            state_breakdown=state_breakdown
        )

    except Exception as e:
        logger.error(f"Error fetching ICP queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch ICP queue data")


@router.get("/activity", response_model=ActivityResponse)
async def get_activity(
    hours: int = Query(default=24, description="Hours of activity to fetch"),
    limit: int = Query(default=15, description="Max items to return")
):
    """
    Get recent activity feed.
    """
    try:
        supabase = get_supabase()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        companies = supabase.table("dim_companies").select(
            "company_id, company_name, updated_at, icp_tier, current_stage"
        ).gte("updated_at", cutoff.isoformat()).order(
            "updated_at", desc=True
        ).limit(limit).execute()

        activities = []
        for c in (companies.data or []):
            tier = c.get("icp_tier") or "UNKNOWN"
            stage = c.get("current_stage") or "COLD"

            if tier in ["PLATINUM", "GOLD"]:
                activity_type = "high_value_lead"
                icon = "star"
                color = "text-yellow-500"
                title = f"High-Value Lead: {c.get('company_name')}"
                desc = f"ICP Tier: {tier}"
            elif stage == "HOT":
                activity_type = "hot_lead"
                icon = "flame"
                color = "text-red-500"
                title = f"HOT Lead Updated: {c.get('company_name')}"
                desc = "Lead moved to HOT stage"
            else:
                activity_type = "enrichment"
                icon = "refresh"
                color = "text-blue-500"
                title = f"Lead Enriched: {c.get('company_name')}"
                desc = f"ICP Score calculated: {tier}"

            activities.append(ActivityItem(
                id=str(c.get("company_id")),
                type=activity_type,
                title=title,
                description=desc,
                timestamp=c.get("updated_at") or "",
                lead_id=str(c.get("company_id")),
                lead_name=c.get("company_name"),
                icon=icon,
                color=color
            ))

        return ActivityResponse(
            activities=activities,
            total=len(activities),
            period_hours=hours
        )

    except Exception as e:
        logger.error(f"Error fetching activity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch activity data")


@router.get("/attention", response_model=AttentionResponse)
async def get_attention_queue():
    """
    Get leads needing immediate attention.
    Excludes customers and do_not_contact.
    """
    EXCLUDED_STAGES = ["customer", "do_not_contact"]

    try:
        supabase = get_supabase()
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        companies = supabase.table("dim_companies").select(
            "company_id, company_name, phone, icp_tier, current_stage, updated_at, close_lead_id"
        ).in_("icp_tier", ["PLATINUM", "GOLD", "SILVER"]).not_.in_(
            "current_stage", EXCLUDED_STAGES
        ).lt(
            "updated_at", cutoff.isoformat()
        ).limit(20).execute()

        contacts = supabase.table("dim_contacts").select(
            "company_id, full_name, phone, email"
        ).execute()

        contact_map = {c.get("company_id"): c for c in (contacts.data or [])}

        items = []
        urgent_count = 0
        now = datetime.now(timezone.utc)

        for c in (companies.data or []):
            tier = c.get("icp_tier")
            updated = c.get("updated_at")

            days_stale = 999
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    days_stale = (now - updated_dt).days
                except (ValueError, TypeError):
                    pass

            priority = "HIGH" if tier in ["PLATINUM", "GOLD"] else "MEDIUM"
            if priority == "HIGH":
                urgent_count += 1

            contact = contact_map.get(c.get("company_id"))

            items.append(AttentionItem(
                id=str(c.get("company_id")),
                company_name=c.get("company_name") or "Unknown",
                reason=f"No activity for {days_stale} days",
                priority=priority,
                days_stale=days_stale,
                last_activity=updated,
                contact_name=contact.get("full_name") if contact else None,
                contact_phone=contact.get("phone") if contact else c.get("phone")
            ))

        items.sort(key=lambda x: x.days_stale, reverse=True)

        return AttentionResponse(
            items=items[:15],
            total=len(items),
            urgent_count=urgent_count
        )

    except Exception as e:
        logger.error(f"Error fetching attention queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch attention queue")


@router.get("/workqueue", response_model=WorkQueueResponse)
async def get_work_queue():
    """
    Get BDR work queue.
    Excludes customers and do_not_contact.
    """
    EXCLUDED_STAGES = ["customer", "do_not_contact"]

    try:
        supabase = get_supabase()

        # HOT leads (excluding customers) - include state, icp_score, icp_tier, domain for Executive Dashboard
        hot_leads = supabase.table("dim_companies").select(
            "company_id, company_name, phone, domain, close_lead_id, state, icp_score, icp_tier"
        ).eq("current_stage", "HOT").not_.in_(
            "current_stage", EXCLUDED_STAGES
        ).limit(10).execute()

        # High tier leads (excluding customers) - include state, icp_score, icp_tier, domain for Executive Dashboard
        high_tier = supabase.table("dim_companies").select(
            "company_id, company_name, phone, domain, close_lead_id, state, icp_score, icp_tier"
        ).in_("icp_tier", ["PLATINUM", "GOLD"]).not_.in_(
            "current_stage", EXCLUDED_STAGES
        ).limit(10).execute()

        contacts = supabase.table("dim_contacts").select(
            "company_id, full_name, phone, email, title"
        ).execute()

        contact_map = {c.get("company_id"): c for c in (contacts.data or [])}

        tasks = []
        priority_counts = {"P1": 0, "P2": 0, "P3": 0}
        seen_ids = set()

        # Add HOT leads as P1
        for c in (hot_leads.data or []):
            cid = c.get("company_id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            contact = contact_map.get(cid)
            close_lead_id = c.get("close_lead_id")
            close_lead_url = f"https://app.close.com/lead/{close_lead_id}/" if close_lead_id else None
            tasks.append(WorkQueueItem(
                id=str(cid),
                company_name=c.get("company_name") or "Unknown",
                task_type="CALL",
                priority=1,
                contact_name=contact.get("full_name") if contact else None,
                contact_phone=contact.get("phone") if contact else c.get("phone"),
                contact_email=contact.get("email") if contact else None,
                notes="HOT lead - call today",
                close_lead_url=close_lead_url,
                # Executive Dashboard fields
                state=c.get("state"),
                lead_score=c.get("icp_score"),
                icp_tier=c.get("icp_tier"),
                website=c.get("domain"),
                contact_title=contact.get("title") if contact else None
            ))
            priority_counts["P1"] += 1

        # Add high tier as P2
        for c in (high_tier.data or []):
            cid = c.get("company_id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            contact = contact_map.get(cid)
            close_lead_id = c.get("close_lead_id")
            close_lead_url = f"https://app.close.com/lead/{close_lead_id}/" if close_lead_id else None
            tasks.append(WorkQueueItem(
                id=str(cid),
                company_name=c.get("company_name") or "Unknown",
                task_type="RESEARCH",
                priority=2,
                contact_name=contact.get("full_name") if contact else None,
                contact_phone=contact.get("phone") if contact else c.get("phone"),
                contact_email=contact.get("email") if contact else None,
                notes="High-value lead",
                close_lead_url=close_lead_url,
                # Executive Dashboard fields
                state=c.get("state"),
                lead_score=c.get("icp_score"),
                icp_tier=c.get("icp_tier"),
                website=c.get("domain"),
                contact_title=contact.get("title") if contact else None
            ))
            priority_counts["P2"] += 1

        return WorkQueueResponse(
            tasks=tasks,
            total=len(tasks),
            by_priority=priority_counts
        )

    except Exception as e:
        logger.error(f"Error fetching work queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch work queue")


@router.get("/imports", response_model=ImportHistoryResponse)
async def get_import_history(
    limit: int = Query(default=5, description="Max imports to return")
):
    """
    Get recent import history from Supabase list_imports table.
    """
    try:
        supabase = get_supabase()

        # Query list_imports table for recent imports
        result = supabase.table("list_imports").select(
            "id, filename, total_rows, processed_count, failed_count, created_at"
        ).order("created_at", desc=True).limit(limit).execute()

        imports = []
        for row in (result.data or []):
            processed = row.get("processed_count") or row.get("total_rows") or 0
            errors = row.get("failed_count") or 0
            status = "completed" if processed > 0 and errors == 0 else "partial" if errors > 0 else "pending"

            imports.append(ImportRecord(
                id=str(row.get("id")),
                filename=row.get("filename") or "unknown.csv",
                status=status,
                total_rows=row.get("total_rows") or 0,
                processed=processed,
                errors=errors,
                created_at=row.get("created_at") or datetime.now(timezone.utc).isoformat()
            ))

        # If no imports found, show the known dim_companies count as a fallback
        if not imports:
            companies = supabase.table("dim_companies").select("company_id", count="exact").execute()
            total_companies = companies.count or 0

            imports.append(ImportRecord(
                id="fallback-1",
                filename="dim_companies (current)",
                status="completed",
                total_rows=total_companies,
                processed=total_companies,
                errors=0,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        return ImportHistoryResponse(
            imports=imports,
            total=len(imports)
        )

    except Exception as e:
        logger.error(f"Error fetching import history: {e}", exc_info=True)
        # Fallback: try to get real count, or return empty on complete failure
        try:
            supabase = get_supabase()
            companies = supabase.table("dim_companies").select("company_id", count="exact").execute()
            total_companies = companies.count or 0
            return ImportHistoryResponse(
                imports=[
                    ImportRecord(
                        id="error-fallback",
                        filename="dim_companies (current)",
                        status="completed",
                        total_rows=total_companies,
                        processed=total_companies,
                        errors=0,
                        created_at=datetime.now(timezone.utc).isoformat()
                    )
                ],
                total=1
            )
        except Exception:
            # Complete failure - return empty
            return ImportHistoryResponse(imports=[], total=0)
