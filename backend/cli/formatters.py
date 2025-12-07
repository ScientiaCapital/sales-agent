"""
CLI Formatters

Pretty terminal output for enrichment results using Rich.
"""

from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def print_checking_dedup() -> None:
    """Display checking Close CRM message."""
    console.print("[bold blue]🔍 Checking Close CRM for duplicates...[/bold blue]")


def print_duplicate_found(existing_lead: Dict[str, Any]) -> None:
    """Display duplicate found message with lead details."""
    lead_name = existing_lead.get("company_name") or existing_lead.get("name", "Unknown")
    lead_id = existing_lead.get("lead_id") or existing_lead.get("id", "")
    lead_url = existing_lead.get("url", "")
    confidence = existing_lead.get("confidence", 0)

    panel = Panel(
        f"[bold red]⚠️  Lead Already Exists[/bold red]\n\n"
        f"[yellow]Company:[/yellow] {lead_name}\n"
        f"[yellow]Match Confidence:[/yellow] {confidence:.1f}%\n"
        f"[yellow]Lead ID:[/yellow] {lead_id}\n"
        f"[yellow]Close URL:[/yellow] {lead_url}",
        title="Duplicate Detected",
        border_style="red"
    )
    console.print(panel)


def print_starting_enrichment() -> None:
    """Display starting enrichment message."""
    console.print("[bold green]✅ Not a duplicate. Starting enrichment...[/bold green]")


def print_enrichment_progress(step: str) -> None:
    """Display enrichment progress step."""
    console.print(f"[cyan]  → {step}[/cyan]")


def print_enrichment_result(result: Dict[str, Any]) -> None:
    """
    Display enrichment results in formatted table.

    Args:
        result: Enrichment result dict with company data, contacts, ICP score, etc.
    """
    company_name = result.get("company_name", "Unknown")
    domain = result.get("domain", "N/A")

    # Header
    console.print(f"\n[bold green]✅ Enrichment Complete: {company_name}[/bold green]\n")

    # Company Info Table
    company_table = Table(title="Company Information", box=box.ROUNDED)
    company_table.add_column("Field", style="cyan")
    company_table.add_column("Value", style="white")

    company_table.add_row("Domain", domain)
    company_table.add_row("ICP Score", f"{result.get('icp_score', 0)}/100")
    company_table.add_row("ICP Tier", result.get('icp_tier', 'N/A'))
    company_table.add_row("Quality Tier", result.get('quality_tier', 'N/A'))

    if result.get("oem_brands"):
        brands = ", ".join(result["oem_brands"][:5])
        company_table.add_row("OEM Brands", brands)

    if result.get("service_areas"):
        areas = ", ".join(result["service_areas"][:5])
        company_table.add_row("Service Areas", areas)

    console.print(company_table)

    # Contacts Table
    contacts = result.get("contacts", [])
    if contacts:
        console.print()  # Blank line
        contacts_table = Table(title=f"Contacts Found ({len(contacts)})", box=box.ROUNDED)
        contacts_table.add_column("Name", style="cyan")
        contacts_table.add_column("Title", style="yellow")
        contacts_table.add_column("Email", style="green")
        contacts_table.add_column("Phone", style="magenta")
        contacts_table.add_column("ATL", style="bold")

        for contact in contacts[:10]:  # Show max 10
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            title = contact.get("position") or contact.get("title", "N/A")
            email = contact.get("email", "N/A")
            phone = contact.get("phone", "N/A")
            is_atl = "✅" if contact.get("is_atl") else "❌"

            contacts_table.add_row(name, title, email, phone, is_atl)

        console.print(contacts_table)
    else:
        console.print("[yellow]⚠️  No contacts discovered yet[/yellow]")

    # Summary Stats
    console.print()
    stats = [
        f"[cyan]ATL Contacts:[/cyan] {result.get('atl_count', 0)}",
        f"[cyan]Total Contacts:[/cyan] {len(contacts)}",
        f"[cyan]Email Available:[/cyan] {'✅' if result.get('has_email') else '❌'}",
        f"[cyan]Phone Available:[/cyan] {'✅' if result.get('has_phone') else '❌'}",
    ]
    console.print(" | ".join(stats))


def print_staging_options(channels: List[str]) -> None:
    """Display outreach staging confirmation."""
    console.print(f"\n[bold]📝 Staging outreach for channels:[/bold] {', '.join(channels)}")


def print_staging_complete(drafts_created: int) -> None:
    """Display staging completion message."""
    panel = Panel(
        f"[bold green]✅ Outreach Staged Successfully[/bold green]\n\n"
        f"Drafts created: {drafts_created}\n"
        f"Status: Awaiting approval in Slack",
        title="Staging Complete",
        border_style="green"
    )
    console.print(panel)


def print_error(error_msg: str) -> None:
    """Display error message."""
    console.print(f"[bold red]❌ Error:[/bold red] {error_msg}")


def print_info(msg: str) -> None:
    """Display info message."""
    console.print(f"[blue]ℹ️  {msg}[/blue]")


def print_warning(msg: str) -> None:
    """Display warning message."""
    console.print(f"[yellow]⚠️  {msg}[/yellow]")


def print_success(msg: str) -> None:
    """Display success message."""
    console.print(f"[bold green]✅ {msg}[/bold green]")
