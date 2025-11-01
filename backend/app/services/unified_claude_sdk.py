"""
Unified Claude SDK Service - Intelligent Routing Between Anthropic & DeepSeek

This service provides a unified interface to use the Anthropic Python SDK with both:
- Anthropic Claude models (premium quality)
- DeepSeek models (cost-optimized via Anthropic-compatible API)

Key Features:
- Automatic routing based on task complexity and cost constraints
- Same SDK, different base_url for DeepSeek
- Prompt caching for 90% cost reduction on repeated system prompts
- Streaming support for real-time responses
- Vision API support (Anthropic only)
- Comprehensive cost tracking

Pricing Comparison:
    Anthropic Claude Sonnet 4:
        Input:  $3.00 per 1M tokens
        Output: $15.00 per 1M tokens

    DeepSeek v3 (via Anthropic-compatible API):
        Input:  $0.27 per 1M tokens (11x cheaper)
        Output: $1.10 per 1M tokens (14x cheaper)

Usage:
    ```python
    from app.services.unified_claude_sdk import get_unified_claude_client

    # Get singleton client
    client = await get_unified_claude_client()

    # Automatic routing based on complexity
    response = await client.generate(
        prompt="Analyze this lead...",
        complexity="simple",  # Will route to DeepSeek (cheap)
        max_tokens=500
    )

    # Force specific provider
    response = await client.generate(
        prompt="Complex reasoning task...",
        provider="anthropic",  # Force Claude for quality
        max_tokens=2000
    )

    # Streaming response
    async for chunk in client.generate_stream(
        prompt="Write a marketing email...",
        complexity="medium"  # Will auto-route
    ):
        print(chunk, end="", flush=True)

    # With prompt caching (90% cost savings)
    response = await client.generate_with_caching(
        system_prompt="You are an expert sales agent...",  # This gets cached
        prompt="Qualify this lead: ..."
    )
    ```

Architecture:
    Input → Complexity Analysis → Routing Decision → Provider Selection → Response
                                       ↓
                                  - Simple → DeepSeek (cheap)
                                  - Medium → DeepSeek or Claude
                                  - Complex → Claude (quality)
"""

import os
import time
import asyncio
from typing import Optional, Dict, Any, List, Literal, AsyncIterator
from enum import Enum
from dataclasses import dataclass

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, MessageStreamEvent
from pydantic import BaseModel

from app.core.logging import setup_logging
from app.services.cost_tracking import get_cost_optimizer

logger = setup_logging(__name__)


# ========== Enums & Models ==========

class Provider(str, Enum):
    """Supported providers for Claude SDK."""
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


class Complexity(str, Enum):
    """Task complexity levels for routing decisions."""
    SIMPLE = "simple"          # Simple classification, parsing → DeepSeek
    MEDIUM = "medium"          # Analysis, summarization → Auto-route
    COMPLEX = "complex"        # Complex reasoning, creativity → Claude


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    name: Provider
    base_url: str
    api_key: str
    models: List[str]
    cost_per_1m_input: float   # USD per 1M input tokens
    cost_per_1m_output: float  # USD per 1M output tokens
    supports_vision: bool
    supports_caching: bool
    max_tokens: int


class GenerateRequest(BaseModel):
    """Request model for generate method."""
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    complexity: Optional[Complexity] = None
    provider: Optional[Provider] = None
    budget_limit_usd: Optional[float] = None
    enable_caching: bool = False
    model_override: Optional[str] = None


class GenerateResponse(BaseModel):
    """Response model for generate method."""
    content: str
    provider: Provider
    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int
    cached: bool = False


# ========== Unified Claude SDK Client ==========

