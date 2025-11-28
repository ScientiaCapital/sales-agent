"""
Work Queue Endpoint for Sales-Agent Dashboard

GET /api/workqueue - Returns BDR daily task queue from Star Schema

Uses mv_bdr_work_queue materialized view for pre-computed task priorities.
"""

import os
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


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
                    "opportunity_value": float(row.get("opportunity_value")) if row.get("opportunity_value") else None,
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

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
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
async def get_workqueue(limit: int = 25) -> JSONResponse:
    """
    Get BDR daily work queue from Star Schema.

    Query params:
    - limit: Max tasks to return (default 25)

    Returns prioritized task list with recommended actions for Tim's daily workflow.
    Data comes from mv_bdr_work_queue materialized view (refreshes every 15 min).
    """
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
