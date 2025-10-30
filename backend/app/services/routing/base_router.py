"""
Base Router - Core routing interface and common functionality

This module provides the foundation for all routing implementations,
including common patterns, error handling, and performance monitoring.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, AsyncIterator, Union
from contextlib import asynccontextmanager

from app.core.exceptions import RoutingError, ProviderError
from app.services.circuit_breaker import CircuitBreaker
from app.services.retry_handler import RetryWithBackoff

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of AI tasks with different optimization requirements."""
    QUALIFICATION = "qualification"           # Fast inference, low cost
    CONTENT_GENERATION = "content_generation" # High quality, moderate cost
    RESEARCH = "research"                     # Cost-effective, comprehensive
    SIMPLE_PARSING = "simple_parsing"         # Local/cheap, basic extraction
    COMPLEX_REASONING = "complex_reasoning"   # High quality, expensive
    VOICE_GENERATION = "voice_generation"     # Specialized, moderate cost


class ProviderType(str, Enum):
    """Available LLM providers."""
    CEREBRAS = "cerebras"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


@dataclass
class RoutingRequest:
    """Request for LLM routing."""
    task_type: TaskType
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    priority: int = 1  # 1=low, 5=high
    budget_limit: Optional[float] = None
    timeout_seconds: Optional[int] = None


@dataclass
class RoutingResponse:
    """Response from LLM routing."""
    content: str
    provider: ProviderType
    model: str
    tokens_used: int
    cost_usd: float
    latency_ms: int
    metadata: Dict[str, Any]


@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""
    provider_type: ProviderType
    model: str
    base_url: str
    api_key: str
    max_tokens: int
    temperature: float
    timeout_seconds: int
    cost_per_token: float
    circuit_breaker_config: Dict[str, Any]
    retry_config: Dict[str, Any]


