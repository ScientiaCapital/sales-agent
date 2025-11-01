#!/usr/bin/env python3
"""
Simple validation script for Unified Claude SDK
Tests the implementation without requiring API keys or pytest
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """Test that all modules can be imported."""
    print("✓ Testing imports...")

    try:
        from app.services.unified_claude_sdk import (
            UnifiedClaudeClient,
            Provider,
            Complexity,
            GenerateRequest,
            GenerateResponse
        )
        print("  ✅ unified_claude_sdk imports successfully")
    except Exception as e:
        print(f"  ❌ Failed to import unified_claude_sdk: {e}")
        return False

    try:
        from app.services.langgraph.agents.qualification_agent_v2 import (
            QualificationAgentV2,
            LeadInput,
            LeadQualificationOutput
        )
        print("  ✅ qualification_agent_v2 imports successfully")
    except Exception as e:
        print(f"  ❌ Failed to import qualification_agent_v2: {e}")
        return False

    return True


def test_provider_enum():
    """Test Provider enum."""
    print("\n✓ Testing Provider enum...")

    from app.services.unified_claude_sdk import Provider

    assert Provider.ANTHROPIC.value == "anthropic"
    assert Provider.DEEPSEEK.value == "deepseek"
    print("  ✅ Provider enum values correct")

    return True


def test_complexity_enum():
    """Test Complexity enum."""
    print("\n✓ Testing Complexity enum...")

    from app.services.unified_claude_sdk import Complexity

    assert Complexity.SIMPLE.value == "simple"
    assert Complexity.MEDIUM.value == "medium"
    assert Complexity.COMPLEX.value == "complex"
    print("  ✅ Complexity enum values correct")

    return True


def test_client_initialization():
    """Test UnifiedClaudeClient initialization."""
    print("\n✓ Testing UnifiedClaudeClient initialization...")

    from app.services.unified_claude_sdk import UnifiedClaudeClient, Provider

    # Mock environment variables
    os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
    os.environ["DEEPSEEK_API_KEY"] = "test-key-deepseek"

    try:
        client = UnifiedClaudeClient()

        # Check providers are configured
        assert Provider.ANTHROPIC in client.providers
        assert Provider.DEEPSEEK in client.providers
        print("  ✅ Client initialized with both providers")

        # Check provider configs
        anthropic_config = client.providers[Provider.ANTHROPIC]
        assert anthropic_config.cost_per_1m_input == 3.00
        assert anthropic_config.cost_per_1m_output == 15.00
        print("  ✅ Anthropic pricing configured correctly")

        deepseek_config = client.providers[Provider.DEEPSEEK]
        assert deepseek_config.cost_per_1m_input == 0.27
        assert deepseek_config.cost_per_1m_output == 1.10
        print("  ✅ DeepSeek pricing configured correctly")

        # Verify cost savings
        assert deepseek_config.cost_per_1m_input < anthropic_config.cost_per_1m_input / 10
        print("  ✅ DeepSeek is >10x cheaper than Anthropic (verified)")

        return True
    except Exception as e:
        print(f"  ❌ Client initialization failed: {e}")
        return False


def test_routing_logic():
    """Test provider selection logic."""
    print("\n✓ Testing routing logic...")

    from app.services.unified_claude_sdk import UnifiedClaudeClient, Provider, Complexity

    os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
    os.environ["DEEPSEEK_API_KEY"] = "test-key-deepseek"

    client = UnifiedClaudeClient()

    # Test simple task routing
    provider = client._select_provider(complexity=Complexity.SIMPLE)
    assert provider == Provider.DEEPSEEK, f"Expected DEEPSEEK for simple task, got {provider}"
    print("  ✅ Simple tasks route to DeepSeek (cost-optimized)")

    # Test complex task routing
    provider = client._select_provider(complexity=Complexity.COMPLEX)
    assert provider == Provider.ANTHROPIC, f"Expected ANTHROPIC for complex task, got {provider}"
    print("  ✅ Complex tasks route to Claude (quality-optimized)")

    # Test caching requirement
    provider = client._select_provider(enable_caching=True)
    assert provider == Provider.ANTHROPIC, "Caching should force Anthropic"
    print("  ✅ Caching requirement forces Claude (only provider with caching)")

    # Test budget constraint
    provider = client._select_provider(
        complexity=Complexity.MEDIUM,
        budget_limit=0.0005
    )
    assert provider == Provider.DEEPSEEK, "Tight budget should prefer DeepSeek"
    print("  ✅ Budget constraints route to DeepSeek")

    return True


def test_cost_calculation():
    """Test cost calculation."""
    print("\n✓ Testing cost calculation...")

    from app.services.unified_claude_sdk import UnifiedClaudeClient, Provider

    os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
    os.environ["DEEPSEEK_API_KEY"] = "test-key-deepseek"

    client = UnifiedClaudeClient()

    # Test Anthropic cost
    cost_anthropic = client._calculate_cost(
        provider=Provider.ANTHROPIC,
        tokens_input=1000,
        tokens_output=500
    )
    expected_anthropic = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
    assert abs(cost_anthropic - expected_anthropic) < 0.000001
    print(f"  ✅ Anthropic cost calculated correctly: ${cost_anthropic:.6f}")

    # Test DeepSeek cost
    cost_deepseek = client._calculate_cost(
        provider=Provider.DEEPSEEK,
        tokens_input=1000,
        tokens_output=500
    )
    expected_deepseek = (1000 / 1_000_000) * 0.27 + (500 / 1_000_000) * 1.10
    assert abs(cost_deepseek - expected_deepseek) < 0.000001
    print(f"  ✅ DeepSeek cost calculated correctly: ${cost_deepseek:.6f}")

    # Verify savings
    savings_ratio = cost_anthropic / cost_deepseek
    print(f"  ✅ DeepSeek is {savings_ratio:.1f}x cheaper than Claude")
    assert savings_ratio > 10, "DeepSeek should be >10x cheaper"

    return True


def test_qualification_agent_v2():
    """Test QualificationAgentV2."""
    print("\n✓ Testing QualificationAgentV2...")

    from app.services.langgraph.agents.qualification_agent_v2 import (
        QualificationAgentV2,
        LeadInput,
        Complexity
    )

    agent = QualificationAgentV2()
    print("  ✅ QualificationAgentV2 initialized")

    # Test complexity detection
    simple_lead = LeadInput(
        company_name="Test Corp",
        industry="SaaS"
    )
    complexity = agent._detect_complexity(simple_lead)
    assert complexity == Complexity.SIMPLE
    print("  ✅ Simple lead detected correctly")

    complex_lead = LeadInput(
        company_name="Enterprise Corp",
        industry="Enterprise SaaS",
        company_size="500-1000",
        website="https://enterprise.com",
        contact_title="VP of Sales",
        contact_email="vp@enterprise.com",
        revenue="$50M-$100M"
    )
    complexity = agent._detect_complexity(complex_lead)
    assert complexity == Complexity.COMPLEX
    print("  ✅ Complex lead detected correctly")

    # Test prompt building
    prompt = agent._build_qualification_prompt(simple_lead)
    assert "Test Corp" in prompt
    assert "SaaS" in prompt
    print("  ✅ Qualification prompt built correctly")

    return True


def test_stats_tracking():
    """Test statistics tracking."""
    print("\n✓ Testing statistics tracking...")

    from app.services.unified_claude_sdk import UnifiedClaudeClient, Provider

    os.environ["ANTHROPIC_API_KEY"] = "test-key-anthropic"
    os.environ["DEEPSEEK_API_KEY"] = "test-key-deepseek"

    client = UnifiedClaudeClient()

    # Simulate some requests
    client._update_stats(Provider.DEEPSEEK, 0.0001, 150)
    client._update_stats(Provider.DEEPSEEK, 0.0001, 150)
    client._update_stats(Provider.ANTHROPIC, 0.0011, 650)

    stats = client.get_stats()

    assert stats["providers"][Provider.DEEPSEEK]["requests"] == 2
    assert stats["providers"][Provider.ANTHROPIC]["requests"] == 1
    assert stats["total"]["requests"] == 3
    print("  ✅ Statistics tracked correctly")

    total_cost = stats["total"]["cost_usd"]
    avg_cost = stats["total"]["average_cost_per_request"]
    print(f"  ✅ Total cost: ${total_cost:.6f}")
    print(f"  ✅ Average cost per request: ${avg_cost:.6f}")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Unified Claude SDK - Validation Tests")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Provider Enum", test_provider_enum),
        ("Complexity Enum", test_complexity_enum),
        ("Client Initialization", test_client_initialization),
        ("Routing Logic", test_routing_logic),
        ("Cost Calculation", test_cost_calculation),
        ("QualificationAgentV2", test_qualification_agent_v2),
        ("Statistics Tracking", test_stats_tracking),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 All tests passed! Unified Claude SDK is working correctly.")
        print("\n✅ Next steps:")
        print("  1. Add DEEPSEEK_API_KEY to your .env file")
        print("  2. Run integration tests with real API keys")
        print("  3. Test with production leads")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
