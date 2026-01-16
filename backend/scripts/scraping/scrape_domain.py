#!/usr/bin/env python3
"""
Scrape Single Domain - Quick enrichment for a single company
=============================================================

Drop in a domain and enrich it immediately. Checks if company exists
in Supabase first, adds if new, updates if existing.

Usage:
    python scrape_domain.py <domain>
    python scrape_domain.py <company_name> <domain>
    python scrape_domain.py <company_name> <domain> <extra_page1> <extra_page2> ...
    python scrape_domain.py <domain> --ai           # AI-powered intel extraction + drafts

Examples:
    # Basic - domain only
    python scrape_domain.py acmeheating.com

    # With company name
    python scrape_domain.py "Acme Heating & Cooling" acmeheating.com

    # With specific pages to scrape (staff pages, team pages, etc.)
    python scrape_domain.py "Command Comfort" commandcomfort.com /about/staff /team/leadership

    # AI-POWERED: Extract personal intel + generate email/SMS drafts
    python scrape_domain.py "Command Comfort" commandcomfort.com --ai

    # Full URLs work too
    python scrape_domain.py "Acme" acme.com https://acme.com/our-team https://acme.com/management
"""

import asyncio
import sys
import os
import base64
from datetime import datetime
from pathlib import Path

import httpx

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Import from run_enrichment
from run_enrichment import (
    scrape_one, get_supabase, BROWSERBASE_API_KEY,
    BROWSERBASE_PROJECT_ID, SUPABASE_URL, SUPABASE_SERVICE_KEY
)

# Close CRM config
CLOSE_API_KEY = os.getenv("CLOSE_API_KEY", "")
CLOSE_API_BASE = "https://api.close.com/api/v1"


def get_close_headers():
    """Get Close API headers with basic auth."""
    auth = base64.b64encode(f"{CLOSE_API_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }


async def search_close_by_domain(domain: str) -> dict | None:
    """Search Close CRM for a lead by domain/URL."""
    if not CLOSE_API_KEY:
        return None

    async with httpx.AsyncClient() as client:
        # Close uses query parameter for search
        # Search by URL field or company name containing domain
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/",
            headers=get_close_headers(),
            params={
                "query": f'url:"{domain}" OR url:"www.{domain}" OR url:"https://{domain}"',
                "_limit": 5,
                "_fields": "id,display_name,status_label,contacts,url,custom,date_created",
            },
            timeout=15.0
        )

        if response.status_code != 200:
            return None

        data = response.json()
        leads = data.get("data", [])

        # Find exact domain match
        for lead in leads:
            lead_url = lead.get("url", "") or ""
            # Normalize URL for comparison
            lead_domain = lead_url.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
            if lead_domain == domain.lower() or domain.lower() in lead_domain:
                return lead

        return None


async def search_close_by_name(company_name: str) -> dict | None:
    """Search Close CRM for a lead by company name."""
    if not CLOSE_API_KEY or not company_name:
        return None

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/",
            headers=get_close_headers(),
            params={
                "query": f'name:"{company_name}"',
                "_limit": 5,
                "_fields": "id,display_name,status_label,contacts,url,custom,date_created",
            },
            timeout=15.0
        )

        if response.status_code != 200:
            return None

        data = response.json()
        leads = data.get("data", [])

        # Find best match
        for lead in leads:
            lead_name = lead.get("display_name", "").lower()
            if company_name.lower() in lead_name or lead_name in company_name.lower():
                return lead

        return leads[0] if leads else None


def get_close_contacts(lead: dict) -> list:
    """Extract contacts from a Close lead."""
    contacts = []
    for c in lead.get("contacts", []):
        name = c.get("name", "")
        title = c.get("title", "")
        emails = [e.get("email") for e in c.get("emails", []) if e.get("email")]
        phones = [p.get("phone") for p in c.get("phones", []) if p.get("phone")]

        contacts.append({
            "id": c.get("id"),
            "name": name,
            "title": title,
            "emails": emails,
            "phones": phones,
        })
    return contacts


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


