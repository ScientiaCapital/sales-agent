#!/usr/bin/env python3
"""
Enrichment Audit Trail
======================
Creates audit CSVs after FREE enrichment for team review.

Outputs:
1. AUDIT_NEW_CONTACTS_*.csv - All contacts found by BeautifulSoup
2. AUDIT_NO_ATL_FOUND_*.csv - Companies needing Browserbase ($200/mo)
3. AUDIT_SUSPICIOUS_*.csv - Contacts that look like garbage

Usage:
    python audit_enrichment.py
"""

import os
import csv
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Suspicious patterns for garbage detection
GARBAGE_PATTERNS = [
    r'^(schedule|call|contact|click|learn|view|see|read|get|our|the|your|my|home|about|services?)$',
    r'^(heating|cooling|plumbing|electrical|hvac|solar|roofing|air|water)$',
    r'^(request|quote|estimate|free|now|today|more|here|us|me)$',
    r'^\d+$',  # Just numbers
    r'^[a-z]$',  # Single letters
    r'(privacy|policy|terms|copyright|reserved|rights)',
    r'(facebook|twitter|linkedin|instagram|youtube|tiktok)',
    r'^(mr|mrs|ms|dr)\.?$',
    r'(admin|webmaster|info|contact|support|sales)@',
]

GARBAGE_TITLES = [
    'schedule now', 'call now', 'get quote', 'learn more',
    'click here', 'read more', 'view all', 'see more',
    'heating', 'cooling', 'plumbing', 'electrical',
    'home', 'about', 'services', 'contact', 'careers',
]


def is_suspicious(name: str, title: str) -> tuple[bool, str]:
    """Check if contact looks like garbage."""
    name_lower = name.lower().strip()
    title_lower = (title or '').lower().strip()

    reasons = []

    # Check name patterns
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, name_lower):
            reasons.append(f"name matches '{pattern}'")
            break

    # Check title patterns
    if title_lower in GARBAGE_TITLES:
        reasons.append(f"title is navigation text: '{title_lower}'")

    # Name too short
    if len(name_lower) < 3:
        reasons.append("name too short")

    # Name too long (probably scraped paragraph)
    if len(name) > 50:
        reasons.append("name too long")

    # No spaces (probably not a real name)
    if ' ' not in name.strip() and len(name) > 15:
        reasons.append("no spaces in long name")

    # Starts with lowercase (probably not a name)
    if name and name[0].islower():
        reasons.append("name starts lowercase")

    return bool(reasons), '; '.join(reasons) if reasons else ''


def fetch_new_contacts():
    """Fetch contacts added by BeautifulSoup scraper."""
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'contact_id, company_id, full_name, first_name, last_name, title, email, phone, is_atl, source, confidence, created_at'
        ).eq('source', 'beautifulsoup_scraper').range(offset, offset + batch_size - 1).execute()

        all_contacts.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    return all_contacts


def fetch_companies_no_atl():
    """Fetch companies enriched but with no ATL contacts."""
    # Get enriched companies
    enriched = supabase.table('dim_companies').select(
        'company_id, company_name, domain, website, icp_score, last_enriched_at'
    ).not_.is_('last_enriched_at', 'null').execute()

    # Get companies with contacts
    contacts = supabase.table('dim_contacts').select('company_id').execute()
    companies_with_contacts = set(c['company_id'] for c in contacts.data if c.get('company_id'))

    # Filter to enriched but no contacts
    no_atl = [c for c in enriched.data if c['company_id'] not in companies_with_contacts]

    return no_atl


