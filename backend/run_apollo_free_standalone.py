#!/usr/bin/env python3
"""
Apollo Free Batch Enrichment - STANDALONE
==========================================

No app imports - uses Apollo API directly.
"""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client

# Config
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Garbage filtering
DEFINITELY_GARBAGE_NAMES = {
    'log in', 'login', 'sign up', 'signup', 'sign in', 'check continue',
    'apply now', 'get started', 'read more', 'learn more', 'click here',
    'view all', 'see all', 'show more', 'load more', 'submit',
    'membership careers', 'create account', 'my account', 'forgot password',
    'los angeles', 'new york', 'san francisco', 'san diego', 'san jose',
    'las vegas', 'santa monica', 'santa ana', 'long beach', 'fort worth',
    'salt lake', 'palm springs', 'palm beach', 'newport beach',
    'service area', 'areas served', 'cities served', 'we serve',
    'preventative maintenance', 'preventive maintenance', 'routine maintenance',
    'customer service', 'technical support', 'emergency service',
    'free estimate', 'free quote', 'contact us', 'about us',
}
CITY_NAME_PREFIXES = {'los', 'las', 'san', 'santa', 'new', 'fort', 'palm', 'salt', 'long', 'newport'}


def is_garbage_contact(name: str, title: str = '') -> bool:
    """Check if a contact name is garbage."""
    name_lower = (name or '').strip().lower()
    if not name_lower:
        return True
    if name_lower in DEFINITELY_GARBAGE_NAMES:
        return True
    words = name_lower.split()
    if len(words) >= 2 and words[0] in CITY_NAME_PREFIXES:
        return True
    if len(name_lower) < 5:
        return True
    if len(words) < 2:
        return True
    if any(c.isdigit() for c in name_lower):
        return True
    return False


def extract_domain(website_url: str) -> str:
    """Extract domain from URL."""
    if not website_url:
        return ""
    if not website_url.startswith(('http://', 'https://')):
        website_url = 'https://' + website_url
    parsed = urlparse(website_url)
    domain = parsed.netloc or parsed.path.split('/')[0]
    return domain.lower().replace('www.', '')


async def apollo_enrich_company(domain: str, http_client: httpx.AsyncClient) -> dict:
    """Call Apollo company enrichment (FREE endpoint)."""
    from apollo_usage_tracker import log_api_call, log_rate_limit_hit

    response = await http_client.post(
        "https://api.apollo.io/api/v1/organizations/enrich",
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "x-api-key": APOLLO_API_KEY
        },
        params={"domain": domain},
        timeout=30.0
    )

    endpoint = "organizations/enrich"
    if response.status_code == 200:
        log_api_call(endpoint, success=True, response_code=200)
        return response.json().get("organization", {})
    elif response.status_code == 429:
        log_api_call(endpoint, success=False, response_code=429)
        reset_time = log_rate_limit_hit(endpoint, dict(response.headers))
        print(f"      ⏳ RATE LIMITED - Reset at {reset_time}")
        return {}
    else:
        log_api_call(endpoint, success=False, response_code=response.status_code)
        print(f"      Apollo company enrich failed: {response.status_code} - {response.text[:200]}")
        return {}


async def apollo_search_contacts(domain: str, http_client: httpx.AsyncClient) -> list:
    """Call Apollo people search (FREE - returns names/titles, no emails)."""
    from apollo_usage_tracker import log_api_call, log_rate_limit_hit

    response = await http_client.post(
        "https://api.apollo.io/api/v1/mixed_people/api_search",
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "x-api-key": APOLLO_API_KEY
        },
        json={
            "q_organization_domains_list": [domain],
            "person_titles": ["CEO", "President", "Owner", "Founder", "VP", "Director", "Chief", "Manager"],
            "per_page": 25,
            "page": 1
        },
        timeout=30.0
    )

    endpoint = "mixed_people/api_search"
    if response.status_code == 200:
        log_api_call(endpoint, success=True, response_code=200)
        return response.json().get("people", [])
    elif response.status_code == 429:
        log_api_call(endpoint, success=False, response_code=429)
        reset_time = log_rate_limit_hit(endpoint, dict(response.headers))
        print(f"      ⏳ RATE LIMITED - Reset at {reset_time}")
        return []
    else:
        log_api_call(endpoint, success=False, response_code=response.status_code)
        print(f"      Apollo contact search failed: {response.status_code} - {response.text[:200]}")
        return []


def save_contact(supabase, company_id: str, contact_data: dict) -> tuple:
    """Save contact with readback verification."""
    full_name = contact_data.get("full_name", "").strip()

    # Validate
    if not full_name or len(full_name) < 3:
        return False, None, "Name too short"
    if full_name.lower() in ["none", "none none", "null"]:
        return False, None, "Garbage name"

    # Check existing
    existing = supabase.table("dim_contacts") \
        .select("contact_id,full_name") \
        .eq("company_id", company_id) \
        .ilike("full_name", full_name.strip()) \
        .execute()

    if existing.data:
        return False, existing.data[0]["contact_id"], f"Exists"

    # Generate ID and insert
    contact_id = str(uuid4())
    insert_data = {
        "contact_id": contact_id,
        "company_id": company_id,
        "full_name": full_name,
        "first_name": contact_data.get("first_name", ""),
        "last_name": contact_data.get("last_name", ""),
        "title": contact_data.get("title", ""),
        "email": contact_data.get("email"),
        "phone": contact_data.get("phone"),
        "is_atl": contact_data.get("is_atl", False),
        "source": contact_data.get("source", "apollo_free"),
    }

    try:
        result = supabase.table("dim_contacts").insert(insert_data).execute()

        # Readback verification
        verify = supabase.table("dim_contacts") \
            .select("contact_id,full_name") \
            .eq("contact_id", contact_id) \
            .execute()

        if verify.data:
            return True, contact_id, None
        return False, None, "Readback failed"
    except Exception as e:
        return False, None, str(e)


