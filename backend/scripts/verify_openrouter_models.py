"""
OpenRouter Model ID Verification Script

Fetches all available models from OpenRouter API and verifies exact identifiers
for our target Chinese AI models (DeepSeek, Qwen, Yi, Moonshot, Gemini).

Usage:
    python scripts/verify_openrouter_models.py

Requires:
    - OPENROUTER_API_KEY environment variable
"""

import requests
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


def fetch_all_models() -> List[Dict[str, Any]]:
    """Fetch all available models from OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment")

    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    print("📡 Fetching models from OpenRouter API...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    data = response.json()
    models = data.get("data", [])
    print(f"✅ Fetched {len(models)} models\n")

    return models


def verify_target_models(models: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Verify our target models and extract their details."""

    # Target model keywords to search for
    targets = {
        "deepseek_r1_distill": ["deepseek", "r1", "distill", "qwen"],
        "deepseek_v3": ["deepseek", "chat", "v3"],
        "deepseek_r1": ["deepseek", "r1"],
        "qwen_qwq": ["qwen", "qwq"],
        "gemini_flash": ["google", "gemini", "flash"],
        "yi_lightning": ["yi", "lightning"],
        "moonshot_kimi": ["moonshot", "kimi", "k2"],
    }

    verified = {}

    for model in models:
        model_id = model["id"]
        model_name = model.get("name", "")

        # Check each target category
        for category, keywords in targets.items():
            # Check if all keywords present in model ID or name (case-insensitive)
            if all(kw.lower() in model_id.lower() or kw.lower() in model_name.lower()
                   for kw in keywords):

                # Extract pricing
                pricing = model.get("pricing", {})
                prompt_cost = pricing.get("prompt", "0")
                completion_cost = pricing.get("completion", "0")

                # Store verified model info
                if category not in verified:
                    verified[category] = []

                verified[category].append({
                    "id": model_id,
                    "name": model_name,
                    "prompt_cost_per_1m": float(prompt_cost) * 1_000_000,
                    "completion_cost_per_1m": float(completion_cost) * 1_000_000,
                    "context_length": model.get("context_length", 0),
                    "is_free": ":free" in model_id,
                    "description": model.get("description", "")[:100]
                })

    return verified


def print_verification_results(verified: Dict[str, Dict[str, Any]]):
    """Print verification results in a readable format."""

    print("=" * 80)
    print("🔍 VERIFIED OPENROUTER MODEL IDs")
    print("=" * 80)
    print()

    # Priority order for our use cases
    priority_categories = [
        ("deepseek_r1_distill", "DeepSeek R1 Distill (EnrichmentAgent)"),
        ("qwen_qwq", "Qwen QwQ (GrowthAgent)"),
        ("gemini_flash", "Gemini Flash (ConversationAgent)"),
        ("yi_lightning", "Yi Lightning (MarketingAgent)"),
        ("moonshot_kimi", "Moonshot Kimi K2 (Premium Tier 1)"),
        ("deepseek_v3", "DeepSeek V3 (Current)"),
        ("deepseek_r1", "DeepSeek R1 (Full)"),
    ]

    for category, display_name in priority_categories:
        if category in verified and verified[category]:
            print(f"📦 {display_name}")
            print("-" * 80)

            models = verified[category]
            # Sort by: free first, then by prompt cost
            models.sort(key=lambda x: (not x["is_free"], x["prompt_cost_per_1m"]))

            for model in models:
                free_label = " [FREE]" if model["is_free"] else ""
                print(f"\nModel ID: {model['id']}{free_label}")
                print(f"  Name: {model['name']}")
                print(f"  Cost: ${model['prompt_cost_per_1m']:.6f}/1M input, ${model['completion_cost_per_1m']:.6f}/1M output")
                print(f"  Context: {model['context_length']:,} tokens")
                if model['description']:
                    print(f"  Description: {model['description']}")

            print()

    # Print summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    total_verified = sum(len(models) for models in verified.values())
    total_free = sum(1 for models in verified.values() for m in models if m["is_free"])
    print(f"Total models verified: {total_verified}")
    print(f"Free models found: {total_free}")
    print()


