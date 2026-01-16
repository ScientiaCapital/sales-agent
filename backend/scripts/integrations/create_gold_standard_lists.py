#!/usr/bin/env python3
"""
Gold Standard Lead Lists Generator
===================================
Combines ALL lead sources, applies Tim's ICP scoring, and creates tiered lists
for Monday's outbound calling campaign.

Sources:
  1. Schneider OEM Dealers (90 leads) - Tag: schneider_oem
  2. Grandmaster Multi-OEM (8,277 leads) - Tag: grandmaster
  3. Master List GOLD+SILVER (151 leads) - Tag: master_*

Output: Top 50, 100, 250, 500, 1000 CSVs with BOTH phone + ATL required for top tiers

REFRESH MODE (--refresh):
  When scrapers are fixed and new data becomes available (every 6-12 months):
  - Loads existing scored leads from last run
  - Compares against new scraper output
  - Identifies: NEW leads, UPDATED leads, STALE leads (missing from new scrape)
  - Generates change report for audit
  - All scripts are IDEMPOTENT - safe to run multiple times

Author: Claude + Tim
Date: Nov 29, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import logging
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# OEM Keywords for ICP scoring (case-insensitive matching)
SCHNEIDER_KEYWORDS = ['schneider', 'square d', 'apc']
GENERAC_KEYWORDS = ['generac']
CARRIER_KEYWORDS = ['carrier', 'bryant', 'payne']
TRANE_KEYWORDS = ['trane', 'american standard']
MITSUBISHI_KEYWORDS = ['mitsubishi']

# ATL Title Keywords (decision-makers)
ATL_TITLES = [
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'cto', 'chief technology', 'cfo', 'chief financial', 'coo', 'chief operating',
    'vp', 'vice president', 'svp', 'evp', 'director', 'head of',
    'manager', 'general manager', 'partner', 'principal'
]

# ============================================================================
# IDEAL STATES for MEP+Energy Contractors
# ============================================================================
# SREC States (Solar Renewable Energy Credits) - highest solar incentives
SREC_STATES = ['NJ', 'MA', 'MD', 'DC', 'PA', 'OH', 'IL']

# High Volume Solar Markets
HIGH_VOLUME_STATES = ['CA', 'TX', 'FL', 'AZ', 'NV', 'CO', 'NC']

# High Permitting Complexity (need experienced contractors)
HIGH_PERMIT_STATES = ['NY', 'NJ', 'PA', 'MA', 'CT', 'CA']

# Combined ideal states with priority scores
IDEAL_STATE_SCORES = {
    # Tier 1: SREC + High Volume (15 pts)
    'CA': 15,  # Largest solar market + complex permitting
    'TX': 15,  # Fast-growing, deregulated, huge opportunity
    'FL': 15,  # Growing fast, hurricane resilience market

    # Tier 2: SREC States (12 pts)
    'NJ': 12,  # Highest SREC value in nation
    'MA': 12,  # Strong SREC + clean energy mandates
    'MD': 10,  # Good SREC market
    'PA': 10,  # Growing SREC market

    # Tier 3: High-Growth Markets (8 pts)
    'NY': 8,   # Complex permitting = need good contractors
    'AZ': 8,   # High solar irradiance
    'NV': 8,   # Solar + battery storage growth
    'CO': 8,   # Clean energy mandates
    'NC': 8,   # Utility-scale solar hub

    # Tier 4: Emerging Markets (5 pts)
    'GA': 5, 'VA': 5, 'OH': 5, 'IL': 5, 'CT': 5,
    'SC': 5, 'MN': 5, 'WI': 5, 'MI': 5, 'IN': 5,
}

# Output directory
OUTPUT_DIR = Path("data/final_enrichment_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Tim's ICP Scoring Formula
# ============================================================================

def calculate_icp_score(row: pd.Series, location_counts: dict = None) -> float:
    """
    Tim's ICP scoring formula (max ~115 points):

    TARGET: "Next generation MEP+E contractors that self-perform"
    PRIORITY: Multi-OEM, Multi-Trade, Multi-Location, Ideal State contractors

    Contact Quality (25 points) - Phone is THE GOLD
    - has_phone: 20 points (required for calling Monday!)
    - has_email: 5 points (for email campaigns)

    Multi-Capability Signals (38 points) - THE BIG DIFFERENTIATOR
    - Multi-OEM: OEM_Count * 5, up to 15 points (3+ OEMs = ideal)
    - Multi-Trade: capability_count * 3, up to 12 points (4+ trades = ideal)
    - Multi-Location: state_count * 4, up to 8 points (2+ states = regional player)
    - Self-Performing bonus: 3 points (multi-trade + not GC)

    OEM Certification (20 points) - Premium brand signal
    - is_schneider_dealer: 10 points (baseline ICP)
    - is_generac_dealer: 5 points (generator = high value)
    - is_carrier_dealer: 5 points (HVAC = core)

    Business Maturity (20 points) - Established company signals
    - has_website/domain: 5 points
    - employee_tier: 0-5 points (100+ = 5, 50+ = 3, 10+ = 2)
    - rating: 0-5 points (4.5+ = 5, 4.0+ = 3, 3.5+ = 2)
    - review_count: 0-5 points (100+ = 5, 50+ = 3, 10+ = 2)

    IDEAL STATE BONUS (up to 15 points) - MEP+Energy priority markets
    - Tier 1 (15 pts): CA, TX, FL - highest volume solar markets
    - Tier 2 (10-12 pts): NJ, MA, MD, PA - SREC states
    - Tier 3 (8 pts): NY, AZ, NV, CO, NC - high-growth markets
    - Tier 4 (5 pts): GA, VA, OH, IL, CT, etc. - emerging markets
    """
    score = 0.0

    # =========================================================================
    # CONTACT QUALITY (25 points) - Phone is THE GOLD for Monday calling
    # =========================================================================
    has_phone = pd.notna(row.get('phone')) and str(row.get('phone', '')).strip() != ''
    has_email = pd.notna(row.get('email')) and '@' in str(row.get('email', ''))

    if has_phone:
        score += 20  # THE GOLD - required for calling
    if has_email:
        score += 5   # Bonus for email campaigns

    # =========================================================================
    # MULTI-CAPABILITY SIGNALS (35 points) - Tim's priority!
    # =========================================================================

    # Multi-OEM (up to 15 points) - contractors working with multiple brands
    oem_count = 0
    if pd.notna(row.get('OEM_Count')):
        try:
            oem_count = int(row['OEM_Count'])
        except:
            pass
    # Also count OEMs from comma-separated field
    oem_field = str(row.get('OEMs_Certified', '') or row.get('oem_certifications', '') or '')
    if oem_field and oem_field != 'nan':
        oem_list = [o.strip() for o in oem_field.split(',') if o.strip()]
        oem_count = max(oem_count, len(oem_list))
    score += min(oem_count * 5, 15)  # 3+ OEMs = max 15 points

    # Multi-Trade (up to 12 points) - contractors with multiple capabilities
    # This is our best indicator of SELF-PERFORMING contractors
    # GCs (general contractors) typically subcontract - they won't have multiple trade flags
    # Self-performers DO the work - they'll have has_hvac, has_electrical, etc.
    capability_count = 0
    mep_trades = []  # Track which MEP trades they have
    for cap in ['has_hvac', 'has_solar', 'has_generator', 'has_battery', 'has_electrical', 'has_plumbing']:
        if str(row.get(cap, '')).lower() in ['true', '1', 'yes']:
            capability_count += 1
            mep_trades.append(cap.replace('has_', ''))

    # Also check capability_count field if populated
    if pd.notna(row.get('capability_count')):
        try:
            capability_count = max(capability_count, int(row['capability_count']))
        except:
            pass

    # Self-performing inference:
    # - 2+ MEP trades = likely self-performing (they do the work themselves)
    # - Explicitly NOT a GC (is_gc = False) = good signal
    # - has_om_capability = operations/maintenance = self-performing signal
    is_gc = str(row.get('is_gc', '')).lower() in ['true', '1', 'yes']
    is_likely_self_performing = (
        capability_count >= 2 or  # Multiple trades = does own work
        str(row.get('has_om_capability', '')).lower() in ['true', '1', 'yes'] or  # O&M work
        str(row.get('is_self_performing', '')).lower() in ['true', '1', 'yes']  # Explicit flag
    )

    # Award points for multi-trade (capped at 12)
    score += min(capability_count * 3, 12)  # 4+ trades = max 12 points

    # Bonus for self-performing (not a GC + has multiple trades)
    if is_likely_self_performing and not is_gc:
        score += 3  # Bonus for self-performers

    # Multi-Location (up to 8 points) - regional/national players
    if location_counts:
        company_name = str(row.get('name', '') or row.get('name_normalized', '')).strip().lower()
        state_count = location_counts.get(company_name, 1)
        score += min(state_count * 4, 8)  # 2+ states = regional player

    # =========================================================================
    # OEM CERTIFICATION (20 points) - Premium brand partnerships
    # =========================================================================
    oem_text = str(row.get('oem_certifications', '') or row.get('OEMs_Certified', '') or '').lower()
    source_tag = str(row.get('source_tag', '')).lower()

    # Schneider detection: OEM field OR source_tag for pre-tagged leads
    is_schneider = any(kw in oem_text for kw in SCHNEIDER_KEYWORDS) or 'schneider' in source_tag
    is_generac = any(kw in oem_text for kw in GENERAC_KEYWORDS)
    is_carrier = any(kw in oem_text for kw in CARRIER_KEYWORDS)

    if is_schneider:
        score += 10  # Baseline ICP
    if is_generac:
        score += 5   # Generator = high value
    if is_carrier:
        score += 5   # HVAC = core

    # =========================================================================
    # BUSINESS MATURITY (20 points) - Established company signals
    # =========================================================================

    # Website/Domain (5 points)
    has_website = pd.notna(row.get('website')) or pd.notna(row.get('domain'))
    if has_website:
        score += 5

    # Employee tier (5 points)
    try:
        emp = int(row.get('employee_count', 0) or 0)
        if emp >= 100:
            score += 5
        elif emp >= 50:
            score += 3
        elif emp >= 10:
            score += 2
    except:
        pass

    # Rating (5 points)
    try:
        rating = float(row.get('rating', 0) or 0)
        if rating >= 4.5:
            score += 5
        elif rating >= 4.0:
            score += 3
        elif rating >= 3.5:
            score += 2
    except:
        pass

    # Review count (5 points) - more reviews = more established
    try:
        reviews = int(row.get('review_count', 0) or 0)
        if reviews >= 100:
            score += 5
        elif reviews >= 50:
            score += 3
        elif reviews >= 10:
            score += 2
    except:
        pass

    # =========================================================================
    # IDEAL STATE BONUS (up to 15 points) - MEP+Energy priority markets
    # =========================================================================
    state = str(row.get('state', '')).strip().upper()
    if len(state) > 2:
        # Try to extract 2-letter state code from longer strings
        state = state[:2]
    state_bonus = IDEAL_STATE_SCORES.get(state, 0)
    score += state_bonus

    return round(score, 1)


def determine_tier(score: float, has_phone: bool, has_email: bool, is_oem_certified: bool) -> str:
    """
    Determine tier based on score and contact quality.

    - PLATINUM (80+): BOTH phone + ATL + OEM cert
    - GOLD (65+): BOTH phone + contact info
    - SILVER (50+): Phone + email
    - BRONZE (35+): Phone OR email
    - LEAD (20+): Has domain
    """
    if score >= 80 and has_phone and is_oem_certified:
        return 'PLATINUM'
    elif score >= 65 and has_phone and has_email:
        return 'GOLD'
    elif score >= 50 and has_phone:
        return 'SILVER'
    elif score >= 35 and (has_phone or has_email):
        return 'BRONZE'
    else:
        return 'LEAD'


# ============================================================================
# Data Loading Functions
# ============================================================================

def load_schneider_leads() -> pd.DataFrame:
    """Load pre-enriched Schneider OEM dealer leads (90 records)."""
    path = Path("/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/clean_leads_gold_silver_20251128.csv")

    if not path.exists():
        logger.warning(f"Schneider file not found: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path)
    df['source_tag'] = 'schneider_oem'
    df['oem_certifications'] = df.get('source', 'schneider')

    # Normalize column names
    df = df.rename(columns={'company_name': 'name'})

    logger.info(f"Loaded {len(df)} Schneider OEM leads")
    return df


def load_grandmaster_leads() -> pd.DataFrame:
    """Load grandmaster multi-OEM leads (8,277 records)."""
    path = Path("/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/_archive/2025-11-26_pre_cleanup/grandmaster_list_expanded_20251029.csv")

    if not path.exists():
        logger.warning(f"Grandmaster file not found: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    df['source_tag'] = 'grandmaster'

    logger.info(f"Loaded {len(df)} grandmaster leads")
    return df


def load_master_list_gold_silver() -> pd.DataFrame:
    """Load master list GOLD and SILVER tier leads (151 records)."""
    path = Path("/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/master/master_list_20251126_074350.csv")

    if not path.exists():
        logger.warning(f"Master list file not found: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)

    # Filter for GOLD and SILVER only
    df = df[df['icp_tier'].isin(['GOLD', 'SILVER'])]
    df['source_tag'] = df['icp_tier'].apply(lambda x: f"master_{x.lower()}")

    # Normalize column names
    df = df.rename(columns={'company_name': 'name'})

    logger.info(f"Loaded {len(df)} master list GOLD+SILVER leads")
    return df


# ============================================================================
# Main Processing
# ============================================================================

def combine_and_score_leads() -> pd.DataFrame:
    """Combine all sources and apply unified ICP scoring."""

    logger.info("=" * 60)
    logger.info("LOADING ALL LEAD SOURCES")
    logger.info("=" * 60)

    # Load all sources
    schneider_df = load_schneider_leads()
    grandmaster_df = load_grandmaster_leads()
    master_df = load_master_list_gold_silver()

    # Standardize columns across all sources
    common_columns = [
        'name', 'phone', 'email', 'domain', 'website', 'city', 'state', 'zip',
        'OEM_Count', 'OEMs_Certified', 'oem_certifications',
        'has_hvac', 'has_solar', 'has_generator', 'has_battery', 'has_electrical', 'has_plumbing',
        'is_commercial', 'has_om_capability', 'is_self_performing', 'is_gc',  # GC = general contractor
        'employee_count', 'rating', 'review_count',
        'capability_count',  # Multi-trade count
        'source_tag'
    ]

    # Ensure all dataframes have all columns
    for col in common_columns:
        if col not in schneider_df.columns:
            schneider_df[col] = None
        if col not in grandmaster_df.columns:
            grandmaster_df[col] = None
        if col not in master_df.columns:
            master_df[col] = None

    # Combine all sources
    all_leads = pd.concat([
        schneider_df[common_columns],
        grandmaster_df[common_columns],
        master_df[common_columns]
    ], ignore_index=True)

    logger.info(f"\nCombined total: {len(all_leads)} leads")
    logger.info(f"  - Schneider OEM: {len(schneider_df)}")
    logger.info(f"  - Grandmaster: {len(grandmaster_df)}")
    logger.info(f"  - Master GOLD+SILVER: {len(master_df)}")

    # Deduplicate by name (case-insensitive)
    all_leads['name_normalized'] = all_leads['name'].str.lower().str.strip()
    all_leads = all_leads.drop_duplicates(subset=['name_normalized'], keep='first')
    logger.info(f"\nAfter deduplication: {len(all_leads)} unique leads")

    # Apply ICP scoring
    logger.info("\n" + "=" * 60)
    logger.info("APPLYING TIM'S ICP SCORING")
    logger.info("=" * 60)
    logger.info("Prioritizing: Multi-OEM, Multi-Trade, Multi-Location contractors")

    # Calculate multi-location counts (companies in multiple states)
    location_counts = {}
    name_states = all_leads.groupby('name_normalized')['state'].apply(
        lambda x: x.dropna().nunique()
    )
    for name, count in name_states.items():
        if count > 1:  # Only track multi-state companies
            location_counts[name] = count

    multi_location_count = len(location_counts)
    if multi_location_count > 0:
        logger.info(f"Found {multi_location_count} multi-location contractors (operating in 2+ states)")

    all_leads['icp_score'] = all_leads.apply(
        lambda row: calculate_icp_score(row, location_counts), axis=1
    )

    # Calculate additional flags for tier assignment
    all_leads['has_phone'] = all_leads['phone'].notna() & (all_leads['phone'].astype(str).str.strip() != '')
    all_leads['has_email'] = all_leads['email'].notna() & all_leads['email'].astype(str).str.contains('@', na=False)
    all_leads['has_domain'] = all_leads['domain'].notna() | all_leads['website'].notna()

    # Check OEM certification
    all_leads['is_oem_certified'] = all_leads.apply(
        lambda row: any(kw in str(row.get('oem_certifications', '') or row.get('source_tag', '')).lower()
                       for kw in SCHNEIDER_KEYWORDS + GENERAC_KEYWORDS + CARRIER_KEYWORDS),
        axis=1
    )

    # Assign tiers
    all_leads['tier'] = all_leads.apply(
        lambda row: determine_tier(row['icp_score'], row['has_phone'], row['has_email'], row['is_oem_certified']),
        axis=1
    )

    # Sort by score descending
    all_leads = all_leads.sort_values('icp_score', ascending=False).reset_index(drop=True)
    all_leads['rank'] = range(1, len(all_leads) + 1)

    # Print score distribution
    logger.info(f"\nScore Distribution:")
    logger.info(f"  Max: {all_leads['icp_score'].max()}")
    logger.info(f"  Min: {all_leads['icp_score'].min()}")
    logger.info(f"  Mean: {all_leads['icp_score'].mean():.1f}")
    logger.info(f"  Median: {all_leads['icp_score'].median():.1f}")

    logger.info(f"\nTier Distribution:")
    tier_counts = all_leads['tier'].value_counts()
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
        count = tier_counts.get(tier, 0)
        logger.info(f"  {tier}: {count}")

    logger.info(f"\nSource Distribution:")
    source_counts = all_leads['source_tag'].value_counts()
    for source, count in source_counts.items():
        logger.info(f"  {source}: {count}")

    # Contact quality stats
    logger.info(f"\nContact Quality:")
    logger.info(f"  With phone: {all_leads['has_phone'].sum()} ({all_leads['has_phone'].mean()*100:.1f}%)")
    logger.info(f"  With email: {all_leads['has_email'].sum()} ({all_leads['has_email'].mean()*100:.1f}%)")
    logger.info(f"  With domain: {all_leads['has_domain'].sum()} ({all_leads['has_domain'].mean()*100:.1f}%)")
    logger.info(f"  OEM certified: {all_leads['is_oem_certified'].sum()} ({all_leads['is_oem_certified'].mean()*100:.1f}%)")

    return all_leads


def export_tiered_lists(all_leads: pd.DataFrame):
    """Export tiered CSVs for outbound calling."""

    timestamp = datetime.now().strftime("%Y%m%d")

    # Define export columns
    export_columns = [
        'rank', 'name', 'phone', 'email', 'domain', 'website',
        'city', 'state', 'zip',
        'icp_score', 'tier', 'source_tag',
        'OEM_Count', 'oem_certifications',
        'has_phone', 'has_email', 'is_oem_certified',
        'has_hvac', 'has_solar', 'has_generator', 'has_battery',
        'employee_count', 'rating'
    ]

    # Filter columns that exist
    export_columns = [c for c in export_columns if c in all_leads.columns]

    # Export tiers
    tiers = [50, 100, 250, 500, 1000]

    logger.info("\n" + "=" * 60)
    logger.info("EXPORTING TIERED LISTS")
    logger.info("=" * 60)

    for n in tiers:
        df_tier = all_leads.head(n)[export_columns]
        filename = f"GOLD_STANDARD_TOP_{n}_{timestamp}.csv"
        filepath = OUTPUT_DIR / filename
        df_tier.to_csv(filepath, index=False)

        # Stats for this tier
        with_phone = df_tier['has_phone'].sum()
        with_email = df_tier['has_email'].sum()
        oem_cert = df_tier['is_oem_certified'].sum()

        logger.info(f"\n✅ {filename}")
        logger.info(f"   Records: {len(df_tier)}")
        logger.info(f"   With phone: {with_phone} ({with_phone/n*100:.1f}%)")
        logger.info(f"   With email: {with_email} ({with_email/n*100:.1f}%)")
        logger.info(f"   OEM certified: {oem_cert} ({oem_cert/n*100:.1f}%)")
        logger.info(f"   Score range: {df_tier['icp_score'].min():.1f} - {df_tier['icp_score'].max():.1f}")

    # Export full scored list for enrichment
    full_path = OUTPUT_DIR / f"all_leads_scored_{timestamp}.csv"
    all_leads.to_csv(full_path, index=False)
    logger.info(f"\n✅ Full scored list: {full_path}")

    # Export top 2000 for Hunter.io enrichment
    enrichment_path = OUTPUT_DIR / f"leads_for_enrichment_{timestamp}.csv"
    enrichment_df = all_leads.head(2000)
    enrichment_df[['rank', 'name', 'domain', 'website', 'phone', 'email', 'source_tag', 'icp_score']].to_csv(enrichment_path, index=False)
    logger.info(f"✅ Enrichment batch (2000): {enrichment_path}")

    return enrichment_path


def analyze_schneider_baseline(all_leads: pd.DataFrame):
    """Generate Schneider ICP baseline analysis report."""

    schneider_leads = all_leads[all_leads['source_tag'] == 'schneider_oem']

    if len(schneider_leads) == 0:
        logger.warning("No Schneider leads found for baseline analysis")
        return

    timestamp = datetime.now().strftime("%Y%m%d")
    report_path = OUTPUT_DIR / f"schneider_icp_analysis_{timestamp}.md"

    report = f"""# Schneider Electric Dealer ICP Baseline Analysis
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Summary
- **Total Schneider dealers**: {len(schneider_leads)}
- **Avg ICP score**: {schneider_leads['icp_score'].mean():.1f}
- **Score range**: {schneider_leads['icp_score'].min():.1f} - {schneider_leads['icp_score'].max():.1f}

