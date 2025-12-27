#!/usr/bin/env python3
"""
Sync Close CRM Data to Star Schema

Pulls Tim Kipper's leads and activities from Close CRM
and populates the Star Schema tables in Supabase.

Usage:
    python sync_close_to_star_schema.py
    python sync_close_to_star_schema.py --leads-only
    python sync_close_to_star_schema.py --activities-only
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Optional
import httpx
from dotenv import load_dotenv

# Load environment
load_dotenv()

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Tim Kipper's Close user ID
TIM_USER_ID = "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1"

# Close API base
CLOSE_API_BASE = "https://api.close.com/api/v1"


def get_close_headers():
    """Get Close API headers with basic auth."""
    import base64
    auth = base64.b64encode(f"{CLOSE_API_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }


def get_supabase_headers():
    """Get Supabase REST API headers."""
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


async def fetch_close_leads(client: httpx.AsyncClient, limit: int = 10000) -> list:
    """Fetch leads from Close CRM (Tim's leads or all)."""
    leads = []
    skip = 0

    print(f"Fetching leads from Close CRM...", flush=True)

    while True:
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/",
            headers=get_close_headers(),
            params={
                "_skip": skip,
                "_limit": 100,
                "_fields": "id,display_name,status_label,contacts,custom,url,created_by,date_created,date_updated",
            },
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"Error fetching leads: {response.status_code}", flush=True)
            break

        data = response.json()
        batch = data.get("data", [])

        if not batch:
            break

        leads.extend(batch)
        skip += len(batch)
        print(f"  Fetched {len(leads)} leads...", flush=True)

        if len(leads) >= limit:
            break

    print(f"Total leads fetched: {len(leads)}", flush=True)
    return leads[:limit]


async def fetch_close_activities(client: httpx.AsyncClient, days: int = 90) -> list:
    """Fetch activities from Close CRM (calls, emails)."""
    activities = []

    # Date filter
    date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Fetch calls
    print(f"Fetching calls from last {days} days...", flush=True)
    skip = 0
    while True:
        response = await client.get(
            f"{CLOSE_API_BASE}/activity/call/",
            headers=get_close_headers(),
            params={
                "_skip": skip,
                "_limit": 100,
                "date_created__gte": date_from,
            },
            timeout=30.0
        )

        if response.status_code != 200:
            break

        batch = response.json().get("data", [])
        if not batch:
            break

        for call in batch:
            activities.append({
                "type": "call",
                "close_activity_id": call.get("id"),
                "lead_id": call.get("lead_id"),
                "user_id": call.get("user_id"),
                "direction": call.get("direction"),
                "duration": call.get("duration"),
                "disposition": call.get("disposition"),
                "date_created": call.get("date_created"),
            })

        skip += len(batch)
        if skip >= 500:  # Limit
            break

    print(f"  Calls: {len([a for a in activities if a['type'] == 'call'])}", flush=True)

    # Fetch emails
    print("Fetching emails...", flush=True)
    skip = 0
    while True:
        response = await client.get(
            f"{CLOSE_API_BASE}/activity/email/",
            headers=get_close_headers(),
            params={
                "_skip": skip,
                "_limit": 100,
                "date_created__gte": date_from,
            },
            timeout=30.0
        )

        if response.status_code != 200:
            break

        batch = response.json().get("data", [])
        if not batch:
            break

        for email in batch:
            activities.append({
                "type": "email",
                "close_activity_id": email.get("id"),
                "lead_id": email.get("lead_id"),
                "user_id": email.get("user_id"),
                "direction": email.get("direction"),
                "subject": email.get("subject", "")[:500],
                "date_created": email.get("date_created"),
            })

        skip += len(batch)
        if skip >= 500:  # Limit
            break

    print(f"  Emails: {len([a for a in activities if a['type'] == 'email'])}", flush=True)
    print(f"Total activities: {len(activities)}", flush=True)

    return activities


def should_exclude_status(status_label: str) -> bool:
    """
    Check if a Close CRM status should be EXCLUDED from sync entirely.

    These leads are junk/dead OR protected - never sync to Supabase, never enrich.
    """
    status_lower = status_label.lower().strip()

    # PROTECTED - Customers are OFF LIMITS for agents
    if "customer" in status_lower:
        return True

    # JUNK STATUSES - Never sync these
    if "do not sell" in status_lower:
        return True
    if "junk" in status_lower:
        return True
    if "out of business" in status_lower:
        return True
    if "unqualified" in status_lower:
        return True

    return False


