"""
Attention Endpoint for Sales-Agent Dashboard

GET /api/attention - Returns leads needing attention (stuck, failed, stale)

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

# Alert type icons and colors
ALERT_CONFIG = {
    "stuck": {"icon": "clock", "color": "#F59E0B", "label": "Stuck"},
    "failed": {"icon": "x-circle", "color": "#EF4444", "label": "Failed"},
    "stale": {"icon": "pause-circle", "color": "#6B7280", "label": "Stale"},
    "no_contact": {"icon": "phone-off", "color": "#8B5CF6", "label": "No Contact"},
}


async def fetch_attention_queue(limit: int = 20) -> dict | None:
    """
    Fetch alerts from pipeline_alerts table.

    Returns unresolved alerts sorted by severity.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "count=exact"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get unresolved alerts
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/pipeline_alerts",
                headers=headers,
                params={
                    "resolved": "eq.false",
                    "select": "*",
                    "order": "severity.asc,created_at.desc",
                    "limit": str(limit)
                }
            )

            if response.status_code != 200:
                logger.warning(f"Supabase query failed: {response.status_code}")
                return None

            alerts = response.json()
            total_count = int(response.headers.get("content-range", "0-0/0").split("/")[-1])

            # Count by severity
            severity_counts = {"critical": 0, "warning": 0, "info": 0}
            type_counts = {"stuck": 0, "failed": 0, "stale": 0, "no_contact": 0}

            formatted_alerts = []
            for alert in alerts:
                severity = alert.get("severity", "info")
                alert_type = alert.get("alert_type", "stuck")

                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                type_counts[alert_type] = type_counts.get(alert_type, 0) + 1

                config = ALERT_CONFIG.get(alert_type, ALERT_CONFIG["stuck"])

                formatted_alerts.append({
                    "id": alert.get("id"),
                    "company_name": alert.get("company_name"),
                    "alert_type": alert_type,
                    "type_label": config["label"],
                    "severity": severity,
                    "message": alert.get("message"),
                    "stage": alert.get("stage"),
                    "icon": config["icon"],
                    "color": config["color"],
                    "created_at": alert.get("created_at"),
                })

            return {
                "alerts": formatted_alerts,
                "total": total_count,
                "by_severity": severity_counts,
                "by_type": type_counts,
            }

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


def get_mock_attention() -> dict:
    """Return mock attention data for development."""
    now = datetime.utcnow()

    alerts = [
        {
            "id": "mock-1",
            "company_name": "ABC HVAC Services",
            "alert_type": "stuck",
            "type_label": "Stuck",
            "severity": "critical",
            "message": "Lead stuck in qualified stage for 72 hours",
            "stage": "qualified",
            "icon": "clock",
            "color": "#F59E0B",
            "created_at": (now - timedelta(hours=72)).isoformat(),
        },
        {
            "id": "mock-2",
            "company_name": "XYZ Mechanical Inc",
            "alert_type": "failed",
            "type_label": "Failed",
            "severity": "critical",
            "message": "Enrichment failed: Hunter.io rate limit exceeded",
            "stage": "enrichment",
            "icon": "x-circle",
            "color": "#EF4444",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "id": "mock-3",
            "company_name": "123 Electrical LLC",
            "alert_type": "no_contact",
            "type_label": "No Contact",
            "severity": "warning",
            "message": "Qualified lead with 0 outreach attempts (3 days)",
            "stage": "in_close",
            "icon": "phone-off",
            "color": "#8B5CF6",
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "id": "mock-4",
            "company_name": "Premier Plumbing Co",
            "alert_type": "stale",
            "type_label": "Stale",
            "severity": "info",
            "message": "No activity in 7 days",
            "stage": "contacted",
            "icon": "pause-circle",
            "color": "#6B7280",
            "created_at": (now - timedelta(days=7)).isoformat(),
        },
    ]

    return {
        "alerts": alerts,
        "total": len(alerts),
        "by_severity": {"critical": 2, "warning": 1, "info": 1},
        "by_type": {"stuck": 1, "failed": 1, "stale": 1, "no_contact": 1},
    }


@app.get("/api/attention")
async def get_attention(limit: int = 20) -> JSONResponse:
    """
    Get leads needing attention.

    Query params:
    - limit: Max alerts to return (default 20)

    Returns alerts sorted by severity (critical first).
    """
    # Try Supabase first
    data = await fetch_attention_queue(limit)

    if data is not None:
        logger.info("Using Supabase REST API attention data")
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
    logger.info("Using mock attention data")
    return JSONResponse(
        content={
            **get_mock_attention(),
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=30",
            "Access-Control-Allow-Origin": "*",
        }
    )
