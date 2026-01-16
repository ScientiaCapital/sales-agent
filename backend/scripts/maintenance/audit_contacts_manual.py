#!/usr/bin/env python3
"""
Manual Contact Quality Audit
=============================
Shows you ACTUAL contacts found so you can verify they're real people.

This helps prevent hallucinations by showing you:
1. The exact text extracted
2. The website URL to manually check
3. Red flags (short names, weird titles, etc.)

Usage:
    python3 audit_contacts_manual.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent.parent / '.env')

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

print("\n" + "=" * 80)
print("MANUAL CONTACT QUALITY AUDIT - FIND HALLUCINATIONS")
print("=" * 80 + "\n")

# Get ATL contacts with source = beautifulsoup_scraper (from recent enrichment)
recent_contacts = supabase.table('dim_contacts') \
    .select('contact_id, full_name, title, company_id, email, phone, source') \
    .eq('source', 'beautifulsoup_scraper') \
    .eq('is_atl', True) \
    .limit(100) \
    .execute()

print(f"Found {len(recent_contacts.data)} recent ATL contacts from BeautifulSoup scraper\n")

# Quality check each contact
good_contacts = []
suspicious_contacts = []

for contact in recent_contacts.data:
    name = contact['full_name']
    title = contact['title']

    # Red flags for garbage data
    red_flags = []

    # Flag 1: Name is too short or too long
    if len(name) < 5:
        red_flags.append("Name too short")
    if len(name) > 50:
        red_flags.append("Name too long")

    # Flag 2: Name contains obvious non-person words
    non_person_keywords = [
        'blog', 'faq', 'click', 'email', 'zipcode', 'message', 'contact',
        'website', 'cookies', 'privacy', 'terms', 'should', 'follow',
        'operated', 'recent', 'news', 'locations', 'careers', 'join',
        'download', 'video', 'testimonial', 'magazine', 'tv', 'payment'
    ]

    name_lower = name.lower()
    for keyword in non_person_keywords:
        if keyword in name_lower:
            red_flags.append(f"Contains '{keyword}'")
            break

    # Flag 3: Title contains obvious non-title words
    title_lower = title.lower()
    for keyword in non_person_keywords:
        if keyword in title_lower:
            red_flags.append(f"Title contains '{keyword}'")
            break

    # Flag 4: Name is all caps with weird formatting
    if name == name.upper() and ' ' not in name and len(name) > 10:
        red_flags.append("All caps, no spaces")

    # Categorize
    if red_flags:
        suspicious_contacts.append({
            'contact': contact,
            'red_flags': red_flags
        })
    else:
        good_contacts.append(contact)

# Show results
print("✅ GOOD CONTACTS (Likely Real People)")
print("-" * 80)
for contact in good_contacts[:20]:  # Show first 20
    company = supabase.table('dim_companies') \
        .select('company_name, website') \
        .eq('company_id', contact['company_id']) \
        .single() \
        .execute()

    print(f"• {contact['full_name']} - {contact['title']}")
    print(f"  Company: {company.data['company_name']}")
    print(f"  Verify: {company.data['website']}/about or /team")
    if contact['email']:
        print(f"  Email: {contact['email']}")
    print()

print(f"\n{'=' * 80}\n")
print("🚩 SUSPICIOUS CONTACTS (Likely Garbage)")
print("-" * 80)
for item in suspicious_contacts[:20]:  # Show first 20
    contact = item['contact']
    red_flags = item['red_flags']

    company = supabase.table('dim_companies') \
        .select('company_name, website') \
        .eq('company_id', contact['company_id']) \
        .single() \
        .execute()

    print(f"❌ {contact['full_name']} - {contact['title']}")
    print(f"   Red Flags: {', '.join(red_flags)}")
    print(f"   Company: {company.data['company_name']}")
    print()

# Summary
print(f"\n{'=' * 80}")
print(f"\n📊 QUALITY SUMMARY:")
print(f"   Total Contacts: {len(recent_contacts.data)}")
print(f"   ✅ Good (Real People): {len(good_contacts)} ({len(good_contacts)/len(recent_contacts.data)*100:.1f}%)")
print(f"   🚩 Suspicious (Garbage): {len(suspicious_contacts)} ({len(suspicious_contacts)/len(recent_contacts.data)*100:.1f}%)")
print()

# Recommendation
if len(suspicious_contacts) / len(recent_contacts.data) > 0.3:
    print("⚠️  HIGH GARBAGE RATE (>30%)")
    print("   RECOMMENDATION: Fix the BeautifulSoup scraper before continuing")
    print("   Current scraper is too aggressive and catching non-person text")
    print()
    print("   Next Steps:")
    print("   1. Improve HTML parsing to filter out navigation/buttons")
    print("   2. Add validation: name must have first + last name format")
    print("   3. Add validation: title must be from known title list")
    print("   4. Re-run enrichment with fixed scraper")
else:
    print("✅ QUALITY IS ACCEPTABLE (<30% garbage)")
    print("   Can proceed with enrichment, but monitor quality")

print()
