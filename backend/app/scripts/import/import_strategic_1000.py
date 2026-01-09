#!/usr/bin/env python3
"""
Import Strategic 1000 Companies from icp_gold_leads
====================================================
Imports high-value dealer leads with source diversity:
- 400 Generac (generator dealers)
- 300 Cummins (industrial generators)
- 150 Trane (top HVAC)
- 100 Mitsubishi (mini-splits)
- 50 Rheem (water heater + HVAC)

Features:
- Source quota management
- Full audit logging to lead_audit_log
- Phase tracking (enrichment_status)
- Deduplication by normalized company name
"""

import os
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Strategic source quotas
SOURCE_QUOTAS = {
    'OEM:Generac': 400,
    'OEM:Cummins': 300,
    'OEM:Trane': 150,
    'OEM:Mitsubishi': 100,
    'OEM:Rheem': 50,
}

def get_tier_from_score(score: float) -> str:
    if not score:
        return 'BRONZE'
    if score >= 80:
        return 'PLATINUM'
    elif score >= 65:
        return 'GOLD'
    elif score >= 50:
        return 'SILVER'
    return 'BRONZE'


def fetch_existing_names(supabase) -> set:
    """Fetch all normalized company names from dim_companies."""
    logger.info("Fetching existing companies...")
    names = set()
    offset = 0
    while True:
        result = supabase.table('dim_companies').select('normalized_name').range(offset, offset + 999).execute()
        for c in result.data:
            if c.get('normalized_name'):
                names.add(c['normalized_name'])
        if len(result.data) < 1000:
            break
        offset += 1000
    logger.info(f"Found {len(names)} existing companies")
    return names


def fetch_leads_by_source(supabase, source: str, existing_names: set, limit: int) -> list:
    """Fetch leads from a specific source that aren't already imported or synced."""
    # Only fetch leads NOT already synced to sales-agent
    result = supabase.table('icp_gold_leads').select('*').eq('source', source).neq('status_label', 'synced_to_sales_agent').execute()

    leads = []
    for lead in result.data:
        name = lead.get('company_name', '')
        normalized = name.lower().strip() if name else ''
        if normalized and normalized not in existing_names:
            lead['_normalized_name'] = normalized
            leads.append(lead)
        if len(leads) >= limit:
            break

    return leads[:limit]


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
    """Log import to lead_audit_log with full context."""
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
                'imported_from': 'icp_gold_leads',
                'import_type': 'strategic_1000'
            },
            'created_at': datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger.warning(f"Audit log error for {company_name}: {e}")


def mark_lead_as_synced(supabase, lead_id: str, company_id: str):
    """Mark lead in icp_gold_leads as synced to sales-agent."""
    try:
        supabase.table('icp_gold_leads').update({
            'status_label': 'synced_to_sales_agent',
            'synced_at': datetime.now(timezone.utc).isoformat(),
            'close_lead_id': company_id  # Reference to dim_companies.company_id
        }).eq('id', lead_id).execute()
    except Exception as e:
        logger.warning(f"Could not mark lead {lead_id} as synced: {e}")


def main():
    parser = argparse.ArgumentParser(description='Import strategic 1000 companies')
    parser.add_argument('--dry-run', action='store_true', help='Preview without importing')
    parser.add_argument('--execute', action='store_true', help='Actually import leads')
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        return

    print("=" * 70)
    print("STRATEGIC 1000 IMPORT: High-Value Dealer Selection")
    print("=" * 70)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    batch_id = f"strategic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Get existing companies
    existing_names = fetch_existing_names(supabase)

    # Collect leads from each source
    all_leads = []
    print(f"\n📊 Fetching leads by source:")

    for source, quota in SOURCE_QUOTAS.items():
        leads = fetch_leads_by_source(supabase, source, existing_names, quota)
        print(f"  {source:<25}: {len(leads):>4} / {quota} quota")
        all_leads.extend(leads)
        # Add to existing to prevent cross-source duplicates
        for lead in leads:
            existing_names.add(lead['_normalized_name'])

    print(f"\n✅ Total selected: {len(all_leads)} companies")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("DRY-RUN - No changes made")
        print(f"{'='*70}")

        # Show samples
        print(f"\nSample by source:")
        for source in SOURCE_QUOTAS.keys():
            source_leads = [l for l in all_leads if l.get('source') == source][:3]
            print(f"\n  [{source}]")
            for lead in source_leads:
                print(f"    • {lead.get('company_name', '')[:50]}")
        return

    # Execute import
    print(f"\n{'='*70}")
    print(f"IMPORTING {len(all_leads)} COMPANIES")
    print(f"{'='*70}")

    imported = 0
    errors = 0
    by_source = {s: 0 for s in SOURCE_QUOTAS}

    for i, lead in enumerate(all_leads, 1):
        try:
            company = map_lead_to_company(lead, batch_id)
            supabase.table('dim_companies').insert(company).execute()

            # Log audit
            log_import_audit(
                supabase,
                company['company_id'],
                company['company_name'],
                company['source_type'],
                batch_id
            )

            # Mark as synced in icp_gold_leads (so dealer-scraper-mvp knows)
            mark_lead_as_synced(supabase, lead['id'], company['company_id'])

            imported += 1
            by_source[lead.get('source', 'unknown')] = by_source.get(lead.get('source', 'unknown'), 0) + 1

            if imported % 100 == 0:
                print(f"  Progress: {imported}/{len(all_leads)} imported...")

        except Exception as e:
            errors += 1
            logger.error(f"Error importing {lead.get('company_name')}: {e}")

    # Summary
    print(f"\n{'='*70}")
    print("IMPORT COMPLETE")
    print(f"{'='*70}")
    print(f"  Batch ID: {batch_id}")
    print(f"  Imported: {imported}")
    print(f"  Errors: {errors}")
    print(f"\n  By source:")
    for source, count in by_source.items():
        if count > 0:
            print(f"    {source:<25}: {count:>4}")

    # Verify
    result = supabase.table('dim_companies').select('company_id', count='exact').execute()
    print(f"\n  Total dim_companies: {result.count}")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
