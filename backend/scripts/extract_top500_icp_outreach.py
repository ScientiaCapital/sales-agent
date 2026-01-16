#!/usr/bin/env python3
"""
Extract Top 500 ICP Companies for Outreach
==========================================
Extracts the best 500 ICP companies with quality ATL contacts.
- Email REQUIRED
- Phone PREFERRED (ranked higher)
- Excludes existing Close CRM leads

Usage:
    cd backend
    source venv/bin/activate
    python app/scripts/extract_top500_icp_outreach.py

Author: Claude + Tim
Date: Jan 2026
"""

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Load environment - check multiple locations
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent.parent
backend_root = script_dir.parent.parent.parent

for env_path in [project_root / '.env', backend_root / '.env']:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

# Output directory
OUTPUT_DIR = Path(__file__).parent / "data" / "icp_extracts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y%m%d")


def get_supabase_client():
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def fetch_all_data():
    """Fetch all companies and contacts into pandas DataFrames."""
    print("\n" + "=" * 60)
    print("FETCHING DATA FROM SUPABASE")
    print("=" * 60)

    supabase = get_supabase_client()

    # Fetch all companies
    print("\n[1/2] Fetching companies...")
    all_companies = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_companies').select('*').range(offset, offset + batch_size - 1).execute()
        if not result.data:
            break
        all_companies.extend(result.data)
        offset += batch_size
        if len(result.data) < batch_size:
            break

    companies_df = pd.DataFrame(all_companies)
    print(f"   Loaded {len(companies_df)} companies")

    # Fetch all contacts
    print("\n[2/2] Fetching contacts...")
    all_contacts = []
    offset = 0

    while True:
        result = supabase.table('dim_contacts').select('*').range(offset, offset + batch_size - 1).execute()
        if not result.data:
            break
        all_contacts.extend(result.data)
        offset += batch_size
        if len(result.data) < batch_size:
            break

    contacts_df = pd.DataFrame(all_contacts)
    print(f"   Loaded {len(contacts_df)} contacts")

    return companies_df, contacts_df


