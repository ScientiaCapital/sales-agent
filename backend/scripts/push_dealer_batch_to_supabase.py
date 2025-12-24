#!/usr/bin/env python3
"""
Push Dealer-Scraper Batch to Sales-Agent Supabase

Pushes a small batch of NEW dealer-scraper companies (WITH domains) to sales-agent
for enrichment pipeline testing.

Usage:
    python backend/scripts/push_dealer_batch_to_supabase.py --batch 5
    python backend/scripts/push_dealer_batch_to_supabase.py --batch 10 --dry-run
"""

import asyncio
import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")


async def get_batch_from_dealer_scraper(db_path: str, batch_size: int = 5) -> List[Dict]:
    """Get batch of NEW companies WITH domains from dealer-scraper"""
    print(f"📂 Loading {batch_size} companies from dealer-scraper...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get companies WITH domains that haven't been pushed yet
    # Filter OUT non-ICP: sheet metal, aluminum, roofing, siding, etc.
    query = f"""
        SELECT
            id,
            company_name,
            normalized_name,
            primary_domain,
            website_url,
            primary_phone,
            primary_email,
            street,
            city,
            state,
            zip,
            company_linkedin_url,
            year_founded,
            employee_count,
            estimated_revenue,
            icp_score,
            icp_tier,
            is_resimercial
        FROM contractors
        WHERE is_deleted = 0
            AND pushed_to_sales_agent = 0
            AND primary_domain IS NOT NULL
            AND primary_domain != ''
            -- CRITICAL: Only verified, reachable domains
            AND domain_verified_at IS NOT NULL
            AND domain_is_valid = 1
            -- Exclude non-ICP companies (KEEP roofing - they're ICP!)
            AND LOWER(company_name) NOT LIKE '%sheet metal%'
            AND LOWER(company_name) NOT LIKE '%aluminum%'
            AND LOWER(company_name) NOT LIKE '%siding%'
            AND LOWER(company_name) NOT LIKE '%window%'
            AND LOWER(company_name) NOT LIKE '%landscap%'
            AND LOWER(company_name) NOT LIKE '%painting%'
            AND LOWER(company_name) NOT LIKE '%drywall%'
            AND LOWER(company_name) NOT LIKE '%concrete%'
            AND LOWER(company_name) NOT LIKE '%masonry%'
            AND LOWER(company_name) NOT LIKE '%flooring%'
            AND LOWER(company_name) NOT LIKE '%carpenter%'
        ORDER BY RANDOM()
        LIMIT {batch_size}
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    companies = []
    for row in rows:
        # Use primary_domain first, fallback to extracting from website_url
        domain = row["primary_domain"]
        if not domain and row["website_url"]:
            # Extract domain from website_url
            url = row["website_url"]
            if "://" in url:
                url = url.split("://", 1)[1]
            if url.startswith("www."):
                url = url[4:]
            domain = url.split("/")[0].split(":")[0].split("?")[0].lower()

        companies.append({
            "dealer_id": row["id"],
            "company_name": row["company_name"],
            "normalized_name": row["normalized_name"],
            "domain": domain,
            "website": row["website_url"],
            "phone": row["primary_phone"],
            "email": row["primary_email"],
            "street": row["street"],
            "city": row["city"],
            "state": row["state"],
            "zip": row["zip"],
            "linkedin_url": row["company_linkedin_url"],
            "year_founded": row["year_founded"],
            "employee_count": row["employee_count"],
            "estimated_revenue": row["estimated_revenue"],
            "icp_score": row["icp_score"] or 0,
            "icp_tier": row["icp_tier"] or "BRONZE",
            "is_resimercial": bool(row["is_resimercial"])
        })

    conn.close()

    print(f"✅ Loaded {len(companies)} companies")
    return companies


async def push_to_supabase(companies: List[Dict], dry_run: bool = False) -> List[str]:
    """Push companies to sales-agent Supabase"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    supabase = create_client(supabase_url, supabase_key)

    pushed_ids = []

    for i, company in enumerate(companies, 1):
        print(f"\n{i}. {company['company_name']}")
        print(f"   Domain: {company['domain']}")
        print(f"   State: {company['state']}, City: {company['city']}")
        print(f"   ICP Tier: {company['icp_tier']} (score: {company['icp_score']})")

        if dry_run:
            print("   [DRY RUN] Would insert to Supabase")
            continue

        # Insert to dim_companies
        data = {
            "company_name": company["company_name"],
            "normalized_name": company["normalized_name"],
            "domain": company["domain"],
            "website": company["website"],
            "phone": company["phone"],
            "street": company["street"],
            "city": company["city"],
            "state": company["state"],
            "zip": company["zip"],
            "icp_score": company["icp_score"],
            "icp_tier": company["icp_tier"],
            "source_type": "dealer-scraper",
            "current_stage": "imported",
            "first_seen_at": datetime.utcnow().isoformat(),
        }

        try:
            response = supabase.table("dim_companies").insert(data).execute()
            company_id = response.data[0]["company_id"]
            pushed_ids.append(company_id)
            print(f"   ✅ Pushed to Supabase (company_id: {company_id})")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    return pushed_ids


async def mark_as_pushed(db_path: str, dealer_ids: List[int], dry_run: bool = False):
    """Mark companies as pushed in dealer-scraper database"""
    if dry_run:
        print(f"\n[DRY RUN] Would mark {len(dealer_ids)} companies as pushed")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for dealer_id in dealer_ids:
        cursor.execute(
            "UPDATE contractors SET pushed_to_sales_agent = 1, pushed_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), dealer_id)
        )

    conn.commit()
    conn.close()

    print(f"\n✅ Marked {len(dealer_ids)} companies as pushed in dealer-scraper")


async def main():
    parser = argparse.ArgumentParser(
        description="Push dealer-scraper batch to sales-agent Supabase"
    )

    parser.add_argument(
        "--db-path",
        default="/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/pipeline.db",
        help="Path to dealer-scraper SQLite database"
    )

    parser.add_argument(
        "--batch",
        type=int,
        default=5,
        help="Number of companies to push (default: 5)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to database"
    )

    args = parser.parse_args()

    # Validate database exists
    if not Path(args.db_path).exists():
        print(f"❌ Error: Database not found at {args.db_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f" PUSH DEALER-SCRAPER BATCH TO SALES-AGENT")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made\n")

    # Get batch
    companies = await get_batch_from_dealer_scraper(args.db_path, args.batch)

    if not companies:
        print("❌ No companies found to push")
        sys.exit(0)

    # Push to Supabase
    print(f"\n📤 Pushing {len(companies)} companies to sales-agent Supabase...\n")
    company_ids = await push_to_supabase(companies, args.dry_run)

    # Mark as pushed
    dealer_ids = [c["dealer_id"] for c in companies]
    await mark_as_pushed(args.db_path, dealer_ids, args.dry_run)

    print(f"\n{'='*60}")
    print(f" SUMMARY")
    print(f"{'='*60}\n")
    print(f"  Companies processed: {len(companies)}")
    print(f"  Successfully pushed: {len(company_ids)}")
    print(f"\n✅ Batch push complete!\n")

    if not args.dry_run and company_ids:
        print("Next steps:")
        print("  1. Run free enrichment: python backend/run_free_enrichment.py --batch 5")
        print("  2. Run VLM enrichment: python backend/enrich_vlm_batch.py --batch 5")
        print("  3. Run Browserbase: python backend/run_browserbase_enrichment.py --batch 5")
        print("")


if __name__ == "__main__":
    asyncio.run(main())
