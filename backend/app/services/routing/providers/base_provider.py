"""
Base Provider - Common interface for all LLM providers

This module defines the standard interface that all providers must implement,
ensuring consistency across different LLM services.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncIterator

from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


@dataclass
class ProviderResponse:
    """Standard response format for all providers."""
    content: str
    model: str
    tokens_used: int
    cost_usd: float
    latency_ms: int
    metadata: Dict[str, Any]


class BaseProvider(ABC):
    """
    Base class for all LLM providers.
    
    Defines the standard interface that all providers must implement:
    - Text generation
    - Streaming generation  
    - Health checks
    - Cost calculation
    - Performance monitoring
    """
    
    def __init__(self, config: Any):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.model = config.model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.timeout_seconds = config.timeout_seconds
        self.cost_per_token = config.cost_per_token
        
        # Performance tracking
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
    
    @abstractmethod
    async def generate(self, request) -> ProviderResponse:
        """
        Generate text completion.
        
        Args:
            request: The generation request
            
        Returns:
            Provider response with generated content
            
        Raises:
            ProviderError: If generation fails
        """
        pass
    
    @abstractmethod
    async def generate_stream(self, request) -> AsyncIterator[str]:
        """
        Generate streaming text completion.
        
        Args:
            request: The generation request
            
        Yields:
            Streaming content chunks
            
        Raises:
            ProviderError: If generation fails
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check provider health.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def calculate_cost(self, tokens_used: int) -> float:
        """
        Calculate cost for token usage.
        
        Args:
            tokens_used: Number of tokens used
            
        Returns:
            Cost in USD
        """
        return tokens_used * self.cost_per_token
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4
    
    def _update_stats(self, tokens_used: int, cost_usd: float, latency_ms: int):
        """Update performance statistics."""
        self.total_requests += 1
        self.total_tokens += tokens_used
        self.total_cost += cost_usd
        self.total_latency += latency_ms
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost,
            "average_latency_ms": self.total_latency / max(self.total_requests, 1),
            "average_cost_per_token": self.total_cost / max(self.total_tokens, 1),
            "model": self.model,
            "provider_type": self.__class__.__name__
        }
    
    def reset_stats(self):
        """Reset performance statistics."""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
    
    def _create_metadata(self, **kwargs) -> Dict[str, Any]:
        """Create metadata dictionary with common fields."""
        metadata = {
            "provider": self.__class__.__name__,
            "model": self.model,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        return metadata
    
    def _validate_request(self, request) -> None:
        """
        Validate generation request.
        
        Args:
            request: The generation request
            
        Raises:
            ProviderError: If request is invalid
        """
        if not hasattr(request, 'prompt') or not request.prompt:
            raise ProviderError("Request must have a non-empty prompt")
        
        if hasattr(request, 'max_tokens') and request.max_tokens:
            if request.max_tokens > self.max_tokens:
                raise ProviderError(f"max_tokens ({request.max_tokens}) exceeds provider limit ({self.max_tokens})")
        
        if hasattr(request, 'temperature') and request.temperature is not None:
            if not 0 <= request.temperature <= 2:
                raise ProviderError("temperature must be between 0 and 2")
    
    async def _execute_with_timeout(self, coro, timeout_seconds: Optional[int] = None):
        """
        Execute coroutine with timeout.
        
        Args:
            coro: The coroutine to execute
            timeout_seconds: Timeout in seconds (uses provider default if None)
            
        Returns:
            Coroutine result
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        timeout = timeout_seconds or self.timeout_seconds
        return await asyncio.wait_for(coro, timeout=timeout)
    
    def _log_request(self, request, response: Optional[ProviderResponse] = None, error: Optional[Exception] = None):
        """Log request details for monitoring."""
        log_data = {
            "provider": self.__class__.__name__,
            "model": self.model,
            "prompt_length": len(request.prompt),
            "max_tokens": getattr(request, 'max_tokens', None),
            "temperature": getattr(request, 'temperature', None)
        }
        
        if response:
            log_data.update({
                "tokens_used": response.tokens_used,
                "cost_usd": response.cost_usd,
                "latency_ms": response.latency_ms,
                "success": True
            })
        elif error:
            log_data.update({
                "error": str(error),
                "success": False
            })
        
        logger.info("Provider request", extra=log_data)
