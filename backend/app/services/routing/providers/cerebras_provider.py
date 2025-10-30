"""
Cerebras Provider - Ultra-fast inference for qualification tasks

This provider implements the Cerebras API for high-speed, low-cost inference,
optimized for lead qualification and simple reasoning tasks.
"""

import asyncio
import logging
from typing import Dict, Any, AsyncIterator
from datetime import datetime

from openai import AsyncOpenAI
from .base_provider import BaseProvider, ProviderResponse
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)


class CerebrasProvider(BaseProvider):
    """
    Cerebras provider for ultra-fast inference.
    
    Optimized for:
    - Lead qualification (633ms average latency)
    - Simple reasoning tasks
    - High-volume, low-cost operations
    """
    
    def __init__(self, config):
        """Initialize Cerebras provider."""
        super().__init__(config)
        
        # Initialize OpenAI client with Cerebras endpoint
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        
        # Cerebras-specific configuration
        self.model = config.model or "llama3.1-8b"
        self.max_tokens = config.max_tokens or 512
        self.temperature = config.temperature or 0.7
        
        logger.info(f"Cerebras provider initialized: {self.model}")
    
    async def generate(self, request) -> ProviderResponse:
        """
        Generate text completion using Cerebras.
        
        Args:
            request: The generation request
            
        Returns:
            Provider response with generated content
        """
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
            error_msg = f"Cerebras request timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            self._log_request(request, error=ProviderError(error_msg))
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Cerebras generation failed: {e}"
            logger.error(error_msg)
            self._log_request(request, error=e)
            raise ProviderError(error_msg) from e
    
    async def generate_stream(self, request) -> AsyncIterator[str]:
        """
        Generate streaming text completion using Cerebras.
        
        Args:
            request: The generation request
            
        Yields:
            Streaming content chunks
        """
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
            error_msg = f"Cerebras stream timed out after {self.timeout_seconds}s"
            logger.error(error_msg)
            raise ProviderError(error_msg)
            
        except Exception as e:
            error_msg = f"Cerebras streaming failed: {e}"
            logger.error(error_msg)
            raise ProviderError(error_msg) from e
    
    async def health_check(self) -> bool:
        """
        Check Cerebras provider health.
        
        Returns:
            True if healthy, False otherwise
        """
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
            logger.error(f"Cerebras health check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the Cerebras model.
        
        Returns:
            Model information dictionary
        """
        return {
            "provider": "cerebras",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "cost_per_token": self.cost_per_token,
            "typical_latency_ms": 633,  # Cerebras average
            "use_cases": [
                "lead_qualification",
                "simple_reasoning",
                "text_classification",
                "sentiment_analysis"
            ]
        }
    
    def estimate_latency(self, prompt_length: int) -> int:
        """
        Estimate latency for a given prompt length.
        
        Args:
            prompt_length: Length of the prompt in characters
            
        Returns:
            Estimated latency in milliseconds
        """
        # Cerebras has very consistent latency regardless of prompt length
        # Base latency + small increase for longer prompts
        base_latency = 600  # ms
        length_factor = prompt_length * 0.1  # 0.1ms per character
        return int(base_latency + length_factor)
    
    def is_suitable_for_task(self, task_type: str) -> bool:
        """
        Check if Cerebras is suitable for a specific task type.
        
        Args:
            task_type: The task type
            
        Returns:
            True if suitable, False otherwise
        """
        suitable_tasks = [
            "qualification",
            "simple_parsing", 
            "text_classification",
            "sentiment_analysis",
            "basic_reasoning"
        ]
        
        return task_type.lower() in suitable_tasks
