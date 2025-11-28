"""
ICP Queue Endpoint for Sales-Agent Dashboard

GET /api/icp-queue - Returns Q3/Q4 ICP leads from Tim's Smart Views + Max/Abdullah opportunity tracking

Philosophy: "Never lost, always aware" - surfaces leads that haven't been touched recently.

Smart Views:
- Tim's: Q3/Q4 SQLs, Q3/Q4 Leads, PPL
- AE Tracking: Max, Abdullah, Levi, Jerry opportunities (active + lost)
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

# Team User IDs
USERS = {
    "tim": "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1",
    "abdullah": "user_lFVhSWUaqu2vff3eQEk5KG6jfkbihC1s1g6VUjn5w44",
    "max": "user_mARlgTfFvEkDMgcFflJErBYXNr3AxGxsTNWAVxc75gH",
    "levi": "user_MSAjv3Vr0ZjcXAoGt38JPZFjXnIJUNtw0KYaMqMovET",
    "jerry": "user_8ZClygANhdAJI7Tzn89mDBG3mw6SYFeyAmTbkAKe6sR",
}

# Tim's Smart View IDs
SMART_VIEWS = {
    "q3_sqls": {
        "id": "save_m5RDRHUNY8t1CvsW4wQBa7iP5z8FbG3OYnR0exZdNr2",
        "name": "3rd_QTR_SQLs_Book/Rebook",
        "priority": 1,
        "color": "#EF4444",
        "quarter": "Q3",
    },
    "q4_sqls": {
        "id": "save_d01lfNavD2kkrb0UACDzNNOZ6addJmu4kLLfulF3Uck",
        "name": "4th_QTR_SQLs_Book/Rebook",
        "priority": 2,
        "color": "#F59E0B",
        "quarter": "Q4",
    },
    "q3_leads": {
        "id": "save_1rEzQOws9l2joCyz6AbcJj6ly2NHLCcbBiAV2qEVoFM",
        "name": "3rd_QTR_Leads",
        "priority": 3,
        "color": "#3B82F6",
        "quarter": "Q3",
    },
    "q4_leads": {
        "id": "save_fxo5NkMWcjPAU2M7WCdczloeHoqsAGPHzI7loFdq7Vg",
        "name": "4th_QTR_Leads",
        "priority": 4,
        "color": "#8B5CF6",
        "quarter": "Q4",
    },
    "ppl": {
        "id": "save_ALEPunhYOfLtftHXoypnT05GU1eMawSJtyb6e7NJQNx",
        "name": "PPL",
        "priority": 5,
        "color": "#10B981",
        "quarter": "PPL",
    },
}


async def execute_saved_search(saved_search_id: str, limit: int = 50) -> list:
    """
    Execute a saved search and return matching leads.

    Uses Close's Advanced Filter API with the saved search's query.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First, get the saved search to get its query
        response = await client.get(
            f"{CLOSE_API_URL}/saved_search/{saved_search_id}/",
            auth=(CLOSE_API_KEY, "")
        )

        if response.status_code != 200:
            logger.warning(f"Error fetching saved search {saved_search_id}: {response.status_code}")
            return []

        saved_search = response.json()
        s_query = saved_search.get("s_query", {})

        if not s_query:
            logger.warning(f"No s_query in saved search {saved_search_id}")
            return []

        # Execute the search using the data/search endpoint
        search_payload = {
            **s_query,
            "results_limit": limit,
            "include_counts": False,
        }

        response = await client.post(
            f"{CLOSE_API_URL}/data/search/",
            auth=(CLOSE_API_KEY, ""),
            json=search_payload
        )

        if response.status_code != 200:
            logger.warning(f"Error executing search: {response.status_code} - {response.text[:200]}")
            return []

        return response.json().get("data", [])


