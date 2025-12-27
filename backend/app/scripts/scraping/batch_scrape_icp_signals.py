#!/usr/bin/env python3
"""
Batch Scrape ICP Signals for All Companies
===========================================
Re-scrapes ALL companies to populate the 15 ICP signals using the upgraded scraper.

Runs in batches of 25 companies. 100% FREE (no paid APIs).

Usage:
    python3 batch_scrape_icp_signals.py              # Start batch 0
    python3 batch_scrape_icp_signals.py --batch 5    # Resume from batch 5
    python3 batch_scrape_icp_signals.py --auto       # Run all batches non-stop

Author: Claude + Tim
Date: Dec 22, 2025
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from app.services.website_content_scraper import WebsiteContentScraper
from app.services.save_verifier import SaveVerifier
import argparse

load_dotenv(Path(__file__).parent.parent / '.env')

# Config
BATCH_SIZE = 25
DELAY_BETWEEN_COMPANIES = 2  # seconds (be polite to servers)

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Initialize SaveVerifier for mandatory readback verification
save_verifier = SaveVerifier(supabase, max_retries=2)


async def scrape_and_save(company: dict, scraper: WebsiteContentScraper):
    """Scrape company website and save ICP signals"""
    company_id = company["company_id"]
    company_name = company["company_name"]
    website = company.get("website") or company.get("domain")

    if not website:
        print(f"⏭️  {company_name}: No website")
        return {"status": "skipped", "reason": "no_website"}

    # Ensure https://
    if not website.startswith('http'):
        website = f'https://{website}'

    print(f"🔍 {company_name[:40]:<40} ", end='', flush=True)

    try:
        # Scrape website
        result = await scraper.scrape_website(website)

        if not result or result.get('error'):
            print(f"❌ scrape error")
            return {"status": "failed"}

        signals = result.get("signals", {})

        # Update ALL 15 signals
        update_data = {
            # HIGH-VALUE SIGNALS (7)
            'has_design_build': signals.get('has_design_build', False),
            'has_engineering': signals.get('has_engineering', False),
            'has_medical_specialization': signals.get('has_medical_specialization', False),
            'has_building_automation': signals.get('has_building_automation', False),
            'has_oem_partnerships': signals.get('has_oem_partnerships', False),
            'has_awards': signals.get('has_awards', False),
            'has_emergency_service': signals.get('has_emergency_service', False),

            # STANDARD SIGNALS (6)
            'has_generators': signals.get('has_generators', False),
            'has_commercial': signals.get('has_commercial', False),
            'has_industrial': signals.get('has_industrial', False),
            'has_membership': signals.get('has_maintenance_plan', False),  # Map maintenance_plan to membership
            'has_specials': signals.get('has_specials', False),
            'has_financing': signals.get('has_financing', False),

            # Other enrichment fields
            'is_hiring': signals.get('is_hiring', False),
            'enrichment_status': 'free_enriched',
            'ai_enriched_at': datetime.utcnow().isoformat(),
        }

        # Count signals before saving
        signal_count = sum([
            update_data['has_design_build'], update_data['has_engineering'],
            update_data['has_medical_specialization'], update_data['has_building_automation'],
            update_data['has_oem_partnerships'], update_data['has_awards'],
            update_data['has_emergency_service'], update_data['has_generators'],
            update_data['has_commercial'], update_data['has_industrial'],
            update_data['has_membership'], update_data['has_specials'],
            update_data['has_financing']
        ])

        # Extract signal fields only for verification
        signal_fields = {k: v for k, v in update_data.items()
                        if k.startswith('has_') or k == 'is_hiring'}

        # Use SaveVerifier with mandatory readback verification
        success, error = save_verifier.update_company_signals(
            company_id=company_id,
            signals=signal_fields,
            source="free_scraper"
        )

        if success:
            # Also update enrichment status metadata (not verified, but less critical)
            supabase.table('dim_companies').update({
                'enrichment_status': 'free_enriched',
                'ai_enriched_at': datetime.utcnow().isoformat(),
            }).eq('company_id', company_id).execute()

            print(f"✅ {signal_count}/13 signals (verified)")
            return {"status": "success", "signals": signal_count}
        else:
            print(f"⚠️ {signal_count}/13 signals - verify failed: {error}")
            return {"status": "verify_failed", "signals": signal_count, "error": error}

    except Exception as e:
        print(f"❌ error: {str(e)[:30]}")
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
    print(f"BATCH {batch_num}/{total_batches - 1} ({len(batch_companies)} companies)")
    print(f"Companies {start_idx + 1}-{end_idx} of {total_companies}")
    print("=" * 80 + "\n")

    # Initialize scraper
    scraper = WebsiteContentScraper()

    # Track results
    successful = 0
    failed = 0
    skipped = 0

    start_time = datetime.now()

    # Process each company
    for i, company in enumerate(batch_companies):
        result = await scrape_and_save(company, scraper)

        if result["status"] == "success":
            successful += 1
        elif result["status"] == "skipped":
            skipped += 1
        else:
            failed += 1

        # Delay between companies (except last one)
        if i < len(batch_companies) - 1:
            await asyncio.sleep(DELAY_BETWEEN_COMPANIES)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Batch summary
    print("\n" + "-" * 80)
    print(f"BATCH {batch_num} COMPLETE")
    print(f"✅ Success: {successful} | ❌ Failed: {failed} | ⏭️  Skipped: {skipped}")
    print(f"⏱️  Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print("-" * 80 + "\n")

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
                print(f"\nTo resume, run: python3 batch_scrape_icp_signals.py --batch {batch_num + 1}\n")
    else:
        print("\n" + "=" * 80)
        print("🎉 ALL BATCHES COMPLETE!")
        print(f"Total companies processed: {total_companies}")
        print("=" * 80 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Batch scrape ICP signals for all companies")
    parser.add_argument('--batch', type=int, default=0, help='Batch number to start from (default: 0)')
    parser.add_argument('--auto', action='store_true', help='Auto mode: run all batches non-stop')
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("ICP SIGNAL BATCH SCRAPER")
    print("=" * 80)
    print(f"Batch size: {BATCH_SIZE} companies")
    print(f"Delay: {DELAY_BETWEEN_COMPANIES}s between companies")
    print(f"Mode: {'AUTO (non-stop)' if args.auto else 'INTERACTIVE (batch-by-batch)'}")
    print("=" * 80)

    await run_batch(args.batch, auto=args.auto)


if __name__ == "__main__":
    asyncio.run(main())