class UnifiedClaudeClient:
    """
    Unified client for Claude SDK with intelligent routing between Anthropic and DeepSeek.

    Features:
    - Automatic provider selection based on complexity
    - Cost optimization with budget constraints
    - Prompt caching for repeated system prompts
    - Streaming support
    - Vision API (Anthropic only)
    - Comprehensive cost tracking
    """

    def __init__(self):
        """Initialize unified Claude client with both Anthropic and DeepSeek."""

        # ========== Provider Configurations ==========

        self.providers = {
            Provider.ANTHROPIC: ProviderConfig(
                name=Provider.ANTHROPIC,
                base_url="https://api.anthropic.com",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                models=[
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229"
                ],
                cost_per_1m_input=3.00,
                cost_per_1m_output=15.00,
                supports_vision=True,
                supports_caching=True,
                max_tokens=4096
            ),
            Provider.DEEPSEEK: ProviderConfig(
                name=Provider.DEEPSEEK,
                base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                models=[
                    "deepseek-chat",
                    "deepseek-reasoner"
                ],
                cost_per_1m_input=0.27,
                cost_per_1m_output=1.10,
                supports_vision=False,
                supports_caching=False,  # DeepSeek doesn't support prompt caching yet
                max_tokens=4096
            )
        }

        # Initialize SDK clients (both use Anthropic SDK!)
        self.clients = {}

        # Anthropic client
        if self.providers[Provider.ANTHROPIC].api_key:
            self.clients[Provider.ANTHROPIC] = AsyncAnthropic(
                api_key=self.providers[Provider.ANTHROPIC].api_key,
                base_url=self.providers[Provider.ANTHROPIC].base_url
            )
            logger.info("✅ Anthropic Claude SDK initialized")
        else:
            logger.warning("⚠️ ANTHROPIC_API_KEY not set - Claude unavailable")

        # DeepSeek client (uses same Anthropic SDK with different base_url!)
        if self.providers[Provider.DEEPSEEK].api_key:
            self.clients[Provider.DEEPSEEK] = AsyncAnthropic(
                api_key=self.providers[Provider.DEEPSEEK].api_key,
                base_url=self.providers[Provider.DEEPSEEK].base_url
            )
            logger.info("✅ DeepSeek SDK initialized (Anthropic-compatible)")
        else:
            logger.warning("⚠️ DEEPSEEK_API_KEY not set - DeepSeek unavailable")

        # Cost optimizer for tracking
        self.cost_optimizer = None

        # Statistics
        self.stats = {
            Provider.ANTHROPIC: {"requests": 0, "total_cost": 0.0, "total_tokens": 0},
            Provider.DEEPSEEK: {"requests": 0, "total_cost": 0.0, "total_tokens": 0}
        }

    async def initialize(self):
        """Initialize async resources."""
        self.cost_optimizer = await get_cost_optimizer()
        logger.info("Unified Claude SDK client initialized with Anthropic + DeepSeek")

    # ========== Core Generation Methods ==========

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        complexity: Optional[Complexity] = None,
        provider: Optional[Provider] = None,
        budget_limit_usd: Optional[float] = None,
        enable_caching: bool = False,
        model_override: Optional[str] = None
    ) -> GenerateResponse:
        """
        Generate a response using Claude SDK with intelligent routing.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Max tokens to generate
            temperature: Temperature for sampling
            complexity: Task complexity (auto-routes if not specified)
            provider: Force specific provider (optional)
            budget_limit_usd: Budget limit in USD (optional)
            enable_caching: Enable prompt caching (Anthropic only)
            model_override: Override default model selection

        Returns:
            GenerateResponse with content, metadata, and cost
        """
        start_time = time.time()

        try:
            # Select provider
            selected_provider = provider or self._select_provider(
                complexity=complexity,
                budget_limit=budget_limit_usd,
                enable_caching=enable_caching
            )

            # Get client and config
            client = self.clients.get(selected_provider)
            if not client:
                raise ValueError(f"Provider {selected_provider} not available (missing API key)")

            config = self.providers[selected_provider]

            # Select model
            model = model_override or config.models[0]

            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Build system prompt with optional caching
            system = None
            if system_prompt:
                if enable_caching and config.supports_caching:
                    # Use prompt caching (Anthropic only)
                    system = [
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                else:
                    system = system_prompt

            # Make API call
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages
            )

            # Extract content
            content = response.content[0].text if response.content else ""

            # Calculate cost
            tokens_input = response.usage.input_tokens
            tokens_output = response.usage.output_tokens
            cost_usd = self._calculate_cost(
                provider=selected_provider,
                tokens_input=tokens_input,
                tokens_output=tokens_output
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Check if cached
            cached = hasattr(response.usage, 'cache_read_input_tokens') and response.usage.cache_read_input_tokens > 0

            # Update statistics
            self._update_stats(selected_provider, cost_usd, tokens_input + tokens_output)

            # Log to cost optimizer
            if self.cost_optimizer:
                await self.cost_optimizer.log_llm_call(
                    provider=selected_provider.value,
                    model=model,
                    prompt=prompt,
                    response=content,
                    tokens_in=tokens_input,
                    tokens_out=tokens_output,
                    cost_usd=cost_usd,
                    agent_name="unified_claude_sdk"
                )

            logger.info(
                f"✅ Generated response via {selected_provider.value} "
                f"({tokens_input + tokens_output} tokens, ${cost_usd:.6f}, {latency_ms}ms, cached={cached})"
            )

            return GenerateResponse(
                content=content,
                provider=selected_provider,
                model=model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                cached=cached
            )

        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        complexity: Optional[Complexity] = None,
        provider: Optional[Provider] = None,
        model_override: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response using Claude SDK.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Max tokens to generate
            temperature: Temperature for sampling
            complexity: Task complexity (auto-routes if not specified)
            provider: Force specific provider (optional)
            model_override: Override default model selection

        Yields:
            Content chunks as they arrive
        """
        try:
            # Select provider
            selected_provider = provider or self._select_provider(complexity=complexity)

            # Get client and config
            client = self.clients.get(selected_provider)
            if not client:
                raise ValueError(f"Provider {selected_provider} not available")

            config = self.providers[selected_provider]
            model = model_override or config.models[0]

            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Start streaming
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        yield event.delta.text

            logger.info(f"✅ Streaming completed via {selected_provider.value}")

        except Exception as e:
            logger.error(f"❌ Streaming failed: {e}")
            raise

    async def generate_with_vision(
        self,
        prompt: str,
        image_data: str,  # Base64 encoded image
        image_media_type: str = "image/jpeg",
        max_tokens: int = 1000
    ) -> GenerateResponse:
        """
        Generate a response with vision input (Anthropic only).

        Args:
            prompt: Text prompt
            image_data: Base64 encoded image
            image_media_type: MIME type of image
            max_tokens: Max tokens to generate

        Returns:
            GenerateResponse with analysis
        """
        if Provider.ANTHROPIC not in self.clients:
            raise ValueError("Vision API requires Anthropic provider")

        start_time = time.time()

        client = self.clients[Provider.ANTHROPIC]
        config = self.providers[Provider.ANTHROPIC]

        # Build multimodal message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        # Make API call
        response = await client.messages.create(
            model=config.models[0],
            max_tokens=max_tokens,
            messages=messages
        )

        # Extract and return
        content = response.content[0].text if response.content else ""
        tokens_input = response.usage.input_tokens
        tokens_output = response.usage.output_tokens
        cost_usd = self._calculate_cost(Provider.ANTHROPIC, tokens_input, tokens_output)
        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(f"✅ Vision analysis completed (${cost_usd:.6f}, {latency_ms}ms)")

        return GenerateResponse(
            content=content,
            provider=Provider.ANTHROPIC,
            model=config.models[0],
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            latency_ms=latency_ms
        )

    # ========== Routing Logic ==========

    def _select_provider(
        self,
        complexity: Optional[Complexity] = None,
        budget_limit: Optional[float] = None,
        enable_caching: bool = False
    ) -> Provider:
        """
        Intelligently select provider based on complexity and constraints.

        Args:
            complexity: Task complexity
            budget_limit: Budget limit in USD
            enable_caching: Whether caching is needed

        Returns:
            Selected provider
        """
        # If caching is required, use Anthropic (only provider that supports it)
        if enable_caching and Provider.ANTHROPIC in self.clients:
            logger.debug("Selected Anthropic (caching required)")
            return Provider.ANTHROPIC

        # Auto-detect complexity if not specified
        if complexity is None:
            complexity = Complexity.MEDIUM

        # Routing logic based on complexity
        if complexity == Complexity.SIMPLE:
            # Simple tasks → DeepSeek (11x cheaper)
            if Provider.DEEPSEEK in self.clients:
                logger.debug("Selected DeepSeek (simple task, cost-optimized)")
                return Provider.DEEPSEEK

        elif complexity == Complexity.MEDIUM:
            # Medium tasks → Check budget, prefer DeepSeek if available
            if budget_limit and budget_limit < 0.001:
                # Tight budget → DeepSeek
                if Provider.DEEPSEEK in self.clients:
                    logger.debug("Selected DeepSeek (budget constraint)")
                    return Provider.DEEPSEEK
            else:
                # No tight budget → Prefer DeepSeek for cost, fall back to Claude
                if Provider.DEEPSEEK in self.clients:
                    logger.debug("Selected DeepSeek (medium task, cost-optimized)")
                    return Provider.DEEPSEEK

        elif complexity == Complexity.COMPLEX:
            # Complex tasks → Claude (best quality)
            if Provider.ANTHROPIC in self.clients:
                logger.debug("Selected Anthropic Claude (complex reasoning)")
                return Provider.ANTHROPIC

        # Fallback: use whatever is available
        if Provider.DEEPSEEK in self.clients:
            logger.debug("Fallback: DeepSeek")
            return Provider.DEEPSEEK
        if Provider.ANTHROPIC in self.clients:
            logger.debug("Fallback: Anthropic")
            return Provider.ANTHROPIC

        raise ValueError("No providers available (missing API keys)")

    def _calculate_cost(
        self,
        provider: Provider,
        tokens_input: int,
        tokens_output: int
    ) -> float:
        """
        Calculate cost for a request.

        Args:
            provider: Provider used
            tokens_input: Input tokens
            tokens_output: Output tokens

        Returns:
            Cost in USD
        """
        config = self.providers[provider]

        cost_input = (tokens_input / 1_000_000) * config.cost_per_1m_input
        cost_output = (tokens_output / 1_000_000) * config.cost_per_1m_output

        return cost_input + cost_output

    def _update_stats(self, provider: Provider, cost: float, tokens: int):
        """Update internal statistics."""
        self.stats[provider]["requests"] += 1
        self.stats[provider]["total_cost"] += cost
        self.stats[provider]["total_tokens"] += tokens

    # ========== Utility Methods ==========

    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.

        Returns:
            Statistics for each provider
        """
        total_cost = sum(p["total_cost"] for p in self.stats.values())
        total_requests = sum(p["requests"] for p in self.stats.values())

        return {
            "providers": self.stats,
            "total": {
                "requests": total_requests,
                "cost_usd": round(total_cost, 6),
                "average_cost_per_request": round(total_cost / max(total_requests, 1), 6)
            },
            "savings": {
                "deepseek_vs_claude_input": "11x cheaper",
                "deepseek_vs_claude_output": "14x cheaper"
            }
        }

    def estimate_cost(
        self,
        prompt: str,
        max_tokens: int,
        provider: Provider
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            prompt: Input prompt
            max_tokens: Expected output tokens
            provider: Provider to use

        Returns:
            Estimated cost in USD
        """
        # Rough token estimation (1 token ≈ 0.75 words)
        estimated_input_tokens = len(prompt.split()) * 1.3

        return self._calculate_cost(
            provider=provider,
            tokens_input=int(estimated_input_tokens),
            tokens_output=max_tokens
        )

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all providers.

        Returns:
            Health status for each provider
        """
        health = {}

        for provider, client in self.clients.items():
            try:
                # Simple test request
                response = await client.messages.create(
                    model=self.providers[provider].models[0],
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                health[provider.value] = True
            except Exception as e:
                logger.error(f"Health check failed for {provider}: {e}")
                health[provider.value] = False

        return health


# ========== Singleton Instance ==========

_unified_claude_client: Optional[UnifiedClaudeClient] = None


async def get_unified_claude_client() -> UnifiedClaudeClient:
    """
    Get or create singleton UnifiedClaudeClient.

    Returns:
        UnifiedClaudeClient instance
    """
    global _unified_claude_client

    if _unified_claude_client is None:
        _unified_claude_client = UnifiedClaudeClient()
        await _unified_claude_client.initialize()

        # Log available providers
        providers = list(_unified_claude_client.clients.keys())
        logger.info(f"🚀 Unified Claude SDK ready with providers: {[p.value for p in providers]}")

    return _unified_claude_client
