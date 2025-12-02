#!/usr/bin/env python3
"""
Top ICP Lead Filter for Coperniq
=================================
Filters and ranks leads based on Coperniq's Ideal Customer Profile BEFORE
spending money on Hunter.io enrichment.

ICP Criteria (Priority Order):
1. SREC Tier 1 States (DC, NJ, MA, PA) - Premium solar markets
2. SREC Tier 2 States (MD, DE, VA, IL, OH) - Active solar markets
3. High-Value States (CA, TX, FL, NY, AZ, NC, CO) - Large solar demand
4. Multi-OEM Certified (2+ brands) - Established dealers
5. Has Website/Domain - Can be verified and enriched
6. Existing ICP Score from qualification - Data quality signal

Output:
- TOP_1000_ICP_FILTERED_<date>.csv - Best leads for enrichment
- ICP_ANALYSIS_REPORT_<date>.txt - Summary statistics

Usage:
    python filter_top_icp_leads.py --top 1000
    python filter_top_icp_leads.py --top 2000 --report
    python filter_top_icp_leads.py --analyze  # Just show stats, no file
"""

import pandas as pd
import logging
import os
from pathlib import Path
from datetime import datetime
import argparse
from dotenv import load_dotenv

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

# ============================================================================
# COPERNIQ ICP CRITERIA
# ============================================================================

# SREC State Tiers (Solar Renewable Energy Credit markets)
# Tier 1: Premium SREC markets - highest $/MWh, best margins
SREC_TIER1 = {'DC', 'NJ', 'MA', 'PA'}

# Tier 2: Active SREC markets - good incentives
SREC_TIER2 = {'MD', 'DE', 'VA', 'IL', 'OH'}

# All SREC states
ALL_SREC_STATES = SREC_TIER1 | SREC_TIER2

# High-value large markets (no SREC but huge solar demand)
HIGH_VALUE_STATES = {'CA', 'TX', 'FL', 'NY', 'AZ', 'NC', 'CO'}

# All priority states
ALL_PRIORITY_STATES = ALL_SREC_STATES | HIGH_VALUE_STATES

# ============================================================================
# SCORING WEIGHTS
# ============================================================================

SCORING_CONFIG = {
    # State-based scoring (location is king for solar)
    'srec_tier1': 300,      # DC/NJ/MA/PA - premium markets
    'srec_tier2': 200,      # MD/DE/VA/IL/OH - active markets
    'high_value_state': 150, # CA/TX/FL/NY/AZ/NC/CO
    'other_state': 25,       # Any other US state

    # Business signals
    'has_domain': 50,        # Can be enriched via website
    'multi_oem': 40,         # 2+ OEM certifications
    'single_oem': 20,        # 1 OEM certification

    # Existing data quality
    'has_phone': 30,         # Already have a phone number
    'has_city': 10,          # Location specificity

    # ICP score bonus (from prior qualification)
    'icp_multiplier': 0.5,   # Multiply existing ICP score by this
}


def get_supabase_client():
    """Create Supabase client."""
    return create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )


def load_all_companies() -> pd.DataFrame:
    """Load all companies from Supabase dim_companies."""
    logger.info("Loading all companies from Supabase...")

    supabase = get_supabase_client()

    # Fetch all companies (paginated if needed)
    all_data = []
    page_size = 1000
    offset = 0

    while True:
        result = supabase.table('dim_companies').select(
            'company_id, company_name, normalized_name, domain, phone, '
            'city, state, oem_brands, oem_count, icp_score, icp_tier'
        ).range(offset, offset + page_size - 1).execute()

        if not result.data:
            break

        all_data.extend(result.data)
        offset += page_size

        if len(result.data) < page_size:
            break

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} total companies from Supabase")

    return df


