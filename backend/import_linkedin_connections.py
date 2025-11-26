#!/usr/bin/env python3
"""
LinkedIn Connections CSV Importer

Imports contacts from LinkedIn's "Download your data" export and processes them
through the sales-agent pipeline for contractor/solar lead enrichment.

LinkedIn CSV Format (Connections.csv):
    First Name, Last Name, Email Address, Company, Position, Connected On

Usage:
    # Import all connections
    python import_linkedin_connections.py Connections.csv

    # Filter for contractors only
    python import_linkedin_connections.py Connections.csv --contractors-only

    # Dry run (no enrichment, just preview)
    python import_linkedin_connections.py Connections.csv --dry-run

    # Output to specific file
    python import_linkedin_connections.py Connections.csv -o my_leads.csv

Author: Claude Code
Date: November 26, 2025
"""

import argparse
import csv
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# CONTRACTOR/SOLAR KEYWORD FILTERS
# =============================================================================

# Industries we want to target
TARGET_INDUSTRIES = {
    # HVAC & Mechanical
    "hvac", "heating", "cooling", "air conditioning", "mechanical", "plumbing",
    "refrigeration", "ventilation", "climate control", "furnace", "boiler",

    # Electrical
    "electrical", "electrician", "power", "wiring", "lighting",

    # Solar & Renewable
    "solar", "renewable", "photovoltaic", "pv", "energy", "green energy",
    "clean energy", "sustainable", "ev charging", "battery storage",

    # Construction & Contracting
    "contractor", "contracting", "construction", "building", "remodeling",
    "renovation", "home improvement", "general contractor",

    # MEP (Mechanical, Electrical, Plumbing)
    "mep", "mechanical electrical", "building systems", "facility",

    # Roofing (often does solar)
    "roofing", "roof", "rooftop",

    # Specific trades
    "sheet metal", "pipefitting", "insulation", "ductwork",
}

# ATL (Above The Line) titles - decision makers
ATL_TITLES = {
    "owner", "ceo", "president", "founder", "co-founder", "partner",
    "principal", "director", "vp", "vice president", "head of",
    "general manager", "gm", "managing director", "chief",
    "executive", "manager",  # manager is borderline but often decision-maker in SMBs
}

# Titles to EXCLUDE (BTL or irrelevant)
EXCLUDE_TITLES = {
    "intern", "student", "retired", "freelance", "consultant",
    "sales rep", "sales representative", "account executive",  # They sell TO contractors
    "recruiter", "hr", "human resources",
    "marketing", "social media",
}

# OEM/Manufacturer keywords to exclude (they're suppliers, not customers)
OEM_KEYWORDS = {
    "trane", "carrier", "lennox", "rheem", "goodman", "daikin", "york",
    "mitsubishi", "fujitsu", "lg", "samsung", "bosch", "honeywell",
    "schneider", "siemens", "eaton", "solaredge", "enphase", "tesla",
    "generac", "kohler", "moen", "delta",
}


# =============================================================================
# LINKEDIN CSV PARSER
# =============================================================================