def fetch_company_names(company_ids: list) -> dict:
    """Fetch company names for a list of IDs."""
    if not company_ids:
        return {}

    # Batch fetch
    names = {}
    for i in range(0, len(company_ids), 100):
        batch = company_ids[i:i+100]
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain'
        ).in_('company_id', batch).execute()
        for c in result.data:
            names[c['company_id']] = {'name': c['company_name'], 'domain': c.get('domain', '')}

    return names


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("ENRICHMENT AUDIT")
    print("=" * 60)

    # 1. Fetch all new contacts
    print("\nFetching contacts from BeautifulSoup scraper...")
    contacts = fetch_new_contacts()
    print(f"Found {len(contacts)} contacts")

    # Get company names
    company_ids = list(set(c['company_id'] for c in contacts if c.get('company_id')))
    company_names = fetch_company_names(company_ids)

    # 2. Identify suspicious contacts
    suspicious = []
    clean = []

    for contact in contacts:
        name = contact.get('full_name', '')
        title = contact.get('title', '')
        is_sus, reason = is_suspicious(name, title)

        contact_row = {
            'company': company_names.get(contact['company_id'], {}).get('name', ''),
            'domain': company_names.get(contact['company_id'], {}).get('domain', ''),
            'name': name,
            'title': title,
            'email': contact.get('email', ''),
            'phone': contact.get('phone', ''),
            'confidence': contact.get('confidence', ''),
            'created_at': contact.get('created_at', ''),
            'contact_id': contact.get('contact_id', ''),
        }

        if is_sus:
            contact_row['reason'] = reason
            suspicious.append(contact_row)
        else:
            clean.append(contact_row)

    # 3. Export new contacts
    contacts_file = data_dir / f'AUDIT_NEW_CONTACTS_{timestamp}.csv'
    with open(contacts_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'company', 'domain', 'name', 'title', 'email', 'phone', 'confidence', 'created_at', 'contact_id'
        ])
        writer.writeheader()
        writer.writerows(clean)
    print(f"\n[1] Clean contacts: {len(clean)}")
    print(f"    Saved to: {contacts_file.name}")

    # 4. Export suspicious contacts
    if suspicious:
        suspicious_file = data_dir / f'AUDIT_SUSPICIOUS_{timestamp}.csv'
        with open(suspicious_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'company', 'domain', 'name', 'title', 'reason', 'email', 'phone', 'confidence', 'contact_id'
            ])
            writer.writeheader()
            writer.writerows(suspicious)
        print(f"\n[2] Suspicious contacts: {len(suspicious)}")
        print(f"    Saved to: {suspicious_file.name}")
        print(f"    ACTION: Review and delete garbage entries")
    else:
        print(f"\n[2] Suspicious contacts: 0 (all clean!)")

    # 5. Companies with no ATL
    print("\nFetching companies with no ATL contacts...")
    no_atl = fetch_companies_no_atl()

    no_atl_file = data_dir / f'AUDIT_NO_ATL_FOUND_{timestamp}.csv'
    with open(no_atl_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'company_name', 'domain', 'website', 'icp_score', 'last_enriched_at', 'company_id', 'action'
        ])
        writer.writeheader()
        for c in sorted(no_atl, key=lambda x: -(x.get('icp_score') or 0)):
            writer.writerow({
                'company_name': c['company_name'],
                'domain': c.get('domain', ''),
                'website': c.get('website', ''),
                'icp_score': c.get('icp_score', ''),
                'last_enriched_at': c.get('last_enriched_at', ''),
                'company_id': c['company_id'],
                'action': 'BROWSERBASE' if (c.get('icp_score') or 0) >= 50 else '',
            })

    print(f"\n[3] Companies with no ATL: {len(no_atl)}")
    print(f"    Saved to: {no_atl_file.name}")
    high_icp_no_atl = sum(1 for c in no_atl if (c.get('icp_score') or 0) >= 50)
    print(f"    High ICP (>=50) needing Browserbase: {high_icp_no_atl}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total contacts from BeautifulSoup: {len(contacts)}")
    print(f"  Clean:      {len(clean)}")
    print(f"  Suspicious: {len(suspicious)}")
    print(f"Companies enriched but no ATL: {len(no_atl)}")
    print(f"  Recommend Browserbase for: {high_icp_no_atl} (ICP >= 50)")
    print("\nAudit files saved to: backend/data/")


if __name__ == "__main__":
    main()
