#!/usr/bin/env python3
"""
VLM Batch-of-5 Contact Extraction
==================================
Processes 5 companies at a time using VLM screenshot extraction.
Saves contacts to Supabase with verification after each company.

Usage:
    python3 vlm_batch_5.py                    # Start from beginning
    python3 vlm_batch_5.py --offset 5         # Start from company 6
    python3 vlm_batch_5.py --tier PLATINUM    # Only PLATINUM tier
    python3 vlm_batch_5.py --source spw       # Only SPW (Solar Power World) companies
    python3 vlm_batch_5.py --source amicus    # Only Amicus Solar companies
    python3 vlm_batch_5.py --source solar     # Both SPW + Amicus
    python3 vlm_batch_5.py --no-contacts      # Only companies with 0 contacts
    python3 vlm_batch_5.py --test             # Dry run

Author: Claude + Tim
Date: Dec 23, 2025
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import argparse
from uuid import uuid4

# Add backend to path (for app.services imports)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment
load_dotenv(Path(__file__).parent.parent.parent.parent / '.env', override=True)

# Import VLM services
from app.services.website_crawler import WebsiteCrawler
from app.services.vlm_contact_extractor import VLMContactExtractor
from app.services.save_verifier import SaveVerifier

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Initialize SaveVerifier for mandatory readback verification
save_verifier = SaveVerifier(supabase, max_retries=2)

# Config
BATCH_SIZE = 3
MAX_PAGES_PER_COMPANY = 10  # Optimized for speed - fail fast on slow sites
DELAY_BETWEEN_COMPANIES = 2
CONCURRENT_COMPANIES = 3      # Max companies processing at once
CONCURRENT_SCREENSHOTS = 3    # Max screenshots per company at once


def get_companies_to_process(tier: str = None, source: str = None, offset: int = 0, limit: int = BATCH_SIZE, no_contacts: bool = False) -> list:
    """
    Get companies that need VLM enrichment.

    Priority:
    1. Has website
    2. No contacts yet (or low count)
    3. PLATINUM/GOLD tier first

    Source filters:
    - 'spw': Solar Power World companies only
    - 'amicus': Amicus Solar companies only
    - 'solar': Both SPW + Amicus
    """
    # If filtering for companies with 0 contacts, get those IDs first
    if no_contacts:
        # Get all company IDs that have contacts
        contacts = supabase.table("dim_contacts").select("company_id").execute()
        cos_with_contacts = set(c["company_id"] for c in contacts.data)

        # Get all companies with websites that haven't been enriched yet
        all_query = supabase.table("dim_companies") \
            .select("company_id, company_name, website, domain, icp_tier, icp_score, source_type") \
            .not_.is_("website", "null") \
            .is_("last_enriched_at", "null")  # Skip already-enriched companies

        if tier:
            all_query = all_query.eq("icp_tier", tier.upper())

        if source:
            source = source.lower()
            if source == 'spw':
                all_query = all_query.eq("source_type", "spw_scraper")
            elif source == 'amicus':
                all_query = all_query.eq("source_type", "amicus_scraper")
            elif source == 'solar':
                all_query = all_query.in_("source_type", ["spw_scraper", "amicus_scraper"])

        all_companies = all_query.execute().data

        # Filter to only those with 0 contacts
        no_contact_companies = [c for c in all_companies if c["company_id"] not in cos_with_contacts]

        # Sort by tier priority (PLATINUM > GOLD > SILVER > BRONZE)
        tier_order = {"PLATINUM": 0, "GOLD": 1, "SILVER": 2, "BRONZE": 3, None: 4}
        no_contact_companies.sort(key=lambda x: (tier_order.get(x.get("icp_tier"), 4), -(x.get("icp_score") or 0)))

        # Apply pagination
        return no_contact_companies[offset:offset + limit]

    query = supabase.table("dim_companies") \
        .select("company_id, company_name, website, domain, icp_tier, icp_score, source_type") \
        .not_.is_("website", "null") \
        .is_("last_enriched_at", "null")  # Skip already-enriched companies

    if tier:
        query = query.eq("icp_tier", tier.upper())

    # Source filtering for solar companies
    if source:
        source = source.lower()
        if source == 'spw':
            query = query.eq("source_type", "spw_scraper")
        elif source == 'amicus':
            query = query.eq("source_type", "amicus_scraper")
        elif source == 'solar':
            query = query.in_("source_type", ["spw_scraper", "amicus_scraper"])

    # Order by tier priority and score
    query = query.order("icp_score", desc=True)

    # Apply pagination
    result = query.range(offset, offset + limit - 1).execute()

    return result.data


def parse_name(full_name: str) -> tuple[str, str]:
    """Parse full name into first and last name."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], " ".join(parts[1:])