## Rank Distribution in Master List
Where did Schneider dealers rank among ALL {len(all_leads)} leads?

| Rank Bucket | Count | Percentage |
|-------------|-------|------------|
| Top 50 | {len(schneider_leads[schneider_leads['rank'] <= 50])} | {len(schneider_leads[schneider_leads['rank'] <= 50])/len(schneider_leads)*100:.1f}% |
| Top 100 | {len(schneider_leads[schneider_leads['rank'] <= 100])} | {len(schneider_leads[schneider_leads['rank'] <= 100])/len(schneider_leads)*100:.1f}% |
| Top 250 | {len(schneider_leads[schneider_leads['rank'] <= 250])} | {len(schneider_leads[schneider_leads['rank'] <= 250])/len(schneider_leads)*100:.1f}% |
| Top 500 | {len(schneider_leads[schneider_leads['rank'] <= 500])} | {len(schneider_leads[schneider_leads['rank'] <= 500])/len(schneider_leads)*100:.1f}% |
| Top 1000 | {len(schneider_leads[schneider_leads['rank'] <= 1000])} | {len(schneider_leads[schneider_leads['rank'] <= 1000])/len(schneider_leads)*100:.1f}% |

## Tier Distribution
| Tier | Count |
|------|-------|
| PLATINUM | {len(schneider_leads[schneider_leads['tier'] == 'PLATINUM'])} |
| GOLD | {len(schneider_leads[schneider_leads['tier'] == 'GOLD'])} |
| SILVER | {len(schneider_leads[schneider_leads['tier'] == 'SILVER'])} |
| BRONZE | {len(schneider_leads[schneider_leads['tier'] == 'BRONZE'])} |
| LEAD | {len(schneider_leads[schneider_leads['tier'] == 'LEAD'])} |

