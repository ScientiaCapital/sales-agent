"""
Outreach Endpoint for Sales-Agent Dashboard

GET /api/outreach - Returns Close CRM activity metrics

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


async def fetch_outreach_metrics(period: str = "7d") -> dict | None:
    """
    Fetch outreach metrics from close_activities.

    Aggregates calls, emails, SMS, meetings from Close CRM sync.
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
            # Use the view for aggregated metrics
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/v_outreach_summary",
                headers=headers,
                params={"select": "*"}
            )

            if response.status_code != 200:
                logger.warning(f"Supabase query failed: {response.status_code}")
                return None

            rows = response.json()

            # Build metrics structure
            metrics = {
                "calls": {"total": 0, "count_7d": 0, "count_mtd": 0, "outbound": 0, "inbound": 0, "avg_duration": 0},
                "emails": {"total": 0, "count_7d": 0, "count_mtd": 0, "sent": 0, "received": 0},
                "sms": {"total": 0, "count_7d": 0, "count_mtd": 0, "sent": 0, "received": 0},
                "meetings": {"total": 0, "count_7d": 0, "count_mtd": 0, "scheduled": 0, "completed": 0},
            }

            for row in rows:
                activity_type = row.get("activity_type", "").lower()
                direction = row.get("direction", "")
                count = row.get("total_count", 0)
                count_7d = row.get("count_7d", 0)
                count_mtd = row.get("count_mtd", 0)

                if activity_type == "call":
                    metrics["calls"]["total"] += count
                    metrics["calls"]["count_7d"] += count_7d
                    metrics["calls"]["count_mtd"] += count_mtd
                    if direction == "outbound":
                        metrics["calls"]["outbound"] += count
                    else:
                        metrics["calls"]["inbound"] += count
                    if row.get("avg_call_duration"):
                        metrics["calls"]["avg_duration"] = round(row["avg_call_duration"], 0)

                elif activity_type == "email":
                    metrics["emails"]["total"] += count
                    metrics["emails"]["count_7d"] += count_7d
                    metrics["emails"]["count_mtd"] += count_mtd
                    if direction == "outbound":
                        metrics["emails"]["sent"] += count
                    else:
                        metrics["emails"]["received"] += count

                elif activity_type == "sms":
                    metrics["sms"]["total"] += count
                    metrics["sms"]["count_7d"] += count_7d
                    metrics["sms"]["count_mtd"] += count_mtd
                    if direction == "outbound":
                        metrics["sms"]["sent"] += count
                    else:
                        metrics["sms"]["received"] += count

                elif activity_type == "meeting":
                    metrics["meetings"]["total"] += count
                    metrics["meetings"]["count_7d"] += count_7d
                    metrics["meetings"]["count_mtd"] += count_mtd
                    metrics["meetings"]["completed"] += count

            # Calculate totals
            total_outreach = (
                metrics["calls"]["total"] +
                metrics["emails"]["total"] +
                metrics["sms"]["total"]
            )
            total_7d = (
                metrics["calls"]["count_7d"] +
                metrics["emails"]["count_7d"] +
                metrics["sms"]["count_7d"]
            )

            # Estimate response rate (received / sent)
            total_sent = (
                metrics["calls"]["outbound"] +
                metrics["emails"]["sent"] +
                metrics["sms"]["sent"]
            )
            total_received = (
                metrics["calls"]["inbound"] +
                metrics["emails"]["received"] +
                metrics["sms"]["received"]
            )
            response_rate = round(total_received / max(total_sent, 1) * 100, 1)

            return {
                "metrics": metrics,
                "summary": {
                    "total_outreach": total_outreach,
                    "total_7d": total_7d,
                    "meetings_booked": metrics["meetings"]["total"],
                    "response_rate": response_rate,
                },
                "period": period,
            }

    except Exception as e:
        logger.error(f"Supabase REST API error: {e}")
        return None


def get_mock_outreach() -> dict:
    """Return mock outreach data for development."""
    return {
        "metrics": {
            "calls": {
                "total": 156,
                "count_7d": 45,
                "count_mtd": 156,
                "outbound": 142,
                "inbound": 14,
                "avg_duration": 180,
            },
            "emails": {
                "total": 423,
                "count_7d": 120,
                "count_mtd": 423,
                "sent": 380,
                "received": 43,
            },
            "sms": {
                "total": 67,
                "count_7d": 18,
                "count_mtd": 67,
                "sent": 52,
                "received": 15,
            },
            "meetings": {
                "total": 12,
                "count_7d": 3,
                "count_mtd": 12,
                "scheduled": 2,
                "completed": 10,
            },
        },
        "summary": {
            "total_outreach": 646,
            "total_7d": 183,
            "meetings_booked": 12,
            "response_rate": 15.2,
        },
        "period": "7d",
    }


@app.get("/api/outreach")
async def get_outreach(period: str = "7d") -> JSONResponse:
    """
    Get Close CRM outreach metrics.

    Query params:
    - period: "7d" (rolling 7 days) or "mtd" (month-to-date)

    Returns aggregated calls, emails, SMS, meetings from Close CRM.
    """
    # Try Supabase first
    data = await fetch_outreach_metrics(period)

    if data is not None:
        logger.info("Using Supabase REST API outreach data")
        return JSONResponse(
            content={
                **data,
                "data_source": "supabase_rest",
                "updated_at": datetime.utcnow().isoformat()
            },
            headers={
                "Cache-Control": "public, max-age=120",
                "Access-Control-Allow-Origin": "*",
            }
        )

    # Fall back to mock
    logger.info("Using mock outreach data")
    return JSONResponse(
        content={
            **get_mock_outreach(),
            "data_source": "mock",
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=120",
            "Access-Control-Allow-Origin": "*",
        }
    )
