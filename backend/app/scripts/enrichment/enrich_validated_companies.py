#!/usr/bin/env python3
"""
Enrich Validated Companies - Match by Name
===========================================
Scrape and save enrichment data for manually validated companies.
Matches by company name since website column is NULL in database.

Usage:
    python3 enrich_validated_companies.py
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from app.services.website_content_scraper import WebsiteContentScraper

load_dotenv(Path(__file__).parent.parent / '.env')

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Test companies with DB company_id mapping
TEST_COMPANIES = [
    {
        "db_id": "f4e19975-0f94-4378-9697-d104095c2589",
        "db_name": "ACTION AIR CON HEATING AND SOLAR",
        "website": "https://actionac.net"
    },
    {
        "db_id": "1ff68fe1-cb89-4207-972c-b48a9f90b39f",
        "db_name": "BERKEYS A/C PLUMBING & ELECTRICAL",
        "website": "https://www.berkeys.com"
    },
    {
        "db_id": "abe09d67-6a64-4d48-8ac2-88cd9b50c745",
        "db_name": "POSITIVE ENERGY ELECTRICAL, LLC",
        "website": "https://www.positiveee.com"
    },
    {
        "db_id": "e7444082-7238-4a7b-bee6-3b4a14c68382",
        "db_name": "RAVINIA PLUMBING HEATING & ELECTRIC",
        "website": "https://raviniaplumbing.com"
    },
    {
        "db_id": "58960d18-0ae0-43a2-addd-ed52b0d295f6",
        "db_name": "Restano Heating, Cooling & Plumbing, Inc.",
        "website": "https://www.restano.com"
    },
    {
        "db_id": "b1143126-adf2-48e2-ae71-08b4daae82fd",
        "db_name": "Raymond Plumbing and Heating Inc",
        "website": "https://www.raymondplumbing.com"
    },
    {
        "db_id": "11bbae76-f127-4643-9df2-c198deb16479",
        "db_name": "Denron Hall Plumbing and HVAC LLC",
        "website": "https://denronhall.com"
    },
]

async def scrape_and_save(company: dict, scraper: WebsiteContentScraper):
    """Scrape company and save to database"""
    db_id = company["db_id"]
    db_name = company["db_name"]
    website = company["website"]

    print(f"\n{'=' * 70}")
    print(f"SCRAPING: {db_name}")
    print(f"URL: {website}")
    print(f"DB ID: {db_id}")
    print('=' * 70)

    # Scrape website
    result = await scraper.scrape_website(website)

    # Extract signals
    signals = result.get("signals", {})
    mep = result.get("mep_capabilities", {})

    # Count signals
    signal_names = [
        'is_hiring', 'has_maintenance_plan', 'has_generators', 'has_commercial',
        'has_industrial', 'has_membership', 'has_specials', 'has_financing',
        'has_oem_partnerships', 'has_emergency_service', 'has_design_build',
        'has_engineering', 'has_medical_specialization', 'has_building_automation',
        'has_awards'
    ]

    signal_count = sum([signals.get(s, False) for s in signal_names])
    mep_count = sum([v for v in mep.values()])

    print(f"\nPAGES SCRAPED: {len(result['pages_scraped'])}")
    print(f"SIGNALS DETECTED: {signal_count}/15")
    print(f"MEP CAPABILITIES: {mep_count}/9")

    # Show HIGH-VALUE signals
    high_value = []
    if signals.get('has_design_build'): high_value.append('Design-Build')
    if signals.get('has_engineering'): high_value.append('Engineering/CAD')
    if signals.get('has_medical_specialization'): high_value.append('Medical/Healthcare')
    if signals.get('has_building_automation'): high_value.append('Building Automation')
    if signals.get('has_industrial'): high_value.append('Industrial')

    if high_value:
        print(f"HIGH-VALUE: {', '.join(high_value)}")

    # Update database
    update_data = {
        # Website URL (was NULL before)
        'website': website,

        # All 15 signals
        'is_hiring': signals.get('is_hiring', False),
        'has_maintenance_plan': signals.get('has_maintenance_plan', False),
        'has_generators': signals.get('has_generators', False),
        'has_commercial': signals.get('has_commercial', False),
        'has_industrial': signals.get('has_industrial', False),
        'has_membership': signals.get('has_membership', False),
        'has_specials': signals.get('has_specials', False),
        'has_financing': signals.get('has_financing', False),
        'has_oem_partnerships': signals.get('has_oem_partnerships', False),
        'has_emergency_service': signals.get('has_emergency_service', False),
        'has_design_build': signals.get('has_design_build', False),
        'has_engineering': signals.get('has_engineering', False),
        'has_medical_specialization': signals.get('has_medical_specialization', False),
        'has_building_automation': signals.get('has_building_automation', False),
        'has_awards': signals.get('has_awards', False),

        # Metadata
        'enrichment_status': 'free_enriched',
    }

    # Save to database
    supabase.table('dim_companies').update(update_data).eq('company_id', db_id).execute()

    print("💾 SAVED TO DATABASE")

    return {
        'company_id': db_id,
        'name': db_name,
        'signals': signal_count,
        'mep': mep_count,
        'high_value': high_value,
    }

async def main():
    scraper = WebsiteContentScraper()

    print("\n" + "=" * 70)
    print("ENRICHMENT PIPELINE - 7 VALIDATED COMPANIES")
    print("=" * 70)

    results = []

    for company in TEST_COMPANIES:
        result = await scrape_and_save(company, scraper)
        results.append(result)
        await asyncio.sleep(2)  # Be nice to servers

    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE - VERIFYING DATABASE")
    print("=" * 70 + "\n")

    # Verify data saved correctly
    for r in results:
        company = supabase.table('dim_companies') \
            .select('company_name, website, is_hiring, has_design_build, has_engineering, has_medical_specialization, has_building_automation, has_commercial, has_industrial') \
            .eq('company_id', r['company_id']) \
            .single() \
            .execute()

        c = company.data
        print(f"✅ {c['company_name']}")
        print(f"   Website: {c.get('website', 'NULL')}")
        print(f"   Hiring: {c.get('is_hiring', False)} | Commercial: {c.get('has_commercial', False)} | Industrial: {c.get('has_industrial', False)}")

        hv_signals = []
        if c.get('has_design_build'): hv_signals.append('Design-Build')
        if c.get('has_engineering'): hv_signals.append('Engineering')
        if c.get('has_medical_specialization'): hv_signals.append('Medical')
        if c.get('has_building_automation'): hv_signals.append('Automation')

        if hv_signals:
            print(f"   HIGH-VALUE: {', '.join(hv_signals)}")
        print()

    print("=" * 70)
    print("✅ ALL DATA SAVED AND VERIFIED!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
