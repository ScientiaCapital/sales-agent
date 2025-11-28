"""
Close Activity Endpoint for Sales-Agent Dashboard

GET /api/close-activity - Returns real-time activity metrics from Close CRM (last 90 days)

Queries Close CRM directly (not Supabase cache) for accurate activity data.
Parallel queries for calls, emails, SMS, and meetings.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Close CRM API
CLOSE_API_URL = "https://api.close.com/api/v1"
CLOSE_API_KEY = os.environ.get("CLOSE_API_KEY", "").strip()

# Team User IDs
USERS = {
    "tim": "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1",
    "abdullah": "user_lFVhSWUaqu2vff3eQEk5KG6jfkbihC1s1g6VUjn5w44",
    "max": "user_mARlgTfFvEkDMgcFflJErBYXNr3AxGxsTNWAVxc75gH",
    "levi": "user_MSAjv3Vr0ZjcXAoGt38JPZFjXnIJUNtw0KYaMqMovET",
    "jerry": "user_8ZClygANhdAJI7Tzn89mDBG3mw6SYFeyAmTbkAKe6sR",
}


async def fetch_activity_stats(client: httpx.AsyncClient, activity_type: str, since_date: str) -> dict:
    """Fetch activity count from Close CRM for a specific activity type."""
    stats = {
        "total": 0,
        "outbound": 0,
        "inbound": 0,
        "by_user": {},
    }

    try:
        # Fetch activities with date filter
        params = {
            "date_created__gte": since_date,
            "_limit": 200,  # Max per request
            "_fields": "id,direction,user_id,duration",
        }

        response = await client.get(
            f"{CLOSE_API_URL}/activity/{activity_type}/",
            auth=(CLOSE_API_KEY, ""),
            params=params
        )

        if response.status_code != 200:
            logger.warning(f"Error fetching {activity_type} activities: {response.status_code}")
            return stats

        data = response.json()
        activities = data.get("data", [])

        # Count totals
        stats["total"] = len(activities)

        total_duration = 0
        duration_count = 0

        for activity in activities:
            direction = activity.get("direction", "")
            if direction == "outbound":
                stats["outbound"] += 1
            else:
                stats["inbound"] += 1

            # Track by user
            user_id = activity.get("user_id", "")
            if user_id:
                stats["by_user"][user_id] = stats["by_user"].get(user_id, 0) + 1

            # Track call duration
            if activity_type == "call" and activity.get("duration"):
                total_duration += activity["duration"]
                duration_count += 1

        if duration_count > 0:
            stats["avg_duration"] = round(total_duration / duration_count)

    except Exception as e:
        logger.error(f"Error fetching {activity_type}: {e}")

    return stats


async def fetch_meeting_stats(client: httpx.AsyncClient, since_date: str) -> dict:
    """Fetch meeting activity count from Close CRM."""
    stats = {"total": 0, "scheduled": 0, "completed": 0, "by_user": {}}

    try:
        params = {
            "date_created__gte": since_date,
            "_limit": 200,
            "_fields": "id,user_id,status",
        }

        response = await client.get(
            f"{CLOSE_API_URL}/activity/meeting/",
            auth=(CLOSE_API_KEY, ""),
            params=params
        )

        if response.status_code != 200:
            # Meetings might not be available in all Close accounts
            return stats

        data = response.json()
        activities = data.get("data", [])

        stats["total"] = len(activities)
        for activity in activities:
            status = activity.get("status", "")
            if status == "completed":
                stats["completed"] += 1
            else:
                stats["scheduled"] += 1

            user_id = activity.get("user_id", "")
            if user_id:
                stats["by_user"][user_id] = stats["by_user"].get(user_id, 0) + 1

    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")

    return stats


def resolve_user_names(by_user: dict) -> dict:
    """Convert user IDs to names."""
    id_to_name = {v: k.title() for k, v in USERS.items()}
    return {id_to_name.get(uid, "Other"): count for uid, count in by_user.items()}


async def fetch_close_activity(days: int = 90) -> dict:
    """
    Fetch activity metrics directly from Close CRM.
    """
    if not CLOSE_API_KEY:
        logger.warning("Close API key not configured")
        return None

    since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Parallel fetch all activity types
        results = await asyncio.gather(
            fetch_activity_stats(client, "call", since_date),
            fetch_activity_stats(client, "email", since_date),
            fetch_activity_stats(client, "sms", since_date),
            fetch_meeting_stats(client, since_date),
            return_exceptions=True
        )

        calls = results[0] if not isinstance(results[0], Exception) else {"total": 0}
        emails = results[1] if not isinstance(results[1], Exception) else {"total": 0}
        sms = results[2] if not isinstance(results[2], Exception) else {"total": 0}
        meetings = results[3] if not isinstance(results[3], Exception) else {"total": 0}

        return {
            "metrics": {
                "calls": {
                    "total": calls.get("total", 0),
                    "outbound": calls.get("outbound", 0),
                    "inbound": calls.get("inbound", 0),
                    "avg_duration": calls.get("avg_duration", 0),
                    "by_user": resolve_user_names(calls.get("by_user", {})),
                },
                "emails": {
                    "total": emails.get("total", 0),
                    "outbound": emails.get("outbound", 0),
                    "inbound": emails.get("inbound", 0),
                    "by_user": resolve_user_names(emails.get("by_user", {})),
                },
                "sms": {
                    "total": sms.get("total", 0),
                    "outbound": sms.get("outbound", 0),
                    "inbound": sms.get("inbound", 0),
                    "by_user": resolve_user_names(sms.get("by_user", {})),
                },
                "meetings": {
                    "total": meetings.get("total", 0),
                    "scheduled": meetings.get("scheduled", 0),
                    "completed": meetings.get("completed", 0),
                    "by_user": resolve_user_names(meetings.get("by_user", {})),
                },
            },
            "summary": {
                "total_activities": calls.get("total", 0) + emails.get("total", 0) + sms.get("total", 0),
                "total_meetings": meetings.get("total", 0),
            },
            "period_days": days,
        }


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for Close Activity."""

    def do_GET(self):
        """GET - Return real-time activity from Close CRM."""
        import asyncio

        days = 90  # Default to 90 days

        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if param.startswith("days="):
                    days = min(int(param.split("=")[1]), 180)  # Cap at 180 days

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(fetch_close_activity(days))
            loop.close()

            if data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=300")  # Cache 5 min
                self.end_headers()

                response = {
                    **data,
                    "data_source": "close_crm",
                    "updated_at": datetime.utcnow().isoformat(),
                }

                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                self.wfile.write(json.dumps({
                    "error": "Could not fetch Close activity - check API key",
                    "data_source": "none",
                }).encode())

        except Exception as e:
            logger.error(f"Error in Close activity: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            self.wfile.write(json.dumps({
                "error": str(e),
                "type": type(e).__name__,
            }).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