class BaseRouter(ABC):
    """
    Base class for all routing implementations.
    
    Provides common functionality including:
    - Circuit breaker integration
    - Retry logic with exponential backoff
    - Performance monitoring
    - Error handling and logging
    """
    
    def __init__(self, providers: Dict[ProviderType, ProviderConfig]):
        """
        Initialize base router.
        
        Args:
            providers: Dictionary of provider configurations
        """
        self.providers = providers
        self.circuit_breakers = {}
        self.retry_handlers = {}
        self.performance_stats = {}
        
        # Initialize circuit breakers and retry handlers for each provider
        for provider_type, config in providers.items():
            self.circuit_breakers[provider_type] = CircuitBreaker(
                **config.circuit_breaker_config
            )
            self.retry_handlers[provider_type] = RetryWithBackoff(
                **config.retry_config
            )
    
    @abstractmethod
    async def route_request(self, request: RoutingRequest) -> RoutingResponse:
        """
        Route a request to the appropriate provider.
        
        Args:
            request: The routing request
            
        Returns:
            Routing response with content and metadata
            
        Raises:
            RoutingError: If routing fails
        """
        pass
    
    @abstractmethod
    async def route_stream(self, request: RoutingRequest) -> AsyncIterator[str]:
        """
        Route a streaming request to the appropriate provider.
        
        Args:
            request: The routing request
            
        Yields:
            Streaming content chunks
            
        Raises:
            RoutingError: If routing fails
        """
        pass
    
    def get_provider_config(self, provider_type: ProviderType) -> ProviderConfig:
        """Get configuration for a specific provider."""
        if provider_type not in self.providers:
            raise RoutingError(f"Provider {provider_type} not configured")
        return self.providers[provider_type]
    
    @asynccontextmanager
    async def get_provider_client(self, provider_type: ProviderType):
        """
        Get a provider client with proper error handling.
        
        Args:
            provider_type: The provider to get client for
            
        Yields:
            Provider client instance
            
        Raises:
            ProviderError: If client creation fails
        """
        try:
            config = self.get_provider_config(provider_type)
            client = await self._create_provider_client(config)
            yield client
        except Exception as e:
            logger.error(f"Failed to create {provider_type} client: {e}")
            raise ProviderError(f"Failed to create {provider_type} client: {e}") from e
        finally:
            # Cleanup if needed
            await self._cleanup_provider_client(provider_type)
    
    async def _create_provider_client(self, config: ProviderConfig):
        """Create a provider client. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _create_provider_client")
    
    async def _cleanup_provider_client(self, provider_type: ProviderType):
        """Cleanup provider client. Override in subclasses if needed."""
        pass
    
    async def _execute_with_circuit_breaker(
        self, 
        provider_type: ProviderType, 
        operation: callable
    ) -> Any:
        """
        Execute operation with circuit breaker protection.
        
        Args:
            provider_type: The provider type
            operation: The operation to execute
            
        Returns:
            Operation result
            
        Raises:
            CircuitBreakerError: If circuit breaker is open
        """
        circuit_breaker = self.circuit_breakers[provider_type]
        
        try:
            return await circuit_breaker.call(operation)
        except Exception as e:
            logger.error(f"Circuit breaker error for {provider_type}: {e}")
            raise CircuitBreakerError(f"Circuit breaker open for {provider_type}") from e
    
    async def _execute_with_retry(
        self, 
        provider_type: ProviderType, 
        operation: callable
    ) -> Any:
        """
        Execute operation with retry logic.
        
        Args:
            provider_type: The provider type
            operation: The operation to execute
            
        Returns:
            Operation result
            
        Raises:
            RetryExhaustedError: If all retries are exhausted
        """
        retry_handler = self.retry_handlers[provider_type]
        
        try:
            return await retry_handler.execute(operation)
        except Exception as e:
            logger.error(f"Retry exhausted for {provider_type}: {e}")
            raise RetryExhaustedError(f"Retry exhausted for {provider_type}") from e
    
    def _update_performance_stats(
        self, 
        provider_type: ProviderType, 
        latency_ms: int, 
        tokens_used: int, 
        cost_usd: float
    ):
        """Update performance statistics for a provider."""
        if provider_type not in self.performance_stats:
            self.performance_stats[provider_type] = {
                "total_requests": 0,
                "total_latency_ms": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "average_latency_ms": 0.0,
                "average_cost_per_token": 0.0
            }
        
        stats = self.performance_stats[provider_type]
        stats["total_requests"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["total_tokens"] += tokens_used
        stats["total_cost_usd"] += cost_usd
        stats["average_latency_ms"] = stats["total_latency_ms"] / stats["total_requests"]
        stats["average_cost_per_token"] = stats["total_cost_usd"] / stats["total_tokens"]
    
    def get_performance_stats(self) -> Dict[ProviderType, Dict[str, Any]]:
        """Get performance statistics for all providers."""
        return self.performance_stats.copy()
    
    def reset_performance_stats(self):
        """Reset performance statistics."""
        self.performance_stats.clear()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all providers.
        
        Returns:
            Health status for each provider
        """
        health_status = {}
        
        for provider_type in self.providers:
            try:
                # Test circuit breaker status
                circuit_breaker = self.circuit_breakers[provider_type]
                circuit_breaker_status = "open" if circuit_breaker.is_open() else "closed"
                
                # Test provider connectivity
                async with self.get_provider_client(provider_type) as client:
                    # Simple health check - override in subclasses
                    is_healthy = await self._test_provider_health(provider_type, client)
                
                health_status[provider_type.value] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "circuit_breaker": circuit_breaker_status,
                    "last_check": datetime.now().isoformat()
                }
                
            except Exception as e:
                health_status[provider_type.value] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
        
        return health_status
    
    async def _test_provider_health(self, provider_type: ProviderType, client) -> bool:
        """
        Test provider health. Override in subclasses.
        
        Args:
            provider_type: The provider type
            client: The provider client
            
        Returns:
            True if healthy, False otherwise
        """
        # Default implementation - always return True
        # Subclasses should implement actual health checks
        return True
