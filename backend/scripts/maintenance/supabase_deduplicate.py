#!/usr/bin/env python3
"""
Supabase Company Deduplication
==============================
Deduplicates dim_companies table by normalized company name.

Priority for keeping records:
1. Has close_lead_id (linked to Close CRM)
2. Highest icp_score
3. Most recent updated_at

Usage:
    python supabase_deduplicate.py --analyze    # Just count duplicates
    python supabase_deduplicate.py --dry-run    # Show what would be deleted
    python supabase_deduplicate.py --execute    # Actually delete duplicates
"""

import os
import re
import logging
import argparse
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path(__file__).parent.parent / '.env')

from supabase import create_client

# Supabase config
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY required in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Common suffixes to strip for normalization
COMPANY_SUFFIXES = [
    r'\s+inc\.?$', r'\s+llc\.?$', r'\s+corp\.?$', r'\s+co\.?$',
    r'\s+ltd\.?$', r'\s+limited$', r'\s+incorporated$',
    r'\s+company$', r'\s+corporation$', r'\s+enterprises?$',
    r'\s+services?$', r'\s+systems?$', r'\s+solutions?$',
    r'\s+group$', r'\s+holdings?$', r',?\s+llc\.?$', r',?\s+inc\.?$',
    r'\s+pbc$', r'\s+dba\s+.*$',
]


def normalize_company_name(name: str) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""

    normalized = str(name).lower().strip()

    # Remove punctuation except hyphens
    normalized = re.sub(r'[^\w\s-]', '', normalized)

    # Strip common suffixes
    for suffix in COMPANY_SUFFIXES:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def fetch_all_companies():
    """Fetch all companies from Supabase with pagination."""
    all_companies = []
    offset = 0
    batch_size = 1000

    logger.info("Fetching all companies from Supabase...")

    while True:
        result = supabase.table('dim_companies').select(
            'company_id, company_name, close_lead_id, icp_score, created_at, updated_at, domain, website'
        ).range(offset, offset + batch_size - 1).execute()

        all_companies.extend(result.data)

        if len(result.data) < batch_size:
            break
        offset += batch_size
        logger.info(f"  Fetched {len(all_companies)} companies...")

    logger.info(f"Total companies fetched: {len(all_companies)}")
    return all_companies


def analyze_duplicates(companies: list) -> dict:
    """
    Analyze duplicates and determine which records to keep/delete.

    Returns dict with:
    - groups: dict of normalized_name -> list of company records
    - to_keep: set of company_ids to keep
    - to_delete: set of company_ids to delete
    """
    # Group by normalized name
    groups = defaultdict(list)
    for company in companies:
        norm_name = normalize_company_name(company.get('company_name', ''))
        if norm_name:  # Skip empty names
            groups[norm_name].append(company)

    to_keep = set()
    to_delete = set()

    for norm_name, group in groups.items():
        if len(group) == 1:
            # No duplicates
            to_keep.add(group[0]['company_id'])
            continue

        # Sort by priority: close_lead_id first, then icp_score, then updated_at
        def sort_key(c):
            has_close = 1 if c.get('close_lead_id') else 0
            score = c.get('icp_score') or 0
            updated = c.get('updated_at') or '1970-01-01'
            return (has_close, score, updated)

        sorted_group = sorted(group, key=sort_key, reverse=True)

        # Keep the best one, delete the rest
        to_keep.add(sorted_group[0]['company_id'])
        for company in sorted_group[1:]:
            to_delete.add(company['company_id'])

    # Handle companies with no normalized name (empty/null)
    no_name = [c for c in companies if not normalize_company_name(c.get('company_name', ''))]
    for company in no_name:
        to_keep.add(company['company_id'])  # Keep all - can't dedupe without name

    return {
        'groups': groups,
        'to_keep': to_keep,
        'to_delete': to_delete,
    }


def backup_to_csv(companies: list, filename: str):
    """Backup companies to CSV before deletion."""
    import csv

    backup_dir = Path(__file__).parent / 'data' / 'supabase_backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    filepath = backup_dir / filename

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        if companies:
            writer = csv.DictWriter(f, fieldnames=companies[0].keys())
            writer.writeheader()
            writer.writerows(companies)

    logger.info(f"Backup saved: {filepath}")
    return filepath


def reassign_related_records(to_delete: set, groups: dict, companies: list):
    """
    Reassign related records (activities, contacts) from duplicate companies to the keeper.
    Uses batch processing for efficiency.
    """
    # Build a map: duplicate_id -> keeper_id
    duplicate_to_keeper = {}
    company_map = {c['company_id']: c for c in companies}

    for norm_name, group in groups.items():
        if len(group) <= 1:
            continue

        # Sort by priority (same as analyze_duplicates)
        def sort_key(c):
            has_close = 1 if c.get('close_lead_id') else 0
            score = c.get('icp_score') or 0
            updated = c.get('updated_at') or '1970-01-01'
            return (has_close, score, updated)

        sorted_group = sorted(group, key=sort_key, reverse=True)
        keeper_id = sorted_group[0]['company_id']

        for company in sorted_group[1:]:
            if company['company_id'] in to_delete:
                duplicate_to_keeper[company['company_id']] = keeper_id

    logger.info(f"Reassigning related records for {len(duplicate_to_keeper)} duplicates...")

    # Process in batches grouped by keeper_id
    # Group duplicates by their keeper
    keeper_to_dups = defaultdict(list)
    for dup_id, keeper_id in duplicate_to_keeper.items():
        keeper_to_dups[keeper_id].append(dup_id)

    # Reassign in batches (100 keepers at a time)
    total_reassigned = {'activities': 0, 'contacts': 0, 'opportunities': 0}
    batch_count = 0

    for keeper_id, dup_ids in keeper_to_dups.items():
        # Reassign all duplicates for this keeper in one batch per table
        for table, key in [('fact_activities', 'activities'), ('dim_contacts', 'contacts'), ('fact_opportunities', 'opportunities')]:
            try:
                result = supabase.table(table).update(
                    {'company_id': keeper_id}
                ).in_('company_id', dup_ids).execute()
                if result.data:
                    total_reassigned[key] += len(result.data)
            except Exception as e:
                pass  # Table may not have matching records

        batch_count += 1
        if batch_count % 100 == 0:
            logger.info(f"  Processed {batch_count}/{len(keeper_to_dups)} keepers...")

    logger.info(f"  Reassigned {total_reassigned['activities']} activities")
    logger.info(f"  Reassigned {total_reassigned['contacts']} contacts")
    logger.info(f"  Reassigned {total_reassigned['opportunities']} opportunities")

    return sum(total_reassigned.values())


