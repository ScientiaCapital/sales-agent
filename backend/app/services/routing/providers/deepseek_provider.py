"""
DeepSeek Provider - Cost-effective research and analysis

This provider implements the DeepSeek API for cost-effective,
comprehensive research and analysis tasks.
"""

import asyncio
import logging
from typing import Dict, Any, AsyncIterator
from datetime import datetime

from openai import AsyncOpenAI
from .base_provider import BaseProvider, ProviderResponse
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseProvider):
    """
    DeepSeek provider for cost-effective research and analysis.
    
    Optimized for:
    - Research tasks
    - Cost-effective analysis
    - Comprehensive responses
    """
    
    def __init__(self, config):
        """Initialize DeepSeek provider."""
        super().__init__(config)
        
        # Initialize OpenAI client with DeepSeek endpoint
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        
        # DeepSeek-specific configuration
        self.model = config.model or "deepseek-chat"
        self.max_tokens = config.max_tokens or 2048
        self.temperature = config.temperature or 0.7
        
        logger.info(f"DeepSeek provider initialized: {self.model}")
    
    async def generate(self, request) -> ProviderResponse:
        """Generate text completion using DeepSeek."""
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
            tokens_used = response.usage.total_tokens
            cost_usd = self.calculate_cost(tokens_used)
            
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
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens
                )
            )
            
            # Update stats
            self._update_stats(tokens_used, cost_usd, latency_ms)
            
            # Log request
            self._log_request(request, response_obj)
            
            return response_obj
            
        except asyncio.TimeoutError:
            error_msg = f"DeepSeek request timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            self._log_request(request, error=ProviderError(error_msg))
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"DeepSeek generation failed: {e}"
            logger.error(error_msg)
            self._log_request(request, error=e)
            raise ProviderError(error_msg) from e
    
    async def generate_stream(self, request) -> AsyncIterator[str]:
        """Generate streaming text completion using DeepSeek."""
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
            error_msg = f"DeepSeek stream timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"DeepSeek streaming failed: {e}"
            logger.error(error_msg)
            raise ProviderError(error_msg) from e
    
    async def health_check(self) -> bool:
        """Check DeepSeek provider health."""
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
            logger.error(f"DeepSeek health check failed: {e}")
            return False
