#!/usr/bin/env python3
"""
Test streaming implementation - verifies Claude SDK streaming and model router
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from dotenv import load_dotenv
load_dotenv()

async def test_claude_streaming():
    """Test Claude streaming service"""
    from app.services.claude_streaming import ClaudeStreamingService

    print("\n🧪 Test 1: Claude Streaming Service")
    print("=" * 60)

    # Check if API key is configured
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not configured - skipping Claude test")
        return False

    try:
        service = ClaudeStreamingService()
        print(f"✅ Service initialized with model: {service.default_model}")

        prompt = "In exactly 3 sentences, explain what a circuit breaker pattern is in software engineering."

        print(f"\n📝 Prompt: {prompt}")
        print("\n🔄 Streaming response:")
        print("-" * 60)

        accumulated = ""
        token_count = 0

        async for chunk in service.stream_completion(
            prompt=prompt,
            temperature=0.7,
            max_tokens=200
        ):
            if chunk["type"] == "token":
                print(chunk["content"], end="", flush=True)
                accumulated += chunk["content"]
                token_count += 1
            elif chunk["type"] == "complete":
                print("\n" + "-" * 60)
                metadata = chunk["metadata"]
                print(f"\n✅ Streaming complete!")
                print(f"   • Total tokens streamed: {token_count}")
                print(f"   • Input tokens: {metadata['input_tokens']}")
                print(f"   • Output tokens: {metadata['output_tokens']}")
                print(f"   • Latency: {metadata['latency_ms']}ms")
                print(f"   • Cost: ${metadata['total_cost_usd']:.6f}")
            elif chunk["type"] == "error":
                print(f"\n❌ Error: {chunk['error']}")
                return False

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_model_router_streaming():
    """Test model router streaming with Cerebras"""
    from app.services.model_router import ModelRouter, TaskType

    print("\n🧪 Test 2: Model Router Streaming (Cerebras)")
    print("=" * 60)

    if not os.getenv("CEREBRAS_API_KEY"):
        print("⚠️  CEREBRAS_API_KEY not configured - skipping router test")
        return False

    try:
        router = ModelRouter()
        print("✅ Model router initialized")

        prompt = "You are a sales qualification AI. Analyze this lead: Company: Tesla, Industry: Electric Vehicles, Size: 50,000 employees. Provide a score 0-100 and brief reasoning."

        print(f"\n📝 Prompt: {prompt[:100]}...")
        print(f"🎯 Task type: {TaskType.QUALIFICATION.value}")
        print("\n🔄 Streaming response:")
        print("-" * 60)

        accumulated = ""
        token_count = 0

        async for chunk in router.stream_request(
            task_type=TaskType.QUALIFICATION,
            prompt=prompt,
            max_latency_ms=2000,
            temperature=0.7,
            max_tokens=300
        ):
            if chunk.get("type") == "token":
                print(chunk["content"], end="", flush=True)
                accumulated += chunk["content"]
                token_count += 1
            elif chunk.get("type") == "complete":
                print("\n" + "-" * 60)
                metadata = chunk["metadata"]
                print(f"\n✅ Streaming complete!")
                print(f"   • Model: {metadata['model']}")
                print(f"   • Provider: {metadata['provider']}")
                print(f"   • Tokens streamed: {token_count}")
                print(f"   • Latency: {metadata['latency_ms']}ms")
                print(f"   • Cost: ${metadata['cost_usd']:.6f}")
                print(f"   • Fallback used: {chunk.get('fallback_used', False)}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_circuit_breaker_streaming():
    """Test circuit breaker with streaming"""
    from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError

    print("\n🧪 Test 3: Circuit Breaker Streaming")
    print("=" * 60)

    try:
        breaker = CircuitBreaker(
            name="test_streaming",
            failure_threshold=2,
            recovery_timeout=5
        )
        print(f"✅ Circuit breaker initialized: {breaker.name}")
        print(f"   • Failure threshold: {breaker.failure_threshold}")
        print(f"   • State: {breaker.state.value}")

        # Test successful streaming
        async def mock_stream():
            for i in range(3):
                yield {"token": f"chunk_{i}"}

        print("\n🔄 Testing successful stream:")
        async for chunk in breaker.call_streaming(mock_stream):
            print(f"   • Received: {chunk}")

        print(f"✅ Stream completed, state: {breaker.state.value}")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all streaming tests"""
    print("\n" + "=" * 60)
    print("🚀 Streaming Implementation Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Claude streaming
    result1 = await test_claude_streaming()
    results.append(("Claude Streaming", result1))

    await asyncio.sleep(1)

    # Test 2: Model router streaming
    result2 = await test_model_router_streaming()
    results.append(("Model Router Streaming", result2))

    await asyncio.sleep(1)

    # Test 3: Circuit breaker streaming
    result3 = await test_circuit_breaker_streaming()
    results.append(("Circuit Breaker Streaming", result3))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\n🎯 Overall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("🎉 All streaming components working perfectly!")
        return 0
    else:
        print("⚠️  Some tests failed - review output above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
