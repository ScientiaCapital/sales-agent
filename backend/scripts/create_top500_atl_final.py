#!/usr/bin/env python3
"""
Create Final Top 500 ATL Outreach List
======================================
Creates the definitive Top 500 ICP companies with verified ATL contacts.

Criteria:
- Email REQUIRED for all contacts
- Phone PREFERRED (prioritized in ranking)
- ATL contacts ONLY (decision makers)
- Top ICP scoring (HVAC + MEP heavy)
- Not in Close CRM, not customers

Output:
- CSV with top 500 companies + best ATL contact
- All ATL contacts flattened list
- Saved to Supabase

Author: Claude + Tim
Date: Jan 2026
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Load environment
script_dir = Path(__file__).resolve().parent
for env_path in [script_dir.parent.parent.parent / '.env', script_dir.parent.parent / '.env']:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

OUTPUT_DIR = Path(__file__).parent / "data" / "final_outreach"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y%m%d")


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return create_client(url, key)


ATL_TITLES = [
    'owner', 'president', 'ceo', 'chief', 'founder', 'principal',
    'vp', 'vice president', 'director', 'manager', 'partner',
    'executive', 'general manager', 'gm', 'operations', 'head of'
]


def is_atl_title(title: str) -> bool:
    """Check if title indicates Above The Line decision maker."""
    if not title:
        return False
    title_lower = title.lower()
    return any(kw in title_lower for kw in ATL_TITLES)


def main():
    print("\n" + "=" * 60)
    print("CREATING FINAL TOP 500 ATL OUTREACH LIST")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    supabase = get_supabase()

    # 1. Fetch all companies
    print("\n[1/6] Fetching companies...")
    all_companies = []
    offset = 0
    while True:
        result = supabase.table('dim_companies').select('*').range(offset, offset + 999).execute()
        if not result.data:
            break
        all_companies.extend(result.data)
        offset += 1000
        if len(result.data) < 1000:
            break
    companies_df = pd.DataFrame(all_companies)
    print(f"       Total companies: {len(companies_df)}")

    # 2. Fetch all contacts
    print("\n[2/6] Fetching contacts...")
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
    contacts_df = pd.DataFrame(all_contacts)
    print(f"       Total contacts: {len(contacts_df)}")

    # 3. Filter companies
    print("\n[3/6] Filtering companies...")

    # Not in Close CRM
    filtered = companies_df[
        companies_df['close_lead_id'].isna() | (companies_df['close_lead_id'] == '')
    ].copy()
    print(f"       Not in Close: {len(filtered)}")

    # Not customers
    filtered = filtered[filtered['became_customer_at'].isna()].copy()
    print(f"       Not customers: {len(filtered)}")

    # Not excluded
    filtered = filtered[
        filtered['is_excluded'].isna() | (filtered['is_excluded'] == False)
    ].copy()
    print(f"       Not excluded: {len(filtered)}")

    # 4. Get ATL contacts with EMAIL
    print("\n[4/6] Finding ATL contacts with email...")

    # Filter to ATL with email
    atl_contacts = contacts_df[
        (contacts_df['is_atl'] == True) &
        (contacts_df['email'].notna()) &
        (contacts_df['email'] != '')
    ].copy()
    print(f"       ATL contacts with email: {len(atl_contacts)}")

    # Also check title for ATL
    atl_contacts['verified_atl'] = atl_contacts['title'].apply(
        lambda x: is_atl_title(x) if pd.notna(x) else False
    )

    # Aggregate by company
    contact_stats = atl_contacts.groupby('company_id').agg(
        atl_count=('contact_id', 'count'),
        atl_with_phone=('phone', lambda x: x.notna().sum()),
        verified_atl_count=('verified_atl', 'sum')
    ).reset_index()

    contact_stats['has_phone'] = contact_stats['atl_with_phone'] > 0
    print(f"       Companies with ATL+email: {len(contact_stats)}")
    print(f"       Companies with ATL+email+phone: {contact_stats['has_phone'].sum()}")

    # 5. Calculate scores and rank
    print("\n[5/6] Calculating ICP scores...")

    # Merge
    merged = filtered.merge(contact_stats, on='company_id', how='inner')
    print(f"       Companies after merge: {len(merged)}")

    # Industry score (HVAC + MEP heavy)
    merged['industry_score'] = 0
    merged.loc[merged['has_hvac_trade'] == True, 'industry_score'] += 200  # HVAC is king
    merged.loc[merged['is_mep_contractor'] == True, 'industry_score'] += 150  # MEP
    merged.loc[merged['is_multi_trade'] == True, 'industry_score'] += 100  # Multi-trade
    merged.loc[merged['has_commercial'] == True, 'industry_score'] += 50   # C&I
    merged.loc[merged['has_industrial'] == True, 'industry_score'] += 50   # Industrial
    merged.loc[merged['has_residential'] == True, 'industry_score'] += 25  # Resi

    # Phone bonus (big bonus for having phone)
    merged['phone_bonus'] = merged['has_phone'].astype(int) * 150

    # ATL bonus (more verified ATLs = better)
    merged['atl_bonus'] = merged['verified_atl_count'] * 20

    # Total score
    merged['icp_score'] = merged['icp_score'].fillna(0)
    merged['total_score'] = (
        merged['icp_score'] +
        merged['industry_score'] +
        merged['phone_bonus'] +
        merged['atl_bonus']
    )

    # Sort and rank
    merged = merged.sort_values('total_score', ascending=False).reset_index(drop=True)
    merged['rank'] = range(1, len(merged) + 1)

    # Top 500
    top_500 = merged.head(500)
    print(f"       TOP 500 selected")

    # 6. Create output with best ATL contact per company
    print("\n[6/6] Creating output files...")

    output_rows = []
    all_atl_rows = []

    for _, company in top_500.iterrows():
        company_id = company['company_id']

        # Get ATL contacts for this company
        company_atls = atl_contacts[atl_contacts['company_id'] == company_id].copy()

        if company_atls.empty:
            continue

        # Sort by: has phone, verified title, confidence
        company_atls['sort_key'] = (
            company_atls['phone'].notna().astype(int) * 1000 +
            company_atls['verified_atl'].astype(int) * 100 +
            company_atls['confidence'].fillna(0)
        )
        company_atls = company_atls.sort_values('sort_key', ascending=False)

        # Best ATL
        best = company_atls.iloc[0]

        output_rows.append({
            'Rank': company['rank'],
            'Company': company.get('company_name'),
            'Domain': company.get('domain'),
            'Website': company.get('website'),
            'Company Phone': company.get('phone'),
            'City': company.get('city'),
            'State': company.get('state'),
            'ICP Score': company.get('icp_score'),
            'ICP Tier': company.get('icp_tier'),
            'Total Score': company.get('total_score'),
            'Industry Score': company.get('industry_score'),
            'ATL Count': company.get('atl_count'),
            'Has Phone': company.get('has_phone'),
            # Best ATL
            'ATL Name': best.get('full_name') or f"{best.get('first_name', '')} {best.get('last_name', '')}".strip(),
            'ATL Title': best.get('title'),
            'ATL Email': best.get('email'),
            'ATL Phone': best.get('phone'),
            'ATL LinkedIn': best.get('linkedin_url'),
            'ATL Verified': best.get('verified_atl'),
            'ATL Source': best.get('source'),
            # Industry signals
            'HVAC Trade': company.get('has_hvac_trade'),
            'MEP Contractor': company.get('is_mep_contractor'),
            'Commercial': company.get('has_commercial'),
            'Industrial': company.get('has_industrial'),
            'Multi-Trade': company.get('is_multi_trade'),
        })

        # All ATLs for this company
        for _, atl in company_atls.iterrows():
            all_atl_rows.append({
                'Rank': company['rank'],
                'Company': company.get('company_name'),
                'Domain': company.get('domain'),
                'State': company.get('state'),
                'ICP Tier': company.get('icp_tier'),
                'ATL Name': atl.get('full_name') or f"{atl.get('first_name', '')} {atl.get('last_name', '')}".strip(),
                'ATL Title': atl.get('title'),
                'ATL Email': atl.get('email'),
                'ATL Phone': atl.get('phone'),
                'ATL LinkedIn': atl.get('linkedin_url'),
                'Verified ATL': atl.get('verified_atl'),
                'Has Phone': pd.notna(atl.get('phone')),
                'Source': atl.get('source'),
            })

    # Save company list
    company_df = pd.DataFrame(output_rows)
    company_path = OUTPUT_DIR / f"TOP_500_ATL_OUTREACH_{TODAY}.csv"
    company_df.to_csv(company_path, index=False)
    print(f"\n[SAVED] {company_path}")
    print(f"        {len(company_df)} companies")

    # Save all ATLs
    all_atl_df = pd.DataFrame(all_atl_rows)
    all_atl_path = OUTPUT_DIR / f"TOP_500_ALL_ATL_CONTACTS_{TODAY}.csv"
    all_atl_df.to_csv(all_atl_path, index=False)
    print(f"\n[SAVED] {all_atl_path}")
    print(f"        {len(all_atl_df)} total ATL contacts")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    with_phone = company_df['Has Phone'].sum()
    print(f"\nCompanies: {len(company_df)}")
    print(f"  With phone: {with_phone} ({with_phone/len(company_df)*100:.1f}%)")
    print(f"  Email only: {len(company_df) - with_phone}")

    print(f"\nATL Contacts: {len(all_atl_df)}")
    atl_with_phone = all_atl_df['Has Phone'].sum()
    print(f"  With phone: {atl_with_phone} ({atl_with_phone/len(all_atl_df)*100:.1f}%)")

    print("\nTier Distribution:")
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
        count = (company_df['ICP Tier'] == tier).sum()
        print(f"  {tier:10}: {count:4}")

    print("\nIndustry Signals:")
    print(f"  HVAC Trade:     {company_df['HVAC Trade'].sum()}")
    print(f"  MEP Contractor: {company_df['MEP Contractor'].sum()}")
    print(f"  Multi-Trade:    {company_df['Multi-Trade'].sum()}")
    print(f"  Commercial:     {company_df['Commercial'].sum()}")
    print(f"  Industrial:     {company_df['Industrial'].sum()}")

    print("\nTop 10 States:")
    state_counts = company_df['State'].value_counts().head(10)
    for state, count in state_counts.items():
        print(f"  {str(state)[:15]:15}: {count}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"\nFiles:")
    print(f"  {company_path}")
    print(f"  {all_atl_path}")


if __name__ == "__main__":
    main()
