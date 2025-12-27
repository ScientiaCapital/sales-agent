#!/usr/bin/env python3
"""
Top 30 HOT Leads Export - ATL Contacts with Unique Direct Phones
================================================================
Requirements:
- ATL contact (decision maker)
- Direct phone DIFFERENT from company main phone
- Email address for outreach
- Sorted by ICP score

Author: Claude + Tim
Date: Dec 4, 2025
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

# Connect to Supabase
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

print("=" * 60)
print("TOP 30 HOT LEADS - ATL + Unique Direct Phone + Email")
print("=" * 60)

# Fetch all ATL contacts with phone and email
print("\n[1/4] Fetching ATL contacts with phone + email...")
all_contacts = []
offset = 0
batch_size = 1000

while True:
    result = supabase.table('dim_contacts').select(
        'company_id, full_name, title, email, phone'
    ).eq('is_atl', True).range(offset, offset + batch_size - 1).execute()

    if not result.data:
        break
    all_contacts.extend(result.data)
    offset += batch_size
    if len(result.data) < batch_size:
        break

print(f"   Found {len(all_contacts)} ATL contacts total")

# Filter contacts with both phone and email
contacts_with_phone_email = [
    c for c in all_contacts
    if c.get('phone') and c.get('email') and '@' in str(c.get('email', ''))
]
print(f"   {len(contacts_with_phone_email)} have both phone AND email")

# Get unique company IDs
company_ids = list(set(c['company_id'] for c in contacts_with_phone_email if c.get('company_id')))
print(f"   {len(company_ids)} unique companies")

# Fetch those companies
print("\n[2/4] Fetching company data...")
companies_by_id = {}
for i in range(0, len(company_ids), 50):
    batch_ids = company_ids[i:i+50]
    result = supabase.table('dim_companies').select('*').in_('company_id', batch_ids).execute()
    for c in result.data or []:
        companies_by_id[c['company_id']] = c

print(f"   Loaded {len(companies_by_id)} companies")


def normalize_phone(phone):
    """Normalize phone to last 10 digits for comparison."""
    if not phone:
        return ''
    return re.sub(r'\D', '', str(phone))[-10:]


# Build HOT leads list (unique direct phone different from company main)
print("\n[3/4] Finding HOT leads (unique direct phone ≠ company phone)...")
hot_leads = []

for contact in contacts_with_phone_email:
    company_id = contact.get('company_id')
    if not company_id or company_id not in companies_by_id:
        continue

    company = companies_by_id[company_id]

    contact_phone = normalize_phone(contact.get('phone'))
    company_phone = normalize_phone(company.get('phone'))

    # Skip companies marked as DUPLICATE
    company_name = str(company.get('company_name', ''))
    if '[DUPLICATE]' in company_name or '[duplicate]' in company_name.lower():
        continue

    # Skip malformed phone numbers (should be 10-11 digits)
    if len(contact_phone) > 11:
        continue

    # CRITICAL: Contact phone must be DIFFERENT from company main phone
    if contact_phone and contact_phone != company_phone:
        # Calculate ICP score inline
        score = 0

        # Contact quality (has unique phone + email = 25 pts)
        score += 20  # unique phone
        score += 5   # email

        # State bonus
        state = str(company.get('state') or '').upper()[:2]
        state_scores = {
            'CA': 15, 'TX': 15, 'FL': 15,
            'NJ': 12, 'MA': 12, 'MD': 10, 'PA': 10,
            'NY': 8, 'AZ': 8, 'NV': 8, 'CO': 8, 'NC': 8
        }
        score += state_scores.get(state, 0)

        # Domain bonus
        if company.get('domain'):
            score += 5

        # OEM brands bonus
        oem_brands = company.get('oem_brands') or []
        if isinstance(oem_brands, str):
            oem_brands = [b.strip() for b in oem_brands.split(',') if b.strip()]
        score += min(len(oem_brands) * 5, 15)

        hot_leads.append({
            'company': company,
            'contact': contact,
            'icp_score': score,
            'contact_phone_normalized': contact_phone,
            'company_phone_normalized': company_phone
        })

print(f"   Found {len(hot_leads)} HOT leads with unique direct phones!")

# DEDUPE: Keep only the best contact per company
print("\n   Deduplicating (1 best contact per company)...")
best_by_company = {}
for lead in hot_leads:
    company_id = lead['company']['company_id']
    if company_id not in best_by_company:
        best_by_company[company_id] = lead
    else:
        # Keep the one with higher score or better title
        existing = best_by_company[company_id]
        existing_title = str(existing['contact'].get('title', '')).lower()
        new_title = str(lead['contact'].get('title', '')).lower()

        # Prefer Owner > President > CEO > VP > Director > Manager
        title_priority = ['owner', 'president', 'ceo', 'founder', 'vp', 'vice president', 'director']

        def get_title_score(title):
            for i, t in enumerate(title_priority):
                if t in title:
                    return len(title_priority) - i
            return 0

        if get_title_score(new_title) > get_title_score(existing_title):
            best_by_company[company_id] = lead

hot_leads = list(best_by_company.values())
print(f"   {len(hot_leads)} unique companies with HOT leads")

if len(hot_leads) == 0:
    print("\n⚠️  NO HOT LEADS FOUND!")
    print("   This means no ATL contacts have:")
    print("   - A phone number different from company main")
    print("   - An email address")
    print("\n   Options:")
    print("   1. Run more enrichment to discover direct phones")
    print("   2. Export leads with email only (no unique phone requirement)")
    sys.exit(1)

# Sort by ICP score and take top 30
hot_leads.sort(key=lambda x: x['icp_score'], reverse=True)
top_30 = hot_leads[:30]

print(f"\n[4/4] Exporting top {len(top_30)} leads to CSV...")

# Build Close CRM format rows
rows = []
for lead in top_30:
    company = lead['company']
    contact = lead['contact']

    row = {
        'Company': company.get('company_name', ''),
        'Company Domain': company.get('domain', ''),
        'Company Phone': company.get('phone', ''),
        'Company Address': company.get('address', ''),
        'Company City': company.get('city', ''),
        'Company State': company.get('state', ''),
        'Company Zip': company.get('zip', ''),
        'Contact Name': contact.get('full_name', ''),
        'Contact Title': contact.get('title', ''),
        'Contact Email': contact.get('email', ''),
        'Contact Direct Phone': contact.get('phone', ''),  # THE UNIQUE DIRECT PHONE
        'Lead Source': 'ICP Top 30 HOT - Dec 2025',
        'LinkedIn URL': company.get('linkedin_url', ''),
        'LinkedIn Employees': company.get('employee_count', ''),
        'ICP Score': lead['icp_score'],
        'ICP Tier': 'HOT'
    }
    rows.append(row)

# Export
df = pd.DataFrame(rows)
output_dir = Path(__file__).parent / "data" / "final_enrichment_output"
output_dir.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y%m%d")
output_path = output_dir / f"CLOSE_CRM_IMPORT_TOP30_HOT_{today}.csv"
df.to_csv(output_path, index=False)

print("\n" + "=" * 60)
print("✅ EXPORT COMPLETE!")
print("=" * 60)
print(f"\nFile: {output_path}")
print(f"Leads: {len(df)}")
print("\nAll leads have:")
print("  ✓ ATL contact (decision maker)")
print("  ✓ Unique direct phone (≠ company main)")
print("  ✓ Email address")
print("\n" + "-" * 60)
print("TOP 10 PREVIEW:")
print("-" * 60)
for i, row in df.head(10).iterrows():
    name = str(row['Company'])[:28]
    contact = str(row['Contact Name'])[:18]
    phone = str(row['Contact Direct Phone'])
    print(f"{i+1:>2}. {name:<28} | {contact:<18} | {phone}")
print("-" * 60)
