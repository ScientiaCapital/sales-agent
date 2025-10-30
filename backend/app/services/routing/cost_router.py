"""
Cost Router - Cost optimization and budget management

This module handles routing decisions based on cost optimization and budget constraints,
providing intelligent provider selection for cost-sensitive operations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime

from .base_router import BaseRouter, RoutingRequest, RoutingResponse, TaskType, ProviderType
from .providers.cerebras_provider import CerebrasProvider
from .providers.claude_provider import ClaudeProvider
from .providers.deepseek_provider import DeepSeekProvider
from .providers.ollama_provider import OllamaProvider
from app.core.exceptions import RoutingError

logger = logging.getLogger(__name__)


class CostRouter(BaseRouter):
    """
    Cost-optimized router that selects providers based on budget constraints.
    
    Routing Strategy:
    - Prioritize cheapest providers that meet quality requirements
    - Fall back to higher-cost providers if budget allows
    - Consider task complexity vs. cost trade-offs
    """
    
    def __init__(self, providers: Dict[ProviderType, Any]):
        """Initialize cost router with provider configurations."""
        super().__init__(providers)
        
        # Initialize provider instances
        self.provider_instances = {
            ProviderType.CEREBRAS: CerebrasProvider(providers[ProviderType.CEREBRAS]),
            ProviderType.CLAUDE: ClaudeProvider(providers[ProviderType.CLAUDE]),
            ProviderType.DEEPSEEK: DeepSeekProvider(providers[ProviderType.DEEPSEEK]),
            ProviderType.OLLAMA: OllamaProvider(providers[ProviderType.OLLAMA]),
        }
        
        # Cost-based provider ranking (cheapest first)
        self.cost_ranking = [
            ProviderType.OLLAMA,      # Free (local)
            ProviderType.CEREBRAS,    # $0.000006 per token
            ProviderType.DEEPSEEK,    # $0.00027 per token
            ProviderType.CLAUDE,      # $0.001743 per token
        ]
    
    async def route_request(self, request: RoutingRequest) -> RoutingResponse:
        """
        Route a request based on cost optimization.
        
        Args:
            request: The routing request
            
        Returns:
            Routing response with content and metadata
        """
        try:
            # Select provider based on cost optimization
            provider_type = self._select_cost_optimal_provider(request)
            
            # Get provider instance
            provider = self.provider_instances[provider_type]
            
            # Execute with circuit breaker and retry
            start_time = datetime.now()
            
            async def execute():
                return await provider.generate(request)
            
            result = await self._execute_with_circuit_breaker(provider_type, execute)
            
            # Calculate metrics
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update performance stats
            self._update_performance_stats(
                provider_type, 
                latency_ms, 
                result.tokens_used, 
                result.cost_usd
            )
            
            logger.info(
                f"Cost-optimized routing successful",
                extra={
                    "provider": provider_type.value,
                    "cost_usd": result.cost_usd,
                    "latency_ms": latency_ms,
                    "budget_limit": request.budget_limit
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Cost routing failed: {e}", extra={"budget_limit": request.budget_limit})
            raise RoutingError(f"Cost routing failed: {e}") from e
    
    async def route_stream(self, request: RoutingRequest) -> AsyncIterator[str]:
        """
        Route a streaming request based on cost optimization.
        
        Args:
            request: The routing request
            
        Yields:
            Streaming content chunks
        """
        try:
            # Select provider based on cost optimization
            provider_type = self._select_cost_optimal_provider(request)
            
            # Get provider instance
            provider = self.provider_instances[provider_type]
            
            # Execute streaming with circuit breaker
            async def execute():
                async for chunk in provider.generate_stream(request):
                    yield chunk
            
            async for chunk in self._execute_with_circuit_breaker(provider_type, execute):
                yield chunk
                
        except Exception as e:
            logger.error(f"Cost stream routing failed: {e}", extra={"budget_limit": request.budget_limit})
            raise RoutingError(f"Cost stream routing failed: {e}") from e
    
    def _select_cost_optimal_provider(self, request: RoutingRequest) -> ProviderType:
        """
        Select the most cost-effective provider for the request.
        
        Args:
            request: The routing request
            
        Returns:
            Selected provider type
        """
        # Estimate cost for each provider
        estimated_costs = {}
        
        for provider_type in self.cost_ranking:
            if not self.is_provider_available(provider_type):
                continue
                
            # Estimate cost
            estimated_cost = self._estimate_request_cost(request, provider_type)
            
            # Check if within budget
            if request.budget_limit and estimated_cost > request.budget_limit:
                continue
                
            # Check if suitable for task
            if not self._is_provider_suitable(request, provider_type):
                continue
                
            estimated_costs[provider_type] = estimated_cost
        
        if not estimated_costs:
            # Fall back to cheapest available provider
            for provider_type in self.cost_ranking:
                if self.is_provider_available(provider_type):
                    return provider_type
            
            raise RoutingError("No suitable providers available")
        
        # Return cheapest suitable provider
        return min(estimated_costs.items(), key=lambda x: x[1])[0]
    
    def _estimate_request_cost(self, request: RoutingRequest, provider_type: ProviderType) -> float:
        """
        Estimate cost for a request with a specific provider.
        
        Args:
            request: The routing request
            provider_type: The provider type
            
        Returns:
            Estimated cost in USD
        """
        config = self.get_provider_config(provider_type)
        
        # Estimate token usage
        prompt_tokens = len(request.prompt.split()) * 1.3  # Rough estimation
        max_tokens = request.max_tokens or config.max_tokens
        total_tokens = prompt_tokens + max_tokens
        
        # Calculate cost
        return total_tokens * config.cost_per_token
    
    def _is_provider_suitable(self, request: RoutingRequest, provider_type: ProviderType) -> bool:
        """
        Check if a provider is suitable for the request.
        
        Args:
            request: The routing request
            provider_type: The provider type
            
        Returns:
            True if suitable, False otherwise
        """
        provider = self.provider_instances[provider_type]
        
        # Check if provider supports the task type
        if hasattr(provider, 'is_suitable_for_task'):
            return provider.is_suitable_for_task(request.task_type.value)
        
        # Default suitability check
        suitable_tasks = {
            ProviderType.OLLAMA: [TaskType.SIMPLE_PARSING, TaskType.QUALIFICATION],
            ProviderType.CEREBRAS: [TaskType.QUALIFICATION, TaskType.SIMPLE_PARSING],
            ProviderType.DEEPSEEK: [TaskType.RESEARCH, TaskType.CONTENT_GENERATION],
            ProviderType.CLAUDE: [TaskType.CONTENT_GENERATION, TaskType.COMPLEX_REASONING]
        }
        
        return request.task_type in suitable_tasks.get(provider_type, [])
    
    async def _create_provider_client(self, config):
        """Create provider client. Not used in cost router."""
        pass
    
    async def _test_provider_health(self, provider_type: ProviderType, client) -> bool:
        """
        Test provider health.
        
        Args:
            provider_type: The provider type
            client: The provider client
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            provider = self.provider_instances[provider_type]
            return await provider.health_check()
        except Exception as e:
            logger.error(f"Health check failed for {provider_type}: {e}")
            return False
    
    def get_cost_optimization_stats(self) -> Dict[str, Any]:
        """
        Get cost optimization statistics.
        
        Returns:
            Statistics about cost optimization
        """
        stats = self.get_performance_stats()
        
        # Calculate cost savings
        total_cost = sum(provider_stats.get("total_cost_usd", 0) for provider_stats in stats.values())
        total_requests = sum(provider_stats.get("total_requests", 0) for provider_stats in stats.values())
        
        return {
            "total_cost_usd": total_cost,
            "total_requests": total_requests,
            "average_cost_per_request": total_cost / max(total_requests, 1),
            "cost_ranking": [p.value for p in self.cost_ranking],
            "providers_used": list(stats.keys())
        }
    
    def is_provider_available(self, provider_type: ProviderType) -> bool:
        """
        Check if a provider is available.
        
        Args:
            provider_type: The provider type
            
        Returns:
            True if available, False otherwise
        """
        if provider_type not in self.providers:
            return False
        
        circuit_breaker = self.circuit_breakers[provider_type]
        return not circuit_breaker.is_open()
