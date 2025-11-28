"""
ICP Queue Endpoint for Sales-Agent Dashboard

GET /api/icp-queue - Returns Q3/Q4 ICP leads from Tim's Smart Views + AE opportunity tracking

Philosophy: "Never lost, always aware" - surfaces leads that haven't been touched recently.

Smart Views:
- Tim's: Q3/Q4 SQLs, Q3/Q4 Leads, PPL
- AE Tracking: Max, Abdullah, Levi, Jerry opportunities (active + lost)

OPTIMIZED: Uses asyncio.gather for parallel API calls to avoid Vercel timeout.
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


async def execute_saved_search(client: httpx.AsyncClient, saved_search_id: str, limit: int = 10) -> list:
    """
    Execute a saved search and return matching leads.
    Uses Close's Advanced Filter API with the saved search's query.
    """
    try:
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
            logger.warning(f"Error executing search: {response.status_code}")
            return []

        return response.json().get("data", [])

    except Exception as e:
        logger.error(f"Error in execute_saved_search: {e}")
        return []


async def get_ae_opportunities(client: httpx.AsyncClient, user_id: str, user_name: str) -> dict:
    """Get opportunities for an AE (active, won, lost)."""
    result = {"name": user_name, "active": [], "won": [], "lost": [], "totals": {}}

    try:
        response = await client.get(
            f"{CLOSE_API_URL}/opportunity/",
            auth=(CLOSE_API_KEY, ""),
            params={
                "user_id": user_id,
                "_limit": 100,
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

    except Exception as e:
        logger.error(f"Error fetching opportunities for {user_name}: {e}")

    return result


async def fetch_single_view(client: httpx.AsyncClient, view_key: str, view_config: dict, limit: int, untouched_days: int) -> tuple:
    """Fetch a single smart view's leads."""
    leads = await execute_saved_search(client, view_config["id"], limit=limit)

    view_leads = []
    for lead in leads:
        # Extract data directly from search results (avoid extra API calls)
        lead_id = lead.get("id")
        contacts = lead.get("contacts", [])
        primary_contact = contacts[0] if contacts else {}

        # Use date_updated as proxy for activity (avoids extra API call)
        date_updated = lead.get("date_updated", "")
        days_since = 999
        if date_updated:
            try:
                updated_dt = datetime.fromisoformat(date_updated.replace("Z", "+00:00"))
                days_since = (datetime.now(updated_dt.tzinfo) - updated_dt).days
            except Exception:
                pass

        lead_data = {
            "id": lead_id,
            "company_name": lead.get("display_name", "Unknown"),
            "status": lead.get("status_label", ""),
            "contact_name": primary_contact.get("name", ""),
            "contact_phone": (primary_contact.get("phones", [{}])[0].get("phone", "")
                              if primary_contact.get("phones") else ""),
            "contact_email": (primary_contact.get("emails", [{}])[0].get("email", "")
                              if primary_contact.get("emails") else ""),
            "smart_view": view_config["name"],
            "quarter": view_config["quarter"],
            "priority": view_config["priority"],
            "color": view_config["color"],
            "days_since_activity": days_since,
            "is_untouched": days_since >= untouched_days,
        }
        view_leads.append(lead_data)

    return view_key, {
        "name": view_config["name"],
        "color": view_config["color"],
        "priority": view_config["priority"],
        "leads": view_leads,
        "total": len(view_leads),
        "untouched": len([l for l in view_leads if l["is_untouched"]]),
    }


async def fetch_icp_queue(untouched_days: int = 7, limit: int = 10) -> dict:
    """
    Fetch ICP leads from Tim's smart views + AE opportunity tracking.
    OPTIMIZED: Uses parallel requests to avoid timeout.
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

    async with httpx.AsyncClient(timeout=25.0) as client:
        # Parallel fetch: all smart views + all AE opportunities at once
        tasks = []

        # Smart view tasks
        for view_key, view_config in SMART_VIEWS.items():
            tasks.append(fetch_single_view(client, view_key, view_config, limit, untouched_days))

        # AE opportunity tasks
        ae_keys = ["max", "abdullah", "levi", "jerry"]
        for ae_key in ae_keys:
            user_id = USERS.get(ae_key)
            if user_id:
                tasks.append(get_ae_opportunities(client, user_id, ae_key.title()))

        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process smart view results (first 5)
        for i, res in enumerate(results[:5]):
            if isinstance(res, Exception):
                logger.error(f"Smart view task failed: {res}")
                continue
            if isinstance(res, tuple):
                view_key, view_data = res
                result["smart_views"][view_key] = view_data
                result["summary"]["total_leads"] += view_data["total"]

                # Add untouched leads
                for lead in view_data["leads"]:
                    if lead["is_untouched"]:
                        result["untouched_leads"].append(lead)
                        result["summary"]["untouched_count"] += 1

                # Update quarter count
                quarter = SMART_VIEWS[view_key]["quarter"]
                result["summary"]["by_quarter"][quarter] += view_data["total"]

        # Process AE opportunity results (remaining)
        for i, res in enumerate(results[5:]):
            if isinstance(res, Exception):
                logger.error(f"AE opportunity task failed: {res}")
                continue
            if isinstance(res, dict) and "name" in res:
                ae_key = ae_keys[i]
                result["ae_tracking"][ae_key] = res

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
        limit = 10  # Reduced default for faster response

        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if param.startswith("days="):
                    untouched_days = int(param.split("=")[1])
                elif param.startswith("limit="):
                    limit = min(int(param.split("=")[1]), 15)  # Cap at 15

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
