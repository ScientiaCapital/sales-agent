#!/usr/bin/env python3
"""
Apollo FREE Enrichment Service
================================

Preemptive enrichment using Apollo's FREE search/read capabilities.
Gets rich company data and contacts WITHOUT spending credits.

This runs AFTER website scraping to add Apollo's free data:
- Company info (industry, employee count, founded year, LinkedIn, etc.)
- Contact names, titles, LinkedIn URLs (FREE search - no credits)
- Company structure and keywords

NO PAID REVEAL - This only uses free Apollo search/read APIs.

Usage:
    cd backend
    python enrich_apollo.py --test --domain example.com
    python enrich_apollo.py --test --limit 3
    python enrich_apollo.py --auto --limit 100
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
load_dotenv(Path(__file__).parent.parent.parent.parent.parent / '.env', override=True)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

# Add backend to path for Apollo service
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.apollo import ApolloService
from app.core.exceptions import (
    MissingAPIKeyError,
    APIRateLimitError,
    APIConnectionError,
    ValidationError
)

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
APOLLO_API_KEY = os.getenv('APOLLO_API_KEY')

BATCH_SIZE = 5
RATE_LIMIT_DELAY = 6  # 6 seconds between companies (600/hour = 10/minute, so 6s is safe)


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_companies_for_apollo_enrichment(supabase, batch_size: int, test_domains: Optional[List[str]] = None):
    """Get companies that need Apollo enrichment.
    
    Criteria:
    - Have domain (required)
    - Have been website-enriched (have last_enriched_at)
    - Don't have apollo_enriched_at yet (or need refresh)
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
    
    # Normal mode: get companies that need Apollo enrichment
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('apollo_enriched_at', 'null')\
        .limit(batch_size)\
        .execute()
    return result.data


async def enrich_company_with_apollo(apollo: ApolloService, company_id: str, company_name: str, domain: str, company_only: bool = False) -> Dict[str, Any]:
    """Enrich one company with Apollo FREE data.

    Returns dict with:
    - company_data: Rich company info from Apollo
    - contacts: List of contacts (names/titles/LinkedIn - FREE search)
    - success: bool
    - error: str if failed
    """
    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'company_data': None,
        'contacts': [],
        'error': ''
    }

    try:
        # Step 1: Enrich company data (FREE)
        company_data = await apollo.enrich_company(domain)
        result['company_data'] = company_data

        # Step 2: Search for contacts (SKIP if --company-only, as FREE search returns placeholder data)
        if not company_only:
            # Focus on ATL titles
            atl_titles = ["CEO", "President", "Owner", "Founder", "VP", "Vice President",
                          "Director", "General Manager", "CFO", "CTO", "COO"]

            contacts = await apollo.search_company_contacts(
                domain=domain,
                job_titles=atl_titles,
                max_results=25  # Get up to 25 contacts (FREE search)
            )
            result['contacts'] = contacts

        result['success'] = True
        
    except APIRateLimitError as e:
        result['error'] = f"Rate limit: {str(e)}"
    except ValidationError as e:
        result['error'] = f"Validation: {str(e)}"
    except APIConnectionError as e:
        result['error'] = f"Connection: {str(e)}"
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


