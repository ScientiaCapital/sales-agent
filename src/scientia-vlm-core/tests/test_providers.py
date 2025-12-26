#!/usr/bin/env python3
"""
Sequential Provider Validation - Scientia Capital VLM Audit

Run: python tests/test_providers.py

This script tests each VLM provider sequentially with interactive gates
for investor-grade validation of:
1. Cost comparison (Chinese VLMs vs Western baseline)
2. Accuracy parity
3. Latency metrics

Models to test:
- OpenRouter (Chinese VLMs): qwen3-vl-30b, qwen2.5-vl-72b, qwen-vl-max, glm-4.6v
- Anthropic 4.5: claude-sonnet, claude-opus, claude-haiku
- Gemini: 2.0-flash, 2.0-flash-lite, 2.5-flash, 2.5-pro, 3.0-flash
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.audit import AuditLogger, AuditRecord, Provider
from shared.config import get_settings

# Lazy import providers to avoid dependency errors when only importing constants
def get_providers():
    """Lazy import of provider classes to avoid runtime dependency errors."""
    from shared.providers import (
        OpenRouterProvider,
        AnthropicProvider,
        GeminiProvider,
    )
    return OpenRouterProvider, AnthropicProvider, GeminiProvider


# =============================================================================
# TEST CONFIGURATION - 504 Test Matrix (12 models × 42 images)
# =============================================================================

# Image base path
BASE_PATH = Path("/Users/tmkipper/Downloads/construction_research_extracted/home/ubuntu/construction_research")

# Trade image definitions (42 total images)
TRADES = {
    "solar": {
        "blueprints": [
            "solar_site_plan.png",
            "solar_electrical_diagram.png",
            "solar_design_layout.png",
            "solar_system_design.jpg",
        ],
        "field_photos": [
            "solar_roof_installation.jpg",
            "solar_site_assessment_roof.jpg",
            "solar_electrical_panel.jpg",
            "solar_ground_mount.jpg",
        ],
    },
    "electrical": {
        "blueprints": [
            "electrical_single_line_diagram.jpg",
            "electrical_floor_plan.jpg",
            "electrical_symbols_legend.jpg",
            "electrical_panel_schedule.jpg",
        ],
        "field_photos": [
            "electrical_panel_labels.jpg",
            "electrical_panel_interior.jpg",
            "electrical_panel_breakers.jpg",
            "electrical_service_upgrade.jpg",
        ],
    },
    "hvac": {
        "blueprints": [
            "hvac_ductwork_layout.png",
            "hvac_symbols_legend.png",
            "hvac_equipment_symbols.jpg",
            "hvac_floor_plan.jpg",
        ],
        "field_photos": [
            "hvac_mechanical_room.jpg",
            "hvac_american_standard_label.jpg",
            "hvac_equipment_label.jpg",
        ],
    },
    "roofing": {
        "blueprints": [
            "roof_pitch_chart.png",
            "roof_framing_plan.jpg",
            "architectural_symbols.png",
            "roof_plan_hip.png",
        ],
        "field_photos": [
            "roof_hail_damage_closeup.jpg",
            "roof_hail_damage_multiple.jpg",
            "roof_shingle_damage_closeup.jpg",
            "roof_storm_damage_overview.jpg",
        ],
    },
    "plumbing": {
        "blueprints": [
            "plumbing_isometric_detailed.png",
            "plumbing_symbols_legend.jpg",
            "plumbing_floor_plan.jpg",
            "plumbing_isometric_drawing.jpg",
        ],
        "field_photos": [
            "tankless_water_heater_installation.jpg",
            "water_heater_label_gama.jpg",
            "water_heater_serial_number.jpg",
            "water_heater_rating_plate.jpg",
        ],
    },
    "edge_cases": {
        "blueprints": [
            "vintage_mechanical_blueprint.jpg",
            "faded_blueprint_poor_quality.png",
            "vintage_hand_drawn_blueprints.jpg",
        ],
        "field_photos": [],
    },
}

# Model definitions - Chinese VLMs via OpenRouter (paid tier)
OPENROUTER_MODELS = [
    "qwen/qwen3-vl-30b-a3b-instruct",
    "qwen/qwen2.5-vl-72b-instruct",
    "qwen/qwen-vl-max",
    "z-ai/glm-4.6v",
    "moonshotai/kimi-vl-a3b-thinking",  # Moonshot Kimi VL
]

ANTHROPIC_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-5-haiku-20241022",
]

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.0-flash",
]

ALL_MODELS = {
    "openrouter": OPENROUTER_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "gemini": GEMINI_MODELS,
}

# Test prompt for VLM audit
TEST_PROMPT = """Analyze this construction/trade image and extract the following information as JSON:

