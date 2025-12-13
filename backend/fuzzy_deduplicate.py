#!/usr/bin/env python3
"""
Fuzzy Company Deduplication
===========================
Uses fuzzy string matching + domain verification to find near-duplicates.

Only merges companies when:
1. Name similarity > 90% AND same domain, OR
2. Name similarity > 95% (very high confidence)

Usage:
    python fuzzy_deduplicate.py --analyze    # Show potential duplicates
    python fuzzy_deduplicate.py --dry-run    # Show what would be merged
    python fuzzy_deduplicate.py --execute    # Actually merge duplicates
"""

import os
import re
import logging
import argparse
from difflib import SequenceMatcher
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path(__file__).parent.parent / '.env')

from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_domain(url_or_domain: str) -> str:
    """Extract clean domain from URL or domain string."""
    if not url_or_domain:
        return ""

    # Add scheme if missing
    if not url_or_domain.startswith(('http://', 'https://')):
        url_or_domain = 'https://' + url_or_domain

    try:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc.lower()
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""


def fuzzy_ratio(s1: str, s2: str) -> float:
    """Calculate fuzzy string similarity ratio."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def fetch_all_companies():
    """Fetch all companies with pagination."""
    all_companies = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_companies').select(
            'company_id, company_name, normalized_name, domain, website, close_lead_id, icp_score, updated_at'
        ).range(offset, offset + batch_size - 1).execute()

        all_companies.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_companies


def find_fuzzy_duplicates(companies: list, name_threshold: float = 0.90, high_confidence_threshold: float = 0.95):
    """
    Find fuzzy duplicate pairs.

    Returns list of (score, keeper, duplicate) tuples.
    """
    duplicates = []

    # Index by first 3 chars of normalized name for faster comparison
    name_index = defaultdict(list)
    for c in companies:
        norm = c.get('normalized_name') or ''
        if len(norm) >= 3:
            # Add to multiple buckets for fuzzy matching
            name_index[norm[:3]].append(c)
            if len(norm) >= 4:
                name_index[norm[:2]].append(c)

    checked = set()

    for c1 in companies:
        norm1 = c1.get('normalized_name') or ''
        domain1 = extract_domain(c1.get('domain') or c1.get('website') or '')

        if len(norm1) < 3:
            continue

        # Check against similar prefixes
        candidates = []
        for prefix_len in [2, 3]:
            if len(norm1) >= prefix_len:
                candidates.extend(name_index.get(norm1[:prefix_len], []))

        for c2 in candidates:
            if c1['company_id'] >= c2['company_id']:
                continue

            pair_key = (c1['company_id'], c2['company_id'])
            if pair_key in checked:
                continue
            checked.add(pair_key)

            norm2 = c2.get('normalized_name') or ''
            if norm1 == norm2:  # Exact match already handled
                continue

            ratio = fuzzy_ratio(norm1, norm2)

            if ratio < name_threshold:
                continue

            domain2 = extract_domain(c2.get('domain') or c2.get('website') or '')

            # High confidence: very similar names OR same domain
            is_duplicate = False
            confidence = "LOW"

            if ratio >= high_confidence_threshold:
                is_duplicate = True
                confidence = "HIGH"
            elif ratio >= name_threshold and domain1 and domain1 == domain2:
                is_duplicate = True
                confidence = "MEDIUM"

            if is_duplicate:
                # Decide keeper: prefer close_lead_id, then icp_score, then updated_at
                def sort_key(c):
                    has_close = 1 if c.get('close_lead_id') else 0
                    score = c.get('icp_score') or 0
                    updated = c.get('updated_at') or '1970-01-01'
                    return (has_close, score, updated)

                sorted_pair = sorted([c1, c2], key=sort_key, reverse=True)
                keeper, duplicate = sorted_pair[0], sorted_pair[1]

                duplicates.append({
                    'ratio': ratio,
                    'confidence': confidence,
                    'keeper': keeper,
                    'duplicate': duplicate,
                    'domain_match': domain1 == domain2 if domain1 and domain2 else None
                })

    return sorted(duplicates, key=lambda x: -x['ratio'])


def merge_duplicate(keeper: dict, duplicate: dict):
    """Merge duplicate into keeper record."""
    keeper_id = keeper['company_id']
    dup_id = duplicate['company_id']

    # Reassign related records
    for table in ['fact_activities', 'dim_contacts', 'fact_opportunities']:
        try:
            supabase.table(table).update({'company_id': keeper_id}).eq('company_id', dup_id).execute()
        except:
            pass

    # Delete duplicate
    supabase.table('dim_companies').delete().eq('company_id', dup_id).execute()

    return True


def main():
    parser = argparse.ArgumentParser(description='Fuzzy deduplicate companies')
    parser.add_argument('--analyze', action='store_true', help='Show potential duplicates')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be merged')
    parser.add_argument('--execute', action='store_true', help='Actually merge duplicates')
    parser.add_argument('--threshold', type=float, default=0.90, help='Minimum similarity threshold')
    parser.add_argument('--limit', type=int, default=50, help='Limit results shown')

    args = parser.parse_args()

    if not any([args.analyze, args.dry_run, args.execute]):
        parser.print_help()
        return

    logger.info("Fetching companies...")
    companies = fetch_all_companies()
    logger.info(f"Fetched {len(companies)} companies")

    logger.info("Finding fuzzy duplicates...")
    duplicates = find_fuzzy_duplicates(companies, name_threshold=args.threshold)

    print(f"\n{'='*70}")
    print(f"FUZZY DEDUPLICATION ANALYSIS")
    print(f"{'='*70}")
    print(f"Total companies: {len(companies)}")
    print(f"Potential fuzzy duplicates: {len(duplicates)}")
    print(f"  HIGH confidence (>95%): {sum(1 for d in duplicates if d['confidence'] == 'HIGH')}")
    print(f"  MEDIUM confidence (>90% + same domain): {sum(1 for d in duplicates if d['confidence'] == 'MEDIUM')}")

    if args.analyze or args.dry_run:
        print(f"\nTop {args.limit} fuzzy duplicates:")
        for d in duplicates[:args.limit]:
            ratio = d['ratio']
            conf = d['confidence']
            keeper = d['keeper']
            dup = d['duplicate']
            domain_match = "✓ same domain" if d['domain_match'] else ""

            print(f"\n{ratio:.0%} [{conf}] {domain_match}")
            print(f"  KEEP: {keeper['company_name'][:50]}")
            print(f"  DEL:  {dup['company_name'][:50]}")

    if args.execute:
        # Only execute HIGH confidence duplicates by default
        high_conf = [d for d in duplicates if d['confidence'] == 'HIGH']

        print(f"\n{'='*70}")
        print(f"EXECUTING FUZZY MERGE")
        print(f"{'='*70}")
        print(f"Merging {len(high_conf)} HIGH confidence duplicates")

        confirm = input("\nType 'MERGE' to confirm: ")
        if confirm != 'MERGE':
            print("Aborted.")
            return

        merged = 0
        for d in high_conf:
            try:
                merge_duplicate(d['keeper'], d['duplicate'])
                merged += 1
                logger.info(f"Merged: {d['duplicate']['company_name'][:40]} -> {d['keeper']['company_name'][:40]}")
            except Exception as e:
                logger.error(f"Failed to merge: {e}")

        print(f"\nMerged {merged} duplicates")

        # Verify
        final = supabase.table('dim_companies').select('company_id', count='exact').execute()
        print(f"Final company count: {final.count}")


if __name__ == "__main__":
    main()
