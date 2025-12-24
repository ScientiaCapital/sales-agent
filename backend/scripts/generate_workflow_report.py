#!/usr/bin/env python3
"""
Close CRM Workflow Intelligence Report Generator

Generate comprehensive analytics reports for Close CRM sequences/workflows.
Since Close doesn't provide built-in analytics endpoints, this aggregates
data from Close API subscriptions + Supabase enrichment.

Usage:
    # All sequences for tim@coperniq.io
    python backend/scripts/generate_workflow_report.py --user tim@coperniq.io

    # Specific sequence
    python backend/scripts/generate_workflow_report.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6

    # Export to JSON
    python backend/scripts/generate_workflow_report.py --user tim@coperniq.io --format json --output /tmp/workflows.json

    # Export to CSV
    python backend/scripts/generate_workflow_report.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6 --format csv

    # Export to HTML dashboard
    python backend/scripts/generate_workflow_report.py --user tim@coperniq.io --format html

Options:
    --user              Filter sequences by user email (e.g., tim@coperniq.io)
    --sequence-id       Generate report for specific sequence ID
    --format            Output format: text (default), json, csv, html
    --output            Output file path (default: stdout or /tmp/workflow_report.{format})
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.services.workflow_intelligence import (
    WorkflowIntelligenceService,
    WorkflowReport
)


def print_section_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")


def format_percentage(count: int, total: int) -> str:
    """Format count with percentage"""
    if total == 0:
        return f"{count:,} (0.0%)"
    pct = (count / total * 100)
    return f"{count:,} ({pct:.1f}%)"


def print_text_report(report: WorkflowReport):
    """Print report in human-readable text format"""
    print_section_header(f"SEQUENCE: {report.sequence_name} ({report.sequence_id})")

    print(f"Total Enrolled: {report.total_enrolled:,} contacts\n")

    # Status breakdown
    print("STATUS BREAKDOWN:")
    for status, count in sorted(report.status_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {status.capitalize():12} {format_percentage(count, report.total_enrolled)}")

    # ICP tier breakdown
    print("\nICP TIER BREAKDOWN:")
    tier_order = ["PLATINUM", "GOLD", "SILVER", "BRONZE", "UNKNOWN"]
    for tier in tier_order:
        count = report.icp_breakdown.get(tier, 0)
        if count > 0:
            print(f"  {tier:12} {format_percentage(count, report.total_enrolled)}")

    # Industry breakdown
    print("\nINDUSTRY BREAKDOWN:")
    for industry, count in sorted(report.industry_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {industry:15} {format_percentage(count, report.total_enrolled)}")

    # ATL vs BTL
    print("\nCONTACT LEVEL:")
    cb = report.contact_breakdown
    total_contacts = cb["atl_count"] + cb["btl_count"] + cb["unknown_count"]
    if total_contacts > 0:
        print(f"  ATL:     {format_percentage(cb['atl_count'], total_contacts)}")
        print(f"  BTL:     {format_percentage(cb['btl_count'], total_contacts)}")
        print(f"  Unknown: {format_percentage(cb['unknown_count'], total_contacts)}")

    # Engagement metrics
    print("\nENGAGEMENT:")
    eng = report.engagement
    print(f"  Emails Sent:      {eng.total_emails_sent:,}")
    print(f"  Replies Received: {eng.total_replies:,}")
    print(f"  Reply Rate:       {eng.reply_rate:.1f}%")
    if eng.avg_steps_completed > 0:
        print(f"  Avg Steps/Contact: {eng.avg_steps_completed:.1f}")

    print("")


def export_json(reports: List[WorkflowReport], output_path: str, service: WorkflowIntelligenceService):
    """Export reports to JSON file"""
    data = {
        "generated_at": datetime.now().isoformat(),
        "workflows": [service.to_dict(r) for r in reports]
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Exported {len(reports)} workflow reports to: {output_path}\n")


def export_csv(reports: List[WorkflowReport], output_path: str):
    """Export reports to CSV file"""
    import pandas as pd

    rows = []
    for report in reports:
        # Flatten report to single row
        row = {
            "sequence_id": report.sequence_id,
            "sequence_name": report.sequence_name,
            "total_enrolled": report.total_enrolled,
            **{f"status_{k}": v for k, v in report.status_breakdown.items()},
            **{f"tier_{k}": v for k, v in report.icp_breakdown.items()},
            **{f"industry_{k}": v for k, v in report.industry_breakdown.items()},
            "atl_count": report.contact_breakdown["atl_count"],
            "btl_count": report.contact_breakdown["btl_count"],
            "emails_sent": report.engagement.total_emails_sent,
            "replies": report.engagement.total_replies,
            "reply_rate": report.engagement.reply_rate
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)

    print(f"✅ Exported {len(reports)} workflow reports to: {output_path}\n")


def export_html(reports: List[WorkflowReport], output_path: str):
    """Export reports to HTML dashboard"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Workflow Intelligence Report - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .workflow {{
            background: white;
            border-radius: 8px;
            padding: 24px;
            margin: 24px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .workflow h2 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .metric {{
            display: inline-block;
            margin: 12px 24px 12px 0;
        }}
        .metric-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .breakdown {{
            margin: 20px 0;
        }}
        .breakdown h3 {{
            color: #34495e;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        .bar {{
            display: flex;
            align-items: center;
            margin: 8px 0;
        }}
        .bar-label {{
            width: 120px;
            font-size: 14px;
            color: #2c3e50;
        }}
        .bar-viz {{
            flex: 1;
            height: 24px;
            background: #3498db;
            border-radius: 4px;
            position: relative;
        }}
        .bar-value {{
            margin-left: 12px;
            font-size: 14px;
            color: #7f8c8d;
            min-width: 80px;
        }}
    </style>
