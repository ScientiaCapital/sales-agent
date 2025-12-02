#!/usr/bin/env python3
"""
Advanced Calling List Generator
================================
Creates prioritized calling lists using sophisticated scoring:

Scoring Tiers (Priority Order):
1. SREC States (PA, NJ, NY, MA) + direct email + phone = PLATINUM
2. High-Value States (CA, TX, FL) + direct email + phone = GOLD
3. Multi-OEM certified + direct email + phone = GOLD
4. Has direct ATL email + company phone = SILVER
5. Has company phone only = BRONZE

Data Sources:
- Supabase dim_companies (state, OEM data)
- Hunter.io enriched batches (ATL contacts, emails)
- Website phone scraping (company phones)
- Team page scraping (additional contacts)

Usage:
    python create_advanced_calling_list.py --top 100 --top 500
    python create_advanced_calling_list.py --all
"""

import pandas as pd
import logging
import os
from pathlib import Path
from datetime import datetime
import argparse
from dotenv import load_dotenv
import glob

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

from supabase import create_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = Path("data/final_enrichment_output")

# SREC State Tiers (Solar Renewable Energy Credit markets)
# Tier 1: Premium SREC markets (highest $/MWh)
SREC_TIER1 = {'DC', 'NJ', 'MA', 'PA'}  # DC=$440, NJ/MA/PA premium markets

# Tier 2: Active SREC markets
SREC_TIER2 = {'MD', 'DE', 'VA', 'IL', 'OH'}  # MD=$55, VA=$45, OH=$4

# All SREC states combined
ALL_SREC_STATES = SREC_TIER1 | SREC_TIER2

# High-value large markets (no SREC but huge solar demand)
HIGH_VALUE_STATES = {'CA', 'TX', 'FL', 'NY', 'AZ', 'NC', 'CO'}

# All priority states
ALL_PRIORITY_STATES = ALL_SREC_STATES | HIGH_VALUE_STATES


def get_supabase_client():
    """Create Supabase client."""
    return create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )


def load_supabase_companies() -> pd.DataFrame:
    """Load company data from Supabase with state/OEM info."""
    logger.info("Loading company data from Supabase...")

    supabase = get_supabase_client()

    # Get all companies with relevant fields
    result = supabase.table('dim_companies').select(
        'company_id, company_name, normalized_name, domain, phone, '
        'city, state, oem_brands, oem_count, icp_score, icp_tier'
    ).execute()

    df = pd.DataFrame(result.data)
    logger.info(f"  Loaded {len(df)} companies from Supabase")

    # Log state distribution
    if 'state' in df.columns:
        srec_t1_count = df[df['state'].isin(SREC_TIER1)].shape[0]
        srec_t2_count = df[df['state'].isin(SREC_TIER2)].shape[0]
        high_value_count = df[df['state'].isin(HIGH_VALUE_STATES)].shape[0]
        logger.info(f"  SREC Tier 1 (DC/NJ/MA/PA): {srec_t1_count}")
        logger.info(f"  SREC Tier 2 (MD/DE/VA/IL/OH): {srec_t2_count}")
        logger.info(f"  High-value (CA/TX/FL/NY/AZ/NC/CO): {high_value_count}")

    return df


def load_enrichment_data() -> pd.DataFrame:
    """Load and merge all enrichment data sources."""
    logger.info("Loading enrichment data...")

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
        hunter_df = pd.DataFrame()

    # 2. Load phone scraping data
    phone_files = glob.glob(str(OUTPUT_DIR / "phone_enriched_*.csv"))
    if phone_files:
        latest_phone = max(phone_files, key=os.path.getmtime)
        phone_df = pd.read_csv(latest_phone)
        logger.info(f"  Loaded {len(phone_df)} phone records from {Path(latest_phone).name}")
    else:
        phone_df = pd.DataFrame()

    # 3. Merge Hunter + Phone data on domain
    if not hunter_df.empty and not phone_df.empty:
        # Keep phone columns from phone_df
        phone_cols = ['domain', 'company_phone', 'phone_source', 'scrape_success']
        phone_subset = phone_df[phone_cols].drop_duplicates(subset=['domain'])

        merged = hunter_df.merge(
            phone_subset,
            on='domain',
            how='left',
            suffixes=('', '_phone')
        )
        logger.info(f"  Merged enrichment data: {len(merged)} records")
    elif not hunter_df.empty:
        merged = hunter_df
    elif not phone_df.empty:
        merged = phone_df
    else:
        merged = pd.DataFrame()

    return merged


