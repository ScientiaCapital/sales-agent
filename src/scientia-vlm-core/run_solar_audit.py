#!/usr/bin/env python3
"""
Phase 1 Solar Trade Audit - 96 Total Tests
8 solar images × 12 VLM models

This script runs all 12 VLM models against the 8 solar construction images.

Run: python run_solar_audit.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from shared.config import get_settings
from shared.audit import AuditLogger
from shared.providers import (
    OpenRouterProvider,
    AnthropicProvider,
    GeminiProvider,
)
from tests.test_providers import (
    BASE_PATH,
    OPENROUTER_MODELS,
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    TEST_PROMPT,
)


async def test_image_with_all_models(image_path: Path, trade: str, settings, logger, session_id):
    """Test one image with all 12 models."""
    results = []

    print(f"\n  Testing {image_path.name}...")

    # OpenRouter models
    if settings.openrouter_api_key:
        provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
        for model in OPENROUTER_MODELS:
            try:
                record = await provider.audit_analyze(
                    image_path=image_path,
                    prompt=TEST_PROMPT,
                    model=model,
                    trade=trade,
                    session_id=session_id,
                )
                logger.log(record)
                results.append((
                    "openrouter",
                    model,
                    record.accuracy.success,
                    record.cost.total_cost_usd,
                    record.latency.total_latency_ms,
                ))
                print(f"    ✓ {model}: ${record.cost.total_cost_usd:.6f} | {record.latency.total_latency_ms}ms")
            except Exception as e:
                print(f"    ✗ {model}: {e}")
                results.append(("openrouter", model, False, 0, 0))
            await asyncio.sleep(0.5)

    # Anthropic models (sequential due to rate limits)
    if settings.anthropic_api_key:
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        for model in ANTHROPIC_MODELS:
            try:
                record = await provider.audit_analyze(
                    image_path=image_path,
                    prompt=TEST_PROMPT,
                    model=model,
                    trade=trade,
                    session_id=session_id,
                )
                logger.log(record)
                results.append((
                    "anthropic",
                    model,
                    record.accuracy.success,
                    record.cost.total_cost_usd,
                    record.latency.total_latency_ms,
                ))
                print(f"    ✓ {model}: ${record.cost.total_cost_usd:.6f} | {record.latency.total_latency_ms}ms")
            except Exception as e:
                print(f"    ✗ {model}: {e}")
                results.append(("anthropic", model, False, 0, 0))
            await asyncio.sleep(1)  # Rate limit protection

    # Gemini models
    if settings.google_api_key:
        provider = GeminiProvider(api_key=settings.google_api_key)
        for model in GEMINI_MODELS:
            try:
                record = await provider.audit_analyze(
                    image_path=image_path,
                    prompt=TEST_PROMPT,
                    model=model,
                    trade=trade,
                    session_id=session_id,
                )
                logger.log(record)
                results.append((
                    "gemini",
                    model,
                    record.accuracy.success,
                    record.cost.total_cost_usd,
                    record.latency.total_latency_ms,
                ))
                print(f"    ✓ {model}: ${record.cost.total_cost_usd:.6f} | {record.latency.total_latency_ms}ms")
            except Exception as e:
                print(f"    ✗ {model}: {e}")
                results.append(("gemini", model, False, 0, 0))
            await asyncio.sleep(0.5)

    return results


async def run_solar_audit():
    """Run all 12 models against all 8 solar images."""
    settings = get_settings()
    logger = AuditLogger(repo_name="vlm-ai-core")
    session_id = str(uuid4())

    print("\n" + "=" * 70)
    print("PHASE 1: SOLAR TRADE VLM AUDIT")
    print("8 Images × 12 Models = 96 Total Tests")
    print("=" * 70)
    print(f"\nSession: {session_id}")
    print(f"Audit dir: {logger.audit_dir}")

    # Validate API keys
    key_status = settings.validate_provider_keys()
    print("\nAPI Key Status:")
    for provider, available in key_status.items():
        status = "✓" if available else "✗"
        print(f"  {status} {provider}")

    # Collect solar images
    solar_images = []
    for img_type in ["blueprints", "field_photos"]:
        for filename in [
            "solar_site_plan.png",
            "solar_electrical_diagram.png",
            "solar_design_layout.png",
            "solar_system_design.jpg",
            "solar_roof_installation.jpg",
            "solar_site_assessment_roof.jpg",
            "solar_electrical_panel.jpg",
            "solar_ground_mount.jpg",
        ]:
            path = BASE_PATH / "solar" / img_type / filename
            if path.exists():
                solar_images.append(path)

    print(f"\nSolar images found: {len(solar_images)}")
    for img in solar_images:
        print(f"  - {img.name}")

    # Run tests
    all_results = []
    for i, image_path in enumerate(solar_images, 1):
        print(f"\n[Image {i}/{len(solar_images)}] {image_path.name}")
        results = await test_image_with_all_models(image_path, "solar", settings, logger, session_id)
        all_results.extend(results)

    # Print summary
    print("\n" + "=" * 70)
    print("SOLAR TRADE AUDIT SUMMARY")
    print("=" * 70)

    total_tests = len(all_results)
    successes = sum(1 for r in all_results if r[2])
    success_rate = 100 * successes / total_tests if total_tests > 0 else 0

    print(f"\nTotal tests: {total_tests}")
    print(f"Successful: {successes}")
    print(f"Failed: {total_tests - successes}")
    print(f"Success rate: {success_rate:.1f}%")

    # Cost breakdown by provider
    print(f"\n{'Provider':<15} {'Tests':<8} {'Success':<10} {'Total Cost':<15} {'Avg Cost':<15} {'Avg Latency':<12}")
    print("-" * 75)

    for provider in ["openrouter", "anthropic", "gemini"]:
        provider_results = [r for r in all_results if r[0] == provider]
        if provider_results:
            tests = len(provider_results)
            successes = sum(1 for r in provider_results if r[2])
            total_cost = sum(r[3] for r in provider_results)
            avg_cost = total_cost / tests if tests > 0 else 0
            avg_latency = sum(r[4] for r in provider_results) / tests if tests > 0 else 0

            print(f"{provider:<15} {tests:<8} {successes}/{tests:<8} ${total_cost:<14.6f} ${avg_cost:<14.6f} {avg_latency:<11.0f}ms")

    # Overall summary
    total_cost = sum(r[3] for r in all_results)
    avg_latency = sum(r[4] for r in all_results) / len(all_results) if all_results else 0

    print("-" * 75)
    print(f"{'TOTAL':<15} {total_tests:<8} {successes}/{total_tests:<8} ${total_cost:<14.6f} {'':14s} {avg_latency:<11.0f}ms")

    print(f"\n📁 Audit logs written to: {logger.audit_dir}")
    print(f"   - test_runs.jsonl")
    print(f"   - test_runs.csv")
    print(f"   - model_registry.json")


if __name__ == "__main__":
    asyncio.run(run_solar_audit())