async def get_lead_details(lead_id: str) -> dict:
    """Get full lead details including contacts."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CLOSE_API_URL}/lead/{lead_id}/",
            auth=(CLOSE_API_KEY, ""),
            params={"_fields": "id,display_name,status_label,contacts,date_created,date_updated,custom"}
        )

        if response.status_code != 200:
            return None

        return response.json()


async def get_lead_last_activity(lead_id: str) -> dict:
    """Get last activity date for a lead."""
    activities = {"last_activity": None, "days_since": 999, "calls": 0, "emails": 0}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check last call
        response = await client.get(
            f"{CLOSE_API_URL}/activity/call/",
            auth=(CLOSE_API_KEY, ""),
            params={"lead_id": lead_id, "_limit": 1, "_order_by": "-date_created"}
        )

        if response.status_code == 200:
            calls = response.json().get("data", [])
            if calls:
                activities["last_activity"] = calls[0].get("date_created")
                activities["calls"] = len(calls)

        # Check last email
        response = await client.get(
            f"{CLOSE_API_URL}/activity/email/",
            auth=(CLOSE_API_KEY, ""),
            params={"lead_id": lead_id, "_limit": 1, "_order_by": "-date_created"}
        )

        if response.status_code == 200:
            emails = response.json().get("data", [])
            if emails:
                email_date = emails[0].get("date_created")
                if not activities["last_activity"] or email_date > activities["last_activity"]:
                    activities["last_activity"] = email_date
                activities["emails"] = len(emails)

    # Calculate days since
    if activities["last_activity"]:
        try:
            last_dt = datetime.fromisoformat(activities["last_activity"].replace("Z", "+00:00"))
            activities["days_since"] = (datetime.now(last_dt.tzinfo) - last_dt).days
        except Exception:
            pass

    return activities


async def get_ae_opportunities(user_id: str, user_name: str) -> dict:
    """Get opportunities for an AE (active, won, lost)."""
    result = {"name": user_name, "active": [], "won": [], "lost": [], "totals": {}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get all opportunities for this user
        response = await client.get(
            f"{CLOSE_API_URL}/opportunity/",
            auth=(CLOSE_API_KEY, ""),
            params={
                "user_id": user_id,
                "_limit": 200,
            }
        )

        if response.status_code != 200:
            return result

        opportunities = response.json().get("data", [])

        active_value = 0
        won_value = 0
        lost_value = 0

        for opp in opportunities:
            status = opp.get("status_type", "active")
            value = (opp.get("value", 0) or 0) / 100

            opp_data = {
                "id": opp.get("id"),
                "lead_name": opp.get("lead_name", ""),
                "status_label": opp.get("status_label", ""),
                "value": value,
                "confidence": opp.get("confidence", 0),
                "created_at": opp.get("date_created"),
                "date_won": opp.get("date_won"),
                "date_lost": opp.get("date_lost"),
            }

            if status == "active":
                result["active"].append(opp_data)
                active_value += value
            elif status == "won":
                result["won"].append(opp_data)
                won_value += value
            elif status == "lost":
                result["lost"].append(opp_data)
                lost_value += value

        result["totals"] = {
            "active_count": len(result["active"]),
            "active_value": round(active_value, 2),
            "won_count": len(result["won"]),
            "won_value": round(won_value, 2),
            "lost_count": len(result["lost"]),
            "lost_value": round(lost_value, 2),
        }

    return result


async def fetch_icp_queue(untouched_days: int = 7, limit: int = 25) -> dict:
    """
    Fetch ICP leads from Tim's smart views + AE opportunity tracking.
    """
    if not CLOSE_API_KEY:
        logger.warning("Close API key not configured")
        return None

    result = {
        "smart_views": {},
        "untouched_leads": [],
        "ae_tracking": {},
        "summary": {
            "total_leads": 0,
            "untouched_count": 0,
            "by_quarter": {"Q3": 0, "Q4": 0, "PPL": 0},
        },
    }

    # 1. Fetch Tim's Smart Views
    for view_key, view_config in SMART_VIEWS.items():
        logger.info(f"Fetching smart view: {view_config['name']}")

        leads = await execute_saved_search(view_config["id"], limit=limit)
        logger.info(f"  Found {len(leads)} leads")

        view_leads = []
        for lead in leads:
            lead_id = lead.get("id")

            # Get full lead details
            lead_details = await get_lead_details(lead_id) if lead_id else None
            if not lead_details:
                lead_details = lead

            # Get activity info
            activity = await get_lead_last_activity(lead_id) if lead_id else {"days_since": 999}

            # Extract primary contact
            contacts = lead_details.get("contacts", [])
            primary_contact = contacts[0] if contacts else {}

            lead_data = {
                "id": lead_id,
                "company_name": lead_details.get("display_name", lead.get("display_name", "Unknown")),
                "status": lead_details.get("status_label", lead.get("status_label", "")),
                "contact_name": primary_contact.get("name", ""),
                "contact_phone": (primary_contact.get("phones", [{}])[0].get("phone", "")
                                  if primary_contact.get("phones") else ""),
                "contact_email": (primary_contact.get("emails", [{}])[0].get("email", "")
                                  if primary_contact.get("emails") else ""),
                "smart_view": view_config["name"],
                "quarter": view_config["quarter"],
                "priority": view_config["priority"],
                "color": view_config["color"],
                "days_since_activity": activity["days_since"],
                "is_untouched": activity["days_since"] >= untouched_days,
                "last_activity": activity.get("last_activity"),
            }

            view_leads.append(lead_data)

            if lead_data["is_untouched"]:
                result["untouched_leads"].append(lead_data)
                result["summary"]["untouched_count"] += 1

        result["smart_views"][view_key] = {
            "name": view_config["name"],
            "color": view_config["color"],
            "priority": view_config["priority"],
            "leads": view_leads,
            "total": len(view_leads),
            "untouched": len([l for l in view_leads if l["is_untouched"]]),
        }

        result["summary"]["total_leads"] += len(view_leads)
        result["summary"]["by_quarter"][view_config["quarter"]] += len(view_leads)

    # 2. Fetch AE Opportunities (Max, Abdullah, Levi, Jerry)
    for ae_key in ["max", "abdullah", "levi", "jerry"]:
        user_id = USERS.get(ae_key)
        if user_id:
            logger.info(f"Fetching opportunities for {ae_key}")
            result["ae_tracking"][ae_key] = await get_ae_opportunities(user_id, ae_key.title())

    # Sort untouched leads by priority then days (most stale first)
    result["untouched_leads"].sort(
        key=lambda x: (x["priority"], -x["days_since_activity"])
    )

    return result


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for ICP Queue."""

    def do_GET(self):
        """GET - Return ICP leads needing attention + AE tracking."""
        import asyncio

        untouched_days = 7
        limit = 25

        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if param.startswith("days="):
                    untouched_days = int(param.split("=")[1])
                elif param.startswith("limit="):
                    limit = int(param.split("=")[1])

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(fetch_icp_queue(untouched_days, limit))
            loop.close()

            if data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=60")
                self.end_headers()

                response = {
                    **data,
                    "data_source": "close_crm",
                    "untouched_threshold_days": untouched_days,
                    "updated_at": datetime.utcnow().isoformat(),
                    "philosophy": "Never lost, always aware",
                }

                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                self.wfile.write(json.dumps({
                    "error": "Could not fetch ICP queue - check Close API key",
                    "data_source": "none",
                }).encode())

        except Exception as e:
            logger.error(f"Error in ICP queue: {e}")
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
