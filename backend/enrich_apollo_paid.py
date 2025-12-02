#!/usr/bin/env python3
"""
Apollo PAID Enrichment Service
===============================

PAID Apollo enrichment for high-priority leads only.
Uses Apollo's paid reveal APIs to get:
- Verified email addresses (real emails, not placeholders)
- Direct phone numbers
- Additional contact details

Cost: ~1-2 credits per contact (varies by plan)
⚠️  USE SPARINGLY - Only for high-priority leads!

Usage:
    cd backend
    python enrich_apollo_paid.py --test --domain example.com
    python enrich_apollo_paid.py --test --limit 3
    python enrich_apollo_paid.py --auto --limit 50 --min-score 80  # Only ICP score 80+
"""

import argparse
import asyncio
import os
import sys
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
RATE_LIMIT_DELAY = 6  # 6 seconds between companies


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_companies_for_apollo_paid_enrichment(
    supabase,
    batch_size: int,
    min_icp_score: int = 0,
    test_domains: Optional[List[str]] = None
):
    """Get companies that need Apollo PAID enrichment.
    
    Criteria:
    - Have domain (required)
    - Have been enriched with other services (have last_enriched_at)
    - Have contacts without verified emails/phones
    - ICP score >= min_icp_score (if specified)
    - Don't have apollo_paid_enriched_at yet
    """
    if test_domains:
        # Test mode: get specific domains
        companies = []
        for domain in test_domains[:5]:  # Max 5 for test
            result = supabase.table('dim_companies')\
                .select('company_id, company_name, domain, icp_score')\
                .eq('domain', domain)\
                .limit(1)\
                .execute()
            if result.data:
                companies.append(result.data[0])
        return companies
    
    # Normal mode: get companies that need Apollo PAID enrichment
    query = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, icp_score')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('apollo_paid_enriched_at', 'null')
    
    if min_icp_score > 0:
        query = query.gte('icp_score', min_icp_score)
    
    result = query.limit(batch_size).execute()
    return result.data


async def enrich_contacts_with_apollo_paid(
    apollo: ApolloService,
    company_id: str,
    domain: str,
    contacts: List[Dict]
) -> Dict[str, Any]:
    """Enrich contacts with Apollo PAID reveal.
    
    Uses Apollo's paid reveal APIs to get verified emails and phones.
    """
    result = {
        'company_id': company_id,
        'domain': domain,
        'success': False,
        'enriched_contacts': [],
        'credits_used': 0,
        'error': ''
    }
    
    try:
        # Focus on contacts without verified emails/phones
        contacts_to_enrich = [
            c for c in contacts
            if not c.get('email') or not c.get('phone')
        ][:10]  # Limit to 10 contacts per company to control costs
        
        if not contacts_to_enrich:
            result['error'] = 'No contacts need enrichment'
            return result
        
        enriched = []
        credits = 0
        
        for contact in contacts_to_enrich:
            try:
                # Use Apollo's search_and_enrich_contacts with reveal
                enriched_contact = await apollo.search_and_enrich_contacts(
                    domain=domain,
                    job_titles=[contact.get('title', '')] if contact.get('title') else None,
                    max_results=1,
                    reveal_emails=True,   # PAID - costs credits
                    reveal_phones=True    # PAID - costs credits
                )
                
                if enriched_contact:
                    enriched.append({
                        'name': contact.get('name'),
                        'email': enriched_contact.get('email'),
                        'phone': enriched_contact.get('phone'),
                        'title': contact.get('title'),
                        'linkedin_url': enriched_contact.get('linkedin_url')
                    })
                    credits += 2  # Estimate: ~2 credits per contact reveal
                
            except Exception as e:
                # Continue with other contacts if one fails
                continue
        
        result['enriched_contacts'] = enriched
        result['credits_used'] = credits
        result['success'] = len(enriched) > 0
        
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


async def enrich_company_with_apollo_paid(
    apollo: ApolloService,
    supabase,
    company_id: str,
    company_name: str,
    domain: str
) -> Dict[str, Any]:
    """Enrich one company's contacts with Apollo PAID reveal."""
    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'contacts_enriched': 0,
        'credits_used': 0,
        'error': ''
    }
    
    try:
        # Get existing contacts for this company
        contacts_result = supabase.table('dim_contacts')\
            .select('contact_id, full_name, email, phone, title, linkedin_url')\
            .eq('company_id', company_id)\
            .is_('is_atl', 'true')\
            .limit(20)\
            .execute()
        
        contacts = contacts_result.data if contacts_result.data else []
        
        if not contacts:
            result['error'] = 'No contacts found'
            return result
        
        # Enrich contacts with Apollo PAID reveal
        enrich_result = await enrich_contacts_with_apollo_paid(
            apollo, company_id, domain, contacts
        )
        
        if enrich_result['success']:
            # Update contacts in Supabase with verified emails/phones
            for enriched in enrich_result['enriched_contacts']:
                # Find matching contact
                matching = [c for c in contacts if c.get('full_name') == enriched.get('name')]
                if matching:
                    contact_id = matching[0]['contact_id']
                    update_data = {}
                    
                    if enriched.get('email') and not matching[0].get('email'):
                        update_data['email'] = enriched['email']
                    if enriched.get('phone') and not matching[0].get('phone'):
                        update_data['phone'] = enriched['phone']
                    if enriched.get('linkedin_url') and not matching[0].get('linkedin_url'):
                        update_data['linkedin_url'] = enriched['linkedin_url']
                    
                    if update_data:
                        supabase.table('dim_contacts')\
                            .update(update_data)\
                            .eq('contact_id', contact_id)\
                            .execute()
            
            result['contacts_enriched'] = len(enrich_result['enriched_contacts'])
            result['credits_used'] = enrich_result['credits_used']
            result['success'] = True
        else:
            result['error'] = enrich_result['error']
    
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


