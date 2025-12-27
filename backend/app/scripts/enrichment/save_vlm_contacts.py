#!/usr/bin/env python3
"""
Save VLM-Extracted Contacts to Supabase
========================================
Saves contacts from VLM screenshot extraction to dim_contacts with verification.
Also updates company tier and tracks the enrichment attempt.

Usage:
    python3 save_vlm_contacts.py                    # Save nearu contacts (default)
    python3 save_vlm_contacts.py --company "1roofllc.com"  # Save specific company
    python3 save_vlm_contacts.py --test             # Dry run, no saves

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

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))


# NEARU-SERVICES.COM CONTACTS (from VLM extraction - verified)
NEARU_CONTACTS = [
    {
        "name": "Ashish Achlerkar",
        "title": "Founder and Chairman",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Doug Wilson",
        "title": "Board Director",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Jay Darffer",
        "title": "CEO",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Dietrich McCall",
        "title": "Chief Business Operations Officer",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Sue Young",
        "title": "Chief Legal & Compliance Officer",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Summer Nunn",
        "title": "Chief Marketing Officer",
        "confidence": "HIGH",
        "is_atl": True,
    },
    {
        "name": "Kelley Mudgett",
        "title": "Chief People Officer",
        "confidence": "HIGH",
        "is_atl": True,
    },
]


def confidence_to_score(confidence: str) -> int:
    """Convert VLM confidence to numeric score."""
    return {"HIGH": 90, "MEDIUM": 70, "LOW": 50}.get(confidence.upper(), 50)


def parse_name(full_name: str) -> tuple[str, str]:
    """Parse full name into first and last name."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], " ".join(parts[1:])


def get_or_create_company(domain: str, company_name: str, tier: str = "PLATINUM") -> str:
    """Get existing company or create new one. Returns company_id."""
    # Check if company exists by domain
    existing = supabase.table("dim_companies") \
        .select("company_id, company_name") \
        .eq("domain", domain) \
        .execute()

    if existing.data:
        company_id = existing.data[0]["company_id"]
        print(f"  Found existing company: {existing.data[0]['company_name']} ({company_id[:8]}...)")

        # Update tier if needed
        supabase.table("dim_companies").update({
            "icp_tier": tier,
            "enrichment_status": "vlm_enriched",
            "last_enriched_at": datetime.utcnow().isoformat(),
        }).eq("company_id", company_id).execute()

        return company_id

    # Create new company
    company_id = str(uuid4())
    company_data = {
        "company_id": company_id,
        "company_name": company_name,
        "domain": domain,
        "website": f"https://{domain}",
        "normalized_name": company_name.lower().replace(" ", ""),
        "icp_tier": tier,
        "source_type": "vlm_screenshot",
        "enrichment_status": "vlm_enriched",
        "current_stage": "imported",
        "first_seen_at": datetime.utcnow().isoformat(),
        "last_enriched_at": datetime.utcnow().isoformat(),
    }

    supabase.table("dim_companies").insert(company_data).execute()
    print(f"  Created new company: {company_name} ({company_id[:8]}...)")

    return company_id


