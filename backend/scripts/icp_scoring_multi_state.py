"""
Multi-State ICP Scoring & PLATINUM Tier Extraction
Calculates final ICP scores and extracts top-tier contractors
"""

import pandas as pd
import re
from datetime import datetime

print("=" * 80)
print("MULTI-STATE ICP SCORING & PLATINUM EXTRACTION")
print("=" * 80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# File paths
multi_state_file = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses/multi_state_contractors.csv'
oem_master_file = '/Users/tmkipper/Desktop/tk_projects/gtm-engineer-journey/projects/dealer-scraper-mvp/output/gtm/executive_package_20251025/MASTER_CONTRACTOR_DATABASE_with_overlap.csv'
output_dir = '/Users/tmkipper/Desktop/tk_projects/sales-agent/data/licenses'

# Load multi-state data
print("Loading multi-state contractor data...")
multi_state_df = pd.read_csv(multi_state_file)
print(f"✅ {len(multi_state_df)} total contractors loaded (CA + TX combined)")

print("Loading OEM master database...")
oem_master = pd.read_csv(oem_master_file)
print(f"✅ {len(oem_master)} OEM contractors loaded")
print()

# Normalize phone in OEM master
def normalize_phone(phone):
    if pd.isna(phone):
        return None
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 11 and digits[0] == '1':
        return digits[1:]
    return digits if len(digits) == 10 else None

oem_master['phone_normalized'] = oem_master['Phone'].apply(normalize_phone)

# Join with OEM master to get OEM count
print("Enriching with OEM certification data...")
scored = multi_state_df.merge(
    oem_master[['phone_normalized', 'OEM Count', 'OEM Sources', 'is_multi_oem', 'oem_count_verified']],
    on='phone_normalized',
    how='left',
    suffixes=('', '_oem_master')
)

# Fill missing OEM data
scored['OEM Count'] = scored['OEM Count'].fillna(0).astype(int)
scored['is_multi_oem'] = scored['is_multi_oem'].fillna(False)
scored['oem_count_verified'] = scored['oem_count_verified'].fillna(0).astype(int)

print(f"✅ {len(scored)} contractors enriched with OEM data")
print()

# Calculate multi-OEM score (25 points per OEM, max 100)
print("Calculating ICP scores...")
scored['multi_oem_score'] = (scored['OEM Count'] * 25).clip(upper=100)

# Get base scores from CA or TX data
def get_base_score(row, field):
    """Get base score from CA or TX data, preferring CA"""
    ca_val = row.get(f'{field}_ca', 0)
    tx_val = row.get(f'{field}_tx', 0)

    # If both exist, take the average
    if pd.notna(ca_val) and pd.notna(tx_val) and ca_val > 0 and tx_val > 0:
        return (ca_val + tx_val) / 2
    # Otherwise take whichever is available
    elif pd.notna(ca_val) and ca_val > 0:
        return ca_val
    elif pd.notna(tx_val) and tx_val > 0:
        return tx_val
    else:
        return 0

# Extract base ICP dimensions
# For CA contractors, we don't have these scores yet, so we'll use conservative estimates
# For TX contractors, we can use their existing scores
scored['resimercial_score'] = scored.apply(
    lambda row: get_base_score(row, 'Resimercial Score') if 'Resimercial Score_ca' in scored.columns
    else row.get('Resimercial Score', 70),  # Default 70 for contractors with licenses
    axis=1
)
scored['om_score'] = scored.apply(
    lambda row: get_base_score(row, 'O&M Score') if 'O&M Score_ca' in scored.columns
    else row.get('O&M Score', 60),  # Default 60
    axis=1
)
scored['mepr_score'] = scored.apply(
    lambda row: get_base_score(row, 'MEP+R Score') if 'MEP+R Score_ca' in scored.columns
    else row.get('MEP+R Score', 0),  # Will calculate from license data
    axis=1
)

# Calculate MEP+R score from license data (multi-license = MEP+R capability)
# If contractor has multi-license pattern, give 80 points
def calculate_mepr_from_license(row):
    """Calculate MEP+R score from license classifications"""
    classification = row.get('Classifications(s)', '')
    if pd.isna(classification):
        return row.get('mepr_score', 0)

    classification_str = str(classification)
    multi_license_patterns = ['B|', 'A|', '|B', '|A', 'B |', 'A |', 'C10|', 'C20|', '|C10', '|C20']

    for pattern in multi_license_patterns:
        if pattern in classification_str:
            return 80  # Strong MEP+R capability

    return row.get('mepr_score', 40)  # Single-trade capability

scored['mepr_score'] = scored.apply(calculate_mepr_from_license, axis=1)

# Calculate final ICP score with proper weights
# Formula: (resimercial * 0.35) + (multi_oem * 0.25) + (mepr * 0.25) + (om * 0.15) + (multi_state_bonus * 0.10)
scored['icp_score'] = (
    (scored['resimercial_score'] * 0.35) +
    (scored['multi_oem_score'] * 0.25) +
    (scored['mepr_score'] * 0.25) +
    (scored['om_score'] * 0.15) +
    (scored['multi_state_bonus'] * 0.10)
)

# Assign tiers
def assign_tier(score):
    if score >= 80:
        return 'PLATINUM'
    elif score >= 60:
        return 'GOLD'
    elif score >= 40:
        return 'SILVER'
    else:
        return 'BRONZE'

scored['tier'] = scored['icp_score'].apply(assign_tier)

print(f"✅ ICP scores calculated")
print()

# Save outputs
print("Saving results...")

# Output 1: All scored contractors
output_all = f'{output_dir}/ca_tx_icp_scored_20251031.csv'
scored.to_csv(output_all, index=False)
print(f"✅ Saved: ca_tx_icp_scored_20251031.csv ({len(scored)} contractors)")

# Output 2: PLATINUM tier only
platinum = scored[scored['tier'] == 'PLATINUM'].copy()
platinum_sorted = platinum.sort_values('icp_score', ascending=False)
output_platinum = f'{output_dir}/platinum_contractors_20251031.csv'
platinum_sorted.to_csv(output_platinum, index=False)
print(f"✅ Saved: platinum_contractors_20251031.csv ({len(platinum_sorted)} contractors)")

# Output 3: GOLD tier only
gold = scored[scored['tier'] == 'GOLD'].copy()
gold_sorted = gold.sort_values('icp_score', ascending=False)
output_gold = f'{output_dir}/gold_contractors_20251031.csv'
gold_sorted.to_csv(output_gold, index=False)
print(f"✅ Saved: gold_contractors_20251031.csv ({len(gold_sorted)} contractors)")

print()

# Statistics
print("=" * 80)
print("FINAL RESULTS SUMMARY")
print("=" * 80)
print()

# Tier breakdown
tier_counts = scored['tier'].value_counts()
print("Tier Distribution:")
print("-" * 80)
for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE']:
    count = tier_counts.get(tier, 0)
    pct = (count / len(scored)) * 100
    print(f"  {tier:<10} {count:>4} contractors ({pct:>5.1f}%)")
print()

# Multi-state analysis
multi_state_count = (scored['state_count'] >= 2).sum()
multi_state_pct = (multi_state_count / len(scored)) * 100
print(f"Multi-state contractors: {multi_state_count} ({multi_state_pct:.1f}%)")

# Multi-OEM analysis
multi_oem_count = (scored['OEM Count'] >= 2).sum()
multi_oem_pct = (multi_oem_count / len(scored)) * 100
print(f"Multi-OEM contractors:   {multi_oem_count} ({multi_oem_pct:.1f}%)")

# The holy grail: Multi-state + Multi-OEM
holy_grail = scored[(scored['state_count'] >= 2) & (scored['OEM Count'] >= 2)]
print(f"Multi-state + Multi-OEM: {len(holy_grail)} contractors 🔥")
print()

# Show PLATINUM tier contractors
if len(platinum_sorted) > 0:
    print("=" * 80)
    print("🏆 PLATINUM TIER CONTRACTORS (ICP Score 80+)")
    print("=" * 80)
    print()

    for idx, row in platinum_sorted.head(10).iterrows():
        # Get name from CA or TX
        name = row.get('Contractor Name', row.get('name_ca', row.get('name_tx', 'Unknown')))
        phone = row['phone_normalized']
        icp_score = row['icp_score']
        oem_count = row['OEM Count']
        state_list = row['state_list']
        license = row.get('Classifications(s)', row.get('license_type', 'Unknown'))

        print(f"  {name}")
        print(f"    ICP Score: {icp_score:.1f} | States: {state_list} | OEMs: {int(oem_count)}")
        print(f"    Phone: {phone} | License: {license}")

        # Show dimension breakdown
        print(f"    Breakdown: Resi/Commercial={row['resimercial_score']:.0f} | " +
              f"Multi-OEM={row['multi_oem_score']:.0f} | " +
              f"MEP+R={row['mepr_score']:.0f} | " +
              f"O&M={row['om_score']:.0f} | " +
              f"Multi-State Bonus={row['multi_state_bonus']:.0f}")
        print()
else:
    print("⚠️  No PLATINUM tier contractors found")
    print("Showing top 10 contractors by ICP score:")
    print("-" * 80)
    top_10 = scored.nlargest(10, 'icp_score')
    for idx, row in top_10.iterrows():
        name = row.get('Contractor Name', row.get('name_ca', row.get('name_tx', 'Unknown')))
        icp_score = row['icp_score']
        tier = row['tier']
        print(f"  {name}: {icp_score:.1f} ({tier})")

print()
print(f"✅ Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
