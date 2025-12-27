#!/usr/bin/env python3
"""
Gold Standard Batch Enrichment Script
======================================
Enriches leads via Hunter.io domain search in batches to avoid rate limits.

Usage:
    python enrich_gold_standard_batch.py --batch 1  # Process leads 0-500
    python enrich_gold_standard_batch.py --batch 2  # Process leads 500-1000
    python enrich_gold_standard_batch.py --batch 3  # Process leads 1000-1500
    python enrich_gold_standard_batch.py --batch 4  # Process leads 1500-2000
    python enrich_gold_standard_batch.py --all      # Process all (be careful of rate limits!)

Cost: ~$0.01 per domain searched
Rate Limit: Hunter.io has hourly limits, hence the batching
"""

import asyncio
import pandas as pd
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
import time
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(Path(__file__).parent.parent / '.env')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.hunter_service import HunterService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Batch configuration
BATCH_SIZE = 500
INPUT_FILE = "data/final_enrichment_output/leads_for_enrichment_20251129.csv"
OUTPUT_DIR = Path("data/final_enrichment_output")

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


async def enrich_lead(hunter: HunterService, row: pd.Series) -> dict:
    """
    Enrich a single lead with Hunter.io domain search.

    Returns enriched data dict with ATL contacts found.
    """
    result = {
        'name': row['name'],
        'phone': row.get('phone', ''),
        'original_email': row.get('email', ''),
        'domain': row.get('domain', ''),
        'city': row.get('city', ''),
        'state': row.get('state', ''),
        'icp_score': row.get('icp_score', 0),
        'source_tag': row.get('source_tag', ''),
        'atl_contacts': [],
        'enrichment_success': False,
        'enrichment_error': None
    }

    domain = row.get('domain', '')
    if not domain or pd.isna(domain):
        result['enrichment_error'] = 'No domain available'
        return result

    try:
        # Hunter.io domain search
        contacts = await hunter.domain_search(domain, limit=10, atl_only=True)

        if contacts:
            atl_contacts = []
            for contact in contacts:
                if is_atl(contact.get('position', '')):
                    atl_contacts.append({
                        'name': f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                        'email': contact.get('email', ''),
                        'position': contact.get('position', ''),
                        'phone': contact.get('phone_number', ''),  # Hunter returns phone_number field
                        'linkedin': contact.get('linkedin', ''),
                        'twitter': contact.get('twitter', ''),
                        'confidence': contact.get('confidence', 0),
                        'seniority': contact.get('seniority', ''),
                        'department': contact.get('department', ''),
                    })

            result['atl_contacts'] = atl_contacts
            result['enrichment_success'] = len(atl_contacts) > 0

            if atl_contacts:
                # Use best ATL contact
                best_atl = max(atl_contacts, key=lambda x: x['confidence'])
                result['best_atl_name'] = best_atl['name']
                result['best_atl_email'] = best_atl['email']
                result['best_atl_position'] = best_atl['position']
                result['best_atl_phone'] = best_atl['phone']
                result['atl_count'] = len(atl_contacts)
            else:
                result['enrichment_error'] = 'No ATL contacts found'
        else:
            result['enrichment_error'] = 'No contacts returned from Hunter.io'

    except Exception as e:
        result['enrichment_error'] = str(e)
        logger.error(f"Error enriching {domain}: {e}")

    return result


