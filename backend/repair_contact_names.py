#!/usr/bin/env python3
"""
Repair Contact Names - FIX instead of DELETE
=============================================
Finds concatenated names like "Becky BrandborgOwner/ Partner" and splits them:
- Name: "Becky Brandborg"
- Title: "Owner/ Partner"

Usage:
    python repair_contact_names.py --dry-run   # Show what would be fixed
    python repair_contact_names.py --execute   # Actually fix the data
"""

import os
import re
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Title patterns to detect in concatenated names (order matters - specific first)
TITLE_PATTERNS = [
    # Compound titles
    r'(Owner/?.*Partner)',
    r'(President\s*&?\s*Owner)',
    # Executive titles
    r'(CEO|CFO|CTO|COO|CMO|CPO|CRO|CHRO)',
    r'(Co-?[Ff]ounder.*)',
    r'(Founder.*)',
    r'(President.*)',
    r'(Vice\s*President.*)',
    r'(Director.*)',
    r'(VP.*)',
    r'(General\s*Manager.*)',
    r'(GM)',
    # Operational roles (crews, teams)
    r'(Tear\s*Off\s*(?:Crew|Lead).*)',
    r'((?:Crew|Team)\s*(?:Lead|Leader|Member).*)',
    r'(Office\s*(?:Administrator|Manager|Assistant).*)',
    r'(Project\s*Manager.*)',
    r'(Account(?:s)?\s*Manager.*)',
    r'(Sales\s*(?:Manager|Rep|Representative).*)',
    r'(Service\s*Manager.*)',
    r'(Operations\s*Manager.*)',
    # Generic roles
    r'(Manager.*)',
    r'(Partner)',
    r'(Owner)',
    r'(Foreman.*)',
    r'(Supervisor.*)',
    r'(Technician.*)',
    r'(Installer.*)',
    r'(Estimator.*)',
    r'(Auditor.*)',
    r'(Customer\s*(?:Advocate|Service).*)',
    r'(Administrator.*)',
]


def clean_title(title: str) -> str:
    """
    Clean up a title - strip READ BIO, pipe separators, etc.

    "CO-FOUNDER | READ BIO" -> "CO-FOUNDER"
    "VP of Sales | READ BIO" -> "VP of Sales"
    """
    if not title:
        return title

    # Strip "READ BIO" and similar suffixes
    title = re.sub(r'\s*\|\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)

    # Strip "View Profile", "Learn More" etc.
    title = re.sub(r'\s*\|\s*(?:VIEW|LEARN|READ)\s*(?:PROFILE|MORE|BIO)\s*$', '', title, flags=re.IGNORECASE)

    # Strip trailing pipes and dashes
    title = re.sub(r'\s*[\|\-]\s*$', '', title)

    # Check if title contains another person's name (merged contacts)
    # e.g., "Jason BoyceVice President" -> "Vice President"
    title_name_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(CEO|CFO|VP|Vice|President|Owner|Director|Manager|Founder)', title)
    if title_name_match:
        title = title[title_name_match.end(1):].strip()

    return title.strip()


def split_concatenated_name(full_name: str) -> tuple[str, str]:
    """
    Split "Becky BrandborgOwner/ Partner" into ("Becky Brandborg", "Owner/ Partner")
    Split "CodyTear Off Crew" into ("Cody", "Tear Off Crew")
    Returns (fixed_name, extracted_title) or (original_name, "") if no fix needed
    """
    if not full_name:
        return full_name, ""

    # Try each title pattern
    for pattern in TITLE_PATTERNS:
        # Look for title concatenated without space
        match = re.search(r'([A-Za-z]+)(' + pattern[1:-1] + r'.*)$', full_name)
        if match:
            # Found concatenated pattern
            before_title = full_name[:match.start(2)]
            title_part = match.group(2)

            # Clean up the name (the word before title needs a space)
            if before_title and before_title[-1].islower():
                # Find where the last word starts
                words = before_title.split()
                if words:
                    last_word = words[-1]
                    # Check if last word has mixed case indicating concatenation
                    for i, char in enumerate(last_word):
                        if char.isupper() and i > 0:
                            # Split at the uppercase letter
                            fixed_last_word = last_word[:i] + " " + last_word[i:]
                            words[-1] = fixed_last_word
                            before_title = " ".join(words)
                            break

            # Clean the extracted title
            title_part = clean_title(title_part)
            return before_title.strip(), title_part.strip()

    # Check for lowercase-uppercase pattern in name (e.g., "JohnSmith")
    # But NOT if it's a normal name like "McDonald"
    if re.search(r'[a-z][A-Z]', full_name):
        # Find all positions where lowercase is followed by uppercase
        positions = [m.start() + 1 for m in re.finditer(r'[a-z][A-Z]', full_name)]

        # Only fix if it looks like a title was concatenated
        for pos in positions:
            potential_title = full_name[pos:]
            # Check if what follows looks like a title
            for pattern in TITLE_PATTERNS:
                if re.match(pattern, potential_title, re.IGNORECASE):
                    cleaned_title = clean_title(potential_title)
                    return full_name[:pos].strip(), cleaned_title.strip()

    return full_name, ""


def fetch_all_contacts():
    """Fetch all contacts with pagination."""
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'contact_id, company_id, full_name, first_name, last_name, title, email, source'
        ).range(offset, offset + batch_size - 1).execute()

        all_contacts.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_contacts


