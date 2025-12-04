#!/usr/bin/env python3
"""
Top 30 HOT Leads Export - NON-CLOSE CRM ONLY
=============================================
Requirements:
- NOT from Close CRM (close_lead_id IS NULL)
- Source: grandmaster, master_silver, schneider_oem (dealer-scraper data)
- ATL contact with direct phone different from company main
- Email address for outreach

Author: Claude + Tim
Date: Dec 4, 2025
"""
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

print("=" * 70)
print("TOP 30 HOT LEADS - NON-CLOSE CRM (Dealer Scraper / Sales Agent Data)")
print("=" * 70)


def normalize_phone(phone):
    """Normalize phone to last 10 digits."""
    if not phone:
        return ''
    return re.sub(r'\D', '', str(phone))[-10:]


# Step 1: Get all non-Close companies
print("\n[1/5] Fetching non-Close CRM companies...")
all_non_close = []
offset = 0
while True:
    result = supabase.table('dim_companies').select('*').is_(
        'close_lead_id', 'null'
    ).range(offset, offset + 999).execute()
    if not result.data:
        break
    all_non_close.extend(result.data)
    offset += 1000
    if len(result.data) < 1000:
        break

# Filter out companies marked as DUPLICATE
all_non_close = [c for c in all_non_close if '[DUPLICATE]' not in str(c.get('company_name', ''))]
print(f"   {len(all_non_close)} non-Close companies (excludes duplicates)")

# Build lookup
companies_by_id = {c['company_id']: c for c in all_non_close}
non_close_ids = set(companies_by_id.keys())

# Step 2: Get all contacts
print("\n[2/5] Fetching contacts...")
all_contacts = []
offset = 0
while True:
    result = supabase.table('dim_contacts').select('*').range(offset, offset + 999).execute()
    if not result.data:
        break
    all_contacts.extend(result.data)
    offset += 1000
    if len(result.data) < 1000:
        break

# Filter to non-Close, ATL contacts
non_close_atl = [
    c for c in all_contacts
    if c.get('company_id') in non_close_ids and c.get('is_atl')
]
print(f"   {len(non_close_atl)} ATL contacts for non-Close companies")

# Step 3: Find HOT leads - ATL with unique direct phone + email
print("\n[3/5] Finding HOT leads (unique direct phone + email)...")
hot_leads = []

for contact in non_close_atl:
    company_id = contact.get('company_id')
    if not company_id or company_id not in companies_by_id:
        continue

    company = companies_by_id[company_id]

    contact_phone = normalize_phone(contact.get('phone'))
    company_phone = normalize_phone(company.get('phone'))
    contact_email = contact.get('email', '')

    # Must have email
    if not contact_email or '@' not in str(contact_email):
        continue

    # Must have unique direct phone (different from company main)
    if not contact_phone or contact_phone == company_phone:
        continue

    # Skip malformed phone numbers
    if len(contact_phone) > 11:
        continue

    # Calculate ICP score
    score = company.get('icp_score') or 0

    # Bonus for unique direct phone + email (HOT criteria)
    score += 25  # HOT bonus

    hot_leads.append({
        'company': company,
        'contact': contact,
        'icp_score': score,
        'has_unique_phone': True
    })

print(f"   {len(hot_leads)} HOT leads (unique direct phone + email)")

# If not enough HOT leads, also include WARM leads (email + company phone)
print("\n[4/5] Finding WARM leads (email + company phone for fallback)...")
warm_leads = []

# Get companies with phone that have ATL contacts with email
companies_with_phone = {c['company_id']: c for c in all_non_close if c.get('phone')}

for contact in non_close_atl:
    company_id = contact.get('company_id')
    if not company_id or company_id not in companies_with_phone:
        continue

    # Skip if already in hot_leads
    if any(h['contact'].get('company_id') == company_id for h in hot_leads):
        continue

    company = companies_with_phone[company_id]
    contact_email = contact.get('email', '')

    # Must have email
    if not contact_email or '@' not in str(contact_email):
        continue

    score = company.get('icp_score') or 0

    warm_leads.append({
        'company': company,
        'contact': contact,
        'icp_score': score,
        'has_unique_phone': False
    })

# Dedupe by company (keep best contact)
warm_by_company = {}
for lead in warm_leads:
    cid = lead['company']['company_id']
    if cid not in warm_by_company or lead['icp_score'] > warm_by_company[cid]['icp_score']:
        warm_by_company[cid] = lead

