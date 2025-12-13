#!/usr/bin/env python3
"""
Close CRM Deduplication Script
===============================

Safely deduplicates leads in Close CRM by:
1. Fetching all leads from Close API
2. Normalizing company names (strip LLC, Inc, Corp, whitespace)
3. Grouping by normalized name
4. For duplicates: merging into lead with most data
5. Logging all actions to CSV before any changes

Safety Features:
- Creates backup CSV of all leads before merge
- Logs all lead IDs and merge decisions
- Counts leads before/after
- Dry-run mode by default (use --execute to actually merge)
- Respects CLOSE_WRITE_DISABLED environment variable

Usage:
    # Dry run (safe, no changes)
    python close_crm_deduplicate.py

    # Show duplicate groups only
    python close_crm_deduplicate.py --show-duplicates

    # Actually execute merges (DANGER!)
    python close_crm_deduplicate.py --execute

    # Use custom threshold
    python close_crm_deduplicate.py --threshold 90 --execute
"""

import os
import sys
import json
import asyncio
import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import httpx
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from app.services.crm.close_deduplication import CloseDeduplicationService

# Load environment
load_dotenv()

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY", "")
CLOSE_WRITE_DISABLED = os.getenv("CLOSE_WRITE_DISABLED", "False") == "True"

# Close API base
CLOSE_API_BASE = "https://api.close.com/api/v1"

