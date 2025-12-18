#!/usr/bin/env python3
"""
Hunter.io Enrichment Service
============================

Enriches companies with Hunter.io domain search to find:
- ATL contacts with verified emails
- Direct phone numbers
- LinkedIn URLs
- Email confidence scores

Cost: ~$0.01 per domain searched
Rate Limit: Hunter.io has hourly limits, so we batch carefully.

Usage:
    cd backend
    python enrich_hunter.py --test --domain example.com
    python enrich_hunter.py --test --limit 3
    python enrich_hunter.py --auto --limit 100
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.hunter_service import HunterService

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
HUNTER_API_KEY = os.getenv('HUNTER_API_KEY')

BATCH_SIZE = 5
RATE_LIMIT_DELAY = 0.5  # 0.5 seconds between companies (Hunter.io allows 15/sec, we use 2/sec)
LOG_FILE = Path(__file__).parent / 'logs' / 'enrichment_log.json'


def log_enrichment_run(
    companies_data: List[Dict],
    total_cost: float,
    source: str = 'hunter_io'
):
    """Log enrichment run to JSON file for tracking and reporting.

    companies_data: List of dicts with company_name, domain, contacts_found, atl, btl
    """
    try:
        # Ensure logs directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing log or create new
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                log_data = json.load(f)
        else:
            log_data = {
                "enrichment_runs": [],
                "summary": {
                    "total_companies_enriched": 0,
                    "total_contacts_found": 0,
                    "total_cost_usd": 0.0,
                    "total_atl_contacts": 0,
                    "total_btl_contacts": 0
                }
            }

        # Calculate totals from companies_data
        total_contacts = sum(c.get('contacts_found', 0) for c in companies_data)
        total_atl = sum(c.get('atl', 0) for c in companies_data)
        total_btl = sum(c.get('btl', 0) for c in companies_data)

        # Add this run with per-company breakdown
        run_entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": source,
            "companies_enriched": len(companies_data),
            "contacts_found": total_contacts,
            "atl_contacts": total_atl,
            "btl_contacts": total_btl,
            "cost_usd": round(total_cost, 2),
            "companies": companies_data  # Per-company breakdown
        }
        log_data["enrichment_runs"].append(run_entry)

        # Update summary
        log_data["summary"]["total_companies_enriched"] += len(companies_data)
        log_data["summary"]["total_contacts_found"] += total_contacts
        log_data["summary"]["total_cost_usd"] = round(log_data["summary"]["total_cost_usd"] + total_cost, 2)
        log_data["summary"]["total_atl_contacts"] += total_atl
        log_data["summary"]["total_btl_contacts"] += total_btl

        # Save
        with open(LOG_FILE, 'w') as f:
            json.dump(log_data, f, indent=2)

        print(f"  📊 Logged to {LOG_FILE}")
    except Exception as e:
        print(f"  ⚠️  Logging error: {e}")


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_companies_for_hunter_enrichment(supabase, batch_size: int, test_domains: Optional[List[str]] = None):
    """Get companies that need Hunter.io enrichment.

    Criteria:
    - Have domain (required)
    - Don't have hunter_enriched_at yet (not enriched by Hunter.io)
    - Not from Close CRM archive (close_lead_id is NULL)
    """
    if test_domains:
        # Test mode: get specific domains
        companies = []
        for domain in test_domains[:5]:  # Max 5 for test
            result = supabase.table('dim_companies')\
                .select('company_id, company_name, domain')\
                .eq('domain', domain)\
                .limit(1)\
                .execute()
            if result.data:
                companies.append(result.data[0])
        return companies

    # Normal mode: get companies with domains that haven't been Hunter.io enriched
    # Use hunter_enriched_at timestamp (more efficient than NOT IN with contact table)
    # CRITICAL: Exclude Close CRM archive leads (they already exist in dim_companies_close)
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, icp_score')\
        .not_.is_('domain', 'null')\
        .is_('close_lead_id', 'null')\
        .is_('hunter_enriched_at', 'null')\
        .order('icp_score', desc=True)\
        .limit(batch_size)\
        .execute()
    return result.data


async def enrich_company_with_hunter(
    hunter: HunterService,
    company_id: str,
    company_name: str,
    domain: str,
    batch_id: str,
    supabase
) -> Dict[str, Any]:
    """Enrich one company with Hunter.io domain search.

    Returns dict with:
    - contacts: List of ATL contacts with emails, phones, LinkedIn
    - success: bool
    - error: str if failed
    - latency_ms: response time in milliseconds
    """
    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'contacts': [],
        'error': '',
        'cost': 0.0,
        'latency_ms': 0
    }

    try:
        # Track response time
        start_time = time.time()

        # Hunter.io domain search (gets ALL contacts with emails - ATL and BTL)
        contacts = await hunter.domain_search(domain, limit=25, atl_only=False)

        # Calculate latency
        response_time_ms = (time.time() - start_time) * 1000
        result['latency_ms'] = int(response_time_ms)

        if contacts:
            result['contacts'] = contacts
            result['success'] = True
            result['cost'] = 0.01  # Hunter.io cost per domain search
        else:
            result['error'] = 'No contacts found'

    except Exception as e:
        result['error'] = str(e)[:100]
        result['latency_ms'] = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0

    # Log enrichment attempt to fact_enrichment_attempts
    contacts = result.get('contacts', [])
    attempt_data = {
        'company_id': str(company_id) if company_id else None,
        'company_name': company_name,
        'domain': domain,
        'source': 'hunter_io',
        'success': result['success'],
        'contacts_found': len(contacts),
        'atl_found': len([c for c in contacts if c.get('is_atl')]),
        'btl_found': len([c for c in contacts if not c.get('is_atl')]),
        'emails_found': len([c for c in contacts if c.get('email')]),
        'phones_found': len([c for c in contacts if c.get('phone_number')]),
        'cost_usd': result['cost'],
        'latency_ms': result['latency_ms'],
        'batch_id': str(batch_id),
        'attempted_at': datetime.utcnow().isoformat()
    }

    try:
        supabase.table('fact_enrichment_attempts').insert(attempt_data).execute()
    except Exception as e:
        print(f"\n    ⚠️  Failed to log enrichment attempt: {e}")

    return result


def sync_hunter_data_to_supabase(supabase, results: List[Dict[str, Any]]) -> tuple:
    """Sync Hunter.io enrichment data to Supabase.

    Returns: (companies_updated, contacts_added, total_cost)
    """
    companies_updated = 0
    contacts_added = 0
    total_cost = 0.0

    for r in results:
        company_id = r['company_id']
        contacts = r.get('contacts', [])
        cost = r.get('cost', 0.0)
        total_cost += cost

        # Mark company as Hunter.io checked (even if no contacts found)
        # This prevents re-checking the same companies
        if not r['success'] and r.get('error') == 'No contacts found':
            # Set hunter_enriched_at timestamp to prevent re-checking
            try:
                supabase.table('dim_companies').update({
                    'hunter_enriched_at': datetime.utcnow().isoformat()
                }).eq('company_id', company_id).execute()
                companies_updated += 1
            except Exception as e:
                print(f"    Company update error: {e}")
            continue
        elif not r['success']:
            # Real error (not just "no contacts") - skip
            continue

        # Update company with Hunter.io enrichment timestamp
        update_data = {
            'last_enriched_at': datetime.utcnow().isoformat(),
            'hunter_enriched_at': datetime.utcnow().isoformat()  # Track Hunter.io specifically
        }

        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            print(f"    Company update error: {e}")
        
        # Add contacts from Hunter.io (ALL contacts - ATL and BTL)
        for contact in contacts:
            email = contact.get('email')
            if not email:
                continue

            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            # Allow contacts without names (generic emails like info@, contact@)
            # They're still valuable for company outreach

            title = contact.get('position', '')
            phone = contact.get('phone_number')
            linkedin_url = contact.get('linkedin')
            confidence = contact.get('confidence', 0)
            
            # Build full_name properly (avoid "None None")
            full_name = name[:100] if name else None

            # Get verification status and twitter
            verification = contact.get('verification', {})
            is_validated = verification.get('status') == 'valid' if isinstance(verification, dict) else None
            twitter = contact.get('twitter')

            contact_data = {
                'company_id': company_id,
                'full_name': full_name,
                'first_name': contact.get('first_name', '')[:50] if contact.get('first_name') else None,
                'last_name': contact.get('last_name', '')[:50] if contact.get('last_name') else None,
                'email': email,
                'title': title[:100] if title else None,
                'phone': phone,
                'linkedin_url': linkedin_url,
                'twitter_handle': twitter,
                'is_atl': contact.get('is_atl', False),
                'source': 'hunter_io',
                'confidence': confidence,
                'seniority': contact.get('seniority'),
                'department': contact.get('department'),
                'validated': is_validated,
            }
            
            try:
                # Check if contact already exists (by email)
                existing = supabase.table('dim_contacts')\
                    .select('contact_id, phone, linkedin_url, confidence')\
                    .eq('company_id', company_id)\
                    .eq('email', email)\
                    .execute()

                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
                else:
                    # Update with Hunter.io data if we have better info
                    existing_contact = existing.data[0]
                    update_contact = {}

                    # Add phone if we have it and they don't
                    if phone and not existing_contact.get('phone'):
                        update_contact['phone'] = phone
                    # Add LinkedIn if we have it and they don't
                    if linkedin_url and not existing_contact.get('linkedin_url'):
                        update_contact['linkedin_url'] = linkedin_url
                    # Update confidence if ours is higher
                    if confidence > (existing_contact.get('confidence') or 0):
                        update_contact['confidence'] = confidence

                    if update_contact:
                        supabase.table('dim_contacts')\
                            .update(update_contact)\
                            .eq('contact_id', existing_contact['contact_id'])\
                            .execute()
            except Exception as e:
                print(f"    Contact error ({email}): {e}")
    
    return companies_updated, contacts_added, total_cost


async def run_hunter_batch(hunter: HunterService, supabase, companies: List[Dict], test_mode: bool = False) -> List[Dict[str, Any]]:
    """Run Hunter.io enrichment on a batch of companies."""
    results = []
    batch_id = uuid.uuid4()  # Generate batch_id for this enrichment run

    for i, company in enumerate(companies, 1):
        # Rate limiting: delay between companies
        if test_mode and i > 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)
        elif not test_mode and i > 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)

        company_id = company['company_id']
        name = company['company_name']
        domain = company['domain']

        print(f"  [{i}/{len(companies)}] {name} ({domain})...", end=" ", flush=True)

        result = await enrich_company_with_hunter(hunter, company_id, name, domain, str(batch_id), supabase)
        results.append(result)

        if result['success']:
            contacts_count = len(result['contacts'])
            atl_count = sum(1 for c in result['contacts'] if c.get('is_atl'))
            cost = result['cost']
            latency = result.get('latency_ms', 0)

            print(f"✅ ({atl_count} ATL, {contacts_count - atl_count} BTL, ${cost:.2f}, {latency}ms)")
        else:
            print(f"❌ {result['error']}")

    return results


async def main():
    parser = argparse.ArgumentParser(description='Hunter.io enrichment service')
    parser.add_argument('--auto', action='store_true', help='Run continuously without prompts')
    parser.add_argument('--limit', type=int, default=0, help='Max companies to process (0=unlimited)')
    parser.add_argument('--test', action='store_true', help='Test mode: max 5 companies, adds rate limiting')
    parser.add_argument('--domain', type=str, help='Test single domain (e.g., acmeheating.com)')
    parser.add_argument('--domains', type=str, help='Test multiple domains, comma-separated (max 5)')
    args = parser.parse_args()
    
    # Validate
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing Supabase environment variables")
        sys.exit(1)
    
    if not HUNTER_API_KEY:
        print("ERROR: Missing HUNTER_API_KEY environment variable")
        sys.exit(1)
    
    supabase = get_supabase()
    hunter = HunterService()
    
    # Test mode handling
    if args.test:
        print(f"\n{'='*60}")
        print(f"HUNTER.IO ENRICHMENT (TEST MODE)")
        print(f"{'='*60}")
        print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
        print(f"Max companies: 5")
        print(f"💰 Cost: ~$0.01 per domain searched")
        
        # Get companies for test
        test_domains = None
        if args.domain:
            test_domains = [args.domain]
            print(f"Testing single domain: {args.domain}")
        elif args.domains:
            test_domains = [d.strip() for d in args.domains.split(',')][:5]
            print(f"Testing multiple domains: {', '.join(test_domains)}")
        else:
            test_limit = min(args.limit or 3, 5)
            print(f"Testing {test_limit} random companies from Supabase")
        
        companies = get_companies_for_hunter_enrichment(supabase, BATCH_SIZE, test_domains=test_domains)
        
        if not companies:
            print("\n❌ No companies found to test")
            return
        
        companies = companies[:5]
        print(f"Processing {len(companies)} companies...\n")
        
        # Run batch
        results = await run_hunter_batch(hunter, supabase, companies, test_mode=True)
        
        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts, cost = sync_hunter_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts, ${cost:.2f}")
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed")
        
        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Companies enriched: {updated}")
        print(f"Contacts found: {contacts}")
        print(f"Total cost: ${cost:.2f}")
        return
    
    # Normal mode
    # Get accurate count of unenriched companies (using hunter_enriched_at timestamp)
    total_with_domains = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .is_('close_lead_id', 'null')\
        .execute()

    unenriched_result = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .is_('close_lead_id', 'null')\
        .is_('hunter_enriched_at', 'null')\
        .execute()

    unenriched_count = unenriched_result.count
    enriched_count = total_with_domains.count - unenriched_count

    print(f"\n{'='*60}")
    print(f"HUNTER.IO ENRICHMENT {'(AUTO MODE)' if args.auto else ''}")
    print(f"{'='*60}")
    print(f"Companies with domains (non-Close): {total_with_domains.count}")
    print(f"Already Hunter.io enriched: {enriched_count}")
    print(f"Remaining to enrich: {unenriched_count}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
    print(f"💰 Cost: ~$0.01 per domain searched")
    if args.limit:
        print(f"Limit: {args.limit} companies")
    
    if not args.auto:
        print(f"\nPress Enter to start, 'q' to quit")
        response = input()
        if response.lower() == 'q':
            return
    
    batch_num = 0
    total_enriched = 0
    total_contacts = 0
    total_cost = 0.0
    total_atl = 0
    total_btl = 0
    all_companies_data = []  # Track per-company results for logging
    
    while True:
        # Check limit
        if args.limit and total_enriched >= args.limit:
            print(f"\n✅ Reached limit of {args.limit} companies")
            break
        
        # Get next batch
        companies = get_companies_for_hunter_enrichment(supabase, BATCH_SIZE)
        
        if not companies:
            print("\n✅ ALL COMPANIES ENRICHED WITH HUNTER.IO!")
            break
        
        batch_num += 1
        remaining = unenriched_count - total_enriched
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num} ({remaining} remaining)")
        print(f"{'='*60}")
        
        # Run batch
        results = await run_hunter_batch(hunter, supabase, companies, test_mode=False)
        
        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts, cost = sync_hunter_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts, ${cost:.2f}")
        
        total_enriched += updated
        total_contacts += contacts
        total_cost += cost

        # Count ATL/BTL and collect per-company data
        for r in results:
            if r['success']:
                company_atl = sum(1 for c in r['contacts'] if c.get('is_atl'))
                company_btl = sum(1 for c in r['contacts'] if not c.get('is_atl'))
                total_atl += company_atl
                total_btl += company_btl

                all_companies_data.append({
                    "company_name": r['company_name'],
                    "domain": r['domain'],
                    "contacts_found": len(r['contacts']),
                    "atl": company_atl,
                    "btl": company_btl
                })

        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed (will retry later)")

        print(f"\n  Session total: {total_enriched} enriched, {total_contacts} contacts ({total_atl} ATL, {total_btl} BTL), ${total_cost:.2f}")
        
        # Prompt (skip in auto mode)
        if not args.auto:
            response = input("\nPress Enter for next batch, 'q' to quit: ")
            if response.lower() == 'q':
                break
        else:
            # Small delay between batches in auto mode
            await asyncio.sleep(2)
    
    print(f"\n{'='*60}")
    print("SESSION COMPLETE")
    print(f"{'='*60}")
    print(f"Companies enriched: {total_enriched}")
    print(f"Contacts found: {total_contacts}")
    print(f"  - ATL (decision makers): {total_atl}")
    print(f"  - BTL (other): {total_btl}")
    print(f"Total cost: ${total_cost:.2f}")

    # Log this run for reporting
    if all_companies_data:
        log_enrichment_run(
            companies_data=all_companies_data,
            total_cost=total_cost,
            source='hunter_io'
        )


if __name__ == '__main__':
    asyncio.run(main())