</head>
<body>
    <h1>🔍 Workflow Intelligence Report</h1>
    <p style="color: #7f8c8d;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""

    for report in reports:
        total = report.total_enrolled

        html += f"""
    <div class="workflow">
        <h2>{report.sequence_name}</h2>
        <p style="color: #7f8c8d; font-family: monospace;">{report.sequence_id}</p>

        <div class="metric">
            <div class="metric-label">Total Enrolled</div>
            <div class="metric-value">{total:,}</div>
        </div>

        <div class="metric">
            <div class="metric-label">Reply Rate</div>
            <div class="metric-value">{report.engagement.reply_rate:.1f}%</div>
        </div>

        <div class="breakdown">
            <h3>ICP Tier Breakdown</h3>
"""

        for tier in ["PLATINUM", "GOLD", "SILVER", "BRONZE"]:
            count = report.icp_breakdown.get(tier, 0)
            if count > 0:
                pct = (count / total * 100) if total > 0 else 0
                width = pct
                html += f"""
            <div class="bar">
                <div class="bar-label">{tier}</div>
                <div class="bar-viz" style="width: {width}%;"></div>
                <div class="bar-value">{count:,} ({pct:.1f}%)</div>
            </div>
"""

        html += """
        </div>

        <div class="breakdown">
            <h3>Contact Level</h3>
"""

        cb = report.contact_breakdown
        total_contacts = cb["atl_count"] + cb["btl_count"] + cb["unknown_count"]
        if total_contacts > 0:
            for label, count_key in [("ATL", "atl_count"), ("BTL", "btl_count")]:
                count = cb[count_key]
                pct = (count / total_contacts * 100)
                width = pct
                html += f"""
            <div class="bar">
                <div class="bar-label">{label}</div>
                <div class="bar-viz" style="width: {width}%;"></div>
                <div class="bar-value">{count:,} ({pct:.1f}%)</div>
            </div>
"""

        html += """
        </div>
    </div>
"""

    html += """
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"✅ Exported HTML dashboard to: {output_path}\n")


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Close CRM Workflow Intelligence Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--user",
        help="Filter sequences by user email (e.g., tim@coperniq.io)"
    )

    parser.add_argument(
        "--sequence-id",
        help="Generate report for specific sequence ID"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json", "csv", "html"],
        default="text",
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--output",
        help="Output file path (default: stdout or /tmp/workflow_report.{format})"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.user and not args.sequence_id:
        parser.error("Either --user or --sequence-id is required")

    # Initialize service
    print("🔍 Initializing Workflow Intelligence Service...\n")
    service = WorkflowIntelligenceService()

    # Generate reports
    reports = []

    if args.sequence_id:
        # Single sequence report
        print(f"📊 Generating report for sequence: {args.sequence_id}\n")
        report = await service.generate_workflow_report(args.sequence_id)
        reports = [report]
    else:
        # All sequences for user
        print(f"📊 Generating reports for user: {args.user}\n")
        reports = await service.generate_all_workflows_report(args.user)

    # Output reports
    if args.format == "text":
        # Print to stdout
        print_section_header(f"Workflow Intelligence Report")
        print(f"User: {args.user or 'N/A'}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")

        for report in reports:
            print_text_report(report)

    elif args.format == "json":
        output_path = args.output or f"/tmp/workflow_report_{datetime.now().strftime('%Y%m%d')}.json"
        export_json(reports, output_path, service)

    elif args.format == "csv":
        output_path = args.output or f"/tmp/workflow_report_{datetime.now().strftime('%Y%m%d')}.csv"
        export_csv(reports, output_path)

    elif args.format == "html":
        output_path = args.output or f"/tmp/workflow_report_{datetime.now().strftime('%Y%m%d')}.html"
        export_html(reports, output_path)


if __name__ == "__main__":
    asyncio.run(main())
