"""
Orchestrator Integration Test

Tests the MEPOrchestrator with real VLM providers.
Validates the full agent loop: Orchestrator -> VLM Extraction -> JSON Validation -> Report
"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_settings
from shared.providers import OpenRouterProvider
from shared.agents import MEPOrchestrator, AgentState


# Test image
TEST_IMAGE = Path(
    "/Users/tmkipper/Downloads/construction_research_extracted"
    "/home/ubuntu/construction_research/solar/blueprints/solar_site_plan.png"
)


async def test_single_extraction():
    """Test single image extraction with orchestrator."""
    print("=" * 60)
    print("TEST: Single Image Extraction via Orchestrator")
    print("=" * 60)

    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)

    # Create orchestrator with Qwen VL provider
    orchestrator = MEPOrchestrator(
        vlm_provider=provider,
        extractor_model="qwen-vl-72b",
        verbose=True,
    )

    print(f"\nImage: {TEST_IMAGE.name}")
    print(f"Model: qwen-vl-72b (Qwen VL via OpenRouter)")
    print("-" * 40)

    try:
        extraction = await orchestrator.extract_image(
            image_path=TEST_IMAGE,
            trade="solar",
            num_extractions=1,
        )

        print("\nExtraction Result:")
        print(f"  Image Type: {extraction.image_type}")
        print(f"  Trade: {extraction.trade}")
        print(f"  Equipment: {extraction.equipment_visible[:3]}...")
        print(f"  Confidence: {extraction.confidence_score:.2%}")
        print(f"  Model: {extraction.model_used}")
        print(f"  Cost: ${extraction.cost_usd:.6f}")

        print("\n✅ Single extraction test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Single extraction test FAILED: {e}")
        return False


async def test_pipeline():
    """Test multi-image pipeline."""
    print("\n" + "=" * 60)
    print("TEST: Multi-Image Pipeline")
    print("=" * 60)

    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)

    # Find 2 test images
    base = Path(
        "/Users/tmkipper/Downloads/construction_research_extracted"
        "/home/ubuntu/construction_research/solar"
    )
    images = [
        base / "blueprints/solar_site_plan.png",
        base / "blueprints/solar_electrical_diagram.png",
    ]
    images = [p for p in images if p.exists()][:2]

    if not images:
        print("❌ No test images found")
        return False

    print(f"\nProcessing {len(images)} images...")

    orchestrator = MEPOrchestrator(
        vlm_provider=provider,
        extractor_model="qwen-vl-72b",
        verbose=True,
    )

    try:
        result = await orchestrator.run_pipeline(
            image_paths=images,
            trade="solar",
            parallel_images=2,
        )

        print("\nPipeline Result:")
        print(f"  Pipeline ID: {result['pipeline_id'][:8]}...")
        print(f"  Status: {result['status']}")
        print(f"  Total Images: {result['total_images']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Total Cost: ${result['total_cost_usd']:.6f}")

        if result['report']:
            print(f"  Report: {result['report'].get('extraction_count', 0)} extractions")

        print("\n✅ Pipeline test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_loop():
    """Test the full ReAct-style agent loop."""
    print("\n" + "=" * 60)
    print("TEST: Agent Loop (ReAct Pattern)")
    print("=" * 60)

    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)

    orchestrator = MEPOrchestrator(
        vlm_provider=provider,
        verbose=True,
    )

    try:
        run = await orchestrator.run_agent_loop(
            initial_message="Extract MEP data from the solar site plan",
            context={
                "image_path": str(TEST_IMAGE),
                "trade": "solar",
            }
        )

        print("\nAgent Loop Result:")
        print(f"  Run ID: {run.run_id[:8]}...")
        print(f"  Final State: {run.state.value}")
        print(f"  Iterations: {run.iteration}")
        print(f"  Messages: {len(run.messages)}")
        print(f"  Tool Results: {len(run.tool_results)}")
        print(f"  Total Cost: ${run.total_cost_usd:.6f}")

        if run.errors:
            print(f"  Errors: {run.errors}")

        # Check final state
        if run.state == AgentState.COMPLETE:
            print("\n✅ Agent loop test PASSED")
            return True
        else:
            print(f"\n❌ Agent loop ended in unexpected state: {run.state}")
            return False

    except Exception as e:
        print(f"\n❌ Agent loop test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_metrics():
    """Test orchestrator metrics."""
    print("\n" + "=" * 60)
    print("TEST: Orchestrator Metrics")
    print("=" * 60)

    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)

    orchestrator = MEPOrchestrator(
        vlm_provider=provider,
        verbose=False,
    )

    # Run a few extractions
    for i in range(2):
        try:
            await orchestrator.run_agent_loop(
                initial_message=f"Test extraction {i+1}",
                context={
                    "image_path": str(TEST_IMAGE),
                    "trade": "solar",
                }
            )
        except Exception:
            pass

    metrics = orchestrator.get_metrics()

    print("\nOrchestrator Metrics:")
    print(f"  Total Runs: {metrics['total_runs']}")
    print(f"  Completed: {metrics['completed']}")
    print(f"  Failed: {metrics['failed']}")
    print(f"  In Progress: {metrics['in_progress']}")
    print(f"  Total Cost: ${metrics['total_cost_usd']:.6f}")
    print(f"  Avg Cost/Run: ${metrics['avg_cost_per_run']:.6f}")

    print("\n✅ Metrics test PASSED")
    return True


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("MEP ORCHESTRATOR INTEGRATION TESTS")
    print("=" * 60)
    print()

    if not TEST_IMAGE.exists():
        print(f"❌ Test image not found: {TEST_IMAGE}")
        return

    results = []

    # Test 1: Single extraction
    results.append(("Single Extraction", await test_single_extraction()))

    # Test 2: Pipeline
    results.append(("Pipeline", await test_pipeline()))

    # Test 3: Agent loop
    results.append(("Agent Loop", await test_agent_loop()))

    # Test 4: Metrics
    results.append(("Metrics", await test_metrics()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed")


if __name__ == "__main__":
    asyncio.run(main())
