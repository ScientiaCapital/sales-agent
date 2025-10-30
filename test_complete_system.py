"""
Comprehensive System Test
Tests A/B Testing API, LangGraph Agents, and Dealer Integration
"""

import httpx
import asyncio
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
BASE_URL = "http://localhost:8001/api/v1"


async def test_health():
    """Test basic health endpoint"""
    console.print("\n[bold cyan]1. Testing Health Endpoint[/bold cyan]")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

        if response.status_code == 200:
            console.print("✅ Health check passed", style="green")
            console.print(json.dumps(response.json(), indent=2))
            return True
        else:
            console.print(f"❌ Health check failed: {response.status_code}", style="red")
            return False


async def test_ab_test_api():
    """Test A/B Testing API endpoints"""
    console.print("\n[bold cyan]2. Testing A/B Test API[/bold cyan]")

    async with httpx.AsyncClient() as client:
        # Create an A/B test
        console.print("\n📝 Creating A/B test...")
        create_data = {
            "test_name": "Email Subject Line Test",
            "test_description": "Testing short vs long subject lines",
            "variant_a_name": "Short Subject",
            "variant_b_name": "Long Subject",
            "test_type": "campaign",
            "campaign_id": 1
        }

        create_response = await client.post(
            f"{BASE_URL}/ab-tests",
            json=create_data,
            timeout=30.0
        )

        if create_response.status_code != 201:
            console.print(f"❌ Create failed: {create_response.status_code}", style="red")
            console.print(create_response.text)
            return False

        test = create_response.json()
        test_id = test["test_id"]
        console.print(f"✅ Created test: {test_id}", style="green")

        # Start the test
        console.print(f"\n▶️  Starting test {test_id}...")
        start_response = await client.post(f"{BASE_URL}/ab-tests/{test_id}/start")
        if start_response.status_code == 200:
            console.print("✅ Test started", style="green")

        # Update metrics
        console.print("\n📊 Updating test metrics...")
        update_data = {
            "participants_a": 100,
            "participants_b": 100,
            "conversions_a": 15,  # 15% conversion
            "conversions_b": 25   # 25% conversion (significant difference)
        }
        update_response = await client.patch(
            f"{BASE_URL}/ab-tests/{test_id}",
            json=update_data
        )
        if update_response.status_code == 200:
            console.print("✅ Metrics updated", style="green")

        # Get statistical analysis
        console.print("\n🔬 Running statistical analysis...")
        analysis_response = await client.get(f"{BASE_URL}/ab-tests/{test_id}/analysis")

        if analysis_response.status_code == 200:
            analysis = analysis_response.json()

            # Display results in a table
            table = Table(title="A/B Test Statistical Analysis")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Test Name", analysis["test_name"])
            table.add_row("Variant A Rate", f"{analysis['variant_a_conversion_rate']:.2f}%")
            table.add_row("Variant B Rate", f"{analysis['variant_b_conversion_rate']:.2f}%")
            table.add_row("P-Value", f"{analysis['p_value']:.6f}")
            table.add_row("Significant?", "✅ Yes" if analysis["is_significant"] else "❌ No")
            table.add_row("Winner", analysis["winner"] or "None")
            table.add_row("Lift", f"{analysis['lift_percentage']:.2f}%")
            table.add_row("Sample Adequacy", f"{analysis['sample_adequacy']:.1f}%")

            console.print(table)
            console.print("\n[bold green]✅ A/B Test API: All tests passed![/bold green]")
            return True
        else:
            console.print(f"❌ Analysis failed: {analysis_response.status_code}", style="red")
            return False


async def test_qualification_agent():
    """Test QualificationAgent with Cerebras"""
    console.print("\n[bold cyan]3. Testing QualificationAgent (Cerebras + LangGraph)[/bold cyan]")

    async with httpx.AsyncClient() as client:
        console.print("\n🤖 Qualifying lead with ultra-fast Cerebras inference...")

        lead_data = {
            "company_name": "TechCorp Inc",
            "email": "john@techcorp.com",
            "company_size": "500",
            "industry": "Software",
            "signals": ["recent_funding", "high_growth"],
            "notes": "Enterprise SaaS company with $50M Series B"
        }

        response = await client.post(
            f"{BASE_URL}/leads/qualify",
            json=lead_data,
            timeout=30.0
        )

        if response.status_code == 200:
            result = response.json()

            table = Table(title="Lead Qualification Result")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Company", lead_data["company_name"])
            table.add_row("Score", f"{result.get('qualification_score', 0):.2f}")
            table.add_row("Tier", result.get('tier', 'Unknown'))
            table.add_row("Status", result.get('status', 'Unknown'))

            console.print(table)

            if "reasoning" in result:
                console.print("\n[bold]AI Reasoning:[/bold]")
                console.print(Panel(result["reasoning"], style="dim"))

            console.print("\n[bold green]✅ QualificationAgent: Working![/bold green]")
            return True
        else:
            console.print(f"❌ Qualification failed: {response.status_code}", style="red")
            console.print(response.text)
            return False


async def check_dealer_scraper_integration():
    """Check dealer-scraper-mvp integration"""
    console.print("\n[bold cyan]4. Checking Dealer Scraper Integration[/bold cyan]")

    import os
    dealer_scraper_path = "/Users/tmkipper/Desktop/dealer-scraper-mvp/output"

    if os.path.exists(dealer_scraper_path):
        console.print(f"✅ Found dealer-scraper at: {dealer_scraper_path}", style="green")

        # List available files
        files = os.listdir(dealer_scraper_path)
        md_files = [f for f in files if f.endswith('.md')]

        if md_files:
            console.print(f"\n📄 Found {len(md_files)} markdown files:")
            for file in md_files[:5]:  # Show first 5
                console.print(f"  • {file}", style="dim")

            # Check if we have ICP data
            console.print("\n💡 Ready to import dealer data via /leads/import/csv endpoint")
            return True
        else:
            console.print("⚠️  No markdown files found in output", style="yellow")
            return False
    else:
        console.print(f"❌ Dealer scraper path not found: {dealer_scraper_path}", style="red")
        return False


async def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold magenta]Sales Agent - Complete System Test[/bold magenta]\n"
        "Testing: A/B APIs, LangGraph Agents, Dealer Integration",
        border_style="magenta"
    ))

    results = []

    # Run all tests
    results.append(("Health Check", await test_health()))
    results.append(("A/B Test API", await test_ab_test_api()))
    results.append(("QualificationAgent", await test_qualification_agent()))
    results.append(("Dealer Integration", await check_dealer_scraper_integration()))

    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]")
    console.print("="*60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        console.print(f"{name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        console.print("\n[bold green]🎉 All tests passed! System ready for production.[/bold green]")
    else:
        console.print("\n[bold red]⚠️  Some tests failed. Check logs above.[/bold red]")

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
