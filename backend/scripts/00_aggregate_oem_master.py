"""
Phase 0: OEM Master Database Aggregation
Aggregates multiple OEM relationship rows into single contractor records
This enables proper multi-OEM and multi-state detection
"""

import pandas as pd
import re
from datetime import datetime

print("=" * 80)
print("PHASE 0: OEM MASTER AGGREGATION")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# File paths
oem_master_file = '/Users/tmkipper/Desktop/tk_projects/gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/MASTER_CONTRACTOR_DATABASE_with_overlap.csv'
output_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/oem_master_aggregated_20251031.csv'

# Load OEM master database
print("Loading OEM master database...")
oem_master = pd.read_csv(oem_master_file)
print(f"✅ {len(oem_master)} OEM relationship records loaded")
print()

# Phone normalization
def normalize_phone(phone):
    """Normalize phone to 10 digits"""
    if pd.isna(phone):
        return None
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 11 and digits[0] == '1':
        return digits[1:]
    return digits if len(digits) == 10 else None

print("Normalizing phone numbers...")
oem_master['phone_normalized'] = oem_master['Phone'].apply(normalize_phone)

# Count valid phones
valid_phones = oem_master['phone_normalized'].notna().sum()
print(f"✅ {valid_phones}/{len(oem_master)} records have valid phones ({valid_phones/len(oem_master)*100:.1f}%)")
print()

# Show sample before aggregation
print("Sample BEFORE aggregation (showing contractors with multiple OEMs):")
print("-" * 80)
phone_counts = oem_master['phone_normalized'].value_counts()
multi_oem_phones = phone_counts[phone_counts > 1].head(3)

for phone in multi_oem_phones.index:
    if pd.notna(phone):
        records = oem_master[oem_master['phone_normalized'] == phone]
        print(f"\nPhone: {phone}")
        for idx, row in records.iterrows():
            print(f"  - {row['Contractor Name']} | {row.get('State', 'N/A')} | OEM: {row.get('OEM Sources', 'N/A')}")
print()

# Aggregate by phone
print("Aggregating OEM relationships by phone number...")

oem_aggregated = oem_master.groupby('phone_normalized').agg({
    # Keep first contractor info
    'Contractor Name': 'first',
    'Phone': 'first',
    'Domain': 'first',
    'City': 'first',

    # Aggregate states (multi-state if contractor appears in multiple states)
    'State': lambda x: ','.join(x.unique()) if x.notna().any() else None,

    # Aggregate OEM sources (combine all OEM certifications)
    'OEM Sources': lambda x: ', '.join([str(s) for s in x if pd.notna(s)]),

    # Count total OEMs per contractor
    'OEM Count': 'sum',

    # Average ICP scores across OEM relationships
    'ICP Fit Score': lambda x: x.mean() if x.notna().any() else 0,
    'ICP Tier': 'first',
    'Resimercial Score': lambda x: x.mean() if x.notna().any() else 0,
    'O&M Score': lambda x: x.mean() if x.notna().any() else 0,
    'Multi-OEM Score': lambda x: x.mean() if x.notna().any() else 0,
    'MEP+R Score': lambda x: x.mean() if x.notna().any() else 0,

    # Keep verified flags
    'is_multi_oem': 'max',
    'oem_count_verified': 'sum',
}).reset_index()

print(f"✅ Aggregated to {len(oem_aggregated)} unique contractors")
print()

# Calculate state count
def count_states(state_str):
    """Count unique states from comma-separated string"""
    if pd.isna(state_str):
        return 0
    return len([s.strip() for s in str(state_str).split(',') if s.strip()])

oem_aggregated['state_count'] = oem_aggregated['State'].apply(count_states)

# Update is_multi_oem flag based on aggregated OEM Count
oem_aggregated['is_multi_oem'] = oem_aggregated['OEM Count'] >= 2

# Mark multi-state contractors
oem_aggregated['is_multi_state'] = oem_aggregated['state_count'] >= 2

# Calculate multi-state bonus
oem_aggregated['multi_state_bonus'] = (oem_aggregated['state_count'] - 1) * 20
oem_aggregated['multi_state_bonus'] = oem_aggregated['multi_state_bonus'].clip(lower=0)

# Recalculate multi-OEM score with aggregated count
oem_aggregated['Multi-OEM Score'] = (oem_aggregated['OEM Count'] * 25).clip(upper=100)

# Save aggregated data
print("Saving aggregated OEM master database...")
oem_aggregated.to_csv(output_file, index=False)
print(f"✅ Saved: {output_file.split('/')[-1]}")
print()

# Statistics
print("=" * 80)
print("AGGREGATION RESULTS")
print("=" * 80)
print()

print(f"Original OEM relationships: {len(oem_master)}")
print(f"Unique contractors:          {len(oem_aggregated)}")
print(f"Aggregation ratio:           {len(oem_master) / len(oem_aggregated):.2f}x")
print()

# OEM distribution
print("OEM Count Distribution:")
print("-" * 80)
oem_counts = oem_aggregated['OEM Count'].value_counts().sort_index()
for count, num_contractors in oem_counts.items():
    pct = (num_contractors / len(oem_aggregated)) * 100
    print(f"  {int(count)} OEM(s):  {num_contractors:>4} contractors ({pct:>5.1f}%)")

print()
multi_oem = (oem_aggregated['OEM Count'] >= 2).sum()
print(f"✅ Multi-OEM contractors: {multi_oem} ({multi_oem/len(oem_aggregated)*100:.1f}%)")

# State distribution
print()
print("State Count Distribution:")
print("-" * 80)
state_counts = oem_aggregated['state_count'].value_counts().sort_index()
for count, num_contractors in state_counts.items():
    pct = (num_contractors / len(oem_aggregated)) * 100
    print(f"  {int(count)} state(s): {num_contractors:>4} contractors ({pct:>5.1f}%)")

print()
multi_state = (oem_aggregated['state_count'] >= 2).sum()
print(f"✅ Multi-state contractors: {multi_state} ({multi_state/len(oem_aggregated)*100:.1f}%)")

# The holy grail: Multi-state + Multi-OEM
holy_grail = oem_aggregated[(oem_aggregated['state_count'] >= 2) & (oem_aggregated['OEM Count'] >= 2)]
print()
print(f"🔥 Multi-state + Multi-OEM: {len(holy_grail)} contractors")

# Show top multi-OEM contractors
print()
print("=" * 80)
print("TOP 10 MULTI-OEM CONTRACTORS")
print("=" * 80)
top_multi_oem = oem_aggregated[oem_aggregated['OEM Count'] >= 2].nlargest(10, 'OEM Count')

if len(top_multi_oem) > 0:
    for idx, row in top_multi_oem.iterrows():
        print(f"\n{row['Contractor Name']}")
        print(f"  OEM Count: {int(row['OEM Count'])} | States: {row['State']} ({int(row['state_count'])} state(s))")
        print(f"  OEM Sources: {row['OEM Sources']}")
        print(f"  Phone: {row['phone_normalized']}")
        print(f"  ICP Score: {row['ICP Fit Score']:.1f} | Multi-OEM Score: {row['Multi-OEM Score']:.0f}")
else:
    print("⚠️  No multi-OEM contractors found (all contractors have single OEM)")

print()
print(f"✅ Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print()
print("📊 Next Step: Re-run Phase 3 (icp_scoring_multi_state.py) using aggregated OEM master")
print("   This will enable proper PLATINUM tier detection for multi-OEM + multi-state contractors")
