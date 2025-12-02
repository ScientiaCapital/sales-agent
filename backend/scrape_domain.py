#!/usr/bin/env python3
"""
Scrape Single Domain - Quick enrichment for a single company
=============================================================

Drop in a domain and enrich it immediately. Checks if company exists
in Supabase first, adds if new, updates if existing.

Usage:
    python scrape_domain.py bryantheatandair.com
    python scrape_domain.py "Bryant Heat and Air" bryantheatandair.com

Examples:
    python scrape_domain.py acmeheating.com
    python scrape_domain.py "Acme Heating & Cooling" acmeheating.com
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Import from run_enrichment
from run_enrichment import (
    scrape_one, get_supabase, BROWSERBASE_API_KEY,
    BROWSERBASE_PROJECT_ID, SUPABASE_URL, SUPABASE_SERVICE_KEY
)


def normalize_name(name):
    """Normalize company name for matching."""
    import re
    name = name.lower().strip()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    # Remove common suffixes
    for suffix in ['llc', 'inc', 'corp', 'co', 'ltd', 'company']:
        name = re.sub(rf'\s+{suffix}$', '', name)
    return name.strip()


def find_company_by_domain(supabase, domain):
    """Find company in Supabase by domain."""
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, last_enriched_at')\
        .eq('domain', domain)\
        .execute()
    return result.data[0] if result.data else None


def find_company_by_name(supabase, name):
    """Find company in Supabase by name (fuzzy match)."""
    normalized = normalize_name(name)
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, last_enriched_at')\
        .ilike('company_name', f'%{name[:30]}%')\
        .limit(5)\
        .execute()

    # Try to find exact normalized match
    for r in result.data:
        if normalize_name(r['company_name']) == normalized:
            return r

    # Return first match if any
    return result.data[0] if result.data else None


def create_new_company(supabase, company_name, domain):
    """Create new company in Supabase."""
    data = {
        'company_name': company_name,
        'domain': domain,
        'normalized_name': normalize_name(company_name),
        'source': 'manual_scrape',
        'created_at': datetime.now().isoformat()
    }
    result = supabase.table('dim_companies').insert(data).execute()
    return result.data[0] if result.data else None


def sync_results_to_supabase(supabase, company_id, result):
    """Sync scrape results to Supabase."""
    contacts_added = 0

    # Update company with service areas if found
    update_data = {'last_enriched_at': datetime.now().isoformat()}
    if result.get('service_areas'):
        update_data['service_areas'] = result['service_areas']

    try:
        supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
    except Exception:
        # If service_areas column doesn't exist, update without it
        if 'service_areas' in update_data:
            del update_data['service_areas']
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()

    # Add ALL contacts (ATL + BTL)
    for contact in result['atl_contacts']:
        name_parts = contact['name'].split()
        is_atl = contact.get('is_atl', True)
        contact_data = {
            'company_id': company_id,
            'full_name': contact['name'],
            'first_name': name_parts[0] if name_parts else '',
            'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
            'title': contact['title'],
            'is_atl': is_atl,
            'source': 'domain_scrape'
        }

        # Check if contact already exists
        existing = supabase.table('dim_contacts')\
            .select('contact_id')\
            .eq('company_id', company_id)\
            .eq('full_name', contact['name'])\
            .execute()

        if not existing.data:
            supabase.table('dim_contacts').insert(contact_data).execute()
            contacts_added += 1
            marker = '🎯' if is_atl else '👤'
            print(f"    ✅ Added contact: {marker} {contact['name']} ({contact['title']})")
        else:
            print(f"    ⏭️  Contact exists: {contact['name']}")

    return contacts_added


async def scrape_domain(domain, company_name=None):
    """Main function to scrape a single domain."""

    # Validate environment
    if not all([BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("❌ ERROR: Missing environment variables")
        sys.exit(1)

    # Clean domain
    domain = domain.lower().strip()
    if domain.startswith('http'):
        domain = domain.split('//')[1].split('/')[0]
    if domain.startswith('www.'):
        domain = domain[4:]

    print(f"\n{'='*60}")
    print(f"SCRAPE DOMAIN: {domain}")
    print(f"{'='*60}")

    supabase = get_supabase()

    # Step 1: Check if company exists
    print("\n🔍 Checking Supabase...")
    existing = find_company_by_domain(supabase, domain)

    if existing:
        company_id = existing['company_id']
        company_name = existing['company_name']
        last_enriched = existing.get('last_enriched_at')
        print(f"   Found: {company_name}")
        print(f"   Company ID: {company_id}")
        print(f"   Last enriched: {last_enriched or 'Never'}")
    else:
        # Try to find by name if provided
        if company_name:
            existing = find_company_by_name(supabase, company_name)
            if existing:
                company_id = existing['company_id']
                company_name = existing['company_name']
                # Update domain if missing
                if not existing.get('domain'):
                    supabase.table('dim_companies').update({'domain': domain}).eq('company_id', company_id).execute()
                    print(f"   Found by name: {company_name}")
                    print(f"   Updated domain to: {domain}")
                else:
                    print(f"   Found: {company_name} (different domain: {existing['domain']})")

        if not existing:
            # Create new company
            if not company_name:
                # Try to guess name from domain
                company_name = domain.replace('.com', '').replace('.net', '').replace('.org', '')
                company_name = company_name.replace('-', ' ').replace('_', ' ').title()

            print(f"   Not found - creating new company: {company_name}")
            new_company = create_new_company(supabase, company_name, domain)
            if new_company:
                company_id = new_company['company_id']
                print(f"   ✅ Created with ID: {company_id}")
            else:
                print("   ❌ Failed to create company")
                return

    # Step 2: Run scraper
    print(f"\n🌐 Scraping {domain}...")
    result = await scrape_one(company_id, company_name, domain)

    if not result['success']:
        print(f"   ❌ Scrape failed: {result['error']}")
        return

    print(f"   ✅ Scraped in {result['duration']:.0f}s")
    print(f"   Pages checked: {len(result.get('pages_checked', []))}")
    for p in result.get('pages_checked', []):
        print(f"      - {p}")

    # Step 3: Show results
    print(f"\n📊 RESULTS:")

    # Show contacts with ATL/BTL distinction
    contacts = result['atl_contacts']
    atl_contacts = [c for c in contacts if c.get('is_atl', True)]
    btl_contacts = [c for c in contacts if not c.get('is_atl', True)]

    print(f"   ATL Contacts (Decision Makers): {len(atl_contacts)}")
    for c in atl_contacts:
        print(f"      🎯 {c['name']} - {c['title']}")

    print(f"   BTL Contacts (Staff): {len(btl_contacts)}")
    for c in btl_contacts:
        print(f"      👤 {c['name']} - {c['title']}")

    print(f"   Phones: {len(result['phones'])}")
    for p in result['phones']:
        print(f"      📞 {p}")

    print(f"   Emails: {len(result['emails'])}")
    for e in result['emails']:
        print(f"      📧 {e}")

    print(f"   Services: {len(result.get('services', []))}")
    if result.get('services'):
        print(f"      🔧 {', '.join(result['services'])}")

    print(f"   Service Areas: {len(result.get('service_areas', []))}")
    if result.get('service_areas'):
        areas = result['service_areas']
        if len(areas) <= 10:
            print(f"      📍 {', '.join(areas)}")
        else:
            print(f"      📍 {', '.join(areas[:10])}... and {len(areas)-10} more")

    print(f"   HVAC Brands: {len(result.get('brands', []))}")
    if result.get('brands'):
        print(f"      🏭 {', '.join(result['brands'])}")

    # Step 4: Sync to Supabase
    print(f"\n☁️  Syncing to Supabase...")
    contacts_added = sync_results_to_supabase(supabase, company_id, result)

    print(f"\n{'='*60}")
    print(f"✅ COMPLETE")
    print(f"{'='*60}")
    print(f"Company: {company_name}")
    print(f"Domain: {domain}")
    print(f"Company ID: {company_id}")
    print(f"ATL contacts found: {len(atl_contacts)}")
    print(f"BTL contacts found: {len(btl_contacts)}")
    print(f"Service areas found: {len(result.get('service_areas', []))}")
    print(f"HVAC brands found: {len(result.get('brands', []))}")
    print(f"New contacts added: {contacts_added}")
    print(f"Last enriched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if len(sys.argv) == 2:
        # Just domain
        domain = sys.argv[1]
        company_name = None
    else:
        # Company name and domain
        company_name = sys.argv[1]
        domain = sys.argv[2]

    asyncio.run(scrape_domain(domain, company_name))


if __name__ == '__main__':
    main()