def map_close_status_to_stage(status_label: str) -> str:
    """
    Map Close CRM status_label to our current_stage.

    NOTE: Excluded statuses (Customer, Junk, etc.) are filtered out
    by should_exclude_status() BEFORE this function is called.
    """
    status_lower = status_label.lower().strip()

    # Evangelist - advocates, low priority for outreach
    if "evangelist" in status_lower:
        return "evangelist"

    # Win-back opportunities - CAN be contacted
    if "churned" in status_lower:
        return "churned"  # OK to enrich and contact for win-back

    # Active pipeline statuses - work queue eligible
    if "hot" in status_lower:
        return "qualified"
    if "sql" in status_lower:
        return "qualified"
    if "sal" in status_lower:
        return "qualified"
    if "mql" in status_lower:
        return "contacted"
    if "nurture" in status_lower:
        return "nurture"
    if "opportunity" in status_lower or "opp" in status_lower:
        return "opportunity"
    if "raw" in status_lower:
        return "imported"

    # Default for unrecognized statuses
    return "imported"


def transform_lead_to_company(lead: dict) -> dict:
    """Transform a Close lead to dim_companies format."""
    custom = lead.get("custom", {})
    contacts = lead.get("contacts", [])
    primary_contact = contacts[0] if contacts else {}
    phones = primary_contact.get("phones", [])

    status = lead.get("status_label", "")
    current_stage = map_close_status_to_stage(status)

    # Determine ICP tier from status
    if "Hot" in status:
        tier = "PLATINUM"
        score = 85
    elif "Validated" in status or "ATL" in status:
        tier = "GOLD"
        score = 75
    elif "BTL" in status:
        tier = "SILVER"
        score = 55
    else:
        tier = "BRONZE"
        score = 40

    # Website is in the 'url' field, not custom fields
    website_url = lead.get("url")

    # Extract domain from URL for the domain field
    domain = None
    if website_url:
        domain = website_url.replace("https://", "").replace("http://", "").split("/")[0].lower()

    return {
        "company_name": lead.get("display_name", "Unknown"),
        "phone": phones[0].get("phone") if phones else None,
        "website": website_url,
        "domain": domain,
        "city": custom.get("City") or custom.get("city"),
        "state": custom.get("State") or custom.get("state"),
        "icp_score": score,
        "icp_tier": tier,
        "current_stage": current_stage,
        "close_lead_id": lead.get("id"),
        "source_type": "close_crm",
        "first_seen_at": lead.get("date_created"),
    }


async def upsert_companies(client: httpx.AsyncClient, leads: list, batch_size: int = 100) -> int:
    """
    Insert/update leads into dim_companies using sync_company_from_close() RPC.

    This uses the database function that:
    1. Checks for existing company by close_lead_id first
    2. Falls back to checking by normalized_name
    3. Updates if found, inserts if not
    4. Prevents duplicates via normalized_name unique constraint
    """
    # Filter out excluded statuses (Customer, Junk, Do Not Sell, etc.)
    filtered_leads = [
        lead for lead in leads
        if not should_exclude_status(lead.get("status_label", ""))
    ]
    excluded_count = len(leads) - len(filtered_leads)

    print(f"\nFiltering leads: {len(leads)} total, {excluded_count} excluded (Customer/Junk/etc), {len(filtered_leads)} to sync", flush=True)
    print(f"Upserting {len(filtered_leads)} companies via sync_company_from_close()...", flush=True)

    success = 0
    errors = 0

    # Process each lead through the dedup-safe RPC function
    for i, lead in enumerate(filtered_leads):
        company = transform_lead_to_company(lead)

        # Call the sync_company_from_close RPC function
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/sync_company_from_close",
            headers=get_supabase_headers(),
            json={
                "p_close_lead_id": company.get("close_lead_id"),
                "p_company_name": company.get("company_name"),
                "p_domain": company.get("domain"),
                "p_website": company.get("website"),
                "p_phone": company.get("phone"),
                "p_city": company.get("city"),
                "p_state": company.get("state"),
                "p_icp_score": company.get("icp_score"),
                "p_icp_tier": company.get("icp_tier"),
            },
            timeout=10.0
        )

        if response.status_code in (200, 201, 204):
            success += 1
        else:
            errors += 1
            if errors <= 5:  # Only log first 5 errors
                print(f"  Error syncing {company.get('company_name')}: {response.status_code}", flush=True)

        # Progress logging
        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(filtered_leads)} ({success} success, {errors} errors)...", flush=True)

    print(f"Successfully synced {success}/{len(filtered_leads)} companies ({errors} errors)", flush=True)
    return success


