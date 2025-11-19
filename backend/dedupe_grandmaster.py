"""
Deduplicate grandmaster list against the 220 list we already ran.
"""

import pandas as pd
from pathlib import Path

# Paths
inbox = Path("data/csv/inbox")
grandmaster_path = inbox / "grandmaster_list_expanded_20251029.csv"
top200_path = inbox / "top_200_prospects_20251028.csv"
hvac_path = inbox / "hvac_contractors_20.csv"
output_path = inbox / "grandmaster_deduped.csv"

print("=" * 60)
print("DEDUPLICATING GRANDMASTER LIST")
print("=" * 60)

# Load grandmaster
gm = pd.read_csv(grandmaster_path)
print(f"\nGrandmaster list: {len(gm)} leads")

# Load already-processed lists
top200 = pd.read_csv(top200_path)
hvac = pd.read_csv(hvac_path)

print(f"Top 200: {len(top200)} leads")
print(f"HVAC 20: {len(hvac)} leads")

# Get company names we've already processed
# Normalize names for comparison
def normalize(name):
    if pd.isna(name):
        return ""
    return str(name).strip().lower().replace(".", "").replace(",", "").replace("  ", " ")

processed_names = set()

# Top 200 uses 'name' column
if 'name' in top200.columns:
    processed_names.update(top200['name'].apply(normalize))

# HVAC uses 'Company Name' column
if 'Company Name' in hvac.columns:
    processed_names.update(hvac['Company Name'].apply(normalize))

print(f"\nAlready processed: {len(processed_names)} unique company names")

# Normalize grandmaster names
gm['normalized_name'] = gm['name'].apply(normalize)

# Find duplicates
duplicates = gm[gm['normalized_name'].isin(processed_names)]
unique = gm[~gm['normalized_name'].isin(processed_names)]

print(f"\nDuplicates found: {len(duplicates)}")
print(f"New unique leads: {len(unique)}")

# Show some duplicates
if len(duplicates) > 0:
    print(f"\nSample duplicates (first 10):")
    for name in duplicates['name'].head(10):
        print(f"  - {name}")

# Save deduped list
unique = unique.drop(columns=['normalized_name'])
unique.to_csv(output_path, index=False)

print(f"\n✅ Saved deduped list: {output_path}")
print(f"   {len(unique)} leads ready to process")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
