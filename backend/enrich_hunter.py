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
import os
import sys
import time
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
RATE_LIMIT_DELAY = 2  # 2 seconds between companies (Hunter.io allows more requests)


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_companies_for_hunter_enrichment(supabase, batch_size: int, test_domains: Optional[List[str]] = None):
    """Get companies that need Hunter.io enrichment.
    
    Criteria:
    - Have domain (required)
    - Have been website-enriched (have last_enriched_at)
    - Don't have hunter_enriched_at yet (or need refresh)
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
    
    # Normal mode: get companies that need Hunter.io enrichment
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('hunter_enriched_at', 'null')\
        .limit(batch_size)\
        .execute()
    return result.data


async def enrich_company_with_hunter(hunter: HunterService, company_id: str, company_name: str, domain: str) -> Dict[str, Any]:
    """Enrich one company with Hunter.io domain search.
    
    Returns dict with:
    - contacts: List of ATL contacts with emails, phones, LinkedIn
    - success: bool
    - error: str if failed
    """
    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'contacts': [],
        'error': '',
        'cost': 0.0
    }
    
    try:
        # Hunter.io domain search (gets ATL contacts with emails)
        contacts = await hunter.domain_search(domain, limit=25, atl_only=True)
        
        if contacts:
            result['contacts'] = contacts
            result['success'] = True
            result['cost'] = 0.01  # Hunter.io cost per domain search
        else:
            result['error'] = 'No contacts found'
        
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


def sync_hunter_data_to_supabase(supabase, results: List[Dict[str, Any]]) -> tuple:
    """Sync Hunter.io enrichment data to Supabase.
    
    Returns: (companies_updated, contacts_added, total_cost)
    """
    companies_updated = 0
    contacts_added = 0
    total_cost = 0.0
    
    for r in results:
        if not r['success']:
            continue
        
        company_id = r['company_id']
        contacts = r.get('contacts', [])
        cost = r.get('cost', 0.0)
        total_cost += cost
        
        # Update company with Hunter.io enrichment timestamp
        update_data = {
            'hunter_enriched_at': datetime.now().isoformat()
        }
        
        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            print(f"    Company update error: {e}")
        
        # Add contacts from Hunter.io (ATL contacts with verified emails)
        for contact in contacts:
            email = contact.get('email')
            if not email:
                continue
            
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            if not name:
                continue
            
            title = contact.get('position', '')
            phone = contact.get('phone_number')
            linkedin_url = contact.get('linkedin')
            confidence = contact.get('confidence', 0)
            
            contact_data = {
                'company_id': company_id,
                'full_name': name[:100],
                'first_name': contact.get('first_name', name.split()[0] if name.split() else '')[:50],
                'last_name': contact.get('last_name', ' '.join(name.split()[1:]) if len(name.split()) > 1 else '')[:50],
                'email': email,
                'title': title[:100] if title else None,
                'phone': phone,
                'linkedin_url': linkedin_url,
                'is_atl': True,  # Hunter.io domain_search with atl_only=True
                'source': 'hunter_io',
                'confidence': confidence
            }
            
            try:
                # Check if contact already exists (by email)
                existing = supabase.table('dim_contacts')\
                    .select('contact_id')\
                    .eq('company_id', company_id)\
                    .eq('email', email)\
                    .execute()
                
                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
                else:
                    # Update with Hunter.io data if better
                    existing_contact = existing.data[0]
                    update_contact = {}
                    
                    if not existing_contact.get('email') and email:
                        update_contact['email'] = email
                    if not existing_contact.get('phone') and phone:
                        update_contact['phone'] = phone
                    if not existing_contact.get('linkedin_url') and linkedin_url:
                        update_contact['linkedin_url'] = linkedin_url
                    if confidence > (existing_contact.get('confidence') or 0):
                        update_contact['confidence'] = confidence
                    
                    if update_contact:
                        supabase.table('dim_contacts')\
                            .update(update_contact)\
                            .eq('contact_id', existing_contact['contact_id'])\
                            .execute()
            except Exception as e:
                print(f"    Contact error: {e}")
    
    return companies_updated, contacts_added, total_cost


async def run_hunter_batch(hunter: HunterService, supabase, companies: List[Dict], test_mode: bool = False) -> List[Dict[str, Any]]:
    """Run Hunter.io enrichment on a batch of companies."""
    results = []
    
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
        
        result = await enrich_company_with_hunter(hunter, company_id, name, domain)
        results.append(result)
        
        if result['success']:
            contacts_count = len(result['contacts'])
            atl_count = contacts_count  # All are ATL since atl_only=True
            cost = result['cost']
            
            print(f"✅ ({contacts_count} ATL contacts, ${cost:.2f})")
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
    # Get stats
    total = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('hunter_enriched_at', 'null')\
        .execute()
    
    print(f"\n{'='*60}")
    print(f"HUNTER.IO ENRICHMENT {'(AUTO MODE)' if args.auto else ''}")
    print(f"{'='*60}")
    print(f"Companies needing Hunter.io enrichment: {total.count}")
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
        remaining = total.count - total_enriched
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
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed (will retry later)")
        
        print(f"\n  Session total: {total_enriched} enriched, {total_contacts} contacts, ${total_cost:.2f}")
        
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
    print(f"Total cost: ${total_cost:.2f}")


if __name__ == '__main__':
    asyncio.run(main())