async def upsert_contacts(client: httpx.AsyncClient, leads: list) -> int:
    """Insert contacts into dim_contacts."""
    print(f"\nExtracting contacts from {len(leads)} leads...", flush=True)

    # First, get company_ids from dim_companies
    response = await client.get(
        f"{SUPABASE_URL}/rest/v1/dim_companies",
        headers=get_supabase_headers(),
        params={"select": "company_id,close_lead_id"},
        timeout=30.0
    )

    company_map = {}
    if response.status_code == 200:
        for row in response.json():
            if row.get("close_lead_id"):
                company_map[row["close_lead_id"]] = row["company_id"]

    success = 0
    for lead in leads:
        company_id = company_map.get(lead.get("id"))
        if not company_id:
            continue

        for contact in lead.get("contacts", []):
            name = contact.get("name", "")
            title = contact.get("title", "")

            # ATL detection
            is_atl = any(kw in title.lower() for kw in [
                "ceo", "president", "owner", "founder", "vp", "director",
                "head", "manager", "partner", "principal"
            ]) if title else False

            phones = contact.get("phones", [])
            emails = contact.get("emails", [])

            contact_data = {
                "company_id": company_id,
                "full_name": name,
                "email": emails[0].get("email") if emails else None,
                "phone": phones[0].get("phone") if phones else None,
                "title": title,
                "is_atl": is_atl,
                "source": "close_crm",
                "confidence": 90,  # High confidence from CRM
            }

            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/dim_contacts",
                headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
                json=contact_data,
                timeout=10.0
            )

            if response.status_code in (200, 201, 204):
                success += 1

    print(f"Successfully upserted {success} contacts", flush=True)
    return success


async def upsert_activities(client: httpx.AsyncClient, activities: list) -> int:
    """Insert activities into fact_activities."""
    print(f"\nUpserting {len(activities)} activities to fact_activities...", flush=True)

    # Get company_id mapping
    response = await client.get(
        f"{SUPABASE_URL}/rest/v1/dim_companies",
        headers=get_supabase_headers(),
        params={"select": "company_id,close_lead_id"},
        timeout=30.0
    )

    company_map = {}
    if response.status_code == 200:
        for row in response.json():
            if row.get("close_lead_id"):
                company_map[row["close_lead_id"]] = row["company_id"]

    # Get user_id mapping
    response = await client.get(
        f"{SUPABASE_URL}/rest/v1/dim_users",
        headers=get_supabase_headers(),
        params={"select": "user_id,close_user_id"},
        timeout=30.0
    )

    user_map = {}
    if response.status_code == 200:
        for row in response.json():
            if row.get("close_user_id"):
                user_map[row["close_user_id"]] = row["user_id"]

    success = 0
    for activity in activities:
        company_id = company_map.get(activity.get("lead_id"))
        user_id = user_map.get(activity.get("user_id"))

        fact = {
            "close_activity_id": activity.get("close_activity_id"),
            "company_id": company_id,
            "user_id": user_id,
            "activity_type": activity.get("type"),
            "direction": activity.get("direction"),
            "outcome": activity.get("disposition"),
            "duration_seconds": activity.get("duration"),
            "subject": activity.get("subject"),
            "activity_at": activity.get("date_created"),
        }

        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/fact_activities",
            headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json=fact,
            timeout=10.0
        )

        if response.status_code in (200, 201, 204):
            success += 1

    print(f"Successfully upserted {success}/{len(activities)} activities", flush=True)
    return success


async def refresh_views(client: httpx.AsyncClient):
    """Refresh materialized views."""
    print("\nRefreshing materialized views...", flush=True)

    # Call the refresh function via RPC
    response = await client.post(
        f"{SUPABASE_URL}/rest/v1/rpc/refresh_star_schema_views",
        headers=get_supabase_headers(),
        json={},
        timeout=60.0
    )

    if response.status_code in (200, 204):
        print("✅ Views refreshed!", flush=True)
    else:
        print(f"Warning: View refresh returned {response.status_code}", flush=True)
        print("  You may need to run: SELECT refresh_star_schema_views(); manually", flush=True)


async def main():
    parser = argparse.ArgumentParser(description="Sync Close CRM to Star Schema")
    parser.add_argument("--leads-only", action="store_true", help="Only sync leads")
    parser.add_argument("--activities-only", action="store_true", help="Only sync activities")
    parser.add_argument("--limit", type=int, default=10000, help="Max leads to fetch")
    parser.add_argument("--days", type=int, default=90, help="Days of activities to fetch")
    args = parser.parse_args()

    if not CLOSE_API_KEY:
        print("ERROR: CLOSE_API_KEY not set", flush=True)
        sys.exit(1)
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: Supabase credentials not set", flush=True)
        sys.exit(1)

    print("=" * 60, flush=True)
    print("CLOSE CRM → STAR SCHEMA SYNC", flush=True)
    print("=" * 60, flush=True)
    print(f"Close API: {'*' * 10}{CLOSE_API_KEY[-4:]}", flush=True)
    print(f"Supabase URL: {SUPABASE_URL}", flush=True)
    print(flush=True)

    async with httpx.AsyncClient() as client:
        if not args.activities_only:
            # Sync leads
            leads = await fetch_close_leads(client, limit=args.limit)
            await upsert_companies(client, leads)
            await upsert_contacts(client, leads)

        if not args.leads_only:
            # Sync activities
            activities = await fetch_close_activities(client, days=args.days)
            await upsert_activities(client, activities)

        # Refresh views
        await refresh_views(client)

    print(flush=True)
    print("=" * 60, flush=True)
    print("SYNC COMPLETE!", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
