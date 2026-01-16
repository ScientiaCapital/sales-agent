#!/usr/bin/env python3
"""
Repair Contact Titles
=====================
Fixes titles with:
- "READ BIO" suffixes
- Another person's name concatenated (e.g., "Jason BoyceVice President")
- Pipe separators and other artifacts

Usage:
    python repair_titles.py --dry-run   # Show what would be fixed
    python repair_titles.py --execute   # Actually fix the data
"""

import os
import re
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def clean_title(title: str) -> str:
    """
    Clean up a title - strip READ BIO, pipe separators, merged names.

    "CO-FOUNDER | READ BIO" -> "CO-FOUNDER"
    "Jason BoyceVice President" -> "Vice President"
    "SpencerPresident & Owner" -> "President & Owner"

    DOES NOT modify valid titles like:
    - "EVP & General Manager" (EVP is a title, not a name)
    - "Warehouse Manager" (Warehouse is a qualifier, not a name)
    - "Managing Director" (Managing is part of the title)
    """
    if not title:
        return title

    # Strip "READ BIO" and similar suffixes
    title = re.sub(r'\s*\|\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)

    # Strip "View Profile", "Learn More" etc.
    title = re.sub(r'\s*\|\s*(?:VIEW|LEARN|READ)\s*(?:PROFILE|MORE|BIO)\s*$', '', title, flags=re.IGNORECASE)

    # Strip trailing pipes and dashes
    title = re.sub(r'\s*[\|\-]\s*$', '', title)

    # Title qualifiers/prefixes that should NOT be stripped (they're part of the title)
    title_qualifiers = {
        # Level prefixes
        'svp', 'evp', 'avp', 'vp', 'senior', 'junior', 'sr', 'jr', 'chief',
        'executive', 'managing', 'assistant', 'associate', 'deputy',
        # Department/area qualifiers
        'warehouse', 'operations', 'project', 'field', 'regional', 'national',
        'global', 'area', 'district', 'zone', 'commercial', 'residential',
        'sales', 'marketing', 'finance', 'hr', 'it', 'tech', 'engineering',
        'construction', 'maintenance', 'service', 'customer', 'business',
        'product', 'account', 'general', 'corporate', 'master', 'maine',
        'north', 'south', 'east', 'west', 'america', 'division',
    }

    # Only try to strip ACTUAL person names concatenated to titles
    # Pattern: PersonName + TitleKeyword (without space)
    # e.g., "JasonVice President", "SpencerPresident", "Jason BoyceVice President"

    # Executive role keywords that would follow a person's name
    role_keywords = ['Vice', 'President', 'CEO', 'CFO', 'CTO', 'COO', 'CMO',
                     'Owner', 'Founder', 'Director', 'Partner']

    # Check for pattern: [ProperName(s)][RoleKeyword]
    # The name part should:
    # - Be capitalized
    # - NOT be a title qualifier
    # - Be directly followed by a role keyword (no space or lowercase letter between)
    for keyword in role_keywords:
        # Pattern: Proper name(s) directly followed by role keyword
        # e.g., "JasonVice" or "Jason BoyceVice"
        match = re.match(rf'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)({keyword}.*)$', title)
        if match:
            potential_name = match.group(1).strip()
            role_part = match.group(2).strip()

            # Verify the potential name is NOT a title qualifier
            name_words = potential_name.lower().split()
            if not any(w in title_qualifiers for w in name_words):
                # This looks like a person name prepended to a title
                title = role_part
                break

    return title.strip()


def fetch_all_contacts():
    """Fetch all contacts with pagination."""
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'contact_id, company_id, full_name, title, source'
        ).range(offset, offset + batch_size - 1).execute()

        all_contacts.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_contacts


def fetch_company_names(company_ids: list) -> dict:
    """Fetch company names for context."""
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
    parser = argparse.ArgumentParser(description='Repair contact titles')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed')
    parser.add_argument('--execute', action='store_true', help='Actually fix the data')

    args = parser.parse_args()

    if not any([args.dry_run, args.execute]):
        parser.print_help()
        return

    print("=" * 70)
    print("CONTACT TITLE REPAIR")
    print("=" * 70)

    # Fetch all contacts
    print("\nFetching contacts...")
    contacts = fetch_all_contacts()
    print(f"Total contacts: {len(contacts)}")

    # Find contacts that need title repair
    repairs_needed = []

    for contact in contacts:
        original_title = contact.get('title') or ''
        cleaned_title = clean_title(original_title)

        if cleaned_title != original_title:
            repairs_needed.append({
                'contact_id': contact['contact_id'],
                'company_id': contact.get('company_id'),
                'name': contact.get('full_name', ''),
                'original_title': original_title,
                'cleaned_title': cleaned_title,
            })

    print(f"\nTitles needing repair: {len(repairs_needed)}")

    if not repairs_needed:
        print("\nNo title repairs needed!")
        return

    # Get company names for context
    company_ids = list(set(r['company_id'] for r in repairs_needed if r.get('company_id')))
    company_names = fetch_company_names(company_ids)

    # Show repairs
    print(f"\n{'='*70}")
    print("TITLE REPAIRS TO APPLY")
    print(f"{'='*70}")

    for r in repairs_needed[:30]:
        company = company_names.get(r['company_id'], 'Unknown')
        print(f"\n  Company: {company[:40]}")
        print(f"  Name: {r['name']}")
        print(f"  BEFORE: '{r['original_title']}'")
        print(f"  AFTER:  '{r['cleaned_title']}'")

    if len(repairs_needed) > 30:
        print(f"\n  ... and {len(repairs_needed) - 30} more")

    # Save audit log
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    audit_file = data_dir / f'TITLE_REPAIR_LOG_{timestamp}.csv'
    with open(audit_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'company', 'name', 'original_title', 'cleaned_title', 'contact_id'
        ])
        writer.writeheader()
        for r in repairs_needed:
            writer.writerow({
                'company': company_names.get(r['company_id'], ''),
                'name': r['name'],
                'original_title': r['original_title'],
                'cleaned_title': r['cleaned_title'],
                'contact_id': r['contact_id'],
            })
    print(f"\nAudit log saved to: {audit_file.name}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN - No changes made")
        print(f"{'='*70}")
        return

    if args.execute:
        print(f"\n{'='*70}")
        print("EXECUTING TITLE REPAIRS")
        print(f"{'='*70}")

        confirm = input(f"\nType 'FIX' to confirm repair of {len(repairs_needed)} titles: ")
        if confirm != 'FIX':
            print("Aborted.")
            return

        # Apply repairs
        fixed = 0
        for r in repairs_needed:
            try:
                supabase.table('dim_contacts').update({
                    'title': r['cleaned_title']
                }).eq('contact_id', r['contact_id']).execute()
                fixed += 1

            except Exception as e:
                logger.error(f"Error fixing title for {r['name']}: {e}")

        print(f"\n{'='*70}")
        print(f"TITLE REPAIR COMPLETE")
        print(f"{'='*70}")
        print(f"Fixed: {fixed} titles")


if __name__ == "__main__":
    main()
