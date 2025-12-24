#!/usr/bin/env python3
"""
Dealer-Scraper Deduplication & Domain Analysis

Analyzes 249K dealer-scraper contractors to determine:
1. How many are duplicates (already in sales-agent Supabase)
2. How many are NEW unique companies
3. Of NEW companies, how many HAVE domains (ready for VLM scraping)
4. Of NEW companies, how many NEED domain discovery first

Uses fuzzy matching to detect duplicates:
- Exact domain match (www.acme.com = acme.com)
- Company name similarity (Levenshtein distance)
- Phone/address matching

Usage:
    python backend/scripts/analyze_dealer_scraper_dedup.py \
        --db-path /path/to/dealer-scraper.db \
        --similarity-threshold 0.85 \
        --output /tmp/dedup_report.json

Output:
    {
        "total_dealer_scraper": 249618,
        "duplicates": 2845,
        "new_unique": 246773,
        "new_with_domain": 142500,
        "new_without_domain": 104273,
        "ready_for_vlm": 142500
    }
"""

import asyncio
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from difflib import SequenceMatcher
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def normalize_domain(url: str) -> str:
    """
    Normalize URL/domain for matching

    Examples:
        https://www.acme.com -> acme.com
        www.acme.com/about -> acme.com
        ACME.COM -> acme.com
    """
    if not url:
        return ""

    # Remove protocol
    if "://" in url:
        url = url.split("://", 1)[1]

    # Remove www.
    if url.startswith("www."):
        url = url[4:]

    # Remove trailing slash and path
    url = url.split("/")[0]

    # Remove port
    url = url.split(":")[0]

    # Remove query params
    url = url.split("?")[0]

    return url.lower().strip()


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for fuzzy matching

    Examples:
        ABC Construction, Inc. -> abc construction
        The Acme Corp -> acme corp
        ACME LLC -> acme
    """
    if not name:
        return ""

    name = name.lower().strip()

    # Remove common suffixes
    suffixes = [
        r'\binc\.?$', r'\bincorporated$', r'\bcorp\.?$', r'\bcorporation$',
        r'\bllc\.?$', r'\bllp\.?$', r'\bltd\.?$', r'\blimited$',
        r'\bco\.?$', r'\bcompany$', r'\b&\s*co\.?$'
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # Remove "the" prefix
    name = re.sub(r'^\bthe\b\s*', '', name, flags=re.IGNORECASE)

    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings (0.0 to 1.0)
    Uses SequenceMatcher for fuzzy matching
    """
    if not str1 or not str2:
        return 0.0

    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def normalize_phone(phone: str) -> str:
    """Normalize phone number for matching"""
    if not phone:
        return ""

    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)

    # Remove leading 1 if present (US country code)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]

    return digits


