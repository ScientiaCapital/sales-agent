#!/usr/bin/env python3
"""
Mark Exported ICP Leads as Added to Close CRM
=============================================
Marks companies from COPERNIQ_ICP_VERIFIED.csv as already imported to Close.
This ensures they don't appear in the new Top 500 ICP list.

Usage:
    cd backend
    source venv/bin/activate
    python app/scripts/mark_exported_leads.py

Author: Claude + Tim
Date: Jan 2026
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Load environment
script_dir = Path(__file__).resolve().parent
for env_path in [script_dir.parent.parent.parent / '.env', script_dir.parent.parent / '.env']:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

# CSV path
CSV_PATH = Path(__file__).parent.parent.parent / "exports" / "COPERNIQ_ICP_VERIFIED.csv"
IMPORT_MARKER = "CTO_IMPORT_20260116"  # Placeholder to indicate CTO imported these


def get_supabase():
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY required")
    return create_client(url, key)


def normalize_domain(domain: str) -> str:
    """Normalize domain for matching."""
    if not domain:
        return ""
    domain = str(domain).lower().strip()
    domain = domain.replace("www.", "")
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.rstrip("/")
    return domain


def main():
    print("\n" + "=" * 60)
    print("MARKING EXPORTED ICP LEADS AS ADDED TO CLOSE")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load CSV
    print(f"\n[1/4] Loading CSV: {CSV_PATH}")
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    print(f"       Loaded {len(df)} leads from CSV")

    # Get unique domains
    domains = df['domain'].dropna().unique()
    domains = [normalize_domain(d) for d in domains if d]
    print(f"       Found {len(domains)} unique domains")

    # Connect to Supabase
    print("\n[2/4] Connecting to Supabase...")
    supabase = get_supabase()

    # Fetch all companies with matching domains
    print("\n[3/4] Finding matching companies in database...")
    matched_companies = []

    # Process in batches of 100 domains
    batch_size = 100
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, close_lead_id'
        ).in_('domain', batch).execute()

        if result.data:
            matched_companies.extend(result.data)

    print(f"       Found {len(matched_companies)} matching companies")

    # Filter to companies not already in Close
    to_update = [
        c for c in matched_companies
        if not c.get('close_lead_id') or c['close_lead_id'] == ''
    ]
    print(f"       {len(to_update)} companies not yet marked as in Close")

    already_in_close = len(matched_companies) - len(to_update)
    if already_in_close > 0:
        print(f"       {already_in_close} already have close_lead_id set")

    # Update companies
    print(f"\n[4/4] Marking {len(to_update)} companies as imported to Close...")

    updated_count = 0
    errors = []

    for company in to_update:
        try:
            supabase.table('dim_companies').update({
                'close_lead_id': IMPORT_MARKER,
                'updated_at': datetime.utcnow().isoformat(),
            }).eq('company_id', company['company_id']).execute()
            updated_count += 1
        except Exception as e:
            errors.append(f"{company['company_name']}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nCSV leads:          {len(df)}")
    print(f"Unique domains:     {len(domains)}")
    print(f"Matched in DB:      {len(matched_companies)}")
    print(f"Already in Close:   {already_in_close}")
    print(f"Newly marked:       {updated_count}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    # Show domains not found
    matched_domains = set(normalize_domain(c['domain']) for c in matched_companies if c.get('domain'))
    not_found = [d for d in domains if d and d not in matched_domains]
    if not_found:
        print(f"\nDomains not found in DB ({len(not_found)}):")
        for d in not_found[:20]:
            print(f"  - {d}")
        if len(not_found) > 20:
            print(f"  ... and {len(not_found) - 20} more")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"\nThese {updated_count} companies are now marked with close_lead_id='{IMPORT_MARKER}'")
    print("They will be EXCLUDED from the mv_top500_icp materialized view.")
    print("\nNext: Refresh the materialized view with:")
    print("  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top500_icp;")


if __name__ == "__main__":
    main()
