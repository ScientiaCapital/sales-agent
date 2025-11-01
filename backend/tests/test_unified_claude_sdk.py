"""
Tests for Unified Claude SDK

Tests the intelligent routing, cost optimization, and provider selection
for the unified Claude/DeepSeek SDK service.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.unified_claude_sdk import (
    UnifiedClaudeClient,
    get_unified_claude_client,
    Provider,
    Complexity,
    GenerateRequest,
    GenerateResponse
)


# ========== Fixtures ==========

@pytest.fixture
async def unified_client():
    """Create unified Claude client for testing."""
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "DEEPSEEK_API_KEY": "test-deepseek-key"
    }):
        client = UnifiedClaudeClient()
        await client.initialize()
        yield client


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response from Claude")]
    mock_response.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0
    )
    return mock_response


@pytest.fixture
def mock_deepseek_response():
    """Mock DeepSeek API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response from DeepSeek")]
    mock_response.usage = MagicMock(
        input_tokens=100,
        output_tokens=50
    )
    return mock_response


# ========== Provider Selection Tests ==========

@pytest.mark.asyncio
async def test_select_provider_simple_task(unified_client):
    """Test that simple tasks route to DeepSeek."""
    provider = unified_client._select_provider(complexity=Complexity.SIMPLE)

    # Should prefer DeepSeek for simple tasks (11x cheaper)
    assert provider == Provider.DEEPSEEK


@pytest.mark.asyncio
async def test_select_provider_complex_task(unified_client):
    """Test that complex tasks route to Claude."""
    provider = unified_client._select_provider(complexity=Complexity.COMPLEX)

    # Should use Claude for complex reasoning
    assert provider == Provider.ANTHROPIC


@pytest.mark.asyncio
async def test_select_provider_budget_constraint(unified_client):
    """Test provider selection with budget constraint."""
    provider = unified_client._select_provider(
        complexity=Complexity.MEDIUM,
        budget_limit=0.0005  # Tight budget
    )

    # Should prefer DeepSeek when budget is tight
    assert provider == Provider.DEEPSEEK


@pytest.mark.asyncio
async def test_select_provider_caching_required(unified_client):
    """Test that caching requirement forces Anthropic."""
    provider = unified_client._select_provider(
        complexity=Complexity.SIMPLE,
        enable_caching=True
    )

    # Must use Anthropic for prompt caching
    assert provider == Provider.ANTHROPIC


# ========== Generation Tests ==========

@pytest.mark.asyncio
async def test_generate_with_deepseek(unified_client, mock_deepseek_response):
    """Test generation with DeepSeek provider."""
    with patch.object(
        unified_client.clients[Provider.DEEPSEEK],
        'messages',
        MagicMock(create=AsyncMock(return_value=mock_deepseek_response))
    ):
        response = await unified_client.generate(
            prompt="Qualify this lead",
            complexity=Complexity.SIMPLE,
            provider=Provider.DEEPSEEK
        )

        assert response.provider == Provider.DEEPSEEK
        assert response.content == "Test response from DeepSeek"
        assert response.tokens_input == 100
        assert response.tokens_output == 50
        assert response.cost_usd < 0.0002  # DeepSeek is cheap!


@pytest.mark.asyncio
async def test_generate_with_claude(unified_client, mock_anthropic_response):
    """Test generation with Claude provider."""
    with patch.object(
        unified_client.clients[Provider.ANTHROPIC],
        'messages',
        MagicMock(create=AsyncMock(return_value=mock_anthropic_response))
    ):
        response = await unified_client.generate(
            prompt="Complex reasoning task",
            complexity=Complexity.COMPLEX,
            provider=Provider.ANTHROPIC
        )

        assert response.provider == Provider.ANTHROPIC
        assert response.content == "Test response from Claude"
        assert response.tokens_input == 100
        assert response.tokens_output == 50


@pytest.mark.asyncio
async def test_generate_auto_routing(unified_client, mock_deepseek_response):
    """Test automatic routing based on complexity."""
    with patch.object(
        unified_client.clients[Provider.DEEPSEEK],
        'messages',
        MagicMock(create=AsyncMock(return_value=mock_deepseek_response))
    ):
        # Don't specify provider - should auto-route to DeepSeek for simple task
        response = await unified_client.generate(
            prompt="Simple classification",
            complexity=Complexity.SIMPLE
        )

        assert response.provider == Provider.DEEPSEEK


# ========== Cost Calculation Tests ==========

def test_calculate_cost_anthropic(unified_client):
    """Test cost calculation for Anthropic."""
    cost = unified_client._calculate_cost(
        provider=Provider.ANTHROPIC,
        tokens_input=1000,
        tokens_output=500
    )

    # Anthropic: $3/1M input, $15/1M output
    expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
    assert abs(cost - expected) < 0.000001


def test_calculate_cost_deepseek(unified_client):
    """Test cost calculation for DeepSeek."""
    cost = unified_client._calculate_cost(
        provider=Provider.DEEPSEEK,
        tokens_input=1000,
        tokens_output=500
    )

    # DeepSeek: $0.27/1M input, $1.10/1M output
    expected = (1000 / 1_000_000) * 0.27 + (500 / 1_000_000) * 1.10
    assert abs(cost - expected) < 0.000001


