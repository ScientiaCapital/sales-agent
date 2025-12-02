#!/usr/bin/env python3
"""
Company Phone Scraper
=====================
Scrapes company phone numbers from websites for leads in the Gold Standard list.

Usage:
    python scrape_company_phones.py --all           # Process all leads with domains
    python scrape_company_phones.py --batch 1       # Process batch 1 (0-500)
    python scrape_company_phones.py --batch 2       # Process batch 2 (500-1000)
    python scrape_company_phones.py --dry-run       # Show what would be processed

Output:
    data/final_enrichment_output/phone_enriched_TIMESTAMP.csv
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

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.website_validator import WebsiteValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 500
INPUT_FILE = "data/final_enrichment_output/leads_for_enrichment_20251129.csv"
OUTPUT_DIR = Path("data/final_enrichment_output")
DELAY_BETWEEN_REQUESTS = 0.5  # seconds


async def scrape_phone_for_domain(validator: WebsiteValidator, domain: str) -> dict:
    """
    Scrape phone number from a company website.

    Returns dict with phone info or error.
    """
    result = {
        'domain': domain,
        'company_phone': None,
        'phone_source': None,
        'scrape_success': False,
        'scrape_error': None
    }

    if not domain or pd.isna(domain):
        result['scrape_error'] = 'No domain'
        return result

    try:
        # Validate and scrape
        validation = await validator.validate(domain)

        if validation.is_valid:
            result['company_phone'] = validation.company_phone
            result['phone_source'] = validation.phone_source
            result['scrape_success'] = bool(validation.company_phone)
            if not validation.company_phone:
                result['scrape_error'] = 'No phone found on website'
        else:
            result['scrape_error'] = validation.error_message or 'Website not reachable'

    except Exception as e:
        result['scrape_error'] = str(e)
        logger.error(f"Error scraping {domain}: {e}")

    return result


async def process_leads(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    dry_run: bool = False
) -> pd.DataFrame:
    """
    Process a range of leads for phone scraping.
    """
    batch_df = df.iloc[start_idx:end_idx].copy()

    # Filter to only leads with domains
    has_domain = batch_df['domain'].notna()
    leads_with_domains = batch_df[has_domain]

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPANY PHONE SCRAPER")
    logger.info(f"{'='*60}")
    logger.info(f"Processing range: {start_idx} to {end_idx}")
    logger.info(f"Leads with domains: {len(leads_with_domains)}")

    if dry_run:
        logger.info("\n[DRY RUN] Would scrape:")
        for _, row in leads_with_domains.head(10).iterrows():
            logger.info(f"  - {row['name']}: {row['domain']}")
        if len(leads_with_domains) > 10:
            logger.info(f"  ... and {len(leads_with_domains) - 10} more")
        return pd.DataFrame()

    # Initialize validator
    validator = WebsiteValidator()

    # Process each lead
    results = []
    phones_found = 0
    errors = 0

    try:
        for idx, (i, row) in enumerate(leads_with_domains.iterrows()):
            # Progress logging
            if idx > 0 and idx % 25 == 0:
                pct = idx / len(leads_with_domains) * 100
                logger.info(f"Progress: {idx}/{len(leads_with_domains)} ({pct:.1f}%) - {phones_found} phones found")

            domain = row['domain']
            logger.info(f"[{idx+1}/{len(leads_with_domains)}] Scraping: {row['name']} ({domain})")

            # Scrape phone
            phone_result = await scrape_phone_for_domain(validator, domain)

            # Merge with original row data
            result = {
                'name': row['name'],
                'phone': row.get('phone', ''),  # Original company phone from source
                'email': row.get('email', ''),
                'domain': domain,
                'city': row.get('city', ''),
                'state': row.get('state', ''),
                'icp_score': row.get('icp_score', 0),
                'source_tag': row.get('source_tag', ''),
                **phone_result  # Add scraped phone data
            }
            results.append(result)

            if phone_result['scrape_success']:
                phones_found += 1
                logger.info(f"  ✅ Found: {phone_result['company_phone']} ({phone_result['phone_source']})")
            else:
                errors += 1
                logger.info(f"  ❌ {phone_result['scrape_error']}")

            # Rate limiting
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    finally:
        await validator.close()

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"phone_enriched_{timestamp}.csv"
    results_df.to_csv(output_file, index=False)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"SCRAPING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total processed: {len(results)}")
    logger.info(f"Phones found: {phones_found} ({phones_found/len(results)*100:.1f}%)")
    logger.info(f"Errors/No phone: {errors}")
    logger.info(f"Output saved: {output_file}")

    return results_df


async def main():
    parser = argparse.ArgumentParser(description='Scrape company phones from websites')
    parser.add_argument('--batch', type=int, choices=[1, 2, 3, 4],
                        help='Batch number to process (1=0-500, 2=500-1000, etc.)')
    parser.add_argument('--all', action='store_true', help='Process all leads with domains')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')

    args = parser.parse_args()

    if not args.batch and not args.all:
        parser.print_help()
        print("\n⚠️  Please specify --batch N or --all")
        return

    # Load leads
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    df = pd.read_csv(INPUT_FILE)
    total_leads = len(df)
    logger.info(f"Loaded {total_leads} leads from {INPUT_FILE}")

    if args.all:
        # Process all leads
        await process_leads(df, 0, total_leads, args.dry_run)
    else:
        # Process specific batch
        start_idx = (args.batch - 1) * BATCH_SIZE
        end_idx = min(args.batch * BATCH_SIZE, total_leads)
        await process_leads(df, start_idx, end_idx, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
