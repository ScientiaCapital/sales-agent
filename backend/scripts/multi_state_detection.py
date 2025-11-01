"""
Multi-State Contractor Detection
Identifies contractors operating in both CA and TX
"""

import pandas as pd
from datetime import datetime

print("=" * 80)
print("MULTI-STATE CONTRACTOR DETECTION")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# File paths
ca_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/ca_cross_referenced_20251031.csv'
tx_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/tx_final_hottest_leads_20251031.csv'
output_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/multi_state_contractors.csv'

# Load enriched contractors
print("Loading CA enriched contractors...")
ca_df = pd.read_csv(ca_file)
print(f"✅ {len(ca_df)} CA contractors loaded")

print("Loading TX enriched contractors...")
tx_df = pd.read_csv(tx_file)
print(f"✅ {len(tx_df)} TX contractors loaded")
print()

# Add state flags
ca_df['has_ca'] = True
ca_df['state_ca'] = 'CA'
tx_df['has_tx'] = True
tx_df['state_tx'] = 'TX'

# Normalize TX phone column name
if 'phone' in tx_df.columns and 'phone_normalized' not in tx_df.columns:
    tx_df['phone_normalized'] = tx_df['phone']

# Convert phone_normalized to string for both dataframes (fix type mismatch)
ca_df['phone_normalized'] = ca_df['phone_normalized'].astype(str)
tx_df['phone_normalized'] = tx_df['phone_normalized'].astype(str)

# Merge on phone_normalized
print("Merging CA and TX contractors by phone number...")
multi_state = pd.merge(
    ca_df,
    tx_df[['phone_normalized', 'has_tx', 'name', 'license_number', 'oem_source', 'icp_score', 'tier']],
    on='phone_normalized',
    how='outer',
    suffixes=('_ca', '_tx')
)

# Fill missing state flags
multi_state['has_ca'] = multi_state['has_ca'].fillna(False)
multi_state['has_tx'] = multi_state['has_tx'].fillna(False)

# Calculate state count
multi_state['state_count'] = (
    multi_state['has_ca'].astype(int) +
    multi_state['has_tx'].astype(int)
)

# Create state list
def get_state_list(row):
    states = []
    if row['has_ca']:
        states.append('CA')
    if row['has_tx']:
        states.append('TX')
    return ','.join(states) if states else 'UNKNOWN'

multi_state['state_list'] = multi_state.apply(get_state_list, axis=1)

# Multi-state bonus (20 points per additional state)
multi_state['multi_state_bonus'] = (multi_state['state_count'] - 1) * 20
multi_state['multi_state_bonus'] = multi_state['multi_state_bonus'].clip(lower=0)

# Save
print("Saving multi-state contractor data...")
multi_state.to_csv(output_file, index=False)
print(f"✅ Saved: multi_state_contractors.csv ({len(multi_state)} total contractors)")
print()

# Statistics
print("=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
print(f"Total contractors (CA + TX combined): {len(multi_state)}")
print(f"CA only: {(multi_state['state_count'] == 1) & (multi_state['has_ca'] == True)}.sum()")
print(f"TX only: {((multi_state['state_count'] == 1) & (multi_state['has_tx'] == True)).sum()}")
print(f"Multi-state (CA + TX): {(multi_state['state_count'] >= 2).sum()}")
print()

# Show multi-state contractors
multi_state_only = multi_state[multi_state['state_count'] >= 2]
if len(multi_state_only) > 0:
    print(f"🔥 Multi-State Contractors (operate in both CA and TX):")
    print("-" * 80)
    for idx, row in multi_state_only.head(10).iterrows():
        name_ca = row.get('Contractor Name', row.get('name_ca', 'Unknown'))
        name_tx = row.get('name_tx', '')
        phone = row['phone_normalized']
        print(f"  {name_ca}")
        if name_tx and name_tx != name_ca:
            print(f"    (TX Name: {name_tx})")
        print(f"    Phone: {phone}")
        print(f"    States: {row['state_list']}")
        print()

print(f"✅ Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
