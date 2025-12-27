#!/usr/bin/env python3
"""
Export Enriched ATL Contacts to Close CRM
==========================================
Exports ATL contacts discovered by BeautifulSoup enrichment.

Features:
- Filters garbage/invalid contact names
- Excludes companies already in Close CRM
- Validates contact titles are real ATL titles
- Exports in Close CRM import format

Author: Claude + Tim
Date: Dec 13, 2025
"""
import os
import re
import csv
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

print("=" * 70)
print("EXPORT ENRICHED ATL CONTACTS TO CLOSE CRM")
print("Source: BeautifulSoup Website Enrichment")
print("=" * 70)


def is_valid_contact_name(name: str) -> bool:
    """Check if a name looks like a real person's name."""
    if not name:
        return False

    # Normalize for checking (handle ALL CAPS names)
    name_normalized = name.strip()

    # Must be 2-4 words
    words = name_normalized.split()
    if len(words) < 2 or len(words) > 4:
        return False

    # Must be reasonable length (5-35 chars)
    if len(name_normalized) < 5 or len(name_normalized) > 35:
        return False

    # Each word should be 2-15 chars
    for word in words:
        if len(word) < 2 or len(word) > 15:
            return False

    # Common garbage patterns
    garbage_patterns = [
        r'^\d',           # Starts with number
        r'@',             # Email
        r'www\.',         # URL
        r'\.com',         # Domain
        r'LLC|Inc|Corp|Ltd',  # Company suffix
        # Navigation/marketing text
        r'Contact|Email|Phone|Call|Ask|Learn|Read|View|See|Get|Try|Click',
        r'About|Team|Leadership|Company|Home|Blog|News|Press|Privacy',
        r'Solutions?|Products?|Services?|Features?|Pricing|Login|Sign',
        r'Growth|Marketing|Sales|Support|Help|Customer|Partner',
        r'Explore|Quick\s+Links|Our\s+Proven|Why\s+Choose|Know\s+More',
        r'Solar\s+Panel|Home\s+Owner|Half\s+Price',  # Common garbage
        r'Comparison|Checklist|Your\s+Perfect',
    ]

    for pattern in garbage_patterns:
        if re.search(pattern, name_normalized, re.I):
            return False

    return True


def is_valid_atl_title(title: str) -> bool:
    """Check if title is a real ATL executive title."""
    if not title:
        return False

    # Title must be reasonable length (not a paragraph)
    if len(title) > 80 or '\n' in title:
        return False

    # Must contain ATL keywords
    atl_patterns = [
        r'\b(CEO|Chief\s+Executive|President)(?!\s+of\s+)',
        r'\b(CFO|Chief\s+Financial|Finance\s+Director)',
        r'\b(COO|Chief\s+Operating|Operations\s+Director)',
        r'\b(CTO|Chief\s+Technology|Tech\s+Director)',
        r'\b(CMO|Chief\s+Marketing|Marketing\s+Director)',
        r'\b(CRO|Chief\s+Revenue|Revenue\s+Director)',
        r'\b(CPO|Chief\s+Product|Product\s+Director)',
        r'\bVice\s+President\b|\bVP\b|\bSVP\b|\bEVP\b',
        r'\bDirector\b',
        r'\b(Founder|Co-?Founder|Owner)\b',
        r'\bGeneral\s+Manager\b|\bManaging\s+Director\b',
        r'\bPartner\b',
    ]

    for pattern in atl_patterns:
        if re.search(pattern, title, re.I):
            return True

    return False


# Step 1: Get all Close CRM companies (to exclude)
print("\n[1/6] Fetching Close CRM companies to exclude...")
close_companies = set()
offset = 0
while True:
    result = supabase.table('dim_companies').select('company_id, normalized_name').not_.is_(
        'close_lead_id', 'null'
    ).range(offset, offset + 999).execute()
    if not result.data:
        break
    for c in result.data:
        close_companies.add(c['company_id'])
        if c.get('normalized_name'):
            close_companies.add(c['normalized_name'].lower())
    offset += 1000
    if len(result.data) < 1000:
        break

print(f"   {len(close_companies)} Close CRM company IDs to exclude")


# Step 2: Get all contacts from BeautifulSoup enrichment
print("\n[2/6] Fetching BeautifulSoup enriched contacts...")
all_contacts = []
offset = 0
while True:
    result = supabase.table('dim_contacts').select(
        'contact_id, company_id, full_name, first_name, last_name, email, phone, title, source'
    ).eq('source', 'beautifulsoup_scraper').range(offset, offset + 999).execute()
    if not result.data:
        break
    all_contacts.extend(result.data)
    offset += 1000
    if len(result.data) < 1000:
        break

print(f"   {len(all_contacts)} total contacts from enrichment")


# Step 3: Get company details for these contacts
print("\n[3/6] Fetching company details...")
company_ids = list(set(c['company_id'] for c in all_contacts if c.get('company_id')))
companies_by_id = {}