def calculate_advanced_score(row: pd.Series) -> dict:
    """
    Calculate advanced lead score with tier assignment.

    Scoring Priority:
    1. SREC Tier 1 (DC/NJ/MA/PA) = +300 pts (premium SREC markets)
    2. SREC Tier 2 (MD/DE/VA/IL/OH) = +200 pts (active SREC markets)
    3. High-Value States (CA/TX/FL/NY/AZ/NC/CO) = +150 pts (large solar markets)
    4. Direct ATL email = +100 pts
    5. Company phone = +75 pts
    6. Unique ATL direct phone = +50 pts
    7. Multi-OEM certified = +40 pts
    8. ATL contact name = +30 pts
    9. Has domain = +20 pts
    10. ICP score bonus (0-50 pts)

    Returns dict with score, tier, and score breakdown.
    """
    score = 0
    breakdown = []

    # 1. State scoring (SREC tiers + high-value markets)
    state = str(row.get('state', '')).upper().strip()
    if state in SREC_TIER1:
        score += 300
        breakdown.append(f"+300 SREC Tier 1 ({state})")
    elif state in SREC_TIER2:
        score += 200
        breakdown.append(f"+200 SREC Tier 2 ({state})")
    elif state in HIGH_VALUE_STATES:
        score += 150
        breakdown.append(f"+150 high-value state ({state})")
    elif state:
        score += 25
        breakdown.append(f"+25 other state ({state})")

    # 2. Direct ATL email (+100)
    atl_email = row.get('best_atl_email', '')
    if pd.notna(atl_email) and atl_email and '@' in str(atl_email):
        score += 100
        breakdown.append("+100 direct ATL email")

    # 3. Company phone (+75)
    company_phone = row.get('company_phone', '')
    if pd.notna(company_phone) and company_phone:
        score += 75
        breakdown.append("+75 company phone")

    # 4. ATL direct phone different from company (+50)
    atl_phone = row.get('best_atl_phone', '')
    if pd.notna(atl_phone) and atl_phone:
        atl_clean = ''.join(filter(str.isdigit, str(atl_phone)))
        company_clean = ''.join(filter(str.isdigit, str(company_phone))) if company_phone else ''
        if atl_clean and atl_clean != company_clean:
            score += 50
            breakdown.append("+50 unique ATL direct phone")

    # 5. Multi-OEM certified (+40)
    oem_count = row.get('oem_count', 0) or 0
    if oem_count > 1:
        score += 40
        breakdown.append(f"+40 multi-OEM ({oem_count} brands)")
    elif oem_count == 1:
        score += 20
        breakdown.append("+20 single OEM")

    # 6. Has ATL name (+30)
    atl_name = row.get('best_atl_name', '')
    if pd.notna(atl_name) and atl_name:
        score += 30
        breakdown.append("+30 ATL contact name")

    # 7. Has domain (+20)
    domain = row.get('domain', '')
    if pd.notna(domain) and domain:
        score += 20
        breakdown.append("+20 has domain")

    # 8. ICP score bonus (0-100 scaled to 0-50)
    icp_score = row.get('icp_score', 0) or 0
    if icp_score > 0:
        icp_bonus = int(icp_score * 0.5)
        score += icp_bonus
        breakdown.append(f"+{icp_bonus} ICP score ({icp_score})")

    # Determine tier based on state + contact quality
    has_email = pd.notna(atl_email) and atl_email and '@' in str(atl_email)
    has_phone = pd.notna(company_phone) and company_phone

    # PLATINUM: SREC Tier 1 state + email + phone (highest value)
    if state in SREC_TIER1 and has_email and has_phone:
        tier = "PLATINUM"
    # GOLD: SREC Tier 2 OR high-value state + email + phone
    elif (state in SREC_TIER2 or state in HIGH_VALUE_STATES) and has_email and has_phone:
        tier = "GOLD"
    # GOLD: Multi-OEM anywhere + email + phone
    elif oem_count > 1 and has_email and has_phone:
        tier = "GOLD"
    # SILVER: Any state with email + phone
    elif has_email and has_phone:
        tier = "SILVER"
    # BRONZE: Has phone (can call but no email)
    elif has_phone:
        tier = "BRONZE"
    # PROSPECT: Needs more enrichment
    else:
        tier = "PROSPECT"

    return {
        'advanced_score': score,
        'tier': tier,
        'score_breakdown': ' | '.join(breakdown)
    }


def merge_with_supabase(enrichment_df: pd.DataFrame, supabase_df: pd.DataFrame) -> pd.DataFrame:
    """Merge enrichment data with Supabase company data."""
    logger.info("Merging enrichment data with Supabase...")

    if enrichment_df.empty:
        return supabase_df

    if supabase_df.empty:
        return enrichment_df

    # Merge on domain
    merged = enrichment_df.merge(
        supabase_df[['domain', 'state', 'city', 'oem_count', 'oem_brands', 'company_id']],
        on='domain',
        how='left',
        suffixes=('', '_supabase')
    )

    # Fill in state from supabase if missing
    if 'state_supabase' in merged.columns:
        merged['state'] = merged['state'].fillna(merged['state_supabase'])
        merged.drop(columns=['state_supabase'], inplace=True, errors='ignore')

    if 'city_supabase' in merged.columns:
        merged['city'] = merged['city'].fillna(merged['city_supabase'])
        merged.drop(columns=['city_supabase'], inplace=True, errors='ignore')

    logger.info(f"  Merged: {len(merged)} records with state/OEM data")

    return merged