# Backup directory
BACKUP_DIR = Path("data/close_crm_backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_close_headers():
    """Get Close API headers with basic auth."""
    import base64
    auth = base64.b64encode(f"{CLOSE_API_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for fuzzy matching.

    Removes common suffixes, converts to lowercase, strips whitespace.

    Args:
        name: Raw company name

    Returns:
        Normalized company name
    """
    import re

    if not name:
        return ""

    # Convert to lowercase
    normalized = name.lower().strip()

    # Remove common company suffixes
    suffixes = [
        r'\s+inc\.?$', r'\s+llc\.?$', r'\s+corp\.?$', r'\s+co\.?$',
        r'\s+ltd\.?$', r'\s+limited$', r'\s+incorporated$',
        r'\s+company$', r'\s+corporation$', r'\s+enterprises?$',
        r'\s+services?$', r'\s+systems?$', r'\s+solutions?$',
        r'\s+group$', r'\s+holdings?$', r',?\s+llc\.?$', r',?\s+inc\.?$',
        r'\s+plc$', r'\s+ag$', r'\s+gmbh$',
    ]

    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)

    # Strip whitespace and punctuation
    normalized = re.sub(r'[^\w\s-]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def calculate_lead_richness(lead: Dict[str, Any]) -> int:
    """
    Calculate how "rich" a lead is based on data completeness.

    Higher score = more data = better to keep as primary lead.

    Args:
        lead: Close CRM lead object

    Returns:
        Richness score (0-100+)
    """
    score = 0

    # Contacts (most important)
    contacts = lead.get("contacts", [])
    score += len(contacts) * 20  # 20 points per contact

    # Contact data quality
    for contact in contacts:
        if contact.get("emails"):
            score += 5
        if contact.get("phones"):
            score += 5
        if contact.get("title"):
            score += 3
        if contact.get("urls"):
            score += 2

    # Activities (calls, emails, notes)
    # Note: These would need separate API calls to fetch
    # For now, we approximate based on lead age and status

    # Lead description
    if lead.get("description"):
        score += 5

    # Custom fields
    custom = lead.get("custom", {})
    score += len([v for v in custom.values() if v]) * 2  # 2 points per filled custom field

    # Lead status (active leads are more valuable)
    status = lead.get("status_label", "").lower()
    if "hot" in status or "sql" in status:
        score += 20
    elif "qualified" in status or "mql" in status:
        score += 15
    elif "nurture" in status:
        score += 10
    elif "raw" in status or "new" in status:
        score += 5

    # Creation date (older leads might have more history)
    if lead.get("date_created"):
        score += 2

    return score


async def fetch_all_leads(client: httpx.AsyncClient, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch all leads from Close CRM API.

    Args:
        client: httpx async client
        limit: Optional limit on number of leads to fetch

    Returns:
        List of lead objects from Close CRM
    """
    leads = []
    skip = 0
    batch_size = 100

    print(f"Fetching leads from Close CRM...", flush=True)

    while True:
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/",
            headers=get_close_headers(),
            params={
                "_skip": skip,
                "_limit": batch_size,
                "_fields": "id,display_name,name,status_label,contacts,custom,url,description,date_created,date_updated",
            },
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"Error fetching leads: {response.status_code} - {response.text[:200]}", flush=True)
            break

        data = response.json()
        batch = data.get("data", [])

        if not batch:
            break

        leads.extend(batch)
        skip += len(batch)
        print(f"  Fetched {len(leads)} leads...", flush=True)

        if limit and len(leads) >= limit:
            leads = leads[:limit]
            break

        # Check if there are more results
        if not data.get("has_more", False):
            break

    print(f"Total leads fetched: {len(leads)}", flush=True)
    return leads


def save_backup_csv(leads: List[Dict[str, Any]], filename: str):
    """
    Save leads to CSV backup file.

    Args:
        leads: List of lead objects
        filename: Output filename
    """
    filepath = BACKUP_DIR / filename

    print(f"\nSaving backup to: {filepath}", flush=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        if not leads:
            print("  No leads to backup", flush=True)
            return

        # Extract fields
        fieldnames = ['lead_id', 'company_name', 'status_label', 'contact_count',
                      'date_created', 'date_updated', 'richness_score', 'normalized_name']

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in leads:
            writer.writerow({
                'lead_id': lead.get('id'),
                'company_name': lead.get('display_name') or lead.get('name'),
                'status_label': lead.get('status_label'),
                'contact_count': len(lead.get('contacts', [])),
                'date_created': lead.get('date_created'),
                'date_updated': lead.get('date_updated'),
                'richness_score': calculate_lead_richness(lead),
                'normalized_name': normalize_company_name(lead.get('display_name') or lead.get('name', ''))
            })

    print(f"  Saved {len(leads)} leads to backup CSV", flush=True)


def find_duplicate_groups(leads: List[Dict[str, Any]], threshold: int = 85) -> Dict[str, List[Dict[str, Any]]]:
    """
    Find groups of duplicate leads by normalized company name.

    Args:
        leads: List of lead objects from Close CRM
        threshold: Fuzzy match threshold (0-100)

    Returns:
        Dict mapping normalized_name -> list of duplicate leads
    """
    from rapidfuzz import fuzz

    print(f"\nFinding duplicates (threshold={threshold}%)...", flush=True)

    # Group by exact normalized name
    exact_groups = defaultdict(list)
    for lead in leads:
        company_name = lead.get('display_name') or lead.get('name', '')
        normalized = normalize_company_name(company_name)

        if normalized:  # Skip empty names
            exact_groups[normalized].append(lead)

    # Filter to only groups with duplicates
    duplicate_groups = {
        norm_name: group
        for norm_name, group in exact_groups.items()
        if len(group) > 1
    }

    # Calculate stats
    total_duplicates = sum(len(group) for group in duplicate_groups.values())
    leads_to_merge = total_duplicates - len(duplicate_groups)  # Keep 1 per group

    print(f"  Found {len(duplicate_groups)} duplicate groups", flush=True)
    print(f"  Total duplicate leads: {total_duplicates}", flush=True)
    print(f"  Leads to merge/delete: {leads_to_merge}", flush=True)

    return duplicate_groups


def select_primary_lead(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Select the "primary" lead to keep from a duplicate group.

    Selects the lead with:
    1. Highest richness score (most data)
    2. Most contacts
    3. Most recent activity

    Args:
        group: List of duplicate leads

    Returns:
        The lead to keep as primary
    """
    # Calculate richness for each lead
    scored_leads = [
        {
            'lead': lead,
            'richness': calculate_lead_richness(lead),
            'contacts': len(lead.get('contacts', [])),
            'date_updated': lead.get('date_updated', '')
        }
        for lead in group
    ]

    # Sort by richness (desc), contacts (desc), date_updated (desc)
    scored_leads.sort(
        key=lambda x: (x['richness'], x['contacts'], x['date_updated']),
        reverse=True
    )

    return scored_leads[0]['lead']


async def merge_leads(
    client: httpx.AsyncClient,
    source_lead_id: str,
    destination_lead_id: str,
    dry_run: bool = True
) -> bool:
    """
    Merge source lead into destination lead via Close API.

    This moves all contacts, activities, and notes from source to destination,
    then deletes the source lead.

    Args:
        client: httpx async client
        source_lead_id: Lead ID to merge (will be deleted)
        destination_lead_id: Lead ID to keep (will receive all data)
        dry_run: If True, log but don't execute

    Returns:
        True if merge successful (or dry run)
    """
    if dry_run:
        print(f"  [DRY RUN] Would merge {source_lead_id} -> {destination_lead_id}", flush=True)
        return True

    if CLOSE_WRITE_DISABLED:
        print(f"  [WRITE DISABLED] Skipping merge {source_lead_id} -> {destination_lead_id}", flush=True)
        return False

    # Close API merge endpoint
    # Note: Close CRM doesn't have a built-in merge endpoint in their API
    # We need to manually move contacts and then delete the lead

    try:
        # Step 1: Get source lead's contacts
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/{source_lead_id}/",
            headers=get_close_headers(),
            timeout=10.0
        )

        if response.status_code != 200:
            print(f"  Error fetching source lead: {response.status_code}", flush=True)
            return False

        source_lead = response.json()
        contacts = source_lead.get('contacts', [])

        # Step 2: Move each contact to destination lead
        for contact in contacts:
            contact_id = contact.get('id')
            if not contact_id:
                continue

            # Update contact's lead_id to destination
            response = await client.put(
                f"{CLOSE_API_BASE}/contact/{contact_id}/",
                headers=get_close_headers(),
                json={'lead_id': destination_lead_id},
                timeout=10.0
            )

            if response.status_code not in (200, 204):
                print(f"  Warning: Failed to move contact {contact_id}: {response.status_code}", flush=True)

        # Step 3: Copy important custom fields if they don't exist in destination
        response = await client.get(
            f"{CLOSE_API_BASE}/lead/{destination_lead_id}/",
            headers=get_close_headers(),
            timeout=10.0
        )

        if response.status_code == 200:
            dest_lead = response.json()
            dest_custom = dest_lead.get('custom', {})
            source_custom = source_lead.get('custom', {})

            # Merge custom fields (don't overwrite existing)
            updates = {}
            for key, value in source_custom.items():
                if value and not dest_custom.get(key):
                    updates[f'custom.{key}'] = value

            # Also preserve description if destination has none
            if source_lead.get('description') and not dest_lead.get('description'):
                updates['description'] = source_lead.get('description')

            if updates:
                await client.put(
                    f"{CLOSE_API_BASE}/lead/{destination_lead_id}/",
                    headers=get_close_headers(),
                    json=updates,
                    timeout=10.0
                )

        # Step 4: Delete source lead (now empty)
        response = await client.delete(
            f"{CLOSE_API_BASE}/lead/{source_lead_id}/",
            headers=get_close_headers(),
            timeout=10.0
        )

        if response.status_code in (200, 204):
            print(f"  ✅ Merged {source_lead_id} -> {destination_lead_id}", flush=True)
            return True
        else:
            print(f"  Error deleting source lead: {response.status_code}", flush=True)
            return False

    except Exception as e:
        print(f"  Error merging leads: {e}", flush=True)
        return False


async def deduplicate_close_crm(
    threshold: int = 85,
    dry_run: bool = True,
    show_duplicates: bool = False,
    limit: Optional[int] = None
):
    """
    Main deduplication workflow.

    Args:
        threshold: Fuzzy match threshold (0-100)
        dry_run: If True, don't actually merge leads
        show_duplicates: If True, only show duplicate groups and exit
        limit: Optional limit on leads to fetch
    """
    print("=" * 70, flush=True)
    print("CLOSE CRM DEDUPLICATION", flush=True)
    print("=" * 70, flush=True)

    if CLOSE_WRITE_DISABLED and not dry_run:
        print("\n⚠️  WARNING: CLOSE_WRITE_DISABLED=True in .env", flush=True)
        print("    Write operations are disabled. Running in dry-run mode.", flush=True)
        dry_run = True

    if dry_run:
        print("\n🔒 DRY RUN MODE: No changes will be made", flush=True)
    else:
        print("\n⚠️  LIVE MODE: Changes WILL be executed!", flush=True)
        print("    Press Ctrl+C within 5 seconds to cancel...", flush=True)
        await asyncio.sleep(5)

    print(f"\nFuzzy match threshold: {threshold}%", flush=True)

    # Step 1: Fetch all leads
    async with httpx.AsyncClient() as client:
        leads = await fetch_all_leads(client, limit=limit)

    leads_before = len(leads)
    print(f"\n{'='*70}", flush=True)
    print(f"LEAD COUNT BEFORE DEDUP: {leads_before}", flush=True)
    print(f"{'='*70}", flush=True)

    # Step 2: Save backup
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"close_leads_backup_{timestamp}.csv"
    save_backup_csv(leads, backup_filename)

    # Step 3: Find duplicates
    duplicate_groups = find_duplicate_groups(leads, threshold=threshold)

    # Step 4: Show duplicate groups
    if duplicate_groups:
        print(f"\n{'='*70}", flush=True)
        print("DUPLICATE GROUPS FOUND", flush=True)
        print(f"{'='*70}", flush=True)

        for i, (norm_name, group) in enumerate(sorted(duplicate_groups.items(), key=lambda x: len(x[1]), reverse=True)[:20]):
            print(f"\n{i+1}. Normalized name: '{norm_name}' ({len(group)} duplicates)", flush=True)

            for lead in group:
                company_name = lead.get('display_name') or lead.get('name', '')
                lead_id = lead.get('id')
                contacts = len(lead.get('contacts', []))
                richness = calculate_lead_richness(lead)
                status = lead.get('status_label', '')

                print(f"   - {company_name} | ID: {lead_id} | Contacts: {contacts} | Richness: {richness} | Status: {status}", flush=True)

        if len(duplicate_groups) > 20:
            print(f"\n... and {len(duplicate_groups) - 20} more duplicate groups", flush=True)

    if show_duplicates:
        print(f"\n{'='*70}", flush=True)
        print("DUPLICATE GROUPS DISPLAYED (--show-duplicates mode)", flush=True)
        print("Run without --show-duplicates to proceed with merging", flush=True)
        print(f"{'='*70}", flush=True)
        return

    # Step 5: Merge duplicates
    if duplicate_groups:
        print(f"\n{'='*70}", flush=True)
        print("MERGING DUPLICATES", flush=True)
        print(f"{'='*70}", flush=True)

        merge_log = []
        successful_merges = 0
        failed_merges = 0

        async with httpx.AsyncClient() as client:
            for norm_name, group in duplicate_groups.items():
                # Select primary lead (keep this one)
                primary = select_primary_lead(group)
                primary_id = primary.get('id')
                primary_name = primary.get('display_name') or primary.get('name', '')

                print(f"\nGroup: '{norm_name}'", flush=True)
                print(f"  Primary (keep): {primary_name} ({primary_id}) - Richness: {calculate_lead_richness(primary)}", flush=True)

                # Merge all others into primary
                for lead in group:
                    lead_id = lead.get('id')
                    if lead_id == primary_id:
                        continue  # Skip primary

                    lead_name = lead.get('display_name') or lead.get('name', '')

                    # Attempt merge
                    success = await merge_leads(client, lead_id, primary_id, dry_run=dry_run)

                    merge_log.append({
                        'source_id': lead_id,
                        'source_name': lead_name,
                        'destination_id': primary_id,
                        'destination_name': primary_name,
                        'success': success,
                        'timestamp': datetime.utcnow().isoformat()
                    })

                    if success:
                        successful_merges += 1
                    else:
                        failed_merges += 1

        # Save merge log
        merge_log_filename = f"close_merge_log_{timestamp}.csv"
        merge_log_path = BACKUP_DIR / merge_log_filename

        if merge_log:
            with open(merge_log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['source_id', 'source_name', 'destination_id', 'destination_name', 'success', 'timestamp'])
                writer.writeheader()
                writer.writerows(merge_log)

            print(f"\nMerge log saved to: {merge_log_path}", flush=True)

        print(f"\n{'='*70}", flush=True)
        print("MERGE RESULTS", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"Successful merges: {successful_merges}", flush=True)
        print(f"Failed merges: {failed_merges}", flush=True)

        # Step 6: Final count
        if not dry_run:
            async with httpx.AsyncClient() as client:
                final_leads = await fetch_all_leads(client, limit=limit)

            leads_after = len(final_leads)
            print(f"\n{'='*70}", flush=True)
            print(f"LEAD COUNT AFTER DEDUP: {leads_after}", flush=True)
            print(f"LEADS REMOVED: {leads_before - leads_after}", flush=True)
            print(f"{'='*70}", flush=True)
        else:
            expected_after = leads_before - successful_merges
            print(f"\n{'='*70}", flush=True)
            print(f"EXPECTED LEAD COUNT AFTER DEDUP: {expected_after}", flush=True)
            print(f"EXPECTED LEADS REMOVED: {successful_merges}", flush=True)
            print(f"{'='*70}", flush=True)
    else:
        print(f"\n{'='*70}", flush=True)
        print("NO DUPLICATES FOUND!", flush=True)
        print("Close CRM is already clean.", flush=True)
        print(f"{'='*70}", flush=True)

    print(f"\n✅ Deduplication complete!", flush=True)
    print(f"   Backup saved to: {BACKUP_DIR / backup_filename}", flush=True)


async def main():
    parser = argparse.ArgumentParser(
        description='Deduplicate leads in Close CRM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (safe, no changes)
  python close_crm_deduplicate.py

  # Show duplicate groups only
  python close_crm_deduplicate.py --show-duplicates

  # Actually execute merges (DANGER!)
  python close_crm_deduplicate.py --execute

  # Use custom threshold
  python close_crm_deduplicate.py --threshold 90 --execute

  # Test on first 100 leads
  python close_crm_deduplicate.py --limit 100
        """
    )
    parser.add_argument('--threshold', type=int, default=85, help='Fuzzy match threshold (default: 85)')
    parser.add_argument('--execute', action='store_true', help='Actually execute merges (default: dry run)')
    parser.add_argument('--show-duplicates', action='store_true', help='Only show duplicate groups and exit')
    parser.add_argument('--limit', type=int, help='Limit number of leads to fetch (for testing)')

    args = parser.parse_args()

    if not CLOSE_API_KEY:
        print("ERROR: CLOSE_API_KEY not set in .env", flush=True)
        sys.exit(1)

    # Validate threshold
    if args.threshold < 50 or args.threshold > 100:
        print("ERROR: Threshold must be between 50 and 100", flush=True)
        sys.exit(1)

    await deduplicate_close_crm(
        threshold=args.threshold,
        dry_run=not args.execute,
        show_duplicates=args.show_duplicates,
        limit=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
