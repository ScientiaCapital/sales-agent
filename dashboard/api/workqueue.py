"""
Work Queue Endpoint for Sales-Agent Dashboard

GET /api/workqueue - Returns BDR daily task queue from Star Schema

Uses mv_bdr_work_queue materialized view for pre-computed task priorities.
Generates contextual talking points for each lead based on ICP tier, title, and activity.

Security: Protected by Vercel deployment protection (authenticated users only).
For local development, set DASHBOARD_API_KEY in environment.
"""

import os
from datetime import datetime
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
import httpx
import logging

# Suppress httpx DEBUG logging only (keeps INFO/WARNING/ERROR for security events)
logging.getLogger("httpx").setLevel(logging.INFO)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

# Optional API key for local development (Vercel handles auth in production)
DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "").strip()


# ============================================================================
# TALKING POINTS GENERATION
# ============================================================================

# OEM brands to highlight as talking points
NOTABLE_OEMS = {
    "carrier", "trane", "lennox", "rheem", "york", "daikin",
    "mitsubishi", "lg", "bosch", "generac", "kohler", "briggs"
}

# Title-based talking points
TITLE_TALKING_POINTS = {
    "ceo": "CEOs appreciate ROI and bottom-line impact",
    "owner": "Owners care about efficiency and customer satisfaction",
    "founder": "Founders appreciate innovation and new technology",
    "president": "Presidents focus on growth and competitive advantage",
    "vp": "VPs need solutions that make their teams more effective",
    "director": "Directors value operational efficiency and team tools",
    "manager": "Managers want tools that simplify their daily work",
    "head": "Department heads need visibility and reporting"
}


def generate_talking_points(row: dict) -> list[str]:
    """
    Generate contextual talking points for a lead based on available data.

    Talking points are prioritized:
    1. ICP Tier (PLATINUM/GOLD = strongest)
    2. Contact title (decision-maker angles)
    3. Phone availability
    4. Activity status (new vs existing)
    5. Stale data warning
    """
    points = []

    # 1. ICP Tier
    tier = row.get("icp_tier", "")
    score = row.get("icp_score", 0)
    if tier == "PLATINUM":
        points.append(f"🏆 PLATINUM lead (Score: {score}) - our ideal customer profile")
    elif tier == "GOLD":
        points.append(f"⭐ GOLD lead (Score: {score}) - strong ICP fit")
    elif tier == "SILVER":
        points.append(f"🥈 SILVER lead (Score: {score}) - good potential")

    # 2. Contact title
    title = row.get("best_contact_title", "") or ""
    title_lower = title.lower()
    for keyword, point in TITLE_TALKING_POINTS.items():
        if keyword in title_lower:
            points.append(f"👤 {title}: {point}")
            break

    # 3. Phone availability
    if row.get("best_contact_phone"):
        points.append("📞 Phone number available for outreach")

    # 4. Activity status
    total_touches = row.get("total_touches", 0)
    days_since = row.get("days_since_activity")

    if total_touches == 0:
        points.append("🆕 First outreach - introduce Coperniq value proposition")
    elif days_since and days_since > 14:
        points.append(f"⏰ {days_since} days since last touch - may need re-engagement")
    elif total_touches >= 3:
        points.append(f"📊 {total_touches} previous touches - reference prior conversations")

    # 5. Stale data warning
    enrichment_age = row.get("enrichment_age_days")
    if enrichment_age and enrichment_age > 30:
        points.append(f"🔄 Data is {int(enrichment_age)} days old - may need re-enrichment")

    return points[:5]  # Limit to 5 most relevant