def sync_apollo_data_to_supabase(supabase, results: List[Dict[str, Any]]) -> tuple:
    """Sync Apollo enrichment data to Supabase.
    
    Returns: (companies_updated, contacts_added)
    """
    companies_updated = 0
    contacts_added = 0
    
    for r in results:
        if not r['success']:
            continue
        
        company_id = r['company_id']
        company_data = r.get('company_data', {})
        contacts = r.get('contacts', [])
        
        # Update company with Apollo data
        update_data = {
            'apollo_enriched_at': datetime.now().isoformat()
        }
        
        # Company data from Apollo (FREE)
        if company_data:
            if company_data.get('linkedin_url'):
                update_data['linkedin_url'] = company_data['linkedin_url']
            if company_data.get('founded_year'):
                update_data['founded_year'] = company_data['founded_year']
            if company_data.get('employee_count'):
                update_data['employee_count'] = str(company_data['employee_count'])
            if company_data.get('industry'):
                update_data['industry'] = company_data['industry']
            if company_data.get('address'):
                addr = company_data['address']
                if addr.get('city'):
                    update_data['city'] = addr['city']
                if addr.get('state'):
                    update_data['state'] = addr['state']
                if addr.get('country'):
                    update_data['country'] = addr['country']
        
        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            # Handle missing columns gracefully
            error_str = str(e).lower()
            if 'column' in error_str and 'does not exist' in error_str:
                print(f"    ⚠️  Missing column - run migration: {e}")
                # Try without problematic columns
                safe_update = {'apollo_enriched_at': update_data.get('apollo_enriched_at')}
                try:
                    supabase.table('dim_companies').update(safe_update).eq('company_id', company_id).execute()
                    companies_updated += 1
                except Exception as e2:
                    print(f"    Update error: {e2}")
            else:
                print(f"    Company update error: {e}")
        
        # Add contacts from Apollo (FREE search - names/titles/LinkedIn)
        for contact in contacts:
            name = contact.get('name') or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            if not name or len(name) < 3:
                continue
            
            title = contact.get('title', '')
            linkedin_url = contact.get('linkedin_url')
            
            # Determine if ATL based on title
            title_lower = title.lower() if title else ''
            is_atl = any(keyword in title_lower for keyword in [
                'ceo', 'president', 'owner', 'founder', 'vp', 'vice president',
                'director', 'general manager', 'cfo', 'cto', 'coo'
            ])
            
            contact_data = {
                'company_id': company_id,
                'full_name': name[:100],
                'first_name': contact.get('first_name', name.split()[0] if name.split() else '')[:50],
                'last_name': contact.get('last_name', ' '.join(name.split()[1:]) if len(name.split()) > 1 else '')[:50],
                'title': title[:100] if title else None,
                'linkedin_url': linkedin_url,
                'is_atl': is_atl,
                'source': 'apollo_search'  # FREE search, not paid reveal
            }
            
            try:
                # Check if contact already exists
                existing = supabase.table('dim_contacts')\
                    .select('contact_id')\
                    .eq('company_id', company_id)\
                    .eq('full_name', name[:100])\
                    .execute()
                
                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
                elif linkedin_url:
                    # Update LinkedIn URL if missing
                    supabase.table('dim_contacts')\
                        .update({'linkedin_url': linkedin_url})\
                        .eq('contact_id', existing.data[0]['contact_id'])\
                        .is_('linkedin_url', 'null')\
                        .execute()
            except Exception as e:
                print(f"    Contact error: {e}")
    
    return companies_updated, contacts_added


async def run_apollo_batch(apollo: ApolloService, supabase, companies: List[Dict], test_mode: bool = False, company_only: bool = False) -> List[Dict[str, Any]]:
    """Run Apollo enrichment on a batch of companies."""
    results = []

    for i, company in enumerate(companies, 1):
        # Rate limiting: delay between companies
        if i > 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)

        company_id = company['company_id']
        name = company['company_name']
        domain = company['domain']

        print(f"  [{i}/{len(companies)}] {name} ({domain})...", end=" ", flush=True)

        result = await enrich_company_with_apollo(apollo, company_id, name, domain, company_only=company_only)
        results.append(result)

        if result['success']:
            company_info = result['company_data'] or {}
            contacts_count = len(result['contacts'])
            employee_count = company_info.get('employee_count', '?')
            industry = company_info.get('industry', '?')
            linkedin = '✅' if company_info.get('linkedin_url') else '❌'

            if company_only:
                print(f"OK ({employee_count} emp, {industry}, LinkedIn: {linkedin})")
            else:
                print(f"OK ({contacts_count} contacts, {employee_count} emp, {industry}, LinkedIn: {linkedin})")
        else:
            print(f"FAIL: {result['error']}")
    
    return results


