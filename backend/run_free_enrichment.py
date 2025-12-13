#!/usr/bin/env python3
"""
FREE Website Enrichment Pipeline - BeautifulSoup Edition

Scrapes team/about pages from company websites using BeautifulSoup.
Discovers ATL contacts and saves them to Supabase.

100% FREE - uses httpx + BeautifulSoup (no Browserbase needed)

Usage:
    python run_free_enrichment.py                    # Process 10 companies
    python run_free_enrichment.py --batch 50         # Process 50 companies
    python run_free_enrichment.py --batch 100 --auto # Run 100 without prompts
    python run_free_enrichment.py --limit 1000       # Process up to 1000 total
    python run_free_enrichment.py --test             # Test on 3 sites first
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def get_supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


async def get_companies_to_scrape(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get companies that have websites but haven't been enriched yet.
    Prioritizes by ICP score (highest first).
    """
    console.print("[cyan]Fetching companies with websites (not yet enriched)...[/cyan]")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/dim_companies",
            headers=get_supabase_headers(),
            params={
                "select": "company_id,company_name,website,domain,icp_score,current_stage",
                "domain": "not.is.null",
                "last_enriched_at": "is.null",
                "order": "icp_score.desc",
                "limit": limit
            },
            timeout=60.0
        )

        if response.status_code != 200:
            console.print(f"[red]Error fetching companies: {response.status_code}[/red]")
            return []

        companies = response.json()
        console.print(f"[green]Found {len(companies)} companies to scrape[/green]")
        return companies


async def save_atl_contacts(
    client: httpx.AsyncClient,
    company_id: str,
    contacts: List[Dict[str, str]]
) -> int:
    """Save ATL contacts to dim_contacts."""
    saved = 0

    for contact in contacts:
        name = contact.get("name", "").strip()
        title = contact.get("title", "").strip()

        if not name:
            continue

        # Parse first/last name
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        contact_data = {
            "company_id": company_id,
            "full_name": name,
            "first_name": first_name,
            "last_name": last_name,
            "title": title,
            "is_atl": True,
            "source": "beautifulsoup_scraper",  # Mark source
            "confidence": 70,  # Medium confidence from web scraping
        }

        # Upsert (avoid duplicates)
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/dim_contacts",
            headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json=contact_data,
            timeout=10.0
        )

        if response.status_code in (200, 201, 204):
            saved += 1

    return saved


async def mark_company_enriched(
    client: httpx.AsyncClient,
    company_id: str,
    method: str = "beautifulsoup"
):
    """Mark company as enriched."""
    # Only update last_enriched_at (enrichment_method column may not exist)
    await client.patch(
        f"{SUPABASE_URL}/rest/v1/dim_companies",
        headers=get_supabase_headers(),
        params={"company_id": f"eq.{company_id}"},
        json={
            "last_enriched_at": datetime.now().isoformat()
        },
        timeout=10.0
    )