async def load_dealer_scraper_companies(db_path: str) -> List[Dict]:
    """Load all companies from dealer-scraper SQLite database"""
    print(f"📂 Loading companies from {db_path}...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Actual dealer-scraper schema uses 'contractors' table
    query = """
        SELECT
            id,
            company_name as name,
            website_url as website,
            primary_domain as domain,
            primary_phone as phone,
            street as address,
            city,
            state,
            zip
        FROM contractors
        WHERE is_deleted = 0
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    companies = []
    for row in rows:
        companies.append({
            "id": row["id"],
            "name": row["name"],
            "website": row["website"],
            "domain": row["domain"],
            "phone": row["phone"],
            "address": row["address"],
            "city": row["city"],
            "state": row["state"],
            "zip_code": row["zip"]
        })

    conn.close()

    print(f"✅ Loaded {len(companies):,} companies from dealer-scraper")
    return companies


async def load_sales_agent_companies() -> List[Dict]:
    """Load all companies from sales-agent Supabase"""
    print("📂 Loading companies from sales-agent Supabase...")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    supabase = create_client(supabase_url, supabase_key)

    # Load all companies
    response = supabase.table("dim_companies").select(
        "company_id, company_name, domain, phone, street, city, state, zip"
    ).execute()

    # Normalize field names to match dedup logic
    companies = []
    for row in response.data:
        companies.append({
            "company_id": row["company_id"],
            "company_name": row["company_name"],
            "domain": row.get("domain"),
            "phone": row.get("phone"),
            "address": row.get("street"),  # Map street -> address
            "city": row.get("city"),
            "state": row.get("state"),
            "zip_code": row.get("zip")  # Map zip -> zip_code
        })

    print(f"✅ Loaded {len(companies):,} companies from sales-agent")
    return companies


def is_duplicate(
    dealer_company: Dict,
    sales_company: Dict,
    similarity_threshold: float = 0.85
) -> Tuple[bool, str]:
    """
    Check if dealer-scraper company is a duplicate of sales-agent company

    Returns:
        (is_duplicate: bool, match_reason: str)
    """
    # Extract and normalize domains
    dealer_domain = normalize_domain(
        dealer_company.get("domain") or dealer_company.get("website") or ""
    )
    sales_domain = normalize_domain(sales_company.get("domain") or "")

    # 1. Exact domain match (highest confidence)
    if dealer_domain and sales_domain and dealer_domain == sales_domain:
        return (True, f"exact_domain_match:{dealer_domain}")

    # 2. Fuzzy company name match
    dealer_name = normalize_company_name(dealer_company.get("name") or "")
    sales_name = normalize_company_name(sales_company.get("company_name") or "")

    if dealer_name and sales_name:
        name_similarity = calculate_similarity(dealer_name, sales_name)

        if name_similarity >= similarity_threshold:
            # High name similarity - check additional signals

            # Same state/zip increases confidence
            same_state = (
                dealer_company.get("state") and
                sales_company.get("state") and
                dealer_company["state"].upper() == sales_company["state"].upper()
            )

            same_zip = (
                dealer_company.get("zip_code") and
                sales_company.get("zip_code") and
                dealer_company["zip_code"] == sales_company["zip_code"]
            )

            # Phone number match
            dealer_phone = normalize_phone(dealer_company.get("phone") or "")
            sales_phone = normalize_phone(sales_company.get("phone") or "")
            same_phone = dealer_phone and sales_phone and dealer_phone == sales_phone

            # If high name similarity + (same state OR same phone OR same zip)
            if same_state or same_phone or same_zip:
                return (True, f"fuzzy_name_match:{name_similarity:.2f}+location/phone")

    # 3. Phone number match (if domains don't match, still check phone)
    dealer_phone = normalize_phone(dealer_company.get("phone") or "")
    sales_phone = normalize_phone(sales_company.get("phone") or "")

    if dealer_phone and sales_phone and dealer_phone == sales_phone and len(dealer_phone) == 10:
        # Same phone + different domains might be branch offices - be cautious
        # Only mark as duplicate if also in same state
        same_state = (
            dealer_company.get("state") and
            sales_company.get("state") and
            dealer_company["state"].upper() == sales_company["state"].upper()
        )

        if same_state:
            return (True, f"phone_match:{dealer_phone}")

    return (False, "no_match")


async def analyze_deduplication(
    dealer_companies: List[Dict],
    sales_companies: List[Dict],
    similarity_threshold: float = 0.85
) -> Dict:
    """
    Perform deduplication analysis (OPTIMIZED)

    Returns comprehensive report
    """
    import time
    start_time = time.time()

    print(f"\n🔍 Running deduplication analysis (threshold={similarity_threshold})...")
    print(f"📊 Processing {len(dealer_companies):,} dealer companies vs {len(sales_companies):,} sales companies")

    duplicates = []
    new_unique = []

    # Performance tracking
    domain_matches = 0
    fuzzy_matches = 0

    # Build optimized indexes for fast lookup
    print("🏗️  Building search indexes...")

    # 1. Domain index (exact matches)
    sales_domain_map = {}
    for sc in sales_companies:
        domain = normalize_domain(sc.get("domain") or "")
        if domain:
            if domain not in sales_domain_map:
                sales_domain_map[domain] = []
            sales_domain_map[domain].append(sc)

    # 2. State index (for fuzzy matching - only check same state)
    sales_state_map = {}
    for sc in sales_companies:
        state = sc.get("state", "").upper() if sc.get("state") else None
        if state:
            if state not in sales_state_map:
                sales_state_map[state] = []
            sales_state_map[state].append(sc)

    # 3. Phone index (for fast phone lookups)
    sales_phone_map = {}
    for sc in sales_companies:
        phone = normalize_phone(sc.get("phone") or "")
        if phone and len(phone) == 10:
            if phone not in sales_phone_map:
                sales_phone_map[phone] = []
            sales_phone_map[phone].append(sc)

    print(f"✅ Indexes built: {len(sales_domain_map)} domains, {len(sales_state_map)} states, {len(sales_phone_map)} phones")

    # Check each dealer company
    last_report = 0
    for i, dc in enumerate(dealer_companies):
        # Progress every 1,000 companies
        if i > 0 and (i % 1000 == 0 or i == len(dealer_companies) - 1):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(dealer_companies) - i) / rate if rate > 0 else 0
            print(f"  📍 {i:,}/{len(dealer_companies):,} ({i/len(dealer_companies)*100:.1f}%) | "
                  f"⏱️  {elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining | "
                  f"✅ {domain_matches:,} domain, 🔍 {fuzzy_matches:,} fuzzy, 🆕 {len(new_unique):,} new")

        found_duplicate = False
        match_reason = None

        # OPTIMIZATION 1: Quick domain lookup (O(1))
        dc_domain = normalize_domain(dc.get("domain") or dc.get("website") or "")
        if dc_domain and dc_domain in sales_domain_map:
            duplicates.append({
                "dealer_id": dc["id"],
                "dealer_name": dc["name"],
                "match_reason": f"exact_domain:{dc_domain}",
                "sales_company": sales_domain_map[dc_domain][0]
            })
            found_duplicate = True
            domain_matches += 1

        # OPTIMIZATION 2: Quick phone lookup (O(1))
        if not found_duplicate:
            dc_phone = normalize_phone(dc.get("phone") or "")
            dc_state = dc.get("state", "").upper() if dc.get("state") else None
            if dc_phone and len(dc_phone) == 10 and dc_phone in sales_phone_map:
                # Phone match - verify same state
                for sc in sales_phone_map[dc_phone]:
                    sc_state = sc.get("state", "").upper() if sc.get("state") else None
                    if sc_state and dc_state and sc_state == dc_state:
                        duplicates.append({
                            "dealer_id": dc["id"],
                            "dealer_name": dc["name"],
                            "match_reason": f"phone_match:{dc_phone}",
                            "sales_company": sc
                        })
                        found_duplicate = True
                        fuzzy_matches += 1
                        break

        # OPTIMIZATION 3: Fuzzy matching ONLY against same-state companies (O(k) not O(n))
        if not found_duplicate:
            dc_state = dc.get("state", "").upper() if dc.get("state") else None

            # Get candidate companies (same state only - reduces search space ~50x)
            candidates = sales_state_map.get(dc_state, []) if dc_state else []

            # If no state match, skip fuzzy matching (too expensive without filtering)
            # This prevents the O(n*m) explosion for companies without state data
            if not candidates:
                new_unique.append(dc)
                continue

            # Fuzzy matching against filtered candidates only
            for sc in candidates:
                is_dup, reason = is_duplicate(dc, sc, similarity_threshold)

                if is_dup:
                    duplicates.append({
                        "dealer_id": dc["id"],
                        "dealer_name": dc["name"],
                        "match_reason": reason,
                        "sales_company": sc
                    })
                    found_duplicate = True
                    fuzzy_matches += 1
                    break

        if not found_duplicate:
            new_unique.append(dc)

    # Analyze NEW unique companies
    new_with_domain = []
    new_without_domain = []

    for company in new_unique:
        domain = normalize_domain(company.get("domain") or company.get("website") or "")

        if domain:
            new_with_domain.append(company)
        else:
            new_without_domain.append(company)

    # Performance summary
    total_time = time.time() - start_time
    print(f"\n⚡ Performance Summary:")
    print(f"  Total time: {total_time/60:.1f} minutes ({total_time:.1f}s)")
    print(f"  Processing rate: {len(dealer_companies)/total_time:.0f} companies/second")
    print(f"  Domain matches: {domain_matches:,} (instant)")
    print(f"  Fuzzy matches: {fuzzy_matches:,} (state-filtered)")
    print(f"  NEW companies: {len(new_unique):,}")

    # Build report
    report = {
        "analysis_date": "2025-12-24",
        "similarity_threshold": similarity_threshold,
        "total_dealer_scraper": len(dealer_companies),
        "total_sales_agent": len(sales_companies),
        "duplicates": len(duplicates),
        "new_unique": len(new_unique),
        "new_with_domain": len(new_with_domain),
        "new_without_domain": len(new_without_domain),
        "ready_for_vlm_scraping": len(new_with_domain),
        "need_domain_discovery": len(new_without_domain),
        "duplicate_breakdown": {},
        "performance": {
            "total_time_seconds": total_time,
            "processing_rate": len(dealer_companies)/total_time,
            "domain_matches": domain_matches,
            "fuzzy_matches": fuzzy_matches
        },
        "sample_duplicates": duplicates[:20] if duplicates else [],
        "sample_new_with_domain": new_with_domain[:20] if new_with_domain else [],
        "sample_new_without_domain": new_without_domain[:20] if new_without_domain else []
    }

    # Count duplicate match reasons
    for dup in duplicates:
        reason_type = dup["match_reason"].split(":")[0]
        report["duplicate_breakdown"][reason_type] = report["duplicate_breakdown"].get(reason_type, 0) + 1

    return report


def print_report(report: Dict):
    """Print human-readable report"""
    print("\n" + "="*70)
    print(" DEALER-SCRAPER DEDUPLICATION ANALYSIS REPORT")
    print("="*70)
    print(f"\n📊 Dataset Sizes:")
    print(f"  Dealer-Scraper:  {report['total_dealer_scraper']:,} companies")
    print(f"  Sales-Agent:     {report['total_sales_agent']:,} companies")

    print(f"\n🔍 Deduplication Results (threshold={report['similarity_threshold']}):")
    print(f"  Duplicates:      {report['duplicates']:,} ({report['duplicates']/report['total_dealer_scraper']*100:.1f}%)")
    print(f"  NEW Unique:      {report['new_unique']:,} ({report['new_unique']/report['total_dealer_scraper']*100:.1f}%)")

    print(f"\n🌐 Domain Analysis (NEW companies only):")
    print(f"  WITH domain:     {report['new_with_domain']:,} ({report['new_with_domain']/report['new_unique']*100:.1f}% of NEW)")
    print(f"  WITHOUT domain:  {report['new_without_domain']:,} ({report['new_without_domain']/report['new_unique']*100:.1f}% of NEW)")

    print(f"\n🚀 Pipeline Readiness:")
    print(f"  ✅ Ready for VLM scraping NOW:  {report['ready_for_vlm_scraping']:,}")
    print(f"  ⏳ Need domain discovery first: {report['need_domain_discovery']:,}")

    print(f"\n📋 Duplicate Match Breakdown:")
    for reason, count in sorted(report['duplicate_breakdown'].items(), key=lambda x: -x[1]):
        print(f"  {reason:30} {count:,}")

    print("\n" + "="*70 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Dealer-Scraper Deduplication & Domain Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to dealer-scraper SQLite database"
    )

    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Company name similarity threshold (0.0-1.0, default: 0.85)"
    )

    parser.add_argument(
        "--output",
        help="Output JSON file path (default: /tmp/dedup_report.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.db_path).exists():
        print(f"❌ Error: Database not found at {args.db_path}")
        sys.exit(1)

    if not 0.0 <= args.similarity_threshold <= 1.0:
        print(f"❌ Error: Similarity threshold must be between 0.0 and 1.0")
        sys.exit(1)

    # Load data
    dealer_companies = await load_dealer_scraper_companies(args.db_path)
    sales_companies = await load_sales_agent_companies()

    # Run analysis
    report = await analyze_deduplication(
        dealer_companies,
        sales_companies,
        args.similarity_threshold
    )

    # Print report
    print_report(report)

    # Save to file
    output_path = args.output or "/tmp/dedup_report.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"📄 Full report saved to: {output_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
