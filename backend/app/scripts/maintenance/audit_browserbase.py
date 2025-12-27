#!/usr/bin/env python3
"""
Browserbase Enrichment Audit
============================
Audits Browserbase-sourced contacts to identify quality issues.

Usage:
    python audit_browserbase.py              # Show audit summary
    python audit_browserbase.py --verbose    # Show all contacts with issues
    python audit_browserbase.py --export     # Export to CSV for review
"""

import os
import re
import csv
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Import shared patterns for validation
import sys
sys.path.insert(0, str(Path(__file__).parent))
from app.services.scraper_patterns import (
    is_atl_title,
    is_garbage_name,
    clean_title,
    ATL_TITLE_KEYWORDS,
    GARBAGE_NAMES,
)


def fetch_browserbase_contacts():
    """Fetch all contacts sourced from Browserbase."""
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'contact_id, company_id, full_name, first_name, last_name, title, email, source, confidence, is_atl, created_at'
        ).eq('source', 'browserbase_scraper').range(offset, offset + batch_size - 1).execute()

        all_contacts.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_contacts


def fetch_company_names(company_ids):
    """Fetch company names for context."""
    if not company_ids:
        return {}

    names = {}
    for i in range(0, len(company_ids), 100):
        batch = company_ids[i:i+100]
        result = supabase.table('dim_companies').select(
            'company_id, company_name, website, domain, icp_score'
        ).in_('company_id', batch).execute()
        for c in result.data:
            names[c['company_id']] = c

    return names


def audit_contact(contact):
    """
    Audit a contact for quality issues.
    Returns dict with issues found.
    """
    issues = []

    name = contact.get('full_name', '') or ''
    title = contact.get('title', '') or ''
    email = contact.get('email')

    # Check for garbage name
    if is_garbage_name(name):
        issues.append('GARBAGE_NAME')

    # Check name too short
    if len(name.strip()) < 4:
        issues.append('NAME_TOO_SHORT')

    # Check name too long (probably scraped paragraph)
    if len(name) > 50:
        issues.append('NAME_TOO_LONG')

    # Check for merged name+title
    if re.search(r'[a-z][A-Z]', name):
        issues.append('MERGED_NAME_TITLE')

    # Check title has "READ BIO" or similar
    if 'read bio' in title.lower() or 'view profile' in title.lower():
        issues.append('UNCLEANED_TITLE')

    # Check if marked ATL but title not ATL
    if contact.get('is_atl') and not is_atl_title(title):
        issues.append('INCORRECT_ATL_FLAG')

    # Check if title looks like garbage
    title_lower = title.lower()
    if any(garbage in title_lower for garbage in ['learn more', 'click here', 'schedule', 'solar panel']):
        issues.append('GARBAGE_TITLE')

    # Check for missing email (not critical, but trackable)
    if not email:
        issues.append('NO_EMAIL')

    # Check title is empty
    if not title.strip():
        issues.append('EMPTY_TITLE')

    return issues


