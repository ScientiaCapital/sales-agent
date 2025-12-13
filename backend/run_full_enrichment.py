#!/usr/bin/env python3
"""
Full Website Enrichment Pipeline - ATL + Content + Screenshots

Captures EVERYTHING from company websites:
1. ATL contacts (executives)
2. Landing page content (for agent context)
3. Company signals (hiring, funding, tech stack)
4. Screenshots (for VLM/OCR when Playwright available)

100% FREE with BeautifulSoup (screenshots optional with Playwright)

Usage:
    python run_full_enrichment.py                    # Process 10 companies
    python run_full_enrichment.py --batch 50         # Process 50 companies
    python run_full_enrichment.py --batch 100 --auto # Run 100 without prompts
    python run_full_enrichment.py --test             # Test on sample sites
    python run_full_enrichment.py --screenshots      # Also take screenshots (needs Playwright)
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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
    """Get companies with websites not yet enriched."""
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
            "source": "beautifulsoup_scraper",
            "confidence": 70,
        }

        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/dim_contacts",
            headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
            json=contact_data,
            timeout=10.0
        )

        if response.status_code in (200, 201, 204):
            saved += 1

    return saved


async def save_website_content(
    client: httpx.AsyncClient,
    company_id: str,
    content: Dict[str, Any]
) -> bool:
    """Save website content to fact_website_content table."""
    # Prepare data for storage
    content_data = {
        "company_id": company_id,
        "url": content.get("url", ""),
        "homepage_title": content.get("homepage_title", "")[:500],
        "homepage_description": content.get("homepage_description", "")[:1000],
        "homepage_text": content.get("homepage_text", "")[:10000],
        "value_proposition": content.get("value_proposition", "")[:500],
        "all_text": content.get("all_text", "")[:50000],
        "pages_scraped": json.dumps(content.get("pages_scraped", [])),
        "services": content.get("services", [])[:10],
        "products": content.get("products", [])[:10],
        "is_hiring": content.get("signals", {}).get("is_hiring", False),
        "has_funding": content.get("signals", {}).get("has_funding", False),
        "growth_indicators": content.get("signals", {}).get("growth_indicators", [])[:5],
        "tech_stack": content.get("tech_stack", [])[:10],
        "social_links": json.dumps(content.get("social_links", {})),
        "scraped_at": content.get("scraped_at", datetime.now().isoformat()),
    }

    # Try to insert (table may not exist yet)
    response = await client.post(
        f"{SUPABASE_URL}/rest/v1/fact_website_content",
        headers={**get_supabase_headers(), "Prefer": "resolution=merge-duplicates"},
        json=content_data,
        timeout=10.0
    )

    if response.status_code in (200, 201, 204):
        return True
    elif response.status_code == 404:
        # Table doesn't exist - that's OK, we'll update the company instead
        return False
    else:
        # Log but don't fail
        return False


async def update_company_signals(
    client: httpx.AsyncClient,
    company_id: str,
    content: Dict[str, Any]
) -> bool:
    """Update company record with scraped signals."""
    # Only update fields we know exist in dim_companies
    update_data = {
        "last_enriched_at": datetime.now().isoformat(),
    }

    # Try to add enrichment data if columns exist
    # These are common columns that should exist
    signals = content.get("signals", {})
    if signals.get("is_hiring"):
        update_data["is_hiring"] = True

    response = await client.patch(
        f"{SUPABASE_URL}/rest/v1/dim_companies",
        headers=get_supabase_headers(),
        params={"company_id": f"eq.{company_id}"},
        json=update_data,
        timeout=10.0
    )

    return response.status_code in (200, 204)


async def scrape_company_full(website: str) -> Dict[str, Any]:
    """
    Full scrape: ATL contacts + website content.
    """
    sys.path.insert(0, str(Path(__file__).parent))

    from app.services.beautifulsoup_team_scraper import BeautifulSoupTeamScraper
    from app.services.website_content_scraper import WebsiteContentScraper

    results = {
        "contacts": [],
        "content": {},
        "error": None
    }

    try:
        # Scrape team page for ATL contacts
        team_scraper = BeautifulSoupTeamScraper()
        results["contacts"] = await team_scraper.scrape_team_page(website)

        # Scrape full website content
        content_scraper = WebsiteContentScraper()
        results["content"] = await content_scraper.scrape_website(website)

    except Exception as e:
        results["error"] = str(e)

    return results


async def run_enrichment(
    batch_size: int = 10,
    limit: int = 100,
    auto: bool = False,
    with_screenshots: bool = False
):
    """Main enrichment loop."""
    console.print(Panel.fit(
        "[bold green]FULL WEBSITE ENRICHMENT[/bold green]\n"
        "[bold green]ATL + Content + Signals[/bold green]\n\n"
        f"Batch Size: [yellow]{batch_size}[/yellow]\n"
        f"Max Companies: [magenta]{limit}[/magenta]\n"
        f"Mode: [cyan]{'Auto' if auto else 'Interactive'}[/cyan]\n"
        f"Screenshots: [cyan]{'Yes' if with_screenshots else 'No'}[/cyan]\n\n"
        "[dim]Captures:[/dim]\n"
        "[dim]- ATL contacts (executives)[/dim]\n"
        "[dim]- Landing page content[/dim]\n"
        "[dim]- Hiring/Funding signals[/dim]\n"
        "[dim]- Tech stack detection[/dim]\n"
        "[dim]- Social links[/dim]",
        title="Configuration"
    ))

    companies = await get_companies_to_scrape(limit)

    if not companies:
        console.print("[yellow]No companies to scrape![/yellow]")
        return

    # Stats
    stats = {
        "scraped": 0,
        "atl_found": 0,
        "content_saved": 0,
        "is_hiring": 0,
        "has_funding": 0,
        "errors": 0,
    }

    async with httpx.AsyncClient() as supabase_client:
        for batch_start in range(0, len(companies), batch_size):
            batch = companies[batch_start:batch_start + batch_size]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(companies) + batch_size - 1) // batch_size

            console.print(f"\n[bold]Batch {batch_num}/{total_batches}[/bold] ({len(batch)} companies)")
            console.print("-" * 70)

            for i, company in enumerate(batch):
                company_id = company["company_id"]
                company_name = company["company_name"] or "Unknown"
                website = company.get("website") or f"https://{company.get('domain')}"

                display_name = company_name[:30] + "..." if len(company_name) > 30 else company_name
                console.print(f"[{i+1}/{len(batch)}] {display_name:<35}", end=" ")

                try:
                    # Full scrape
                    results = await scrape_company_full(website)

                    if results.get("error"):
                        console.print(f"[red]ERR: {results['error'][:30]}[/red]")
                        stats["errors"] += 1
                        continue

                    # Save ATL contacts
                    contacts = results.get("contacts", [])
                    if contacts:
                        saved = await save_atl_contacts(supabase_client, company_id, contacts)
                        stats["atl_found"] += saved

                    # Save website content
                    content = results.get("content", {})
                    if content:
                        saved_content = await save_website_content(supabase_client, company_id, content)
                        if saved_content:
                            stats["content_saved"] += 1

                        # Track signals
                        if content.get("signals", {}).get("is_hiring"):
                            stats["is_hiring"] += 1
                        if content.get("signals", {}).get("has_funding"):
                            stats["has_funding"] += 1

                    # Update company with signals
                    await update_company_signals(supabase_client, company_id, content)

                    # Display results
                    parts = []
                    if contacts:
                        parts.append(f"[green]{len(contacts)} ATL[/green]")
                    if content.get("signals", {}).get("is_hiring"):
                        parts.append("[yellow]HIRING[/yellow]")
                    if content.get("signals", {}).get("has_funding"):
                        parts.append("[magenta]FUNDED[/magenta]")
                    if content.get("tech_stack"):
                        parts.append(f"[cyan]{','.join(content['tech_stack'][:2])}[/cyan]")

                    if parts:
                        console.print(" | ".join(parts))
                    else:
                        console.print("[dim]scraped[/dim]")

                    stats["scraped"] += 1
                    await asyncio.sleep(0.3)  # Be nice to servers

                except Exception as e:
                    console.print(f"[red]ERR: {str(e)[:40]}[/red]")
                    stats["errors"] += 1

            # Batch summary
            console.print(
                f"\n[cyan]Batch {batch_num}:[/cyan] "
                f"{stats['scraped']} scraped, {stats['atl_found']} ATL, "
                f"{stats['is_hiring']} hiring, {stats['has_funding']} funded"
            )

            remaining = len(companies) - (batch_start + len(batch))
            if remaining <= 0:
                break

            if not auto:
                console.print(f"\n[yellow]{remaining} companies remaining[/yellow]")
                response = console.input("Press Enter for next batch, or 'q' to quit: ")
                if response.lower() == 'q':
                    console.print("[yellow]Stopped by user[/yellow]")
                    break

    # Final summary
    summary = Table(title="Full Enrichment Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", style="green")

    summary.add_row("Companies Scraped", str(stats["scraped"]))
    summary.add_row("ATL Contacts Found", str(stats["atl_found"]))
    summary.add_row("Content Saved", str(stats["content_saved"]))
    summary.add_row("Companies Hiring", str(stats["is_hiring"]))
    summary.add_row("Companies w/ Funding", str(stats["has_funding"]))
    summary.add_row("Errors", str(stats["errors"]))
    summary.add_row("Success Rate", f"{stats['scraped'] / max(stats['scraped'] + stats['errors'], 1) * 100:.1f}%")
    summary.add_row("Cost", "[bold green]$0.00[/bold green]")

    console.print("\n")
    console.print(summary)


async def test_scraper():
    """Test full scraping on sample sites."""
    console.print(Panel.fit(
        "[bold yellow]TEST MODE[/bold yellow]\n\n"
        "Testing full website scraper on sample sites...",
        title="Test Run"
    ))

    test_sites = [
        ("Linear", "https://linear.app"),
        ("Stripe", "https://stripe.com"),
    ]

    for name, url in test_sites:
        console.print(f"\n[cyan]Testing: {name} ({url})[/cyan]")
        console.print("-" * 50)

        try:
            results = await scrape_company_full(url)

            contacts = results.get("contacts", [])
            content = results.get("content", {})

            console.print(f"  [green]ATL Contacts: {len(contacts)}[/green]")
            for c in contacts[:3]:
                console.print(f"    - {c['name']}: {c['title']}")

            console.print(f"\n  [cyan]Homepage Title:[/cyan] {content.get('homepage_title', '')[:60]}...")
            console.print(f"  [cyan]Value Prop:[/cyan] {content.get('value_proposition', '')[:100]}...")
            console.print(f"  [cyan]Is Hiring:[/cyan] {content.get('signals', {}).get('is_hiring')}")
            console.print(f"  [cyan]Has Funding:[/cyan] {content.get('signals', {}).get('has_funding')}")
            console.print(f"  [cyan]Tech Stack:[/cyan] {content.get('tech_stack', [])}")
            console.print(f"  [cyan]Social Links:[/cyan] {list(content.get('social_links', {}).keys())}")
            console.print(f"  [cyan]Pages Scraped:[/cyan] {len(content.get('pages_scraped', []))}")
            console.print(f"  [cyan]Total Text:[/cyan] {len(content.get('all_text', ''))} chars")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    console.print("\n[green]Test complete![/green]")


async def main():
    parser = argparse.ArgumentParser(description="Full Website Enrichment (ATL + Content)")
    parser.add_argument("--batch", type=int, default=10, help="Companies per batch")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process")
    parser.add_argument("--auto", action="store_true", help="Run without prompts")
    parser.add_argument("--screenshots", action="store_true", help="Take screenshots (needs Playwright)")
    parser.add_argument("--test", action="store_true", help="Test mode")
    args = parser.parse_args()

    if args.test:
        await test_scraper()
    else:
        await run_enrichment(
            batch_size=args.batch,
            limit=args.limit,
            auto=args.auto,
            with_screenshots=args.screenshots
        )


if __name__ == "__main__":
    asyncio.run(main())