for i in range(0, len(company_ids), 50):
    batch_ids = company_ids[i:i+50]
    result = supabase.table('dim_companies').select('*').in_('company_id', batch_ids).execute()
    for company in result.data:
        companies_by_id[company['company_id']] = company

print(f"   {len(companies_by_id)} companies loaded")


# Step 4: Filter contacts
print("\n[4/6] Filtering valid contacts...")
valid_contacts = []
filtered_reasons = {
    'garbage_name': 0,
    'invalid_title': 0,
    'in_close': 0,
    'no_company': 0,
}

for contact in all_contacts:
    company_id = contact.get('company_id')
    full_name = contact.get('full_name', '')
    title = contact.get('title', '')

    # Skip if no company
    if not company_id or company_id not in companies_by_id:
        filtered_reasons['no_company'] += 1
        continue

    company = companies_by_id[company_id]

    # Skip if company already in Close CRM
    if company_id in close_companies:
        filtered_reasons['in_close'] += 1
        continue

    normalized_name = company.get('normalized_name', '')
    if normalized_name and normalized_name.lower() in close_companies:
        filtered_reasons['in_close'] += 1
        continue

    # Validate name
    if not is_valid_contact_name(full_name):
        filtered_reasons['garbage_name'] += 1
        continue

    # Validate title
    if not is_valid_atl_title(title):
        filtered_reasons['invalid_title'] += 1
        continue

    valid_contacts.append({
        'contact': contact,
        'company': company,
    })

print(f"   {len(valid_contacts)} valid contacts")
print(f"   Filtered out:")
print(f"     - Garbage names: {filtered_reasons['garbage_name']}")
print(f"     - Invalid titles: {filtered_reasons['invalid_title']}")
print(f"     - Already in Close: {filtered_reasons['in_close']}")
print(f"     - No company: {filtered_reasons['no_company']}")


# Step 5: Deduplicate by company (keep best contact)
print("\n[5/6] Deduplicating by company...")
best_by_company = {}

for vc in valid_contacts:
    company_id = vc['company']['company_id']
    contact = vc['contact']

    # Score this contact (prefer ones with email/phone)
    score = 0
    if contact.get('email'):
        score += 50
    if contact.get('phone'):
        score += 30

    # Check for executive titles
    title_lower = contact.get('title', '').lower()
    if any(t in title_lower for t in ['ceo', 'president', 'owner', 'founder']):
        score += 20

    if company_id not in best_by_company or score > best_by_company[company_id]['score']:
        best_by_company[company_id] = {
            **vc,
            'score': score
        }

deduped = list(best_by_company.values())
print(f"   {len(deduped)} unique companies with ATL contacts")


# Step 6: Build export
print("\n[6/6] Building export CSV...")
rows = []

for item in deduped:
    company = item['company']
    contact = item['contact']

    # Format name properly (convert ALL CAPS to Title Case)
    name = contact.get('full_name', '')
    if name.isupper():
        name = name.title()

    row = {
        'Company': company.get('company_name', ''),
        'Company Domain': company.get('domain', ''),
        'Company Phone': company.get('phone', ''),
        'Company Address': company.get('street', ''),
        'Company City': company.get('city', ''),
        'Company State': company.get('state', ''),
        'Company Zip': company.get('zip', ''),
        'Contact Name': name,
        'Contact Title': contact.get('title', ''),
        'Contact Email': contact.get('email', ''),
        'Contact Phone': contact.get('phone', ''),
        'Lead Source': 'Website Enrichment - BeautifulSoup - Dec 2025',
        'Website': company.get('website', ''),
        'LinkedIn URL': company.get('linkedin_url', ''),
        'ICP Score': company.get('icp_score', ''),
        'ICP Tier': company.get('icp_tier', ''),
    }
    rows.append(row)

# Export
if rows:
    # Sort by ICP score descending
    rows.sort(key=lambda x: (x.get('ICP Score') or 0), reverse=True)

    output_dir = Path(__file__).parent / "data" / "final_enrichment_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"CLOSE_CRM_IMPORT_ENRICHED_ATL_{today}.csv"

    # Write CSV
    fieldnames = [
        'Company', 'Company Domain', 'Company Phone', 'Company Address',
        'Company City', 'Company State', 'Company Zip', 'Contact Name',
        'Contact Title', 'Contact Email', 'Contact Phone', 'Lead Source',
        'Website', 'LinkedIn URL', 'ICP Score', 'ICP Tier'
    ]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print("EXPORT COMPLETE!")
    print("=" * 70)
    print(f"\nFile: {output_path}")
    print(f"Total Leads: {len(rows)}")
    print("\n" + "-" * 70)
    print("PREVIEW:")
    print("-" * 70)
    for i, row in enumerate(rows[:15], 1):
        name = str(row['Company'])[:30]
        contact = str(row['Contact Name'])[:20]
        title = str(row['Contact Title'])[:25]
        print(f"{i:>2}. {name:<30} | {contact:<20} | {title}")
    print("-" * 70)
else:
    print("\nNo valid contacts to export!")
    print("Enrichment may still be running - check back later.")
