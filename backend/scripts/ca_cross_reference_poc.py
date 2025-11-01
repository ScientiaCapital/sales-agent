"""
CA License Cross-Reference - Proof of Concept
Quick test to see how many CA OEM contractors match with CSLB licenses
"""

import pandas as pd
import re
import sys

print("=" * 80)
print("CA LICENSE CROSS-REFERENCE - PROOF OF CONCEPT")
print("=" * 80)
print()

# File paths
oem_file = '/Users/tmkipper/Desktop/tk_projects/gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/MASTER_CONTRACTOR_DATABASE_with_overlap.csv'
ca_licenses_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/ca_licenses_raw_20251031.csv'

print("Step 1: Loading OEM contractor database...")
try:
    oem_df = pd.read_csv(oem_file)
    print(f"✅ Loaded {len(oem_df)} total OEM contractors")

    # Filter for CA only
    ca_oem = oem_df[oem_df['State'] == 'CA'].copy()
    print(f"✅ Filtered to {len(ca_oem)} CA OEM contractors")
except Exception as e:
    print(f"❌ Error loading OEM database: {e}")
    sys.exit(1)

print()
print("Step 2: Loading CA CSLB licenses (242,892 records - this may take a moment)...")
try:
    ca_licenses = pd.read_csv(ca_licenses_file)
    print(f"✅ Loaded {len(ca_licenses)} CA state licenses")
except Exception as e:
    print(f"❌ Error loading CA licenses: {e}")
    sys.exit(1)

print()
print("Step 3: Normalizing phone numbers...")

def normalize_phone(phone):
    """Normalize phone to 10 digits"""
    if pd.isna(phone):
        return None
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str(phone))
    # Remove leading 1 if present
    if len(digits) == 11 and digits[0] == '1':
        return digits[1:]
    # Return only if exactly 10 digits
    return digits if len(digits) == 10 else None

ca_oem['phone_normalized'] = ca_oem['Phone'].apply(normalize_phone)
ca_licenses['phone_normalized'] = ca_licenses['BusinessPhone'].apply(normalize_phone)

# Count valid phones
oem_valid_phones = ca_oem['phone_normalized'].notna().sum()
licenses_valid_phones = ca_licenses['phone_normalized'].notna().sum()

print(f"✅ OEM contractors with valid phones: {oem_valid_phones}/{len(ca_oem)} ({oem_valid_phones/len(ca_oem)*100:.1f}%)")
print(f"✅ CA licenses with valid phones: {licenses_valid_phones}/{len(ca_licenses)} ({licenses_valid_phones/len(ca_licenses)*100:.1f}%)")

print()
print("Step 4: Cross-referencing by phone number...")

# Merge on phone
matched = ca_oem.merge(
    ca_licenses,
    on='phone_normalized',
    how='left',
    suffixes=('_oem', '_license')
)

# Count matches (where license data exists)
total_matches = matched['LicenseNo'].notna().sum()
match_rate = (total_matches / len(ca_oem)) * 100

print(f"✅ Phone matches found: {total_matches}/{len(ca_oem)} ({match_rate:.1f}% match rate)")

print()
print("Step 5: Filtering for ICP-aligned licenses...")

# ICP license types
icp_licenses = ['C10', 'C20', 'C36', 'C27', 'C15', 'C-7']
multi_license_patterns = ['B|', 'A|', '|B', '|A', 'B |', 'A |']

def is_icp_license(classification):
    """Check if license classification matches ICP criteria"""
    if pd.isna(classification):
        return False
    classification_str = str(classification)

    # Check for ICP single licenses
    for lic in icp_licenses:
        if lic in classification_str:
            return True

    # Check for multi-license patterns (B|C10, A|B, etc.)
    for pattern in multi_license_patterns:
        if pattern in classification_str:
            return True

    return False

matched['is_icp'] = matched['Classifications(s)'].apply(is_icp_license)
matched_icp = matched[matched['is_icp'] == True].copy()

print(f"✅ ICP-aligned matches: {len(matched_icp)}/{total_matches} ({len(matched_icp)/total_matches*100:.1f}% of matches)")

print()
print("=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
print()
print(f"CA OEM Contractors:           {len(ca_oem)}")
print(f"Phone Matches Found:          {total_matches} ({match_rate:.1f}%)")
print(f"ICP-Aligned Matches:          {len(matched_icp)} ({len(matched_icp)/len(ca_oem)*100:.1f}% of total)")
print()

# License type breakdown
print("License Type Breakdown (Top 10):")
print("-" * 80)
if len(matched_icp) > 0:
    license_counts = matched_icp['Classifications(s)'].value_counts().head(10)
    for license_type, count in license_counts.items():
        print(f"  {license_type:<40} {count:>3} contractors")
else:
    print("  No ICP matches found")

print()

# Sample matched contractors
if len(matched_icp) > 0:
    print("Sample Matched Contractors (Top 5):")
    print("-" * 80)
    sample = matched_icp[['Contractor Name', 'Phone', 'BusinessName', 'Classifications(s)', 'City']].head(5)
    for idx, row in sample.iterrows():
        print(f"\n{row['Contractor Name']}")
        print(f"  Phone: {row['Phone']}")
        print(f"  License Business Name: {row['BusinessName']}")
        print(f"  License Type: {row['Classifications(s)']}")
        print(f"  City: {row['City']}")

print()
print("=" * 80)

# Save results
output_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/ca_cross_referenced_poc_20251031.csv'
matched_icp.to_csv(output_file, index=False)
print(f"✅ Results saved to: {output_file}")
print()
print(f"📊 Final Count: {len(matched_icp)} ICP-aligned CA contractors ready for enrichment")
print("=" * 80)