def parse_linkedin_csv(filepath: str) -> List[Dict]:
    """
    Parse LinkedIn Connections.csv export file.

    Args:
        filepath: Path to Connections.csv

    Returns:
        List of connection dicts with normalized keys
    """
    connections = []

    # LinkedIn uses different column names sometimes
    column_mappings = {
        "first name": "first_name",
        "last name": "last_name",
        "email address": "email",
        "email": "email",
        "company": "company",
        "position": "position",
        "title": "position",
        "connected on": "connected_on",
        "connection date": "connected_on",
    }

    with open(filepath, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
        # Detect delimiter (LinkedIn sometimes uses different ones)
        sample = f.read(4096)
        f.seek(0)

        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        reader = csv.DictReader(f, dialect=dialect)

        # Normalize column names
        if reader.fieldnames:
            normalized_fields = {}
            for field in reader.fieldnames:
                key = field.lower().strip()
                if key in column_mappings:
                    normalized_fields[field] = column_mappings[key]
                else:
                    normalized_fields[field] = key.replace(' ', '_')

        for row in reader:
            # Normalize the row
            normalized = {}
            for orig_key, value in row.items():
                new_key = normalized_fields.get(orig_key, orig_key.lower().replace(' ', '_'))
                normalized[new_key] = value.strip() if value else ""

            # Skip empty rows
            if not normalized.get('first_name') and not normalized.get('company'):
                continue

            connections.append(normalized)

    return connections


def is_contractor_related(connection: Dict) -> Tuple[bool, str]:
    """
    Check if a connection is in a contractor/solar-related industry.

    Args:
        connection: Parsed connection dict

    Returns:
        Tuple of (is_match, reason)
    """
    company = connection.get('company', '').lower()
    position = connection.get('position', '').lower()

    # Check for OEM exclusions first
    for oem in OEM_KEYWORDS:
        if oem in company:
            return False, f"OEM/Manufacturer: {oem}"

    # Check company name for target industries
    for keyword in TARGET_INDUSTRIES:
        if keyword in company:
            return True, f"Company matches: {keyword}"

    # Check position for target industries
    for keyword in TARGET_INDUSTRIES:
        if keyword in position:
            return True, f"Position matches: {keyword}"

    return False, "No industry match"


def is_atl_contact(connection: Dict) -> Tuple[bool, str]:
    """
    Check if contact is Above The Line (decision maker).

    Args:
        connection: Parsed connection dict

    Returns:
        Tuple of (is_atl, reason)
    """
    position = connection.get('position', '').lower()

    # Check for exclusions first
    for exclude in EXCLUDE_TITLES:
        if exclude in position:
            return False, f"Excluded title: {exclude}"

    # Check for ATL titles
    for title in ATL_TITLES:
        if title in position:
            return True, f"ATL title: {title}"

    return False, "No ATL title match"


def format_for_pipeline(connection: Dict, is_atl: bool) -> Dict:
    """
    Format a LinkedIn connection for the sales-agent pipeline.

    Args:
        connection: Parsed connection dict
        is_atl: Whether contact is ATL

    Returns:
        Dict formatted for pipeline import
    """
    first_name = connection.get('first_name', '')
    last_name = connection.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()

    return {
        "company_name": connection.get('company', ''),
        "contact_name": full_name,
        "contact_title": connection.get('position', ''),
        "email": connection.get('email', ''),
        "phone": "",  # LinkedIn doesn't export phone
        "website": "",  # Will be discovered by pipeline
        "source": "linkedin_connections",
        "is_atl": is_atl,
        "linkedin_connected_on": connection.get('connected_on', ''),
        "notes": f"LinkedIn connection: {full_name} - {connection.get('position', '')}",
    }


# =============================================================================
# MAIN IMPORTER
# =============================================================================

def import_linkedin_connections(
    filepath: str,
    contractors_only: bool = True,
    atl_only: bool = False,
    dry_run: bool = False,
    output_file: Optional[str] = None,
) -> Dict:
    """
    Import LinkedIn connections and prepare for pipeline processing.

    Args:
        filepath: Path to Connections.csv
        contractors_only: Only include contractor-related industries
        atl_only: Only include ATL contacts
        dry_run: Preview without writing output
        output_file: Custom output filename

    Returns:
        Summary dict with stats
    """
    print(f"\n{'='*60}")
    print("LinkedIn Connections Importer")
    print(f"{'='*60}\n")

    # Parse the CSV
    print(f"Reading: {filepath}")
    connections = parse_linkedin_csv(filepath)
    print(f"Found {len(connections)} total connections\n")

    # Filter and classify
    results = {
        "total": len(connections),
        "contractors": 0,
        "non_contractors": 0,
        "atl": 0,
        "btl": 0,
        "has_email": 0,
        "no_email": 0,
        "included": [],
        "excluded": [],
    }

    for conn in connections:
        # Check if contractor-related
        is_contractor, contractor_reason = is_contractor_related(conn)

        if contractors_only and not is_contractor:
            results["non_contractors"] += 1
            results["excluded"].append({
                **conn,
                "exclude_reason": contractor_reason
            })
            continue

        results["contractors"] += 1

        # Check ATL status
        is_atl, atl_reason = is_atl_contact(conn)

        if atl_only and not is_atl:
            results["btl"] += 1
            results["excluded"].append({
                **conn,
                "exclude_reason": atl_reason
            })
            continue

        if is_atl:
            results["atl"] += 1
        else:
            results["btl"] += 1

        # Track email availability
        if conn.get('email'):
            results["has_email"] += 1
        else:
            results["no_email"] += 1

        # Format for pipeline
        formatted = format_for_pipeline(conn, is_atl)
        formatted["contractor_reason"] = contractor_reason
        formatted["atl_reason"] = atl_reason
        results["included"].append(formatted)

    # Print summary
    print("="*60)
    print("FILTERING SUMMARY")
    print("="*60)
    print(f"Total connections:     {results['total']}")
    print(f"Contractor-related:    {results['contractors']}")
    print(f"Non-contractors:       {results['non_contractors']}")
    print(f"ATL contacts:          {results['atl']}")
    print(f"BTL contacts:          {results['btl']}")
    print(f"Has email:             {results['has_email']}")
    print(f"Missing email:         {results['no_email']}")
    print(f"Included for import:   {len(results['included'])}")
    print("="*60)

    if dry_run:
        print("\n[DRY RUN] No output file created")

        # Show sample of included
        if results["included"]:
            print("\nSample of contacts to import:")
            for contact in results["included"][:5]:
                print(f"  - {contact['contact_name']} @ {contact['company_name']}")
                print(f"    Position: {contact['contact_title']}")
                print(f"    ATL: {contact['is_atl']} | Email: {contact['email'] or 'N/A'}")
                print()

        return results

    # Write output CSV
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/csv/inbox/linkedin_connections_{timestamp}.csv"

    # Ensure directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if results["included"]:
        fieldnames = [
            "company_name", "contact_name", "contact_title", "email", "phone",
            "website", "source", "is_atl", "linkedin_connected_on", "notes"
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results["included"])

        print(f"\nOutput written to: {output_file}")
        print(f"Ready for pipeline: python import_mep_batch.py {output_file}")
    else:
        print("\nNo contacts matched filters - no output file created")

    return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import LinkedIn connections for contractor lead enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s Connections.csv                    # Import contractor connections
  %(prog)s Connections.csv --all              # Import ALL connections (no filter)
  %(prog)s Connections.csv --atl-only         # Only ATL decision makers
  %(prog)s Connections.csv --dry-run          # Preview without creating output
  %(prog)s Connections.csv -o leads.csv       # Custom output filename
        """
    )

    parser.add_argument(
        "csv_file",
        help="Path to LinkedIn Connections.csv export"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Import all connections (disable contractor filter)"
    )
    parser.add_argument(
        "--atl-only",
        action="store_true",
        help="Only include ATL (decision maker) contacts"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview results without creating output file"
    )
    parser.add_argument(
        "--output", "-o",
        help="Custom output filename"
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.csv_file):
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Run import
    results = import_linkedin_connections(
        filepath=args.csv_file,
        contractors_only=not args.all,
        atl_only=args.atl_only,
        dry_run=args.dry_run,
        output_file=args.output,
    )

    # Exit code based on results
    if results["included"]:
        sys.exit(0)
    else:
        print("\nNo contacts matched filters")
        sys.exit(1)


if __name__ == "__main__":
    main()
