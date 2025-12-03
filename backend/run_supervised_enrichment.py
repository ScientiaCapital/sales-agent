#!/usr/bin/env python3
"""
Supervised Enrichment Runner

Interactive terminal-based enrichment with manual checkpoints.

Usage:
    python run_supervised_enrichment.py --budget 5.0 --batch-size 2 --limit 100
    python run_supervised_enrichment.py --help

Controls:
    - Process companies in small batches (default: 2 at a time)
    - Review results after each batch
    - Approve or stop before continuing
    - Real-time cost tracking with budget enforcement
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Rich for beautiful terminal UI
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Redis and Supabase clients
from redis.asyncio import from_url as redis_from_url
from supabase import create_client

# Supervised pipeline components
from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator
from app.services.supervised_pipeline.budget_tracker import BudgetTracker
from app.services.supervised_pipeline.state_manager import StateManager

console = Console()


async def get_unenriched_companies(supabase, limit: int) -> List[Dict[str, Any]]:
    """Fetch companies needing enrichment from Supabase.

    Args:
        supabase: Supabase client
        limit: Maximum number of companies to fetch

    Returns:
        List of company dictionaries
    """
    console.print("[cyan]Querying Supabase for unenriched companies...[/cyan]")

    # Use actual column names from dim_companies schema
    # Only get companies that have a website (required for enrichment)
    result = supabase.table("dim_companies").select(
        "company_id", "company_name", "website", "icp_tier"
    ).is_("last_enriched_at", "null").not_.is_(
        "website", "null"
    ).order(
        "icp_tier", desc=False  # Prioritize PLATINUM > GOLD > SILVER > BRONZE
    ).limit(limit).execute()

    # Map to expected field names for orchestrator compatibility
    companies = []
    for row in (result.data or []):
        companies.append({
            "id": row.get("company_id"),
            "name": row.get("company_name"),
            "domain": row.get("website"),
            "icp_tier": row.get("icp_tier"),
        })

    console.print(f"[green]Found {len(companies)} companies needing enrichment[/green]")

    return companies


def display_header(budget: float, batch_size: int, total: int, batch_num: int = 0) -> None:
    """Display pipeline header with key metrics.

    Args:
        budget: Total budget in USD
        batch_size: Companies per batch
        total: Total companies in queue
        batch_num: Current batch number
    """
    header_text = (
        f"[bold cyan]SUPERVISED ENRICHMENT PIPELINE[/bold cyan]\n\n"
        f"Budget: [green]${budget:.2f}[/green] | "
        f"Batch Size: [yellow]{batch_size}[/yellow] | "
        f"Queue: [magenta]{total}[/magenta] companies"
    )

    if batch_num > 0:
        header_text += f" | [blue]Batch #{batch_num}[/blue]"

    console.print(Panel(header_text, title="Sales Agent", border_style="cyan"))


def display_results_table(results: List[Dict[str, Any]], batch_num: int) -> None:
    """Display batch results in a formatted table.

    Args:
        results: List of enrichment result dictionaries
        batch_num: Current batch number
    """
    table = Table(title=f"Batch #{batch_num} Results", show_header=True, header_style="bold magenta")

    table.add_column("Company", style="cyan", no_wrap=False, width=30)
    table.add_column("Contacts", justify="right", style="green")
    table.add_column("Stages", justify="right", style="yellow")
    table.add_column("Cost", justify="right", style="blue")
    table.add_column("Time", justify="right", style="white")
    table.add_column("Status", justify="center")

    for result in results:
        company_name = result.get("company_name", "Unknown")
        contact_count = len(result.get("contacts", []))
        stages_completed = result.get("stages_completed", 0)
        total_stages = result.get("total_stages", 4)
        cost = result.get("total_cost_usd", 0.0)
        latency_ms = result.get("total_latency_ms", 0)
        latency_sec = latency_ms / 1000
        success = result.get("success", False)

        # Determine status emoji
        if success:
            status = "[green]✓[/green]"
        elif result.get("budget_exceeded"):
            status = "[red]$[/red]"  # Budget exceeded
        else:
            status = "[red]✗[/red]"  # Failed

        table.add_row(
            company_name,
            str(contact_count),
            f"{stages_completed}/{total_stages}",
            f"${cost:.4f}",
            f"{latency_sec:.1f}s",
            status,
        )

    console.print(table)


def display_budget_status(budget_tracker, budget_limit: float, processed: int, total: int) -> None:
    """Display current budget status.

    Args:
        budget_tracker: BudgetTracker instance
        budget_limit: Total budget limit
        processed: Number of companies processed
        total: Total companies in queue
    """
    # This would be async in real usage, but we'll keep it simple for display
    # In practice, call: status = asyncio.run(budget_tracker.get_status())

    spent = 0.0  # Placeholder - would be from budget_tracker.get_status()
    percent_used = (spent / budget_limit * 100) if budget_limit > 0 else 0

    status_text = (
        f"[bold]Budget:[/bold] "
        f"[blue]${spent:.4f}[/blue] / [green]${budget_limit:.2f}[/green] "
        f"([yellow]{percent_used:.1f}%[/yellow] used) | "
        f"[bold]Progress:[/bold] {processed}/{total} companies"
    )

    console.print(Panel(status_text, border_style="blue"))


def prompt_action() -> str:
    """Prompt user for next action.

    Returns:
        Single character action code: c/s/r/v/q
    """
    console.print("\n[bold]Actions:[/bold]")
    console.print("  [c] Continue - Process next batch")
    console.print("  [s] Stop - Finish current batch and exit")
    console.print("  [v] View - Show detailed results")
    console.print("  [q] Quit - Exit immediately (no save)")

    while True:
        action = console.input("[cyan]Choose action > [/cyan]").strip().lower()
        if action in ("c", "s", "v", "q"):
            return action
        console.print("[red]Invalid choice. Enter c, s, v, or q[/red]")


def display_detailed_results(results: List[Dict[str, Any]]) -> None:
    """Display detailed view of enrichment results.

    Args:
        results: List of enrichment result dictionaries
    """
    console.print("\n[bold cyan]Detailed Results View[/bold cyan]\n")

    for i, result in enumerate(results, 1):
        company_name = result.get("company_name", "Unknown")
        success = result.get("success", False)

        console.print(f"[bold]{i}. {company_name}[/bold]")
        console.print(f"   Status: {'[green]Success[/green]' if success else '[red]Failed[/red]'}")
        console.print(f"   Stages: {result.get('stages_completed', 0)}/{result.get('total_stages', 4)}")
        console.print(f"   Cost: ${result.get('total_cost_usd', 0.0):.4f}")
        console.print(f"   Latency: {result.get('total_latency_ms', 0)}ms")

        # Show contacts
        contacts = result.get("contacts", [])
        if contacts:
            console.print(f"   Contacts ({len(contacts)}):")
            for contact in contacts[:3]:  # Show first 3
                name = contact.get("name", "Unknown")
                email = contact.get("email", "N/A")
                console.print(f"      - {name} ({email})")
            if len(contacts) > 3:
                console.print(f"      ... and {len(contacts) - 3} more")
        else:
            console.print("   Contacts: None found")

        # Show errors
        if "error" in result:
            console.print(f"   [red]Error: {result['error']}[/red]")

        console.print()


async def main():
    """Main entry point for supervised enrichment."""
    parser = argparse.ArgumentParser(
        description="Supervised Enrichment Pipeline - Interactive batch processing with budget control"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=5.0,
        help="Total budget in USD (default: 5.0)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Number of companies per batch (default: 2)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum companies to queue (default: 100)"
    )
    args = parser.parse_args()

    # Validate inputs
    if args.budget <= 0:
        console.print("[red]Error: Budget must be positive[/red]")
        sys.exit(1)

    if args.batch_size <= 0:
        console.print("[red]Error: Batch size must be positive[/red]")
        sys.exit(1)

    # Initialize clients
    console.print("[cyan]Initializing clients...[/cyan]")

    # Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis = await redis_from_url(redis_url, encoding="utf-8", decode_responses=True)
        await redis.ping()
        console.print("[green]✓ Redis connected[/green]")
    except Exception as e:
        console.print(f"[red]✗ Redis connection failed: {e}[/red]")
        sys.exit(1)

    # Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        console.print("[red]✗ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env[/red]")
        sys.exit(1)

    try:
        supabase = create_client(supabase_url, supabase_key)
        console.print("[green]✓ Supabase connected[/green]")
    except Exception as e:
        console.print(f"[red]✗ Supabase connection failed: {e}[/red]")
        sys.exit(1)

    # Create batch ID
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    console.print(f"[cyan]Batch ID: {batch_id}[/cyan]\n")

    # Initialize pipeline components
    budget_tracker = BudgetTracker(redis, batch_id, args.budget)
    state_manager = StateManager(redis, supabase)
    orchestrator = SupervisedOrchestrator(state_manager, budget_tracker)

    # Fetch companies
    try:
        companies = await get_unenriched_companies(supabase, args.limit)
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch companies: {e}[/red]")
        await redis.aclose()
        sys.exit(1)

    if not companies:
        console.print("[yellow]No companies found needing enrichment. Exiting.[/yellow]")
        await redis.aclose()
        sys.exit(0)

    # Initialize batch in budget tracker
    await budget_tracker.init_batch(len(companies))

    # Display header
    display_header(args.budget, args.batch_size, len(companies))

    # Main processing loop
    batch_num = 0
    total_processed = 0
    all_results = []
    user_stopped = False

    while total_processed < len(companies):
        # Check budget
        if not await budget_tracker.can_proceed():
            console.print("\n[red]Budget exceeded! Stopping pipeline.[/red]")
            await budget_tracker.set_stop_reason("budget_exceeded")
            break

        # Get next batch
        batch_start = total_processed
        batch_end = min(batch_start + args.batch_size, len(companies))
        batch = companies[batch_start:batch_end]
        batch_num += 1

        console.print(f"\n[bold cyan]Processing Batch #{batch_num}[/bold cyan] ({len(batch)} companies)")

        # Process batch with progress spinner
        with console.status(f"[bold green]Enriching {len(batch)} companies...", spinner="dots"):
            try:
                batch_results = await orchestrator.process_batch(batch)
                all_results.extend(batch_results)
            except Exception as e:
                console.print(f"[red]✗ Batch processing failed: {e}[/red]")
                # Continue to next batch
                batch_results = []

        # Display results
        if batch_results:
            display_results_table(batch_results, batch_num)

        # Update progress
        total_processed = batch_end

        # Display budget status
        budget_status = await budget_tracker.get_status()
        spent = budget_status.get("spent_usd", 0.0)
        remaining = args.budget - spent
        percent_used = (spent / args.budget * 100) if args.budget > 0 else 0

        status_text = (
            f"[bold]Budget:[/bold] "
            f"[blue]${spent:.4f}[/blue] / [green]${args.budget:.2f}[/green] "
            f"([yellow]{percent_used:.1f}%[/yellow] used) | "
            f"[bold]Progress:[/bold] {total_processed}/{len(companies)} companies"
        )
        console.print(Panel(status_text, border_style="blue"))

        # Check if done
        if total_processed >= len(companies):
            console.print("\n[green]All companies processed![/green]")
            break

        # Prompt for action
        action = prompt_action()

        if action == "c":
            # Continue to next batch
            continue
        elif action == "s":
            # Stop gracefully
            console.print("\n[yellow]Stopping pipeline. Results saved.[/yellow]")
            await budget_tracker.set_stop_reason("user_stopped")
            user_stopped = True
            break
        elif action == "v":
            # View detailed results
            display_detailed_results(all_results)
            # Ask again after viewing
            action = prompt_action()
            if action == "s" or action == "q":
                user_stopped = True
                break
            elif action == "c":
                continue  # Continue to next batch
        elif action == "q":
            # Quit immediately
            console.print("\n[red]Quitting without save.[/red]")
            await redis.aclose()
            sys.exit(0)

    # Final summary
    console.print("\n[bold cyan]Pipeline Summary[/bold cyan]\n")

    total_cost = sum(r.get("total_cost_usd", 0.0) for r in all_results)
    successful = sum(1 for r in all_results if r.get("success", False))
    failed = len(all_results) - successful
    total_contacts = sum(len(r.get("contacts", [])) for r in all_results)

    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")

    summary_table.add_row("Companies Processed", str(total_processed))
    summary_table.add_row("Successful", str(successful))
    summary_table.add_row("Failed", str(failed))
    summary_table.add_row("Total Contacts Found", str(total_contacts))
    summary_table.add_row("Total Cost", f"${total_cost:.4f}")
    summary_table.add_row("Budget Remaining", f"${args.budget - total_cost:.4f}")

    console.print(summary_table)

    # Cleanup
    await redis.aclose()
    console.print("\n[green]✓ Session complete[/green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)
