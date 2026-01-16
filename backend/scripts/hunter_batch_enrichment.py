#!/usr/bin/env python3
"""
Hunter.io Batch Enrichment with Logging & Supabase Save
========================================================
Enriches domains in batches of 5, logs results, saves to Supabase.

Usage:
    python app/scripts/hunter_batch_enrichment.py --start 0 --batch 5
    python app/scripts/hunter_batch_enrichment.py --start 50 --batch 10

Author: Claude + Tim
Date: Jan 2026
"""

import argparse
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from supabase import create_client

# Load environment
script_dir = Path(__file__).resolve().parent
for env_path in [script_dir.parent.parent.parent / '.env', script_dir.parent.parent / '.env']:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

# Config
HUNTER_API_KEY = os.getenv('HUNTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

OUTPUT_DIR = Path(__file__).parent / "data" / "hunter_enrichment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOMAINS_FILE = OUTPUT_DIR / "HVAC_MULTITRADE_DOMAINS_TO_ENRICH.txt"
RESULTS_FILE = OUTPUT_DIR / f"hunter_results_{datetime.now().strftime('%Y%m%d')}.csv"
LOG_FILE = OUTPUT_DIR / f"hunter_log_{datetime.now().strftime('%Y%m%d')}.txt"


def log(message: str):
    """Log to file and console."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


async def search_domain(domain: str) -> dict:
    """Search Hunter.io for emails at a domain."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            'https://api.hunter.io/v2/domain-search',
            params={
                'domain': domain,
                'api_key': HUNTER_API_KEY,
                'limit': 10
            }
        )
        return response.json()


def save_to_csv(results: list):
    """Append results to CSV file."""
    file_exists = RESULTS_FILE.exists()

    with open(RESULTS_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'domain', 'organization', 'email', 'first_name', 'last_name',
            'position', 'phone_number', 'confidence', 'enriched_at'
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)


async def save_to_supabase(supabase, results: list):
    """Save enrichment results to Supabase."""
    if not results:
        return

    # Check if hunter_enrichment table exists, if not we'll save to a staging table
    for result in results:
        try:
            # Try to find matching company by domain
            company_result = supabase.table('dim_companies').select('company_id').eq('domain', result['domain']).limit(1).execute()

            if company_result.data:
                company_id = company_result.data[0]['company_id']

                # Check if contact already exists
                existing = supabase.table('dim_contacts').select('contact_id').eq('email', result['email']).limit(1).execute()

                if not existing.data:
                    # Skip if no name info (DB constraint requires name)
                    first_name = result['first_name'] if result['first_name'] else None
                    last_name = result['last_name'] if result['last_name'] else None

                    if not first_name and not last_name:
                        log(f"  [SKIP] No name: {result['email']}")
                        continue

                    # Insert new contact
                    contact_data = {
                        'company_id': company_id,
                        'email': result['email'],
                        'first_name': first_name,
                        'last_name': last_name,
                        'full_name': f"{first_name or ''} {last_name or ''}".strip() or None,
                        'title': result['position'] if result['position'] else None,
                        'phone': result.get('phone_number') if result.get('phone_number') else None,
                        'confidence': result['confidence'],
                        'source': 'hunter.io',
                        'is_atl': is_atl_title(result['position']),
                    }
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    log(f"  [SUPABASE] Added: {result['email']}")
                else:
                    log(f"  [SUPABASE] Exists: {result['email']}")
        except Exception as e:
            log(f"  [ERROR] Supabase save failed for {result['email']}: {e}")


def is_atl_title(title: str) -> bool:
    """Check if title indicates Above The Line decision maker."""
    if not title:
        return False
    title_lower = title.lower()
    atl_keywords = [
        'owner', 'president', 'ceo', 'chief', 'vp', 'vice president',
        'director', 'manager', 'partner', 'founder', 'principal',
        'executive', 'general manager', 'gm', 'operations'
    ]
    return any(kw in title_lower for kw in atl_keywords)


async def run_batch(start: int, batch_size: int):
    """Run enrichment on a batch of domains."""
    log(f"\n{'='*60}")
    log(f"HUNTER.IO BATCH ENRICHMENT")
    log(f"Start: {start}, Batch: {batch_size}")
    log(f"{'='*60}")

    # Load domains
    if not DOMAINS_FILE.exists():
        log(f"[ERROR] Domains file not found: {DOMAINS_FILE}")
        return

    with open(DOMAINS_FILE) as f:
        all_domains = [line.strip() for line in f if line.strip()]

    log(f"Total domains available: {len(all_domains)}")

    # Get batch
    domains = all_domains[start:start + batch_size]
    if not domains:
        log(f"[DONE] No more domains to process (start={start})")
        return

    log(f"Processing domains {start+1} to {start+len(domains)}")

    supabase = get_supabase()
    batch_results = []
    total_emails = 0

    for i, domain in enumerate(domains):
        log(f"\n[{start+i+1}/{start+len(domains)}] {domain}")

        try:
            result = await search_domain(domain)

            if 'data' in result:
                data = result['data']
                emails = data.get('emails', [])
                org = data.get('organization', 'Unknown')

                log(f"  Organization: {org}")
                log(f"  Emails found: {len(emails)}")

                for email in emails:
                    email_result = {
                        'domain': domain,
                        'organization': org,
                        'email': email.get('value'),
                        'first_name': email.get('first_name'),
                        'last_name': email.get('last_name'),
                        'position': email.get('position'),
                        'phone_number': email.get('phone_number'),
                        'confidence': email.get('confidence', 0),
                        'enriched_at': datetime.now().isoformat()
                    }
                    batch_results.append(email_result)

                    name = f"{email.get('first_name', '')} {email.get('last_name', '')}".strip()
                    pos = email.get('position', '')
                    phone = email.get('phone_number', '')
                    atl = '★ATL' if is_atl_title(pos) else ''
                    phone_flag = f'📞{phone}' if phone else ''
                    log(f"    {email.get('value')} - {name} ({pos}) {atl} {phone_flag}")

                total_emails += len(emails)
            else:
                log(f"  No results or error: {result.get('errors', 'unknown')}")

            await asyncio.sleep(0.5)  # Rate limit

        except Exception as e:
            log(f"  [ERROR] {e}")

    # Save results
    log(f"\n{'='*60}")
    log(f"SAVING RESULTS")
    log(f"{'='*60}")

    if batch_results:
        save_to_csv(batch_results)
        log(f"[CSV] Saved {len(batch_results)} emails to {RESULTS_FILE.name}")

        await save_to_supabase(supabase, batch_results)
        log(f"[SUPABASE] Contacts synced")

    # Summary
    log(f"\n{'='*60}")
    log(f"BATCH COMPLETE")
    log(f"{'='*60}")
    log(f"Domains processed: {len(domains)}")
    log(f"Emails found: {total_emails}")
    log(f"Next batch: --start {start + batch_size}")
    log(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Hunter.io Batch Enrichment")
    parser.add_argument('--start', type=int, default=0, help='Starting domain index')
    parser.add_argument('--batch', type=int, default=5, help='Batch size')
    args = parser.parse_args()

    if not HUNTER_API_KEY:
        print("[ERROR] HUNTER_API_KEY not set")
        return

    asyncio.run(run_batch(args.start, args.batch))


if __name__ == "__main__":
    main()
