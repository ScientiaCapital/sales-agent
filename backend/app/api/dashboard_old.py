"""
Dashboard API Endpoints
=======================
FastAPI endpoints for the BDR Dashboard frontend.

Provides real data from Supabase for:
- /metrics - Executive summary KPIs
- /icp-queue - ICP leads by smart views
- /activity - Recent activity feed
- /attention - Leads needing attention
- /workqueue - BDR work queue
- /imports - Recent import history
- /outreach - Outreach metrics from Close CRM
- /lifecycle - Lead lifecycle funnel

Author: Claude + Tim
Date: Dec 6, 2025
"""

import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Close CRM API configuration
CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
CLOSE_API_BASE = "https://api.close.com/api/v1"

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ============================================================================
# Business Metrics Configuration (Override via environment variables)
# ============================================================================
# These are configurable estimates until we have real Close CRM deal data
ESTIMATED_COST_PER_LEAD = float(os.getenv("DASHBOARD_COST_PER_LEAD", "0.002"))
ESTIMATED_AVG_DEAL_SIZE = float(os.getenv("DASHBOARD_AVG_DEAL_SIZE", "15000"))
ESTIMATED_QUALIFICATION_TIME_MS = float(os.getenv("DASHBOARD_AVG_QUALIFICATION_MS", "850"))

# Post-pivot date (Sep 9, 2025 - strategic pivot date)
POST_PIVOT_DATE = os.getenv("DASHBOARD_POST_PIVOT_DATE", "2025-09-09")

# Fiscal quarter definitions for 2025
FISCAL_QUARTERS = {
    "Q3_2025": {"start": "2025-07-01", "end": "2025-09-30", "label": "Q3 2025"},
    "Q4_2025": {"start": "2025-10-01", "end": "2025-12-31", "label": "Q4 2025"},
}

# Cache TTL in seconds (5 minutes - balance between freshness and performance)
CLOSE_CACHE_TTL = int(os.getenv("CLOSE_CACHE_TTL_SECONDS", "300"))

# In-memory cache for Close CRM opportunities
_close_opportunities_cache: Dict[str, Any] = {
    "data": [],
    "last_fetched": None,
}