async def process_batch(batch_num: int, dry_run: bool = False) -> pd.DataFrame:
    """
    Process a batch of leads through Hunter.io enrichment.

    Args:
        batch_num: Batch number (1-4)
        dry_run: If True, just show what would be processed without calling APIs
    """
    # Load leads
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file not found: {INPUT_FILE}")
        return pd.DataFrame()

    df = pd.read_csv(INPUT_FILE)
    total_leads = len(df)

    # Calculate batch range
    start_idx = (batch_num - 1) * BATCH_SIZE
    end_idx = min(batch_num * BATCH_SIZE, total_leads)

    logger.info(f"\n{'='*60}")
    logger.info(f"GOLD STANDARD BATCH ENRICHMENT - Batch {batch_num}")
    logger.info(f"{'='*60}")
    logger.info(f"Total leads in file: {total_leads}")
    logger.info(f"Processing: {start_idx} to {end_idx} (batch size: {end_idx - start_idx})")

    # Get batch
    batch_df = df.iloc[start_idx:end_idx].copy()

    # Count leads with domains
    has_domain = batch_df['domain'].notna().sum()
    logger.info(f"Leads with domains: {has_domain} ({has_domain/(end_idx-start_idx)*100:.1f}%)")

    if dry_run:
        logger.info("\n[DRY RUN] Would process the following leads:")
        for i, row in batch_df.head(10).iterrows():
            logger.info(f"  - {row['name']}: {row.get('domain', 'NO DOMAIN')}")
        logger.info(f"  ... and {len(batch_df) - 10} more")
        estimated_cost = has_domain * 0.01
        logger.info(f"\n[DRY RUN] Estimated cost: ${estimated_cost:.2f}")
        return pd.DataFrame()

    # Initialize Hunter service
    hunter = HunterService()
    if not hunter.api_key:
        logger.error("HUNTER_API_KEY not set in environment")
        return pd.DataFrame()

    # Process each lead
    results = []
    enriched_count = 0
    error_count = 0

    for idx, (i, row) in enumerate(batch_df.iterrows()):
        if pd.isna(row.get('domain')):
            results.append({
                'name': row['name'],
                'phone': row.get('phone', ''),
                'email': row.get('email', ''),
                'domain': '',
                'enrichment_error': 'No domain',
                'enrichment_success': False
            })
            continue

        # Rate limiting - be nice to Hunter.io
        if idx > 0 and idx % 50 == 0:
            logger.info(f"Progress: {idx}/{len(batch_df)} ({idx/len(batch_df)*100:.1f}%) - Pausing 5s for rate limit...")
            await asyncio.sleep(5)

        logger.info(f"[{idx+1}/{len(batch_df)}] Enriching: {row['name']} ({row['domain']})")

        result = await enrich_lead(hunter, row)
        results.append(result)

        if result['enrichment_success']:
            enriched_count += 1
            logger.info(f"  ✅ Found {result.get('atl_count', 0)} ATL contacts")
        else:
            error_count += 1
            logger.info(f"  ❌ {result.get('enrichment_error', 'Unknown error')}")

        # Small delay between requests
        await asyncio.sleep(0.5)

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"enriched_batch_{batch_num}_{timestamp}.csv"
    results_df.to_csv(output_file, index=False)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH {batch_num} COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Processed: {len(batch_df)}")
    logger.info(f"Successfully enriched: {enriched_count} ({enriched_count/len(batch_df)*100:.1f}%)")
    logger.info(f"Errors/No ATL: {error_count}")
    logger.info(f"Output saved: {output_file}")
    logger.info(f"Estimated cost: ${has_domain * 0.01:.2f}")

    return results_df


async def main():
    parser = argparse.ArgumentParser(description='Enrich Gold Standard leads via Hunter.io')
    parser.add_argument('--batch', type=int, choices=[1, 2, 3, 4],
                        help='Batch number to process (1=0-500, 2=500-1000, etc.)')
    parser.add_argument('--all', action='store_true', help='Process all batches (be careful of rate limits!)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without calling APIs')

    args = parser.parse_args()

    if not args.batch and not args.all:
        parser.print_help()
        print("\n⚠️  Please specify --batch N or --all")
        return

    if args.all:
        logger.warning("Processing ALL batches - this will take ~2 hours and cost ~$20")
        for batch in [1, 2, 3, 4]:
            await process_batch(batch, args.dry_run)
            if batch < 4 and not args.dry_run:
                logger.info("\n⏰ Waiting 30 minutes before next batch to respect rate limits...")
                await asyncio.sleep(30 * 60)
    else:
        await process_batch(args.batch, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
