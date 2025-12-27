#!/usr/bin/env python3
"""
Sync Close CRM Contacts to Supabase Star Schema
================================================
This script syncs contacts Tim manually adds/updates in Close CRM back to Supabase.

Use Cases:
1. Tim finds a contact via LinkedIn/research → adds to Close → synced to Supabase
2. Tim updates contact info (new phone, email verified) → synced to Supabase
3. Tim marks contact as ATL decision-maker → synced to Supabase

Flow:
    Close CRM (Tim's manual additions)
         ↓
    Cron runs every 30 minutes
         ↓
    Supabase dim_contacts (update or insert)
         ↓
    BDR Work Queue auto-updates (follow-up tasks)

Usage:
    python sync_close_contacts_to_supabase.py                    # Sync last 2 hours
    python sync_close_contacts_to_supabase.py --hours 24        # Sync last 24 hours
    python sync_close_contacts_to_supabase.py --full            # Full sync (all contacts)

Cron Setup (every 30 minutes):
    */30 * * * * cd /path/to/sales-agent/backend && /path/to/venv/bin/python sync_close_contacts_to_supabase.py >> /var/log/close_sync.log 2>&1
"""

import asyncio
import logging
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

# Close CRM
CLOSE_API_KEY = os.getenv('CLOSE_API_KEY')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ATL title keywords
ATL_TITLES = [
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'cto', 'chief technology', 'cfo', 'chief financial', 'coo', 'chief operating',
    'vp', 'vice president', 'svp', 'evp', 'director', 'head of',
    'manager', 'general manager', 'partner', 'principal'
]


def is_atl(title: str) -> bool:
    """Check if title indicates an Above-The-Line decision maker"""
    if not title:
        return False
    title_lower = title.lower()
    return any(atl in title_lower for atl in ATL_TITLES)


async def fetch_close_contacts(hours: int = 2, full_sync: bool = False) -> list:
    """
    Fetch contacts from Close CRM that were recently updated.

    Args:
        hours: Number of hours to look back for updates
        full_sync: If True, fetch all contacts regardless of update time
    """
    if not CLOSE_API_KEY:
        logger.error("CLOSE_API_KEY not configured")
        return []

    contacts = []

    async with httpx.AsyncClient() as client:
        # Paginate through all contacts
        has_more = True
        cursor = None

        while has_more:
            url = "https://api.close.com/api/v1/contact/"
            params = {"_limit": 100}

            if cursor:
                params["_cursor"] = cursor

            response = await client.get(
                url,
                params=params,
                auth=(CLOSE_API_KEY, "")
            )

            if response.status_code != 200:
                logger.error(f"Close API error: {response.status_code} - {response.text}")
                break

            data = response.json()
            batch = data.get("data", [])

            # Filter by update time if not full sync
            if not full_sync:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                batch = [
                    c for c in batch
                    if datetime.fromisoformat(c.get('date_updated', '2000-01-01T00:00:00Z').replace('Z', '+00:00')) > cutoff
                ]

            contacts.extend(batch)

            # Check for more pages
            cursor = data.get("cursor")
            has_more = cursor is not None and len(data.get("data", [])) == 100

            # Early exit if we're filtering by time and batch is empty
            if not full_sync and not batch:
                break

        logger.info(f"Fetched {len(contacts)} contacts from Close CRM")

    return contacts


