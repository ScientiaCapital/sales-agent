#!/usr/bin/env python3
"""
Clean Garbage Contacts from Database
=====================================
Removes non-person entries that were scraped before the BS filter was added.

Targets:
1. Service/product category names (e.g., "Installation Types", "Battery Storage")
2. Concatenated names (e.g., "John SmithCEO", "Laud VidalCustomer Advocate")
3. Placeholder names (e.g., "John Doe")
4. Social media artifacts (e.g., "LinkedinVisit LinkedIn")

Usage:
    python clean_garbage_contacts.py --dry-run   # Show what would be deleted
    python clean_garbage_contacts.py --execute   # Actually delete garbage
"""

import os
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Garbage names (exact match, case-insensitive)
GARBAGE_NAMES = {
    # Service/product categories
    "installation types", "battery storage", "industrial solar", "commercial solar",
    "residential solar", "solar panels", "solar energy", "solar power",
    "heating", "cooling", "plumbing", "electrical", "hvac", "roofing",
    "air conditioning", "water heater", "energy", "services",
    "ev charging", "ev chargers", "solar installation", "solar installer",
    "heat pump", "ductless", "mini split", "geothermal",
    # Placeholder names
    "john doe", "jane doe", "test user", "sample name", "your name",
    "first last", "name here", "full name",
    # Navigation/UI text
    "learn more", "read more", "click here", "view all", "see more",
    "schedule now", "call now", "get quote", "request quote", "contact us",
    "about us", "our team", "meet the team", "leadership", "management",
    # Social media
    "facebook", "twitter", "linkedin", "instagram", "youtube", "tiktok",
}

# Patterns that indicate garbage
GARBAGE_PATTERNS = [
    r'^(schedule|call|contact|click|learn|view|see|read|get|our|the|your|my|home|about|services?)$',
    r'^(heating|cooling|plumbing|electrical|hvac|solar|roofing|air|water)$',
    r'^(request|quote|estimate|free|now|today|more|here|us|me)$',
    r'^\d+$',  # Just numbers
    r'^[a-z]$',  # Single letters
    r'(privacy|policy|terms|copyright|reserved|rights)',
    r'(facebook|twitter|linkedin|instagram|youtube|tiktok)',
    r'^(mr|mrs|ms|dr)\.?$',
    r'(admin|webmaster|info|contact|support|sales)@',
]

# Concatenated name patterns - more specific to avoid false positives like "McCall"
CONCATENATED_PATTERNS = [
    # Role concatenated without space (e.g., "JohnCEO", "MaryDirector")
    r'\w+(CEO|CFO|CTO|COO|CMO|VP|Vice|Director|Manager|Owner|Founder|President|Customer|Advocate|Designer|Specialist|Crew|Lead|Installer|Technician|Roofing)$',
]


def is_garbage_contact(name: str, title: str = "") -> tuple[bool, str]:
    """Check if a contact is garbage."""
    if not name:
        return True, "empty name"

    name_lower = name.lower().strip()
    title_lower = (title or '').lower().strip()

    reasons = []

    # Check exact garbage names
    if name_lower in GARBAGE_NAMES:
        reasons.append(f"garbage name: '{name_lower}'")

    # Check garbage patterns
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, name_lower):
            reasons.append(f"matches pattern: '{pattern}'")
            break

    # Check concatenated patterns (role stuck to name)
    for pattern in CONCATENATED_PATTERNS:
        if re.search(pattern, name):
            reasons.append(f"concatenated role")
            break

    # Check for social media keywords
    social_keywords = ['linkedin', 'facebook', 'twitter', 'instagram', 'visit', 'follow']
    if any(kw in name_lower for kw in social_keywords):
        reasons.append(f"social media keyword in name")

    # Name too short
    if len(name_lower) < 3:
        reasons.append("name too short")

    # Name too long (probably scraped paragraph)
    if len(name) > 50:
        reasons.append("name too long (>50 chars)")

    # Check for "Visit" prefix (social media artifacts)
    if name.startswith("Visit ") or name.endswith(" Visit"):
        reasons.append("starts/ends with 'Visit'")

    # Contains role concatenated without space
    if re.search(r'[a-z](Customer|Designer|Specialist|Advocate|Engineer|Technician)', name):
        reasons.append("role concatenated to name")

    return bool(reasons), '; '.join(reasons) if reasons else ''


