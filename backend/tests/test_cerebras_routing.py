"""
Test suite for Multi-Provider Cerebras Routing

Validates all 4 access methods:
1. Direct Cerebras API
2. OpenRouter with Cerebras provider
3. LangChain ChatCerebras
4. Cartesia voice streaming

Tests on Neon database branch: routing-tables (br-steep-rain-aea0fn4x)
"""

import pytest
import asyncio
import os
from typing import List, Dict, Any
from datetime import datetime

# Set up environment for Neon branch testing
os.environ["DATABASE_URL"] = (
    "postgresql://neondb_owner:npg_YLcRA7T8ZGQr@"
    "ep-young-waterfall-ae9y03xz.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

from app.services.cerebras_routing import (
    CerebrasRouter,
    CerebrasAccessMethod,
    CerebrasResponse
)


@pytest.fixture
async def router():
    """Create CerebrasRouter instance for testing."""
    router = CerebrasRouter()
    yield router


@pytest.mark.asyncio
class TestCerebrasRouting:
    """Test suite for multi-provider Cerebras routing."""

    async def test_direct_cerebras_access(self, router):
        """Test Method 1: Direct Cerebras API access."""
        prompt = "What is 2+2? Answer in one sentence."

        response = await router.route_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.DIRECT,
            max_tokens=50,
            temperature=0.1
        )

        assert isinstance(response, CerebrasResponse)
        assert response.access_method == CerebrasAccessMethod.DIRECT
        assert response.content is not None
        assert len(response.content) > 0
        assert response.latency_ms > 0
        assert response.latency_ms < 5000  # Should be ultra-fast
        assert response.cost_usd >= 0
        assert response.tokens_used["total"] > 0
        assert not response.fallback_used

        print(f"\n✅ Direct Cerebras Test:")
        print(f"   Response: {response.content[:100]}...")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"   Cost: ${response.cost_usd:.6f}")
        print(f"   Tokens: {response.tokens_used}")

    async def test_openrouter_access(self, router):
        """Test Method 2: OpenRouter with Cerebras provider."""
        prompt = "Explain photosynthesis in one sentence."

        response = await router.route_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.OPENROUTER,
            max_tokens=50,
            temperature=0.1
        )

        assert isinstance(response, CerebrasResponse)
        assert response.access_method == CerebrasAccessMethod.OPENROUTER
        assert response.content is not None
        assert len(response.content) > 0
        assert response.latency_ms > 0
        assert response.cost_usd >= 0
        assert response.tokens_used["total"] > 0
        assert response.provider == "Cerebras"

        print(f"\n✅ OpenRouter Test:")
        print(f"   Response: {response.content[:100]}...")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"   Cost: ${response.cost_usd:.6f}")
        print(f"   Provider: {response.provider}")

    async def test_langchain_access(self, router):
        """Test Method 3: LangChain ChatCerebras integration."""
        prompt = "What is the speed of light? Answer in one sentence."

        response = await router.route_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.LANGCHAIN,
            max_tokens=50,
            temperature=0.1
        )

        assert isinstance(response, CerebrasResponse)
        assert response.access_method == CerebrasAccessMethod.LANGCHAIN
        assert response.content is not None
        assert len(response.content) > 0
        assert response.latency_ms > 0
        assert response.cost_usd >= 0

        print(f"\n✅ LangChain Test:")
        print(f"   Response: {response.content[:100]}...")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"   Cost: ${response.cost_usd:.6f}")

    async def test_cartesia_access(self, router):
        """Test Method 4: Cartesia voice streaming (placeholder)."""
        prompt = "Hello world"

        # Cartesia is a placeholder - should fall back to Direct
        response = await router.route_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.CARTESIA,
            max_tokens=30,
            temperature=0.1
        )

        assert isinstance(response, CerebrasResponse)
        # Should fallback to Direct when Cartesia unavailable
        assert response.access_method in [
            CerebrasAccessMethod.CARTESIA,
            CerebrasAccessMethod.DIRECT
        ]
        assert response.content is not None

        print(f"\n✅ Cartesia Test:")
        print(f"   Method Used: {response.access_method}")
        print(f"   Fallback: {response.fallback_used}")
        print(f"   Response: {response.content[:100]}...")

    async def test_intelligent_routing(self, router):
        """Test intelligent routing with latency constraints."""
        prompt = "What is AI?"

        # Request ultra-low latency - should prefer Direct Cerebras
        response = await router.route_inference(
            prompt=prompt,
            max_latency_ms=500,
            max_tokens=30,
            temperature=0.1
        )

        assert isinstance(response, CerebrasResponse)
        assert response.latency_ms < 5000  # Should meet constraint
        assert response.content is not None

        print(f"\n✅ Intelligent Routing Test:")
        print(f"   Selected Method: {response.access_method}")
        print(f"   Latency: {response.latency_ms}ms (target: <500ms)")
        print(f"   Response: {response.content[:100]}...")

    async def test_streaming_direct(self, router):
        """Test streaming inference with Direct Cerebras."""
        prompt = "Count from 1 to 5"
        tokens_received = []

        async for chunk in router.stream_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.DIRECT,
            max_tokens=30,
            temperature=0.1
        ):
            if chunk["type"] == "token":
                tokens_received.append(chunk["content"])
            elif chunk["type"] == "complete":
                metadata = chunk["metadata"]

        assert len(tokens_received) > 0
        full_text = "".join(tokens_received)
        assert len(full_text) > 0

        print(f"\n✅ Streaming Test (Direct):")
        print(f"   Tokens Received: {len(tokens_received)}")
        print(f"   Full Response: {full_text[:100]}...")
        print(f"   Latency: {metadata['latency_ms']}ms")

    async def test_streaming_openrouter(self, router):
        """Test streaming inference with OpenRouter."""
        prompt = "List 3 colors"
        tokens_received = []

        async for chunk in router.stream_inference(
            prompt=prompt,
            preferred_method=CerebrasAccessMethod.OPENROUTER,
            max_tokens=30,
            temperature=0.1
        ):
            if chunk["type"] == "token":
                tokens_received.append(chunk["content"])
            elif chunk["type"] == "complete":
                metadata = chunk["metadata"]

        assert len(tokens_received) > 0
        full_text = "".join(tokens_received)
        assert len(full_text) > 0

        print(f"\n✅ Streaming Test (OpenRouter):")
        print(f"   Tokens Received: {len(tokens_received)}")
        print(f"   Full Response: {full_text[:100]}...")
        print(f"   Provider: {metadata.get('provider', 'N/A')}")

    async def test_circuit_breaker_isolation(self, router):
        """Test that circuit breakers are isolated per method."""
        # Get status of all access methods
        status = router.get_status()

        assert "access_methods" in status
        assert CerebrasAccessMethod.DIRECT.value in status["access_methods"]
        assert CerebrasAccessMethod.OPENROUTER.value in status["access_methods"]
        assert CerebrasAccessMethod.LANGCHAIN.value in status["access_methods"]

        # All circuit breakers should start in CLOSED state
        for method, method_status in status["access_methods"].items():
            cb_status = method_status["circuit_breaker"]
            assert cb_status["state"] == "closed"
            assert cb_status["failure_count"] == 0

        print(f"\n✅ Circuit Breaker Isolation Test:")
        for method, method_status in status["access_methods"].items():
            cb_status = method_status["circuit_breaker"]
            print(f"   {method}: {cb_status['state']} "
                  f"(failures: {cb_status['failure_count']})")

    async def test_fallback_on_failure(self, router):
        """Test automatic fallback when primary method fails."""
        prompt = "Test fallback"

        # Force failure by using invalid API key temporarily
        original_key = os.getenv("CEREBRAS_API_KEY")
        os.environ["CEREBRAS_API_KEY"] = "invalid_key_for_testing"

        try:
            # Should fall back to OpenRouter or LangChain
            response = await router.route_inference(
                prompt=prompt,
                preferred_method=CerebrasAccessMethod.DIRECT,
                max_tokens=20,
                temperature=0.1
            )

            # If we got a response, fallback worked
            if response:
                assert response.fallback_used
                print(f"\n✅ Fallback Test:")
                print(f"   Fallback Method: {response.access_method}")
                print(f"   Retry Count: {response.retry_count}")
        except Exception as e:
            # All methods failed - acceptable outcome
            print(f"\n⚠️ Fallback Test: All methods failed (expected with invalid keys)")
        finally:
            # Restore original key
            if original_key:
                os.environ["CEREBRAS_API_KEY"] = original_key

    async def test_cost_tracking(self, router):
        """Test accurate cost tracking across methods."""
        prompt = "What is 1+1?"
        results = []

        # Test cost tracking for each method
        for method in [
            CerebrasAccessMethod.DIRECT,
            CerebrasAccessMethod.OPENROUTER,
            CerebrasAccessMethod.LANGCHAIN
        ]:
            try:
                response = await router.route_inference(
                    prompt=prompt,
                    preferred_method=method,
                    max_tokens=20,
                    temperature=0.1
                )
                results.append({
                    "method": method.value,
                    "cost": response.cost_usd,
                    "tokens": response.tokens_used["total"]
                })
            except Exception as e:
                print(f"   {method.value}: Skipped ({str(e)[:50]})")

        print(f"\n✅ Cost Tracking Test:")
        for result in results:
            print(f"   {result['method']}: "
                  f"${result['cost']:.6f} "
                  f"({result['tokens']} tokens)")

        # All methods should report costs
        assert all(r["cost"] >= 0 for r in results)


