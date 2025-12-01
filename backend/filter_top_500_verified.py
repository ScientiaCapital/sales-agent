#!/usr/bin/env python3
"""
Filter enriched leads to TOP 500 for Hunter.io enrichment.

Scoring Priority (for Hunter.io ROI):
1. Verified phones (multi-source confirmation) - +100 pts per verified
2. ATL contacts already found - +200 pts (Hunter.io will find email)
3. Website verified - +50 pts (Hunter.io needs valid domain)
4. Multiple phone numbers - +20 pts per phone (healthy company)
5. Social presence (LinkedIn/Facebook) - +30 pts (easier to find people)

Hunter.io costs ~$0.01/domain, so we want domains most likely to:
- Have findable email addresses
- Be real, active businesses
- Have decision-makers we can reach
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path


def calculate_hunter_priority_score(row: pd.Series) -> int:
    """Calculate priority score for Hunter.io enrichment."""
    score = 0

    # 1. Verified phones = trust signal (+100 per verified, max 300)
    verified_count = row.get('verified_phone_count', 0) or 0
    score += min(verified_count * 100, 300)

    # 2. ATL contact already found = Hunter will find email (+200)
    has_atl = pd.notna(row.get('contact_1_name')) and row.get('contact_1_name') != ''
    if has_atl:
        score += 200

    # 3. Website verified = Hunter.io can scan domain (+50)
    if row.get('website_verified', False):
        score += 50

    # 4. Multiple phones = active business (+20 per phone, max 100)
    phone_count = row.get('phone_count', 0) or 0
    score += min(phone_count * 20, 100)

    # 5. Social presence (+30 each)
    if row.get('linkedin_verified', False):
        score += 30
    if row.get('facebook_verified', False):
        score += 30

    # 6. BBB/Yelp presence = established business (+20 each)
    if row.get('bbb_verified', False):
        score += 20
    if row.get('yelp_verified', False):
        score += 20

    return score


def main():
    # Load enriched data
    input_file = Path('data/final_enrichment_output/ENRICHED_1000_ICP_COMPLETE_20251201.csv')
    df = pd.read_csv(input_file)

    print(f"=== FILTERING TOP 500 FOR HUNTER.IO ===")
    print(f"Input: {len(df)} enriched leads")
    print()

    # Calculate Hunter priority scores
    df['hunter_priority_score'] = df.apply(calculate_hunter_priority_score, axis=1)

    # Sort by score descending
    df_sorted = df.sort_values('hunter_priority_score', ascending=False)

    # Show score distribution
    print("Hunter Priority Score Distribution:")
    score_bins = [0, 50, 100, 150, 200, 300, 400, 500, 1000]
    df_sorted['score_tier'] = pd.cut(df_sorted['hunter_priority_score'], bins=score_bins)
    print(df_sorted['score_tier'].value_counts().sort_index())
    print()

    # Take top 500
    top_500 = df_sorted.head(500).copy()

    # Stats
    print(f"=== TOP 500 STATS ===")
    print(f"Min score: {top_500['hunter_priority_score'].min()}")
    print(f"Max score: {top_500['hunter_priority_score'].max()}")
    print(f"Mean score: {top_500['hunter_priority_score'].mean():.1f}")
    print(f"With verified phones: {(top_500['verified_phone_count'] > 0).sum()}")
    print(f"With ATL contacts: {top_500['contact_1_name'].notna().sum()}")
    print(f"With website verified: {top_500['website_verified'].sum()}")
    print()

    # Create output for Hunter.io
    # Hunter only needs: domain, company_name, and optionally first_name/last_name to search
    hunter_columns = [
        'company_name', 'domain', 'hunter_priority_score',
        'primary_phone', 'verified_phone_count', 'phone_count',
        'contact_1_name', 'contact_1_title',
        'city', 'state',
        'website_verified', 'linkedin_verified', 'facebook_verified',
        'phone_1', 'phone_1_verified', 'phone_1_sources',
        'phone_2', 'phone_2_verified',
        'enrichment_timestamp'
    ]

    # Only include columns that exist
    hunter_columns = [c for c in hunter_columns if c in top_500.columns]
    hunter_df = top_500[hunter_columns]

    # Save outputs
    timestamp = datetime.now().strftime('%Y%m%d')

    # Full top 500 with all data
    full_output = f'data/final_enrichment_output/TOP_500_FOR_HUNTER_{timestamp}.csv'
    top_500.to_csv(full_output, index=False)
    print(f"✅ Full data: {full_output}")

    # Simplified Hunter.io input file (just domain + company_name)
    hunter_input = top_500[['company_name', 'domain', 'hunter_priority_score', 'contact_1_name', 'contact_1_title']].copy()
    hunter_input_file = f'data/final_enrichment_output/HUNTER_INPUT_500_{timestamp}.csv'
    hunter_input.to_csv(hunter_input_file, index=False)
    print(f"✅ Hunter input: {hunter_input_file}")

    # JSON backup
    json_output = f'data/final_enrichment_output/TOP_500_FOR_HUNTER_{timestamp}.json'
    top_500.to_json(json_output, orient='records', indent=2)
    print(f"✅ JSON backup: {json_output}")

    print()
    print(f"=== HUNTER.IO COST ESTIMATE ===")
    print(f"Domains to enrich: 500")
    print(f"Cost per domain: ~$0.01")
    print(f"Estimated total: ~$5.00")
    print()

    # Show top 20 leads
    print("=== TOP 20 LEADS (Highest Priority) ===")
    top_20 = top_500.head(20)[['company_name', 'domain', 'hunter_priority_score', 'verified_phone_count', 'contact_1_name', 'state']]
    print(top_20.to_string(index=False))


if __name__ == '__main__':
    main()
