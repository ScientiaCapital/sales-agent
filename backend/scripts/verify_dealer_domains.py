#!/usr/bin/env python3
"""
Verify Dealer-Scraper Domains
==============================
Checks if domains are reachable before pushing to enrichment pipeline.

This should run FIRST before any enrichment to ensure we only process
companies with valid, reachable websites.

Usage:
    python backend/scripts/verify_dealer_domains.py --batch 100  # Verify 100
    python backend/scripts/verify_dealer_domains.py --all        # All domains
    python backend/scripts/verify_dealer_domains.py --dry-run    # Test only
"""

import asyncio
import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Config
TIMEOUT = 10  # seconds
MAX_CONCURRENT = 10  # parallel requests


async def verify_domain(domain: str) -> Dict:
    """Check if domain is reachable"""
    if not domain:
        return {"domain": domain, "valid": False, "status": "empty"}

    # Normalize domain
    if not domain.startswith('http'):
        test_url = f'https://{domain}'
    else:
        test_url = domain

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.get(test_url)

            # Consider 200, 301, 302, 403 (behind firewall) as valid
            if response.status_code in [200, 301, 302, 403]:
                return {
                    "domain": domain,
                    "valid": True,
                    "status": response.status_code,
                    "final_url": str(response.url)
                }
            else:
                return {
                    "domain": domain,
                    "valid": False,
                    "status": response.status_code
                }

    except httpx.TimeoutException:
        return {"domain": domain, "valid": False, "status": "timeout"}
    except httpx.ConnectError:
        return {"domain": domain, "valid": False, "status": "connection_error"}
    except Exception as e:
        return {"domain": domain, "valid": False, "status": f"error: {str(e)[:50]}"}


async def verify_batch(domains: List[str]) -> List[Dict]:
    """Verify multiple domains in parallel"""
    tasks = [verify_domain(d) for d in domains]
    return await asyncio.gather(*tasks)


def get_unverified_domains(db_path: str, batch_size: int = None) -> List[Dict]:
    """Get domains that haven't been verified yet"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get companies with domains that haven't been verified
    query = """
        SELECT
            id,
            company_name,
            primary_domain
        FROM contractors
        WHERE is_deleted = 0
            AND primary_domain IS NOT NULL
            AND primary_domain != ''
            AND domain_verified_at IS NULL
            -- Exclude non-ICP by name (KEEP roofing!)
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
    """

    if batch_size:
        query += f" LIMIT {batch_size}"

    cursor.execute(query)
    rows = cursor.fetchall()

    companies = [dict(row) for row in rows]
    conn.close()

    return companies


def mark_domain_verified(db_path: str, contractor_id: int, is_valid: bool, status: str):
    """Mark domain as verified in database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contractors
        SET domain_verified_at = ?,
            domain_is_valid = ?,
            domain_check_status = ?
        WHERE id = ?
    """, (datetime.utcnow().isoformat(), 1 if is_valid else 0, status, contractor_id))

    conn.commit()
    conn.close()


async def main():
    parser = argparse.ArgumentParser(description='Verify dealer-scraper domains')
    parser.add_argument(
        '--db-path',
        default='/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/pipeline.db',
        help='Path to dealer-scraper database'
    )
    parser.add_argument('--batch', type=int, default=100, help='Batch size')
    parser.add_argument('--all', action='store_true', help='Verify ALL domains')
    parser.add_argument('--dry-run', action='store_true', help='Test without saving')

    args = parser.parse_args()

    # Check if columns exist (need to add them)
    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()

    # Add columns if they don't exist
    try:
        cursor.execute("ALTER TABLE contractors ADD COLUMN domain_verified_at TEXT")
        print("Added column: domain_verified_at")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE contractors ADD COLUMN domain_is_valid INTEGER DEFAULT 0")
        print("Added column: domain_is_valid")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE contractors ADD COLUMN domain_check_status TEXT")
        print("Added column: domain_check_status")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

    print("\n" + "="*70)
    print(" DOMAIN VERIFICATION")
    print("="*70)

    # Get unverified companies
    batch_size = None if args.all else args.batch
    companies = get_unverified_domains(args.db_path, batch_size)

    print(f"\nCompanies to verify: {len(companies)}")

    if args.dry_run:
        print("\n[DRY RUN] First 10 domains to check:")
        for i, c in enumerate(companies[:10], 1):
            print(f"  {i}. {c['company_name'][:50]:50s} | {c['primary_domain']}")
        return

    # Process in chunks to avoid overwhelming the network
    valid_count = 0
    invalid_count = 0

    for i in range(0, len(companies), MAX_CONCURRENT):
        chunk = companies[i:i + MAX_CONCURRENT]
        domains = [c['primary_domain'] for c in chunk]

        print(f"\nVerifying batch {i//MAX_CONCURRENT + 1} ({i+1}-{min(i+MAX_CONCURRENT, len(companies))})...")

        results = await verify_batch(domains)

        # Save results
        for company, result in zip(chunk, results):
            status_icon = "✅" if result['valid'] else "❌"
            print(f"  {status_icon} {company['company_name'][:40]:40s} | {result['status']}")

            if result['valid']:
                valid_count += 1
            else:
                invalid_count += 1

            # Mark in database
            mark_domain_verified(
                args.db_path,
                company['id'],
                result['valid'],
                str(result['status'])
            )

        await asyncio.sleep(1)  # Rate limit between batches

    # Summary
    print("\n" + "="*70)
    print(" VERIFICATION SUMMARY")
    print("="*70)
    print(f"  Total checked: {len(companies)}")
    print(f"  ✅ Valid: {valid_count} ({valid_count/len(companies)*100:.1f}%)")
    print(f"  ❌ Invalid: {invalid_count} ({invalid_count/len(companies)*100:.1f}%)")
    print(f"\n✅ Domain verification complete!")
    print(f"\nNext: python backend/scripts/push_dealer_batch_to_supabase.py --batch 5")


if __name__ == '__main__':
    asyncio.run(main())