async def run_apollo_paid_batch(
    apollo: ApolloService,
    supabase,
    companies: List[Dict],
    test_mode: bool = False
) -> List[Dict[str, Any]]:
    """Run Apollo PAID enrichment on a batch of companies."""
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
        icp_score = company.get('icp_score', 0)
        
        print(f"  [{i}/{len(companies)}] {name} ({domain}, ICP: {icp_score})...", end=" ", flush=True)
        
        result = await enrich_company_with_apollo_paid(apollo, supabase, company_id, name, domain)
        results.append(result)
        
        if result['success']:
            contacts = result['contacts_enriched']
            credits = result['credits_used']
            print(f"✅ ({contacts} contacts, {credits} credits)")
        else:
            print(f"❌ {result['error']}")
    
    return results


async def main():
    parser = argparse.ArgumentParser(description='Apollo PAID enrichment service')
    parser.add_argument('--auto', action='store_true', help='Run continuously without prompts')
    parser.add_argument('--limit', type=int, default=0, help='Max companies to process (0=unlimited)')
    parser.add_argument('--min-score', type=int, default=0, help='Minimum ICP score (default: 0, use 80+ for high-priority only)')
    parser.add_argument('--test', action='store_true', help='Test mode: max 5 companies, adds rate limiting')
    parser.add_argument('--domain', type=str, help='Test single domain (e.g., acmeheating.com)')
    parser.add_argument('--domains', type=str, help='Test multiple domains, comma-separated (max 5)')
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
        print(f"APOLLO PAID ENRICHMENT (TEST MODE)")
        print(f"{'='*60}")
        print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
        print(f"Max companies: 5")
        print(f"💰 Cost: ~1-2 credits per contact (PAID)")
        print(f"⚠️  WARNING: This uses Apollo credits!")
        
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
        
        companies = get_companies_for_apollo_paid_enrichment(
            supabase, BATCH_SIZE, args.min_score, test_domains=test_domains
        )
        
        if not companies:
            print("\n❌ No companies found to test")
            return
        
        companies = companies[:5]
        print(f"Processing {len(companies)} companies...\n")
        
        # Run batch
        results = await run_apollo_paid_batch(apollo, supabase, companies, test_mode=True)
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        total_contacts = sum(r.get('contacts_enriched', 0) for r in results)
        total_credits = sum(r.get('credits_used', 0) for r in results)
        
        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Companies enriched: {successful}")
        print(f"Contacts enriched: {total_contacts}")
        print(f"Credits used: {total_credits}")
        if failed > 0:
            print(f"⚠️  {failed} failed")
        return
    
    # Normal mode
    # Get stats
    query = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('apollo_paid_enriched_at', 'null')
    
    if args.min_score > 0:
        query = query.gte('icp_score', args.min_score)
    
    total = query.execute()
    
    print(f"\n{'='*60}")
    print(f"APOLLO PAID ENRICHMENT {'(AUTO MODE)' if args.auto else ''}")
    print(f"{'='*60}")
    print(f"Companies needing Apollo PAID enrichment: {total.count}")
    if args.min_score > 0:
        print(f"Minimum ICP score: {args.min_score}+")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
    print(f"💰 Cost: ~1-2 credits per contact (PAID)")
    print(f"⚠️  WARNING: This uses Apollo credits!")
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
    total_credits = 0
    
    while True:
        # Check limit
        if args.limit and total_enriched >= args.limit:
            print(f"\n✅ Reached limit of {args.limit} companies")
            break
        
        # Get next batch
        companies = get_companies_for_apollo_paid_enrichment(
            supabase, BATCH_SIZE, args.min_score
        )
        
        if not companies:
            print("\n✅ ALL COMPANIES ENRICHED WITH APOLLO PAID!")
            break
        
        batch_num += 1
        remaining = total.count - total_enriched
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num} ({remaining} remaining)")
        print(f"{'='*60}")
        
        # Run batch
        results = await run_apollo_paid_batch(apollo, supabase, companies, test_mode=False)
        
        # Update companies with apollo_paid_enriched_at timestamp
        for r in results:
            if r['success']:
                supabase.table('dim_companies')\
                    .update({'apollo_paid_enriched_at': datetime.now().isoformat()})\
                    .eq('company_id', r['company_id'])\
                    .execute()
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        batch_contacts = sum(r.get('contacts_enriched', 0) for r in results)
        batch_credits = sum(r.get('credits_used', 0) for r in results)
        
        total_enriched += successful
        total_contacts += batch_contacts
        total_credits += batch_credits
        
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed (will retry later)")
        
        print(f"\n  Session total: {total_enriched} enriched, {total_contacts} contacts, {total_credits} credits")
        
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
    print(f"Contacts enriched: {total_contacts}")
    print(f"Total credits used: {total_credits}")
    
    # Cleanup
    await apollo.close()


if __name__ == '__main__':
    asyncio.run(main())