async def main():
    parser = argparse.ArgumentParser(description='Apollo FREE enrichment service')
    parser.add_argument('--auto', action='store_true', help='Run continuously without prompts')
    parser.add_argument('--limit', type=int, default=0, help='Max companies to process (0=unlimited)')
    parser.add_argument('--test', action='store_true', help='Test mode: max 5 companies, adds rate limiting')
    parser.add_argument('--domain', type=str, help='Test single domain (e.g., acmeheating.com)')
    parser.add_argument('--domains', type=str, help='Test multiple domains, comma-separated (max 5)')
    parser.add_argument('--company-only', action='store_true', help='Skip contact search (FREE contact data is placeholder garbage)')
    args = parser.parse_args()
    
    # Validate
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing Supabase environment variables")
        sys.exit(1)
    
    if not APOLLO_API_KEY:
        print("ERROR: Missing APOLLO_API_KEY environment variable")
        sys.exit(1)
    
    supabase = get_supabase()
    apollo = ApolloService()
    
    # Test mode handling
    if args.test:
        print(f"\n{'='*60}")
        print(f"APOLLO FREE ENRICHMENT (TEST MODE)")
        print(f"{'='*60}")
        print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
        print(f"Max companies: 5")
        print(f"⚠️  Using FREE Apollo search only (no credits spent)")
        
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
        
        companies = get_companies_for_apollo_enrichment(supabase, BATCH_SIZE, test_domains=test_domains)
        
        if not companies:
            print("\n❌ No companies found to test")
            return
        
        companies = companies[:5]
        print(f"Processing {len(companies)} companies...\n")
        
        # Run batch
        company_only = getattr(args, 'company_only', False)
        results = await run_apollo_batch(apollo, supabase, companies, test_mode=True, company_only=company_only)

        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts = sync_apollo_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts")

        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed")

        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Companies enriched: {updated}")
        if not company_only:
            print(f"Contacts found: {contacts}")
        print(f"⚠️  Company data from FREE Apollo (no credits spent)")
        return
    
    # Normal mode
    # Get stats
    total = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('apollo_enriched_at', 'null')\
        .execute()
    
    print(f"\n{'='*60}")
    print(f"APOLLO FREE ENRICHMENT {'(AUTO MODE)' if args.auto else ''}")
    print(f"{'='*60}")
    print(f"Companies needing Apollo enrichment: {total.count}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
    print(f"⚠️  Using FREE Apollo search only (no credits spent)")
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
    
    while True:
        # Check limit
        if args.limit and total_enriched >= args.limit:
            print(f"\n✅ Reached limit of {args.limit} companies")
            break
        
        # Get next batch
        companies = get_companies_for_apollo_enrichment(supabase, BATCH_SIZE)
        
        if not companies:
            print("\n✅ ALL COMPANIES ENRICHED WITH APOLLO!")
            break
        
        batch_num += 1
        remaining = total.count - total_enriched
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num} ({remaining} remaining)")
        print(f"{'='*60}")
        
        # Run batch
        company_only = getattr(args, 'company_only', False)
        results = await run_apollo_batch(apollo, supabase, companies, test_mode=False, company_only=company_only)

        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts = sync_apollo_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts")

        total_enriched += updated
        total_contacts += contacts

        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed (will retry later)")

        print(f"\n  Session total: {total_enriched} enriched")
        if not company_only:
            print(f"  Contacts found: {total_contacts}")
        print(f"  ⚠️  Company data from FREE Apollo (no credits spent)")
        
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
    print(f"⚠️  All data from FREE Apollo search (no credits spent)")
    
    # Cleanup
    await apollo.close()


if __name__ == '__main__':
    asyncio.run(main())