def save_verification_report(verified: Dict[str, Dict[str, Any]]):
    """Save verification report to markdown file."""

    output_path = Path(__file__).parent.parent.parent / "VERIFIED_MODEL_IDS.md"

    with open(output_path, 'w') as f:
        f.write("# Verified OpenRouter Model IDs\n\n")
        f.write(f"**Generated**: {Path(__file__).name}\n")
        f.write(f"**Date**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("This document contains verified model identifiers from OpenRouter API for use in our sales-agent system.\n\n")

        f.write("---\n\n")

        # Recommended models section
        f.write("## 🎯 Recommended Models for Implementation\n\n")

        recommendations = {
            "EnrichmentAgent": ("deepseek_r1_distill", "deepseek/deepseek-r1-distill-qwen-32b"),
            "GrowthAgent": ("qwen_qwq", "qwen/qwq-32b:free"),
            "ConversationAgent": ("gemini_flash", "google/gemini-2.0-flash-exp:free"),
            "MarketingAgent": ("yi_lightning", "01-ai/yi-lightning"),
            "Tier 1 Leads": ("moonshot_kimi", "moonshot/kimi-k2"),
        }

        for agent, (category, expected_id) in recommendations.items():
            if category in verified and verified[category]:
                models = verified[category]
                # Find exact match or best match
                exact_match = next((m for m in models if m["id"] == expected_id), None)
                best_match = exact_match or models[0]

                free_badge = " 🆓" if best_match["is_free"] else ""
                f.write(f"### {agent}{free_badge}\n\n")
                f.write(f"```python\n")
                f.write(f'"{best_match["id"]}"\n')
                f.write(f"```\n\n")
                f.write(f"- **Cost**: ${best_match['prompt_cost_per_1m']:.6f}/1M input, ${best_match['completion_cost_per_1m']:.6f}/1M output\n")
                f.write(f"- **Context**: {best_match['context_length']:,} tokens\n")
                if best_match['description']:
                    f.write(f"- **Description**: {best_match['description']}\n")
                f.write("\n")

        f.write("---\n\n")

        # Full listing
        f.write("## 📋 Complete Verified Models\n\n")

        for category, models in verified.items():
            if models:
                category_name = category.replace("_", " ").title()
                f.write(f"### {category_name}\n\n")

                for model in models:
                    free_badge = " 🆓 FREE" if model["is_free"] else ""
                    f.write(f"#### {model['name']}{free_badge}\n\n")
                    f.write(f"**Model ID**:\n```python\n\"{model['id']}\"\n```\n\n")
                    f.write(f"| Property | Value |\n")
                    f.write(f"|----------|-------|\n")
                    f.write(f"| Input Cost | ${model['prompt_cost_per_1m']:.6f}/1M tokens |\n")
                    f.write(f"| Output Cost | ${model['completion_cost_per_1m']:.6f}/1M tokens |\n")
                    f.write(f"| Context Window | {model['context_length']:,} tokens |\n")
                    if model['description']:
                        f.write(f"| Description | {model['description']} |\n")
                    f.write("\n")

        f.write("---\n\n")
        f.write("## 💡 Implementation Notes\n\n")
        f.write("1. **FREE models** (`:free` suffix): 20 req/min, 200 req/day limit\n")
        f.write("2. **Paid models**: No rate limits (subject to OpenRouter account limits)\n")
        f.write("3. **Model format**: `provider/model-name` (e.g., `deepseek/deepseek-r1-distill-qwen-32b`)\n")
        f.write("4. **Testing**: Always test with small batch before full rollout\n\n")

    print(f"💾 Verification report saved to: {output_path}\n")


def main():
    """Main verification flow."""
    try:
        # Fetch all models
        models = fetch_all_models()

        # Verify target models
        verified = verify_target_models(models)

        # Print results
        print_verification_results(verified)

        # Save report
        save_verification_report(verified)

        print("✅ Verification complete!")
        print(f"\n📖 See VERIFIED_MODEL_IDS.md for full details")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