def confidence_to_score(confidence: str) -> int:
    """Convert VLM confidence to numeric score."""
    return {"HIGH": 90, "MEDIUM": 70, "LOW": 50}.get(confidence.upper(), 50)


async def save_contact(company_id: str, contact: dict) -> tuple[bool, str]:
    """
    Save a single contact to dim_contacts using SaveVerifier.

    Uses mandatory readback verification to ensure data is actually saved.
    """
    full_name = contact.get("name", "").strip()
    if not full_name or len(full_name) < 3:
        return False, "Invalid name"

    first_name, last_name = parse_name(full_name)
    confidence_score = confidence_to_score(contact.get("confidence", "MEDIUM"))

    # Determine if ATL based on title
    title = contact.get("title", "").lower()
    is_atl = any(t in title for t in [
        "ceo", "cfo", "coo", "cto", "cmo", "president", "owner", "founder",
        "vice president", "vp", "director", "chief", "partner", "principal",
        "general manager", "gm", "managing"
    ])

    contact_data = {
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "title": contact.get("title", ""),
        "email": contact.get("email"),
        "is_atl": is_atl,
        "confidence": confidence_score,
    }

    # Use SaveVerifier with mandatory readback verification
    success, contact_id, error = save_verifier.save_contact(
        company_id=company_id,
        contact_data=contact_data,
        source="vlm_screenshot"
    )

    if success:
        return True, f"{full_name} - {contact.get('title', 'no title')}"
    else:
        return False, error or f"Failed: {full_name}"


def save_visual_signals(company_id: str, signals: dict) -> tuple[bool, str]:
    """
    Save VLM-extracted visual signals to dim_companies.

    Uses SaveVerifier with mandatory readback verification.
    """
    if not signals:
        return False, "No signals to save"

    # Filter to only valid VLM signal columns
    vlm_signals = {}
    valid_keys = {
        "has_design_build", "has_engineering", "has_medical_specialization",
        "has_building_automation", "has_awards", "has_oem_partnerships"
    }

    for key, value in signals.items():
        if key in valid_keys:
            vlm_signals[key] = bool(value)

    if not vlm_signals:
        return False, "No valid signals"

    # Use SaveVerifier with mandatory readback verification
    success, error = save_verifier.update_company_signals(
        company_id=company_id,
        signals=vlm_signals,
        source="vlm_screenshot"
    )

    if success:
        return True, f"Saved {len(vlm_signals)} signals"
    else:
        return False, error or "Signal save failed"


def update_company_after_enrichment(company_id: str, contacts_found: int, team_page_url: str = None):
    """Update company record after VLM enrichment."""
    update_data = {
        "enrichment_status": "vlm_enriched",
        "last_enriched_at": datetime.utcnow().isoformat(),
    }

    if team_page_url:
        update_data["team_page_url"] = team_page_url

    supabase.table("dim_companies").update(update_data).eq("company_id", company_id).execute()