{
    "image_type": "field_photo|blueprint|label|diagram",
    "trade": "hvac|electrical|plumbing|roofing|solar|general",
    "equipment_visible": ["list of equipment/components seen"],
    "key_details": {
        "manufacturer": "if visible",
        "model": "if visible",
        "serial_number": "if visible",
        "specifications": {}
    },
    "condition_assessment": "good|fair|poor|unknown",
    "notes": "any additional observations"
}

Be thorough but only include fields you can confidently extract from the image."""

# Models to test in order - FULL STACK AUDIT
TEST_MATRIX = [
    # ==========================================================================
    # OPENROUTER - Chinese VLMs (COST LEADERS) - The margin story
    # ==========================================================================
    ("openrouter", "qwen/qwen3-vl-30b-a3b-instruct", "solar"),      # Audit winner
    ("openrouter", "qwen/qwen2.5-vl-72b-instruct", "electrical"),   # Budget fallback
    ("openrouter", "qwen/qwen-vl-max", "hvac"),                     # High accuracy
    ("openrouter", "z-ai/glm-4.6v", "roofing"),                     # Chart specialist

    # ==========================================================================
    # ANTHROPIC 4.5 - Premium Western Baseline (accuracy reference)
    # ==========================================================================
    ("anthropic", "claude-sonnet-4-5-20250514", "plumbing"),
    ("anthropic", "claude-opus-4-5-20250514", "solar"),
    ("anthropic", "claude-haiku-4-5-20250514", "electrical"),

    # ==========================================================================
    # GEMINI - Alternative Western Baseline (cost/quality spectrum)
    # ==========================================================================
    ("gemini", "gemini-2.0-flash", "hvac"),
    ("gemini", "gemini-2.0-flash-lite", "roofing"),
    ("gemini", "gemini-2.5-flash", "plumbing"),
    ("gemini", "gemini-2.5-pro", "solar"),
    ("gemini", "gemini-3.0-flash", "electrical"),
]


# =============================================================================
# TEST RUNNER
# =============================================================================

async def run_single_test(
    provider_name: str,
    model: str,
    trade: str,
    settings,
    logger: AuditLogger,
    session_id: str,
) -> AuditRecord:
    """Run a single provider test with full audit logging."""

    print(f"\n{'='*60}")
    print(f"TESTING: {provider_name} / {model}")
    print(f"Trade: {trade}")
    print(f"{'='*60}")

    # Get test image
    test_image = settings.get_test_image(trade, "field_photos")
    if not test_image:
        test_image = settings.get_test_image(trade, "blueprints")

    if not test_image:
        print(f"⚠️  No test image found for trade: {trade}")
        # Use a default image
        all_images = settings.get_all_test_images()
        for t, images in all_images.items():
            if images:
                test_image = images[0]
                trade = t
                break

    print(f"Image: {test_image}")

    # Get provider classes
    OpenRouterProvider, AnthropicProvider, GeminiProvider = get_providers()

    # Initialize provider
    if provider_name == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    elif provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    elif provider_name == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        provider = GeminiProvider(api_key=settings.google_api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    # Run audit analysis
    record = await provider.audit_analyze(
        image_path=test_image,
        prompt=TEST_PROMPT,
        model=model,
        trade=trade,
        session_id=session_id,
    )

    # Log the record
    logger.log(record)

    return record


async def run_all_tests(interactive: bool = True):
    """Run all provider tests sequentially with gate reviews."""

    print("\n" + "=" * 60)
    print("SCIENTIA CAPITAL VLM PROVIDER AUDIT")
    print("Investor-Grade Validation")
    print("=" * 60)

    # Load settings
    settings = get_settings()

    # Validate API keys
    key_status = settings.validate_provider_keys()
    print("\nAPI Key Status:")
    for provider, available in key_status.items():
        status = "✅" if available else "❌"
        print(f"  {status} {provider}")

    # Initialize logger
    logger = AuditLogger(repo_name="vlm-ai-core")
    session_id = str(uuid4())

    print(f"\nSession ID: {session_id}")
    print(f"Audit dir: {logger.audit_dir}")

    # Track results
    results = []
    failed = []

    # Run tests
    for i, (provider_name, model, trade) in enumerate(TEST_MATRIX):
        test_num = i + 1
        total = len(TEST_MATRIX)

        print(f"\n[Test {test_num}/{total}]")

        # Check if provider key is available
        provider_key_map = {
            "openrouter": settings.openrouter_api_key,
            "anthropic": settings.anthropic_api_key,
            "gemini": settings.google_api_key,
        }

        if not provider_key_map.get(provider_name):
            print(f"⏭️  Skipping {provider_name}/{model} - API key not configured")
            continue

        try:
            record = await run_single_test(
                provider_name=provider_name,
                model=model,
                trade=trade,
                settings=settings,
                logger=logger,
                session_id=session_id,
            )
            results.append(record)

            # Print gate summary
            logger.print_gate_summary(record)

            # Interactive gate
            if interactive:
                try:
                    input()  # Wait for Enter
                    print("✅ Gate approved - continuing...")
                except KeyboardInterrupt:
                    print("\n❌ Audit aborted by user")
                    break

        except Exception as e:
            print(f"❌ FAILED: {type(e).__name__}: {e}")
            failed.append((provider_name, model, str(e)))

            if interactive:
                try:
                    print("\nPress Enter to continue to next test, or Ctrl+C to abort...")
                    input()
                except KeyboardInterrupt:
                    print("\n❌ Audit aborted by user")
                    break

    # Print final summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)

    print(f"\nTotal tests: {len(TEST_MATRIX)}")
    print(f"Passed: {len(results)}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {len(TEST_MATRIX) - len(results) - len(failed)}")

    if results:
        # Cost comparison
        chinese_costs = [r.cost.total_cost_usd for r in results if r.model.is_chinese_vlm]
        western_costs = [r.cost.total_cost_usd for r in results if not r.model.is_chinese_vlm]

        if chinese_costs and western_costs:
            avg_chinese = sum(chinese_costs) / len(chinese_costs)
            avg_western = sum(western_costs) / len(western_costs)
            savings = ((avg_western - avg_chinese) / avg_western) * 100

            print(f"\n💰 COST ANALYSIS:")
            print(f"   Chinese VLM avg: ${avg_chinese:.6f}")
            print(f"   Western avg: ${avg_western:.6f}")
            print(f"   SAVINGS: {savings:.1f}%")

    if failed:
        print(f"\n❌ FAILURES:")
        for provider, model, error in failed:
            print(f"   - {provider}/{model}: {error}")

    print(f"\n📁 Audit files written to: {logger.audit_dir}")
    print(f"   - test_runs.jsonl")
    print(f"   - test_runs.csv")
    print(f"   - model_registry.json")

    return results, failed


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VLM Provider Audit")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Run without interactive gates"
    )
    args = parser.parse_args()

    results, failed = asyncio.run(run_all_tests(interactive=not args.no_interactive))

    # Exit with error code if any failures
    sys.exit(1 if failed else 0)
