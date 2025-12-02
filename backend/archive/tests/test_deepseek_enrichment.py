"""Quick test of EnrichmentAgent with DeepSeek via OpenRouter"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent

async def test_enrichment():
    print("Testing EnrichmentAgent with DeepSeek via OpenRouter...")
    print(f"OPENROUTER_API_KEY present: {bool(os.getenv('OPENROUTER_API_KEY'))}")

    agent = EnrichmentAgent(
        provider="openrouter",
        model="deepseek/deepseek-chat"
    )

    print("\nEnriching EMCOR Group...")
    result = await agent.enrich({
        "company_name": "EMCOR Group",
        "website": "emcorgroup.com",
        "industry": "MEP Contractor"
    })

    # EnrichmentResult is a Pydantic model, not a dict
    print(f"\nResult type: {type(result)}")
    print(f"Success: {result.success}")
    print(f"Contacts: {len(result.contacts) if result.contacts else 0}")
    if result.contacts:
        for c in result.contacts[:5]:
            print(f"  - {c.name} ({c.title}) - {c.email}")
    if result.error:
        print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_enrichment())