async def process_company(
    company: dict,
    crawler: WebsiteCrawler,
    extractor: VLMContactExtractor,
    dry_run: bool = False
) -> dict:
    """
    Process a single company with VLM extraction.

    Returns:
        {
            "company_name": str,
            "status": "success" | "failed" | "no_contacts",
            "contacts_saved": int,
            "contacts_found": int,
            "cost_usd": float,
            "pages_crawled": int
        }
    """
    company_id = company["company_id"]
    company_name = company["company_name"]
    website = company.get("website") or company.get("domain")

    if not website:
        return {"company_name": company_name, "status": "no_website", "contacts_saved": 0}

    if not website.startswith("http"):
        website = f"https://{website}"

    print(f"\n{'=' * 60}")
    print(f"Processing: {company_name}")
    print(f"Website: {website}")
    print(f"Tier: {company.get('icp_tier', 'N/A')} | Score: {company.get('icp_score', 'N/A')}")
    print("=" * 60)

    if dry_run:
        print("  [DRY RUN] Would crawl and extract")
        return {"company_name": company_name, "status": "dry_run", "contacts_saved": 0}

    # Step 1: Crawl website
    print("\n Step 1: Crawling website...")
    try:
        pages = await crawler.crawl_website(
            website_url=website,
            max_pages=MAX_PAGES_PER_COMPANY,
            max_depth=3,
            company_id=company_id,
        )
        print(f"  Crawled {len(pages)} pages")
    except Exception as e:
        print(f"  Crawl failed: {str(e)[:50]}")
        return {"company_name": company_name, "status": "crawl_failed", "contacts_saved": 0}

    if not pages:
        return {"company_name": company_name, "status": "no_pages", "contacts_saved": 0}

    # Step 2: VLM extraction on each page (parallel processing)
    print("\n Step 2: VLM extraction...")
    all_contacts = []
    total_cost = 0.0
    team_page_url = None
    all_signals = {}  # Aggregate signals from all pages

    # Build tasks for parallel execution
    tasks = []
    page_map = {}
    for page in pages:
        if not page.screenshot_path:
            continue
        task = extractor.extract_contacts(
            screenshot_path=Path(page.screenshot_path),
            page_url=page.url,
            page_text=page.text[:1000] if page.text else "",
        )
        tasks.append(task)
        page_map[len(tasks) - 1] = page

    # Process in batches of CONCURRENT_SCREENSHOTS
    all_results = []
    for i in range(0, len(tasks), CONCURRENT_SCREENSHOTS):
        batch = tasks[i:i + CONCURRENT_SCREENSHOTS]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        for idx, result in enumerate(batch_results):
            all_results.append((i + idx, result))

    # Process results
    for idx, result in all_results:
        page = page_map[idx]

        if isinstance(result, Exception):
            print(f"    {page.url[:50]}... -> Error: {str(result)[:30]}")
            continue

        try:
            contacts = result.get("contacts", [])
            cost = result.get("cost", 0)
            total_cost += cost

            # Collect ICP signals (OR logic - any True stays True)
            page_signals = result.get("icp_signals", {})
            for key, value in page_signals.items():
                if value:  # Only update if True
                    all_signals[key] = True

            if contacts:
                print(f"    {page.url[:50]}... -> {len(contacts)} contacts")
                all_contacts.extend(contacts)
                # Track first page with contacts as team page
                if not team_page_url and len(contacts) > 1:
                    team_page_url = page.url

        except Exception as e:
            print(f"    {page.url[:50]}... -> Error: {str(e)[:30]}")

    # Step 3: Deduplicate and save
    print(f"\n Step 3: Saving {len(all_contacts)} contacts...")
    seen_names = set()
    saved_count = 0
    atl_count = 0

    for contact in all_contacts:
        name = contact.get("name", "").strip()
        if name in seen_names or not name:
            continue
        seen_names.add(name)

        success, msg = await save_contact(company_id, contact)
        if success:
            saved_count += 1
            if "chief" in contact.get("title", "").lower() or "ceo" in contact.get("title", "").lower():
                atl_count += 1
            print(f"    Saved: {msg}")
        else:
            print(f"    Skip: {msg}")

    # Step 4: Save visual signals
    signals_saved = 0
    if all_signals:
        print(f"\n Step 4: Saving {len(all_signals)} visual signals...")
        success, msg = save_visual_signals(company_id, all_signals)
        if success:
            signals_saved = len(all_signals)
            print(f"    {msg}")
        else:
            print(f"    Signal save failed: {msg}")

    # Step 5: Update company enrichment status
    update_company_after_enrichment(company_id, saved_count, team_page_url)

    print(f"\n Summary:")
    print(f"  Pages: {len(pages)}, Cost: ${total_cost:.4f}")
    print(f"  Contacts saved: {saved_count}/{len(seen_names)}")
    print(f"  Signals saved: {signals_saved}")

    status = "success" if saved_count > 0 else "no_contacts"
    return {
        "company_name": company_name,
        "status": status,
        "contacts_saved": saved_count,
        "contacts_found": len(seen_names),
        "signals_saved": signals_saved,
        "cost_usd": total_cost,
        "pages_crawled": len(pages),
    }


