#!/usr/bin/env python3
"""
Hunter.io Enrichment for TOP 500 Verified Leads
================================================

This script enriches the TOP 500 leads (filtered by phone verification + ICP score)
with Hunter.io domain search to find ATL contacts and emails.

Input: TOP_500_FOR_HUNTER_*.csv (from filter_top_500_verified.py)
Output: HUNTER_ENRICHED_500_*.csv with ATL contacts + emails

Cost: ~$5 for 500 domains
Rate Limit: Hunter.io allows 25 req/sec, but we'll be gentle with 1/sec

Usage:
    python enrich_hunter_top500.py              # Full run (500 leads)
    python enrich_hunter_top500.py --test 10    # Test with 10 leads
    python enrich_hunter_top500.py --dry-run    # Preview without API calls
    python enrich_hunter_top500.py --resume     # Resume from progress file
"""

import asyncio
import pandas as pd
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.hunter_service import HunterService

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"hunter_enrichment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# Config
INPUT_DIR = Path('data/final_enrichment_output')
OUTPUT_DIR = Path('data/final_enrichment_output')

# ATL title keywords
ATL_TITLES = [
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'cto', 'chief technology', 'cfo', 'chief financial', 'coo', 'chief operating',
    'vp', 'vice president', 'svp', 'evp', 'director', 'head of',
    'manager', 'general manager', 'partner', 'principal'
]


def is_atl(position: str) -> bool:
    """Check if position is above-the-line (decision maker)"""
    if not position:
        return False
    position_lower = position.lower()
    return any(title in position_lower for title in ATL_TITLES)


async def enrich_with_hunter(hunter: HunterService, row: pd.Series) -> dict:
    """
    Enrich a single lead with Hunter.io domain search.

    Uses the company name and any ATL contact hints we already have.
    """
    domain = row.get('domain', '')
    company_name = row.get('company_name', '')

    # Start with existing data
    result = {
        'company_name': company_name,
        'domain': domain,
        'hunter_priority_score': row.get('hunter_priority_score', 0),
        'primary_phone': row.get('primary_phone', ''),
        'verified_phone_count': row.get('verified_phone_count', 0),
        'existing_contact_name': row.get('contact_1_name', ''),
        'existing_contact_title': row.get('contact_1_title', ''),
        'city': row.get('city', ''),
        'state': row.get('state', ''),
        # Hunter results
        'hunter_atl_count': 0,
        'hunter_atl_contacts_json': '[]',
        'best_atl_name': '',
        'best_atl_email': '',
        'best_atl_position': '',
        'best_atl_phone': '',
        'best_atl_linkedin': '',
        'best_atl_confidence': 0,
        'hunter_success': False,
        'hunter_error': None
    }

    if not domain or pd.isna(domain):
        result['hunter_error'] = 'No domain'
        return result

    try:
        # Hunter.io domain search - get up to 10 people
        contacts = await hunter.domain_search(domain, limit=10, atl_only=False)

        if contacts:
            atl_contacts = []
            for contact in contacts:
                # Check if ATL position
                position = contact.get('position', '') or ''
                if is_atl(position):
                    atl_contact = {
                        'name': f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                        'email': contact.get('email', ''),
                        'position': position,
                        'phone': contact.get('phone_number', ''),
                        'linkedin': contact.get('linkedin', ''),
                        'twitter': contact.get('twitter', ''),
                        'confidence': contact.get('confidence', 0),
                        'seniority': contact.get('seniority', ''),
                        'department': contact.get('department', ''),
                    }
                    atl_contacts.append(atl_contact)

            result['hunter_atl_count'] = len(atl_contacts)
            result['hunter_atl_contacts_json'] = json.dumps(atl_contacts)
            result['hunter_success'] = len(atl_contacts) > 0

            if atl_contacts:
                # Pick the best ATL (highest confidence)
                best = max(atl_contacts, key=lambda x: x['confidence'])
                result['best_atl_name'] = best['name']
                result['best_atl_email'] = best['email']
                result['best_atl_position'] = best['position']
                result['best_atl_phone'] = best['phone']
                result['best_atl_linkedin'] = best['linkedin']
                result['best_atl_confidence'] = best['confidence']
            else:
                result['hunter_error'] = 'No ATL contacts found (found BTL only)'
        else:
            result['hunter_error'] = 'No contacts returned from Hunter.io'

    except Exception as e:
        result['hunter_error'] = str(e)
        logger.error(f"Error enriching {domain}: {e}")

    return result


def find_latest_input() -> Path:
    """Find the most recent TOP_500_FOR_HUNTER file."""
    pattern = 'TOP_500_FOR_HUNTER_*.csv'
    files = list(INPUT_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} in {INPUT_DIR}")
    return max(files, key=lambda p: p.stat().st_mtime)


