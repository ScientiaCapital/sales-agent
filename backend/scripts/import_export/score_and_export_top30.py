#!/usr/bin/env python3
"""
ICP Scoring + Top 30 Export for Close CRM
=========================================
Run fresh ICP scoring on all Supabase companies, export top 30 for CEO/CTO.

Usage:
    cd backend
    source ../venv/bin/activate
    python score_and_export_top30.py

Output:
    - CLOSE_CRM_IMPORT_TOP30_20251204.csv (Close CRM ready)
    - TOP_1000_RESCORED_20251204.csv (reference)

Author: Claude + Tim
Date: Dec 4, 2025
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

# Load environment
load_dotenv()

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.icp_scorer import calculate_icp_score, get_supabase_client

console = Console()

# Output directory
OUTPUT_DIR = Path(__file__).parent / "data" / "final_enrichment_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Today's date for filenames
TODAY = datetime.now().strftime("%Y%m%d")


def fetch_all_companies() -> list[dict]:
    """Fetch all companies from Supabase dim_companies."""
    console.print("\n[cyan]Fetching all companies from Supabase...[/cyan]")

    supabase = get_supabase_client()

    # Supabase has 1000 row limit per query, so paginate
    all_companies = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_companies').select('*').range(
            offset, offset + batch_size - 1
        ).execute()

        if not result.data:
            break

        all_companies.extend(result.data)
        offset += batch_size

        if len(result.data) < batch_size:
            break

    console.print(f"[green]Fetched {len(all_companies):,} companies[/green]")
    return all_companies


def fetch_atl_contacts() -> dict[str, dict]:
    """Fetch best ATL contact per company from dim_contacts."""
    console.print("\n[cyan]Fetching ATL contacts...[/cyan]")

    supabase = get_supabase_client()

    # Get all ATL contacts
    all_contacts = []
    offset = 0
    batch_size = 1000

    while True:
        result = supabase.table('dim_contacts').select(
            'company_id, full_name, title, email, phone, is_atl'
        ).eq('is_atl', True).range(offset, offset + batch_size - 1).execute()

        if not result.data:
            break

        all_contacts.extend(result.data)
        offset += batch_size

        if len(result.data) < batch_size:
            break

    # Group by company_id, pick best contact (prefer one with email+phone)
    contacts_by_company = {}
    for contact in all_contacts:
        company_id = contact.get('company_id')
        if not company_id:
            continue

        existing = contacts_by_company.get(company_id)

        # Score: email=2, phone=1
        contact_score = 0
        if contact.get('email') and '@' in str(contact.get('email', '')):
            contact_score += 2
        if contact.get('phone'):
            contact_score += 1

        if existing:
            existing_score = 0
            if existing.get('email') and '@' in str(existing.get('email', '')):
                existing_score += 2
            if existing.get('phone'):
                existing_score += 1
            if contact_score > existing_score:
                contacts_by_company[company_id] = contact
        else:
            contacts_by_company[company_id] = contact

    console.print(f"[green]Found {len(contacts_by_company):,} companies with ATL contacts[/green]")
    return contacts_by_company


def score_all_companies(companies: list[dict]) -> list[dict]:
    """Calculate ICP score for all companies."""
    console.print("\n[cyan]Calculating ICP scores...[/cyan]")

    scored = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("Scoring companies", total=len(companies))

        for company in companies:
            score, tier = calculate_icp_score(company)
            company['icp_score'] = score
            company['icp_tier'] = tier
            scored.append(company)
            progress.advance(task)

    return scored


def update_supabase_scores(companies: list[dict]) -> int:
    """Batch update ICP scores in Supabase."""
    console.print("\n[cyan]Updating scores in Supabase...[/cyan]")

    supabase = get_supabase_client()
    updated = 0
    batch_size = 100
    now = datetime.now(timezone.utc).isoformat()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("Updating Supabase", total=len(companies))

        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]

            for company in batch:
                company_id = company.get('company_id')
                if not company_id:
                    continue

                try:
                    supabase.table('dim_companies').update({
                        'icp_score': int(company['icp_score']),  # Convert to int for Supabase
                        'icp_tier': company['icp_tier'],
                        'icp_last_checked': now
                    }).eq('company_id', company_id).execute()
                    updated += 1
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to update {company_id}: {e}[/yellow]")

                progress.advance(task)

    console.print(f"[green]Updated {updated:,} companies in Supabase[/green]")
    return updated


def export_close_crm_csv(companies: list[dict], contacts: dict[str, dict], top_n: int = 30):
    """Export top N companies in Close CRM import format."""

    # Sort by ICP score descending
    sorted_companies = sorted(companies, key=lambda x: x.get('icp_score', 0), reverse=True)
    top_companies = sorted_companies[:top_n]

    # Build Close CRM format rows
    rows = []
    for company in top_companies:
        company_id = company.get('company_id')
        contact = contacts.get(company_id, {})

        # Count ATL contacts for this company
        atl_count = 1 if contact else 0

        row = {
            'Company': company.get('company_name', ''),
            'Company Domain': company.get('domain', ''),
            'Company Phone': company.get('phone', ''),
            'Company Address': company.get('address', ''),
            'Company City': company.get('city', ''),
            'Company State': company.get('state', ''),
            'Company Zip': company.get('zip', ''),
            'Contact Name': contact.get('full_name', ''),
            'Contact Title': contact.get('title', ''),
            'Contact Email': contact.get('email', ''),
            'Lead Source': 'ICP Top 30 - Dec 2025',
            'LinkedIn URL': company.get('linkedin_url', ''),
            'LinkedIn Employees': company.get('employee_count', ''),
            'ATL Count': atl_count,
            'ICP Score': company.get('icp_score', 0),
            'ICP Tier': company.get('icp_tier', 'LEAD'),
        }
        rows.append(row)

    # Create DataFrame and export
    df = pd.DataFrame(rows)

    # Export top 30 for Close CRM
    output_path = OUTPUT_DIR / f"CLOSE_CRM_IMPORT_TOP30_{TODAY}.csv"
    df.to_csv(output_path, index=False)
    console.print(f"\n[green bold]Exported: {output_path}[/green bold]")

    return df, output_path


def export_top_1000_csv(companies: list[dict], contacts: dict[str, dict]):
    """Export top 1000 companies for reference."""

    # Sort by ICP score descending
    sorted_companies = sorted(companies, key=lambda x: x.get('icp_score', 0), reverse=True)
    top_1000 = sorted_companies[:1000]

    # Build rows with rank
    rows = []
    for rank, company in enumerate(top_1000, 1):
        company_id = company.get('company_id')
        contact = contacts.get(company_id, {})

        row = {
            'Rank': rank,
            'Company': company.get('company_name', ''),
            'Company Domain': company.get('domain', ''),
            'Company Phone': company.get('phone', ''),
            'Company City': company.get('city', ''),
            'Company State': company.get('state', ''),
            'Contact Name': contact.get('full_name', ''),
            'Contact Title': contact.get('title', ''),
            'Contact Email': contact.get('email', ''),
            'ICP Score': company.get('icp_score', 0),
            'ICP Tier': company.get('icp_tier', 'LEAD'),
            'OEM Brands': ', '.join(company.get('oem_brands', []) or []),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    output_path = OUTPUT_DIR / f"TOP_1000_RESCORED_{TODAY}.csv"
    df.to_csv(output_path, index=False)
    console.print(f"[green]Exported: {output_path}[/green]")

    return df, output_path


def display_tier_summary(companies: list[dict]):
    """Display ICP tier distribution."""

    tier_counts = {'PLATINUM': 0, 'GOLD': 0, 'SILVER': 0, 'BRONZE': 0, 'LEAD': 0}
    for company in companies:
        tier = company.get('icp_tier', 'LEAD')
        if tier in tier_counts:
            tier_counts[tier] += 1

    table = Table(title="ICP Tier Distribution")
    table.add_column("Tier", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Percentage", justify="right")

    total = len(companies)
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
        count = tier_counts[tier]
        pct = (count / total * 100) if total > 0 else 0
        table.add_row(tier, f"{count:,}", f"{pct:.1f}%")

    table.add_row("─" * 10, "─" * 8, "─" * 8)
    table.add_row("TOTAL", f"{total:,}", "100%")

    console.print("\n")
    console.print(table)


def display_top_30_preview(df: pd.DataFrame):
    """Display preview of top 30 leads."""

    table = Table(title="Top 30 Leads for Close CRM Import")
    table.add_column("#", style="dim", width=3)
    table.add_column("Company", style="cyan", max_width=30)
    table.add_column("Phone", style="green")
    table.add_column("State", width=5)
    table.add_column("Contact", max_width=20)
    table.add_column("Score", justify="right")
    table.add_column("Tier", style="bold")

    for idx, row in df.head(30).iterrows():
        tier_style = {
            'PLATINUM': 'bold magenta',
            'GOLD': 'bold yellow',
            'SILVER': 'white',
            'BRONZE': 'dim'
        }.get(row['ICP Tier'], '')

        table.add_row(
            str(idx + 1),
            str(row['Company'])[:30],
            str(row['Company Phone'])[:15],
            str(row['Company State']),
            str(row['Contact Name'])[:20],
            str(int(row['ICP Score'])),
            f"[{tier_style}]{row['ICP Tier']}[/{tier_style}]"
        )

    console.print("\n")
    console.print(table)


def main():
    """Main execution."""
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]     ICP SCORING + TOP 30 EXPORT FOR CLOSE CRM            [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")

    # Step 1: Fetch all companies
    companies = fetch_all_companies()

    # Step 2: Fetch ATL contacts
    contacts = fetch_atl_contacts()

    # Step 3: Score all companies
    scored_companies = score_all_companies(companies)

    # Step 4: Update Supabase with new scores
    update_supabase_scores(scored_companies)

    # Step 5: Display tier summary
    display_tier_summary(scored_companies)

    # Step 6: Export top 30 for Close CRM
    top30_df, top30_path = export_close_crm_csv(scored_companies, contacts, top_n=30)

    # Step 7: Export top 1000 for reference
    export_top_1000_csv(scored_companies, contacts)

    # Step 8: Preview top 30
    display_top_30_preview(top30_df)

    # Final summary
    console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]                    COMPLETE!                              [/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("\n[bold]Close CRM Import File:[/bold]")
    console.print(f"  [cyan]{top30_path}[/cyan]")
    console.print("\n[dim]Hand this CSV to the CTO for direct Close CRM import.[/dim]\n")


if __name__ == "__main__":
    main()