def test_cost_comparison():
    """Test that DeepSeek is significantly cheaper than Claude."""
    client = UnifiedClaudeClient()

    tokens_input = 1000
    tokens_output = 500

    cost_anthropic = client._calculate_cost(Provider.ANTHROPIC, tokens_input, tokens_output)
    cost_deepseek = client._calculate_cost(Provider.DEEPSEEK, tokens_input, tokens_output)

    # DeepSeek should be at least 10x cheaper
    assert cost_deepseek < cost_anthropic / 10


# ========== Statistics Tests ==========

@pytest.mark.asyncio
async def test_stats_tracking(unified_client, mock_deepseek_response):
    """Test that statistics are tracked correctly."""
    with patch.object(
        unified_client.clients[Provider.DEEPSEEK],
        'messages',
        MagicMock(create=AsyncMock(return_value=mock_deepseek_response))
    ):
        # Make 3 requests
        for _ in range(3):
            await unified_client.generate(
                prompt="Test",
                provider=Provider.DEEPSEEK
            )

        stats = unified_client.get_stats()

        assert stats["providers"][Provider.DEEPSEEK]["requests"] == 3
        assert stats["providers"][Provider.DEEPSEEK]["total_cost"] > 0
        assert stats["total"]["requests"] == 3


# ========== Cost Estimation Tests ==========

def test_estimate_cost(unified_client):
    """Test cost estimation."""
    prompt = "This is a test prompt with about ten words in it"
    max_tokens = 500

    # Estimate for both providers
    cost_anthropic = unified_client.estimate_cost(prompt, max_tokens, Provider.ANTHROPIC)
    cost_deepseek = unified_client.estimate_cost(prompt, max_tokens, Provider.DEEPSEEK)

    # Both should return positive costs
    assert cost_anthropic > 0
    assert cost_deepseek > 0

    # DeepSeek should be cheaper
    assert cost_deepseek < cost_anthropic


# ========== Integration Tests ==========

@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_qualification_simple():
    """
    Integration test: Qualify a simple lead with DeepSeek.
    Requires DEEPSEEK_API_KEY environment variable.
    """
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")

    client = await get_unified_claude_client()

    response = await client.generate(
        prompt="""Qualify this lead:
        Company: TechStartup Inc
        Industry: SaaS

        Respond with a qualification score (0-100) and brief reasoning.""",
        complexity=Complexity.SIMPLE,
        max_tokens=200
    )

    assert response.provider == Provider.DEEPSEEK
    assert response.cost_usd < 0.001  # Should be very cheap
    assert len(response.content) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_complex_reasoning():
    """
    Integration test: Complex reasoning with Claude.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    client = await get_unified_claude_client()

    response = await client.generate(
        prompt="""Analyze this complex business scenario:
        A SaaS company wants to expand to enterprise customers.
        What market research should they prioritize?""",
        complexity=Complexity.COMPLEX,
        max_tokens=500
    )

    assert response.provider == Provider.ANTHROPIC
    assert len(response.content) > 100
    assert response.cost_usd > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_prompt_caching():
    """
    Integration test: Test prompt caching with repeated requests.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    client = await get_unified_claude_client()

    system_prompt = "You are an expert lead qualification agent. " * 50  # Long prompt

    # First request (no cache)
    response1 = await client.generate(
        prompt="Qualify lead A",
        system_prompt=system_prompt,
        provider=Provider.ANTHROPIC,
        enable_caching=True,
        max_tokens=100
    )

    # Second request (should use cache)
    response2 = await client.generate(
        prompt="Qualify lead B",
        system_prompt=system_prompt,
        provider=Provider.ANTHROPIC,
        enable_caching=True,
        max_tokens=100
    )

    # Second request should be cheaper due to caching
    assert response2.cached or response2.cost_usd < response1.cost_usd * 0.5


# ========== Error Handling Tests ==========

@pytest.mark.asyncio
async def test_missing_api_keys():
    """Test error handling when API keys are missing."""
    with patch.dict(os.environ, {}, clear=True):
        client = UnifiedClaudeClient()

        # Should raise error when trying to generate
        with pytest.raises(ValueError, match="not available"):
            await client.generate(prompt="Test")


@pytest.mark.asyncio
async def test_invalid_provider():
    """Test error handling for invalid provider."""
    client = UnifiedClaudeClient()

    with pytest.raises((ValueError, KeyError)):
        await client.generate(
            prompt="Test",
            provider="invalid_provider"  # type: ignore
        )


# ========== Performance Tests ==========

@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_latency_simple_task(unified_client, mock_deepseek_response):
    """Test that simple tasks complete quickly."""
    import time

    with patch.object(
        unified_client.clients[Provider.DEEPSEEK],
        'messages',
        MagicMock(create=AsyncMock(return_value=mock_deepseek_response))
    ):
        start = time.time()
        response = await unified_client.generate(
            prompt="Quick classification",
            complexity=Complexity.SIMPLE
        )
        latency = (time.time() - start) * 1000

        # Should complete in under 5 seconds (mock)
        assert latency < 5000
        assert response.latency_ms > 0