def fetch_all_contacts():
    """Fetch all contacts with pagination."""
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'contact_id, company_id, full_name, first_name, last_name, title, email, phone, source, created_at'
        ).range(offset, offset + batch_size - 1).execute()

        all_contacts.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_contacts


def fetch_company_names(company_ids: list) -> dict:
    """Fetch company names for a list of IDs."""
    if not company_ids:
        return {}

    names = {}
    for i in range(0, len(company_ids), 100):
        batch = company_ids[i:i+100]
        result = supabase.table('dim_companies').select(
            'company_id, company_name'
        ).in_('company_id', batch).execute()
        for c in result.data:
            names[c['company_id']] = c['company_name']

    return names


def main():
    parser = argparse.ArgumentParser(description='Clean garbage contacts from database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')
    parser.add_argument('--execute', action='store_true', help='Actually delete garbage')
    parser.add_argument('--limit', type=int, default=None, help='Limit contacts to process')

    args = parser.parse_args()

    if not any([args.dry_run, args.execute]):
        parser.print_help()
        return

    print("=" * 70)
    print("GARBAGE CONTACT CLEANUP")
    print("=" * 70)

    # Fetch all contacts
    print("\nFetching contacts...")
    contacts = fetch_all_contacts()
    print(f"Total contacts: {len(contacts)}")

    if args.limit:
        contacts = contacts[:args.limit]
        print(f"Limited to: {len(contacts)} contacts")

    # Identify garbage
    garbage = []
    clean = []

    for contact in contacts:
        name = contact.get('full_name', '')
        title = contact.get('title', '')
        is_garbage, reason = is_garbage_contact(name, title)

        if is_garbage:
            garbage.append({
                'contact_id': contact['contact_id'],
                'company_id': contact.get('company_id'),
                'name': name,
                'title': title,
                'reason': reason,
                'source': contact.get('source', ''),
            })
        else:
            clean.append(contact)

    print(f"\nResults:")
    print(f"  Clean contacts: {len(clean)}")
    print(f"  Garbage contacts: {len(garbage)}")

    if not garbage:
        print("\nNo garbage contacts found!")
        return

    # Get company names for context
    company_ids = list(set(g['company_id'] for g in garbage if g.get('company_id')))
    company_names = fetch_company_names(company_ids)

    # Show garbage contacts
    print(f"\n{'='*70}")
    print("GARBAGE CONTACTS TO DELETE")
    print(f"{'='*70}")

    # Group by reason
    by_reason = {}
    for g in garbage:
        reason_key = g['reason'].split(';')[0] if g['reason'] else 'unknown'
        if reason_key not in by_reason:
            by_reason[reason_key] = []
        by_reason[reason_key].append(g)

    for reason, items in sorted(by_reason.items(), key=lambda x: -len(x[1])):
        print(f"\n[{reason}] - {len(items)} contacts")
        for item in items[:5]:  # Show first 5 of each type
            company = company_names.get(item['company_id'], 'Unknown') or 'Unknown'
            name = item.get('name') or '(empty)'
            print(f"  • {name[:40]:<40} | {company[:30]}")
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN - No changes made")
        print(f"{'='*70}")
        print(f"Would delete {len(garbage)} garbage contacts")
        return

    if args.execute:
        print(f"\n{'='*70}")
        print("EXECUTING CLEANUP")
        print(f"{'='*70}")

        confirm = input(f"\nType 'DELETE' to confirm deletion of {len(garbage)} contacts: ")
        if confirm != 'DELETE':
            print("Aborted.")
            return

        # Delete in batches
        deleted = 0
        batch_size = 100
        contact_ids = [g['contact_id'] for g in garbage]

        for i in range(0, len(contact_ids), batch_size):
            batch = contact_ids[i:i+batch_size]
            try:
                supabase.table('dim_contacts').delete().in_('contact_id', batch).execute()
                deleted += len(batch)
                print(f"Deleted batch {i//batch_size + 1}: {len(batch)} contacts")
            except Exception as e:
                logger.error(f"Error deleting batch: {e}")

        print(f"\n{'='*70}")
        print(f"CLEANUP COMPLETE")
        print(f"{'='*70}")
        print(f"Deleted: {deleted} garbage contacts")

        # Verify
        remaining = supabase.table('dim_contacts').select('contact_id', count='exact').execute()
        print(f"Remaining contacts: {remaining.count}")


if __name__ == "__main__":
    main()