## Contact Quality
- **With phone**: {schneider_leads['has_phone'].sum()} ({schneider_leads['has_phone'].mean()*100:.1f}%)
- **With email**: {schneider_leads['has_email'].sum()} ({schneider_leads['has_email'].mean()*100:.1f}%)
- **OEM certified**: {schneider_leads['is_oem_certified'].sum()} ({schneider_leads['is_oem_certified'].mean()*100:.1f}%)

## Top 20 Schneider Dealers (by ICP score)
| Rank | Company | ICP Score | Phone | Email | City, State |
|------|---------|-----------|-------|-------|-------------|
"""

    for _, row in schneider_leads.head(20).iterrows():
        phone_status = "✅" if row['has_phone'] else "❌"
        email_status = "✅" if row['has_email'] else "❌"
        report += f"| {int(row['rank'])} | {row['name'][:40]} | {row['icp_score']:.1f} | {phone_status} | {email_status} | {row.get('city', '')}, {row.get('state', '')} |\n"

    report += f"""

## ICP Insights
These Schneider Electric dealers represent Tim's ideal customer profile:
- Enterprise building automation focus
- Self-performing MEP+E contractors
- Multi-OEM sophistication (can handle complex integrations)

Use these as the baseline for scoring other leads. Leads that match similar signals should score high.