async def main():
    parser = argparse.ArgumentParser(description='Hunter.io enrichment for TOP 500 verified leads')
    parser.add_argument('--test', type=int, help='Only process N leads for testing')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--resume', action='store_true', help='Resume from progress file')
    parser.add_argument('--input', type=str, help='Specific input file to use')

    args = parser.parse_args()

    # Find input file
    if args.input:
        input_file = Path(args.input)
    else:
        input_file = find_latest_input()

    logger.info(f"{'='*60}")
    logger.info(f"HUNTER.IO ENRICHMENT - TOP 500 VERIFIED LEADS")
    logger.info(f"{'='*60}")
    logger.info(f"Input: {input_file}")
    logger.info(f"Log: {log_file}")

    # Load data
    df = pd.read_csv(input_file)
    logger.info(f"Loaded {len(df)} leads")

    # Test mode limit
    if args.test:
        df = df.head(args.test)
        logger.info(f"TEST MODE: Processing only {args.test} leads")

    # Resume support
    already_enriched = set()
    if args.resume:
        progress_pattern = 'hunter_progress_*.csv'
        progress_files = list(OUTPUT_DIR.glob(progress_pattern))
        if progress_files:
            latest_progress = max(progress_files, key=lambda p: p.stat().st_mtime)
            progress_df = pd.read_csv(latest_progress)
            already_enriched = set(progress_df['domain'].dropna().str.lower().str.strip())
            logger.info(f"Resuming: Found {len(already_enriched)} already enriched domains")

    # Dry run mode
    if args.dry_run:
        logger.info("\n[DRY RUN] Would process:")
        for i, row in df.head(10).iterrows():
            logger.info(f"  - {row['company_name']}: {row['domain']}")
        if len(df) > 10:
            logger.info(f"  ... and {len(df) - 10} more")
        cost = (len(df) - len(already_enriched)) * 0.01
        logger.info(f"\n[DRY RUN] Estimated cost: ${cost:.2f}")
        return

    # Initialize Hunter
    hunter = HunterService()
    if not hunter.api_key:
        logger.error("HUNTER_API_KEY not set in environment!")
        return

    # Process leads
    results = []
    success_count = 0
    error_count = 0
    skip_count = 0
    timestamp = datetime.now().strftime('%Y%m%d')
    progress_file = OUTPUT_DIR / f"hunter_progress_{timestamp}.csv"

    for idx, (i, row) in enumerate(df.iterrows()):
        domain = str(row.get('domain', '')).lower().strip()

        # Skip if already enriched
        if domain in already_enriched:
            skip_count += 1
            continue

        logger.info(f"[{idx+1}/{len(df)}] {row['company_name']} ({domain})")

        # Enrich
        result = await enrich_with_hunter(hunter, row)
        results.append(result)

        if result['hunter_success']:
            success_count += 1
            logger.info(f"  ✅ Found {result['hunter_atl_count']} ATL: {result['best_atl_name']} ({result['best_atl_email']})")
        else:
            error_count += 1
            logger.info(f"  ❌ {result.get('hunter_error', 'Unknown error')}")

        # Save progress every 25 leads
        if len(results) > 0 and len(results) % 25 == 0:
            pd.DataFrame(results).to_csv(progress_file, index=False)
            logger.info(f"  💾 Progress saved ({len(results)} leads)")

        # Rate limiting - 1 request per second
        await asyncio.sleep(1)

    # Final save
    if results:
        results_df = pd.DataFrame(results)

        # Save final output
        output_file = OUTPUT_DIR / f"HUNTER_ENRICHED_500_{timestamp}.csv"
        results_df.to_csv(output_file, index=False)
        logger.info(f"\n✅ Saved: {output_file}")

        # JSON backup
        json_file = OUTPUT_DIR / f"HUNTER_ENRICHED_500_{timestamp}.json"
        results_df.to_json(json_file, orient='records', indent=2)
        logger.info(f"✅ JSON: {json_file}")

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"HUNTER.IO ENRICHMENT COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total processed: {len(results)}")
        logger.info(f"Skipped (already enriched): {skip_count}")
        logger.info(f"Success (found ATL): {success_count} ({success_count/len(results)*100:.1f}%)")
        logger.info(f"No ATL found: {error_count}")
        logger.info(f"Estimated cost: ${len(results) * 0.01:.2f}")

        # Show top results
        if success_count > 0:
            logger.info(f"\nTOP 10 ATL CONTACTS FOUND:")
            success_df = results_df[results_df['hunter_success'] == True].head(10)
            for _, r in success_df.iterrows():
                logger.info(f"  - {r['best_atl_name']} ({r['best_atl_position']})")
                logger.info(f"    {r['company_name']} | {r['best_atl_email']}")
    else:
        logger.info("No new leads to process.")


if __name__ == '__main__':
    asyncio.run(main())