def delete_duplicates(to_delete: set, batch_size: int = 100):
    """Delete duplicate records from Supabase."""
    deleted_count = 0
    to_delete_list = list(to_delete)
    failed = []

    for i in range(0, len(to_delete_list), batch_size):
        batch = to_delete_list[i:i+batch_size]

        try:
            result = supabase.table('dim_companies').delete().in_('company_id', batch).execute()
            deleted_count += len(batch)
        except Exception as e:
            # Try one by one for failed batch
            for company_id in batch:
                try:
                    supabase.table('dim_companies').delete().eq('company_id', company_id).execute()
                    deleted_count += 1
                except Exception as e2:
                    failed.append(company_id)
                    logger.warning(f"  Failed to delete {company_id}: {e2}")

        logger.info(f"  Deleted {deleted_count}/{len(to_delete_list)} records...")

    if failed:
        logger.warning(f"  {len(failed)} records could not be deleted due to constraints")

    return deleted_count


def main():
    parser = argparse.ArgumentParser(description='Deduplicate Supabase dim_companies')
    parser.add_argument('--analyze', action='store_true', help='Just analyze duplicates')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted')
    parser.add_argument('--execute', action='store_true', help='Actually delete duplicates')
    parser.add_argument('--top', type=int, default=30, help='Show top N duplicate groups')

    args = parser.parse_args()

    if not any([args.analyze, args.dry_run, args.execute]):
        parser.print_help()
        return

    # Fetch all companies
    companies = fetch_all_companies()

    # Analyze duplicates
    logger.info("\nAnalyzing duplicates...")
    analysis = analyze_duplicates(companies)

    duplicate_groups = {k: v for k, v in analysis['groups'].items() if len(v) > 1}
    total_duplicates = len(analysis['to_delete'])

    print(f"\n{'='*60}")
    print("SUPABASE DEDUPLICATION ANALYSIS")
    print(f"{'='*60}")
    print(f"Total companies:        {len(companies)}")
    print(f"Duplicate groups:       {len(duplicate_groups)}")
    print(f"Records to DELETE:      {total_duplicates}")
    print(f"Records to KEEP:        {len(analysis['to_keep'])}")
    print(f"Expected after cleanup: {len(companies) - total_duplicates}")

    # Show top duplicates
    print(f"\nTop {args.top} duplicate groups:")
    sorted_groups = sorted(duplicate_groups.items(), key=lambda x: -len(x[1]))
    for norm_name, group in sorted_groups[:args.top]:
        with_close = sum(1 for c in group if c.get('close_lead_id'))
        print(f"  \"{norm_name[:50]}\" - {len(group)} copies ({with_close} with Close ID)")

    if args.analyze:
        return

    if args.dry_run:
        print(f"\n--- DRY RUN MODE ---")
        print(f"Would delete {total_duplicates} records")

        # Show some examples
        print(f"\nExample deletions (first 10):")
        examples = list(analysis['to_delete'])[:10]
        for company_id in examples:
            company = next(c for c in companies if c['company_id'] == company_id)
            print(f"  DELETE: {company.get('company_name', 'N/A')[:50]} (ID: {company_id[:8]}...)")

        return

    if args.execute:
        print(f"\n{'='*60}")
        print("EXECUTING DEDUPLICATION")
        print(f"{'='*60}")

        # Create backup first
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"dim_companies_backup_{timestamp}.csv"
        backup_to_csv(companies, backup_file)

        # Also backup just the ones we're deleting
        to_delete_records = [c for c in companies if c['company_id'] in analysis['to_delete']]
        deleted_backup = f"dim_companies_DELETED_{timestamp}.csv"
        backup_to_csv(to_delete_records, deleted_backup)

        # Confirmation
        print(f"\nAbout to DELETE {total_duplicates} records.")
        print(f"Backups created in: data/supabase_backups/")
        confirm = input("\nType 'DELETE' to confirm: ")

        if confirm != 'DELETE':
            print("Aborted.")
            return

        # First reassign related records (activities, contacts) to keeper
        print("\nReassigning related records to keeper companies...")
        reassigned = reassign_related_records(analysis['to_delete'], analysis['groups'], companies)
        print(f"Reassigned {reassigned} related records")

        # Execute deletion
        print("\nDeleting duplicates...")
        deleted = delete_duplicates(analysis['to_delete'])

        print(f"\n{'='*60}")
        print("DEDUPLICATION COMPLETE")
        print(f"{'='*60}")
        print(f"Deleted: {deleted} records")
        print(f"Remaining: {len(companies) - deleted} companies")

        # Verify
        final_count = supabase.table('dim_companies').select('company_id', count='exact').execute()
        print(f"Verified count: {final_count.count}")


if __name__ == "__main__":
    main()