async def fetch_work_queue(limit: int = 25) -> dict | None:
    """
    Fetch BDR work queue from mv_bdr_work_queue materialized view.

    The view pre-computes:
    - Recommended actions (9 types: CALL NOW, First Call, Follow-up, etc.)
    - Priority ranking (hot intent > new ATL > stale > default)
    - Best contact info (name, phone, email, LinkedIn)
    - Close CRM direct links
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Single query to the materialized view - already prioritized!
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/mv_bdr_work_queue",
                headers=headers,
                params={
                    "select": "*",
                    "order": "rank.asc",
                    "limit": str(limit)
                }
            )

            if response.status_code != 200:
                logger.error(f"Supabase error: {response.status_code} - {response.text}")
                return None

            rows = response.json()

            # Transform to frontend format
            tasks = []
            for row in rows:
                action = row.get("recommended_action", "")

                # Determine task type and styling from recommended action
                if "CALL NOW" in action:
                    task_type, icon, color = "hot_intent", "flame", "#EF4444"
                elif "First Call" in action:
                    task_type, icon, color = "new_lead", "phone", "#3B82F6"
                elif "They Read Your Email" in action:
                    task_type, icon, color = "email_opened", "mail-open", "#10B981"
                elif "Follow-up Email" in action:
                    task_type, icon, color = "follow_up", "mail", "#8B5CF6"
                elif "LinkedIn" in action:
                    task_type, icon, color = "linkedin", "linkedin", "#0077B5"
                elif "Warm Handoff" in action:
                    task_type, icon, color = "handoff", "user-check", "#F59E0B"
                elif "Re-enrich" in action:
                    task_type, icon, color = "reenrich", "refresh-cw", "#6366F1"
                elif "Research" in action:
                    task_type, icon, color = "research", "search", "#64748B"
                else:
                    task_type, icon, color = "review", "clipboard", "#94A3B8"

                # Generate talking points for this lead
                talking_points = generate_talking_points(row)

                tasks.append({
                    "id": str(row.get("company_id", "")),
                    "rank": row.get("rank"),
                    "task_type": task_type,
                    "recommended_action": row.get("recommended_action"),
                    "action_reason": row.get("action_reason"),
                    "company_name": row.get("company_name"),
                    "icp_tier": row.get("icp_tier"),
                    "icp_score": row.get("icp_score"),
                    "total_touches": row.get("total_touches", 0),
                    "days_since_activity": row.get("days_since_activity"),
                    "days_in_pipeline": row.get("days_in_pipeline"),
                    "opportunity_value": float(val) if (val := row.get("opportunity_value")) is not None else None,
                    # Best contact info
                    "contact_name": row.get("best_contact_name"),
                    "contact_phone": row.get("best_contact_phone"),
                    "contact_email": row.get("best_contact_email"),
                    "contact_title": row.get("best_contact_title"),
                    "contact_linkedin": row.get("best_contact_linkedin"),
                    # CRM link
                    "close_url": row.get("close_lead_url"),
                    # UI styling
                    "icon": icon,
                    "color": color,
                    # NEW: Talking points for Tim's calls
                    "talking_points": talking_points,
                })

            # Summary counts by action type
            summary = {
                "total": len(tasks),
                "hot_intent": len([t for t in tasks if t["task_type"] == "hot_intent"]),
                "new_leads": len([t for t in tasks if t["task_type"] == "new_lead"]),
                "follow_ups": len([t for t in tasks if t["task_type"] in ("follow_up", "email_opened")]),
                "research": len([t for t in tasks if t["task_type"] in ("research", "reenrich")]),
            }

            return {
                "tasks": tasks,
                "summary": summary,
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Supabase HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Supabase network error: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error in fetch_work_queue: {e}")
        return None


def get_mock_workqueue() -> dict:
    """Return mock work queue for development."""
    tasks = [
        {
            "id": "mock-1",
            "rank": 1,
            "task_type": "hot_intent",
            "recommended_action": "🔥 CALL NOW - Hot Intent",
            "action_reason": "5 email opens, no call in 3 days",
            "company_name": "AUTOMATED CONTROL LOGIC",
            "icp_tier": "GOLD",
            "icp_score": 85,
            "total_touches": 4,
            "days_since_activity": 3,
            "contact_name": "John Smith",
            "contact_phone": "(555) 123-4567",
            "contact_email": "john@aclsystems.com",
            "contact_title": "VP Operations",
            "close_url": "https://app.close.com/lead/lead_abc123",
            "icon": "flame",
            "color": "#EF4444",
            "talking_points": [
                "⭐ GOLD lead (Score: 85) - strong ICP fit",
                "👤 VP Operations: VPs need solutions that make their teams more effective",
                "📞 Phone number available for outreach",
                "📊 4 previous touches - reference prior conversations",
            ],
        },
        {
            "id": "mock-2",
            "rank": 2,
            "task_type": "new_lead",
            "recommended_action": "📞 First Call - ATL Decision Maker",
            "action_reason": "New qualified lead with ATL contact",
            "company_name": "BCM Controls",
            "icp_tier": "PLATINUM",
            "icp_score": 92,
            "total_touches": 0,
            "days_since_activity": None,
            "contact_name": "Sarah Johnson",
            "contact_phone": "(555) 987-6543",
            "contact_email": "sarah@bcmcontrols.com",
            "contact_title": "CEO",
            "close_url": "https://app.close.com/lead/lead_def456",
            "icon": "phone",
            "color": "#3B82F6",
            "talking_points": [
                "🏆 PLATINUM lead (Score: 92) - our ideal customer profile",
                "👤 CEO: CEOs appreciate ROI and bottom-line impact",
                "📞 Phone number available for outreach",
                "🆕 First outreach - introduce Coperniq value proposition",
            ],
        },
        {
            "id": "mock-3",
            "rank": 3,
            "task_type": "research",
            "recommended_action": "🔍 Research - Find Decision Maker",
            "action_reason": "No ATL contacts found yet",
            "company_name": "Climate Systems Inc",
            "icp_tier": "GOLD",
            "icp_score": 78,
            "total_touches": 0,
            "days_since_activity": None,
            "contact_name": None,
            "contact_phone": None,
            "contact_email": None,
            "contact_title": None,
            "close_url": None,
            "icon": "search",
            "color": "#64748B",
            "talking_points": [
                "⭐ GOLD lead (Score: 78) - strong ICP fit",
                "🆕 First outreach - introduce Coperniq value proposition",
            ],
        },
    ]

    return {
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "hot_intent": 1,
            "new_leads": 1,
            "follow_ups": 0,
            "research": 1,
        }
    }


@app.get("/api/workqueue")
async def get_workqueue(
    limit: int = Query(default=25, ge=1, le=100, description="Max tasks to return (1-100)"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> JSONResponse:
    """
    Get BDR daily work queue from Star Schema.

    Query params:
    - limit: Max tasks to return (1-100, default 25)

    Headers:
    - X-API-Key: Optional API key for local development (Vercel handles auth in production)

    Returns prioritized task list with recommended actions for Tim's daily workflow.
    Data comes from mv_bdr_work_queue materialized view (refreshes every 15 min).
    """
    # API key validation for local development (if DASHBOARD_API_KEY is set)
    if DASHBOARD_API_KEY and x_api_key != DASHBOARD_API_KEY:
        logger.warning(f"Unauthorized access attempt to /api/workqueue")
        raise HTTPException(status_code=401, detail="Unauthorized - invalid API key")

    # Try Supabase first
    data = await fetch_work_queue(limit)

    if data is not None:
        logger.info(f"Work queue: {data['summary']['total']} tasks from mv_bdr_work_queue")
        return JSONResponse(
            content={
                **data,
                "data_source": "star_schema",
                "view": "mv_bdr_work_queue",
                "updated_at": datetime.utcnow().isoformat()
            },
            headers={
                "Cache-Control": "public, max-age=30",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fall back to mock
    logger.info("Using mock work queue data")
    return JSONResponse(
        content={
            **get_mock_workqueue(),
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=30",
            "Access-Control-Allow-Origin": "*",
        }
    )
