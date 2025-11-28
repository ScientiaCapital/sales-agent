"""
Work Queue Endpoint for Sales-Agent Dashboard

GET /api/workqueue - Returns BDR daily task queue

Uses Supabase REST API (PostgREST) for serverless-compatible data fetching.
"""

import os
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration (strip to handle Vercel env var newlines)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

# Task type configuration
TASK_CONFIG = {
    "new_lead": {"icon": "user-plus", "color": "#3B82F6", "label": "New Lead", "priority": 1},
    "follow_up": {"icon": "phone", "color": "#10B981", "label": "Follow Up", "priority": 2},
    "callback": {"icon": "phone-incoming", "color": "#F59E0B", "label": "Call Back", "priority": 3},
    "no_answer": {"icon": "phone-missed", "color": "#EF4444", "label": "No Answer", "priority": 4},
    "send_email": {"icon": "mail", "color": "#8B5CF6", "label": "Send Email", "priority": 5},
}


async def fetch_work_queue(limit: int = 25) -> dict | None:
    """
    Fetch BDR work queue from lead_current_state.

    Prioritizes:
    1. Hot ATL leads not yet contacted
    2. Leads needing follow-up (last contact > 24h ago)
    3. Qualified leads without outreach
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
            tasks = []

            # 1. New qualified leads not yet contacted (in_close with no outreach)
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/lead_current_state",
                headers=headers,
                params={
                    "current_stage": "eq.in_close",
                    "total_calls": "eq.0",
                    "total_emails": "eq.0",
                    "select": "id,company_name,qualification_score,is_atl,close_status,created_at",
                    "order": "qualification_score.desc.nullslast",
                    "limit": "10"
                }
            )

            if response.status_code == 200:
                for lead in response.json():
                    config = TASK_CONFIG["new_lead"]
                    tasks.append({
                        "id": f"new-{lead.get('id')}",
                        "task_type": "new_lead",
                        "label": config["label"],
                        "company_name": lead.get("company_name"),
                        "score": lead.get("qualification_score"),
                        "is_atl": lead.get("is_atl", False),
                        "close_status": lead.get("close_status"),
                        "icon": config["icon"],
                        "color": config["color"],
                        "priority": config["priority"],
                        "due": "Today",
                        "created_at": lead.get("created_at"),
                    })

            # 2. Leads needing follow-up (contacted > 24h ago, not meeting_booked)
            day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/lead_current_state",
                headers=headers,
                params={
                    "current_stage": "eq.contacted",
                    "last_contacted_at": f"lt.{day_ago}",
                    "select": "id,company_name,qualification_score,is_atl,last_contacted_at,last_contact_method",
                    "order": "last_contacted_at.asc",
                    "limit": "10"
                }
            )

            if response.status_code == 200:
                for lead in response.json():
                    config = TASK_CONFIG["follow_up"]
                    tasks.append({
                        "id": f"followup-{lead.get('id')}",
                        "task_type": "follow_up",
                        "label": config["label"],
                        "company_name": lead.get("company_name"),
                        "score": lead.get("qualification_score"),
                        "is_atl": lead.get("is_atl", False),
                        "last_contact": lead.get("last_contact_method"),
                        "icon": config["icon"],
                        "color": config["color"],
                        "priority": config["priority"],
                        "due": "Overdue",
                        "created_at": lead.get("last_contacted_at"),
                    })

            # 3. Qualified leads with attention flag
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/lead_current_state",
                headers=headers,
                params={
                    "needs_attention": "eq.true",
                    "select": "id,company_name,qualification_score,is_atl,attention_reason,current_stage",
                    "order": "qualification_score.desc.nullslast",
                    "limit": "5"
                }
            )

            if response.status_code == 200:
                for lead in response.json():
                    config = TASK_CONFIG["callback"]
                    tasks.append({
                        "id": f"attention-{lead.get('id')}",
                        "task_type": "callback",
                        "label": lead.get("attention_reason", "Needs Attention"),
                        "company_name": lead.get("company_name"),
                        "score": lead.get("qualification_score"),
                        "is_atl": lead.get("is_atl", False),
                        "stage": lead.get("current_stage"),
                        "icon": config["icon"],
                        "color": config["color"],
                        "priority": config["priority"],
                        "due": "ASAP",
                        "created_at": None,
                    })

            # Sort by priority
            tasks.sort(key=lambda x: x.get("priority", 99))

            # Summary counts
            summary = {
                "total": len(tasks),
                "new_leads": len([t for t in tasks if t["task_type"] == "new_lead"]),
                "follow_ups": len([t for t in tasks if t["task_type"] == "follow_up"]),
                "callbacks": len([t for t in tasks if t["task_type"] == "callback"]),
            }

            return {
                "tasks": tasks[:limit],
                "summary": summary,
            }

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


def get_mock_workqueue() -> dict:
    """Return mock work queue for development."""
    tasks = [
        {
            "id": "new-1",
            "task_type": "new_lead",
            "label": "New Lead",
            "company_name": "AUTOMATED CONTROL LOGIC",
            "score": 85,
            "is_atl": True,
            "close_status": "Hot ATL",
            "icon": "user-plus",
            "color": "#3B82F6",
            "priority": 1,
            "due": "Today",
        },
        {
            "id": "new-2",
            "task_type": "new_lead",
            "label": "New Lead",
            "company_name": "BCM Controls",
            "score": 78,
            "is_atl": True,
            "close_status": "Hot ATL",
            "icon": "user-plus",
            "color": "#3B82F6",
            "priority": 1,
            "due": "Today",
        },
        {
            "id": "followup-1",
            "task_type": "follow_up",
            "label": "Follow Up",
            "company_name": "Climate Systems Inc",
            "score": 72,
            "is_atl": True,
            "last_contact": "call",
            "icon": "phone",
            "color": "#10B981",
            "priority": 2,
            "due": "Overdue",
        },
        {
            "id": "callback-1",
            "task_type": "callback",
            "label": "Requested callback",
            "company_name": "Stark Tech Operating",
            "score": 80,
            "is_atl": True,
            "icon": "phone-incoming",
            "color": "#F59E0B",
            "priority": 3,
            "due": "ASAP",
        },
    ]

    return {
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "new_leads": 2,
            "follow_ups": 1,
            "callbacks": 1,
        }
    }


@app.get("/api/workqueue")
async def get_workqueue(limit: int = 25) -> JSONResponse:
    """
    Get BDR daily work queue.

    Query params:
    - limit: Max tasks to return (default 25)

    Returns prioritized task list for Tim's daily workflow.
    """
    # Try Supabase first
    data = await fetch_work_queue(limit)

    if data is not None:
        logger.info("Using Supabase REST API work queue data")
        return JSONResponse(
            content={
                **data,
                "data_source": "supabase_rest",
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
