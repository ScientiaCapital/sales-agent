#!/usr/bin/env python3
"""
Final Calling List Generator
============================
Merges all enrichment data sources and generates prioritized calling lists.

Data Sources:
- Hunter.io enriched batches (ATL contacts + emails)
- Website phone scraping (company phones)
- Original lead data (ICP scores)

Output:
- TOP_100_CALLING_LIST_YYYYMMDD.csv
- TOP_500_CALLING_LIST_YYYYMMDD.csv

Usage:
    python create_final_calling_list.py --top 100 --top 500
    python create_final_calling_list.py --all  # Generate all standard lists
"""

import pandas as pd
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
import glob
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = Path("data/final_enrichment_output")


def find_latest_file(pattern: str) -> str:
    """Find the most recent file matching pattern."""
    files = glob.glob(str(OUTPUT_DIR / pattern))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only for comparison."""
    if not phone or pd.isna(phone):
        return ""
    return re.sub(r'\D', '', str(phone))


def calculate_lead_score(row: pd.Series) -> int:
    """
    Calculate lead score for prioritization.

    Scoring:
    +100 pts: Has unique direct phone (ATL phone ≠ company phone)
    +50 pts: Has verified ATL email
    +30 pts: Has company phone
    +20 pts: Has company domain
    + ICP score (0-100)
    """
    score = 0

    # Base ICP score
    icp_score = row.get('icp_score', 0)
    if pd.notna(icp_score):
        score += int(icp_score)

    # Has domain (+20)
    domain = row.get('domain', '')
    if pd.notna(domain) and domain:
        score += 20

    # Has company phone (+30)
    company_phone = normalize_phone(row.get('company_phone', ''))
    if company_phone:
        score += 30

    # Has ATL email (+50)
    atl_email = row.get('best_atl_email', '')
    if pd.notna(atl_email) and atl_email and '@' in str(atl_email):
        score += 50

    # Has unique direct phone (+100)
    # ATL contact's phone that is different from company main line
    atl_phone = normalize_phone(row.get('best_atl_phone', ''))
    if atl_phone and atl_phone != company_phone:
        score += 100

    return score


def load_and_merge_data() -> pd.DataFrame:
    """
    Load and merge all enrichment data sources.

    Returns:
        DataFrame with merged data from all sources
    """
    logger.info("Loading enrichment data sources...")

    # 1. Load Hunter.io enriched batches
    hunter_files = glob.glob(str(OUTPUT_DIR / "enriched_batch_*.csv"))
    hunter_data = []
    for f in sorted(hunter_files):
        df = pd.read_csv(f)
        logger.info(f"  Loaded {len(df)} leads from {Path(f).name}")
        hunter_data.append(df)

    if hunter_data:
        hunter_df = pd.concat(hunter_data, ignore_index=True)
        logger.info(f"  Total Hunter.io records: {len(hunter_df)}")
    else:
        logger.warning("No Hunter.io enriched files found!")
        hunter_df = pd.DataFrame()

    # 2. Load phone scraping data
    phone_file = find_latest_file("phone_enriched_*.csv")
    if phone_file:
        phone_df = pd.read_csv(phone_file)
        logger.info(f"  Loaded {len(phone_df)} phone records from {Path(phone_file).name}")
    else:
        logger.info("  No phone scraping data found (will use Hunter.io data only)")
        phone_df = pd.DataFrame()

    # 3. Merge data
    if not hunter_df.empty and not phone_df.empty:
        # Merge on domain (or name as fallback)
        merged = hunter_df.merge(
            phone_df[['domain', 'company_phone', 'phone_source', 'scrape_success']],
            on='domain',
            how='left',
            suffixes=('', '_scraped')
        )
        logger.info(f"  Merged: {len(merged)} records")
    elif not hunter_df.empty:
        merged = hunter_df
        merged['company_phone'] = None
        merged['phone_source'] = None
    elif not phone_df.empty:
        merged = phone_df
    else:
        logger.error("No data files found!")
        return pd.DataFrame()

    return merged


def generate_calling_list(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """
    Generate a prioritized calling list.

    Args:
        df: Merged enrichment data
        top_n: Number of leads to include

    Returns:
        DataFrame with top N leads, scored and sorted
    """
    logger.info(f"\nGenerating TOP {top_n} calling list...")

    # Calculate scores
    df = df.copy()
    df['lead_score'] = df.apply(calculate_lead_score, axis=1)

    # Sort by score (descending)
    df_sorted = df.sort_values('lead_score', ascending=False)

    # Take top N
    top_leads = df_sorted.head(top_n)

    # Select and rename columns for output
    output_columns = [
        'name',
        'best_atl_name',
        'best_atl_position',
        'best_atl_email',
        'best_atl_phone',
        'company_phone',
        'phone',  # Original phone from source
        'domain',
        'city',
        'state',
        'icp_score',
        'lead_score',
        'source_tag',
        'enrichment_success',
        'phone_source'
    ]

    # Only include columns that exist
    available_columns = [c for c in output_columns if c in top_leads.columns]
    result = top_leads[available_columns].copy()

    # Clean up display
    result = result.fillna('')

    # Stats
    has_atl_email = (result['best_atl_email'] != '').sum() if 'best_atl_email' in result.columns else 0
    has_company_phone = (result['company_phone'] != '').sum() if 'company_phone' in result.columns else 0
    has_atl_phone = (result['best_atl_phone'] != '').sum() if 'best_atl_phone' in result.columns else 0

    logger.info(f"  Total leads: {len(result)}")
    logger.info(f"  With ATL email: {has_atl_email}")
    logger.info(f"  With company phone: {has_company_phone}")
    logger.info(f"  With ATL direct phone: {has_atl_phone}")
    logger.info(f"  Score range: {result['lead_score'].min()} - {result['lead_score'].max()}")

    return result


def main():
    parser = argparse.ArgumentParser(description='Generate prioritized calling lists')
    parser.add_argument('--top', type=int, action='append',
                        help='Generate TOP N list (can specify multiple)')
    parser.add_argument('--all', action='store_true',
                        help='Generate standard lists (100, 500)')

    args = parser.parse_args()

    if not args.top and not args.all:
        parser.print_help()
        print("\n⚠️  Please specify --top N or --all")
        return

    # Determine which lists to generate
    tops = args.top if args.top else []
    if args.all:
        tops.extend([100, 500])
    tops = sorted(set(tops))  # Deduplicate

    # Load and merge data
    merged_df = load_and_merge_data()
    if merged_df.empty:
        logger.error("No data to process!")
        return

    # Generate each list
    timestamp = datetime.now().strftime('%Y%m%d')

    for top_n in tops:
        if top_n > len(merged_df):
            logger.warning(f"Requested TOP {top_n} but only {len(merged_df)} leads available")
            top_n = len(merged_df)

        calling_list = generate_calling_list(merged_df, top_n)

        # Save
        output_file = OUTPUT_DIR / f"TOP_{top_n}_CALLING_LIST_{timestamp}.csv"
        calling_list.to_csv(output_file, index=False)
        logger.info(f"  ✅ Saved: {output_file}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("CALLING LISTS GENERATED")
    logger.info(f"{'='*60}")
    for top_n in tops:
        output_file = OUTPUT_DIR / f"TOP_{top_n}_CALLING_LIST_{timestamp}.csv"
        if output_file.exists():
            df = pd.read_csv(output_file)
            hot = len(df[(df.get('best_atl_phone', '') != '') & (df.get('best_atl_email', '') != '')])
            warm = len(df[(df.get('best_atl_email', '') != '') & (df.get('best_atl_phone', '') == '')])
            logger.info(f"TOP {top_n}: 🔥 {hot} HOT | 🌡️ {warm} WARM")


if __name__ == "__main__":
    main()
