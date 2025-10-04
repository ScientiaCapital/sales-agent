"""
Claude SDK streaming service for real-time AI responses

Provides streaming completions with AsyncAnthropic for progressive token delivery.
"""
import os
import time
from typing import AsyncIterator, Dict, Tuple
from anthropic import AsyncAnthropic, APIConnectionError, RateLimitError, APIStatusError

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ClaudeStreamingService:
    """
    Service for streaming Claude AI responses in real-time
    
    Uses AsyncAnthropic SDK with context managers for automatic resource cleanup.
    Streams tokens progressively for <100ms time-to-first-token.
    """
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        # Initialize async Anthropic client
        self.client = AsyncAnthropic(api_key=self.api_key)
        
        # Default model (Claude Sonnet 4.0 for quality)
        self.default_model = os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    
    async def stream_completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a Claude completion with progressive token delivery
        
        Args:
            prompt: User prompt/message
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            
        Yields:
            Dict with type ("token"|"complete"|"error"), content, and metadata
        """
        
        start_time = time.time()
        accumulated_text = ""
        input_tokens = 0
        output_tokens = 0
        
        try:
            # Build messages
            messages = [{"role": "user", "content": prompt}]
            
            # Stream with context manager for automatic cleanup
            async with self.client.messages.stream(
                model=self.default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                system=system_prompt if system_prompt else None
            ) as stream:
                
                # Stream text tokens only (fastest iteration)
                async for text in stream.text_stream:
                    accumulated_text += text
                    
                    yield {
                        "type": "token",
                        "content": text,
                        "snapshot": accumulated_text,  # Full text so far
                        "metadata": {
                            "model": self.default_model
                        }
                    }
                
                # Get final message for usage stats
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens
            
            # Calculate final metrics
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            cost_info = self.calculate_cost(input_tokens, output_tokens)
            
            # Send completion message
            yield {
                "type": "complete",
                "content": accumulated_text,
                "metadata": {
                    "model": self.default_model,
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    **cost_info
                }
            }
            
        except APIConnectionError as e:
            logger.error(f"Claude API connection error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": "API connection failed - server unreachable",
                "metadata": {"exception": str(e)}
            }
            
        except RateLimitError as e:
            logger.error(f"Claude API rate limit hit: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": "Rate limit exceeded - please retry later",
                "metadata": {"exception": str(e)}
            }
            
        except APIStatusError as e:
            logger.error(f"Claude API status error: {e.status_code}", exc_info=True)
            yield {
                "type": "error",
                "error": f"API error: {e.status_code}",
                "metadata": {"status_code": e.status_code, "response": str(e.response)}
            }
            
        except Exception as e:
            logger.error(f"Unexpected error during Claude streaming: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": "Unexpected streaming error",
                "metadata": {"exception": str(e)}
            }
    
    async def stream_agent_response(
        self,
        agent_type: str,
        lead_data: Dict[str, Any],
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream an agent's response with agent context
        
        Args:
            agent_type: Type of agent (enrichment, growth, marketing, etc.)
            lead_data: Lead information for context
            system_prompt: Agent-specific system instructions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Dict with agent context and streaming tokens
        """
        
        # Build prompt from lead data
        prompt_parts = []
        for key, value in lead_data.items():
            if value:
                prompt_parts.append(f"{key}: {value}")
        
        user_prompt = "\n".join(prompt_parts)
        
        # Stream with agent context
        async for chunk in self.stream_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            # Add agent type to metadata
            chunk["metadata"]["agent_type"] = agent_type
            yield chunk
    
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = None
    ) -> Dict[str, float]:
        """
        Calculate API call cost based on token usage
        
        Claude pricing (as of January 2025):
        - Sonnet 4.0: $3/M input, $15/M output
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name (defaults to default_model)
            
        Returns:
            Dict with input_cost_usd, output_cost_usd, and total_cost_usd
        """
        model = model or self.default_model
        
        # Pricing per million tokens
        pricing = {
            "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-opus-20240229": {"input": 15.00, "output": 75.00}
        }
        
        prices = pricing.get(model, {"input": 3.00, "output": 15.00})
        
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6)
        }
    
    async def count_tokens(self, text: str) -> int:
        """
        Count tokens in text for cost estimation
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        try:
            count = await self.client.messages.count_tokens(
                model=self.default_model,
                messages=[{"role": "user", "content": text}]
            )
            return count.input_tokens
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4
