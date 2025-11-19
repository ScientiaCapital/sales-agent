"""
Import leads from dealer-scraper-mvp into sales-agent pipeline.

Transforms dealer-scraper column format to sales-agent format and
copies to inbox for processing.

Usage:
    python import_from_scraper.py [filename]
    python import_from_scraper.py top_100_mep_energy_prospects_20251119.csv
    python import_from_scraper.py --list  # Show available files
    python import_from_scraper.py --all   # Import all MEP files
"""

import pandas as pd
from pathlib import Path
import sys
import shutil
from datetime import datetime

# Paths
SCRAPER_OUTPUT = Path("/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output")
SALES_AGENT_INBOX = Path("data/csv/inbox")

# Column mapping: dealer-scraper → sales-agent
COLUMN_MAP = {
    "business_name": "name",
    "phone_normalized": "phone",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "contractor_id": "contractor_id",
    "license_classifications": "license_types",
    "license_count": "license_count",
    "tenure_years": "tenure_years",
    "coperniq_score": "coperniq_score",
    "icp_tier": "icp_tier",
    "has_electrical": "has_electrical",
    "has_hvac": "has_hvac",
    "has_solar": "has_solar",
    "has_plumbing": "has_plumbing",
    "is_multi_trade": "is_multi_trade",
    "oem_sources": "oem_sources",
    "oem_source_count": "OEM_Count",
    "rating": "rating",
    "review_count": "review_count",
    "composite_score": "composite_score",
}


def list_available_files():
    """Show available CSV files in dealer-scraper output."""
    print("=" * 60)
    print("AVAILABLE FILES IN DEALER-SCRAPER OUTPUT")
    print("=" * 60)

    csv_files = sorted(SCRAPER_OUTPUT.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in output directory")
        return

    for f in csv_files:
        size_kb = f.stat().st_size / 1024
        # Count records
        try:
            df = pd.read_csv(f)
            records = len(df)
        except:
            records = "?"

        print(f"  {f.name}")
        print(f"    → {records} records, {size_kb:.1f} KB")
        print()


def transform_scraper_to_agent(df: pd.DataFrame) -> pd.DataFrame:
    """Transform dealer-scraper columns to sales-agent format."""
    # Create new dataframe with mapped columns
    result = pd.DataFrame()

    for old_col, new_col in COLUMN_MAP.items():
        if old_col in df.columns:
            result[new_col] = df[old_col]

    # Preserve any extra columns (like composite_score variants)
    for col in df.columns:
        if col not in COLUMN_MAP and col not in result.columns:
            result[col] = df[col]

    # Clean phone numbers (remove .0 suffix from float conversion)
    if "phone" in result.columns:
        result["phone"] = result["phone"].apply(
            lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace(".", "").isdigit() else x
        )

    # Add empty website column (will be discovered by pipeline)
    if "website" not in result.columns:
        result["website"] = ""

    # Add empty email column (will be discovered by pipeline)
    if "email" not in result.columns:
        result["email"] = ""

    return result


def import_file(filename: str, force: bool = False):
    """Import a single file from dealer-scraper to sales-agent."""
    source = SCRAPER_OUTPUT / filename

    if not source.exists():
        print(f"❌ File not found: {source}")
        return False

    # Read and transform
    print(f"📂 Reading: {filename}")
    df = pd.read_csv(source)
    print(f"   → {len(df)} records")

    # Transform columns
    transformed = transform_scraper_to_agent(df)

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"scraper_import_{filename.replace('.csv', '')}_{timestamp}.csv"
    output_path = SALES_AGENT_INBOX / output_name

    # Check if already exists in inbox
    existing = list(SALES_AGENT_INBOX.glob(f"*{filename.replace('.csv', '')}*"))
    if existing and not force:
        print(f"   ⚠️  Similar file already in inbox: {existing[0].name}")
        print(f"   Use --force to import anyway")
        return False

    # Save to inbox
    transformed.to_csv(output_path, index=False)
    print(f"✅ Imported to: {output_path.name}")
    print(f"   → {len(transformed)} leads ready for pipeline")

    # Show sample
    print(f"\n   Sample columns: {list(transformed.columns)[:6]}...")

    return True


def import_all_mep():
    """Import all MEP files from today."""
    mep_files = [
        "top_100_mep_energy_prospects_20251119.csv",
        "license_oem_overlap_mep_20251119.csv",
        "mep_energy_contractors_20251119.csv",
        "established_mep_contractors_20251119.csv",
    ]

    print("=" * 60)
    print("IMPORTING ALL MEP FILES")
    print("=" * 60)

    success = 0
    for f in mep_files:
        if (SCRAPER_OUTPUT / f).exists():
            if import_file(f, force=True):
                success += 1
            print()

    print(f"\n✅ Imported {success}/{len(mep_files)} files")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    arg = sys.argv[1]

    if arg == "--list":
        list_available_files()
    elif arg == "--all":
        import_all_mep()
    elif arg == "--force" and len(sys.argv) > 2:
        import_file(sys.argv[2], force=True)
    else:
        import_file(arg)


if __name__ == "__main__":
    main()
