#!/usr/bin/env python3
"""
Filter Gold Standard Leads by OEM
==================================
Quick filter tool for Tim to pull leads by specific OEM when focusing outreach.

Usage:
    python filter_leads_by_oem.py schneider           # Schneider Electric dealers
    python filter_leads_by_oem.py carrier             # Carrier HVAC dealers
    python filter_leads_by_oem.py generac             # Generac generator dealers
    python filter_leads_by_oem.py trane               # Trane HVAC dealers
    python filter_leads_by_oem.py --list              # Show all available OEMs
    python filter_leads_by_oem.py --multi             # Multi-OEM contractors (3+)

Output: data/final_enrichment_output/filtered_[OEM]_YYYYMMDD.csv
"""

import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Paths
INPUT_FILE = Path("data/final_enrichment_output/all_leads_scored_20251129.csv")
OUTPUT_DIR = Path("data/final_enrichment_output")

# Known OEMs (normalized to lowercase for matching)
KNOWN_OEMS = {
    'schneider': ['schneider', 'schneider electric'],
    'carrier': ['carrier'],
    'trane': ['trane'],
    'lennox': ['lennox'],
    'generac': ['generac'],
    'kohler': ['kohler'],
    'briggs': ['briggs', 'briggs & stratton'],
    'cummins': ['cummins'],
    'caterpillar': ['caterpillar', 'cat'],
    'daikin': ['daikin'],
    'york': ['york'],
    'rheem': ['rheem'],
    'goodman': ['goodman'],
    'mitsubishi': ['mitsubishi'],
    'lg': ['lg'],
    'samsung': ['samsung'],
    'panasonic': ['panasonic'],
    'tesla': ['tesla'],
    'enphase': ['enphase'],
    'solaredge': ['solaredge'],
    'sunpower': ['sunpower'],
    'sunrun': ['sunrun'],
}


def load_leads() -> pd.DataFrame:
    """Load the master scored leads file"""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Master file not found: {INPUT_FILE}")
    return pd.read_csv(INPUT_FILE)


def get_oem_distribution(df: pd.DataFrame) -> dict:
    """Count leads by OEM certification"""
    oem_counts = Counter()

    for idx, row in df.iterrows():
        oems = str(row.get('OEMs_Certified', '') or row.get('oem_certifications', '') or '')
        source_tag = str(row.get('source_tag', ''))

        if pd.isna(oems) or not oems:
            continue

        # Parse OEM list
        oem_list = [o.strip().lower() for o in oems.split(',')]

        for oem in oem_list:
            # Normalize OEM names
            for key, variants in KNOWN_OEMS.items():
                if any(v in oem for v in variants):
                    oem_counts[key] += 1
                    break
            else:
                # Unknown OEM
                oem_counts[oem] += 1

        # Also check source_tag for schneider
        if 'schneider' in source_tag.lower():
            oem_counts['schneider'] += 1

    return dict(oem_counts.most_common())


def filter_by_oem(df: pd.DataFrame, oem_name: str) -> pd.DataFrame:
    """Filter leads by OEM certification"""
    oem_lower = oem_name.lower()
    variants = KNOWN_OEMS.get(oem_lower, [oem_lower])

    def has_oem(row):
        oems = str(row.get('OEMs_Certified', '') or row.get('oem_certifications', '') or '').lower()
        source_tag = str(row.get('source_tag', '')).lower()

        # Check OEM certifications
        for variant in variants:
            if variant in oems:
                return True

        # Check source_tag (e.g., schneider_oem)
        for variant in variants:
            if variant in source_tag:
                return True

        return False

    mask = df.apply(has_oem, axis=1)
    return df[mask].copy()


def filter_multi_oem(df: pd.DataFrame, min_oems: int = 3) -> pd.DataFrame:
    """Filter leads with multiple OEM certifications"""
    def count_oems(row):
        oems = str(row.get('OEMs_Certified', '') or row.get('oem_certifications', '') or '')
        if pd.isna(oems) or not oems:
            return 0
        return len([o for o in oems.split(',') if o.strip()])

    df['_oem_count'] = df.apply(count_oems, axis=1)
    filtered = df[df['_oem_count'] >= min_oems].copy()
    filtered = filtered.drop(columns=['_oem_count'])
    return filtered


def main():
    parser = argparse.ArgumentParser(description='Filter Gold Standard leads by OEM')
    parser.add_argument('oem', nargs='?', help='OEM name to filter (e.g., schneider, carrier, generac)')
    parser.add_argument('--list', action='store_true', help='List all OEMs and their counts')
    parser.add_argument('--multi', action='store_true', help='Filter multi-OEM contractors (3+)')
    parser.add_argument('--min-oems', type=int, default=3, help='Minimum OEM count for --multi filter')
    parser.add_argument('--top', type=int, help='Limit output to top N by ICP score')

    args = parser.parse_args()

    # Load data
    print("Loading Gold Standard leads...")
    df = load_leads()
    print(f"Total leads: {len(df)}")

    # List OEMs
    if args.list:
        print("\n" + "=" * 60)
        print("OEM DISTRIBUTION IN GOLD STANDARD LIST")
        print("=" * 60)

        oem_dist = get_oem_distribution(df)
        for oem, count in oem_dist.items():
            print(f"  {oem.title():20} {count:5} leads")

        print("\n📌 Usage: python filter_leads_by_oem.py <oem_name>")
        return

    # Multi-OEM filter
    if args.multi:
        filtered = filter_multi_oem(df, args.min_oems)
        output_name = f"filtered_multi_oem_{args.min_oems}plus_{datetime.now().strftime('%Y%m%d')}.csv"
        filter_desc = f"Multi-OEM ({args.min_oems}+)"

    # Single OEM filter
    elif args.oem:
        filtered = filter_by_oem(df, args.oem)
        output_name = f"filtered_{args.oem.lower()}_{datetime.now().strftime('%Y%m%d')}.csv"
        filter_desc = args.oem.title()

    else:
        parser.print_help()
        return

    # Sort by ICP score
    filtered = filtered.sort_values('icp_score', ascending=False)

    # Apply top limit if specified
    if args.top:
        filtered = filtered.head(args.top)

    # Stats
    print(f"\n{'=' * 60}")
    print(f"FILTERED: {filter_desc}")
    print(f"{'=' * 60}")
    print(f"Leads found: {len(filtered)}")

    if len(filtered) > 0:
        print(f"Score range: {filtered['icp_score'].min():.0f} - {filtered['icp_score'].max():.0f}")
        print(f"With phone: {filtered['phone'].notna().sum()} ({filtered['phone'].notna().sum()/len(filtered)*100:.1f}%)")
        print(f"With domain: {filtered['domain'].notna().sum()} ({filtered['domain'].notna().sum()/len(filtered)*100:.1f}%)")

        # State distribution
        state_dist = filtered['state'].value_counts().head(5)
        print(f"\nTop states:")
        for state, count in state_dist.items():
            print(f"  {state}: {count}")

        # Save
        output_path = OUTPUT_DIR / output_name
        filtered.to_csv(output_path, index=False)
        print(f"\n✅ Saved to: {output_path}")

        # Preview
        print(f"\nTop 10 {filter_desc} leads:")
        print("-" * 60)
        for idx, row in filtered.head(10).iterrows():
            phone_emoji = "📞" if pd.notna(row.get('phone')) else "  "
            print(f"{phone_emoji} {row['name'][:40]:<40} | Score: {row['icp_score']:.0f} | {row.get('state', 'NA')}")


if __name__ == "__main__":
    main()