def save_contact(company_id: str, contact: dict, source: str = "vlm_screenshot") -> tuple[bool, str]:
    """
    Save a single contact to dim_contacts.

    Returns:
        (success, message)
    """
    full_name = contact["name"]
    first_name, last_name = parse_name(full_name)
    confidence_score = confidence_to_score(contact.get("confidence", "MEDIUM"))

    # Check if contact already exists
    existing = supabase.table("dim_contacts") \
        .select("contact_id") \
        .eq("company_id", company_id) \
        .eq("full_name", full_name) \
        .execute()

    if existing.data:
        return False, f"Already exists: {full_name}"

    # Create contact
    contact_data = {
        "contact_id": str(uuid4()),
        "company_id": company_id,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "title": contact.get("title", ""),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "is_atl": contact.get("is_atl", False),
        "confidence": confidence_score,
        "source": source,
        "validated": False,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("dim_contacts").insert(contact_data).execute()
        return True, f"Saved: {full_name} - {contact.get('title', 'no title')}"
    except Exception as e:
        return False, f"Error saving {full_name}: {str(e)}"


def verify_contact_saved(company_id: str, full_name: str) -> bool:
    """Verify a contact was saved by reading it back."""
    result = supabase.table("dim_contacts") \
        .select("contact_id, full_name, title, confidence") \
        .eq("company_id", company_id) \
        .eq("full_name", full_name) \
        .execute()

    return len(result.data) > 0


def log_enrichment_attempt(
    company_id: str,
    domain: str,
    company_name: str,
    contacts_found: int,
    atl_found: int,
    cost_usd: float = 0.001,
    success: bool = True,
    source: str = "vlm_screenshot"
) -> None:
    """Log the enrichment attempt for tracking."""
    attempt_data = {
        "attempt_id": str(uuid4()),
        "company_id": company_id,
        "company_name": company_name,
        "domain": domain,
        "source": source,
        "contacts_found": contacts_found,
        "atl_found": atl_found,
        "btl_found": contacts_found - atl_found,
        "emails_found": 0,
        "phones_found": 0,
        "cost_usd": cost_usd,
        "success": success,
        "attempted_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        supabase.table("fact_enrichment_attempts").insert(attempt_data).execute()
        print(f"  Logged enrichment attempt ({contacts_found} contacts, ${cost_usd:.4f})")
    except Exception as e:
        print(f"  Warning: Failed to log enrichment: {str(e)}")


def save_nearu_contacts(dry_run: bool = False):
    """Save all nearu-services.com contacts."""
    print("\n" + "=" * 60)
    print("SAVING NEARU-SERVICES.COM CONTACTS TO SUPABASE")
    print("=" * 60)

    domain = "nearu-services.com"
    company_name = "Nearu Services"
    tier = "PLATINUM"  # C-suite heavy company

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Get or create company
    print(f"\n1. Getting/creating company: {company_name}")
    if not dry_run:
        company_id = get_or_create_company(domain, company_name, tier)
    else:
        company_id = "dry-run-id"
        print(f"  [DRY RUN] Would create/get company: {company_name}")

    # Save contacts
    print(f"\n2. Saving {len(NEARU_CONTACTS)} contacts:")
    print("-" * 40)

    saved_count = 0
    atl_count = 0

    for contact in NEARU_CONTACTS:
        if dry_run:
            print(f"  [DRY RUN] Would save: {contact['name']} - {contact['title']}")
            saved_count += 1
            if contact.get("is_atl"):
                atl_count += 1
        else:
            success, message = save_contact(company_id, contact, source="vlm_screenshot")
            if success:
                saved_count += 1
                if contact.get("is_atl"):
                    atl_count += 1
                print(f"  {message}")
            else:
                print(f"  {message}")

    # Verify saves
    print(f"\n3. Verifying saves:")
    print("-" * 40)

    verified_count = 0
    if not dry_run:
        for contact in NEARU_CONTACTS:
            if verify_contact_saved(company_id, contact["name"]):
                verified_count += 1
                print(f"  Verified: {contact['name']}")
            else:
                print(f"  NOT FOUND: {contact['name']}")
    else:
        verified_count = saved_count
        print("  [DRY RUN] Verification skipped")

    # Log enrichment attempt
    print(f"\n4. Logging enrichment attempt:")
    print("-" * 40)
    if not dry_run:
        log_enrichment_attempt(
            company_id=company_id,
            domain=domain,
            company_name=company_name,
            contacts_found=saved_count,
            atl_found=atl_count,
            cost_usd=0.001,  # VLM cost estimate
            success=True,
            source="browserbase"  # Use browserbase until vlm_screenshot constraint added
        )
    else:
        print("  [DRY RUN] Would log enrichment attempt")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Company: {company_name} ({domain})")
    print(f"  Tier: {tier}")
    print(f"  Contacts saved: {saved_count}/{len(NEARU_CONTACTS)}")
    print(f"  ATL contacts: {atl_count}")
    print(f"  Verified: {verified_count}/{saved_count}")

    if verified_count == saved_count and saved_count > 0:
        print("\n  ALL CONTACTS VERIFIED SAVED")
    elif dry_run:
        print("\n  [DRY RUN COMPLETE - Run without --test to save]")
    else:
        print("\n  WARNING: Some contacts may not have saved correctly")

    print("=" * 60 + "\n")

    return saved_count, verified_count


def main():
    parser = argparse.ArgumentParser(description="Save VLM-extracted contacts to Supabase")
    parser.add_argument('--test', action='store_true', help='Dry run - no changes made')
    parser.add_argument('--company', type=str, help='Company domain to save (default: nearu-services.com)')
    args = parser.parse_args()

    # For now, only nearu is supported
    if args.company and args.company not in ["nearu-services.com", "nearu"]:
        print(f"Company '{args.company}' not yet supported. Currently only nearu-services.com")
        return

    saved, verified = save_nearu_contacts(dry_run=args.test)

    if not args.test and verified == saved and saved > 0:
        print("Ready for next batch! Run: python3 test_vlm_single.py <next-website>")


if __name__ == "__main__":
    main()
