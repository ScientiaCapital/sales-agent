"""
Close CRM Activity Sync - Pulls team activity and opportunity data
Syncs calls, emails, SMS, meetings, opportunities, and hot nurture leads.

Team Structure:
- Tim Kipper (BDR): Prospecting, qualification, booking meetings
- Abdullah (AE - Primary): Creating and closing opportunities (going forward)
- Max (AE - Legacy): Historical opportunities

Usage:
- Manual: POST /api/sync-close (triggers full sync)
- Scheduled: Vercel Cron runs daily at 6 AM CST
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler

# Team User IDs
TIM_USER_ID = "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1"  # BDR
# Note: Abdullah and Max user IDs will be fetched dynamically or set via env vars
ABDULLAH_USER_ID = os.environ.get("CLOSE_ABDULLAH_USER_ID", "")  # AE - Primary
MAX_USER_ID = os.environ.get("CLOSE_MAX_USER_ID", "")  # AE - Legacy

# Close CRM API
CLOSE_API_URL = "https://api.close.com/api/v1"
CLOSE_API_KEY = os.environ.get("CLOSE_API_KEY", "").strip()

# Supabase (strip to remove any trailing newlines)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


async def fetch_close_activities(activity_type: str, since_date: str, user_id: str = TIM_USER_ID) -> list:
    """
    Fetch activities from Close CRM by type.

    Args:
        activity_type: call, email, sms, or meeting
        since_date: ISO date string (YYYY-MM-DD)
        user_id: Close user ID to filter by

    Returns:
        List of activity dicts
    """
    activities = []
    skip = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params = {
                "_skip": skip,
                "_limit": limit,
                "user_id": user_id,
                "date_created__gte": since_date,
            }

            response = await client.get(
                f"{CLOSE_API_URL}/activity/{activity_type}/",
                auth=(CLOSE_API_KEY, ""),
                params=params
            )

            if response.status_code != 200:
                print(f"Error fetching {activity_type}: {response.status_code}")
                break

            data = response.json()
            batch = data.get("data", [])
            activities.extend(batch)

            if not data.get("has_more", False):
                break

            skip += limit

    return activities


async def fetch_call_outcomes() -> dict:
    """Fetch call outcome mappings (ID -> name)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CLOSE_API_URL}/call_outcome/",
            auth=(CLOSE_API_KEY, "")
        )

        if response.status_code != 200:
            return {}

        outcomes = {}
        for outcome in response.json().get("data", []):
            outcomes[outcome["id"]] = outcome.get("name", "Unknown")

        return outcomes


async def sync_to_supabase(activities: list, activity_type: str) -> int:
    """
    Upsert activities to Supabase close_activities table.

    Returns:
        Count of synced records
    """
    if not activities:
        return 0

    # Transform to our schema
    records = []
    for act in activities:
        record = {
            "id": act.get("id"),
            "activity_type": activity_type,
            "user_id": act.get("user_id"),
            "lead_id": act.get("lead_id"),
            "contact_id": act.get("contact_id"),
            "direction": act.get("direction", "outbound"),  # calls/emails have direction
            "duration_seconds": act.get("duration"),  # calls only
            "status": act.get("status"),  # emails: sent/received
            "outcome": act.get("disposition"),  # calls: answered, voicemail, etc
            "created_at": act.get("date_created"),
            "synced_at": datetime.utcnow().isoformat(),
        }
        records.append(record)

    # Upsert to Supabase
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/close_activities",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=records
        )

        if response.status_code not in [200, 201]:
            print(f"Supabase upsert error: {response.status_code} - {response.text}")
            return 0

    return len(records)


