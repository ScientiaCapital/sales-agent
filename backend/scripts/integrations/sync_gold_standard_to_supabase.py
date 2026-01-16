#!/usr/bin/env python3
"""
Sync Gold Standard Leads to Supabase Star Schema
=================================================
Syncs scored leads and discovered contacts to Supabase for:
1. Dashboard querying (mv_bdr_work_queue, mv_icp_gold_leads)
2. Progress tracking as enrichment improves scores
3. Persistent storage for the sales team

Tables Updated:
- dim_companies: Master lead list with ICP scores
- dim_contacts: ATL contacts discovered via Hunter.io
- fact_enrichments: Track enrichment costs and results

Usage:
    python sync_gold_standard_to_supabase.py                    # Sync all scored leads
    python sync_gold_standard_to_supabase.py --enriched batch_1.csv  # Sync enriched batch
    python sync_gold_standard_to_supabase.py --refresh-views    # Refresh materialized views
"""

import asyncio
import pandas as pd
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_tier_from_score(score: float) -> str:
    """Convert ICP score to tier"""
    if score >= 80:
        return 'PLATINUM'
    elif score >= 65:
        return 'GOLD'
    elif score >= 50:
        return 'SILVER'
    elif score >= 35:
        return 'BRONZE'
    else:
        return None  # Below threshold


