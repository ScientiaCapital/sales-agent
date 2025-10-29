#!/usr/bin/env python3
"""
Interactive Agent CLI for Sales-Agent Platform

Provides terminal-based interaction with LangGraph agents:
- Qualification: Lead scoring with Cerebras AI
- Enrichment: Contact enrichment with Apollo/LinkedIn
- Conversation: Voice-enabled conversational AI

Usage:
    python agent_cli.py                    # Interactive mode
    python agent_cli.py --agent qualify    # Direct agent invocation
    python agent_cli.py --trace            # Enable LangSmith tracing
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.json import JSON
from rich.tree import Tree
import click

# Import agents
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.langgraph.agents.conversation_agent import ConversationAgent

console = Console()

class AgentCLI:
    """Interactive CLI for LangGraph agents."""
    
    def __init__(self, enable_tracing: bool = False):
        self.enable_tracing = enable_tracing
        self.conversation_thread_id = None
        
        # Set up LangSmith tracing if enabled
        if enable_tracing:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = "sales-agent-cli"
            console.print("[dim]LangSmith tracing enabled[/dim]")
        
    async def run(self):
        """Main CLI loop."""
        console.print(Panel.fit(
            "[bold cyan]Sales Agent CLI[/bold cyan]\n"
            "Interactive terminal for LangGraph agents",
            border_style="cyan"
        ))
        
        while True:
            choice = self.show_main_menu()
            
            if choice == "1":
                await self.run_qualification_agent()
            elif choice == "2":
                await self.run_enrichment_agent()
            elif choice == "3":
                await self.run_conversation_agent()
            elif choice == "4":
                console.print("[yellow]Exiting...[/yellow]")
                break
    
    def show_main_menu(self) -> str:
        """Display main menu and get user choice."""
        console.print("\n[bold]Select an agent:[/bold]")
        console.print("1. [green]Qualification Agent[/green] - Score leads (<1000ms)")
        console.print("2. [blue]Enrichment Agent[/blue] - Enrich contacts (<3000ms)")
        console.print("3. [magenta]Conversation Agent[/magenta] - Voice chat (<1000ms/turn)")
        console.print("4. [red]Exit[/red]")
        
        return Prompt.ask("Choice", choices=["1", "2", "3", "4"])
    
    async def run_qualification_agent(self):
        """Run QualificationAgent with user inputs."""
        console.print("\n[bold green]Qualification Agent[/bold green]")
        
        # Get inputs
        company_name = Prompt.ask("Company name")
        industry = Prompt.ask("Industry", default="")
        company_size = Prompt.ask("Company size", default="")
        
        # Execute with progress spinner
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Qualifying lead...", total=None)
            
            agent = QualificationAgent()
            result, latency_ms, metadata = await agent.qualify(
                company_name=company_name,
                industry=industry or None,
                company_size=company_size or None
            )
        
        # Display results
        self.display_qualification_result(result, latency_ms, metadata)
    
    async def run_enrichment_agent(self):
        """Run EnrichmentAgent with user inputs."""
        console.print("\n[bold blue]Enrichment Agent[/bold blue]")
        
        # Get inputs
        email = Prompt.ask("Email address", default="")
        linkedin_url = Prompt.ask("LinkedIn URL", default="")
        
        if not email and not linkedin_url:
            console.print("[red]Error: Provide at least email or LinkedIn URL[/red]")
            return
        
        # Execute with progress spinner
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Enriching contact...", total=None)
            
            agent = EnrichmentAgent()
            result = await agent.enrich(
                email=email or None,
                linkedin_url=linkedin_url or None
            )
        
        # Display results
        self.display_enrichment_result(result)
    
    async def run_conversation_agent(self):
        """Run ConversationAgent with multi-turn support."""
        console.print("\n[bold magenta]Conversation Agent[/bold magenta]")
        console.print("[dim]Type 'exit' to return to main menu[/dim]\n")
        
        agent = ConversationAgent()
        
        while True:
            user_input = Prompt.ask("[cyan]You[/cyan]")
            
            if user_input.lower() in ["exit", "quit", "q"]:
                break
            
            # Execute with progress spinner
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Thinking...", total=None)
                
                result = await agent.send_message(text=user_input)
            
            # Display response
            console.print(f"[green]Agent[/green]: {result.assistant_response}")
            console.print(f"[dim]({result.latency_breakdown['total_ms']}ms)[/dim]\n")
    
    def display_qualification_result(self, result, latency_ms, metadata):
        """Display formatted qualification results."""
        # Create results table
        table = Table(title="Qualification Results", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Score", f"{result.qualification_score}/100")
        table.add_row("Tier", result.tier.upper())
        table.add_row("Latency", f"{latency_ms}ms")
        table.add_row("Cost", f"${metadata['estimated_cost_usd']:.6f}")
        
        console.print(table)
        
        # Display reasoning
        console.print(f"\n[bold]Reasoning:[/bold]\n{result.qualification_reasoning}")
        
        # Display recommendations
        console.print("\n[bold]Recommendations:[/bold]")
        for i, rec in enumerate(result.recommendations, 1):
            console.print(f"  {i}. {rec}")
    
    def display_enrichment_result(self, result):
        """Display formatted enrichment results."""
        # Create tree for enriched data
        tree = Tree("[bold]Enriched Data[/bold]")
        
        for key, value in result.enriched_data.items():
            if isinstance(value, dict):
                branch = tree.add(f"[cyan]{key}[/cyan]")
                for k, v in value.items():
                    branch.add(f"{k}: {v}")
            elif isinstance(value, list):
                branch = tree.add(f"[cyan]{key}[/cyan]")
                for item in value:
                    branch.add(str(item))
            else:
                tree.add(f"[cyan]{key}[/cyan]: {value}")
        
        console.print(tree)
        
        # Display metadata
        console.print(f"\n[bold]Confidence:[/bold] {result.confidence_score:.2f}")
        console.print(f"[bold]Sources:[/bold] {', '.join(result.data_sources)}")
        console.print(f"[bold]Latency:[/bold] {result.latency_ms}ms")
        console.print(f"[bold]Cost:[/bold] ${result.total_cost_usd:.6f}")

@click.command()
@click.option('--agent', type=click.Choice(['qualify', 'enrich', 'converse']), help='Direct agent invocation')
@click.option('--trace/--no-trace', default=False, help='Enable LangSmith tracing')
def main(agent: Optional[str], trace: bool):
    """Interactive CLI for Sales-Agent LangGraph agents."""
    cli = AgentCLI(enable_tracing=trace)
    
    if agent:
        # Direct invocation mode
        if agent == 'qualify':
            asyncio.run(cli.run_qualification_agent())
        elif agent == 'enrich':
            asyncio.run(cli.run_enrichment_agent())
        elif agent == 'converse':
            asyncio.run(cli.run_conversation_agent())
    else:
        # Interactive mode
        asyncio.run(cli.run())

if __name__ == "__main__":
    main()
