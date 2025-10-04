"""Unit tests for model router service with 4 access methods."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from datetime import datetime

from app.services.model_router import ModelRouter, AccessMethod, ModelConfig


@pytest.fixture
def model_router():
    """Create ModelRouter instance."""
    return ModelRouter()


class TestModelRouter:
    """Test suite for ModelRouter with 4 access methods."""

    def test_init_default_config(self, model_router):
        """Test initialization with default configuration."""
        assert model_router.default_method == AccessMethod.CEREBRAS
        assert len(model_router.available_methods) == 4
        assert AccessMethod.CEREBRAS in model_router.available_methods
        assert AccessMethod.OPENAI in model_router.available_methods
        assert AccessMethod.ANTHROPIC in model_router.available_methods
        assert AccessMethod.OPENROUTER in model_router.available_methods

    def test_get_model_for_cerebras(self, model_router):
        """Test getting model configuration for Cerebras."""
        config = model_router.get_model_config(AccessMethod.CEREBRAS)
        assert config.provider == "cerebras"
        assert config.model == "llama3.1-8b"
        assert config.latency_target_ms == 100

    def test_get_model_for_openai(self, model_router):
        """Test getting model configuration for OpenAI."""
        config = model_router.get_model_config(AccessMethod.OPENAI)
        assert config.provider == "openai"
        assert config.model in ["gpt-4o-mini", "gpt-4o"]

    def test_get_model_for_anthropic(self, model_router):
        """Test getting model configuration for Anthropic."""
        config = model_router.get_model_config(AccessMethod.ANTHROPIC)
        assert config.provider == "anthropic"
        assert "claude" in config.model.lower()

    def test_get_model_for_openrouter(self, model_router):
        """Test getting model configuration for OpenRouter."""
        config = model_router.get_model_config(AccessMethod.OPENROUTER)
        assert config.provider == "openrouter"
        assert config.model != ""

    @pytest.mark.asyncio
    async def test_route_to_cerebras_fastest(self, model_router):
        """Test routing prioritizes Cerebras for speed."""
        # Mock all providers
        with patch.object(model_router, '_call_cerebras', new_callable=AsyncMock) as mock_cerebras, \
             patch.object(model_router, '_call_openai', new_callable=AsyncMock) as mock_openai:
            
            mock_cerebras.return_value = ("Response from Cerebras", 50)
            mock_openai.return_value = ("Response from OpenAI", 200)

            response, method, latency = await model_router.route_request(
                prompt="Test prompt",
                prefer_speed=True
            )

            assert method == AccessMethod.CEREBRAS
            assert latency == 50
            mock_cerebras.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_fallback_on_failure(self, model_router):
        """Test fallback to alternative provider on failure."""
        with patch.object(model_router, '_call_cerebras', new_callable=AsyncMock) as mock_cerebras, \
             patch.object(model_router, '_call_openai', new_callable=AsyncMock) as mock_openai:
            
            # Cerebras fails
            mock_cerebras.side_effect = Exception("Cerebras unavailable")
            mock_openai.return_value = ("Response from OpenAI", 150)

            response, method, latency = await model_router.route_request(
                prompt="Test prompt"
            )

            assert method == AccessMethod.OPENAI
            assert response == "Response from OpenAI"
            assert latency == 150

    @pytest.mark.asyncio
    async def test_route_quality_over_speed(self, model_router):
        """Test routing prioritizes quality when requested."""
        with patch.object(model_router, '_call_anthropic', new_callable=AsyncMock) as mock_anthropic:
            mock_anthropic.return_value = ("High quality response", 300)

            response, method, latency = await model_router.route_request(
                prompt="Complex analysis task",
                prefer_quality=True
            )

            assert method == AccessMethod.ANTHROPIC
            mock_anthropic.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_cost_optimization(self, model_router):
        """Test routing optimizes for cost when requested."""
        with patch.object(model_router, '_call_openrouter', new_callable=AsyncMock) as mock_router:
            mock_router.return_value = ("Cost-effective response", 120)

            response, method, latency = await model_router.route_request(
                prompt="Simple task",
                prefer_cost=True
            )

            assert method == AccessMethod.OPENROUTER
            mock_router.assert_called_once()

    def test_track_method_performance(self, model_router):
        """Test performance tracking for different methods."""
        # Record some performance metrics
        model_router.record_performance(AccessMethod.CEREBRAS, latency_ms=50, success=True)
        model_router.record_performance(AccessMethod.CEREBRAS, latency_ms=60, success=True)
        model_router.record_performance(AccessMethod.OPENAI, latency_ms=200, success=True)

        stats = model_router.get_performance_stats()

        assert stats[AccessMethod.CEREBRAS]["avg_latency"] == 55
        assert stats[AccessMethod.CEREBRAS]["success_rate"] == 1.0
        assert stats[AccessMethod.OPENAI]["avg_latency"] == 200

    def test_track_failure_rate(self, model_router):
        """Test failure rate tracking."""
        model_router.record_performance(AccessMethod.CEREBRAS, latency_ms=50, success=True)
        model_router.record_performance(AccessMethod.CEREBRAS, latency_ms=0, success=False)

        stats = model_router.get_performance_stats()

        assert stats[AccessMethod.CEREBRAS]["success_rate"] == 0.5
        assert stats[AccessMethod.CEREBRAS]["total_calls"] == 2

    @pytest.mark.asyncio
    async def test_parallel_requests(self, model_router):
        """Test handling multiple parallel requests."""
        async def mock_call(prompt):
            await asyncio.sleep(0.1)
            return (f"Response to: {prompt}", 100)

        with patch.object(model_router, '_call_cerebras', side_effect=mock_call):
            tasks = [
                model_router.route_request(prompt=f"Prompt {i}")
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            for response, method, latency in results:
                assert method == AccessMethod.CEREBRAS
                assert latency >= 100

    def test_method_selection_priority(self, model_router):
        """Test priority order for method selection."""
        # Speed priority: Cerebras > OpenAI > OpenRouter > Anthropic
        speed_order = model_router.get_method_priority(prefer_speed=True)
        assert speed_order[0] == AccessMethod.CEREBRAS

        # Quality priority: Anthropic > OpenAI > Cerebras > OpenRouter
        quality_order = model_router.get_method_priority(prefer_quality=True)
        assert quality_order[0] == AccessMethod.ANTHROPIC

        # Cost priority: OpenRouter > Cerebras > OpenAI > Anthropic
        cost_order = model_router.get_method_priority(prefer_cost=True)
        assert cost_order[0] == AccessMethod.OPENROUTER

    @pytest.mark.asyncio
    async def test_timeout_handling(self, model_router):
        """Test request timeout handling."""
        async def slow_call(prompt):
            await asyncio.sleep(5)  # Simulate slow response
            return ("Late response", 5000)

        with patch.object(model_router, '_call_cerebras', side_effect=slow_call), \
             patch.object(model_router, '_call_openai', new_callable=AsyncMock) as mock_openai:
            
            mock_openai.return_value = ("Fast fallback", 100)

            # Set short timeout
            response, method, latency = await model_router.route_request(
                prompt="Test",
                timeout_ms=1000
            )

            # Should fallback to OpenAI
            assert method == AccessMethod.OPENAI


class TestModelConfig:
    """Test ModelConfig data class."""

    def test_config_creation(self):
        """Test creating model configuration."""
        config = ModelConfig(
            provider="test_provider",
            model="test_model",
            api_key="test_key",
            latency_target_ms=100,
            cost_per_1k_tokens=0.001
        )

        assert config.provider == "test_provider"
        assert config.model == "test_model"
        assert config.latency_target_ms == 100
        assert config.cost_per_1k_tokens == 0.001

    def test_config_defaults(self):
        """Test configuration defaults."""
        config = ModelConfig(
            provider="test",
            model="test_model",
            api_key="key"
        )

        assert config.latency_target_ms is None
        assert config.cost_per_1k_tokens is None
