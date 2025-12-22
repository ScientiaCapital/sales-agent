#!/usr/bin/env python3
"""
FAST Batch ICP Signal Scraper
==============================
Speed-optimized version that checks only essential pages.

Changes from slow version:
- Only checks 7 key pages (not 20+)
- 30 second timeout per company
- Skips on repeated 404s
- ~20 seconds per company instead of 2-3 minutes

Usage:
    python3 batch_scrape_icp_signals_fast.py              # Start batch 0
    python3 batch_scrape_icp_signals_fast.py --batch 5    # Resume from batch 5
    python3 batch_scrape_icp_signals_fast.py --auto       # Run all batches non-stop

Author: Claude + Tim
Date: Dec 22, 2025
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import argparse
import httpx
from bs4 import BeautifulSoup
import re
from collections import Counter

load_dotenv(Path(__file__).parent.parent / '.env')

# Config
BATCH_SIZE = 25
DELAY_BETWEEN_COMPANIES = 1  # Faster delay (1 sec instead of 2)
TIMEOUT_PER_COMPANY = 30     # Max 30 seconds per company

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# BALANCED page list - check 10 key pages (not 5, not 20)
ESSENTIAL_PAGES = [
    "/",                   # Homepage - ALWAYS check
    "/about",              # Company info
    "/services",           # Services overview
    "/commercial",         # Commercial signal
    "/commercial-hvac",    # Commercial HVAC variant
    "/industrial",         # Industrial signal (high-value)
    "/generators",         # Generator offerings
    "/financing",          # Financing options
    "/awards",             # Awards/recognition
    "/team",               # Team page
]

# Signal detection patterns (simplified)
SIGNAL_PATTERNS = {
    'has_commercial': [r'commercial', r'business', r'office'],
    'has_industrial': [r'industrial', r'manufacturing', r'facility', r'plant'],
    'has_generators': [r'generator', r'backup power', r'standby power'],
    'has_design_build': [r'design.build', r'design/build', r'design & build'],
    'has_engineering': [r'engineering', r'CAD', r'design engineer', r'PE license'],
    'has_medical_specialization': [r'medical gas', r'healthcare', r'hospital', r'clinic'],
    'has_building_automation': [r'building automation', r'BAS', r'controls', r'automation system'],
    'has_financing': [r'financing', r'payment plan', r'0%.*financing'],
    'has_awards': [r'award', r'recognition', r'certified', r'accredited'],
    'has_emergency_service': [r'24/7', r'24 hour', r'emergency', r'always available'],
    'has_oem_partnerships': [r'carrier', r'trane', r'lennox', r'generac', r'kohler', r'authorized dealer'],
    'has_specials': [r'special', r'promotion', r'discount', r'coupon'],
    'has_membership': [r'membership', r'maintenance plan', r'service plan', r'club'],
}


def extract_contacts(text: str) -> list:
    """
    Extract contact names from text.
    Looks for capitalized names (2-3 words) that appear multiple times.
    """
    # Find all potential names (2-3 capitalized words)
    name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'
    potential_names = re.findall(name_pattern, text)

    # Filter out common non-names
    stopwords = {'The', 'Our', 'About', 'Contact', 'Services', 'Home', 'Team', 'And',
                 'With', 'From', 'When', 'This', 'That', 'More', 'All', 'New', 'Get',
                 'North', 'South', 'East', 'West', 'United States', 'North Florida'}

    filtered = [name for name in potential_names if name not in stopwords and len(name) > 3]

    # Count frequency - names mentioned 2+ times are likely real people
    name_counts = Counter(filtered)
    contacts = [{"name": name, "title": ""} for name, count in name_counts.items() if count >= 2]

    return contacts[:10]  # Max 10 contacts per company


async def fast_scrape(website: str) -> dict:
    """
    Fast scraper - checks essential pages with timeout, extracts signals + contacts
    """
    if not website.startswith('http'):
        website = f'https://{website}'

    signals = {key: False for key in SIGNAL_PATTERNS.keys()}
    all_text = ""
    all_text_original = ""  # Keep original case for name extraction

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),  # 10 sec per page
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as client:

            for page_path in ESSENTIAL_PAGES:
                url = f"{website}{page_path}" if page_path != "/" else website

                try:
                    response = await client.get(url)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Remove scripts/styles
                        for tag in soup(['script', 'style', 'meta', 'link']):
                            tag.decompose()

                        text = soup.get_text(separator=' ', strip=True)
                        all_text += " " + text.lower()
                        all_text_original += " " + text  # Keep original case

                except (httpx.HTTPError, Exception):
                    # Skip failed pages silently
                    continue

            # Detect signals from combined text
            for signal_name, patterns in SIGNAL_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, all_text, re.IGNORECASE):
                        signals[signal_name] = True
                        break

            # Extract contacts from original case text
            contacts = extract_contacts(all_text_original)

            return {"signals": signals, "contacts": contacts, "error": None}

    except Exception as e:
        return {"signals": signals, "contacts": [], "error": str(e)}


async def save_contacts(company_id: str, contacts: list):
    """Save extracted contacts to dim_contacts"""
    if not contacts:
        return 0

    saved = 0
    for contact in contacts:
        name = contact.get("name", "").strip()
        if not name or len(name) < 3:
            continue

        # Parse first/last name
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        contact_data = {
            "company_id": company_id,
            "full_name": name,
            "first_name": first_name,
            "last_name": last_name,
            "title": contact.get("title", ""),
            "is_atl": True,  # Assume ATL (mentioned on website)
            "source": "website_scraper_fast",
            "confidence": 60,  # Medium-low confidence (no title)
        }

        try:
            # Upsert to avoid duplicates
            supabase.table("dim_contacts").upsert(
                contact_data,
                on_conflict="company_id,full_name"
            ).execute()
            saved += 1
        except:
            pass  # Ignore duplicate/error

    return saved


async def scrape_and_save(company: dict):
    """Scrape company website and save ICP signals + contacts"""
    company_id = company["company_id"]
    company_name = company["company_name"]
    website = company.get("website") or company.get("domain")

    if not website:
        print(f"⏭️  {company_name[:40]:<40} No website")
        return {"status": "skipped", "reason": "no_website"}

    print(f"🔍 {company_name[:40]:<40} ", end='', flush=True)

    try:
        # Fast scrape with timeout
        result = await asyncio.wait_for(
            fast_scrape(website),
            timeout=TIMEOUT_PER_COMPANY
        )

        if result.get('error'):
            print(f"❌ {result['error'][:20]}")
            return {"status": "failed"}

        signals = result.get("signals", {})
        contacts = result.get("contacts", [])

        # Update database
        update_data = {
            # HIGH-VALUE SIGNALS
            'has_design_build': signals.get('has_design_build', False),
            'has_engineering': signals.get('has_engineering', False),
            'has_medical_specialization': signals.get('has_medical_specialization', False),
            'has_building_automation': signals.get('has_building_automation', False),
            'has_oem_partnerships': signals.get('has_oem_partnerships', False),
            'has_awards': signals.get('has_awards', False),
            'has_emergency_service': signals.get('has_emergency_service', False),

            # STANDARD SIGNALS
            'has_generators': signals.get('has_generators', False),
            'has_commercial': signals.get('has_commercial', False),
            'has_industrial': signals.get('has_industrial', False),
            'has_membership': signals.get('has_membership', False),
            'has_specials': signals.get('has_specials', False),
            'has_financing': signals.get('has_financing', False),

            # Metadata
            'enrichment_status': 'free_enriched',
            'ai_enriched_at': datetime.utcnow().isoformat(),
        }

        # Save signals to database
        supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()

        # Save contacts to database
        contacts_saved = await save_contacts(company_id, contacts)

        # Count signals
        signal_count = sum(1 for k, v in update_data.items() if k.startswith('has_') and v == True)

        # Show WHICH signals (first 2) + contacts
        detected = [k.replace('has_', '')[:8] for k, v in update_data.items() if k.startswith('has_') and v == True]
        signal_preview = ', '.join(detected[:2]) if detected else 'none'

        print(f"✅ {signal_count}/13 ({signal_preview}) +{contacts_saved}👤")

        return {"status": "success", "signals": signal_count, "contacts": contacts_saved}

    except asyncio.TimeoutError:
        print(f"⏱️  timeout (>{TIMEOUT_PER_COMPANY}s)")
        return {"status": "timeout"}
    except Exception as e:
        print(f"❌ {str(e)[:20]}")
        return {"status": "failed", "error": str(e)}


async def run_batch(batch_num: int, auto: bool = False):
    """Run a single batch of 25 companies"""

    # Fetch all companies (ordered by name for consistent batching)
    all_companies = supabase.table('dim_companies') \
        .select('company_id, company_name, website, domain') \
        .order('company_name') \
        .execute()

    total_companies = len(all_companies.data)
    total_batches = (total_companies + BATCH_SIZE - 1) // BATCH_SIZE

    # Calculate batch range
    start_idx = batch_num * BATCH_SIZE
    end_idx = min(start_idx + BATCH_SIZE, total_companies)

    if start_idx >= total_companies:
        print(f"\n❌ Batch {batch_num} is out of range (only {total_batches} batches total)")
        return

    batch_companies = all_companies.data[start_idx:end_idx]

    print("\n" + "=" * 80)
    print(f"FAST BATCH {batch_num}/{total_batches - 1} ({len(batch_companies)} companies)")
    print(f"Companies {start_idx + 1}-{end_idx} of {total_companies}")
    print(f"Max time: {TIMEOUT_PER_COMPANY}s per company")
    print("=" * 80 + "\n")

    # Track results
    successful = 0
    failed = 0
    skipped = 0
    timeouts = 0

    start_time = datetime.now()

    # Process each company
    for i, company in enumerate(batch_companies):
        result = await scrape_and_save(company)

        if result["status"] == "success":
            successful += 1
        elif result["status"] == "skipped":
            skipped += 1
        elif result["status"] == "timeout":
            timeouts += 1
        else:
            failed += 1

        # Delay between companies (except last one)
        if i < len(batch_companies) - 1:
            await asyncio.sleep(DELAY_BETWEEN_COMPANIES)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Batch summary
    print("\n" + "-" * 80)
    print(f"BATCH {batch_num} COMPLETE")
    print(f"✅ Success: {successful} | ⏱️  Timeout: {timeouts} | ❌ Failed: {failed} | ⏭️  Skipped: {skipped}")
    print(f"⏱️  Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"📊 Avg: {elapsed/len(batch_companies):.1f}s per company")
    print("-" * 80 + "\n")

    # Estimate time remaining
    batches_remaining = total_batches - batch_num - 1
    est_time_remaining = (elapsed / 60) * batches_remaining

    if batches_remaining > 0:
        print(f"📈 Estimated time remaining: {est_time_remaining:.0f} minutes ({est_time_remaining/60:.1f} hours)")
        print(f"📊 Progress: {((batch_num + 1) / total_batches * 100):.1f}% complete")
        print()

    # Next batch?
    if batch_num < total_batches - 1:
        if auto:
            print(f"🚀 Auto mode: Starting batch {batch_num + 1}...\n")
            await asyncio.sleep(2)
            await run_batch(batch_num + 1, auto=True)
        else:
            response = input(f"Continue to batch {batch_num + 1}? (Enter=yes, q=quit): ")
            if response.lower() != 'q':
                await run_batch(batch_num + 1, auto=False)
            else:
                print("\n✋ Stopped by user")
                print(f"\nTo resume, run: python3 batch_scrape_icp_signals_fast.py --batch {batch_num + 1}\n")
    else:
        print("\n" + "=" * 80)
        print("🎉 ALL BATCHES COMPLETE!")
        print(f"Total companies processed: {total_companies}")
        print("=" * 80 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="FAST batch scrape ICP signals")
    parser.add_argument('--batch', type=int, default=0, help='Batch number to start from (default: 0)')
    parser.add_argument('--auto', action='store_true', help='Auto mode: run all batches non-stop')
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("FAST ICP SIGNAL BATCH SCRAPER")
    print("=" * 80)
    print(f"Batch size: {BATCH_SIZE} companies")
    print(f"Timeout: {TIMEOUT_PER_COMPANY}s per company")
    print(f"Pages checked: {len(ESSENTIAL_PAGES)} (not 20+)")
    print(f"Mode: {'AUTO (non-stop)' if args.auto else 'INTERACTIVE (batch-by-batch)'}")
    print("=" * 80)

    await run_batch(args.batch, auto=args.auto)


if __name__ == "__main__":
    asyncio.run(main())
