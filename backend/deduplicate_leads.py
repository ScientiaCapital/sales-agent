#!/usr/bin/env python3
"""
Lead Deduplication with Fuzzy Matching
=======================================
Deduplicates leads using multiple strategies:
1. Exact domain match - keep highest scored
2. Fuzzy company name match (>90% similarity)
3. Normalized name matching (strip LLC, Inc, etc.)

Usage:
    python deduplicate_leads.py --input ADVANCED_TOP_500_20251130.csv
    python deduplicate_leads.py --all  # Process all advanced lists
"""

import pandas as pd
import logging
import re
from pathlib import Path
from datetime import datetime
import argparse
from rapidfuzz import fuzz, process
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/final_enrichment_output")

# Common suffixes to strip for normalization
COMPANY_SUFFIXES = [
    r'\s+inc\.?$', r'\s+llc\.?$', r'\s+corp\.?$', r'\s+co\.?$',
    r'\s+ltd\.?$', r'\s+limited$', r'\s+incorporated$',
    r'\s+company$', r'\s+corporation$', r'\s+enterprises?$',
    r'\s+services?$', r'\s+systems?$', r'\s+solutions?$',
    r'\s+group$', r'\s+holdings?$', r',?\s+llc\.?$', r',?\s+inc\.?$',
    r'\s+-\s+.*$',  # Strip location suffixes like "- San Antonio"
]


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for comparison.

    - Lowercase
    - Remove punctuation
    - Strip common suffixes (LLC, Inc, etc.)
    - Remove extra whitespace
    """
    if not name or pd.isna(name):
        return ""

    normalized = str(name).lower().strip()

    # Remove punctuation except hyphens
    normalized = re.sub(r'[^\w\s-]', '', normalized)

    # Strip common suffixes
    for suffix in COMPANY_SUFFIXES:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def dedupe_by_domain(df: pd.DataFrame) -> pd.DataFrame:
    """
    First pass: Deduplicate by exact domain match.
    Keep the record with highest advanced_score.
    """
    logger.info("Pass 1: Deduplicating by exact domain match...")

    before = len(df)

    # Sort by score descending, then drop duplicates keeping first
    df_sorted = df.sort_values('advanced_score', ascending=False)
    df_deduped = df_sorted.drop_duplicates(subset=['domain'], keep='first')

    after = len(df_deduped)
    logger.info(f"  Removed {before - after} exact domain duplicates ({before} -> {after})")

    return df_deduped.reset_index(drop=True)


def dedupe_by_normalized_name(df: pd.DataFrame) -> pd.DataFrame:
    """
    Second pass: Deduplicate by normalized company name.
    Groups companies with same normalized name, keeps highest scored.
    """
    logger.info("Pass 2: Deduplicating by normalized company name...")

    before = len(df)

    # Add normalized name column
    df = df.copy()
    df['normalized_name'] = df['name'].apply(normalize_company_name)

    # Sort by score and drop duplicates on normalized name
    df_sorted = df.sort_values('advanced_score', ascending=False)
    df_deduped = df_sorted.drop_duplicates(subset=['normalized_name'], keep='first')

    # Log examples of merged names
    merged_names = df.groupby('normalized_name').filter(lambda x: len(x) > 1)
    if len(merged_names) > 0:
        logger.info("  Examples of merged company names:")
        for norm_name in merged_names['normalized_name'].unique()[:5]:
            originals = df[df['normalized_name'] == norm_name]['name'].unique()
            if len(originals) > 1:
                logger.info(f"    '{norm_name}' <- {list(originals)}")

    after = len(df_deduped)
    logger.info(f"  Removed {before - after} normalized name duplicates ({before} -> {after})")

    return df_deduped.drop(columns=['normalized_name']).reset_index(drop=True)


def dedupe_by_fuzzy_match(df: pd.DataFrame, threshold: int = 90) -> pd.DataFrame:
    """
    Third pass: Fuzzy match on company names.
    Groups companies with >90% name similarity, keeps highest scored.
    """
    logger.info(f"Pass 3: Fuzzy matching company names (threshold={threshold}%)...")

    before = len(df)

    # Normalize names for comparison
    df = df.copy()
    df['normalized_name'] = df['name'].apply(normalize_company_name)

    # Build clusters of similar names
    names = df['normalized_name'].tolist()
    scores = df['advanced_score'].tolist()

    # Track which indices are merged
    merged_to = {}  # index -> cluster_head_index

    for i, name_i in enumerate(names):
        if i in merged_to:
            continue  # Already merged into another cluster

        for j in range(i + 1, len(names)):
            if j in merged_to:
                continue

            name_j = names[j]

            # Skip if names are very different lengths
            if abs(len(name_i) - len(name_j)) > 10:
                continue

            # Calculate fuzzy similarity
            similarity = fuzz.ratio(name_i, name_j)

            if similarity >= threshold:
                # Merge j into i's cluster (i has higher score due to sort order)
                merged_to[j] = i
                logger.debug(f"  Fuzzy match ({similarity}%): '{name_i}' ~ '{name_j}'")

    # Keep only cluster heads (not merged into anyone else)
    keep_indices = [i for i in range(len(df)) if i not in merged_to]
    df_deduped = df.iloc[keep_indices].copy()

    # Log merge examples
    if merged_to:
        logger.info(f"  Found {len(merged_to)} fuzzy matches:")
        shown = 0
        for j, i in list(merged_to.items())[:10]:
            logger.info(f"    '{names[j]}' merged into '{names[i]}'")
            shown += 1
        if len(merged_to) > shown:
            logger.info(f"    ... and {len(merged_to) - shown} more")

    after = len(df_deduped)
    logger.info(f"  Removed {before - after} fuzzy duplicates ({before} -> {after})")

    return df_deduped.drop(columns=['normalized_name']).reset_index(drop=True)


def deduplicate_leads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run all deduplication passes.
    """
    logger.info(f"\n{'='*60}")
    logger.info("LEAD DEDUPLICATION")
    logger.info(f"{'='*60}")
    logger.info(f"Starting records: {len(df)}")

    # Sort by score first (highest first)
    df = df.sort_values('advanced_score', ascending=False).reset_index(drop=True)

    # Pass 1: Exact domain match
    df = dedupe_by_domain(df)

    # Pass 2: Normalized name
    df = dedupe_by_normalized_name(df)

    # Pass 3: Fuzzy match (92% to avoid false positives like Hassler vs Manns)
    df = dedupe_by_fuzzy_match(df, threshold=92)

    logger.info(f"\nFinal unique leads: {len(df)}")

    return df