async def run_batch(offset: int = 0, tier: str = None, source: str = None, dry_run: bool = False, no_contacts: bool = False):
    """Run a batch of 5 companies."""

    # Get companies
    companies = get_companies_to_process(tier=tier, source=source, offset=offset, limit=BATCH_SIZE, no_contacts=no_contacts)

    if not companies:
        print(f"\nNo companies found at offset {offset}")
        return

    print("\n" + "=" * 70)
    print(f"VLM BATCH EXTRACTION - Companies {offset + 1} to {offset + len(companies)}")
    print("=" * 70)
    print(f"Tier filter: {tier or 'All'}")
    print(f"Source filter: {source or 'All'}")
    print(f"No contacts filter: {no_contacts}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 70)

    # Initialize services
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        print("\nERROR: OPENROUTER_API_KEY not set")
        return

    crawler = WebsiteCrawler()
    extractor = VLMContactExtractor(api_key=openrouter_key)

    print(f"\nVLM Model: {extractor.primary_model}")
    print(f"Fallback: {extractor.fallback_model}")

    # Process companies in parallel with semaphore
    semaphore = asyncio.Semaphore(CONCURRENT_COMPANIES)
    results = []
    total_cost = 0.0
    total_contacts = 0

    async def process_with_limit(company):
        """Process company with concurrency limit."""
        async with semaphore:
            result = await process_company(company, crawler, extractor, dry_run)
            if not dry_run:
                await asyncio.sleep(DELAY_BETWEEN_COMPANIES)
            return result

    # Process all companies in parallel (up to CONCURRENT_COMPANIES at once)
    tasks = [process_with_limit(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any exceptions and calculate totals
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"\nCompany {i+1} failed: {str(result)[:50]}")
            results[i] = {"company_name": companies[i]["company_name"], "status": "failed", "contacts_saved": 0}
        else:
            total_cost += result.get("cost_usd", 0)
            total_contacts += result.get("contacts_saved", 0)

    # Batch Summary
    print("\n" + "=" * 70)
    print("BATCH SUMMARY")
    print("=" * 70)

    success_count = len([r for r in results if r["status"] == "success"])
    no_contacts = len([r for r in results if r["status"] == "no_contacts"])
    failed = len([r for r in results if r["status"] not in ["success", "no_contacts", "dry_run"]])

    print(f"\nCompanies processed: {len(results)}")
    print(f"  Success (contacts found): {success_count}")
    print(f"  No contacts found: {no_contacts}")
    print(f"  Failed: {failed}")
    print(f"\nTotal contacts saved: {total_contacts}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Cost per contact: ${total_cost / max(1, total_contacts):.4f}")

    # Individual results
    print("\nPer-company breakdown:")
    for r in results:
        status_icon = "" if r["status"] == "success" else "" if r["status"] == "no_contacts" else ""
        print(f"  {status_icon} {r['company_name'][:30]:<30} -> {r.get('contacts_saved', 0)} contacts")

    # Next batch prompt
    if not dry_run and len(companies) == BATCH_SIZE:
        source_arg = f" --source {source}" if source else ""
        no_contacts_arg = " --no-contacts" if no_contacts else ""
        tier_arg = f" --tier {tier}" if tier else ""
        print(f"\n To continue: python3 vlm_batch_5.py --offset {offset + BATCH_SIZE}{source_arg}{tier_arg}{no_contacts_arg}")

    print("=" * 70 + "\n")

    return results


async def main():
    parser = argparse.ArgumentParser(description="VLM batch contact extraction")
    parser.add_argument('--offset', type=int, default=0, help='Starting offset (default: 0)')
    parser.add_argument('--tier', type=str, help='Filter by tier (PLATINUM, GOLD, SILVER, BRONZE)')
    parser.add_argument('--source', type=str, help='Filter by source: spw, amicus, or solar (both)')
    parser.add_argument('--no-contacts', action='store_true', dest='no_contacts', help='Only companies with 0 contacts')
    parser.add_argument('--test', action='store_true', help='Dry run - no changes')
    args = parser.parse_args()

    await run_batch(offset=args.offset, tier=args.tier, source=args.source, dry_run=args.test, no_contacts=args.no_contacts)


if __name__ == "__main__":
    asyncio.run(main())
