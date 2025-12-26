#!/usr/bin/env python3
"""
Apollo Free Batch Enrichment - Batches of 5 companies

Usage:
    python scripts/run_apollo_free_batch.py --batch-size 5 --tier PLATINUM
    python scripts/run_apollo_free_batch.py --batch-size 5 --tier GOLD --limit 25
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env', override=True)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from supabase import create_client

from app.services.supervised_pipeline.stages.apollo_free import ApolloFreeStage

console = Console()


async def get_companies_for_apollo(supabase, tier: str, limit: int):
    """Get companies that need Apollo enrichment."""
    console.print(f"[cyan]Fetching {tier} companies for Apollo enrichment...[/cyan]")

    # Get companies with website that haven't been Apollo-enriched
    result = supabase.table("dim_companies").select(
        "company_id", "company_name", "website", "domain", "icp_tier"
    ).eq("icp_tier", tier).not_.is_(
        "website", "null"
    ).is_("apollo_enriched_at", "null").limit(limit).execute()

    companies = []
    for row in (result.data or []):
        domain = row.get("domain") or row.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]
        if domain:
            companies.append({
                "company_id": row.get("company_id"),
                "company_name": row.get("company_name"),
                "domain": domain,
                "icp_tier": row.get("icp_tier"),
            })

    console.print(f"[green]Found {len(companies)} companies needing Apollo enrichment[/green]")
    return companies


async def run_apollo_batch(companies: list, stage: ApolloFreeStage, supabase, batch_num: int):
    """Run Apollo free enrichment on a batch of companies."""

    table = Table(title=f"Batch {batch_num} Results")
    table.add_column("Company", style="cyan")
    table.add_column("Domain", style="blue")
    table.add_column("Contacts", justify="right")
    table.add_column("Status", style="green")

    total_contacts = 0

    for company in companies:
        try:
            result = await stage.execute(company)

            contact_count = result.data.get("contact_count", 0) if result.success else 0
            total_contacts += contact_count

            status = "✅" if result.success else f"❌ {result.error[:30]}"
            table.add_row(
                company["company_name"][:30],
                company["domain"][:25],
                str(contact_count),
                status
            )

            # Mark company as Apollo-enriched
            if result.success:
                supabase.table("dim_companies").update({
                    "apollo_enriched_at": datetime.now(timezone.utc).isoformat()
                }).eq("company_id", company["company_id"]).execute()

                # Save contacts if found (Apollo free often doesn't have emails)
                contacts = result.data.get("contacts", [])
                saved = 0
                for contact in contacts:
                    try:
                        # Apollo free gives names/titles but often not emails
                        first_name = contact.get("first_name", "").strip() if contact.get("first_name") else None
                        last_name = contact.get("last_name", "").strip() if contact.get("last_name") else None
                        email = contact.get("email", "").strip() if contact.get("email") else None

                        if not first_name and not last_name:
                            continue  # Skip junk

                        # Build full_name (required by check constraint)
                        full_name = f"{first_name or ''} {last_name or ''}".strip()
                        if len(full_name) < 3:
                            continue  # Skip if name too short

                        supabase.table("dim_contacts").insert({
                            "company_id": company["company_id"],
                            "full_name": full_name,
                            "first_name": first_name,
                            "last_name": last_name,
                            "title": contact.get("title"),
                            "email": email,
                            "source": "apollo_free",
                        }).execute()
                        saved += 1
                    except Exception as e:
                        pass  # Duplicate or constraint violation
                console.print(f"[dim]  Saved {saved}/{len(contacts)} contacts[/dim]")

        except Exception as e:
            table.add_row(
                company["company_name"][:30],
                company["domain"][:25],
                "0",
                f"❌ {str(e)[:30]}"
            )

    console.print(table)
    console.print(f"[bold green]Batch {batch_num} complete: {total_contacts} contacts found[/bold green]")
    return total_contacts


async def main():
    parser = argparse.ArgumentParser(description="Apollo Free Batch Enrichment")
    parser.add_argument("--batch-size", type=int, default=5, help="Companies per batch")
    parser.add_argument("--tier", default="PLATINUM", help="ICP tier to process")
    parser.add_argument("--limit", type=int, default=25, help="Total companies to process")
    args = parser.parse_args()

    console.print(Panel(
        f"[bold]Apollo Free Batch Enrichment[/bold]\n"
        f"Tier: {args.tier} | Batch Size: {args.batch_size} | Limit: {args.limit}",
        title="🚀 Starting"
    ))

    # Initialize
    supabase = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )

    stage = ApolloFreeStage()

    # Get companies
    companies = await get_companies_for_apollo(supabase, args.tier, args.limit)

    if not companies:
        console.print("[yellow]No companies found for Apollo enrichment[/yellow]")
        return

    # Process in batches
    total_contacts = 0
    batch_num = 1

    for i in range(0, len(companies), args.batch_size):
        batch = companies[i:i + args.batch_size]
        console.print(f"\n[cyan]Processing batch {batch_num} ({len(batch)} companies)...[/cyan]")

        contacts = await run_apollo_batch(batch, stage, supabase, batch_num)
        total_contacts += contacts
        batch_num += 1

        # Brief pause between batches for rate limiting
        if i + args.batch_size < len(companies):
            console.print("[dim]Pausing 2s between batches...[/dim]")
            await asyncio.sleep(2)

    # Summary
    console.print(Panel(
        f"[bold green]Complete![/bold green]\n"
        f"Companies processed: {len(companies)}\n"
        f"Total contacts found: {total_contacts}",
        title="📊 Summary"
    ))

    await stage.close()


if __name__ == "__main__":
    asyncio.run(main())