def calculate_company_scores(companies_df: pd.DataFrame, contacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate composite scores for ranking companies.

    Criteria:
    1. Email REQUIRED (at least 1 ATL with email)
    2. Phone PREFERRED (bonus points)
    3. HVAC + MEP prioritized
    4. ICP score
    5. ATL count
    """
    print("\n" + "=" * 60)
    print("CALCULATING COMPANY SCORES")
    print("=" * 60)

    # Filter to companies NOT in Close CRM
    not_in_close = companies_df[
        companies_df['close_lead_id'].isna() | (companies_df['close_lead_id'] == '')
    ].copy()
    print(f"\n[1/6] Companies NOT in Close CRM: {len(not_in_close)}")

    # Exclude customers
    not_customers = not_in_close[not_in_close['became_customer_at'].isna()].copy()
    print(f"[2/6] After excluding customers: {len(not_customers)}")

    # Exclude flagged/excluded
    not_excluded = not_customers[
        not_customers['is_excluded'].isna() | (not_customers['is_excluded'] == False)
    ].copy()
    print(f"[3/6] After excluding flagged: {len(not_excluded)}")

    # Get ATL contacts with email
    atl_contacts = contacts_df[contacts_df['is_atl'] == True].copy()
    atl_with_email = atl_contacts[atl_contacts['email'].notna() & (atl_contacts['email'] != '')].copy()
    print(f"\n[4/6] ATL contacts with email: {len(atl_with_email)}")

    # Aggregate contact stats per company
    contact_stats = atl_with_email.groupby('company_id').agg(
        atl_count=('contact_id', 'count'),
        atl_with_phone=('phone', lambda x: x.notna().sum()),
        emails=('email', lambda x: list(x.dropna())),
        phones=('phone', lambda x: list(x.dropna())),
    ).reset_index()

    # Mark if has phone
    contact_stats['has_phone'] = contact_stats['atl_with_phone'] > 0

    print(f"[5/6] Companies with ATL+email: {len(contact_stats)}")
    print(f"       Companies with ATL+email+phone: {contact_stats['has_phone'].sum()}")

    # Merge with company data
    merged = not_excluded.merge(contact_stats, on='company_id', how='inner')
    print(f"\n[6/6] Companies after merge: {len(merged)}")

    # Calculate industry score (HVAC HEAVY prioritization)
    merged['industry_score'] = 0
    merged.loc[merged['has_hvac_trade'] == True, 'industry_score'] += 150  # HVAC is king
    merged.loc[merged['is_mep_contractor'] == True, 'industry_score'] += 100  # MEP second
    merged.loc[merged['is_multi_trade'] == True, 'industry_score'] += 75   # Multi-trade bonus
    merged.loc[merged['has_commercial'] == True, 'industry_score'] += 50   # C&I
    merged.loc[merged['has_industrial'] == True, 'industry_score'] += 50   # Industrial
    merged.loc[merged['has_residential'] == True, 'industry_score'] += 25  # Resi HVAC

    # Calculate phone bonus
    merged['phone_bonus'] = merged['has_phone'].astype(int) * 100

    # Calculate ATL bonus (more ATLs = better)
    merged['atl_bonus'] = np.minimum(merged['atl_count'] * 10, 50)

    # Total score = ICP + Industry + Phone + ATL
    merged['icp_score'] = merged['icp_score'].fillna(0)
    merged['total_score'] = (
        merged['icp_score'] +
        merged['industry_score'] +
        merged['phone_bonus'] +
        merged['atl_bonus']
    )

    # Sort by total score
    merged = merged.sort_values('total_score', ascending=False).reset_index(drop=True)
    merged['rank'] = range(1, len(merged) + 1)

    return merged


def get_best_contact(company_id: str, contacts_df: pd.DataFrame) -> dict:
    """Get the best ATL contact for a company."""
    company_contacts = contacts_df[
        (contacts_df['company_id'] == company_id) &
        (contacts_df['is_atl'] == True) &
        (contacts_df['email'].notna())
    ].copy()

    if company_contacts.empty:
        return {}

    # Prioritize: has phone > verified > confidence
    company_contacts['sort_key'] = (
        company_contacts['phone'].notna().astype(int) * 1000 +
        company_contacts['email_verified'].fillna(False).astype(int) * 100 +
        company_contacts['confidence'].fillna(0)
    )

    best = company_contacts.sort_values('sort_key', ascending=False).iloc[0]

    return {
        'name': best.get('full_name') or f"{best.get('first_name', '')} {best.get('last_name', '')}".strip(),
        'title': best.get('title'),
        'email': best.get('email'),
        'phone': best.get('phone'),
        'linkedin': best.get('linkedin_url'),
        'verified': best.get('email_verified') or best.get('phone_verified'),
        'source': best.get('source')
    }


def display_summary(df: pd.DataFrame):
    """Display summary statistics."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(df)
    with_phone = df['has_phone'].sum()
    without_phone = total - with_phone

    print(f"\nTotal companies: {total}")
    print(f"  With phone:    {with_phone} ({with_phone/total*100:.1f}%)")
    print(f"  Email only:    {without_phone} ({without_phone/total*100:.1f}%)")

    # Tier distribution
    print("\nTier Distribution:")
    tier_counts = df['icp_tier'].value_counts()
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
        count = tier_counts.get(tier, 0)
        pct = count / total * 100
        bar = '#' * int(pct / 2)
        print(f"   {tier:10} {count:4} ({pct:5.1f}%) {bar}")

    # Industry signals
    print("\nIndustry Signals:")
    print(f"   HVAC Trade:      {df['has_hvac_trade'].sum():4}")
    print(f"   MEP Contractor:  {df['is_mep_contractor'].sum():4}")
    print(f"   Multi-Trade:     {df['is_multi_trade'].sum():4}")
    print(f"   Commercial:      {df['has_commercial'].sum():4}")
    print(f"   Industrial:      {df['has_industrial'].sum():4}")

    # Top states
    print("\nTop 10 States:")
    state_counts = df['state'].value_counts().head(10)
    for state, count in state_counts.items():
        print(f"   {str(state)[:15]:15} {count:4}")


def display_top_20(df: pd.DataFrame, contacts_df: pd.DataFrame):
    """Display top 20 preview."""
    print("\n" + "=" * 60)
    print("TOP 20 PREVIEW")
    print("=" * 60)
    print(f"{'#':>3} | {'Company':<30} | {'State':<6} | {'Tier':<8} | {'Score':>5} | {'ATLs':>4} | {'Phone':>5} | {'Best Contact':<20}")
    print("-" * 110)

    for _, row in df.head(20).iterrows():
        best = get_best_contact(row['company_id'], contacts_df)
        phone_status = 'Yes' if row['has_phone'] else 'No'
        print(f"{row['rank']:>3} | {str(row.get('company_name', ''))[:30]:<30} | {str(row.get('state', ''))[:6]:<6} | {str(row.get('icp_tier', 'LEAD'))[:8]:<8} | {row['total_score']:>5.0f} | {row['atl_count']:>4} | {phone_status:>5} | {str(best.get('name', ''))[:20]:<20}")


def export_to_csv(df: pd.DataFrame, contacts_df: pd.DataFrame) -> tuple[Path, Path]:
    """Export companies and contacts to CSV."""
    print("\n" + "=" * 60)
    print("EXPORTING TO CSV")
    print("=" * 60)

    # Company export
    company_rows = []
    for _, row in df.iterrows():
        best = get_best_contact(row['company_id'], contacts_df)
        company_rows.append({
            'Rank': row['rank'],
            'Company': row.get('company_name'),
            'Domain': row.get('domain'),
            'Website': row.get('website'),
            'Company Phone': row.get('phone'),
            'City': row.get('city'),
            'State': row.get('state'),
            'ICP Score': row.get('icp_score'),
            'ICP Tier': row.get('icp_tier'),
            'Total Score': row.get('total_score'),
            'Industry Score': row.get('industry_score'),
            'ATL Count': row.get('atl_count'),
            'Has Phone': row.get('has_phone'),
            # Best contact
            'Best ATL Name': best.get('name'),
            'Best ATL Title': best.get('title'),
            'Best ATL Email': best.get('email'),
            'Best ATL Phone': best.get('phone'),
            'Best ATL LinkedIn': best.get('linkedin'),
            'Best ATL Verified': best.get('verified'),
            # Industry signals
            'HVAC Trade': row.get('has_hvac_trade'),
            'MEP Contractor': row.get('is_mep_contractor'),
            'Commercial': row.get('has_commercial'),
            'Industrial': row.get('has_industrial'),
            'Multi-Trade': row.get('is_multi_trade'),
            'Residential': row.get('has_residential'),
            'Trade Count': row.get('trade_count'),
            'OEM Count': row.get('oem_count'),
        })

    company_df = pd.DataFrame(company_rows)
    company_path = OUTPUT_DIR / f"TOP_500_ICP_OUTREACH_{TODAY}.csv"
    company_df.to_csv(company_path, index=False)
    print(f"\n[EXPORTED] {company_path}")
    print(f"           {len(company_df)} companies")

    # All contacts export (flattened)
    contact_rows = []
    for _, row in df.iterrows():
        company_contacts = contacts_df[
            (contacts_df['company_id'] == row['company_id']) &
            (contacts_df['is_atl'] == True) &
            (contacts_df['email'].notna())
        ]
        for _, contact in company_contacts.iterrows():
            contact_rows.append({
                'Rank': row['rank'],
                'Company': row.get('company_name'),
                'Domain': row.get('domain'),
                'State': row.get('state'),
                'ICP Tier': row.get('icp_tier'),
                'Contact Name': contact.get('full_name') or f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                'Contact Title': contact.get('title'),
                'Contact Email': contact.get('email'),
                'Contact Phone': contact.get('phone'),
                'Contact LinkedIn': contact.get('linkedin_url'),
                'Email Verified': contact.get('email_verified'),
                'Phone Verified': contact.get('phone_verified'),
                'Source': contact.get('source'),
            })

    contacts_export_df = pd.DataFrame(contact_rows)
    contacts_path = OUTPUT_DIR / f"TOP_500_ALL_CONTACTS_{TODAY}.csv"
    contacts_export_df.to_csv(contacts_path, index=False)
    print(f"\n[EXPORTED] {contacts_path}")
    print(f"           {len(contacts_export_df)} total ATL contacts")

    return company_path, contacts_path


def main():
    """Main execution."""
    print("\n" + "=" * 60)
    print("TOP 500 ICP OUTREACH EXTRACTION")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Criteria: Email REQUIRED, Phone PREFERRED")
    print("=" * 60)

    # Fetch data
    companies_df, contacts_df = fetch_all_data()

    # Calculate scores and rank
    scored_df = calculate_company_scores(companies_df, contacts_df)

    if len(scored_df) == 0:
        print("\n[ERROR] No qualifying companies found!")
        return

    # Take top 500
    top_500 = scored_df.head(500)
    print(f"\n*** TOP {len(top_500)} COMPANIES SELECTED ***")

    # Display summary
    display_summary(top_500)
    display_top_20(top_500, contacts_df)

    # Export to CSV
    export_to_csv(top_500, contacts_df)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the CSV files in backend/app/scripts/data/icp_extracts/")
    print("2. Import to Close CRM as new leads")
    print("3. Enroll in ICP-Energy-Multitrade sequence")
    print()


if __name__ == "__main__":
    main()