# ============================================================================
# Close CRM API Helper (with caching)
# ============================================================================
def fetch_close_opportunities_filtered(
    status_type: str = None,
    date_won_gte: str = None,
    date_won_lte: str = None,
    date_lost_gte: str = None,
    date_lost_lte: str = None,
    force_refresh: bool = False,
    aggregate_only: bool = False
) -> Tuple[List[Dict], Dict]:
    """
    Fetch opportunities from Close CRM API with server-side filtering.

    Uses Close's native filtering to reduce API calls and data transfer.
    Close API returns aggregates (total_value, total_results) in response.

    Args:
        status_type: Filter by status ('won', 'lost', 'active') or None for all
        date_won_gte: Filter won deals on/after this date (YYYY-MM-DD)
        date_won_lte: Filter won deals on/before this date (YYYY-MM-DD)
        date_lost_gte: Filter lost deals on/after this date (YYYY-MM-DD)
        date_lost_lte: Filter lost deals on/before this date (YYYY-MM-DD)
        force_refresh: If True, bypass cache
        aggregate_only: If True, skip pagination and just return aggregates (faster!)

    Returns:
        Tuple of (list of opportunities, aggregates dict)
    """
    global _close_opportunities_cache

    if not CLOSE_API_KEY:
        logger.warning("CLOSE_API_KEY not configured - cannot fetch opportunities")
        return [], {}

    # Build cache key based on filters
    cache_key = f"{status_type}_{date_won_gte}_{date_won_lte}_{date_lost_gte}_{date_lost_lte}_{aggregate_only}"

    # Check cache
    if not force_refresh:
        cached = _close_opportunities_cache.get(cache_key)
        if cached:
            last_fetched = cached.get("last_fetched")
            if last_fetched:
                cache_age = (datetime.now(timezone.utc) - last_fetched).total_seconds()
                if cache_age < CLOSE_CACHE_TTL:
                    logger.debug(f"Using cached Close opportunities for {cache_key} ({cache_age:.0f}s old)")
                    return cached.get("data", []), cached.get("aggregates", {})

    all_opps = []
    aggregates = {}
    cursor = None

    try:
        while True:
            # For aggregate_only, just fetch 1 record to get totals
            params = {"_limit": 1 if aggregate_only else 100}
            if status_type:
                params["status_type"] = status_type
            if date_won_gte:
                params["date_won__gte"] = date_won_gte
            if date_won_lte:
                params["date_won__lte"] = date_won_lte
            if date_lost_gte:
                params["date_lost__gte"] = date_lost_gte
            if date_lost_lte:
                params["date_lost__lte"] = date_lost_lte
            if cursor:
                params["_cursor"] = cursor

            response = requests.get(
                f"{CLOSE_API_BASE}/opportunity/",
                auth=(CLOSE_API_KEY, ""),
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Close API error: {response.status_code} - {response.text}")
                break

            data = response.json()
            opps = data.get("data", [])

            # Capture aggregates from first response (Close returns these with list)
            if not aggregates:
                aggregates = {
                    "total_results": data.get("total_results", 0),
                    "total_value_one_time": data.get("total_value_one_time", 0) / 100,  # cents to dollars
                    "total_value_monthly": data.get("total_value_monthly", 0) / 100,
                    "total_value_annual": data.get("total_value_annual", 0) / 100,
                    "total_value_annualized": data.get("total_value_annualized", 0) / 100,
                }

            # Convert values from cents to dollars
            for opp in opps:
                if opp.get("value"):
                    opp["value_dollars"] = opp["value"] / 100
                else:
                    opp["value_dollars"] = 0

            all_opps.extend(opps)

            # For aggregate_only, break after first call (we have totals from response)
            if aggregate_only:
                logger.info(f"Got aggregates from Close CRM (status={status_type}, total={aggregates.get('total_results', 0)})")
                break

            if not data.get("has_more"):
                break
            cursor = data.get("cursor")

        logger.info(f"Fetched {len(all_opps)} opportunities from Close CRM (status={status_type}, won>={date_won_gte})")

        # Update cache
        _close_opportunities_cache[cache_key] = {
            "data": all_opps,
            "aggregates": aggregates,
            "last_fetched": datetime.now(timezone.utc)
        }

        return all_opps, aggregates

    except Exception as e:
        logger.error(f"Error fetching Close opportunities: {e}")
        # Return stale cache if available
        cached = _close_opportunities_cache.get(cache_key)
        if cached:
            logger.warning("Returning stale cache due to API error")
            return cached.get("data", []), cached.get("aggregates", {})
        return [], {}


def fetch_close_opportunities(status_type: str = None, force_refresh: bool = False) -> List[Dict]:
    """
    Legacy wrapper for backward compatibility.
    Fetches all opportunities without date filtering.
    """
    opps, _ = fetch_close_opportunities_filtered(status_type=status_type, force_refresh=force_refresh)
    return opps


# ============================================================================
# Supabase Client
# ============================================================================
_supabase_client = None


def get_supabase():
    """Get or create Supabase client for dashboard."""
    global _supabase_client

    if _supabase_client is None:
        from dotenv import load_dotenv
        load_dotenv()

        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError("supabase package not installed")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized for dashboard")

    return _supabase_client


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
    close_lead_url: Optional[str] = None  # "Open in Close" CRM link


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
        # atl_contacts can be used for future contact-level metrics
        _ = len([c for c in (contacts.data or []) if c.get("is_atl")])

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
        )

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard metrics")