def calculate_icp_score(row: pd.Series) -> dict:
    """
    Calculate ICP score for a lead based on Coperniq criteria.

    Returns dict with score, tier, and breakdown.
    """
    score = 0
    breakdown = []

    # 1. State-based scoring (MOST IMPORTANT)
    state = str(row.get('state', '') or '').upper().strip()

    if state in SREC_TIER1:
        score += SCORING_CONFIG['srec_tier1']
        breakdown.append(f"+{SCORING_CONFIG['srec_tier1']} SREC Tier1 ({state})")
    elif state in SREC_TIER2:
        score += SCORING_CONFIG['srec_tier2']
        breakdown.append(f"+{SCORING_CONFIG['srec_tier2']} SREC Tier2 ({state})")
    elif state in HIGH_VALUE_STATES:
        score += SCORING_CONFIG['high_value_state']
        breakdown.append(f"+{SCORING_CONFIG['high_value_state']} High-Value ({state})")
    elif state and len(state) == 2:  # Valid 2-letter state code
        score += SCORING_CONFIG['other_state']
        breakdown.append(f"+{SCORING_CONFIG['other_state']} Other ({state})")

    # 2. Has domain (can be enriched)
    domain = row.get('domain', '')
    if domain and pd.notna(domain) and domain.strip():
        score += SCORING_CONFIG['has_domain']
        breakdown.append(f"+{SCORING_CONFIG['has_domain']} has domain")

    # 3. OEM certifications
    oem_count = row.get('oem_count', 0) or 0
    if oem_count > 1:
        score += SCORING_CONFIG['multi_oem']
        breakdown.append(f"+{SCORING_CONFIG['multi_oem']} multi-OEM ({oem_count})")
    elif oem_count == 1:
        score += SCORING_CONFIG['single_oem']
        breakdown.append(f"+{SCORING_CONFIG['single_oem']} single-OEM")

    # 4. Already has phone
    phone = row.get('phone', '')
    if phone and pd.notna(phone) and str(phone).strip():
        score += SCORING_CONFIG['has_phone']
        breakdown.append(f"+{SCORING_CONFIG['has_phone']} has phone")

    # 5. Has city (more specific location)
    city = row.get('city', '')
    if city and pd.notna(city) and city.strip():
        score += SCORING_CONFIG['has_city']
        breakdown.append(f"+{SCORING_CONFIG['has_city']} has city")

    # 6. Existing ICP score bonus
    existing_icp = row.get('icp_score', 0) or 0
    if existing_icp > 0:
        bonus = int(existing_icp * SCORING_CONFIG['icp_multiplier'])
        score += bonus
        breakdown.append(f"+{bonus} existing ICP ({existing_icp})")

    # Determine tier
    if state in SREC_TIER1:
        tier = "PLATINUM"
    elif state in SREC_TIER2:
        tier = "GOLD"
    elif state in HIGH_VALUE_STATES:
        tier = "SILVER"
    elif domain and pd.notna(domain):
        tier = "BRONZE"
    else:
        tier = "PROSPECT"

    return {
        'filter_score': score,
        'filter_tier': tier,
        'score_breakdown': ' | '.join(breakdown) if breakdown else 'No criteria matched'
    }


def filter_and_rank_leads(df: pd.DataFrame, top_n: int = 1000) -> pd.DataFrame:
    """
    Filter and rank leads by ICP score.
    """
    logger.info(f"\nFiltering to TOP {top_n} ICP leads...")

    # Calculate scores for all
    df = df.copy()
    score_results = df.apply(calculate_icp_score, axis=1, result_type='expand')
    df = pd.concat([df, score_results], axis=1)

    # Filter out leads without domains (can't enrich)
    has_domain = df['domain'].notna() & (df['domain'] != '')
    df_with_domain = df[has_domain].copy()
    logger.info(f"Companies with domain: {len(df_with_domain)} / {len(df)}")

    # Sort by filter_score descending
    df_sorted = df_with_domain.sort_values('filter_score', ascending=False)

    # Take top N
    top_leads = df_sorted.head(top_n).copy()

    # Select columns for output
    output_columns = [
        'company_name',
        'filter_tier',
        'filter_score',
        'domain',
        'phone',
        'city',
        'state',
        'oem_count',
        'oem_brands',
        'icp_score',
        'icp_tier',
        'score_breakdown'
    ]

    available_columns = [c for c in output_columns if c in top_leads.columns]
    result = top_leads[available_columns].reset_index(drop=True)

    return result


