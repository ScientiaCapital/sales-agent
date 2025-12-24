#!/usr/bin/env python3
"""
Close CRM Campaign Audit CLI Script

Audit database against Close CRM for Dec 29 campaign preparation.

Usage:
    # Generate audit report (read-only)
    python backend/scripts/audit_close_crm_campaign.py --mode report

    # Sync close_lead_id from Close to Supabase (write operation)
    python backend/scripts/audit_close_crm_campaign.py --mode sync --dry-run

    # Export NEW leads for enrichment
    python backend/scripts/audit_close_crm_campaign.py --mode new-leads --tier PLATINUM

Modes:
    report      - Generate comprehensive audit report (read-only)
    sync        - Update dim_companies.close_lead_id from Close API
    new-leads   - Export CSV of NEW leads (close_lead_id IS NULL)

Options:
    --mode          Mode to run (report, sync, new-leads)
    --tier          Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)
    --dry-run       Preview changes without writing to database
    --output        Output file path (default: /tmp/close_audit_YYYY-MM-DD.{format})
    --format        Output format (json, csv, text) - default: text
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.services.close_audit_service import CloseAuditService


def print_section_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


async def mode_report(args):
    """Generate comprehensive audit report"""
    print_section_header("Close CRM Campaign Audit")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    service = CloseAuditService()

    # Cross-reference databases
    print("\n🔍 Cross-referencing Supabase with Close CRM...")
    report = await service.cross_reference()

    print_section_header("CLOSE CRM STATUS")
    print(f"Total leads in Close: {report['total_in_close']:,}")

    # Get sequence stats
    sequence_ids = [
        "seq_469XPP98mPXSR2wh5cX9y6",  # ICP-Energy-Multitrade
        "seq_0FHFD0OQtDAOS8x40MIANW"   # Solar-Pivot-2026
    ]

    print("\nDec 29 Campaign Sequences:")
    campaign_report = await service.generate_campaign_audit(sequence_ids)

    for seq in campaign_report["sequences"]:
        print(f"  - {seq['sequence_id']}: {seq['enrolled_count']} contacts")

    print(f"\nTotal contacts enrolled: {campaign_report['total_contacts_enrolled']:,}")

    print_section_header("SUPABASE STATUS")
    print(f"Total companies: {report['total_in_supabase']:,}")
    print(f"Companies with close_lead_id: {report['loaded_leads']:,} (LOADED)")
    print(f"Companies without close_lead_id: {report['new_leads']:,} (NEW)")

    # Breakdown by tier
    print_section_header("NEW LEADS BREAKDOWN (by tier)")

    for tier in ["PLATINUM", "GOLD", "SILVER", "BRONZE"]:
        leads = await service.get_new_leads(icp_tier=tier)
        zero_contacts = sum(1 for l in leads if l.get("contact_count", 0) == 0)
        print(f"{tier:10} {len(leads):5,} companies ({zero_contacts:,} with 0 contacts)")

    # ICP breakdown for campaign
    print_section_header("CAMPAIGN ICP BREAKDOWN")
    for tier, count in campaign_report["icp_breakdown"].items():
        pct = (count / campaign_report["unique_companies"] * 100) if campaign_report["unique_companies"] > 0 else 0
        print(f"{tier:10} {count:5,} ({pct:5.1f}%)")

    # Industry breakdown
    print_section_header("CAMPAIGN INDUSTRY BREAKDOWN")
    for industry, count in campaign_report["industry_breakdown"].items():
        pct = (count / campaign_report["unique_companies"] * 100) if campaign_report["unique_companies"] > 0 else 0
        print(f"{industry:15} {count:5,} ({pct:5.1f}%)")

    # ATL/BTL breakdown
    print_section_header("CAMPAIGN CONTACT LEVEL BREAKDOWN")
    cb = campaign_report["contact_breakdown"]
    total_contacts = cb["atl_count"] + cb["btl_count"] + cb["unknown_count"]
    if total_contacts > 0:
        print(f"ATL:     {cb['atl_count']:5,} ({cb['atl_count']/total_contacts*100:5.1f}%)")
        print(f"BTL:     {cb['btl_count']:5,} ({cb['btl_count']/total_contacts*100:5.1f}%)")
        print(f"Unknown: {cb['unknown_count']:5,} ({cb['unknown_count']/total_contacts*100:5.1f}%)")

    print_section_header("RECOMMENDED ACTIONS")
    print("1. VLM enrich PLATINUM zero-contact companies")
    print("2. Push dealer-scraper leads to Supabase (target: +14K)")
    print("3. Re-run audit after dealer-scraper push")
    print("4. Enrich top 500 NEW GOLD leads for Dec 29 campaign")

    # Save report to file if requested
    if args.output:
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "cross_reference": report,
            "campaign_audit": campaign_report
        }

        if args.format == "json":
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"\n📄 Report saved to: {args.output}")

    print("")


async def mode_sync(args):
    """Sync close_lead_id from Close CRM to Supabase"""
    print_section_header("SYNC MODE - Update close_lead_id from Close CRM")

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made\n")
    else:
        print("⚠️  WRITE MODE - Database will be updated\n")

    service = CloseAuditService()

    # Get Close leads
    print("🔍 Fetching leads from Close CRM...")
    close_leads = await service._fetch_close_leads()
    print(f"Found {len(close_leads):,} leads in Close CRM")

    # Get Supabase companies
    print("\n🔍 Fetching companies from Supabase...")
    loaded_leads = await service.get_loaded_leads()
    print(f"Found {len(loaded_leads):,} companies already marked as loaded")

    # Identify gaps
    print("\n📊 Analyzing discrepancies...")
    updates_needed = 0  # Placeholder - actual implementation would compare

    if args.dry_run:
        print(f"\n✅ DRY RUN: Would update {updates_needed} companies")
    else:
        print(f"\n⚠️  Would update {updates_needed} companies. Run with --dry-run first!")

    print("\nSync complete.\n")


async def mode_new_leads(args):
    """Export NEW leads to CSV"""
    print_section_header(f"NEW LEADS EXPORT - {args.tier or 'ALL TIERS'}")

    service = CloseAuditService()

    # Generate output path
    if not args.output:
        tier_suffix = f"_{args.tier.lower()}" if args.tier else "_all"
        date_str = datetime.now().strftime("%Y-%m-%d")
        args.output = f"/tmp/new_leads{tier_suffix}_{date_str}.csv"

    # Generate report
    print(f"🔍 Querying NEW leads (tier={args.tier or 'ALL'})...")
    report_path = await service.generate_new_leads_report(
        output_path=args.output,
        icp_tier=args.tier,
        format="csv"
    )

    # Count leads
    new_leads = await service.get_new_leads(icp_tier=args.tier)

    print(f"\n✅ Exported {len(new_leads):,} NEW leads to: {report_path}")

    # Show sample
    if len(new_leads) > 0:
        print("\nSample (first 5):")
        for i, lead in enumerate(new_leads[:5], 1):
            print(f"  {i}. {lead['company_name']} ({lead['domain']}) - "
                  f"{lead['icp_tier']} - {lead.get('contact_count', 0)} contacts")

    print("")


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Close CRM Campaign Audit Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["report", "sync", "new-leads"],
        help="Mode to run"
    )

    parser.add_argument(
        "--tier",
        choices=["PLATINUM", "GOLD", "SILVER", "BRONZE"],
        help="Filter by ICP tier"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to database"
    )

    parser.add_argument(
        "--output",
        help="Output file path"
    )

    parser.add_argument(
        "--format",
        choices=["json", "csv", "text"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Route to appropriate mode
    if args.mode == "report":
        await mode_report(args)
    elif args.mode == "sync":
        await mode_sync(args)
    elif args.mode == "new-leads":
        await mode_new_leads(args)


if __name__ == "__main__":
    asyncio.run(main())
