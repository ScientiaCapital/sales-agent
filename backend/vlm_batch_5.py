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

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Import VLM services
from app.services.website_crawler import WebsiteCrawler
from app.services.vlm_contact_extractor import VLMContactExtractor

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Config
BATCH_SIZE = 5
MAX_PAGES_PER_COMPANY = 10
DELAY_BETWEEN_COMPANIES = 2


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

        # Get all companies with websites
        all_query = supabase.table("dim_companies") \
            .select("company_id, company_name, website, domain, icp_tier, icp_score, source_type") \
            .not_.is_("website", "null")

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
        .not_.is_("website", "null")

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
    """Save a single contact to dim_contacts."""
    full_name = contact.get("name", "").strip()
    if not full_name or len(full_name) < 3:
        return False, "Invalid name"

    first_name, last_name = parse_name(full_name)
    confidence_score = confidence_to_score(contact.get("confidence", "MEDIUM"))

    # Check for existing
    existing = supabase.table("dim_contacts") \
        .select("contact_id") \
        .eq("company_id", company_id) \
        .eq("full_name", full_name) \
        .execute()

    if existing.data:
        return False, f"Exists: {full_name}"

    # Determine if ATL based on title
    title = contact.get("title", "").lower()
    is_atl = any(t in title for t in [
        "ceo", "cfo", "coo", "cto", "cmo", "president", "owner", "founder",
        "vice president", "vp", "director", "chief", "partner", "principal",
        "general manager", "gm", "managing"
    ])

    contact_data = {
        "contact_id": str(uuid4()),
        "company_id": company_id,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "title": contact.get("title", ""),
        "email": contact.get("email"),
        "is_atl": is_atl,
        "confidence": confidence_score,
        "source": "vlm_screenshot",
        "validated": False,
    }

    try:
        supabase.table("dim_contacts").insert(contact_data).execute()
        return True, f"{full_name} - {contact.get('title', 'no title')}"
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"


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

    # Step 2: VLM extraction on each page
    print("\n Step 2: VLM extraction...")
    all_contacts = []
    total_cost = 0.0
    team_page_url = None

    for page in pages:
        if not page.screenshot_path:
            continue

        try:
            result = await extractor.extract_contacts(
                screenshot_path=Path(page.screenshot_path),
                page_url=page.url,
                page_text=page.text[:1000] if page.text else "",
            )

            contacts = result.get("contacts", [])
            cost = result.get("cost", 0)
            total_cost += cost

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

    # Step 4: Update company
    update_company_after_enrichment(company_id, saved_count, team_page_url)

    print(f"\n Summary:")
    print(f"  Pages: {len(pages)}, Cost: ${total_cost:.4f}")
    print(f"  Contacts saved: {saved_count}/{len(seen_names)}")

    status = "success" if saved_count > 0 else "no_contacts"
    return {
        "company_name": company_name,
        "status": status,
        "contacts_saved": saved_count,
        "contacts_found": len(seen_names),
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

    # Process each company
    results = []
    total_cost = 0.0
    total_contacts = 0

    for i, company in enumerate(companies):
        result = await process_company(company, crawler, extractor, dry_run)
        results.append(result)

        total_cost += result.get("cost_usd", 0)
        total_contacts += result.get("contacts_saved", 0)

        # Delay between companies
        if i < len(companies) - 1 and not dry_run:
            print(f"\nWaiting {DELAY_BETWEEN_COMPANIES}s before next company...")
            await asyncio.sleep(DELAY_BETWEEN_COMPANIES)

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