def generate_analysis_report(df: pd.DataFrame, top_leads: pd.DataFrame) -> str:
    """Generate detailed analysis report."""

    # Calculate scores for full dataset
    df_scored = df.copy()
    score_results = df_scored.apply(calculate_icp_score, axis=1, result_type='expand')
    df_scored = pd.concat([df_scored, score_results], axis=1)

    report = []
    report.append("=" * 70)
    report.append("COPERNIQ ICP LEAD ANALYSIS REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)

    # Overall stats
    report.append("\n📊 OVERALL DATABASE STATS")
    report.append("-" * 40)
    report.append(f"Total companies in Supabase: {len(df):,}")

    has_domain = df['domain'].notna() & (df['domain'] != '')
    report.append(f"With domain (enrichable): {has_domain.sum():,} ({has_domain.sum()/len(df)*100:.1f}%)")

    has_state = df['state'].notna() & (df['state'] != '')
    report.append(f"With state data: {has_state.sum():,} ({has_state.sum()/len(df)*100:.1f}%)")

    has_phone = df['phone'].notna() & (df['phone'] != '')
    report.append(f"With phone number: {has_phone.sum():,} ({has_phone.sum()/len(df)*100:.1f}%)")

    # State distribution in full dataset
    report.append("\n📍 STATE DISTRIBUTION (Full Dataset)")
    report.append("-" * 40)

    df_with_state = df[has_state].copy()
    state_counts = df_with_state['state'].value_counts()

    srec_t1_count = df_with_state[df_with_state['state'].isin(SREC_TIER1)].shape[0]
    srec_t2_count = df_with_state[df_with_state['state'].isin(SREC_TIER2)].shape[0]
    high_value_count = df_with_state[df_with_state['state'].isin(HIGH_VALUE_STATES)].shape[0]
    other_count = len(df_with_state) - srec_t1_count - srec_t2_count - high_value_count

    report.append(f"🥇 SREC Tier 1 (DC/NJ/MA/PA): {srec_t1_count:,}")
    for state in sorted(SREC_TIER1):
        count = state_counts.get(state, 0)
        if count > 0:
            report.append(f"     {state}: {count:,}")

    report.append(f"🥈 SREC Tier 2 (MD/DE/VA/IL/OH): {srec_t2_count:,}")
    for state in sorted(SREC_TIER2):
        count = state_counts.get(state, 0)
        if count > 0:
            report.append(f"     {state}: {count:,}")

    report.append(f"🥉 High-Value (CA/TX/FL/NY/AZ/NC/CO): {high_value_count:,}")
    for state in sorted(HIGH_VALUE_STATES):
        count = state_counts.get(state, 0)
        if count > 0:
            report.append(f"     {state}: {count:,}")

    report.append(f"⬜ Other States: {other_count:,}")

    # Top leads analysis
    report.append(f"\n🎯 TOP {len(top_leads)} ICP LEADS ANALYSIS")
    report.append("-" * 40)

    tier_counts = top_leads['filter_tier'].value_counts()
    report.append("Tier Distribution:")
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'PROSPECT']:
        count = tier_counts.get(tier, 0)
        pct = count / len(top_leads) * 100
        report.append(f"  {tier}: {count:,} ({pct:.1f}%)")

    # State breakdown in top leads
    report.append("\nState Distribution in Top Leads:")
    top_state_counts = top_leads['state'].value_counts().head(15)
    for state, count in top_state_counts.items():
        tier_label = ""
        if state in SREC_TIER1:
            tier_label = " [SREC T1]"
        elif state in SREC_TIER2:
            tier_label = " [SREC T2]"
        elif state in HIGH_VALUE_STATES:
            tier_label = " [HIGH]"
        report.append(f"  {state}: {count:,}{tier_label}")

    # Score distribution
    report.append("\nScore Distribution:")
    report.append(f"  Min: {top_leads['filter_score'].min()}")
    report.append(f"  Max: {top_leads['filter_score'].max()}")
    report.append(f"  Mean: {top_leads['filter_score'].mean():.1f}")
    report.append(f"  Median: {top_leads['filter_score'].median():.1f}")

    # Enrichment potential
    has_domain_top = (top_leads['domain'].notna() & (top_leads['domain'] != '')).sum()
    has_phone_top = (top_leads['phone'].notna() & (top_leads['phone'] != '')).sum()

    report.append("\nEnrichment Potential:")
    report.append(f"  With domain (can enrich): {has_domain_top:,} ({has_domain_top/len(top_leads)*100:.1f}%)")
    report.append(f"  Already has phone: {has_phone_top:,} ({has_phone_top/len(top_leads)*100:.1f}%)")
    report.append(f"  Need phone enrichment: {has_domain_top - has_phone_top:,}")

    # Cost estimate
    report.append("\n💰 ENRICHMENT COST ESTIMATE")
    report.append("-" * 40)
    report.append(f"Multi-source scraping: FREE (website, Google, BBB)")
    report.append(f"Hunter.io (if needed): ~${has_domain_top * 0.01:.2f} ({has_domain_top} domains @ $0.01)")

    report.append("\n" + "=" * 70)
    report.append("RECOMMENDATION: Run multi-source enrichment first (free),")
    report.append("then only use Hunter.io on leads with verified phones but")
    report.append("missing email/contact names.")
    report.append("=" * 70)

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='Filter and rank leads by ICP criteria')
    parser.add_argument('--top', type=int, default=1000, help='Number of top leads to filter')
    parser.add_argument('--report', action='store_true', help='Generate detailed analysis report')
    parser.add_argument('--analyze', action='store_true', help='Just analyze, do not save files')

    args = parser.parse_args()

    # Load all companies
    df = load_all_companies()

    if df.empty:
        logger.error("No companies loaded!")
        return

    # Filter and rank
    top_leads = filter_and_rank_leads(df, args.top)

    # Generate report
    report = generate_analysis_report(df, top_leads)
    print(report)

    if args.analyze:
        logger.info("\n[ANALYZE MODE] No files saved.")
        return

    # Save top leads
    timestamp = datetime.now().strftime('%Y%m%d')
    output_file = OUTPUT_DIR / f"TOP_{args.top}_ICP_FILTERED_{timestamp}.csv"
    top_leads.to_csv(output_file, index=False)
    logger.info(f"\n✅ Saved: {output_file}")

    # Save report if requested
    if args.report:
        report_file = OUTPUT_DIR / f"ICP_ANALYSIS_REPORT_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        logger.info(f"✅ Saved: {report_file}")

    # Summary
    logger.info(f"\n🎯 TOP {args.top} ICP LEADS READY FOR ENRICHMENT")
    logger.info(f"   File: {output_file}")
    logger.info(f"   PLATINUM: {(top_leads['filter_tier'] == 'PLATINUM').sum()}")
    logger.info(f"   GOLD: {(top_leads['filter_tier'] == 'GOLD').sum()}")
    logger.info(f"   SILVER: {(top_leads['filter_tier'] == 'SILVER').sum()}")
    logger.info(f"   BRONZE: {(top_leads['filter_tier'] == 'BRONZE').sum()}")


if __name__ == "__main__":
    main()
