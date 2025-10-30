"""
Task Router - Task-specific routing logic

This module handles routing decisions based on task type and requirements,
providing intelligent provider selection for different AI tasks.
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


class TaskRouter(BaseRouter):
    """
    Task-specific router that selects providers based on task requirements.
    
    Routing Strategy:
    - QUALIFICATION: Cerebras (fast, cheap)
    - CONTENT_GENERATION: Claude (high quality)
    - RESEARCH: DeepSeek (cost-effective, comprehensive)
    - SIMPLE_PARSING: Ollama (local, free)
    - COMPLEX_REASONING: Claude (best reasoning)
    - VOICE_GENERATION: Specialized providers
    """
    
    def __init__(self, providers: Dict[ProviderType, Any]):
        """Initialize task router with provider configurations."""
        super().__init__(providers)
        
        # Initialize provider instances
        self.provider_instances = {
            ProviderType.CEREBRAS: CerebrasProvider(providers[ProviderType.CEREBRAS]),
            ProviderType.CLAUDE: ClaudeProvider(providers[ProviderType.CLAUDE]),
            ProviderType.DEEPSEEK: DeepSeekProvider(providers[ProviderType.DEEPSEEK]),
            ProviderType.OLLAMA: OllamaProvider(providers[ProviderType.OLLAMA]),
        }
        
        # Task-to-provider mapping
        self.task_routing = {
            TaskType.QUALIFICATION: ProviderType.CEREBRAS,
            TaskType.CONTENT_GENERATION: ProviderType.CLAUDE,
            TaskType.RESEARCH: ProviderType.DEEPSEEK,
            TaskType.SIMPLE_PARSING: ProviderType.OLLAMA,
            TaskType.COMPLEX_REASONING: ProviderType.CLAUDE,
            TaskType.VOICE_GENERATION: ProviderType.CEREBRAS,  # Fallback
        }
    
    async def route_request(self, request: RoutingRequest) -> RoutingResponse:
        """
        Route a request based on task type.
        
        Args:
            request: The routing request
            
        Returns:
            Routing response with content and metadata
        """
        try:
            # Select provider based on task type
            provider_type = self._select_provider(request)
            
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
                f"Task routed successfully",
                extra={
                    "task_type": request.task_type.value,
                    "provider": provider_type.value,
                    "latency_ms": latency_ms,
                    "tokens_used": result.tokens_used,
                    "cost_usd": result.cost_usd
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Task routing failed: {e}", extra={"task_type": request.task_type.value})
            raise RoutingError(f"Task routing failed: {e}") from e
    
    async def route_stream(self, request: RoutingRequest) -> AsyncIterator[str]:
        """
        Route a streaming request based on task type.
        
        Args:
            request: The routing request
            
        Yields:
            Streaming content chunks
        """
        try:
            # Select provider based on task type
            provider_type = self._select_provider(request)
            
            # Get provider instance
            provider = self.provider_instances[provider_type]
            
            # Execute streaming with circuit breaker
            async def execute():
                async for chunk in provider.generate_stream(request):
                    yield chunk
            
            async for chunk in self._execute_with_circuit_breaker(provider_type, execute):
                yield chunk
                
        except Exception as e:
            logger.error(f"Stream routing failed: {e}", extra={"task_type": request.task_type.value})
            raise RoutingError(f"Stream routing failed: {e}") from e
    
    def _select_provider(self, request: RoutingRequest) -> ProviderType:
        """
        Select the best provider for a task.
        
        Args:
            request: The routing request
            
        Returns:
            Selected provider type
        """
        # Check for explicit provider override in context
        if request.context and "provider" in request.context:
            provider_name = request.context["provider"]
            try:
                return ProviderType(provider_name)
            except ValueError:
                logger.warning(f"Invalid provider override: {provider_name}")
        
        # Check budget constraints
        if request.budget_limit:
            provider_type = self._select_provider_by_budget(request)
            if provider_type:
                return provider_type
        
        # Check priority constraints
        if request.priority >= 4:  # High priority
            provider_type = self._select_provider_by_priority(request)
            if provider_type:
                return provider_type
        
        # Default task-based routing
        return self.task_routing[request.task_type]
    
    def _select_provider_by_budget(self, request: RoutingRequest) -> Optional[ProviderType]:
        """
        Select provider based on budget constraints.
        
        Args:
            request: The routing request
            
        Returns:
            Provider type that fits budget, or None
        """
        # Estimate cost for each provider
        provider_costs = {}
        
        for provider_type, config in self.providers.items():
            # Rough cost estimation based on prompt length
            estimated_tokens = len(request.prompt.split()) * 1.3  # Rough estimation
            estimated_cost = estimated_tokens * config.cost_per_token
            
            if estimated_cost <= request.budget_limit:
                provider_costs[provider_type] = estimated_cost
        
        if not provider_costs:
            return None
        
        # Select cheapest provider that fits budget
        return min(provider_costs.items(), key=lambda x: x[1])[0]
    
    def _select_provider_by_priority(self, request: RoutingRequest) -> Optional[ProviderType]:
        """
        Select provider based on priority constraints.
        
        Args:
            request: The routing request
            
        Returns:
            Provider type for high priority, or None
        """
        # For high priority tasks, prefer fastest providers
        if request.task_type == TaskType.QUALIFICATION:
            return ProviderType.CEREBRAS  # Fastest
        elif request.task_type == TaskType.CONTENT_GENERATION:
            return ProviderType.CLAUDE  # Highest quality
        elif request.task_type == TaskType.RESEARCH:
            return ProviderType.DEEPSEEK  # Good balance
        else:
            return None  # Use default routing
    
    async def _create_provider_client(self, config):
        """Create provider client. Not used in task router."""
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
    
    def get_task_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics by task type.
        
        Returns:
            Statistics grouped by task type
        """
        stats = {}
        
        for task_type in TaskType:
            task_stats = {
                "total_requests": 0,
                "providers_used": {},
                "average_latency_ms": 0.0,
                "average_cost_usd": 0.0
            }
            
            # This would be populated from actual request tracking
            # For now, return empty stats
            stats[task_type.value] = task_stats
        
        return stats
    
    def update_task_routing(self, task_type: TaskType, provider_type: ProviderType):
        """
        Update task-to-provider mapping.
        
        Args:
            task_type: The task type
            provider_type: The provider type
        """
        self.task_routing[task_type] = provider_type
        logger.info(f"Updated routing: {task_type.value} -> {provider_type.value}")
    
    def get_available_providers(self) -> List[ProviderType]:
        """
        Get list of available providers.
        
        Returns:
            List of available provider types
        """
        return list(self.providers.keys())
    
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