def main():
    parser = argparse.ArgumentParser(description='Audit Browserbase contacts')
    parser.add_argument('--verbose', action='store_true', help='Show all contacts with issues')
    parser.add_argument('--export', action='store_true', help='Export to CSV')

    args = parser.parse_args()

    print("=" * 70)
    print("BROWSERBASE ENRICHMENT AUDIT")
    print("=" * 70)

    # Fetch contacts
    print("\nFetching Browserbase-sourced contacts...")
    contacts = fetch_browserbase_contacts()
    print(f"Total Browserbase contacts: {len(contacts)}")

    if not contacts:
        print("\nNo Browserbase contacts found yet.")
        return

    # Fetch company info
    company_ids = list(set(c.get('company_id') for c in contacts if c.get('company_id')))
    companies = fetch_company_names(company_ids)

    # Audit each contact
    issues_by_type = Counter()
    contacts_with_issues = []
    clean_contacts = []

    for contact in contacts:
        issues = audit_contact(contact)

        if issues:
            for issue in issues:
                issues_by_type[issue] += 1
            contacts_with_issues.append({
                'contact': contact,
                'company': companies.get(contact.get('company_id'), {}),
                'issues': issues,
            })
        else:
            clean_contacts.append({
                'contact': contact,
                'company': companies.get(contact.get('company_id'), {}),
            })

    # Summary
    print(f"\n{'=' * 70}")
    print("AUDIT SUMMARY")
    print(f"{'=' * 70}")
    print(f"\nTotal contacts:     {len(contacts)}")
    print(f"Clean contacts:     {len(clean_contacts)} ({len(clean_contacts)/len(contacts)*100:.1f}%)")
    print(f"Contacts w/ issues: {len(contacts_with_issues)} ({len(contacts_with_issues)/len(contacts)*100:.1f}%)")

    # Issue breakdown
    if issues_by_type:
        print(f"\n{'=' * 70}")
        print("ISSUE BREAKDOWN")
        print(f"{'=' * 70}")
        for issue, count in issues_by_type.most_common():
            print(f"  {issue:<25} {count:>5} ({count/len(contacts)*100:.1f}%)")

    # Title distribution
    title_counts = Counter()
    for contact in contacts:
        title = contact.get('title', 'NO_TITLE') or 'NO_TITLE'
        title_counts[title] += 1

    print(f"\n{'=' * 70}")
    print("TOP TITLES (Browserbase)")
    print(f"{'=' * 70}")
    for title, count in title_counts.most_common(15):
        is_atl = "ATL" if is_atl_title(title) else "BTL"
        print(f"  [{is_atl}] {title[:40]:<40} {count:>3}")

    # Show contacts with issues
    if args.verbose and contacts_with_issues:
        print(f"\n{'=' * 70}")
        print("CONTACTS WITH ISSUES")
        print(f"{'=' * 70}")

        for item in contacts_with_issues[:30]:
            contact = item['contact']
            company = item['company']
            issues = item['issues']

            print(f"\n  Company: {company.get('company_name', 'Unknown')[:50]}")
            print(f"  Name:    {contact.get('full_name', '')}")
            print(f"  Title:   {contact.get('title', '')}")
            print(f"  Issues:  {', '.join(issues)}")

        if len(contacts_with_issues) > 30:
            print(f"\n  ... and {len(contacts_with_issues) - 30} more")

    # Show clean contacts
    print(f"\n{'=' * 70}")
    print("SAMPLE CLEAN CONTACTS")
    print(f"{'=' * 70}")

    for item in clean_contacts[:10]:
        contact = item['contact']
        company = item['company']
        print(f"\n  {company.get('company_name', 'Unknown')[:40]}")
        print(f"  → {contact.get('full_name')} ({contact.get('title')})")

    # Export to CSV
    if args.export:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_dir = Path(__file__).parent / 'data'
        data_dir.mkdir(exist_ok=True)

        export_file = data_dir / f'BROWSERBASE_AUDIT_{timestamp}.csv'
        with open(export_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'company_name', 'icp_score', 'full_name', 'title', 'email',
                'is_atl', 'confidence', 'issues', 'contact_id'
            ])
            writer.writeheader()

            for item in contacts_with_issues:
                contact = item['contact']
                company = item['company']
                writer.writerow({
                    'company_name': company.get('company_name', ''),
                    'icp_score': company.get('icp_score', ''),
                    'full_name': contact.get('full_name', ''),
                    'title': contact.get('title', ''),
                    'email': contact.get('email', ''),
                    'is_atl': contact.get('is_atl', ''),
                    'confidence': contact.get('confidence', ''),
                    'issues': ', '.join(item['issues']),
                    'contact_id': contact.get('contact_id', ''),
                })

        print(f"\nExported issues to: {export_file.name}")

    # Recommendations
    print(f"\n{'=' * 70}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 70}")

    if issues_by_type.get('UNCLEANED_TITLE', 0) > 0:
        print("  - Run repair_titles.py to clean 'READ BIO' suffixes")

    if issues_by_type.get('GARBAGE_NAME', 0) > 0:
        print("  - Review garbage names - may need pattern updates in scraper_patterns.py")

    if issues_by_type.get('MERGED_NAME_TITLE', 0) > 0:
        print("  - Run repair_contact_names.py to fix merged names")

    if issues_by_type.get('INCORRECT_ATL_FLAG', 0) > 0:
        print("  - Review ATL classification - titles may need pattern updates")

    if issues_by_type.get('NO_EMAIL', 0) > len(contacts) * 0.5:
        print("  - High rate of missing emails - normal for web scraping")

    if not contacts_with_issues:
        print("  All contacts pass quality checks!")


if __name__ == "__main__":
    main()
