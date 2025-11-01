"""
CA License Cross-Reference Pipeline - Production
Matches 233 CA OEM contractors against 242,892 CA state licenses
"""

import pandas as pd
import re
import sys
from datetime import datetime

print("=" * 80)
print("CA LICENSE CROSS-REFERENCE PIPELINE")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# File paths
oem_file = '/Users/tmkipper/Desktop/tk_projects/gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/MASTER_CONTRACTOR_DATABASE_with_overlap.csv'
ca_licenses_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/ca_licenses_raw_20251031.csv'
output_dir = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses'

# Load data
print("Loading OEM contractor database...")
oem_df = pd.read_csv(oem_file)
ca_oem = oem_df[oem_df['State'] == 'CA'].copy()
print(f"✅ {len(ca_oem)} CA OEM contractors loaded")

print("Loading CA CSLB licenses (242,892 records)...")
ca_licenses = pd.read_csv(ca_licenses_file, low_memory=False)
print(f"✅ {len(ca_licenses)} CA licenses loaded")
print()

# Normalize phones
def normalize_phone(phone):
    if pd.isna(phone):
        return None
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 11 and digits[0] == '1':
        return digits[1:]
    return digits if len(digits) == 10 else None

print("Normalizing phone numbers...")
ca_oem['phone_normalized'] = ca_oem['Phone'].apply(normalize_phone)
ca_licenses['phone_normalized'] = ca_licenses['BusinessPhone'].apply(normalize_phone)

# Cross-reference
print("Cross-referencing by phone number...")
matched = ca_oem.merge(
    ca_licenses,
    on='phone_normalized',
    how='left',
    suffixes=('_oem', '_license')
)

total_matches = matched['LicenseNo'].notna().sum()
print(f"✅ {total_matches} phone matches found")
print()

# ICP license filtering
print("Filtering for ICP-aligned licenses...")
icp_licenses = ['C10', 'C20', 'C36', 'C27', 'C15', 'C-7']
multi_license_patterns = ['B|', 'A|', '|B', '|A', 'B |', 'A |']

def is_icp_license(classification):
    if pd.isna(classification):
        return False
    classification_str = str(classification)
    for lic in icp_licenses:
        if lic in classification_str:
            return True
    for pattern in multi_license_patterns:
        if pattern in classification_str:
            return True
    return False

matched['is_icp'] = matched['Classifications(s)'].apply(is_icp_license)
matched_icp = matched[matched['is_icp'] == True].copy()
print(f"✅ {len(matched_icp)} ICP-aligned matches")
print()

# Clean up columns for final output
output_columns = [
    # OEM data
    'Contractor Name', 'Phone', 'Domain', 'State',
    'ICP Fit Score', 'ICP Tier', 'Resimercial Score', 'O&M Score',
    'Multi-OEM Score', 'MEP+R Score', 'OEM Count', 'OEM Sources',
    'oem_count_verified', 'is_multi_oem',
    # License data
    'LicenseNo', 'BusinessName', 'MailingAddress', 'City_license',
    'County', 'ZIPCode', 'BusinessPhone', 'Classifications(s)',
    'PrimaryStatus', 'ExpirationDate',
    # Normalized phone
    'phone_normalized'
]

# Select available columns
available_cols = [col for col in output_columns if col in matched_icp.columns]
final_df = matched_icp[available_cols].copy()

# Save outputs
print("Saving results...")

# Output 1: Full cross-referenced data
output_file_1 = f'{output_dir}/ca_cross_referenced_20251031.csv'
final_df.to_csv(output_file_1, index=False)
print(f"✅ Saved: ca_cross_referenced_20251031.csv ({len(final_df)} records)")

# Output 2: Summary statistics
summary = {
    'total_ca_oem_contractors': len(ca_oem),
    'phone_matches': total_matches,
    'icp_aligned_matches': len(matched_icp),
    'match_rate': f"{(len(matched_icp) / len(ca_oem)) * 100:.1f}%"
}

print()
print("=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
for key, value in summary.items():
    print(f"{key.replace('_', ' ').title()}: {value}")

print()
print("License Type Breakdown:")
print("-" * 80)
license_counts = final_df['Classifications(s)'].value_counts().head(15)
for license_type, count in license_counts.items():
    print(f"  {license_type:<40} {count:>3}")

print()
print(f"✅ Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