warm_leads = list(warm_by_company.values())
print(f"   {len(warm_leads)} WARM leads (ATL email + company phone)")

# Combine: HOT first, then WARM to fill to 30
print("\n[5/5] Building final list...")

# Dedupe HOT by company
hot_by_company = {}
for lead in hot_leads:
    cid = lead['company']['company_id']
    if cid not in hot_by_company or lead['icp_score'] > hot_by_company[cid]['icp_score']:
        hot_by_company[cid] = lead
hot_leads = list(hot_by_company.values())

# Sort by score
hot_leads.sort(key=lambda x: x['icp_score'], reverse=True)
warm_leads.sort(key=lambda x: x['icp_score'], reverse=True)

# Combine
final_leads = hot_leads[:30]
if len(final_leads) < 30:
    remaining = 30 - len(final_leads)
    # Add WARM leads that aren't already in HOT
    hot_company_ids = set(lead['company']['company_id'] for lead in final_leads)
    for lead in warm_leads:
        if lead['company']['company_id'] not in hot_company_ids:
            final_leads.append(lead)
            if len(final_leads) >= 30:
                break

print(f"   {len(final_leads)} total leads")
hot_count = sum(1 for lead in final_leads if lead['has_unique_phone'])
warm_count = sum(1 for lead in final_leads if not lead['has_unique_phone'])
print(f"   - HOT (unique direct phone): {hot_count}")
print(f"   - WARM (company phone): {warm_count}")

# Build CSV rows
rows = []
for lead in final_leads:
    company = lead['company']
    contact = lead['contact']

    # Use contact direct phone if available, otherwise company phone
    if lead['has_unique_phone']:
        call_phone = contact.get('phone', '')
        phone_type = 'DIRECT'
    else:
        call_phone = company.get('phone', '')
        phone_type = 'COMPANY'

    row = {
        'Company': company.get('company_name', ''),
        'Company Domain': company.get('domain', ''),
        'Company Phone': company.get('phone', ''),
        'Company Address': company.get('street', ''),
        'Company City': company.get('city', ''),
        'Company State': company.get('state', ''),
        'Company Zip': company.get('zip', ''),
        'Contact Name': contact.get('full_name', ''),
        'Contact Title': contact.get('title', ''),
        'Contact Email': contact.get('email', ''),
        'Contact Direct Phone': contact.get('phone', '') if lead['has_unique_phone'] else '',
        'Call This Number': call_phone,
        'Phone Type': phone_type,
        'Lead Source': 'ICP Top 30 - Dealer Scraper - Dec 2025',
        'LinkedIn URL': company.get('linkedin_url', ''),
        'LinkedIn Employees': company.get('employee_count', ''),
        'OEM Brands': (
            ', '.join(company.get('oem_brands') or [])
            if isinstance(company.get('oem_brands'), list)
            else (company.get('oem_brands') or '')
        ),
        'ICP Score': lead['icp_score'],
        'ICP Tier': 'HOT' if lead['has_unique_phone'] else 'WARM'
    }
    rows.append(row)

# Export
df = pd.DataFrame(rows)
output_dir = Path(__file__).parent / "data" / "final_enrichment_output"
output_dir.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y%m%d")
output_path = output_dir / f"CLOSE_CRM_IMPORT_TOP30_NON_CLOSE_{today}.csv"
df.to_csv(output_path, index=False)

print("\n" + "=" * 70)
print("✅ EXPORT COMPLETE!")
print("=" * 70)
print(f"\nFile: {output_path}")
print(f"Total Leads: {len(df)}")
hot_final = sum(1 for lead in final_leads if lead['has_unique_phone'])
warm_final = sum(1 for lead in final_leads if not lead['has_unique_phone'])
print(f"\n  🔥 HOT (unique direct phone): {hot_final}")
print(f"  🌡️  WARM (company phone + ATL email): {warm_final}")
print("\n" + "-" * 70)
print("PREVIEW:")
print("-" * 70)
for i, row in df.head(15).iterrows():
    tier = row['ICP Tier']
    emoji = '🔥' if tier == 'HOT' else '🌡️'
    name = str(row['Company'])[:30]
    contact = str(row['Contact Name'])[:20]
    phone = str(row['Call This Number'])[:15]
    print(f"{emoji} {i+1:>2}. {name:<30} | {contact:<20} | {phone}")
print("-" * 70)
