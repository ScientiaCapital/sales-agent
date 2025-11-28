"""
Lifecycle Endpoint for Sales-Agent Dashboard

GET /api/lifecycle - Returns lead funnel stages with counts

Uses Supabase REST API (PostgREST) for serverless-compatible data fetching.
"""

import os
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration (strip to handle Vercel env var newlines)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

# Pipeline stage order and display names
STAGE_CONFIG = {
    "imported": {"order": 1, "display": "Imported", "color": "#6B7280"},
    "qualified": {"order": 2, "display": "Qualified", "color": "#3B82F6"},
    "enriched": {"order": 3, "display": "Enriched", "color": "#8B5CF6"},
    "in_close": {"order": 4, "display": "In Close CRM", "color": "#10B981"},
    "contacted": {"order": 5, "display": "Contacted", "color": "#F59E0B"},
    "meeting_booked": {"order": 6, "display": "Meeting Booked", "color": "#EF4444"},
    "opportunity": {"order": 7, "display": "Opportunity", "color": "#EC4899"},
    "won": {"order": 8, "display": "Won", "color": "#22C55E"},
    "lost": {"order": 9, "display": "Lost", "color": "#9CA3AF"},
}


class StageMetric(BaseModel):
    stage: str
    display_name: str
    count: int
    count_7d: int
    count_mtd: int
    avg_score: float | None
    attention_count: int
    atl_count: int
    color: str
    order: int


async def fetch_lifecycle_data(period: str = "7d") -> list | None:
    """
    Fetch lifecycle funnel data from Supabase.

    Uses v_pipeline_funnel view for aggregated metrics.
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
            # Query the view
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/v_pipeline_funnel",
                headers=headers,
                params={"select": "*"}
            )

            if response.status_code != 200:
                logger.warning(f"Supabase query failed: {response.status_code} - {response.text}")
                return None

            rows = response.json()

            # Build response with all stages (even if 0 count)
            stages = []
            seen_stages = set()

            for row in rows:
                stage = row.get("current_stage", "unknown")
                seen_stages.add(stage)
                config = STAGE_CONFIG.get(stage, {"order": 99, "display": stage.title(), "color": "#6B7280"})

                stages.append({
                    "stage": stage,
                    "display_name": config["display"],
                    "count": row.get("total_count", 0),
                    "count_7d": row.get("count_7d", 0),
                    "count_mtd": row.get("count_mtd", 0),
                    "avg_score": round(row.get("avg_score") or 0, 1),
                    "attention_count": row.get("attention_count", 0),
                    "atl_count": row.get("atl_count", 0),
                    "color": config["color"],
                    "order": config["order"]
                })

            # Add missing stages with 0 counts
            for stage, config in STAGE_CONFIG.items():
                if stage not in seen_stages:
                    stages.append({
                        "stage": stage,
                        "display_name": config["display"],
                        "count": 0,
                        "count_7d": 0,
                        "count_mtd": 0,
                        "avg_score": None,
                        "attention_count": 0,
                        "atl_count": 0,
                        "color": config["color"],
                        "order": config["order"]
                    })

            # Sort by order
            stages.sort(key=lambda x: x["order"])

            return stages

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


def get_mock_lifecycle() -> list:
    """Return mock lifecycle data for development."""
    mock_data = [
        ("imported", 90, 90, 90),
        ("qualified", 72, 72, 72),
        ("enriched", 65, 65, 65),
        ("in_close", 58, 58, 58),
        ("contacted", 45, 45, 45),
        ("meeting_booked", 12, 12, 12),
        ("opportunity", 5, 5, 5),
        ("won", 2, 2, 2),
        ("lost", 3, 3, 3),
    ]

    stages = []
    for stage, count, count_7d, count_mtd in mock_data:
        config = STAGE_CONFIG.get(stage, {"order": 99, "display": stage.title(), "color": "#6B7280"})
        stages.append({
            "stage": stage,
            "display_name": config["display"],
            "count": count,
            "count_7d": count_7d,
            "count_mtd": count_mtd,
            "avg_score": 75.5 if stage in ["qualified", "enriched"] else None,
            "attention_count": 2 if stage == "qualified" else 0,
            "atl_count": int(count * 0.6),
            "color": config["color"],
            "order": config["order"]
        })

    return stages


@app.get("/api/lifecycle")
async def get_lifecycle(period: str = "7d") -> JSONResponse:
    """
    Get lead lifecycle funnel data.

    Query params:
    - period: "7d" (rolling 7 days) or "mtd" (month-to-date)

    Returns stages with counts, ATL counts, and attention flags.
    """
    # Try Supabase first
    data = await fetch_lifecycle_data(period)

    if data:
        logger.info("Using Supabase REST API lifecycle data")
        return JSONResponse(
            content={
                "stages": data,
                "period": period,
                "data_source": "supabase_rest",
                "updated_at": datetime.utcnow().isoformat()
            },
            headers={
                "Cache-Control": "public, max-age=60",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fall back to mock
    logger.info("Using mock lifecycle data")
    return JSONResponse(
        content={
            "stages": get_mock_lifecycle(),
            "period": period,
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=60",
            "Access-Control-Allow-Origin": "*",
        }
    )
