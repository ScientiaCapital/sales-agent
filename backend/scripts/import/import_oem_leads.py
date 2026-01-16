#!/usr/bin/env python3
"""
Import OEM Leads from icp_gold_leads → dim_companies
====================================================
Imports dealer leads from the gold standard table into the sales pipeline.

Features:
- Deduplication by normalized company name
- Full audit logging to lead_audit_log
- Batch processing with progress tracking
- Dry-run mode for preview

Usage:
    python import_oem_leads.py --dry-run    # Preview what would be imported
    python import_oem_leads.py --execute    # Actually import the leads
    python import_oem_leads.py --source OEM:Carrier  # Filter by source
"""

import os
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent.parent.parent / '.env', override=True)

from supabase import create_client

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BATCH_SIZE = 100

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_tier_from_score(score: float) -> str:
    """Convert ICP score to tier."""
    if not score:
        return 'BRONZE'
    if score >= 80:
        return 'PLATINUM'
    elif score >= 65:
        return 'GOLD'
    elif score >= 50:
        return 'SILVER'
    else:
        return 'BRONZE'


def fetch_existing_companies(supabase) -> set:
    """Fetch all normalized company names from dim_companies."""
    logger.info("Fetching existing companies from dim_companies...")
    result = supabase.table('dim_companies').select('normalized_name').execute()
    names = set(c['normalized_name'] for c in result.data if c.get('normalized_name'))
    logger.info(f"Found {len(names)} existing companies")
    return names


def fetch_leads_to_import(supabase, existing_names: set, source_filter: str = None) -> list:
    """Fetch leads from icp_gold_leads that are NOT in dim_companies."""
    logger.info("Fetching leads from icp_gold_leads...")

    query = supabase.table('icp_gold_leads').select('*')
    if source_filter:
        query = query.eq('source', source_filter)

    result = query.execute()
    all_leads = result.data
    logger.info(f"Found {len(all_leads)} total leads in icp_gold_leads")

    # Filter out already imported
    new_leads = []
    for lead in all_leads:
        name = lead.get('company_name', '')
        normalized = name.lower().strip() if name else ''
        if normalized and normalized not in existing_names:
            lead['_normalized_name'] = normalized
            new_leads.append(lead)

    logger.info(f"Found {len(new_leads)} leads NOT in dim_companies (ready to import)")
    return new_leads


def map_lead_to_company(lead: dict, batch_id: str) -> dict:
    """Map icp_gold_leads record to dim_companies format."""
    now = datetime.now(timezone.utc).isoformat()

    return {
        'company_id': str(uuid4()),
        'company_name': lead.get('company_name', ''),
        'normalized_name': lead.get('_normalized_name', ''),
        'icp_score': lead.get('coperniq_score') or lead.get('qualification_score') or 50,
        'icp_tier': get_tier_from_score(lead.get('coperniq_score')),
        'has_hvac_trade': lead.get('has_hvac') or False,
        'has_electrical_trade': lead.get('has_electrical') or False,
        'has_plumbing_trade': lead.get('has_plumbing') or False,
        'trade_count': lead.get('trade_count') or 1,
        'source_type': lead.get('source', 'OEM:Unknown'),
        'original_source': 'icp_gold_leads',
        'current_stage': 'imported',
        'enrichment_status': 'pending',
        'created_at': now,
        'updated_at': now,
        'source_attribution': f"batch:{batch_id}"
    }


def log_import_audit(supabase, company_id: str, company_name: str, source: str, batch_id: str):
    """Log import to lead_audit_log."""
    try:
        supabase.table('lead_audit_log').insert({
            'company_id': company_id,
            'stage': 'import',
            'event_type': 'lead_imported',
            'success': True,
            'context': {
                'source': source,
                'batch_id': batch_id,
                'company_name': company_name,
                'imported_from': 'icp_gold_leads'
            },
            'created_at': datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.warning(f"Audit log error for {company_name}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Import OEM leads from icp_gold_leads')
    parser.add_argument('--dry-run', action='store_true', help='Preview without importing')
    parser.add_argument('--execute', action='store_true', help='Actually import leads')
    parser.add_argument('--source', type=str, default=None, help='Filter by source (e.g., OEM:Carrier)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of leads to import')

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        return

    print("=" * 70)
    print("OEM LEADS IMPORT: icp_gold_leads → dim_companies")
    print("=" * 70)
    print(f"Mode: {'DRY-RUN (preview only)' if args.dry_run else 'EXECUTE (will import)'}")
    print(f"Source filter: {args.source or 'ALL'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    batch_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Get existing companies
    existing = fetch_existing_companies(supabase)

    # Get leads to import
    leads = fetch_leads_to_import(supabase, existing, args.source)

    if args.limit:
        leads = leads[:args.limit]
        print(f"Limited to: {len(leads)} leads")

    if not leads:
        print("\nNo leads to import!")
        return

    # Group by source
    by_source = {}
    for lead in leads:
        src = lead.get('source', 'unknown')
        by_source[src] = by_source.get(src, 0) + 1

    print(f"\nLeads by source:")
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("DRY-RUN - No changes made")
        print(f"{'='*70}")
        print(f"Would import: {len(leads)} leads")

        # Show sample
        print(f"\nSample leads (first 10):")
        for lead in leads[:10]:
            name = lead.get('company_name', 'Unknown')[:40]
            score = lead.get('coperniq_score', 'N/A')
            src = lead.get('source', 'N/A')
            print(f"  • {name:<40} | Score: {score} | Source: {src}")

        if len(leads) > 10:
            print(f"  ... and {len(leads) - 10} more")
        return

    # Execute import
    print(f"\n{'='*70}")
    print(f"IMPORTING {len(leads)} LEADS")
    print(f"{'='*70}")

    imported = 0
    errors = 0

    for i in range(0, len(leads), BATCH_SIZE):
        batch = leads[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(leads) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\nBatch {batch_num}/{total_batches} - Processing {len(batch)} leads...")

        for lead in batch:
            try:
                company = map_lead_to_company(lead, batch_id)

                # Insert to dim_companies
                supabase.table('dim_companies').insert(company).execute()

                # Log audit
                log_import_audit(
                    supabase,
                    company['company_id'],
                    company['company_name'],
                    company['source_type'],
                    batch_id
                )

                imported += 1

                if imported % 50 == 0:
                    print(f"  Imported: {imported}/{len(leads)}")

            except Exception as e:
                errors += 1
                logger.error(f"Error importing {lead.get('company_name')}: {e}")

    # Final summary
    print(f"\n{'='*70}")
    print("IMPORT COMPLETE")
    print(f"{'='*70}")
    print(f"  Batch ID: {batch_id}")
    print(f"  Imported: {imported}")
    print(f"  Errors: {errors}")
    print(f"  Success Rate: {imported/(imported+errors)*100:.1f}%")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    # Verify
    result = supabase.table('dim_companies').select('company_id', count='exact').execute()
    print(f"\nTotal dim_companies: {result.count}")


if __name__ == "__main__":
    main()