async def fetch_opportunities(since_date: str) -> list:
    """
    Fetch all opportunities from Close CRM.
    Returns opportunities with status (active, won, lost) and values.
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
                print(f"Error fetching opportunities: {response.status_code}")
                break

            data = response.json()
            batch = data.get("data", [])
            opportunities.extend(batch)

            if not data.get("has_more", False):
                break

            skip += limit

    return opportunities


async def fetch_hot_nurture_leads() -> list:
    """
    Fetch leads in 'Nurture Hot' status or with high intent flag.
    These are leads close to converting (90-day opportunity window).
    """
    leads = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search for leads with Nurture Hot status or high intent
        # Close uses Lucene-style query syntax
        queries = [
            'lead_status:"Nurture Hot"',
            'custom.high_intent_flag:"Yes"',
        ]

        for query in queries:
            skip = 0
            limit = 100

            while True:
                params = {
                    "_skip": skip,
                    "_limit": limit,
                    "query": query,
                }

                response = await client.get(
                    f"{CLOSE_API_URL}/lead/",
                    auth=(CLOSE_API_KEY, ""),
                    params=params
                )

                if response.status_code != 200:
                    print(f"Error fetching leads with query {query}: {response.status_code}")
                    break

                data = response.json()
                batch = data.get("data", [])

                # Add leads not already in list (dedup by id)
                existing_ids = {l["id"] for l in leads}
                for lead in batch:
                    if lead["id"] not in existing_ids:
                        leads.append(lead)

                if not data.get("has_more", False):
                    break

                skip += limit

    return leads


async def sync_opportunities_to_supabase(opportunities: list) -> int:
    """
    Upsert opportunities to Supabase.
    Tracks pipeline value, won/lost status, and owner.
    """
    if not opportunities:
        return 0

    records = []
    for opp in opportunities:
        # Determine owner (Abdullah or Max based on user_id)
        owner_id = opp.get("user_id", "")
        owner_name = "Unknown"
        if owner_id == ABDULLAH_USER_ID:
            owner_name = "Abdullah"
        elif owner_id == MAX_USER_ID:
            owner_name = "Max"

        record = {
            "id": opp.get("id"),
            "lead_id": opp.get("lead_id"),
            "lead_name": opp.get("lead_name", ""),
            "status_type": opp.get("status_type", "active"),  # active, won, lost
            "status_label": opp.get("status_label", ""),
            "value": opp.get("value", 0) or 0,  # In cents
            "value_period": opp.get("value_period", "one_time"),
            "confidence": opp.get("confidence", 0),
            "owner_id": owner_id,
            "owner_name": owner_name,
            "date_won": opp.get("date_won"),
            "date_lost": opp.get("date_lost"),
            "created_at": opp.get("date_created"),
            "updated_at": opp.get("date_updated"),
            "synced_at": datetime.utcnow().isoformat(),
        }
        records.append(record)

    # Upsert to Supabase (need to create opportunities table)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/close_opportunities",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=records
        )

        if response.status_code not in [200, 201]:
            print(f"Supabase opportunities upsert error: {response.status_code} - {response.text}")
            return 0

    return len(records)


async def sync_hot_nurture_to_supabase(leads: list) -> int:
    """
    Upsert hot nurture leads to Supabase for tracking.
    """
    if not leads:
        return 0

    records = []
    for lead in leads:
        # Extract primary contact info
        contacts = lead.get("contacts", [])
        primary_contact = contacts[0] if contacts else {}

        record = {
            "id": lead.get("id"),
            "company_name": lead.get("display_name", lead.get("name", "")),
            "status_label": lead.get("status_label", ""),
            "contact_name": primary_contact.get("name", ""),
            "contact_email": primary_contact.get("emails", [{}])[0].get("email", "") if primary_contact.get("emails") else "",
            "contact_phone": primary_contact.get("phones", [{}])[0].get("phone", "") if primary_contact.get("phones") else "",
            "high_intent_flag": "Yes" if lead.get("custom", {}).get("high_intent_flag") == "Yes" else "No",
            "last_activity_at": lead.get("date_updated"),
            "created_at": lead.get("date_created"),
            "synced_at": datetime.utcnow().isoformat(),
        }
        records.append(record)

    # Upsert to Supabase
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/hot_nurture_leads",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            json=records
        )

        if response.status_code not in [200, 201]:
            print(f"Supabase hot nurture upsert error: {response.status_code} - {response.text}")
            return 0

    return len(records)


async def compute_metrics(since_date: str) -> dict:
    """
    Compute aggregated metrics from synced activities.
    Called after sync to update dashboard metrics.
    """
    metrics = {
        "calls": {"total": 0, "outbound": 0, "inbound": 0, "avg_duration": 0},
        "emails": {"total": 0, "sent": 0, "received": 0},
        "sms": {"total": 0, "sent": 0, "received": 0},
        "meetings": {"total": 0, "scheduled": 0, "completed": 0},
    }

    # Query Supabase for aggregated counts
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get counts by type and direction
        for activity_type in ["call", "email", "sms", "meeting"]:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/close_activities",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
                params={
                    "activity_type": f"eq.{activity_type}",
                    "created_at": f"gte.{since_date}",
                    "select": "id,direction,duration_seconds,status",
                }
            )

            if response.status_code == 200:
                activities = response.json()

                if activity_type == "call":
                    metrics["calls"]["total"] = len(activities)
                    metrics["calls"]["outbound"] = sum(1 for a in activities if a.get("direction") == "outbound")
                    metrics["calls"]["inbound"] = sum(1 for a in activities if a.get("direction") == "inbound")
                    durations = [a.get("duration_seconds", 0) or 0 for a in activities]
                    metrics["calls"]["avg_duration"] = sum(durations) / len(durations) if durations else 0

                elif activity_type == "email":
                    metrics["emails"]["total"] = len(activities)
                    metrics["emails"]["sent"] = sum(1 for a in activities if a.get("direction") == "outbound")
                    metrics["emails"]["received"] = sum(1 for a in activities if a.get("direction") == "inbound")

                elif activity_type == "sms":
                    metrics["sms"]["total"] = len(activities)
                    metrics["sms"]["sent"] = sum(1 for a in activities if a.get("direction") == "outbound")
                    metrics["sms"]["received"] = sum(1 for a in activities if a.get("direction") == "inbound")

                elif activity_type == "meeting":
                    metrics["meetings"]["total"] = len(activities)
                    metrics["meetings"]["scheduled"] = sum(1 for a in activities if a.get("status") == "scheduled")
                    metrics["meetings"]["completed"] = sum(1 for a in activities if a.get("status") == "completed")

    return metrics


async def run_sync(days_back: int = 90) -> dict:
    """
    Main sync function - pulls all data for the team.

    Syncs:
    - Tim's activities (calls, emails, SMS, meetings)
    - All opportunities (Abdullah + Max as AEs)
    - Hot nurture leads (top 10 priority)

    Args:
        days_back: How many days of history to sync (default 90)

    Returns:
        Sync summary with counts and metrics
    """
    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    results = {
        "synced_at": datetime.utcnow().isoformat(),
        "since_date": since_date,
        "days_back": days_back,
        "team": {
            "bdr": {"user_id": TIM_USER_ID, "name": "Tim Kipper"},
            "ae_primary": {"user_id": ABDULLAH_USER_ID or "not_set", "name": "Abdullah"},
            "ae_legacy": {"user_id": MAX_USER_ID or "not_set", "name": "Max"},
        },
        "counts": {},
        "opportunities": {},
        "hot_nurture": {},
        "metrics": {},
    }

    # 1. Sync Tim's activities (calls, emails, SMS, meetings)
    print(f"\n📞 Syncing Tim Kipper's activities since {since_date}...")
    for activity_type in ["call", "email", "sms", "meeting"]:
        print(f"  Fetching {activity_type}...")
        activities = await fetch_close_activities(activity_type, since_date)

        print(f"  Syncing {len(activities)} {activity_type} records...")
        count = await sync_to_supabase(activities, activity_type)

        results["counts"][activity_type] = count

    # 2. Sync opportunities (all AEs - 6 month lookback)
    opp_since = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
    print(f"\n💰 Syncing opportunities since {opp_since}...")
    opportunities = await fetch_opportunities(opp_since)

    # Categorize by status
    active = [o for o in opportunities if o.get("status_type") == "active"]
    won = [o for o in opportunities if o.get("status_type") == "won"]
    lost = [o for o in opportunities if o.get("status_type") == "lost"]

    # Calculate pipeline value
    active_value = sum(o.get("value", 0) or 0 for o in active) / 100  # Convert cents to dollars
    won_value = sum(o.get("value", 0) or 0 for o in won) / 100
    lost_value = sum(o.get("value", 0) or 0 for o in lost) / 100

    print(f"  Found {len(opportunities)} total: {len(active)} active, {len(won)} won, {len(lost)} lost")
    print(f"  Pipeline: ${active_value:,.0f} | Won: ${won_value:,.0f} | Lost: ${lost_value:,.0f}")

    opp_count = await sync_opportunities_to_supabase(opportunities)
    results["counts"]["opportunities"] = opp_count
    results["opportunities"] = {
        "total": len(opportunities),
        "active": len(active),
        "won": len(won),
        "lost": len(lost),
        "pipeline_value": active_value,
        "won_value": won_value,
        "lost_value": lost_value,
    }

    # 3. Sync hot nurture leads (top priority for conversion)
    print(f"\n🔥 Syncing hot nurture leads...")
    hot_leads = await fetch_hot_nurture_leads()
    print(f"  Found {len(hot_leads)} hot nurture leads")

    hot_count = await sync_hot_nurture_to_supabase(hot_leads)
    results["counts"]["hot_nurture"] = hot_count
    results["hot_nurture"] = {
        "total": len(hot_leads),
        "top_10": [
            {
                "company": l.get("display_name", l.get("name", "Unknown")),
                "status": l.get("status_label", ""),
            }
            for l in hot_leads[:10]
        ],
    }

    # 4. Compute fresh metrics
    results["metrics"] = await compute_metrics(since_date)

    print(f"\n✅ Sync complete!")
    return results


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for Close CRM sync."""

    def do_GET(self):
        """GET - Return sync status and last sync time."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        response = {
            "status": "ready",
            "endpoint": "/api/sync-close",
            "methods": ["GET (status)", "POST (trigger sync)"],
            "user_id": TIM_USER_ID,
            "description": "Syncs Tim Kipper's Close CRM activities to Supabase",
        }

        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        """POST - Trigger a full sync."""
        import asyncio

        # Check for API key (basic auth for manual triggers)
        auth = self.headers.get("Authorization", "")
        cron_secret = self.headers.get("x-vercel-cron-secret", "")

        # Allow if it's a Vercel cron job or has valid auth
        if not cron_secret and not auth:
            # For now, allow unauthenticated (dashboard internal use)
            pass

        try:
            # Get days_back from query params (default 90)
            days_back = 90
            if "?" in self.path:
                query = self.path.split("?")[1]
                for param in query.split("&"):
                    if param.startswith("days="):
                        days_back = int(param.split("=")[1])

            # Run the sync
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(run_sync(days_back))
            loop.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            self.wfile.write(json.dumps(results).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            error_response = {"error": str(e), "type": type(e).__name__}
            self.wfile.write(json.dumps(error_response).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
