#!/usr/bin/env python3
"""
Investor Value Report Generator

Generates audit trail showing:
1. Coperniq Baseline: Data from Close CRM (source_type = 'close_crm')
2. Value-Add: Enrichment from dealer-scraper, apollo, hunter-io, etc.

Usage:
    python generate_investor_report.py
    python generate_investor_report.py --json  # Output as JSON
"""

import os
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def get_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def get_company_counts(client: httpx.AsyncClient) -> Dict[str, int]:
    """Get company counts by source type."""
    # Paginate to get all companies
    companies = []
    offset = 0
    batch_size = 1000

    while True:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/dim_companies",
            headers=get_headers(),
            params={
                "select": "source_type,icp_tier,current_stage,close_lead_id",
                "offset": offset,
                "limit": batch_size
            },
            timeout=60.0
        )

        if response.status_code != 200:
            return {"error": f"Failed to fetch companies: {response.status_code}"}

        batch = response.json()
        if not batch:
            break

        companies.extend(batch)
        offset += len(batch)

        if len(batch) < batch_size:
            break

    # Count by source
    by_source = {}
    by_tier = {}
    by_stage = {}
    close_linked = 0

    for c in companies:
        src = c.get("source_type") or "unknown"
        tier = c.get("icp_tier") or "unknown"
        stage = c.get("current_stage") or "unknown"

        by_source[src] = by_source.get(src, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_stage[stage] = by_stage.get(stage, 0) + 1

        if c.get("close_lead_id"):
            close_linked += 1

    return {
        "total": len(companies),
        "by_source": by_source,
        "by_tier": by_tier,
        "by_stage": by_stage,
        "close_linked": close_linked
    }


async def get_contact_counts(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Get contact counts by source and ATL status."""
    # Paginate to get all contacts
    contacts = []
    offset = 0
    batch_size = 1000

    while True:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/dim_contacts",
            headers=get_headers(),
            params={
                "select": "source,is_atl,title,email,phone",
                "offset": offset,
                "limit": batch_size
            },
            timeout=60.0
        )

        if response.status_code != 200:
            return {"error": f"Failed to fetch contacts: {response.status_code}"}

        batch = response.json()
        if not batch:
            break

        contacts.extend(batch)
        offset += len(batch)

        if len(batch) < batch_size:
            break

    by_source = {}
    atl_count = 0
    btl_count = 0
    with_email = 0
    with_phone = 0

    for c in contacts:
        src = c.get("source") or "unknown"
        by_source[src] = by_source.get(src, 0) + 1

        if c.get("is_atl"):
            atl_count += 1
        else:
            btl_count += 1

        if c.get("email"):
            with_email += 1
        if c.get("phone"):
            with_phone += 1

    return {
        "total": len(contacts),
        "by_source": by_source,
        "atl_count": atl_count,
        "btl_count": btl_count,
        "with_email": with_email,
        "with_phone": with_phone
    }


async def get_enrichment_stats(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Get enrichment activity stats."""
    response = await client.get(
        f"{SUPABASE_URL}/rest/v1/fact_enrichments",
        headers=get_headers(),
        params={"select": "method,contacts_found,atl_found,emails_found,cost_usd,success", "limit": 10000},
        timeout=60.0
    )

    if response.status_code != 200:
        return {"error": f"Failed to fetch enrichments: {response.status_code}"}

    enrichments = response.json()

    by_method = {}
    total_contacts = 0
    total_atl = 0
    total_emails = 0
    total_cost = 0.0
    success_count = 0

    for e in enrichments:
        method = e.get("method") or "unknown"
        by_method[method] = by_method.get(method, 0) + 1

        total_contacts += e.get("contacts_found") or 0
        total_atl += e.get("atl_found") or 0
        total_emails += e.get("emails_found") or 0
        total_cost += float(e.get("cost_usd") or 0)

        if e.get("success"):
            success_count += 1

    return {
        "total_runs": len(enrichments),
        "by_method": by_method,
        "total_contacts_found": total_contacts,
        "total_atl_found": total_atl,
        "total_emails_found": total_emails,
        "total_cost_usd": round(total_cost, 2),
        "success_rate": f"{(success_count / len(enrichments) * 100):.1f}%" if enrichments else "N/A"
    }


async def generate_report() -> Dict[str, Any]:
    """Generate the full investor report."""
    async with httpx.AsyncClient() as client:
        companies = await get_company_counts(client)
        contacts = await get_contact_counts(client)
        enrichments = await get_enrichment_stats(client)

    # Calculate value-add metrics
    coperniq_baseline = companies.get("by_source", {}).get("close_crm", 0)
    value_add_companies = companies.get("total", 0) - coperniq_baseline

    close_contacts = contacts.get("by_source", {}).get("close_crm", 0)
    value_add_contacts = contacts.get("total", 0) - close_contacts

    report = {
        "report_date": datetime.now().isoformat(),
        "report_title": "Sales-Agent: Investor Value Report",

        "summary": {
            "coperniq_baseline_companies": coperniq_baseline,
            "value_add_companies": value_add_companies,
            "total_companies": companies.get("total", 0),
            "value_add_percentage": f"{(value_add_companies / companies.get('total', 1) * 100):.1f}%" if companies.get("total") else "N/A",

            "coperniq_baseline_contacts": close_contacts,
            "value_add_contacts": value_add_contacts,
            "total_contacts": contacts.get("total", 0),

            "atl_contacts_discovered": contacts.get("atl_count", 0),
            "contacts_with_email": contacts.get("with_email", 0),
            "contacts_with_phone": contacts.get("with_phone", 0),
        },

        "companies": companies,
        "contacts": contacts,
        "enrichments": enrichments,

        "value_attribution": {
            "coperniq_provided": {
                "companies": coperniq_baseline,
                "description": "Leads imported from Close CRM (Coperniq's existing data)"
            },
            "sales_agent_added": {
                "companies": value_add_companies,
                "contacts": value_add_contacts,
                "atl_discovered": contacts.get("atl_count", 0),
                "description": "New leads and contacts discovered through enrichment pipeline"
            },
            "sources": {
                "close_crm": "Coperniq baseline data",
                "dealer-scraper": "Web scraping of dealer directories",
                "apollo": "Apollo.io contact enrichment",
                "hunter-io": "Hunter.io email discovery",
                "browserbase": "LinkedIn profile scraping",
                "manual-import": "Manual list imports"
            }
        }
    }

    return report


def print_report(report: Dict[str, Any]):
    """Print formatted report to console."""
    print("=" * 70)
    print("SALES-AGENT: INVESTOR VALUE REPORT")
    print("=" * 70)
    print(f"Generated: {report['report_date']}")
    print()

    summary = report["summary"]
    print("EXECUTIVE SUMMARY")
    print("-" * 40)
    print(f"Total Companies:       {summary['total_companies']:,}")
    print(f"  - Coperniq Baseline: {summary['coperniq_baseline_companies']:,}")
    print(f"  - Value-Add:         {summary['value_add_companies']:,} ({summary['value_add_percentage']})")
    print()
    print(f"Total Contacts:        {summary['total_contacts']:,}")
    print(f"  - Coperniq Baseline: {summary['coperniq_baseline_contacts']:,}")
    print(f"  - Value-Add:         {summary['value_add_contacts']:,}")
    print()
    print(f"ATL Contacts Found:    {summary['atl_contacts_discovered']:,}")
    print(f"Contacts with Email:   {summary['contacts_with_email']:,}")
    print(f"Contacts with Phone:   {summary['contacts_with_phone']:,}")
    print()

    print("COMPANIES BY SOURCE")
    print("-" * 40)
    for src, count in sorted(report["companies"]["by_source"].items(), key=lambda x: -x[1]):
        indicator = "(Coperniq)" if src == "close_crm" else "(Value-Add)"
        print(f"  {src:20} {count:6,} {indicator}")
    print()

    print("COMPANIES BY ICP TIER")
    print("-" * 40)
    for tier, count in sorted(report["companies"]["by_tier"].items()):
        print(f"  {tier:20} {count:6,}")
    print()

    print("CONTACTS BY SOURCE")
    print("-" * 40)
    for src, count in sorted(report["contacts"]["by_source"].items(), key=lambda x: -x[1]):
        indicator = "(Coperniq)" if src == "close_crm" else "(Value-Add)"
        print(f"  {src:20} {count:6,} {indicator}")
    print()

    enrichments = report["enrichments"]
    if enrichments.get("total_runs", 0) > 0:
        print("ENRICHMENT PIPELINE ACTIVITY")
        print("-" * 40)
        print(f"Total Enrichment Runs: {enrichments['total_runs']:,}")
        print(f"Contacts Discovered:   {enrichments['total_contacts_found']:,}")
        print(f"ATL Contacts Found:    {enrichments['total_atl_found']:,}")
        print(f"Emails Found:          {enrichments['total_emails_found']:,}")
        print(f"Total Cost:            ${enrichments['total_cost_usd']:.2f}")
        print(f"Success Rate:          {enrichments['success_rate']}")
        print()

    print("=" * 70)
    print("VALUE ATTRIBUTION SUMMARY")
    print("=" * 70)
    print()
    print("COPERNIQ PROVIDED (Baseline):")
    print(f"  - {summary['coperniq_baseline_companies']:,} companies from Close CRM")
    print(f"  - {summary['coperniq_baseline_contacts']:,} contacts from Close CRM")
    print()
    print("SALES-AGENT ADDED (Value-Add):")
    print(f"  - {summary['value_add_companies']:,} new companies discovered")
    print(f"  - {summary['value_add_contacts']:,} new contacts discovered")
    print(f"  - {summary['atl_contacts_discovered']:,} decision-maker (ATL) contacts identified")
    print()
    print("=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="Generate Investor Value Report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    report = await generate_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