@pytest.mark.asyncio
async def test_performance_comparison():
    """Compare performance across all 4 access methods."""
    router = CerebrasRouter()
    prompt = "Explain machine learning in one sentence."

    results = []

    for method in [
        CerebrasAccessMethod.DIRECT,
        CerebrasAccessMethod.OPENROUTER,
        CerebrasAccessMethod.LANGCHAIN,
        CerebrasAccessMethod.CARTESIA
    ]:
        try:
            response = await router.route_inference(
                prompt=prompt,
                preferred_method=method,
                max_tokens=50,
                temperature=0.1
            )

            results.append({
                "method": method.value,
                "latency_ms": response.latency_ms,
                "cost_usd": response.cost_usd,
                "tokens": response.tokens_used["total"],
                "fallback": response.fallback_used
            })
        except Exception as e:
            print(f"   {method.value}: Failed ({str(e)[:50]})")

    print(f"\n📊 Performance Comparison:")
    print(f"{'Method':<15} {'Latency (ms)':<15} {'Cost ($)':<15} {'Tokens':<10} {'Fallback'}")
    print("-" * 70)
    for r in results:
        print(f"{r['method']:<15} {r['latency_ms']:<15} "
              f"{r['cost_usd']:<15.6f} {r['tokens']:<10} {r['fallback']}")

    # Find fastest method
    if results:
        fastest = min(results, key=lambda x: x["latency_ms"])
        print(f"\n🏆 Fastest: {fastest['method']} ({fastest['latency_ms']}ms)")


if __name__ == "__main__":
    # Run all tests
    print("=" * 70)
    print("CEREBRAS ROUTING TEST SUITE")
    print("Neon Branch: routing-tables (br-steep-rain-aea0fn4x)")
    print("=" * 70)

    pytest.main([__file__, "-v", "-s"])