def print_sales_card(company_name, domain, result, atl_contacts, btl_contacts, close_lead=None, close_contacts=None, sales_intel=None):
    """Print a formatted sales card for easy copy/paste into Close CRM notes."""
    today = datetime.now().strftime('%Y-%m-%d')
    close_contacts = close_contacts or []

    # Identify NEW contacts (not already in Close)
    close_contact_names = {c['name'].lower().strip() for c in close_contacts if c.get('name')}
    new_atl = [c for c in atl_contacts if c['name'].lower().strip() not in close_contact_names]
    new_btl = [c for c in btl_contacts if c['name'].lower().strip() not in close_contact_names]

    # Build the card
    card = []
    card.append("")
    card.append("=" * 60)
    card.append("📋 CLOSE CRM SALES CARD - COPY BELOW THIS LINE")
    card.append("=" * 60)
    card.append("")
    card.append(f"🏢 {company_name}")
    card.append(f"🌐 https://{domain}")
    card.append(f"📅 Enriched: {today}")

    # Show Close CRM status
    if close_lead:
        card.append(f"📊 Close Status: {close_lead.get('status_label', 'Unknown')}")
    card.append("")

    # NEW Decision Makers (not in Close yet) - highlight these!
    if new_atl:
        card.append("🆕 NEW DECISION MAKERS (not in Close):")
        for c in new_atl:
            card.append(f"   ⭐ {c['name']} - {c['title']}")
        card.append("")

    # Existing contacts in Close (for reference)
    if close_contacts:
        card.append(f"✅ EXISTING CONTACTS IN CLOSE: {len(close_contacts)}")
        for c in close_contacts[:3]:
            card.append(f"   • {c['name']} - {c['title'] or 'No title'}")
        if len(close_contacts) > 3:
            card.append(f"   ... and {len(close_contacts) - 3} more")
        card.append("")

    # All ATL found (if no Close lead, show all)
    if not close_lead and atl_contacts:
        card.append("👔 DECISION MAKERS:")
        for c in atl_contacts:
            card.append(f"   • {c['name']} - {c['title']}")
        card.append("")

    # Phones
    if result['phones']:
        card.append(f"📞 PHONES: {', '.join(result['phones'])}")
    else:
        card.append("📞 PHONES: None found")

    # Emails
    if result['emails']:
        card.append(f"📧 EMAILS: {', '.join(result['emails'])}")
    card.append("")

    # Services (ICP signals)
    if result.get('services'):
        services = result['services'][:8]  # Top 8
        card.append(f"🔧 SERVICES: {', '.join(services)}")

    # Brands (indicates partnerships)
    if result.get('brands'):
        brands = result['brands'][:6]  # Top 6
        card.append(f"🏭 BRANDS: {', '.join(brands)}")

    # Maintenance Plans (BDR opener gold!)
    if result.get('maintenance_plans'):
        plans = result['maintenance_plans'][:3]
        card.append(f"🎯 MAINTENANCE PLANS: {', '.join(plans)}")

    # Service Areas
    if result.get('service_areas'):
        areas = result['service_areas']
        if len(areas) <= 5:
            card.append(f"📍 SERVICE AREAS: {', '.join(areas)}")
        else:
            card.append(f"📍 SERVICE AREAS: {', '.join(areas[:5])} (+{len(areas)-5} more)")

    # ========== AI-POWERED SECTION (if --ai used) ==========
    if sales_intel and sales_intel.get('confidence', 0) > 0.1:
        card.append("")
        card.append("=" * 60)
        card.append("🤖 AI-POWERED SALES INTEL")
        card.append("=" * 60)

        # Personal Hooks - THE GOLD
        if sales_intel.get('personal_hooks'):
            card.append("")
            card.append("🎯 PERSONAL HOOKS (for rapport):")
            for hook in sales_intel['personal_hooks'][:4]:
                card.append(f"   • [{hook.get('category', '?')}] {hook.get('detail', '')}")
                if hook.get('opener'):
                    card.append(f"     💬 \"{hook['opener']}\"")

        # Company Story
        if sales_intel.get('company_story'):
            card.append("")
            card.append(f"📖 COMPANY STORY: {sales_intel['company_story'][:200]}...")

        # Pain Points
        if sales_intel.get('pain_points'):
            card.append("")
            card.append("⚠️ PAIN POINTS:")
            for pp in sales_intel['pain_points'][:3]:
                card.append(f"   • {pp}")

        card.append("")
        card.append("-" * 60)
        card.append("📧 DRAFT EMAIL:")
        card.append("-" * 60)
        card.append(f"Subject: {sales_intel.get('email_subject', '')}")
        card.append("")
        card.append(sales_intel.get('email_body', ''))

        card.append("")
        card.append("-" * 60)
        card.append("💬 DRAFT SMS (under 160 chars):")
        card.append("-" * 60)
        card.append(sales_intel.get('sms_draft', ''))

        card.append("")
        card.append("-" * 60)
        card.append("📞 VOICE OPENER:")
        card.append("-" * 60)
        card.append(sales_intel.get('voice_opener', ''))

    # ========== END AI SECTION ==========

    # Owner Bios - fallback if no AI
    elif result.get('owner_bios'):
        card.append("")
        card.append("💡 CONVERSATION STARTERS (raw - use --ai for better):")
        for bio in result['owner_bios'][:2]:
            if bio.get('bio_snippet'):
                snippet = bio['bio_snippet']
                name = bio.get('name', 'Owner')
                card.append(f"   {name}: \"{snippet[:150]}...\"" if len(snippet) > 150 else f"   {name}: \"{snippet}\"")

    card.append("")

    # NEW Staff (BTL) - abbreviated
    if new_btl:
        btl_names = [c['name'] for c in new_btl[:3]]
        card.append(f"🆕 NEW STAFF: {', '.join(btl_names)}" + (f" (+{len(new_btl)-3} more)" if len(new_btl) > 3 else ""))

    card.append("")
    card.append("=" * 60)
    card.append("📋 END SALES CARD - COPY ABOVE THIS LINE")
    card.append("=" * 60)
    card.append("")

    # Print it
    for line in card:
        print(line)


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


