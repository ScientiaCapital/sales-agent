"""
Claude Provider - High-quality reasoning and content generation

This provider implements the Anthropic Claude API for high-quality,
reasoning-intensive tasks and content generation.
"""

import asyncio
import logging
from typing import Dict, Any, AsyncIterator
from datetime import datetime

from anthropic import AsyncAnthropic
from .base_provider import BaseProvider, ProviderResponse
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseProvider):
    """
    Claude provider for high-quality reasoning and content generation.
    
    Optimized for:
    - Complex reasoning tasks
    - Content generation
    - High-quality responses
    """
    
    def __init__(self, config):
        """Initialize Claude provider."""
        super().__init__(config)
        
        # Initialize Anthropic client
        self.client = AsyncAnthropic(
            api_key=config.api_key
        )
        
        # Claude-specific configuration
        self.model = config.model or "claude-3-5-sonnet-20241022"
        self.max_tokens = config.max_tokens or 4096
        self.temperature = config.temperature or 0.7
        
        logger.info(f"Claude provider initialized: {self.model}")
    
    async def generate(self, request) -> ProviderResponse:
        """Generate text completion using Claude."""
        start_time = datetime.now()
        
        try:
            # Validate request
            self._validate_request(request)
            
            # Prepare generation parameters
            generation_params = {
                "model": self.model,
                "max_tokens": min(request.max_tokens or self.max_tokens, self.max_tokens),
                "temperature": request.temperature or self.temperature,
                "messages": [{"role": "user", "content": request.prompt}]
            }
            
            # Generate completion
            response = await self._execute_with_timeout(
                self.client.messages.create(**generation_params)
            )
            
            # Extract content and metadata
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
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
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    stop_reason=response.stop_reason
                )
            )
            
            # Update stats
            self._update_stats(tokens_used, cost_usd, latency_ms)
            
            # Log request
            self._log_request(request, response_obj)
            
            return response_obj
            
        except asyncio.TimeoutError:
            error_msg = f"Claude request timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            self._log_request(request, error=ProviderError(error_msg))
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Claude generation failed: {e}"
            logger.error(error_msg)
            self._log_request(request, error=e)
            raise ProviderError(error_msg) from e
    
    async def generate_stream(self, request) -> AsyncIterator[str]:
        """Generate streaming text completion using Claude."""
        try:
            # Validate request
            self._validate_request(request)
            
            # Prepare generation parameters
            generation_params = {
                "model": self.model,
                "max_tokens": min(request.max_tokens or self.max_tokens, self.max_tokens),
                "temperature": request.temperature or self.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
                "stream": True
            }
            
            # Generate streaming completion
            stream = await self._execute_with_timeout(
                self.client.messages.create(**generation_params)
            )
            
            # Yield content chunks
            async for chunk in stream:
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    yield chunk.delta.text
                    
        except asyncio.TimeoutError:
            error_msg = f"Claude stream timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Claude streaming failed: {e}"
            logger.error(error_msg)
            raise ProviderError(error_msg) from e
    
    async def health_check(self) -> bool:
        """Check Claude provider health."""
        try:
            # Simple health check with minimal request
            test_request = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1,
                "temperature": 0
            }
            
            response = await asyncio.wait_for(
                self.client.messages.create(**test_request),
                timeout=10
            )
            
            return len(response.content) > 0 and response.content[0].text is not None
            
        except Exception as e:
            logger.error(f"Claude health check failed: {e}")
            return False