async def sync_contacts_to_supabase(contacts: list) -> dict:
    """
    Sync Close CRM contacts to Supabase dim_contacts table.

    Returns:
        dict with inserted, updated, and error counts
    """
    try:
        from supabase import create_client

        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("Supabase not configured")
            return {"error": "Supabase not configured"}

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Get existing companies for FK lookup
        companies = supabase.table('dim_companies').select('company_id, normalized_name').execute()
        company_map = {r['normalized_name']: r['company_id'] for r in companies.data}

        # Get existing contacts by email for dedup
        existing_contacts = supabase.table('dim_contacts').select('contact_id, email').execute()
        existing_emails = {r['email']: r['contact_id'] for r in existing_contacts.data if r.get('email')}

        inserted = 0
        updated = 0
        skipped = 0
        errors = 0

        for contact in contacts:
            try:
                # Extract contact info
                emails = contact.get('emails', [])
                phones = contact.get('phones', [])
                urls = contact.get('urls', [])

                # Phase 0 enhancement: Extract primary + secondary emails/phones
                email_primary = emails[0].get('email') if len(emails) > 0 else None
                email_secondary = emails[1].get('email') if len(emails) > 1 else None

                phone_primary = phones[0].get('phone') if len(phones) > 0 else None
                phone_secondary = phones[1].get('phone') if len(phones) > 1 else None

                # Phase 0 enhancement: Extract LinkedIn and Twitter URLs by type
                linkedin_url = None
                twitter_url = None
                for url_obj in urls:
                    url = url_obj.get('url', '')
                    url_type = url_obj.get('type', '')
                    if 'linkedin' in url.lower() or url_type == 'linkedin':
                        linkedin_url = url
                    elif 'twitter' in url.lower() or url_type == 'twitter':
                        twitter_url = url

                if not email_primary:
                    skipped += 1
                    continue

                # Find company via lead lookup
                lead_id = contact.get('lead_id')
                company_id = None

                if lead_id:
                    # Fetch lead to get company name
                    async with httpx.AsyncClient() as client:
                        lead_response = await client.get(
                            f"https://api.close.com/api/v1/lead/{lead_id}/",
                            auth=(CLOSE_API_KEY, "")
                        )
                        if lead_response.status_code == 200:
                            lead_data = lead_response.json()
                            company_name = lead_data.get('display_name', '').lower().strip()
                            company_id = company_map.get(company_name)

                # Build contact record
                title = contact.get('title', '')
                record = {
                    'full_name': contact.get('name', ''),
                    'email': email_primary.lower(),
                    'email_secondary': email_secondary.lower() if email_secondary else None,  # NEW
                    'phone': phone_primary,
                    'phone_secondary': phone_secondary,  # NEW
                    'linkedin_url': linkedin_url,  # May already exist, but ensure populated
                    'twitter_url': twitter_url,  # NEW
                    'title': title,
                    'is_atl': is_atl(title),
                    'source': 'close_manual',
                    'confidence': 95,  # High confidence - Tim added manually
                    'validated': True,
                    'close_contact_id': contact.get('id'),  # NEW: Close contact ID reference
                    'close_lead_id': lead_id,  # NEW: Close lead ID reference
                    'close_raw_data': contact,  # NEW: Full API response for audit
                    'close_date_created': contact.get('date_created'),  # NEW
                    'close_date_updated': contact.get('date_updated'),  # NEW
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }

                if company_id:
                    record['company_id'] = company_id

                # Insert or update
                if email_primary.lower() in existing_emails:
                    # Update existing
                    contact_id = existing_emails[email_primary.lower()]
                    supabase.table('dim_contacts').update(record).eq('contact_id', contact_id).execute()
                    updated += 1
                else:
                    # Insert new
                    supabase.table('dim_contacts').insert(record).execute()
                    existing_emails[email_primary.lower()] = record  # Track for dedup
                    inserted += 1

            except Exception as e:
                logger.error(f"Error processing contact {contact.get('name')}: {e}")
                errors += 1

        logger.info(f"✅ Synced {inserted} new, {updated} updated, {skipped} skipped, {errors} errors")

        return {
            "success": True,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Sync error: {e}")
        return {"error": str(e)}


async def create_follow_up_tasks(contacts: list) -> int:
    """
    Create follow-up task suggestions for newly synced ATL contacts.

    When Tim adds a new ATL contact, suggest a follow-up call/email.
    """
    # This integrates with the BDR Work Queue via the mv_bdr_work_queue view
    # When a new ATL contact is added with no recent activity,
    # it will appear in the "📞 First Call - ATL" action bucket automatically

    atl_count = sum(1 for c in contacts if is_atl(c.get('title', '')))
    logger.info(f"📋 {atl_count} ATL contacts added - will appear in BDR Work Queue")
    return atl_count


async def main():
    parser = argparse.ArgumentParser(description='Sync Close CRM contacts to Supabase')
    parser.add_argument('--hours', type=int, default=2, help='Hours to look back for updates')
    parser.add_argument('--full', action='store_true', help='Full sync (all contacts)')

    args = parser.parse_args()

    print("=" * 70)
    print("CLOSE CRM → SUPABASE CONTACT SYNC")
    print("=" * 70)

    # Fetch contacts from Close
    contacts = await fetch_close_contacts(hours=args.hours, full_sync=args.full)

    if not contacts:
        print("No contacts to sync")
        return

    # Sync to Supabase
    result = await sync_contacts_to_supabase(contacts)
    print(f"\nSync result: {result}")

    # Create follow-up suggestions for ATL contacts
    await create_follow_up_tasks(contacts)


if __name__ == "__main__":
    asyncio.run(main())
