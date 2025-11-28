"""
Activity Endpoint for Sales-Agent Dashboard

GET /api/activity - Returns recent audit trail events from lead_audit_log
"""

import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


class AuditEvent(BaseModel):
    id: str
    company_name: str
    event_type: str
    stage: str
    event_details: Dict[str, Any]
    created_at: str
    session_id: Optional[str] = None
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None


# Event type icons and colors for UI
EVENT_CONFIG = {
    "lead_imported": {"icon": "download", "color": "#3B82F6", "label": "Imported"},
    "lead_qualified": {"icon": "check-circle", "color": "#10B981", "label": "Qualified"},
    "crm_match_found": {"icon": "link", "color": "#8B5CF6", "label": "CRM Match"},
    "lead_enriched": {"icon": "sparkles", "color": "#F59E0B", "label": "Enriched"},
    "atl_contact_found": {"icon": "user-check", "color": "#10B981", "label": "ATL Found"},
    "dedup_create_new": {"icon": "plus-circle", "color": "#3B82F6", "label": "New Lead"},
    "dedup_add_contact": {"icon": "user-plus", "color": "#6366F1", "label": "Added Contact"},
    "dedup_skip_duplicate": {"icon": "x-circle", "color": "#EF4444", "label": "Skipped (Dup)"},
    "dedup_update_existing": {"icon": "refresh-cw", "color": "#F59E0B", "label": "Updated"},
    "lead_exported": {"icon": "upload", "color": "#10B981", "label": "Exported"},
    "status_changed": {"icon": "arrow-right", "color": "#6366F1", "label": "Status Changed"},
}


async def fetch_activity(hours: int, limit: int) -> list | None:
    """
    Fetch recent activity from lead_audit_log table.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    # Calculate cutoff time
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/lead_audit_log",
                headers=headers,
                params={
                    "select": "id,company_name,event_type,stage,decision_data,created_at,session_id,latency_ms,cost_usd",
                    "created_at": f"gte.{cutoff}",
                    "order": "created_at.desc",
                    "limit": str(limit)
                }
            )

            if response.status_code != 200:
                logger.error(f"Supabase error: {response.status_code} - {response.text}")
                return None

            rows = response.json()

            # Transform to frontend format
            events = []
            for row in rows:
                event_type = row.get("event_type", "unknown")
                config = EVENT_CONFIG.get(event_type, {"icon": "activity", "color": "#94A3B8", "label": event_type})

                events.append({
                    "id": str(row.get("id", "")),
                    "company_name": row.get("company_name"),
                    "event_type": event_type,
                    "stage": row.get("stage"),
                    "event_details": row.get("decision_data", {}),
                    "created_at": row.get("created_at"),
                    "session_id": row.get("session_id"),
                    "latency_ms": row.get("latency_ms"),
                    "cost_usd": float(row["cost_usd"]) if row.get("cost_usd") else None,
                    # UI config
                    "icon": config["icon"],
                    "color": config["color"],
                    "label": config["label"],
                })

            return events

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


# Mock data for when Supabase is unavailable
MOCK_COMPANIES = [
    "ABC HVAC Services",
    "Brower Mechanical Inc",
    "Elite Plumbing & Heating",
    "GreenTech Solar Solutions",
    "Metro Mechanical Contractors",
]


def get_mock_activity(hours: int, limit: int) -> list:
    """Return mock activity for development."""
    events = []
    now = datetime.utcnow()
    max_minutes = hours * 60

    event_types = list(EVENT_CONFIG.keys())

    for i in range(min(limit, 10)):
        minutes_ago = random.randint(1, max_minutes)
        event_type = random.choice(event_types)
        config = EVENT_CONFIG[event_type]

        # Generate event-specific details
        details = {}
        if event_type == "lead_qualified":
            score = random.randint(50, 95)
            details = {"score": score, "tier": "GOLD" if score >= 70 else "SILVER", "model": "cerebras"}
        elif event_type == "lead_enriched":
            details = {"contacts_found": random.randint(1, 5), "source": random.choice(["hunter", "apollo"])}
        elif event_type == "dedup_skip_duplicate":
            details = {"match_confidence": round(random.uniform(0.85, 0.98), 2)}

        events.append({
            "id": f"mock-{i}",
            "company_name": random.choice(MOCK_COMPANIES),
            "event_type": event_type,
            "stage": random.choice(["import", "qualification", "enrichment", "export"]),
            "event_details": details,
            "created_at": (now - timedelta(minutes=minutes_ago)).isoformat(),
            "session_id": f"session_{random.randint(1000, 9999)}",
            "latency_ms": random.randint(100, 1500),
            "cost_usd": round(random.uniform(0.001, 0.03), 4) if random.random() > 0.5 else None,
            "icon": config["icon"],
            "color": config["color"],
            "label": config["label"],
        })

    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events


@app.get("/api/activity")
async def get_activity(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=100)
) -> JSONResponse:
    """
    Get recent audit trail activity from lead_audit_log.

    Args:
        hours: Number of hours to look back (default: 24, max: 168)
        limit: Maximum events to return (default: 10, max: 100)

    Returns events from the sales-agent pipeline showing lead processing activity.
    """
    # Try Supabase first
    events = await fetch_activity(hours, limit)

    if events is not None:
        logger.info(f"Activity: {len(events)} events from lead_audit_log")
        return JSONResponse(
            content={
                "events": events,
                "count": len(events),
                "hours_back": hours,
                "data_source": "lead_audit_log",
                "updated_at": datetime.utcnow().isoformat()
            },
            headers={
                "Cache-Control": "public, max-age=60",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fall back to mock
    logger.info("Using mock activity data")
    mock_events = get_mock_activity(hours, limit)
    return JSONResponse(
        content={
            "events": mock_events,
            "count": len(mock_events),
            "hours_back": hours,
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=60",
            "Access-Control-Allow-Origin": "*",
        }
    )