async def sync_companies_to_supabase(csv_path: str) -> dict:
    """
    Sync scored leads from CSV to dim_companies table.

    Uses check-then-insert pattern since normalized_name unique constraint
    may not exist yet. Updates existing records, inserts new ones.
    """
    try:
        from supabase import create_client
        from datetime import datetime, timezone

        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("SUPABASE_URL or SUPABASE_KEY not configured")
            return {"error": "Supabase not configured"}

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Load CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} leads from {csv_path}")

        # Get existing normalized names for dedup
        logger.info("Fetching existing companies...")
        existing = supabase.table('dim_companies').select('normalized_name, company_id').execute()
        existing_map = {r['normalized_name']: r['company_id'] for r in existing.data}
        logger.info(f"Found {len(existing_map)} existing companies in Supabase")

        # Prepare records for Supabase
        inserts = []
        updates = []

        for idx, row in df.iterrows():
            normalized = str(row.get('name', '')).lower().strip()

            record = {
                'company_name': row.get('name', ''),
                'normalized_name': normalized,
                'domain': row.get('domain') if pd.notna(row.get('domain')) else None,
                'phone': str(row.get('phone')) if pd.notna(row.get('phone')) else None,
                'website': row.get('website') if pd.notna(row.get('website')) else None,
                'city': row.get('city') if pd.notna(row.get('city')) else None,
                'state': str(row.get('state', ''))[:2].upper() if pd.notna(row.get('state')) else None,
                'zip': str(row.get('zip'))[:10] if pd.notna(row.get('zip')) else None,
                'icp_score': int(row.get('icp_score', 0)),
                'icp_tier': get_tier_from_score(row.get('icp_score', 0)),
                'oem_count': int(row.get('OEM_Count', 0)) if pd.notna(row.get('OEM_Count')) else 0,
                'source_type': row.get('source_tag', 'grandmaster'),
                'current_stage': 'imported',
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            # Add OEM brands as JSONB
            oem_str = row.get('OEMs_Certified') or row.get('oem_certifications', '')
            if pd.notna(oem_str) and oem_str:
                record['oem_brands'] = [o.strip() for o in str(oem_str).split(',')]

            if normalized in existing_map:
                record['company_id'] = existing_map[normalized]
                updates.append(record)
            else:
                inserts.append(record)

        logger.info(f"Will insert {len(inserts)} new, update {len(updates)} existing")

        # Batch insert new records
        batch_size = 500
        inserted = 0

        for i in range(0, len(inserts), batch_size):
            batch = inserts[i:i+batch_size]
            try:
                supabase.table('dim_companies').insert(batch).execute()
                inserted += len(batch)
                logger.info(f"Inserted: {inserted}/{len(inserts)}")
            except Exception as e:
                logger.error(f"Insert batch error: {e}")

        # Batch update existing records
        updated = 0
        for record in updates:
            try:
                company_id = record.pop('company_id')
                supabase.table('dim_companies').update(record).eq('company_id', company_id).execute()
                updated += 1
                if updated % 100 == 0:
                    logger.info(f"Updated: {updated}/{len(updates)}")
            except Exception as e:
                logger.error(f"Update error for {record.get('company_name')}: {e}")

        logger.info(f"✅ Synced {inserted} new + {updated} updated = {inserted + updated} total")

        return {
            "success": True,
            "inserted": inserted,
            "updated": updated,
            "total": inserted + updated
        }

    except ImportError:
        logger.error("supabase-py not installed. Run: pip install supabase")
        return {"error": "supabase-py not installed"}
    except Exception as e:
        logger.error(f"Error syncing to Supabase: {e}")
        return {"error": str(e)}


async def sync_contacts_from_enrichment(enriched_csv: str) -> dict:
    """
    Sync discovered ATL contacts from enrichment batch to dim_contacts.

    Uses check-then-insert pattern since email unique constraint may not exist.
    """
    try:
        from supabase import create_client
        from datetime import datetime, timezone

        if not SUPABASE_URL or not SUPABASE_KEY:
            return {"error": "Supabase not configured"}

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        df = pd.read_csv(enriched_csv)
        logger.info(f"Loaded {len(df)} enriched leads from {enriched_csv}")

        # Get existing contacts by email for dedup
        logger.info("Fetching existing contacts...")
        existing_contacts = supabase.table('dim_contacts').select('email, contact_id').execute()
        existing_emails = {r['email'].lower(): r['contact_id'] for r in existing_contacts.data if r.get('email')}
        logger.info(f"Found {len(existing_emails)} existing contacts in Supabase")

        contacts_added = 0
        contacts_updated = 0
        companies_updated = 0
        skipped = 0

        for idx, row in df.iterrows():
            # Skip if no ATL contacts found
            if not row.get('enrichment_success', False):
                skipped += 1
                continue

            company_name = str(row.get('name', '')).lower().strip()

            # Find company in dim_companies
            company_result = supabase.table('dim_companies').select('company_id').eq(
                'normalized_name', company_name
            ).execute()

            if not company_result.data:
                logger.warning(f"Company not found in Supabase: {row.get('name')}")
                skipped += 1
                continue

            company_id = company_result.data[0]['company_id']

            # Add best ATL contact
            if row.get('best_atl_email'):
                email = str(row.get('best_atl_email', '')).lower().strip()

                contact_record = {
                    'company_id': company_id,
                    'full_name': row.get('best_atl_name', ''),
                    'email': email,
                    'phone': row.get('best_atl_phone') if pd.notna(row.get('best_atl_phone')) else None,
                    'title': row.get('best_atl_position', ''),
                    'is_atl': True,
                    'confidence': 90,  # Hunter.io confidence
                    'source': 'hunter',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }

                # Check-then-insert/update pattern
                if email in existing_emails:
                    # Update existing contact
                    contact_id = existing_emails[email]
                    supabase.table('dim_contacts').update(contact_record).eq('contact_id', contact_id).execute()
                    contacts_updated += 1
                else:
                    # Insert new contact
                    contact_record['created_at'] = datetime.now(timezone.utc).isoformat()
                    supabase.table('dim_contacts').insert(contact_record).execute()
                    existing_emails[email] = True  # Track for dedup in this batch
                    contacts_added += 1

            # Update company's enrichment timestamp
            supabase.table('dim_companies').update({
                'last_enriched_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('company_id', company_id).execute()

            companies_updated += 1

            # Progress logging
            if (contacts_added + contacts_updated) % 50 == 0:
                logger.info(f"Progress: {contacts_added + contacts_updated} contacts processed...")

        logger.info(f"✅ Added {contacts_added} new + {contacts_updated} updated = {contacts_added + contacts_updated} ATL contacts")
        logger.info(f"✅ Updated {companies_updated} companies")
        logger.info(f"⏭️ Skipped {skipped} (no ATL found)")

        return {
            "success": True,
            "contacts_added": contacts_added,
            "contacts_updated": contacts_updated,
            "companies_updated": companies_updated,
            "skipped": skipped
        }

    except Exception as e:
        logger.error(f"Error syncing contacts: {e}")
        return {"error": str(e)}


async def refresh_materialized_views():
    """
    Refresh the Star Schema materialized views for dashboard.
    """
    try:
        from supabase import create_client

        if not SUPABASE_URL or not SUPABASE_KEY:
            return {"error": "Supabase not configured"}

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Call the refresh function
        result = supabase.rpc('refresh_star_schema_views').execute()

        logger.info("✅ Refreshed materialized views (mv_icp_gold_leads, mv_bdr_work_queue)")

        return {"success": True}

    except Exception as e:
        logger.error(f"Error refreshing views: {e}")
        return {"error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description='Sync Gold Standard leads to Supabase')
    parser.add_argument('--scored', type=str, default='data/final_enrichment_output/all_leads_scored_20251129.csv',
                        help='Path to scored leads CSV')
    parser.add_argument('--enriched', type=str, help='Path to enriched batch CSV')
    parser.add_argument('--refresh-views', action='store_true', help='Refresh materialized views')

    args = parser.parse_args()

    print("=" * 70)
    print("SUPABASE SYNC - Gold Standard Lead Lists")
    print("=" * 70)

    if args.enriched:
        # Sync enriched contacts
        result = await sync_contacts_from_enrichment(args.enriched)
        print(f"\nContacts sync result: {result}")
    else:
        # Sync scored companies
        result = await sync_companies_to_supabase(args.scored)
        print(f"\nCompanies sync result: {result}")

    if args.refresh_views:
        view_result = await refresh_materialized_views()
        print(f"\nView refresh result: {view_result}")


if __name__ == "__main__":
    asyncio.run(main())
