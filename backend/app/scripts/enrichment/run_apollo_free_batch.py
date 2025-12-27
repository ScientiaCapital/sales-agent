#!/usr/bin/env python3
"""
Apollo Free Batch Enrichment - 5 PLATINUM leads
================================================

Runs FREE Apollo enrichment on target companies:
1. Enrich company data (free)
2. Search contacts (free, no emails)
3. Filter garbage names
4. Save to Supabase with readback verification
5. Audit results
"""

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client
import os

# Garbage filtering from run_enrichment.py
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


async def run_apollo_free_enrichment():
    """Run Apollo Free enrichment on 5 PLATINUM companies."""

    print("\n" + "="*60)
    print("🚀 Apollo FREE Enrichment - 5 PLATINUM Companies")
    print("="*60)

    # Load target companies
    target_file = Path("/tmp/target_companies.json")
    if not target_file.exists():
        print("❌ Target companies file not found!")
        return

    with open(target_file, 'r') as f:
        companies = json.load(f)

    print(f"\n📋 Loaded {len(companies)} companies")

    # Initialize services
    from app.services.supervised_pipeline.stages.apollo_free import ApolloFreeStage
    from app.services.save_verifier import SaveVerifier

    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    verifier = SaveVerifier(supabase)
    apollo_stage = ApolloFreeStage()

    # Track results
    total_contacts_found = 0
    total_contacts_saved = 0
    total_garbage_filtered = 0

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

        # Execute Apollo Free stage
        result = await apollo_stage.execute({"domain": domain})

        if not result.success:
            print(f"    ❌ Apollo failed: {result.error}")
            continue

        contacts = result.data.get("contacts", [])
        contact_count = len(contacts)
        total_contacts_found += contact_count

        print(f"    📊 Found {contact_count} contacts ({result.latency_ms}ms)")

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
            success, contact_id, error = verifier.save_contact(
                company_id=company_id,
                contact_data=contact_data,
                source="apollo_free"
            )

            if success:
                saved_count += 1
                atl_flag = "🎯" if contact_data["is_atl"] else "📌"
                print(f"    {atl_flag} Saved: {full_name} ({title})")
            else:
                print(f"    ⏭️  {error}: {full_name}")

        total_contacts_saved += saved_count
        total_garbage_filtered += garbage_count

        print(f"    ✅ Saved {saved_count}, Filtered {garbage_count} garbage")

    # Cleanup
    await apollo_stage.close()

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
            print(f"    • {c['full_name']} ({c['title']}) - source: {c['source']}")

    print("\n✅ Apollo Free enrichment complete!")


if __name__ == "__main__":
    asyncio.run(run_apollo_free_enrichment())
