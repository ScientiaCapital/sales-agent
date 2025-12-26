#!/usr/bin/env python3
"""
FREE Signals Extraction - BeautifulSoup only
=============================================

Extracts ICP signals from company websites using FREE methods:
- BeautifulSoup for HTML parsing
- No API calls, no cost

Signals detected:
- has_commercial: Commercial/business services
- has_industrial: Industrial/manufacturing work
- has_generators: Generator services (backup/standby power)
- has_design_build: Design-build capability
- has_engineering: Engineering services
- has_service_contracts: Service/maintenance contracts
"""

import asyncio
import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv("/Users/tmk/tk_projects/sales-agent/.env", override=True)

from supabase import create_client

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# ICP Signal patterns
SIGNAL_PATTERNS = {
    'has_commercial': [r'commercial', r'business', r'office', r'retail', r'multi.?family'],
    'has_industrial': [r'industrial', r'manufacturing', r'facility', r'plant', r'warehouse'],
    'has_generators': [r'generator', r'backup power', r'standby', r'generac', r'kohler', r'cummins'],
    'has_design_build': [r'design.?build', r'turnkey', r'design.?construct'],
    'has_engineering': [r'engineering', r'in.?house engineer', r'PE license'],
    'has_service_contracts': [r'service contract', r'maintenance agreement', r'preventive maintenance'],
    'has_solar': [r'solar', r'photovoltaic', r'pv system', r'solar panel'],
    'has_hvac': [r'\bhvac\b', r'heating', r'cooling', r'air conditioning'],
}

PAGES_TO_SCRAPE = ["/", "/about", "/about-us", "/services", "/contact"]


async def scrape_page(url: str, timeout: int = 10) -> str:
    """Scrape page HTML (FREE)"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                return response.text
    except Exception as e:
        pass
    return ""


def detect_signals(html: str) -> dict:
    """Detect ICP signals from page content"""
    signals = {}
    text = BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True).lower()

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        signals[signal_name] = any(re.search(p, text, re.I) for p in patterns)

    return signals


def extract_domain(website_url: str) -> str:
    """Extract domain from URL."""
    if not website_url:
        return ""
    if not website_url.startswith(('http://', 'https://')):
        website_url = 'https://' + website_url
    parsed = urlparse(website_url)
    return parsed.netloc or parsed.path.split('/')[0]


async def run_signals_extraction():
    """Extract signals from 5 PLATINUM companies."""

    print("\n" + "="*60)
    print("🔍 FREE Signals Extraction - 5 PLATINUM Companies")
    print("="*60)

    # Load target companies
    target_file = Path("/tmp/target_companies.json")
    if not target_file.exists():
        print("❌ Target companies file not found!")
        return

    with open(target_file, 'r') as f:
        companies = json.load(f)

    print(f"\n📋 Loaded {len(companies)} companies")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    for i, company in enumerate(companies, 1):
        company_id = company["company_id"]
        company_name = company["company_name"]
        website = company["website"]
        domain = extract_domain(website)

        print(f"\n{'─'*50}")
        print(f"[{i}/{len(companies)}] {company_name}")
        print(f"    🌐 Website: {website}")

        if not website:
            print(f"    ⚠️  No website - skipping")
            continue

        # Normalize URL
        base_url = website.rstrip('/')
        if not base_url.startswith('http'):
            base_url = f'https://{base_url}'

        # Scrape pages and collect HTML
        all_html = ""
        pages_scraped = 0

        for page in PAGES_TO_SCRAPE:
            url = f"{base_url}{page}"
            html = await scrape_page(url)
            if html:
                pages_scraped += 1
                all_html += html

        print(f"    📄 Scraped {pages_scraped} pages")

        if not all_html:
            print(f"    ⚠️  No content scraped")
            continue

        # Detect signals
        signals = detect_signals(all_html)

        # Count positive signals
        positive_signals = [k for k, v in signals.items() if v]
        print(f"    ✅ Signals detected: {len(positive_signals)}")

        for signal_name, detected in signals.items():
            if detected:
                print(f"       • {signal_name}")

        # Update company in Supabase (use actual column names)
        try:
            update_data = {
                "has_commercial": signals.get("has_commercial", False),
                "has_industrial": signals.get("has_industrial", False),
                "has_generators": signals.get("has_generators", False),
                "has_design_build": signals.get("has_design_build", False),
                "has_engineering": signals.get("has_engineering", False),
                "has_maintenance_plans": signals.get("has_service_contracts", False),
                "has_hvac_trade": signals.get("has_hvac", False),
            }
            result = supabase.table("dim_companies").update(update_data).eq("company_id", company_id).execute()

            if result.data:
                print(f"    💾 Saved to Supabase")
            else:
                print(f"    ⚠️  Update returned no data")

        except Exception as e:
            print(f"    ❌ Supabase error: {e}")

    # Audit
    print("\n" + "="*60)
    print("🔍 AUDIT: Verify signals in Supabase")
    print("="*60)

    for company in companies:
        result = supabase.table("dim_companies") \
            .select("company_name, has_commercial, has_industrial, has_generators, has_maintenance_plans, has_hvac_trade") \
            .eq("company_id", company["company_id"]) \
            .execute()

        if result.data:
            c = result.data[0]
            signals_str = []
            if c.get("has_commercial"): signals_str.append("commercial")
            if c.get("has_industrial"): signals_str.append("industrial")
            if c.get("has_generators"): signals_str.append("generators")
            if c.get("has_maintenance_plans"): signals_str.append("maintenance")
            if c.get("has_hvac_trade"): signals_str.append("hvac")

            print(f"\n  {c['company_name'][:40]}")
            print(f"    Signals: {', '.join(signals_str) if signals_str else 'none'}")

    print("\n✅ Signals extraction complete!")


if __name__ == "__main__":
    asyncio.run(run_signals_extraction())