async def scrape_domain(domain, company_name=None, extra_pages=None, use_ai=False):
    """Main function to scrape a single domain.

    Args:
        domain: Domain to scrape (e.g. "acmeheating.com")
        company_name: Optional company name
        extra_pages: Optional list of specific pages to scrape (e.g. ["/about/staff", "/team"])
        use_ai: If True, run SalesIntelAgent for AI-powered extraction + drafts
    """

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

    # Step 0: Check Close CRM first
    close_lead = None
    close_contacts = []
    print("\n🔍 Checking Close CRM...")
    if CLOSE_API_KEY:
        close_lead = await search_close_by_domain(domain)
        if not close_lead and company_name:
            close_lead = await search_close_by_name(company_name)

        if close_lead:
            close_contacts = get_close_contacts(close_lead)
            print(f"   ✅ FOUND IN CLOSE CRM!")
            print(f"   Lead: {close_lead.get('display_name')}")
            print(f"   Status: {close_lead.get('status_label', 'Unknown')}")
            print(f"   Lead ID: {close_lead.get('id')}")
            print(f"   Existing contacts: {len(close_contacts)}")
            for c in close_contacts:
                emails = ', '.join(c['emails']) if c['emails'] else 'no email'
                print(f"      • {c['name']} - {c['title'] or 'No title'} ({emails})")
            # Use Close's company name if we don't have one
            if not company_name:
                company_name = close_lead.get('display_name')
        else:
            print(f"   ⚠️  Not found in Close CRM")
    else:
        print(f"   ⏭️  Skipping (CLOSE_API_KEY not set)")

    supabase = get_supabase()

    # Step 1: Check if company exists in Supabase
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
    if extra_pages:
        print(f"   Extra pages to check: {extra_pages}")
    result = await scrape_one(company_id, company_name, domain, extra_pages=extra_pages)

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

    print(f"   Maintenance Plans: {len(result.get('maintenance_plans', []))}")
    if result.get('maintenance_plans'):
        print(f"      🎯 {', '.join(result['maintenance_plans'])}")

    print(f"   Owner Bios: {len(result.get('owner_bios', []))}")
    if result.get('owner_bios'):
        for bio in result['owner_bios'][:2]:
            if bio.get('bio_snippet'):
                name = bio.get('name', 'Unknown')
                snippet = bio['bio_snippet'][:100]
                print(f"      💡 {name}: \"{snippet}...\"")

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

    # AI-Powered Sales Intel (if --ai flag used)
    sales_intel = None
    if use_ai:
        print(f"\n🤖 Running AI Sales Intelligence Analysis...")
        try:
            # Import the agent here to avoid slow startup when not using --ai
            from app.services.langgraph.agents.sales_intel_agent import extract_sales_intel

            # Get primary ATL contact for personalization
            primary_contact = atl_contacts[0] if atl_contacts else {'name': 'Owner', 'title': 'Owner'}

            # Build raw content for AI analysis (combine all scraped text)
            raw_content = "\n".join([
                f"Company: {company_name}",
                f"Services: {', '.join(result.get('services', []))}",
                f"Brands: {', '.join(result.get('brands', []))}",
                "",
                "--- Scraped Content ---",
                result.get('raw_text', '')[:10000],  # Limit to 10k chars
            ])

            # Get location from result or Supabase
            location = f"{result.get('city', '')}, {result.get('state', '')}".strip(', ')

            sales_intel = await extract_sales_intel(
                company_name=company_name,
                contact_name=primary_contact['name'],
                contact_title=primary_contact['title'],
                scraped_content=raw_content,
                services=result.get('services', []),
                brands=result.get('brands', []),
                location=location or None,
            )

            print(f"   ✅ AI analysis complete in {sales_intel.get('processing_time_ms', 0)}ms")
            print(f"   📊 Confidence: {sales_intel.get('confidence', 0):.0%}")
            print(f"   🎯 Personal hooks found: {len(sales_intel.get('personal_hooks', []))}")

        except ImportError as e:
            print(f"   ⚠️ SalesIntelAgent not available: {e}")
            print(f"   (Check CEREBRAS_API_KEY is set)")
        except Exception as e:
            print(f"   ❌ AI analysis failed: {e}")

    # Print SALES CARD for Close CRM copy/paste
    print_sales_card(company_name, domain, result, atl_contacts, btl_contacts, close_lead, close_contacts, sales_intel)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse arguments
    args = sys.argv[1:]

    # Check for --ai flag
    use_ai = '--ai' in args
    if use_ai:
        args = [a for a in args if a != '--ai']

    # Check if first arg looks like a domain (contains a dot and no spaces)
    if '.' in args[0] and ' ' not in args[0] and not args[0].startswith('/'):
        # First arg is domain
        domain = args[0]
        company_name = None
        extra_pages = args[1:] if len(args) > 1 else None
    else:
        # First arg is company name, second is domain
        company_name = args[0]
        domain = args[1] if len(args) > 1 else None
        extra_pages = args[2:] if len(args) > 2 else None

        if not domain:
            print("❌ ERROR: Domain is required")
            print(__doc__)
            sys.exit(1)

    # Filter out any empty extra_pages and flags
    if extra_pages:
        extra_pages = [p for p in extra_pages if p.strip() and not p.startswith('--')]
        if not extra_pages:
            extra_pages = None

    asyncio.run(scrape_domain(domain, company_name, extra_pages, use_ai))


if __name__ == '__main__':
    main()