def generate_advanced_list(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Generate prioritized calling list with advanced scoring."""
    logger.info(f"\nGenerating TOP {top_n} advanced calling list...")

    # Calculate advanced scores
    df = df.copy()
    score_results = df.apply(calculate_advanced_score, axis=1, result_type='expand')
    df = pd.concat([df, score_results], axis=1)

    # Sort by advanced score (descending)
    df_sorted = df.sort_values('advanced_score', ascending=False)

    # Take top N
    top_leads = df_sorted.head(top_n)

    # Select output columns
    output_columns = [
        'name',
        'tier',
        'advanced_score',
        'best_atl_name',
        'best_atl_position',
        'best_atl_email',
        'best_atl_phone',
        'company_phone',
        'phone_source',
        'domain',
        'city',
        'state',
        'oem_count',
        'oem_brands',
        'icp_score',
        'source_tag',
        'score_breakdown'
    ]

    # Only include columns that exist
    available_columns = [c for c in output_columns if c in top_leads.columns]
    result = top_leads[available_columns].copy()
    result = result.fillna('')

    # Stats
    tier_counts = result['tier'].value_counts()
    logger.info(f"  Total leads: {len(result)}")
    logger.info(f"  Tier distribution:")
    for tier, count in tier_counts.items():
        logger.info(f"    {tier}: {count}")

    has_email = (result['best_atl_email'] != '').sum()
    has_phone = (result['company_phone'] != '').sum()
    srec_t1_count = result[result['state'].isin(SREC_TIER1)].shape[0]
    srec_t2_count = result[result['state'].isin(SREC_TIER2)].shape[0]
    high_value_count = result[result['state'].isin(HIGH_VALUE_STATES)].shape[0]

    logger.info(f"  With ATL email: {has_email}")
    logger.info(f"  With company phone: {has_phone}")
    logger.info(f"  SREC Tier 1 (DC/NJ/MA/PA): {srec_t1_count}")
    logger.info(f"  SREC Tier 2 (MD/DE/VA/IL/OH): {srec_t2_count}")
    logger.info(f"  High-Value (CA/TX/FL/NY/AZ/NC/CO): {high_value_count}")
    logger.info(f"  Score range: {result['advanced_score'].min()} - {result['advanced_score'].max()}")

    return result


def main():
    parser = argparse.ArgumentParser(description='Generate advanced prioritized calling lists')
    parser.add_argument('--top', type=int, action='append',
                        help='Generate TOP N list (can specify multiple)')
    parser.add_argument('--all', action='store_true',
                        help='Generate standard lists (100, 500)')

    args = parser.parse_args()

    if not args.top and not args.all:
        parser.print_help()
        print("\n  Please specify --top N or --all")
        return

    # Determine which lists to generate
    tops = args.top if args.top else []
    if args.all:
        tops.extend([100, 500])
    tops = sorted(set(tops))

    # Load all data sources
    supabase_df = load_supabase_companies()
    enrichment_df = load_enrichment_data()

    # Merge data
    merged_df = merge_with_supabase(enrichment_df, supabase_df)

    if merged_df.empty:
        logger.error("No data to process!")
        return

    # Generate each list
    timestamp = datetime.now().strftime('%Y%m%d')

    for top_n in tops:
        if top_n > len(merged_df):
            logger.warning(f"Requested TOP {top_n} but only {len(merged_df)} leads available")
            top_n = len(merged_df)

        calling_list = generate_advanced_list(merged_df, top_n)

        # Save
        output_file = OUTPUT_DIR / f"ADVANCED_TOP_{top_n}_{timestamp}.csv"
        calling_list.to_csv(output_file, index=False)
        logger.info(f"  Saved: {output_file}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("ADVANCED CALLING LISTS GENERATED")
    logger.info(f"{'='*60}")

    for top_n in tops:
        output_file = OUTPUT_DIR / f"ADVANCED_TOP_{top_n}_{timestamp}.csv"
        if output_file.exists():
            df = pd.read_csv(output_file)
            platinum = len(df[df['tier'] == 'PLATINUM'])
            gold = len(df[df['tier'] == 'GOLD'])
            silver = len(df[df['tier'] == 'SILVER'])
            logger.info(f"TOP {top_n}: PLATINUM {platinum} | GOLD {gold} | SILVER {silver}")


if __name__ == "__main__":
    main()