@router.get("/icp-queue", response_model=ICPQueueResponse)
async def get_icp_queue(
    days: int = Query(default=7, description="Days for untouched threshold"),
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

        # Get companies with Close CRM fields
        # Filter out customers and do_not_contact at the database level for efficiency
        query = supabase.table("dim_companies").select(
            "company_id, company_name, domain, phone, icp_tier, icp_score, current_stage, updated_at, close_lead_id, close_lead_url"
        )

        if not include_customers:
            # Use negation filter to exclude customer and do_not_contact stages
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

        for company in (companies.data or []):
            company_name = company.get("company_name") or ""
            cid = company.get("company_id")
            tier = company.get("icp_tier") or "UNKNOWN"
            stage = company.get("current_stage") or "COLD"
            updated = company.get("updated_at")
            domain = company.get("domain")
            close_lead_id = company.get("close_lead_id")
            close_lead_url = company.get("close_lead_url")

            # Calculate days since update
            days_since = 999
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    days_since = (now - updated_dt).days
                except (ValueError, TypeError):
                    pass  # Keep default days_since = 7 for unparseable dates

            is_untouched = days_since > days

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
            data_source="Supabase"
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
    # Stages to exclude from GTM views
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
                    pass  # Keep default days_stale = 7 for unparseable dates

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
    # Stages to exclude from GTM views
    EXCLUDED_STAGES = ["customer", "do_not_contact"]

    try:
        supabase = get_supabase()

        # HOT leads (excluding customers)
        hot_leads = supabase.table("dim_companies").select(
            "company_id, company_name, phone, domain, close_lead_id, close_lead_url"
        ).eq("current_stage", "HOT").not_.in_(
            "current_stage", EXCLUDED_STAGES
        ).limit(10).execute()

        # High tier leads (excluding customers)
        high_tier = supabase.table("dim_companies").select(
            "company_id, company_name, phone, domain, close_lead_id, close_lead_url"
        ).in_("icp_tier", ["PLATINUM", "GOLD"]).not_.in_(
            "current_stage", EXCLUDED_STAGES
        ).limit(10).execute()

        contacts = supabase.table("dim_contacts").select(
            "company_id, full_name, phone, email"
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
            tasks.append(WorkQueueItem(
                id=str(cid),
                company_name=c.get("company_name") or "Unknown",
                task_type="CALL",
                priority=1,
                contact_name=contact.get("full_name") if contact else None,
                contact_phone=contact.get("phone") if contact else c.get("phone"),
                contact_email=contact.get("email") if contact else None,
                notes="HOT lead - call today",
                close_lead_url=c.get("close_lead_url")
            ))
            priority_counts["P1"] += 1

        # Add high tier as P2
        for c in (high_tier.data or []):
            cid = c.get("company_id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            contact = contact_map.get(cid)
            tasks.append(WorkQueueItem(
                id=str(cid),
                company_name=c.get("company_name") or "Unknown",
                task_type="RESEARCH",
                priority=2,
                contact_name=contact.get("full_name") if contact else None,
                contact_phone=contact.get("phone") if contact else c.get("phone"),
                contact_email=contact.get("email") if contact else None,
                notes="High-value lead",
                close_lead_url=c.get("close_lead_url")
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


# ============================================================================
# Combined Stats Endpoint
# ============================================================================

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


# ============================================================================
# Trifecta Scoring Endpoint
# ============================================================================

class TrifectaStatsResponse(BaseModel):
    """Trifecta detection statistics."""
    unicorn_count: int
    partial_trifecta_count: int
    multi_oem_count: int
    score_distribution: Dict[str, int]
    top_unicorns: List[Dict[str, Any]]
    energy_breakdown: Dict[str, int]
    updated_at: str


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


# ============================================================================
# Elite Team Status Endpoint
# ============================================================================

class EliteAgentStatusModel(BaseModel):
    """Status for a single Elite Squad agent."""
    name: str
    icon: str
    status: str
    last_run: Optional[str] = None
    current_task: Optional[str] = None
    signals_detected: Optional[int] = None
    scraped_today: Optional[int] = None
    queue_size: Optional[int] = None
    unicorns_found: Optional[int] = None
    duplicates_blocked: Optional[int] = None
    routed_to_bdr: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class EliteTeamResponse(BaseModel):
    """Elite Squad status response."""
    signal_scout: EliteAgentStatusModel
    deep_hunter: EliteAgentStatusModel
    intake_commander: EliteAgentStatusModel
    summary: Dict[str, Any]
    updated_at: str


@router.get("/elite-team", response_model=EliteTeamResponse)
async def get_elite_team_status():
    """
    Get Elite Squad status for dashboard.
    """
    try:
        from app.services.langgraph.agents.elite_team.elite_team_hub import get_elite_hub

        hub = get_elite_hub()
        dashboard_data = hub.get_dashboard_status()

        # Transform to response model
        return EliteTeamResponse(
            signal_scout=EliteAgentStatusModel(**dashboard_data["signal_scout"]),
            deep_hunter=EliteAgentStatusModel(**dashboard_data["deep_hunter"]),
            intake_commander=EliteAgentStatusModel(**dashboard_data["intake_commander"]),
            summary=dashboard_data["summary"],
            updated_at=dashboard_data["updated_at"]
        )

    except Exception as e:
        logger.error(f"Error fetching elite team status: {e}", exc_info=True)
        # Return idle state on error
        now = datetime.now(timezone.utc)
        return EliteTeamResponse(
            signal_scout=EliteAgentStatusModel(
                name="Signal Scout",
                icon="telescope",
                status="idle",
                signals_detected=0
            ),
            deep_hunter=EliteAgentStatusModel(
                name="Deep Hunter",
                icon="search",
                status="idle",
                scraped_today=0
            ),
            intake_commander=EliteAgentStatusModel(
                name="Intake Commander",
                icon="shield-check",
                status="idle",
                queue_size=0,
                unicorns_found=0,
                duplicates_blocked=0,
                routed_to_bdr=0
            ),
            summary={
                "signals_today": 0,
                "scraped_today": 0,
                "unicorns_today": 0,
                "bdr_routed_today": 0,
                "duplicates_blocked": 0,
                "pending_orders": 0,
                "intake_queue": 0
            },
            updated_at=now.isoformat()
        )


# ============================================================================
# Agent Health (No Auth - Dashboard Internal)
# ============================================================================

class AgentMetric(BaseModel):
    """Agent health metric for dashboard."""
    agent_type: str
    display_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_latency_ms: float
    target_latency_ms: float
    avg_cost_usd: float
    success_rate: float
    status: str  # "healthy" | "degraded" | "failing" | "idle"
    last_execution_at: Optional[str] = None


AGENT_DEFINITIONS = [
    {"type": "lead_scout", "name": "LeadScoutAgent", "schedule": "Every 30 min", "target_ms": 30000},
    {"type": "icp_checker", "name": "ICPCheckerAgent", "schedule": "Every 15 min", "target_ms": 15000},
    {"type": "prediction_agent", "name": "PredictionAgent", "schedule": "Every 5 min", "target_ms": 10000},
    {"type": "morning_briefing", "name": "MorningBriefingAgent", "schedule": "7 AM EST", "target_ms": 60000},
    {"type": "sales_intel", "name": "SalesIntelAgent", "schedule": "Hourly :30", "target_ms": 45000},
    {"type": "bdr_outreach", "name": "BDRAgent", "schedule": "Hourly :00", "target_ms": 30000},
]


@router.get("/agents", response_model=List[AgentMetric])
async def get_agents():
    """Get agent health metrics for dashboard (no auth required)."""
    try:
        from app.services.agent_tracker import get_agent_tracker
        tracker = get_agent_tracker()

        metrics = []
        for agent_def in AGENT_DEFINITIONS:
            agent_type = agent_def["type"]

            # Get stats from tracker
            stats = tracker.get_agent_stats(agent_type)

            total_exec = stats.get("total_runs", 0)
            successful = stats.get("successful_runs", 0)
            failed = stats.get("failed_runs", 0)
            avg_latency = stats.get("avg_duration_ms", 0.0)
            success_rate = successful / total_exec if total_exec > 0 else 1.0

            # Determine status
            if total_exec == 0:
                status = "idle"
            elif success_rate < 0.8:
                status = "failing"
            elif success_rate < 0.95 or avg_latency > agent_def["target_ms"] * 1.5:
                status = "degraded"
            else:
                status = "healthy"

            metrics.append(AgentMetric(
                agent_type=agent_type,
                display_name=agent_def["name"],
                total_executions=total_exec,
                successful_executions=successful,
                failed_executions=failed,
                avg_latency_ms=avg_latency,
                target_latency_ms=float(agent_def["target_ms"]),
                avg_cost_usd=stats.get("total_cost", 0.0) / max(total_exec, 1),
                success_rate=success_rate,
                status=status,
                last_execution_at=stats.get("last_run")
            ))

        return metrics

    except Exception as e:
        logger.error(f"Error fetching agent metrics: {e}")
        # Return mock data on error
        return [
            AgentMetric(
                agent_type=a["type"],
                display_name=a["name"],
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                avg_latency_ms=0.0,
                target_latency_ms=float(a["target_ms"]),
                avg_cost_usd=0.0,
                success_rate=1.0,
                status="idle",
                last_execution_at=None
            )
            for a in AGENT_DEFINITIONS
        ]


# ============================================================================
# Revival Candidates Endpoint
# ============================================================================

class RevivalCandidate(BaseModel):
    """A lost deal that's ready for re-engagement."""
    close_opportunity_id: str
    company_id: Optional[str] = None
    lead_name: str
    deal_value: float
    close_reason: Optional[str] = None
    date_lost: Optional[str] = None
    days_since_lost: Optional[int] = None
    revival_priority: str  # high, medium, low
    revival_score: int  # 0-100
    last_contact_date: Optional[str] = None
    competitor_lost_to: Optional[str] = None
    notes: Optional[str] = None


class RevivalCandidatesResponse(BaseModel):
    """Response for revival candidates endpoint."""
    candidates: List[RevivalCandidate]
    total_count: int
    total_value: float
    high_priority_count: int
    summary: Dict[str, Any]


@router.get("/revival-candidates", response_model=RevivalCandidatesResponse)
async def get_revival_candidates(
    priority: Optional[str] = Query(None, description="Filter by priority: high, medium, low"),
    min_value: Optional[float] = Query(None, description="Minimum deal value"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get lost deals ready for re-engagement (6+ months since last contact).

    These are deals from fact_lost_opportunities where is_revival_candidate=true.
    Sorted by revival_score DESC, deal_value DESC.
    """
    try:
        from app.core.supabase import get_supabase_client
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("fact_lost_opportunities").select("*").eq("is_revival_candidate", True)

        # Apply filters
        if priority:
            query = query.eq("revival_priority", priority)
        if min_value:
            query = query.gte("deal_value", min_value)

        # Get total count first (for pagination info)
        count_result = supabase.table("fact_lost_opportunities").select(
            "close_opportunity_id", count="exact"
        ).eq("is_revival_candidate", True).execute()
        total_count = count_result.count or 0

        # Get paginated results sorted by score and value
        result = query.order(
            "revival_score", desc=True
        ).order(
            "deal_value", desc=True
        ).range(offset, offset + limit - 1).execute()

        candidates = []
        total_value = 0.0
        high_priority_count = 0

        for row in (result.data or []):
            total_value += row.get("deal_value", 0) or 0
            if row.get("revival_priority") == "high":
                high_priority_count += 1

            candidates.append(RevivalCandidate(
                close_opportunity_id=row.get("close_opportunity_id", ""),
                company_id=row.get("company_id"),
                lead_name=row.get("lead_name", "Unknown"),
                deal_value=row.get("deal_value", 0) or 0,
                close_reason=row.get("close_reason"),
                date_lost=row.get("date_lost"),
                days_since_lost=row.get("days_since_lost"),
                revival_priority=row.get("revival_priority", "low"),
                revival_score=row.get("revival_score", 0) or 0,
                last_contact_date=row.get("last_contact_date"),
                competitor_lost_to=row.get("competitor_lost_to"),
                notes=row.get("notes")[:200] if row.get("notes") else None  # Truncate notes
            ))

        # Get summary stats
        summary_result = supabase.table("fact_lost_opportunities").select(
            "revival_priority"
        ).eq("is_revival_candidate", True).execute()

        priority_counts = {"high": 0, "medium": 0, "low": 0}
        for row in (summary_result.data or []):
            p = row.get("revival_priority", "low")
            if p in priority_counts:
                priority_counts[p] += 1

        return RevivalCandidatesResponse(
            candidates=candidates,
            total_count=total_count,
            total_value=total_value,
            high_priority_count=high_priority_count,
            summary={
                "by_priority": priority_counts,
                "avg_score": sum(c.revival_score for c in candidates) / len(candidates) if candidates else 0,
                "filters_applied": {
                    "priority": priority,
                    "min_value": min_value,
                    "limit": limit,
                    "offset": offset
                }
            }
        )

    except Exception as e:
        logger.error(f"Error fetching revival candidates: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ============================================================================
# Mission Control Stats Endpoint (for Contractor Hunter Dashboard)
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


# ============================================================================
# Celery Observability Endpoint
# ============================================================================

class CeleryWorkerStats(BaseModel):
    """Stats for a single Celery worker."""
    hostname: str
    status: str  # online, offline
    active_tasks: int
    processed_total: int
    pool_size: Optional[int] = None
    concurrency: Optional[int] = None


class CeleryTaskStats(BaseModel):
    """Stats for Celery tasks."""
    scheduled_count: int
    active_count: int
    reserved_count: int
    recent_tasks: List[Dict[str, Any]]


class CeleryStatsResponse(BaseModel):
    """Response for Celery observability endpoint."""
    status: str  # healthy, degraded, offline
    workers: List[CeleryWorkerStats]
    tasks: CeleryTaskStats
    redis_connected: bool
    beat_running: bool
    summary: Dict[str, Any]


@router.get("/celery-stats", response_model=CeleryStatsResponse)
async def get_celery_stats():
    """
    Get real-time Celery worker and task statistics.

    Provides observability into:
    - Worker health and status
    - Active/scheduled/reserved task counts
    - Redis connectivity
    - Beat scheduler status
    """
    try:
        from app.celery_app import celery_app
        import redis

        workers = []
        active_count = 0
        scheduled_count = 0
        reserved_count = 0
        recent_tasks = []

        # Check Redis connectivity
        redis_connected = False
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url)
            r.ping()
            redis_connected = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

        # Get worker stats via Celery inspect
        try:
            inspector = celery_app.control.inspect(timeout=3.0)

            # Ping workers
            ping_result = inspector.ping() or {}
            stats_result = inspector.stats() or {}
            active_result = inspector.active() or {}
            scheduled_result = inspector.scheduled() or {}
            reserved_result = inspector.reserved() or {}

            for hostname, pong in ping_result.items():
                stats = stats_result.get(hostname, {})
                active_tasks = active_result.get(hostname, [])
                scheduled_tasks = scheduled_result.get(hostname, [])
                reserved_tasks = reserved_result.get(hostname, [])

                workers.append(CeleryWorkerStats(
                    hostname=hostname,
                    status="online" if pong else "offline",
                    active_tasks=len(active_tasks),
                    processed_total=stats.get("total", {}).get("celery.backend_cleanup", 0) if stats else 0,
                    pool_size=stats.get("pool", {}).get("max-concurrency") if stats else None,
                    concurrency=stats.get("pool", {}).get("processes") if stats else None
                ))

                active_count += len(active_tasks)
                scheduled_count += len(scheduled_tasks)
                reserved_count += len(reserved_tasks)

                # Collect recent active tasks
                for task in active_tasks[:5]:
                    recent_tasks.append({
                        "name": task.get("name", "unknown"),
                        "id": task.get("id", ""),
                        "args": str(task.get("args", []))[:100],
                        "started": task.get("time_start"),
                        "hostname": hostname
                    })

        except Exception as e:
            logger.warning(f"Celery inspect failed: {e}")

        # Check Beat status (look for celerybeat-schedule file)
        beat_running = False
        try:
            import os.path
            beat_schedule_path = "celerybeat-schedule"
            if os.path.exists(beat_schedule_path):
                # Check if modified in last 5 minutes
                mtime = os.path.getmtime(beat_schedule_path)
                if (datetime.now().timestamp() - mtime) < 300:
                    beat_running = True
        except Exception:
            pass

        # Determine overall status
        if not redis_connected:
            status = "offline"
        elif len(workers) == 0:
            status = "degraded"
        elif all(w.status == "online" for w in workers):
            status = "healthy"
        else:
            status = "degraded"

        return CeleryStatsResponse(
            status=status,
            workers=workers,
            tasks=CeleryTaskStats(
                scheduled_count=scheduled_count,
                active_count=active_count,
                reserved_count=reserved_count,
                recent_tasks=recent_tasks[:10]
            ),
            redis_connected=redis_connected,
            beat_running=beat_running,
            summary={
                "total_workers": len(workers),
                "online_workers": sum(1 for w in workers if w.status == "online"),
                "total_active_tasks": active_count,
                "total_scheduled": scheduled_count,
                "health_score": 100 if status == "healthy" else (50 if status == "degraded" else 0)
            }
        )

    except Exception as e:
        logger.error(f"Error fetching Celery stats: {e}")
        return CeleryStatsResponse(
            status="offline",
            workers=[],
            tasks=CeleryTaskStats(
                scheduled_count=0,
                active_count=0,
                reserved_count=0,
                recent_tasks=[]
            ),
            redis_connected=False,
            beat_running=False,
            summary={
                "error": str(e),
                "total_workers": 0,
                "online_workers": 0,
                "health_score": 0
            }
        )
