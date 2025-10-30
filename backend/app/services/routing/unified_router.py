"""
Unified Router - Clean implementation using modular architecture

This module replaces the monolithic unified_router.py with a clean,
maintainable implementation that uses the new modular structure.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime

from .base_router import BaseRouter, RoutingRequest, RoutingResponse, TaskType, ProviderType, ProviderConfig
from .task_router import TaskRouter
from .cost_router import CostRouter
from app.core.exceptions import RoutingError

logger = logging.getLogger(__name__)


class UnifiedRouter:
    """
    Unified router that combines task-based and cost-based routing strategies.
    
    This is a clean, maintainable replacement for the monolithic unified_router.py.
    It delegates to specialized routers while providing a simple unified interface.
    """
    
    def __init__(self, providers: Dict[ProviderType, ProviderConfig]):
        """
        Initialize unified router.
        
        Args:
            providers: Dictionary of provider configurations
        """
        self.providers = providers
        
        # Initialize specialized routers
        self.task_router = TaskRouter(providers)
        self.cost_router = CostRouter(providers)
        
        # Routing strategy selection
        self.default_strategy = "task"  # "task" or "cost"
        
        logger.info("Unified router initialized with modular architecture")
    
    async def route_request(self, request: RoutingRequest) -> RoutingResponse:
        """
        Route a request using the appropriate strategy.
        
        Args:
            request: The routing request
            
        Returns:
            Routing response with content and metadata
        """
        try:
            # Select routing strategy
            strategy = self._select_strategy(request)
            
            # Route using selected strategy
            if strategy == "task":
                return await self.task_router.route_request(request)
            elif strategy == "cost":
                return await self.cost_router.route_request(request)
            else:
                raise RoutingError(f"Unknown routing strategy: {strategy}")
                
        except Exception as e:
            logger.error(f"Unified routing failed: {e}")
            raise RoutingError(f"Unified routing failed: {e}") from e
    
    async def route_stream(self, request: RoutingRequest) -> AsyncIterator[str]:
        """
        Route a streaming request using the appropriate strategy.
        
        Args:
            request: The routing request
            
        Yields:
            Streaming content chunks
        """
        try:
            # Select routing strategy
            strategy = self._select_strategy(request)
            
            # Route using selected strategy
            if strategy == "task":
                async for chunk in self.task_router.route_stream(request):
                    yield chunk
            elif strategy == "cost":
                async for chunk in self.cost_router.route_stream(request):
                    yield chunk
            else:
                raise RoutingError(f"Unknown routing strategy: {strategy}")
                
        except Exception as e:
            logger.error(f"Unified stream routing failed: {e}")
            raise RoutingError(f"Unified stream routing failed: {e}") from e
    
    def _select_strategy(self, request: RoutingRequest) -> str:
        """
        Select the appropriate routing strategy.
        
        Args:
            request: The routing request
            
        Returns:
            Strategy name ("task" or "cost")
        """
        # Use cost-based routing if budget constraints are specified
        if request.budget_limit:
            return "cost"
        
        # Use cost-based routing for high-volume, low-priority tasks
        if request.priority <= 2 and request.task_type in [TaskType.QUALIFICATION, TaskType.SIMPLE_PARSING]:
            return "cost"
        
        # Use task-based routing for complex or high-priority tasks
        if request.priority >= 4 or request.task_type in [TaskType.COMPLEX_REASONING, TaskType.CONTENT_GENERATION]:
            return "task"
        
        # Default to task-based routing
        return self.default_strategy
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all providers.
        
        Returns:
            Health status for each provider
        """
        try:
            # Get health status from both routers
            task_health = await self.task_router.health_check()
            cost_health = await self.cost_router.health_check()
            
            # Combine health statuses
            combined_health = {}
            for provider_type in self.providers:
                # Use task router health as primary (they use the same providers)
                combined_health[provider_type.value] = task_health.get(provider_type.value, {
                    "status": "unknown",
                    "error": "Provider not found in task router"
                })
            
            return combined_health
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"error": str(e)}
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from all routers.
        
        Returns:
            Combined performance statistics
        """
        try:
            task_stats = self.task_router.get_performance_stats()
            cost_stats = self.cost_router.get_performance_stats()
            
            return {
                "task_router": task_stats,
                "cost_router": cost_stats,
                "unified_stats": {
                    "total_requests": sum(stats.get("total_requests", 0) for stats in [task_stats, cost_stats]),
                    "total_cost_usd": sum(stats.get("total_cost_usd", 0) for stats in [task_stats, cost_stats]),
                    "average_latency_ms": self._calculate_average_latency(task_stats, cost_stats)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}
    
    def _calculate_average_latency(self, task_stats: Dict, cost_stats: Dict) -> float:
        """Calculate average latency across all providers."""
        total_latency = 0
        total_requests = 0
        
        for stats in [task_stats, cost_stats]:
            for provider_stats in stats.values():
                if isinstance(provider_stats, dict):
                    total_latency += provider_stats.get("total_latency_ms", 0)
                    total_requests += provider_stats.get("total_requests", 0)
        
        return total_latency / max(total_requests, 1)
    
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
        return self.task_router.is_provider_available(provider_type)
    
    def update_routing_strategy(self, strategy: str):
        """
        Update the default routing strategy.
        
        Args:
            strategy: Strategy name ("task" or "cost")
        """
        if strategy not in ["task", "cost"]:
            raise ValueError("Strategy must be 'task' or 'cost'")
        
        self.default_strategy = strategy
        logger.info(f"Updated default routing strategy to: {strategy}")
    
    def get_routing_info(self) -> Dict[str, Any]:
        """
        Get information about the routing configuration.
        
        Returns:
            Routing information dictionary
        """
        return {
            "default_strategy": self.default_strategy,
            "available_providers": [p.value for p in self.get_available_providers()],
            "task_routing": self.task_router.task_routing,
            "providers_configured": len(self.providers),
            "architecture": "modular"
        }
    
    async def close(self):
        """Close router and cleanup resources."""
        try:
            # Close any provider connections if needed
            logger.info("Unified router closed")
        except Exception as e:
            logger.error(f"Error closing unified router: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.create_task(self.close())