def main():
    parser = argparse.ArgumentParser(description='Deduplicate leads with fuzzy matching')
    parser.add_argument('--input', type=str, help='Input CSV file')
    parser.add_argument('--all', action='store_true', help='Process all ADVANCED_TOP files')
    parser.add_argument('--threshold', type=int, default=88, help='Fuzzy match threshold (default: 88)')

    args = parser.parse_args()

    if not args.input and not args.all:
        parser.print_help()
        print("\n  Please specify --input FILE or --all")
        return

    # Find files to process
    if args.all:
        files = list(OUTPUT_DIR.glob("ADVANCED_TOP_*.csv"))
    else:
        files = [OUTPUT_DIR / args.input]

    for input_file in files:
        if not input_file.exists():
            logger.error(f"File not found: {input_file}")
            continue

        logger.info(f"\nProcessing: {input_file.name}")

        # Load data
        df = pd.read_csv(input_file)

        # Deduplicate
        df_deduped = deduplicate_leads(df)

        # Save
        output_file = input_file.parent / f"DEDUPED_{input_file.name}"
        df_deduped.to_csv(output_file, index=False)
        logger.info(f"\nSaved: {output_file}")

        # Summary stats
        logger.info(f"\n{'='*60}")
        logger.info("DEDUPLICATION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Original: {len(pd.read_csv(input_file))} records")
        logger.info(f"Deduped:  {len(df_deduped)} unique companies")

        tier_counts = df_deduped['tier'].value_counts()
        logger.info(f"\nTier distribution:")
        for tier, count in tier_counts.items():
            logger.info(f"  {tier}: {count}")


if __name__ == "__main__":
    main()
