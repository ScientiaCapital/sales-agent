#!/usr/bin/env python3
"""
Apollo SMART Enrichment Service
================================

Credit-efficient Apollo enrichment using a 2-step approach:
1. FREE SEARCH: Discover contacts at domain (0 credits)
2. PAID REVEAL: Get emails/phones for ATL contacts only (~2-3 credits each)

This saves 50-80% of credits by only enriching decision-makers.

Flow:
    FREE Search → Filter ATL → Show Credit Estimate → Confirm → Bulk Enrich → Sync to Supabase

Phone reveals are ASYNC - delivered to webhook 5-15 minutes later.
Requires APOLLO_WEBHOOK_BASE_URL in .env for phone reveals.

Usage:
    cd backend
    python enrich_apollo_paid.py --test --domain example.com
    python enrich_apollo_paid.py --limit 10 --min-score 50
    python enrich_apollo_paid.py --auto --limit 50 --min-score 80
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
APOLLO_WEBHOOK_BASE_URL = os.getenv('APOLLO_WEBHOOK_BASE_URL')

BATCH_SIZE = 5  # Companies per batch
BULK_ENRICH_SIZE = 10  # Max contacts per Apollo API call
RATE_LIMIT_DELAY = 3  # Seconds between API calls

# ATL (Above The Line) title keywords - decision makers only
ATL_TITLE_KEYWORDS = [
    'owner', 'ceo', 'president', 'founder', 'principal',
    'vp', 'vice president', 'director', 'general manager', 'gm',
    'partner', 'managing', 'chief', 'head of', 'co-founder',
    'executive', 'chairman', 'cfo', 'coo', 'cto'
]


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def is_atl_title(title: str) -> bool:
    """Check if title indicates ATL (decision maker)."""
    if not title:
        return False
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in ATL_TITLE_KEYWORDS)


def get_companies_for_enrichment(
    supabase,
    batch_size: int,
    min_icp_score: int = 0,
    test_domains: Optional[List[str]] = None
) -> List[Dict]:
    """Get companies that need Apollo PAID enrichment.

    Criteria:
    - Have domain (required)
    - Don't have apollo_paid_enriched_at yet
    - ICP score >= min_icp_score (if specified)
    """
    if test_domains:
        # Test mode: get specific domains
        companies = []
        for domain in test_domains[:5]:
            result = supabase.table('dim_companies')\
                .select('company_id, company_name, domain, icp_score, phone')\
                .eq('domain', domain)\
                .limit(1)\
                .execute()
            if result.data:
                companies.append(result.data[0])
        return companies

    # Normal mode: get companies needing enrichment
    query = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, icp_score, phone')\
        .not_.is_('domain', 'null')\
        .is_('apollo_paid_enriched_at', 'null')

    if min_icp_score > 0:
        query = query.gte('icp_score', min_icp_score)

    result = query.order('icp_score', desc=True).limit(batch_size).execute()
    return result.data


async def smart_enrich_company(
    apollo: ApolloService,
    supabase,
    company: Dict,
    auto_confirm: bool = False
) -> Dict[str, Any]:
    """
    Smart enrichment for one company using the credit-efficient flow.

    Steps:
    1. FREE search to discover contacts
    2. Filter to ATL only
    3. Show credit estimate and confirm
    4. Bulk enrich with reveal
    5. Sync to Supabase
    """
    company_id = company['company_id']
    company_name = company['company_name']
    domain = company['domain']
    icp_score = company.get('icp_score', 0)

    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'contacts_found': 0,
        'atl_contacts': 0,
        'contacts_enriched': 0,
        'credits_used': 0,
        'phone_webhook_pending': False,
        'error': ''
    }

    print(f"\n{'─'*60}")
    print(f"🏢 {company_name} ({domain})")
    print(f"   ICP Score: {icp_score}")

    try:
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: FREE SEARCH (0 credits)
        # ═══════════════════════════════════════════════════════════════
        print(f"\n   📡 Step 1: FREE Search for contacts...")

        all_contacts = await apollo.search_contacts_free(
            domain=domain,
            max_results=50
        )

        result['contacts_found'] = len(all_contacts)

        if not all_contacts:
            print(f"   ⚠️  No contacts found in Apollo database")
            result['error'] = 'No contacts found'
            return result

        print(f"   ✅ Found {len(all_contacts)} contacts (FREE)")

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: FILTER TO ATL ONLY
        # ═══════════════════════════════════════════════════════════════
        print(f"\n   🎯 Step 2: Filtering to ATL (decision makers)...")

        atl_contacts = [c for c in all_contacts if is_atl_title(c.get('title', ''))]
        result['atl_contacts'] = len(atl_contacts)

        if not atl_contacts:
            # No ATL found - check if we have any with seniority info
            seniority_contacts = [
                c for c in all_contacts
                if c.get('seniority') in ['owner', 'founder', 'c_suite', 'vp', 'director']
            ]
            if seniority_contacts:
                atl_contacts = seniority_contacts
                result['atl_contacts'] = len(atl_contacts)
                print(f"   ✅ Found {len(atl_contacts)} ATL via seniority filter")
            else:
                print(f"   ⚠️  No ATL contacts found (found {len(all_contacts)} BTL)")
                # Take top 3 contacts anyway for small companies
                if len(all_contacts) <= 5:
                    atl_contacts = all_contacts[:3]
                    print(f"   📌 Small company - enriching top {len(atl_contacts)} contacts")
                else:
                    result['error'] = 'No ATL contacts found'
                    return result
        else:
            print(f"   ✅ Found {len(atl_contacts)} ATL contacts:")
            for c in atl_contacts[:5]:  # Show first 5
                print(f"      • {c.get('name', 'Unknown')} - {c.get('title', 'No title')}")
            if len(atl_contacts) > 5:
                print(f"      ... and {len(atl_contacts) - 5} more")

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: CREDIT ESTIMATE & CONFIRM
        # ═══════════════════════════════════════════════════════════════
        contacts_to_enrich = atl_contacts[:BULK_ENRICH_SIZE]  # Max 10
        estimated_credits = len(contacts_to_enrich) * 2  # ~2 credits per contact

        print(f"\n   💰 Step 3: Credit Estimate")
        print(f"      Contacts to enrich: {len(contacts_to_enrich)}")
        print(f"      Estimated credits: ~{estimated_credits}")

        if APOLLO_WEBHOOK_BASE_URL:
            print(f"      📱 Phone reveals: ENABLED (via webhook)")
        else:
            print(f"      📱 Phone reveals: DISABLED (no webhook URL)")

        if not auto_confirm:
            response = input(f"\n   Proceed? [Y/n/s(kip)]: ").strip().lower()
            if response == 'n':
                result['error'] = 'Skipped by user'
                return result
            elif response == 's':
                result['error'] = 'Skipped'
                return result

        # ═══════════════════════════════════════════════════════════════
        # STEP 4: BULK ENRICHMENT (PAID)
        # ═══════════════════════════════════════════════════════════════
        print(f"\n   🔓 Step 4: Revealing emails & phones (PAID)...")

        # Prepare contacts for bulk enrichment
        # Use apollo_person_id when available (most reliable matching)
        enrich_requests = []
        for c in contacts_to_enrich:
            req = {
                'first_name': c.get('first_name'),
                'last_name': c.get('last_name'),
                'domain': domain,
            }
            # Include Apollo person ID for reliable matching (key for bulk_match)
            if c.get('apollo_person_id'):
                req['id'] = c['apollo_person_id']
            if c.get('linkedin_url'):
                req['linkedin_url'] = c['linkedin_url']
            enrich_requests.append(req)

        # Call bulk enrich with reveal
        enrich_result = await apollo.bulk_enrich_with_reveal(
            contacts=enrich_requests,
            reveal_emails=True,
            reveal_phones=True
        )

        enriched = enrich_result.get('enriched_contacts', [])
        credits = enrich_result.get('credits_consumed', 0)
        phone_pending = enrich_result.get('phone_webhook_pending', False)

        result['credits_used'] = credits
        result['phone_webhook_pending'] = phone_pending

        if not enriched:
            print(f"   ⚠️  No contacts enriched")
            result['error'] = 'Enrichment returned no data'
            return result

        print(f"   ✅ Enriched {len(enriched)} contacts ({credits} credits)")

        # Show what we got
        emails_found = sum(1 for e in enriched if e.get('email'))
        phones_found = sum(1 for e in enriched if e.get('phone'))
        print(f"      📧 Emails found: {emails_found}")
        print(f"      📱 Phones found: {phones_found}" + (" (more via webhook)" if phone_pending else ""))

        # ═══════════════════════════════════════════════════════════════
        # STEP 5: SYNC TO SUPABASE
        # ═══════════════════════════════════════════════════════════════
        print(f"\n   💾 Step 5: Syncing to Supabase...")

        updated_count = 0
        inserted_count = 0

        for contact in enriched:
            # Check if contact already exists in dim_contacts
            existing = supabase.table('dim_contacts')\
                .select('contact_id')\
                .eq('company_id', company_id)\
                .or_(
                    f"email.eq.{contact.get('email')},"
                    f"full_name.eq.{contact.get('full_name')}"
                )\
                .limit(1)\
                .execute()

            contact_data = {
                'company_id': company_id,
                'full_name': contact.get('full_name'),
                'first_name': contact.get('first_name'),
                'last_name': contact.get('last_name'),
                'title': contact.get('title'),
                'linkedin_url': contact.get('linkedin_url'),
                'is_atl': is_atl_title(contact.get('title', '')),
                'seniority': contact.get('seniority'),
                'source': 'apollo',
                'apollo_enriched_at': datetime.now().isoformat(),
                'apollo_person_id': contact.get('apollo_person_id'),
                'updated_at': datetime.now().isoformat()
            }

            # Add verified email if found
            if contact.get('email'):
                contact_data['email'] = contact['email']
                contact_data['email_verified'] = contact.get('email_verified', True)

            # Add phone if found (immediate, not webhook)
            if contact.get('phone'):
                contact_data['phone'] = contact['phone']
                contact_data['phone_verified'] = True

            if existing.data:
                # Update existing contact
                supabase.table('dim_contacts')\
                    .update(contact_data)\
                    .eq('contact_id', existing.data[0]['contact_id'])\
                    .execute()
                updated_count += 1
            else:
                # Insert new contact
                contact_data['created_at'] = datetime.now().isoformat()
                supabase.table('dim_contacts')\
                    .insert(contact_data)\
                    .execute()
                inserted_count += 1

        result['contacts_enriched'] = updated_count + inserted_count
        print(f"   ✅ Synced: {inserted_count} new, {updated_count} updated")

        # Mark company as apollo_paid_enriched
        supabase.table('dim_companies')\
            .update({'apollo_paid_enriched_at': datetime.now().isoformat()})\
            .eq('company_id', company_id)\
            .execute()

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)[:100]
        print(f"   ❌ Error: {result['error']}")

    return result


async def run_enrichment_batch(
    apollo: ApolloService,
    supabase,
    companies: List[Dict],
    auto_confirm: bool = False
) -> List[Dict[str, Any]]:
    """Run smart enrichment on a batch of companies."""
    results = []

    for i, company in enumerate(companies, 1):
        print(f"\n{'═'*60}")
        print(f"  Company {i}/{len(companies)}")
        print(f"{'═'*60}")

        result = await smart_enrich_company(apollo, supabase, company, auto_confirm)
        results.append(result)

        # Rate limiting between companies
        if i < len(companies):
            await asyncio.sleep(RATE_LIMIT_DELAY)

    return results


def print_summary(results: List[Dict[str, Any]]):
    """Print session summary."""
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    total_found = sum(r.get('contacts_found', 0) for r in results)
    total_atl = sum(r.get('atl_contacts', 0) for r in results)
    total_enriched = sum(r.get('contacts_enriched', 0) for r in results)
    total_credits = sum(r.get('credits_used', 0) for r in results)
    phone_pending = sum(1 for r in results if r.get('phone_webhook_pending'))

    print(f"\n{'═'*60}")
    print("SESSION SUMMARY")
    print(f"{'═'*60}")
    print(f"Companies processed: {len(results)}")
    print(f"  ✅ Successful: {len(successful)}")
    print(f"  ❌ Failed: {len(failed)}")
    print(f"\nContacts:")
    print(f"  📡 Found (FREE): {total_found}")
    print(f"  🎯 ATL filtered: {total_atl}")
    print(f"  🔓 Enriched (PAID): {total_enriched}")
    print(f"\nCredits:")
    print(f"  💰 Total used: {total_credits}")
    print(f"  📱 Phone webhooks pending: {phone_pending}")

    if failed:
        print(f"\nFailed companies:")
        for r in failed:
            print(f"  • {r['company_name']}: {r.get('error', 'Unknown error')}")


async def main():
    parser = argparse.ArgumentParser(
        description='Apollo SMART Enrichment - Credit-efficient contact discovery'
    )
    parser.add_argument('--auto', action='store_true',
                       help='Auto-confirm all enrichments (no prompts)')
    parser.add_argument('--limit', type=int, default=5,
                       help='Max companies to process (default: 5)')
    parser.add_argument('--min-score', type=int, default=0,
                       help='Minimum ICP score (default: 0)')
    parser.add_argument('--test', action='store_true',
                       help='Test mode with extra logging')
    parser.add_argument('--domain', type=str,
                       help='Test single domain (e.g., acmeheating.com)')
    parser.add_argument('--domains', type=str,
                       help='Test multiple domains, comma-separated')
    args = parser.parse_args()

    # Validate environment
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)

    if not APOLLO_API_KEY:
        print("❌ ERROR: Missing APOLLO_API_KEY")
        sys.exit(1)

    # Header
    print(f"\n{'═'*60}")
    print("🚀 APOLLO SMART ENRICHMENT")
    print(f"{'═'*60}")
    print(f"Strategy: FREE Search → ATL Filter → PAID Reveal")
    print(f"Expected savings: 50-80% credits")
    print(f"")
    print(f"Configuration:")
    print(f"  • Limit: {args.limit} companies")
    print(f"  • Min ICP Score: {args.min_score}")
    print(f"  • Auto-confirm: {'Yes' if args.auto else 'No'}")

    if APOLLO_WEBHOOK_BASE_URL:
        print(f"  • Phone webhook: ✅ {APOLLO_WEBHOOK_BASE_URL}")
    else:
        print(f"  • Phone webhook: ❌ Not configured (phones won't be revealed)")
        print(f"    Set APOLLO_WEBHOOK_BASE_URL in .env to enable")

    # Initialize clients
    supabase = get_supabase()
    apollo = ApolloService()

    # Get companies
    test_domains = None
    if args.domain:
        test_domains = [args.domain]
    elif args.domains:
        test_domains = [d.strip() for d in args.domains.split(',')]

    companies = get_companies_for_enrichment(
        supabase,
        args.limit,
        args.min_score,
        test_domains
    )

    if not companies:
        print(f"\n⚠️  No companies found matching criteria")
        return

    print(f"\n📋 Found {len(companies)} companies to enrich:")
    for c in companies[:10]:
        print(f"   • {c['company_name']} ({c['domain']}) - ICP: {c.get('icp_score', 0)}")
    if len(companies) > 10:
        print(f"   ... and {len(companies) - 10} more")

    if not args.auto:
        response = input(f"\nStart enrichment? [Y/n]: ").strip().lower()
        if response == 'n':
            print("Cancelled.")
            return

    # Run enrichment
    results = await run_enrichment_batch(
        apollo,
        supabase,
        companies,
        auto_confirm=args.auto
    )

    # Print summary
    print_summary(results)

    # Cleanup
    await apollo.close()

    print(f"\n{'═'*60}")
    print("✅ ENRICHMENT COMPLETE")
    print(f"{'═'*60}")

    if any(r.get('phone_webhook_pending') for r in results):
        print("\n📱 Phone numbers will arrive via webhook in 5-15 minutes.")
        print(f"   Webhook URL: {APOLLO_WEBHOOK_BASE_URL}/api/v1/apollo/webhooks/phone-reveal")


if __name__ == '__main__':
    asyncio.run(main())