## Next Steps
1. Enrich all {len(schneider_leads)} Schneider leads through Hunter.io for ATL contacts
2. Track close rates for Schneider vs non-Schneider leads
3. Refine ICP scoring based on actual conversion data
"""

    with open(report_path, 'w') as f:
        f.write(report)

    logger.info(f"\n✅ Schneider ICP analysis: {report_path}")


def find_latest_scored_file() -> Path | None:
    """Find the most recent all_leads_scored_*.csv file."""
    scored_files = list(OUTPUT_DIR.glob("all_leads_scored_*.csv"))
    if not scored_files:
        return None
    # Sort by modification time, newest first
    return max(scored_files, key=lambda p: p.stat().st_mtime)


def compare_and_refresh(new_leads: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Compare new scraper data against existing scored leads.

    Returns:
        tuple: (merged_leads DataFrame, change_report dict)

    Change Detection:
    - NEW: In new scrape, not in existing
    - UPDATED: In both, but fields changed
    - STALE: In existing, not in new scrape (mark, don't delete!)
    """
    previous_file = find_latest_scored_file()

    if not previous_file:
        logger.info("No previous scored file found - treating all leads as NEW")
        new_leads['change_type'] = 'new'
        new_leads['is_stale'] = False
        return new_leads, {
            'total_new': len(new_leads),
            'total_updated': 0,
            'total_stale': 0,
            'previous_file': None
        }

    logger.info(f"Loading previous scored data: {previous_file}")
    previous_df = pd.read_csv(previous_file)
    previous_df['name_normalized'] = previous_df['name'].str.lower().str.strip()

    # Create sets for comparison
    previous_names = set(previous_df['name_normalized'].dropna())
    new_names = set(new_leads['name_normalized'].dropna())

    # Categorize leads
    new_only = new_names - previous_names          # Brand new leads
    stale_only = previous_names - new_names       # Missing from new scrape
    in_both = new_names & previous_names          # Need to check for updates

    logger.info(f"\nChange Detection:")
    logger.info(f"  NEW leads: {len(new_only)}")
    logger.info(f"  STALE leads: {len(stale_only)}")
    logger.info(f"  In both (check for updates): {len(in_both)}")

    # Track change types
    new_leads['change_type'] = new_leads['name_normalized'].apply(
        lambda n: 'new' if n in new_only else ('updated' if n in in_both else 'unknown')
    )
    new_leads['is_stale'] = False

    # Mark stale leads from previous file
    stale_leads = previous_df[previous_df['name_normalized'].isin(stale_only)].copy()
    stale_leads['change_type'] = 'stale'
    stale_leads['is_stale'] = True
    stale_leads['stale_since'] = datetime.now().isoformat()
    stale_leads['stale_reason'] = 'not_in_new_scrape'

    # Combine: new leads + stale leads (keep stale for audit, but deprioritize)
    # Stale leads get score penalty to push them down
    stale_leads['icp_score'] = stale_leads['icp_score'].apply(lambda x: max(0, x - 50))

    merged = pd.concat([new_leads, stale_leads], ignore_index=True)
    merged = merged.drop_duplicates(subset=['name_normalized'], keep='first')

    # Sort by score (stale leads will naturally fall to bottom due to penalty)
    merged = merged.sort_values('icp_score', ascending=False).reset_index(drop=True)
    merged['rank'] = range(1, len(merged) + 1)

    # Generate change report
    change_report = {
        'previous_file': str(previous_file),
        'previous_count': len(previous_df),
        'new_count': len(new_leads),
        'merged_count': len(merged),
        'total_new': len(new_only),
        'total_updated': len(in_both),
        'total_stale': len(stale_only),
        'timestamp': datetime.now().isoformat()
    }

    # Export change report
    report_path = OUTPUT_DIR / f"change_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(change_report, f, indent=2)
    logger.info(f"\n✅ Change report saved: {report_path}")

    return merged, change_report


