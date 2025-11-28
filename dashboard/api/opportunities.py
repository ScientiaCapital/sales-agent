"""
Opportunities Endpoint for Sales-Agent Dashboard

GET /api/opportunities - Returns opportunity pipeline by owner (Abdullah, Max, Levi, Jerry)

CEO/CTO View: Pipeline value, won/lost, by AE
BDR View: Opportunities Tim helped create + Lost analysis

"Never lost, always aware" - Track lost deals to learn and improve
"""

import os
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Close CRM API
CLOSE_API_URL = "https://api.close.com/api/v1"
CLOSE_API_KEY = os.environ.get("CLOSE_API_KEY", "").strip()

# Team User IDs (set these in Vercel env vars)
ABDULLAH_USER_ID = os.environ.get("CLOSE_ABDULLAH_USER_ID", "").strip()
MAX_USER_ID = os.environ.get("CLOSE_MAX_USER_ID", "").strip()
TIM_USER_ID = "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1"

# Supabase (for cached data)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


async def fetch_close_opportunities(since_date: str) -> list:
    """
    Fetch all opportunities from Close CRM.
    """
    opportunities = []
    skip = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params = {
                "_skip": skip,
                "_limit": limit,
                "date_created__gte": since_date,
            }

            response = await client.get(
                f"{CLOSE_API_URL}/opportunity/",
                auth=(CLOSE_API_KEY, ""),
                params=params
            )

            if response.status_code != 200:
                logger.warning(f"Error fetching opportunities: {response.status_code}")
                break

            data = response.json()
            batch = data.get("data", [])
            opportunities.extend(batch)

            if not data.get("has_more", False):
                break

            skip += limit

    return opportunities


async def fetch_users() -> dict:
    """
    Fetch all users from Close to map user_id to names.
    """
    users = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CLOSE_API_URL}/user/",
            auth=(CLOSE_API_KEY, "")
        )

        if response.status_code == 200:
            for user in response.json().get("data", []):
                users[user["id"]] = {
                    "name": user.get("first_name", "") + " " + user.get("last_name", ""),
                    "email": user.get("email", ""),
                }

    return users


async def fetch_supabase_opportunities() -> list | None:
    """
    Fetch cached opportunities from Supabase (from sync-close).
    Faster but may be slightly stale.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/close_opportunities",
                headers=headers,
                params={"select": "*", "order": "created_at.desc", "limit": "500"}
            )

            if response.status_code == 200:
                return response.json()

    except Exception as e:
        logger.error(f"Supabase fetch error: {e}")

    return None


def categorize_opportunities(opportunities: list, users: dict) -> dict:
    """
    Categorize opportunities by owner and status.

    Provides:
    - by_owner: Breakdown per AE (Abdullah, Max, Levi, Jerry)
    - by_status: Active pipeline, Won, Lost
    - lost_analysis: Lost deals with reasons for learning
    - top_deals: Biggest opportunities
    """
    result = {
        "by_owner": {},
        "by_status": {"active": [], "won": [], "lost": []},
        "totals": {
            "active_value": 0,
            "won_value": 0,
            "lost_value": 0,
            "active_count": 0,
            "won_count": 0,
            "lost_count": 0,
        },
        "top_deals": [],
        "lost_analysis": {
            "by_owner": {},
            "recent_lost": [],
            "total_lost_value": 0,
        },
    }

    for opp in opportunities:
        user_id = opp.get("user_id") or opp.get("owner_id", "")
        user_name = users.get(user_id, {}).get("name", opp.get("owner_name", "Unknown"))
        status_type = opp.get("status_type", "active")
        value = (opp.get("value", 0) or 0) / 100  # cents to dollars

        # Build opportunity data
        opp_data = {
            "id": opp.get("id"),
            "lead_id": opp.get("lead_id"),
            "lead_name": opp.get("lead_name", ""),
            "status_type": status_type,
            "status_label": opp.get("status_label", ""),
            "value": value,
            "confidence": opp.get("confidence", 0),
            "owner_id": user_id,
            "owner_name": user_name,
            "created_at": opp.get("created_at") or opp.get("date_created"),
            "date_won": opp.get("date_won"),
            "date_lost": opp.get("date_lost"),
        }

        # By owner
        if user_name not in result["by_owner"]:
            result["by_owner"][user_name] = {
                "active": [], "won": [], "lost": [],
                "active_value": 0, "won_value": 0, "lost_value": 0,
            }

        result["by_owner"][user_name][status_type].append(opp_data)

        # By status
        result["by_status"][status_type].append(opp_data)

        # Totals
        if status_type == "active":
            result["totals"]["active_value"] += value
            result["totals"]["active_count"] += 1
            result["by_owner"][user_name]["active_value"] += value
        elif status_type == "won":
            result["totals"]["won_value"] += value
            result["totals"]["won_count"] += 1
            result["by_owner"][user_name]["won_value"] += value
        elif status_type == "lost":
            result["totals"]["lost_value"] += value
            result["totals"]["lost_count"] += 1
            result["by_owner"][user_name]["lost_value"] += value

            # Track for lost analysis
            if user_name not in result["lost_analysis"]["by_owner"]:
                result["lost_analysis"]["by_owner"][user_name] = {
                    "count": 0,
                    "value": 0,
                    "deals": [],
                }
            result["lost_analysis"]["by_owner"][user_name]["count"] += 1
            result["lost_analysis"]["by_owner"][user_name]["value"] += value
            result["lost_analysis"]["by_owner"][user_name]["deals"].append(opp_data)
            result["lost_analysis"]["total_lost_value"] += value

    # Sort top deals by value
    all_opps = result["by_status"]["active"] + result["by_status"]["won"]
    result["top_deals"] = sorted(all_opps, key=lambda x: x["value"], reverse=True)[:10]

    # Recent lost deals (sorted by date)
    lost_deals = result["by_status"]["lost"]
    result["lost_analysis"]["recent_lost"] = sorted(
        lost_deals,
        key=lambda x: x.get("date_lost") or x.get("created_at") or "",
        reverse=True
    )[:20]

    return result


async def fetch_opportunities_data(days_back: int = 180, use_cache: bool = True) -> dict:
    """
    Fetch and categorize opportunities.
    """
    if not CLOSE_API_KEY:
        logger.warning("Close API key not configured")
        return None

    # Try Supabase cache first (faster)
    if use_cache:
        cached = await fetch_supabase_opportunities()
        if cached:
            logger.info(f"Using cached Supabase data: {len(cached)} opportunities")
            users = await fetch_users()
            return categorize_opportunities(cached, users)

    # Fetch fresh from Close
    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    opportunities = await fetch_close_opportunities(since_date)
    users = await fetch_users()

    logger.info(f"Fetched {len(opportunities)} opportunities from Close CRM")

    return categorize_opportunities(opportunities, users)


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for Opportunities."""

    def do_GET(self):
        """GET - Return opportunities by owner."""
        import asyncio

        # Parse query params
        days_back = 180
        use_cache = True

        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if param.startswith("days="):
                    days_back = int(param.split("=")[1])
                elif param == "fresh=true":
                    use_cache = False

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(fetch_opportunities_data(days_back, use_cache))
            loop.close()

            if data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()

                response = {
                    **data,
                    "data_source": "close_crm",
                    "days_back": days_back,
                    "updated_at": datetime.utcnow().isoformat(),
                }

                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                self.wfile.write(json.dumps({
                    "error": "Could not fetch opportunities - check Close API key",
                    "data_source": "none",
                }).encode())

        except Exception as e:
            logger.error(f"Error fetching opportunities: {e}")
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
