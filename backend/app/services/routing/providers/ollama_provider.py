"""
Ollama Provider - Local inference for privacy and cost

This provider implements the Ollama API for local inference,
providing free, private inference for simple tasks.
"""

import asyncio
import logging
from typing import Dict, Any, AsyncIterator
from datetime import datetime

from openai import AsyncOpenAI
from .base_provider import BaseProvider, ProviderResponse
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local inference.
    
    Optimized for:
    - Simple parsing tasks
    - Privacy-sensitive operations
    - Cost-free inference
    """
    
    def __init__(self, config):
        """Initialize Ollama provider."""
        super().__init__(config)
        
        # Initialize OpenAI client with Ollama endpoint
        self.client = AsyncOpenAI(
            api_key="ollama",  # Ollama doesn't require API key
            base_url=config.base_url
        )
        
        # Ollama-specific configuration
        self.model = config.model or "llama3.1:8b"
        self.max_tokens = config.max_tokens or 1024
        self.temperature = config.temperature or 0.7
        
        logger.info(f"Ollama provider initialized: {self.model}")
    
    async def generate(self, request) -> ProviderResponse:
        """Generate text completion using Ollama."""
        start_time = datetime.now()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Prepare generation parameters
            generation_params = {
                "model": self.model,
                "messages": [{"role": "user", "content": request.prompt}],
                "max_tokens": min(request.max_tokens or self.max_tokens, self.max_tokens),
                "temperature": request.temperature or self.temperature,
                "stream": False
            }
            
            # Generate completion
            response = await self._execute_with_timeout(
                self.client.chat.completions.create(**generation_params)
            )
            
            # Extract content and metadata
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else self.estimate_tokens(request.prompt)
            cost_usd = 0.0  # Ollama is free
            
            # Calculate latency
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Create response
            response_obj = ProviderResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                metadata=self._create_metadata(
                    finish_reason=response.choices[0].finish_reason,
                    local_inference=True,
                    cost_free=True
                )
            )
            
            # Update stats
            self._update_stats(tokens_used, cost_usd, latency_ms)
            
            # Log request
            self._log_request(request, response_obj)
            
            return response_obj
            
        except asyncio.TimeoutError:
            error_msg = f"Ollama request timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            self._log_request(request, error=ProviderError(error_msg))
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Ollama generation failed: {e}"
            logger.error(error_msg)
            self._log_request(request, error=e)
            raise ProviderError(error_msg) from e
    
    async def generate_stream(self, request) -> AsyncIterator[str]:
        """Generate streaming text completion using Ollama."""
        try:
            # Validate request
            self._validate_request(request)
            
            # Prepare generation parameters
            generation_params = {
                "model": self.model,
                "messages": [{"role": "user", "content": request.prompt}],
                "max_tokens": min(request.max_tokens or self.max_tokens, self.max_tokens),
                "temperature": request.temperature or self.temperature,
                "stream": True
            }
            
            # Generate streaming completion
            stream = await self._execute_with_timeout(
                self.client.chat.completions.create(**generation_params)
            )
            
            # Yield content chunks
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except asyncio.TimeoutError:
            error_msg = f"Ollama stream timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Ollama streaming failed: {e}"
            logger.error(error_msg)
            raise ProviderError(error_msg) from e
    
    async def health_check(self) -> bool:
        """Check Ollama provider health."""
        try:
            # Simple health check with minimal request
            test_request = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1,
                "temperature": 0
            }
            
            response = await asyncio.wait_for(
                self.client.chat.completions.create(**test_request),
                timeout=10
            )
            
            return response.choices[0].message.content is not None
            
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the Ollama model."""
        return {
            "provider": "ollama",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "cost_per_token": 0.0,  # Free
            "typical_latency_ms": 500,  # Local inference
            "use_cases": [
                "simple_parsing",
                "text_classification",
                "basic_reasoning",
                "privacy_sensitive_tasks"
            ],
            "local_inference": True,
            "cost_free": True
        }
