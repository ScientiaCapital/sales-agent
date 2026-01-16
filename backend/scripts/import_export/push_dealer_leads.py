#!/usr/bin/env python3
"""
Push dealer-scraper-mvp leads to Supabase dim_companies.

Reads CSV exports from dealer-scraper-mvp and inserts into dim_companies
with original_source='dealer-scraper-mvp' and close_lead_id=NULL (fresh leads).
"""
import os
import sys
import csv
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def normalize_domain(url: str) -> str:
    """Extract clean domain from URL."""
    if not url:
        return None
    url = url.lower().strip()
    url = url.replace('http://', '').replace('https://', '').replace('www.', '')
    url = url.split('/')[0]
    return url if url else None


def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address."""
    if not email or '@' not in email:
        return None
    domain = email.split('@')[1].lower().strip()
    # Skip generic email providers
    generic = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
               'icloud.com', 'msn.com', 'live.com', 'mail.com', 'comcast.net']
    if domain in generic:
        return None
    return domain


def push_leads_from_csv(csv_path: str, tier: str = 'gold', dry_run: bool = False):
    """Push leads from dealer-scraper CSV to Supabase."""

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Get existing domains to avoid duplicates
    print("Fetching existing domains from Supabase...")
    existing = supabase.table('dim_companies').select('domain').not_.is_('domain', 'null').execute()
    existing_domains = {r['domain'].lower() for r in existing.data if r.get('domain')}
    print(f"  Found {len(existing_domains)} existing domains")

    # Read CSV
    print(f"\nReading {csv_path}...")
    leads = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)
    print(f"  Found {len(leads)} leads in CSV")

    # Prepare inserts
    inserts = []
    duplicates = 0
    no_domain = 0

    for lead in leads:
        # Handle different column names in CSVs
        website = lead.get('company_website', '') or lead.get('website', '')
        email = lead.get('contact_email', '') or lead.get('email', '')
        phone = lead.get('contact_phone', '') or lead.get('phone', '')

        domain = normalize_domain(website)

        # Try to extract domain from email if no website
        if not domain:
            domain = extract_domain_from_email(email)

        if not domain:
            no_domain += 1
            continue

        if domain in existing_domains:
            duplicates += 1
            continue

        # Build company record (must match dim_companies schema exactly)
        company = {
            'company_name': lead.get('company_name', '').strip(),
            'domain': domain,
            'phone': phone.strip() if phone else None,
            'city': lead.get('city', '').strip() or None,
            'state': lead.get('state', '').strip() or None,
            'zip': lead.get('zip', '').strip() or None,
            'original_source': 'dealer-scraper-mvp',
            'source_type': f'dealer_scraper_{tier}',
            'close_lead_id': None,  # Fresh lead, not from Close CRM
        }

        # Add OEM info to oem_brands column
        oems = lead.get('oems_certified', '')
        if oems and oems != "[]":
            company['oem_brands'] = oems

        inserts.append(company)
        existing_domains.add(domain)  # Prevent duplicates within batch

    print(f"\n  New leads to insert: {len(inserts)}")
    print(f"  Duplicates skipped: {duplicates}")
    print(f"  No domain skipped: {no_domain}")

    if dry_run:
        print("\n[DRY RUN] Would insert these leads:")
        for lead in inserts[:10]:
            print(f"  - {lead['company_name']} ({lead['domain']})")
        if len(inserts) > 10:
            print(f"  ... and {len(inserts) - 10} more")
        return

    if not inserts:
        print("\nNo new leads to insert.")
        return

    # Insert in batches
    batch_size = 50
    total_inserted = 0

    for i in range(0, len(inserts), batch_size):
        batch = inserts[i:i+batch_size]
        try:
            result = supabase.table('dim_companies').insert(batch).execute()
            total_inserted += len(batch)
            print(f"  Inserted batch {i//batch_size + 1}: {len(batch)} leads")
        except Exception as e:
            print(f"  ERROR inserting batch: {e}")
            # Try one by one
            for lead in batch:
                try:
                    supabase.table('dim_companies').insert(lead).execute()
                    total_inserted += 1
                except Exception as e2:
                    print(f"    Failed: {lead['company_name']} - {e2}")

    print(f"\n✅ Total inserted: {total_inserted} leads")


def main():
    parser = argparse.ArgumentParser(description='Push dealer-scraper leads to Supabase')
    parser.add_argument('--file', type=str, required=True, help='Path to CSV file')
    parser.add_argument('--tier', type=str, default='gold', choices=['gold', 'silver', 'bronze'],
                        help='Lead tier (default: gold)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without inserting')

    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    push_leads_from_csv(args.file, args.tier, args.dry_run)


if __name__ == '__main__':
    main()