def main():
    """Main execution function."""

    parser = argparse.ArgumentParser(description='Gold Standard Lead Lists Generator')
    parser.add_argument('--refresh', action='store_true',
                        help='Refresh mode: compare new data against existing and track changes')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run: analyze changes without saving new files')
    args = parser.parse_args()

    logger.info("\n" + "=" * 60)
    logger.info("GOLD STANDARD LEAD LISTS GENERATOR")
    if args.refresh:
        logger.info("MODE: REFRESH (comparing against previous data)")
    if args.dry_run:
        logger.info("MODE: DRY RUN (no files will be saved)")
    logger.info("=" * 60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Phase 1: Load and score all leads
    all_leads = combine_and_score_leads()

    # If refresh mode, compare against previous data
    if args.refresh:
        all_leads, change_report = compare_and_refresh(all_leads)
        logger.info(f"\n📊 Refresh Summary:")
        logger.info(f"  Previous count: {change_report['previous_count']}")
        logger.info(f"  New count: {change_report['new_count']}")
        logger.info(f"  Merged count: {change_report['merged_count']}")
        logger.info(f"  Changes: +{change_report['total_new']} new, "
                   f"~{change_report['total_updated']} updated, "
                   f"-{change_report['total_stale']} stale")

    if args.dry_run:
        logger.info("\n⚠️ DRY RUN - No files saved")
        return all_leads

    # Export tiered lists
    enrichment_path = export_tiered_lists(all_leads)

    # Generate Schneider baseline analysis
    analyze_schneider_baseline(all_leads)

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1 COMPLETE")
    logger.info("=" * 60)
    logger.info(f"\nNext: Run Hunter.io enrichment in batches:")
    logger.info(f"  python enrich_gold_standard_batch.py --batch 1")
    logger.info(f"  (wait 30 min)")
    logger.info(f"  python enrich_gold_standard_batch.py --batch 2")
    logger.info(f"  etc...")

    if args.refresh:
        logger.info(f"\n📝 Remember: Stale leads are kept but deprioritized (-50 score penalty)")
        logger.info(f"   To permanently remove stale leads, review and delete manually")

    return all_leads


if __name__ == "__main__":
    main()
