#!/usr/bin/env python3
"""
Domain Discovery Pipeline

Discovers website domains for companies that don't have them.
This is a prerequisite for the enrichment pipeline.

Usage:
    python run_domain_discovery.py --batch-size 10 --limit 100
    python run_domain_discovery.py --help
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Rich for terminal UI
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.panel import Panel

import httpx

console = Console()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def get_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def get_companies_without_domain(limit: int) -> List[Dict[str, Any]]:
    """Fetch companies that need domain discovery."""
    console.print("[cyan]Fetching companies without domains...[/cyan]")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/dim_companies",
            headers=get_headers(),
            params={
                "select": "company_id,company_name,city,state",
                "website": "is.null",
                "order": "icp_score.desc",
                "limit": limit
            },
            timeout=60.0
        )

        if response.status_code != 200:
            console.print(f"[red]Error fetching companies: {response.status_code}[/red]")
            return []

        companies = response.json()
        console.print(f"[green]Found {len(companies)} companies needing domain discovery[/green]")
        return companies


async def update_company_domain(company_id: str, website: str) -> bool:
    """Update company with discovered domain."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{SUPABASE_URL}/rest/v1/dim_companies",
            headers=get_headers(),
            params={"company_id": f"eq.{company_id}"},
            json={"website": website, "domain": website.replace("https://", "").replace("http://", "").split("/")[0]},
            timeout=10.0
        )
        return response.status_code in (200, 204)


async def run_discovery(batch_size: int = 10, limit: int = 100):
    """Main discovery loop."""
    # Import the discovery service
    sys.path.insert(0, str(Path(__file__).parent))
    from app.services.website_discovery import WebsiteDiscoveryService

    console.print(Panel.fit(
        "[bold cyan]DOMAIN DISCOVERY PIPELINE[/bold cyan]\n\n"
        f"Batch Size: [yellow]{batch_size}[/yellow]\n"
        f"Max Companies: [magenta]{limit}[/magenta]",
        title="Configuration"
    ))

    # Get companies needing discovery
    companies = await get_companies_without_domain(limit)

    if not companies:
        console.print("[yellow]No companies need domain discovery![/yellow]")
        return

    # Initialize discovery service
    discovery = WebsiteDiscoveryService()

    found_count = 0
    not_found_count = 0
    errors = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Discovering domains...", total=len(companies))

        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]

            for company in batch:
                company_id = company["company_id"]
                company_name = company["company_name"]
                city = company.get("city", "")
                state = company.get("state", "")

                try:
                    # Discover website
                    website = await discovery.discover_website(
                        company_name=company_name,
                        city=city,
                        state=state
                    )

                    if website:
                        # Update company
                        success = await update_company_domain(company_id, website)
                        if success:
                            found_count += 1
                            console.print(f"  [green]Found:[/green] {company_name} -> {website}")
                        else:
                            errors.append(f"Failed to update {company_name}")
                    else:
                        not_found_count += 1
                        console.print(f"  [dim]Not found:[/dim] {company_name}")

                except Exception as e:
                    errors.append(f"{company_name}: {str(e)}")
                    console.print(f"  [red]Error:[/red] {company_name} - {e}")

                progress.update(task, advance=1)

            # Brief pause between batches to avoid rate limiting
            if i + batch_size < len(companies):
                await asyncio.sleep(1)

    # Summary
    console.print("\n")
    summary = Table(title="Discovery Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", style="green")

    summary.add_row("Websites Found", str(found_count))
    summary.add_row("Not Found", str(not_found_count))
    summary.add_row("Errors", str(len(errors)))
    summary.add_row("Total Processed", str(len(companies)))
    summary.add_row("Success Rate", f"{found_count / len(companies) * 100:.1f}%")

    console.print(summary)

    if errors:
        console.print(f"\n[yellow]Errors ({len(errors)}):[/yellow]")
        for err in errors[:10]:
            console.print(f"  - {err}")


async def main():
    parser = argparse.ArgumentParser(description="Domain Discovery Pipeline")
    parser.add_argument("--batch-size", type=int, default=10, help="Companies per batch")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process")
    args = parser.parse_args()

    await run_discovery(batch_size=args.batch_size, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