async def run_apollo_free_enrichment():
    """Run Apollo Free enrichment on 5 PLATINUM companies."""
    from apollo_usage_tracker import can_call_apollo, print_status

    print("\n" + "="*60)
    print("🚀 Apollo FREE Enrichment - 5 PLATINUM Companies (Standalone)")
    print("="*60)

    # Check rate limit status first
    can_call, reason = can_call_apollo()
    if not can_call:
        print(f"⏳ {reason}")
        print_status()
        return

    # Verify config
    if not APOLLO_API_KEY:
        print("❌ APOLLO_API_KEY not set!")
        return
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase credentials not set!")
        return

    print(f"✅ Apollo API Key: {APOLLO_API_KEY[:10]}...")
    print(f"✅ Supabase URL: {SUPABASE_URL}")
    print(f"✅ Rate limit check: {reason}")

    # Load target companies
    target_file = Path("/tmp/target_companies.json")
    if not target_file.exists():
        print("❌ Target companies file not found!")
        return

    with open(target_file, 'r') as f:
        companies = json.load(f)

    print(f"\n📋 Loaded {len(companies)} companies")

    # Initialize clients
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Track results
    total_contacts_found = 0
    total_contacts_saved = 0
    total_garbage_filtered = 0

    async with httpx.AsyncClient() as http_client:
        for i, company in enumerate(companies, 1):
            company_id = company["company_id"]
            company_name = company["company_name"]
            website = company["website"]
            domain = extract_domain(website)

            print(f"\n{'─'*50}")
            print(f"[{i}/{len(companies)}] {company_name}")
            print(f"    🌐 Domain: {domain}")

            if not domain:
                print(f"    ⚠️  No domain - skipping")
                continue

            try:
                # 1. Enrich company (FREE)
                company_data = await apollo_enrich_company(domain, http_client)
                if company_data:
                    print(f"    ✅ Company: {company_data.get('name', 'N/A')} | {company_data.get('estimated_num_employees', '?')} employees")

                # 2. Search contacts (FREE - no emails)
                contacts = await apollo_search_contacts(domain, http_client)
                contact_count = len(contacts)
                total_contacts_found += contact_count

                print(f"    📊 Found {contact_count} contacts")

                # Process and save contacts
                saved_count = 0
                garbage_count = 0

                for contact in contacts:
                    full_name = contact.get("name", "")
                    title = contact.get("title", "")

                    # Garbage filter
                    if is_garbage_contact(full_name, title):
                        garbage_count += 1
                        print(f"    🗑️  Garbage: {full_name}")
                        continue

                    # Parse first/last name
                    name_parts = full_name.strip().split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

                    # Prepare contact data
                    contact_data = {
                        "full_name": full_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "title": title,
                        "email": contact.get("email"),  # Usually None in free tier
                        "phone": contact.get("phone"),
                        "is_atl": any(kw in title.lower() for kw in
                            ['owner', 'ceo', 'president', 'founder', 'director', 'vp', 'chief', 'executive', 'manager', 'partner']),
                        "source": "apollo_free"
                    }

                    # Save with verification
                    success, contact_id, error = save_contact(supabase, company_id, contact_data)

                    if success:
                        saved_count += 1
                        atl_flag = "🎯" if contact_data["is_atl"] else "📌"
                        print(f"    {atl_flag} Saved: {full_name} ({title})")
                    elif error != "Exists":
                        print(f"    ⏭️  {error}: {full_name}")

                total_contacts_saved += saved_count
                total_garbage_filtered += garbage_count

                print(f"    ✅ Saved {saved_count}, Filtered {garbage_count} garbage")

            except Exception as e:
                print(f"    ❌ Error: {e}")

    # Summary
    print("\n" + "="*60)
    print("📊 APOLLO FREE ENRICHMENT SUMMARY")
    print("="*60)
    print(f"  Companies processed: {len(companies)}")
    print(f"  Total contacts found: {total_contacts_found}")
    print(f"  Contacts saved: {total_contacts_saved}")
    print(f"  Garbage filtered: {total_garbage_filtered}")
    print("="*60)

    # Audit - verify saves in Supabase
    print("\n🔍 AUDIT: Verifying Supabase saves...")
    for company in companies:
        company_id = company["company_id"]
        company_name = company["company_name"]

        result = supabase.table("dim_contacts") \
            .select("contact_id, full_name, title, source") \
            .eq("company_id", company_id) \
            .execute()

        contacts = result.data or []
        print(f"\n  {company_name}: {len(contacts)} contacts in Supabase")
        for c in contacts:
            print(f"    • {c['full_name']} ({c['title']}) - source: {c.get('source', 'unknown')}")

    print("\n✅ Apollo Free enrichment complete!")


if __name__ == "__main__":
    asyncio.run(run_apollo_free_enrichment())