def fetch_company_names(company_ids: list) -> dict:
    """Fetch company names for context."""
    if not company_ids:
        return {}

    names = {}
    for i in range(0, len(company_ids), 100):
        batch = company_ids[i:i+100]
        result = supabase.table('dim_companies').select(
            'company_id, company_name'
        ).in_('company_id', batch).execute()
        for c in result.data:
            names[c['company_id']] = c['company_name']

    return names


def main():
    parser = argparse.ArgumentParser(description='Repair concatenated contact names')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed')
    parser.add_argument('--execute', action='store_true', help='Actually fix the data')

    args = parser.parse_args()

    if not any([args.dry_run, args.execute]):
        parser.print_help()
        return

    print("=" * 70)
    print("CONTACT NAME REPAIR - FIX instead of DELETE")
    print("=" * 70)

    # Fetch all contacts
    print("\nFetching contacts...")
    contacts = fetch_all_contacts()
    print(f"Total contacts: {len(contacts)}")

    # Find contacts that need repair
    repairs_needed = []

    for contact in contacts:
        original_name = contact.get('full_name') or ''
        original_title = contact.get('title') or ''

        fixed_name, extracted_title = split_concatenated_name(original_name)

        if fixed_name != original_name and extracted_title:
            # We found something to fix
            repairs_needed.append({
                'contact_id': contact['contact_id'],
                'company_id': contact.get('company_id'),
                'original_name': original_name,
                'original_title': original_title,
                'fixed_name': fixed_name,
                'extracted_title': extracted_title,
                'new_title': extracted_title if not original_title else original_title,
            })

    print(f"\nContacts needing repair: {len(repairs_needed)}")

    if not repairs_needed:
        print("\nNo repairs needed!")
        return

    # Get company names for context
    company_ids = list(set(r['company_id'] for r in repairs_needed if r.get('company_id')))
    company_names = fetch_company_names(company_ids)

    # Show repairs
    print(f"\n{'='*70}")
    print("REPAIRS TO APPLY")
    print(f"{'='*70}")

    for r in repairs_needed[:20]:
        company = company_names.get(r['company_id'], 'Unknown')
        print(f"\n  Company: {company[:40]}")
        print(f"  BEFORE:  '{r['original_name']}' | title: '{r['original_title']}'")
        print(f"  AFTER:   '{r['fixed_name']}' | title: '{r['extracted_title']}'")

    if len(repairs_needed) > 20:
        print(f"\n  ... and {len(repairs_needed) - 20} more")

    # Save audit log
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    audit_file = data_dir / f'REPAIR_LOG_{timestamp}.csv'
    with open(audit_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'company', 'original_name', 'fixed_name', 'extracted_title', 'original_title', 'contact_id'
        ])
        writer.writeheader()
        for r in repairs_needed:
            writer.writerow({
                'company': company_names.get(r['company_id'], ''),
                'original_name': r['original_name'],
                'fixed_name': r['fixed_name'],
                'extracted_title': r['extracted_title'],
                'original_title': r['original_title'],
                'contact_id': r['contact_id'],
            })
    print(f"\nAudit log saved to: {audit_file.name}")

    if args.dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN - No changes made")
        print(f"{'='*70}")
        return

    if args.execute:
        print(f"\n{'='*70}")
        print("EXECUTING REPAIRS")
        print(f"{'='*70}")

        confirm = input(f"\nType 'FIX' to confirm repair of {len(repairs_needed)} contacts: ")
        if confirm != 'FIX':
            print("Aborted.")
            return

        # Apply repairs
        fixed = 0
        for r in repairs_needed:
            try:
                update_data = {
                    'full_name': r['fixed_name'],
                }
                # Only update title if we extracted one and original was empty
                if r['extracted_title'] and not r['original_title']:
                    update_data['title'] = r['extracted_title']

                # Also update first/last name
                name_parts = r['fixed_name'].split()
                if len(name_parts) >= 2:
                    update_data['first_name'] = name_parts[0]
                    update_data['last_name'] = ' '.join(name_parts[1:])

                supabase.table('dim_contacts').update(update_data).eq(
                    'contact_id', r['contact_id']
                ).execute()
                fixed += 1

            except Exception as e:
                logger.error(f"Error fixing {r['original_name']}: {e}")

        print(f"\n{'='*70}")
        print(f"REPAIR COMPLETE")
        print(f"{'='*70}")
        print(f"Fixed: {fixed} contacts")


if __name__ == "__main__":
    main()
