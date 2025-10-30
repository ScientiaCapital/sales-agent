"""
Comprehensive tests for the new modular routing system.

This module tests the refactored routing architecture including:
- BaseRouter functionality
- TaskRouter task-specific routing
- CostRouter cost optimization
- Provider implementations
- UnifiedRouter integration
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.routing.unified_router import UnifiedRouter
from app.services.routing.task_router import TaskRouter
from app.services.routing.cost_router import CostRouter
from app.services.routing.base_router import RoutingRequest, RoutingResponse, TaskType, ProviderType
from app.services.routing.providers.cerebras_provider import CerebrasProvider
from app.services.routing.providers.claude_provider import ClaudeProvider
from app.core.exceptions import RoutingError, ProviderError


class TestBaseRouter:
    """Test the base router functionality."""
    
    @pytest.mark.unit
    def test_routing_request_creation(self):
        """Test RoutingRequest creation and validation."""
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test prompt",
            max_tokens=100,
            temperature=0.7
        )
        
        assert request.task_type == TaskType.QUALIFICATION
        assert request.prompt == "Test prompt"
        assert request.max_tokens == 100
        assert request.temperature == 0.7
        assert request.priority == 1  # Default priority
        assert request.budget_limit is None  # Default budget
    
    @pytest.mark.unit
    def test_routing_response_creation(self):
        """Test RoutingResponse creation and validation."""
        response = RoutingResponse(
            content="Test response",
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            tokens_used=25,
            cost_usd=0.0001,
            latency_ms=500,
            metadata={"test": "data"}
        )
        
        assert response.content == "Test response"
        assert response.provider == ProviderType.CEREBRAS
        assert response.tokens_used == 25
        assert response.cost_usd == 0.0001
        assert response.latency_ms == 500


class TestTaskRouter:
    """Test task-specific routing functionality."""
    
    @pytest.mark.unit
    def test_task_router_initialization(self, mock_providers):
        """Test TaskRouter initialization."""
        router = TaskRouter(mock_providers)
        
        assert len(router.providers) == 4
        assert ProviderType.CEREBRAS in router.providers
        assert ProviderType.CLAUDE in router.providers
        assert ProviderType.DEEPSEEK in router.providers
        assert ProviderType.OLLAMA in router.providers
    
    @pytest.mark.unit
    def test_task_routing_mapping(self, mock_providers):
        """Test task-to-provider mapping."""
        router = TaskRouter(mock_providers)
        
        # Test default task routing
        assert router.task_routing[TaskType.QUALIFICATION] == ProviderType.CEREBRAS
        assert router.task_routing[TaskType.CONTENT_GENERATION] == ProviderType.CLAUDE
        assert router.task_routing[TaskType.RESEARCH] == ProviderType.DEEPSEEK
        assert router.task_routing[TaskType.SIMPLE_PARSING] == ProviderType.OLLAMA
    
    @pytest.mark.unit
    def test_provider_selection_by_task(self, mock_providers):
        """Test provider selection based on task type."""
        router = TaskRouter(mock_providers)
        
        # Test qualification task
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Qualify this lead"
        )
        provider = router._select_provider(request)
        assert provider == ProviderType.CEREBRAS
        
        # Test content generation task
        request = RoutingRequest(
            task_type=TaskType.CONTENT_GENERATION,
            prompt="Generate marketing content"
        )
        provider = router._select_provider(request)
        assert provider == ProviderType.CLAUDE
    
    @pytest.mark.unit
    def test_provider_selection_by_budget(self, mock_providers):
        """Test provider selection based on budget constraints."""
        router = TaskRouter(mock_providers)
        
        # Test with very low budget (should select cheapest)
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test prompt",
            budget_limit=0.0001  # Very low budget
        )
        provider = router._select_provider(request)
        assert provider == ProviderType.OLLAMA  # Free provider
    
    @pytest.mark.unit
    def test_provider_selection_by_priority(self, mock_providers):
        """Test provider selection based on priority."""
        router = TaskRouter(mock_providers)
        
        # Test high priority task
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Urgent qualification",
            priority=5  # High priority
        )
        provider = router._select_provider(request)
        assert provider == ProviderType.CEREBRAS  # Fastest provider
    
    @pytest.mark.unit
    def test_provider_availability_check(self, mock_providers):
        """Test provider availability checking."""
        router = TaskRouter(mock_providers)
        
        # All providers should be available initially
        for provider_type in ProviderType:
            assert router.is_provider_available(provider_type)
    
    @pytest.mark.unit
    def test_task_routing_stats(self, mock_providers):
        """Test task routing statistics."""
        router = TaskRouter(mock_providers)
        
        stats = router.get_task_routing_stats()
        
        # Check that stats are returned for all task types
        for task_type in TaskType:
            assert task_type.value in stats
            assert "total_requests" in stats[task_type.value]
            assert "providers_used" in stats[task_type.value]


class TestCostRouter:
    """Test cost optimization routing functionality."""
    
    @pytest.mark.unit
    def test_cost_router_initialization(self, mock_providers):
        """Test CostRouter initialization."""
        router = CostRouter(mock_providers)
        
        assert len(router.providers) == 4
        assert len(router.cost_ranking) == 4
        # Check cost ranking (cheapest first)
        assert router.cost_ranking[0] == ProviderType.OLLAMA  # Free
        assert router.cost_ranking[1] == ProviderType.CEREBRAS  # $0.000006
        assert router.cost_ranking[2] == ProviderType.DEEPSEEK  # $0.00027
        assert router.cost_ranking[3] == ProviderType.CLAUDE  # $0.001743
    
    @pytest.mark.unit
    def test_cost_estimation(self, mock_providers):
        """Test cost estimation for requests."""
        router = CostRouter(mock_providers)
        
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test prompt for cost estimation",
            max_tokens=100
        )
        
        # Test cost estimation for each provider
        for provider_type in ProviderType:
            cost = router._estimate_request_cost(request, provider_type)
            assert cost > 0  # All providers should have some cost (except Ollama)
            assert isinstance(cost, float)
    
    @pytest.mark.unit
    def test_provider_suitability_check(self, mock_providers):
        """Test provider suitability checking."""
        router = CostRouter(mock_providers)
        
        # Test different task types
        qualification_request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test"
        )
        
        content_request = RoutingRequest(
            task_type=TaskType.CONTENT_GENERATION,
            prompt="Test"
        )
        
        # All providers should be suitable for basic tasks
        for provider_type in ProviderType:
            assert router._is_provider_suitable(qualification_request, provider_type)
            assert router._is_provider_suitable(content_request, provider_type)
    
    @pytest.mark.unit
    def test_cost_optimal_provider_selection(self, mock_providers):
        """Test cost-optimal provider selection."""
        router = CostRouter(mock_providers)
        
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test prompt",
            budget_limit=0.01  # Reasonable budget
        )
        
        provider = router._select_cost_optimal_provider(request)
        
        # Should select the cheapest suitable provider
        assert provider in ProviderType
        assert router.is_provider_available(provider)
    
    @pytest.mark.unit
    def test_cost_optimization_stats(self, mock_providers):
        """Test cost optimization statistics."""
        router = CostRouter(mock_providers)
        
        stats = router.get_cost_optimization_stats()
        
        assert "total_cost_usd" in stats
        assert "total_requests" in stats
        assert "average_cost_per_request" in stats
        assert "cost_ranking" in stats
        assert "providers_used" in stats


class TestUnifiedRouter:
    """Test the unified router integration."""
    
    @pytest.mark.unit
    def test_unified_router_initialization(self, mock_providers):
        """Test UnifiedRouter initialization."""
        router = UnifiedRouter(mock_providers)
        
        assert router.task_router is not None
        assert router.cost_router is not None
        assert router.default_strategy == "task"
    
    @pytest.mark.unit
    def test_strategy_selection(self, mock_providers):
        """Test routing strategy selection."""
        router = UnifiedRouter(mock_providers)
        
        # Test task-based routing (default)
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test"
        )
        strategy = router._select_strategy(request)
        assert strategy == "task"
        
        # Test cost-based routing with budget
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test",
            budget_limit=0.01
        )
        strategy = router._select_strategy(request)
        assert strategy == "cost"
        
        # Test cost-based routing for low priority
        request = RoutingRequest(
            task_type=TaskType.QUALIFICATION,
            prompt="Test",
            priority=1
        )
        strategy = router._select_strategy(request)
        assert strategy == "cost"
    
    @pytest.mark.unit
    def test_available_providers(self, mock_providers):
        """Test available providers listing."""
        router = UnifiedRouter(mock_providers)
        
        providers = router.get_available_providers()
        
        assert len(providers) == 4
        assert ProviderType.CEREBRAS in providers
        assert ProviderType.CLAUDE in providers
        assert ProviderType.DEEPSEEK in providers
        assert ProviderType.OLLAMA in providers
    
    @pytest.mark.unit
    def test_provider_availability(self, mock_providers):
        """Test provider availability checking."""
        router = UnifiedRouter(mock_providers)
        
        for provider_type in ProviderType:
            assert router.is_provider_available(provider_type)
    
    @pytest.mark.unit
    def test_routing_info(self, mock_providers):
        """Test routing information retrieval."""
        router = UnifiedRouter(mock_providers)
        
        info = router.get_routing_info()
        
        assert "default_strategy" in info
        assert "available_providers" in info
        assert "task_routing" in info
        assert "providers_configured" in info
        assert "architecture" in info
        assert info["architecture"] == "modular"


class TestProviderImplementations:
    """Test individual provider implementations."""
    
    @pytest.mark.unit
    def test_cerebras_provider_initialization(self, mock_providers):
        """Test CerebrasProvider initialization."""
        config = mock_providers[ProviderType.CEREBRAS]
        provider = CerebrasProvider(config)
        
        assert provider.model == "llama3.1-8b"
        assert provider.max_tokens == 512
        assert provider.temperature == 0.7
        assert provider.cost_per_token == 0.000006
    
    @pytest.mark.unit
    def test_claude_provider_initialization(self, mock_providers):
        """Test ClaudeProvider initialization."""
        config = mock_providers[ProviderType.CLAUDE]
        provider = ClaudeProvider(config)
        
        assert provider.model == "claude-3-5-sonnet-20241022"
        assert provider.max_tokens == 4096
        assert provider.temperature == 0.7
        assert provider.cost_per_token == 0.001743
    
    @pytest.mark.unit
    def test_provider_cost_calculation(self, mock_providers):
        """Test provider cost calculation."""
        config = mock_providers[ProviderType.CEREBRAS]
        provider = CerebrasProvider(config)
        
        # Test cost calculation
        cost = provider.calculate_cost(1000)
        expected_cost = 1000 * 0.000006
        assert cost == expected_cost
    
    @pytest.mark.unit
    def test_provider_token_estimation(self, mock_providers):
        """Test provider token estimation."""
        config = mock_providers[ProviderType.CEREBRAS]
        provider = CerebrasProvider(config)
        
        # Test token estimation
        text = "This is a test prompt with multiple words for token estimation."
        tokens = provider.estimate_tokens(text)
        assert tokens > 0
        assert isinstance(tokens, int)
    
    @pytest.mark.unit
    def test_provider_stats_tracking(self, mock_providers):
        """Test provider statistics tracking."""
        config = mock_providers[ProviderType.CEREBRAS]
        provider = CerebrasProvider(config)
        
        # Initial stats should be zero
        stats = provider.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost_usd"] == 0.0
        
        # Update stats
        provider._update_stats(100, 0.001, 500)
        
        stats = provider.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_tokens"] == 100
        assert stats["total_cost_usd"] == 0.001
        assert stats["average_latency_ms"] == 500.0


class TestErrorHandling:
    """Test error handling in routing system."""
    
    @pytest.mark.unit
    def test_invalid_provider_config(self):
        """Test handling of invalid provider configuration."""
        with pytest.raises(ValueError):
            # Test with missing provider type
            config = ProviderConfig(
                provider_type=None,  # Invalid
                model="test-model",
                base_url="https://test.com",
                api_key="test-key",
                max_tokens=100,
                temperature=0.7,
                timeout_seconds=30,
                cost_per_token=0.001,
                circuit_breaker_config={},
                retry_config={}
            )
    
    @pytest.mark.unit
    def test_routing_error_handling(self, mock_providers):
        """Test routing error handling."""
        router = UnifiedRouter(mock_providers)
        
        # Test with invalid request
        with pytest.raises(RoutingError):
            request = RoutingRequest(
                task_type=None,  # Invalid task type
                prompt="Test"
            )
            # This should raise an error during routing
    
    @pytest.mark.unit
    def test_provider_error_handling(self, mock_providers):
        """Test provider error handling."""
        config = mock_providers[ProviderType.CEREBRAS]
        provider = CerebrasProvider(config)
        
        # Test request validation
        with pytest.raises(ProviderError):
            request = Mock()
            request.prompt = ""  # Empty prompt should fail validation
            provider._validate_request(request)


class TestPerformanceAndMonitoring:
    """Test performance monitoring and statistics."""
    
    @pytest.mark.unit
    def test_performance_stats_aggregation(self, mock_providers):
        """Test performance statistics aggregation."""
        router = UnifiedRouter(mock_providers)
        
        # Get initial stats
        stats = router.get_performance_stats()
        
        assert "task_router" in stats
        assert "cost_router" in stats
        assert "unified_stats" in stats
        
        # Check unified stats structure
        unified_stats = stats["unified_stats"]
        assert "total_requests" in unified_stats
        assert "total_cost_usd" in unified_stats
        assert "average_latency_ms" in unified_stats
    
    @pytest.mark.unit
    def test_health_check_implementation(self, mock_providers):
        """Test health check implementation."""
        router = UnifiedRouter(mock_providers)
        
        # Mock health check responses
        with patch.object(router.task_router, 'health_check') as mock_task_health, \
             patch.object(router.cost_router, 'health_check') as mock_cost_health:
            
            mock_task_health.return_value = {
                "cerebras": {"status": "healthy"},
                "claude": {"status": "healthy"}
            }
            mock_cost_health.return_value = {
                "cerebras": {"status": "healthy"},
                "claude": {"status": "healthy"}
            }
            
            health_status = router.health_check()
            
            assert "cerebras" in health_status
            assert "claude" in health_status
            assert "deepseek" in health_status
            assert "ollama" in health_status


@pytest.mark.integration
class TestIntegrationScenarios:
    """Test integration scenarios with the routing system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_routing_flow(self, mock_providers):
        """Test complete routing flow from request to response."""
        router = UnifiedRouter(mock_providers)
        
        # Mock provider responses
        mock_response = RoutingResponse(
            content="Test response",
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            tokens_used=25,
            cost_usd=0.0001,
            latency_ms=500,
            metadata={}
        )
        
        with patch.object(router.task_router, 'route_request', return_value=mock_response):
            request = RoutingRequest(
                task_type=TaskType.QUALIFICATION,
                prompt="Qualify this lead: Test Company"
            )
            
            response = await router.route_request(request)
            
            assert response.content == "Test response"
            assert response.provider == ProviderType.CEREBRAS
            assert response.tokens_used == 25
    
    @pytest.mark.asyncio
    async def test_streaming_routing_flow(self, mock_providers):
        """Test streaming routing flow."""
        router = UnifiedRouter(mock_providers)
        
        # Mock streaming response
        async def mock_stream():
            yield "Test "
            yield "streaming "
            yield "response"
        
        with patch.object(router.task_router, 'route_stream', return_value=mock_stream()):
            request = RoutingRequest(
                task_type=TaskType.CONTENT_GENERATION,
                prompt="Generate content"
            )
            
            chunks = []
            async for chunk in router.route_stream(request):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert "".join(chunks) == "Test streaming response"
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, mock_providers):
        """Test error recovery and fallback mechanisms."""
        router = UnifiedRouter(mock_providers)
        
        # Mock provider failure
        with patch.object(router.task_router, 'route_request', side_effect=RoutingError("Provider failed")):
            request = RoutingRequest(
                task_type=TaskType.QUALIFICATION,
                prompt="Test prompt"
            )
            
            with pytest.raises(RoutingError):
                await router.route_request(request)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