async def scrape_company_free(website: str) -> List[Dict[str, str]]:
    """
    Scrape a company's team page using BeautifulSoup (FREE).
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from app.services.beautifulsoup_team_scraper import BeautifulSoupTeamScraper

    scraper = BeautifulSoupTeamScraper()

    try:
        contacts = await scraper.scrape_team_page(website)
        return contacts
    except Exception as e:
        console.print(f"[red]Scrape error: {e}[/red]")
        return []


async def test_scraper():
    """Test the scraper on a few example sites."""
    console.print(Panel.fit(
        "[bold yellow]TEST MODE[/bold yellow]\n\n"
        "Testing BeautifulSoup scraper on sample sites...",
        title="Test Run"
    ))

    test_sites = [
        ("Test Site 1", "https://stripe.com"),
        ("Test Site 2", "https://anthropic.com"),
        ("Test Site 3", "https://linear.app"),
    ]

    for name, url in test_sites:
        console.print(f"\n[cyan]Testing: {name} ({url})[/cyan]")

        try:
            contacts = await scrape_company_free(url)

            if contacts:
                console.print(f"  [green]Found {len(contacts)} ATL contacts:[/green]")
                for c in contacts[:5]:  # Show first 5
                    console.print(f"    - {c['name']}: {c['title']}")
                if len(contacts) > 5:
                    console.print(f"    ... and {len(contacts) - 5} more")
            else:
                console.print("  [yellow]No ATL contacts found (may need JS rendering)[/yellow]")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    console.print("\n[green]Test complete![/green]")


async def run_enrichment(batch_size: int = 10, limit: int = 100, auto: bool = False):
    """Main enrichment loop."""
    console.print(Panel.fit(
        "[bold green]FREE WEBSITE ENRICHMENT[/bold green]\n"
        "[bold green]BeautifulSoup Edition[/bold green]\n\n"
        f"Batch Size: [yellow]{batch_size}[/yellow]\n"
        f"Max Companies: [magenta]{limit}[/magenta]\n"
        f"Mode: [cyan]{'Auto' if auto else 'Interactive'}[/cyan]\n\n"
        "[dim]100% FREE - Uses httpx + BeautifulSoup[/dim]\n"
        "[dim]No Browserbase, Hunter.io, or Apollo tokens used[/dim]",
        title="Configuration"
    ))

    # Get companies to scrape
    companies = await get_companies_to_scrape(limit)

    if not companies:
        console.print("[yellow]No companies to scrape![/yellow]")
        return

    # Stats
    total_scraped = 0
    total_atl_found = 0
    total_errors = 0
    total_empty = 0

    async with httpx.AsyncClient() as supabase_client:
        # Process in batches
        for batch_start in range(0, len(companies), batch_size):
            batch = companies[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(companies) + batch_size - 1) // batch_size

            console.print(f"\n[bold]Batch {batch_num}/{total_batches}[/bold] ({len(batch)} companies)")
            console.print("-" * 60)

            for i, company in enumerate(batch):
                company_id = company["company_id"]
                company_name = company["company_name"] or "Unknown"
                website = company.get("website") or f"https://{company.get('domain')}"

                # Truncate company name for display
                display_name = company_name[:35] + "..." if len(company_name) > 35 else company_name
                console.print(f"[{i+1}/{len(batch)}] {display_name:<40}", end=" ")

                try:
                    # Scrape website
                    contacts = await scrape_company_free(website)

                    if contacts:
                        # Save contacts
                        saved = await save_atl_contacts(supabase_client, company_id, contacts)
                        total_atl_found += saved
                        console.print(f"[green]{saved} ATL[/green]")
                    else:
                        console.print("[dim]No ATL[/dim]")
                        total_empty += 1

                    # Mark as enriched
                    await mark_company_enriched(supabase_client, company_id, "beautifulsoup")
                    total_scraped += 1

                    # Small delay to be nice to servers
                    await asyncio.sleep(0.5)

                except Exception as e:
                    console.print(f"[red]ERR: {str(e)[:40]}[/red]")
                    total_errors += 1
                    # Still mark as enriched to avoid retrying bad sites
                    await mark_company_enriched(supabase_client, company_id, "beautifulsoup_error")

            # Batch summary
            console.print(
                f"\n[cyan]Batch {batch_num} complete:[/cyan] "
                f"{total_scraped} scraped, {total_atl_found} ATL found, "
                f"{total_empty} empty, {total_errors} errors"
            )

            # Check if more batches
            remaining = len(companies) - (batch_start + len(batch))
            if remaining <= 0:
                break

            # Prompt for next batch (unless auto mode)
            if not auto:
                console.print(f"\n[yellow]{remaining} companies remaining[/yellow]")
                response = console.input("Press Enter for next batch, or 'q' to quit: ")
                if response.lower() == 'q':
                    console.print("[yellow]Stopped by user[/yellow]")
                    break

    # Final summary
    summary = Table(title="FREE Enrichment Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", style="green")

    summary.add_row("Companies Scraped", str(total_scraped))
    summary.add_row("ATL Contacts Found", str(total_atl_found))
    summary.add_row("No ATL Found", str(total_empty))
    summary.add_row("Errors", str(total_errors))
    summary.add_row("Success Rate", f"{(total_scraped - total_errors) / max(total_scraped, 1) * 100:.1f}%")
    summary.add_row("ATL Hit Rate", f"{(total_scraped - total_empty - total_errors) / max(total_scraped, 1) * 100:.1f}%")
    summary.add_row("Cost", "[bold green]$0.00[/bold green]")

    console.print("\n")
    console.print(summary)

    console.print("\n[dim]Tip: Sites with no ATL may need JS rendering (Browserbase)[/dim]")


async def main():
    parser = argparse.ArgumentParser(description="FREE Website Enrichment (BeautifulSoup)")
    parser.add_argument("--batch", type=int, default=10, help="Companies per batch (default: 10)")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process (default: 100)")
    parser.add_argument("--auto", action="store_true", help="Run without prompts")
    parser.add_argument("--test", action="store_true", help="Test mode - scrape sample sites")
    args = parser.parse_args()

    if args.test:
        await test_scraper()
    else:
        await run_enrichment(batch_size=args.batch, limit=args.limit, auto=args.auto)


if __name__ == "__main__":
    asyncio.run(main())
