"""Unified LLM routing system combining task-based and cost-based strategies.

This module merges the best features of ModelRouter (circuit breakers, retry handlers,
task-based routing) and LLMRouter (cost optimization strategies, usage tracking) into
a single cohesive routing system with automatic strategy selection.

Key Features:
- Automatic task-to-strategy mapping
- Circuit breakers + exponential backoff retry for resilience
- Real-time usage statistics and cost tracking
- Streaming support with async token delivery
- Multiple provider support (Cerebras, Claude, DeepSeek, Ollama)
- Simplified API with intelligent defaults

Performance:
- <5ms routing overhead
- Cerebras: 633ms average latency
- Claude: 4026ms average latency
- DeepSeek: ~2000ms average latency
- Ollama: 500ms local latency (free)
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, AsyncIterator
import os

from anthropic import AsyncAnthropic
from openai import OpenAI, AsyncOpenAI

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError
from app.services.retry_handler import RetryWithBackoff, RetryExhaustedError

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration Classes
# ============================================================================

class TaskType(str, Enum):
    """Types of AI tasks with different optimization requirements."""
    QUALIFICATION = "qualification"           # Fast inference, low cost
    CONTENT_GENERATION = "content_generation" # High quality, moderate cost
    RESEARCH = "research"                     # Cost-effective, comprehensive
    SIMPLE_PARSING = "simple_parsing"         # Local/cheap, basic extraction


class RoutingStrategy(str, Enum):
    """LLM routing strategies for different use cases."""
    COST_OPTIMIZED = "cost_optimized"       # Cheapest available (DeepSeek/Ollama)
    LATENCY_OPTIMIZED = "latency_optimized" # Fastest available (Cerebras)
    QUALITY_OPTIMIZED = "quality_optimized" # Best quality (Claude)
    BALANCED = "balanced"                   # 80/20 split for cost savings


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: str              # cerebras, anthropic, deepseek, ollama
    model: str                 # Model identifier
    max_latency_ms: int = 5000  # Maximum acceptable latency
    max_cost_usd: float = 0.1   # Maximum cost per request
    fallback: bool = False      # Whether this is a fallback option
    via: Optional[str] = None   # Router service (e.g., "openrouter")
    local: bool = False         # Whether this runs locally


@dataclass
class ModelResponse:
    """Response from model inference with metadata."""
    content: str
    model_used: str
    provider: str
    latency_ms: int
    cost_usd: float
    tokens_used: Dict[str, int] = field(default_factory=dict)
    fallback_used: bool = False
    retry_count: int = 0
    error: Optional[str] = None


# ============================================================================
# Default Configuration
# ============================================================================

# Auto task-to-strategy mapping (eliminates need for manual strategy selection)
DEFAULT_STRATEGY_MAP = {
    TaskType.QUALIFICATION: RoutingStrategy.BALANCED,  # 64% cost savings
    TaskType.CONTENT_GENERATION: RoutingStrategy.QUALITY_OPTIMIZED,  # Best quality
    TaskType.RESEARCH: RoutingStrategy.COST_OPTIMIZED,  # Use DeepSeek
    TaskType.SIMPLE_PARSING: RoutingStrategy.COST_OPTIMIZED  # Ollama local (free)
}

# Provider configurations with capabilities and costs
PROVIDER_CONFIGS = {
    "cerebras": {
        "model": "llama3.1-8b",
        "avg_latency_ms": 633,
        "cost_per_1k_tokens": 0.000006,
        "max_tokens": 8192,
        "streaming": True
    },
    "claude": {
        "model": "claude-sonnet-4-20250514",
        "avg_latency_ms": 4026,
        "cost_per_1k_tokens": 0.001743,
        "max_tokens": 8192,
        "streaming": True
    },
    "deepseek": {
        "model": "deepseek/deepseek-chat",
        "avg_latency_ms": 2000,
        "cost_per_1k_tokens": 0.00027,
        "max_tokens": 8192,
        "streaming": True
    },
    "ollama": {
        "model": "llama3.1:8b",
        "avg_latency_ms": 500,
        "cost_per_1k_tokens": 0.0,  # Local, free
        "max_tokens": 8192,
        "streaming": True
    }
}


# ============================================================================
# UnifiedRouter Class
# ============================================================================

class UnifiedRouter:
    """
    Unified LLM routing system with automatic strategy selection.

    Combines task-based routing (ModelRouter) with cost optimization strategies
    (LLMRouter) into a single cohesive system. Automatically selects optimal
    provider based on task type and routing strategy.

    Example:
        >>> router = UnifiedRouter()
        >>> response = await router.route(
        ...     task_type=TaskType.QUALIFICATION,
        ...     prompt="Analyze this lead..."
        ... )
        >>> print(f"Used {response.provider}/{response.model_used}")
        >>> print(f"Cost: ${response.cost_usd:.6f}, Latency: {response.latency_ms}ms")

    With strategy override:
        >>> response = await router.route(
        ...     task_type=TaskType.RESEARCH,
        ...     prompt="Research competitor...",
        ...     strategy_override=RoutingStrategy.COST_OPTIMIZED  # Force DeepSeek
        ... )

    Streaming:
        >>> async for chunk in router.stream(
        ...     task_type=TaskType.CONTENT_GENERATION,
        ...     prompt="Write email..."
        ... ):
        ...     print(chunk["content"], end="", flush=True)
    """

    def __init__(
        self,
        enable_circuit_breakers: bool = True,
        enable_retry: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 60.0
    ):
        """
        Initialize the unified router.

        Args:
            enable_circuit_breakers: Enable circuit breaker protection
            enable_retry: Enable exponential backoff retry
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Seconds before circuit recovery attempt
            max_retries: Maximum retry attempts
            retry_base_delay: Initial retry delay in seconds
            retry_max_delay: Maximum retry delay in seconds
        """
        # Initialize provider clients
        self._init_clients()

        # Circuit breakers per provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        if enable_circuit_breakers:
            for provider in ["cerebras", "claude", "deepseek", "ollama"]:
                self.circuit_breakers[provider] = CircuitBreaker(
                    name=provider,
                    failure_threshold=circuit_breaker_threshold,
                    recovery_timeout=circuit_breaker_timeout
                )

        # Retry strategies per provider
        self.retry_strategies: Dict[str, RetryWithBackoff] = {}
        if enable_retry:
            for provider in ["cerebras", "claude", "deepseek", "ollama"]:
                self.retry_strategies[provider] = RetryWithBackoff(
                    max_retries=max_retries,
                    base_delay=retry_base_delay,
                    max_delay=retry_max_delay
                )

        # Usage tracking
        self.usage_stats = {
            "total_requests": 0,
            "provider_usage": {"cerebras": 0, "claude": 0, "deepseek": 0, "ollama": 0},
            "strategy_usage": {},
            "task_type_usage": {},
            "total_cost": 0.0,
            "total_latency_ms": 0,
            "fallback_count": 0,
            "error_count": 0,
            "circuit_breaker_trips": 0,
            "retry_count": 0
        }

        logger.info(
            f"UnifiedRouter initialized: circuit_breakers={enable_circuit_breakers}, "
            f"retry={enable_retry}, providers={list(self.available_providers.keys())}"
        )

    def _init_clients(self):
        """Initialize API clients for all providers."""
        self.available_providers = {}

        # Cerebras (via OpenAI SDK)
        if os.getenv("CEREBRAS_API_KEY"):
            self.cerebras_client = OpenAI(
                api_key=os.getenv("CEREBRAS_API_KEY"),
                base_url="https://api.cerebras.ai/v1"
            )
            self.cerebras_async_client = AsyncOpenAI(
                api_key=os.getenv("CEREBRAS_API_KEY"),
                base_url="https://api.cerebras.ai/v1"
            )
            self.available_providers["cerebras"] = PROVIDER_CONFIGS["cerebras"]
            logger.info("Cerebras client initialized")

        # Claude (via Anthropic SDK)
        if os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            self.available_providers["claude"] = PROVIDER_CONFIGS["claude"]
            logger.info("Claude client initialized")

        # DeepSeek (via OpenRouter)
        if os.getenv("OPENROUTER_API_KEY"):
            self.openrouter_client = OpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
            self.openrouter_async_client = AsyncOpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
            self.available_providers["deepseek"] = PROVIDER_CONFIGS["deepseek"]
            logger.info("DeepSeek client initialized (via OpenRouter)")

        # Ollama (local)
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            self.ollama_client = OpenAI(
                api_key="ollama",  # Dummy key for local
                base_url=f"{ollama_base_url}/v1"
            )
            self.ollama_async_client = AsyncOpenAI(
                api_key="ollama",
                base_url=f"{ollama_base_url}/v1"
            )
            self.available_providers["ollama"] = PROVIDER_CONFIGS["ollama"]
            logger.info(f"Ollama client initialized: {ollama_base_url}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")

        if not self.available_providers:
            raise RuntimeError("No LLM providers configured. Set API keys in .env")

    def _select_provider(
        self,
        strategy: RoutingStrategy,
        task_type: TaskType,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None
    ) -> str:
        """
        Select optimal provider based on strategy and constraints.

        Args:
            strategy: Routing strategy to apply
            task_type: Type of task (for logging)
            max_latency_ms: Maximum acceptable latency (optional filter)
            max_cost_usd: Maximum acceptable cost (optional filter)

        Returns:
            Provider name (cerebras, claude, deepseek, ollama)

        Raises:
            RuntimeError: If no providers available after filtering
        """
        # Filter providers by constraints
        available = self.available_providers.copy()

        if max_latency_ms:
            available = {
                k: v for k, v in available.items()
                if v["avg_latency_ms"] <= max_latency_ms
            }

        if max_cost_usd:
            available = {
                k: v for k, v in available.items()
                if v["cost_per_1k_tokens"] <= max_cost_usd
            }

        if not available:
            raise RuntimeError(
                f"No providers available for {task_type} with constraints: "
                f"latency<={max_latency_ms}ms, cost<=${max_cost_usd}"
            )

        # Apply routing strategy
        if strategy == RoutingStrategy.COST_OPTIMIZED:
            # Select cheapest provider
            return min(
                available.keys(),
                key=lambda k: available[k]["cost_per_1k_tokens"]
            )

        elif strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            # Select fastest provider
            return min(
                available.keys(),
                key=lambda k: available[k]["avg_latency_ms"]
            )

        elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            # Priority: Claude > Cerebras > DeepSeek > Ollama
            for provider in ["claude", "cerebras", "deepseek", "ollama"]:
                if provider in available:
                    return provider
            return list(available.keys())[0]

        else:  # BALANCED strategy
            # 80/20 split: 80% cheap (DeepSeek/Ollama), 20% fast (Cerebras)
            cheap_providers = [
                k for k in available.keys()
                if k in ["deepseek", "ollama"]
            ]
            fast_providers = [
                k for k in available.keys()
                if k in ["cerebras", "claude"]
            ]

            if cheap_providers and fast_providers:
                # 80% cheap, 20% fast
                if random.random() < 0.8:
                    # Pick cheapest of cheap
                    return min(
                        cheap_providers,
                        key=lambda k: available[k]["cost_per_1k_tokens"]
                    )
                else:
                    # Pick fastest of fast
                    return min(
                        fast_providers,
                        key=lambda k: available[k]["avg_latency_ms"]
                    )
            else:
                # Fallback to cheapest available
                return min(
                    available.keys(),
                    key=lambda k: available[k]["cost_per_1k_tokens"]
                )

    async def route(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        strategy_override: Optional[RoutingStrategy] = None,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> ModelResponse:
        """
        Route request to optimal model with automatic strategy selection.

        Args:
            task_type: Type of task (auto-selects strategy if not overridden)
            prompt: User prompt/content
            system_prompt: Optional system prompt
            strategy_override: Override automatic strategy selection
            max_latency_ms: Override max latency constraint
            max_cost_usd: Override max cost constraint
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum response tokens

        Returns:
            ModelResponse with result and metadata

        Raises:
            CircuitBreakerError: If all providers unavailable
            RetryExhaustedError: If retries exhausted
            RuntimeError: If no providers match constraints
        """
        start_time = datetime.now()

        # Select strategy
        strategy = strategy_override or DEFAULT_STRATEGY_MAP.get(
            task_type,
            RoutingStrategy.BALANCED
        )

        # Select provider
        provider = self._select_provider(
            strategy=strategy,
            task_type=task_type,
            max_latency_ms=max_latency_ms,
            max_cost_usd=max_cost_usd
        )

        logger.info(
            f"Routing {task_type} via {strategy} -> {provider} "
            f"(temp={temperature}, max_tokens={max_tokens})"
        )

        # Execute with resilience patterns
        try:
            response = await self._execute_with_resilience(
                provider=provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Update usage stats
            self._update_stats(
                task_type=task_type,
                strategy=strategy,
                provider=provider,
                cost=response.cost_usd,
                latency=response.latency_ms,
                fallback=response.fallback_used,
                error=False
            )

            return response

        except (CircuitBreakerError, RetryExhaustedError) as e:
            logger.error(f"Primary provider {provider} failed: {e}")

            # Try fallback providers
            fallback_providers = [
                p for p in self.available_providers.keys()
                if p != provider
            ]

            for fallback_provider in fallback_providers:
                try:
                    logger.info(f"Attempting fallback: {fallback_provider}")
                    response = await self._execute_with_resilience(
                        provider=fallback_provider,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    response.fallback_used = True

                    # Update stats
                    self._update_stats(
                        task_type=task_type,
                        strategy=strategy,
                        provider=fallback_provider,
                        cost=response.cost_usd,
                        latency=response.latency_ms,
                        fallback=True,
                        error=False
                    )

                    return response

                except Exception as fallback_error:
                    logger.error(f"Fallback {fallback_provider} failed: {fallback_error}")
                    continue

            # All providers failed
            self._update_stats(
                task_type=task_type,
                strategy=strategy,
                provider=provider,
                cost=0.0,
                latency=(datetime.now() - start_time).total_seconds() * 1000,
                fallback=False,
                error=True
            )

            raise RuntimeError(
                f"All providers failed for {task_type}. Check circuit breaker status."
            )

    async def stream(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        strategy_override: Optional[RoutingStrategy] = None,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream response tokens in real-time.

        Args:
            Same as route()

        Yields:
            Dict with keys: content (str), done (bool), metadata (optional)

        Example:
            >>> async for chunk in router.stream(
            ...     task_type=TaskType.CONTENT_GENERATION,
            ...     prompt="Write an email..."
            ... ):
            ...     if chunk["done"]:
            ...         print(f"\\nCost: ${chunk['metadata']['cost_usd']:.6f}")
            ...     else:
            ...         print(chunk["content"], end="", flush=True)
        """
        start_time = datetime.now()

        # Select strategy and provider
        strategy = strategy_override or DEFAULT_STRATEGY_MAP.get(
            task_type,
            RoutingStrategy.BALANCED
        )

        provider = self._select_provider(
            strategy=strategy,
            task_type=task_type,
            max_latency_ms=max_latency_ms,
            max_cost_usd=max_cost_usd
        )

        logger.info(f"Streaming {task_type} via {strategy} -> {provider}")

        # Execute streaming with resilience
        try:
            async for chunk in self._stream_with_resilience(
                provider=provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                # Add metadata to final chunk
                if chunk.get("done"):
                    latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    chunk["metadata"] = {
                        "provider": provider,
                        "model": self.available_providers[provider]["model"],
                        "strategy": strategy.value,
                        "task_type": task_type.value,
                        "latency_ms": latency_ms
                    }

                    # Update stats
                    self._update_stats(
                        task_type=task_type,
                        strategy=strategy,
                        provider=provider,
                        cost=chunk.get("cost_usd", 0.0),
                        latency=latency_ms,
                        fallback=False,
                        error=False
                    )

                yield chunk

        except Exception as e:
            logger.error(f"Streaming failed for {provider}: {e}")
            self._update_stats(
                task_type=task_type,
                strategy=strategy,
                provider=provider,
                cost=0.0,
                latency=(datetime.now() - start_time).total_seconds() * 1000,
                fallback=False,
                error=True
            )
            raise

    async def _execute_with_resilience(
        self,
        provider: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Execute model call with circuit breaker and retry protection."""
        circuit_breaker = self.circuit_breakers.get(provider)
        retry_strategy = self.retry_strategies.get(provider)

        async def make_call():
            return await self._call_provider(
                provider=provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

        # Apply circuit breaker
        if circuit_breaker:
            async def cb_wrapped():
                return await circuit_breaker.call(make_call)
            call_func = cb_wrapped
        else:
            call_func = make_call

        # Apply retry
        if retry_strategy:
            response = await retry_strategy.execute(call_func)
            response.retry_count = retry_strategy.max_retries
        else:
            response = await call_func()

        return response

    async def _stream_with_resilience(
        self,
        provider: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream with circuit breaker protection (retry not applicable)."""
        circuit_breaker = self.circuit_breakers.get(provider)

        async def stream_call():
            async for chunk in self._stream_provider(
                provider=provider,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                yield chunk

        # Apply circuit breaker
        if circuit_breaker:
            # Check circuit state before streaming
            if circuit_breaker.state.value == "open":
                raise CircuitBreakerError(f"Circuit breaker open for {provider}")

        async for chunk in stream_call():
            yield chunk

    async def _call_provider(
        self,
        provider: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Call specific provider (no resilience patterns here)."""
        start_time = datetime.now()

        if provider == "cerebras":
            return await self._call_cerebras(prompt, system_prompt, temperature, max_tokens, start_time)
        elif provider == "claude":
            return await self._call_claude(prompt, system_prompt, temperature, max_tokens, start_time)
        elif provider == "deepseek":
            return await self._call_deepseek(prompt, system_prompt, temperature, max_tokens, start_time)
        elif provider == "ollama":
            return await self._call_ollama(prompt, system_prompt, temperature, max_tokens, start_time)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _stream_provider(
        self,
        provider: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from specific provider."""
        if provider == "cerebras":
            async for chunk in self._stream_cerebras(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        elif provider == "claude":
            async for chunk in self._stream_claude(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        elif provider == "deepseek":
            async for chunk in self._stream_deepseek(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        elif provider == "ollama":
            async for chunk in self._stream_ollama(prompt, system_prompt, temperature, max_tokens):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ========================================================================
    # Provider-specific implementations
    # ========================================================================

    async def _call_cerebras(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, start_time: datetime
    ) -> ModelResponse:
        """Call Cerebras API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.cerebras_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["cerebras"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }
        cost = (tokens["total"] / 1000) * PROVIDER_CONFIGS["cerebras"]["cost_per_1k_tokens"]

        return ModelResponse(
            content=response.choices[0].message.content,
            model_used=PROVIDER_CONFIGS["cerebras"]["model"],
            provider="cerebras",
            latency_ms=latency_ms,
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_claude(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, start_time: datetime
    ) -> ModelResponse:
        """Call Claude API."""
        response = await self.anthropic_client.messages.create(
            model=PROVIDER_CONFIGS["claude"]["model"],
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}]
        )

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        tokens = {
            "prompt": response.usage.input_tokens,
            "completion": response.usage.output_tokens,
            "total": response.usage.input_tokens + response.usage.output_tokens
        }
        cost = (tokens["total"] / 1000) * PROVIDER_CONFIGS["claude"]["cost_per_1k_tokens"]

        return ModelResponse(
            content=response.content[0].text,
            model_used=PROVIDER_CONFIGS["claude"]["model"],
            provider="claude",
            latency_ms=latency_ms,
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_deepseek(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, start_time: datetime
    ) -> ModelResponse:
        """Call DeepSeek via OpenRouter."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.openrouter_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["deepseek"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }
        cost = (tokens["total"] / 1000) * PROVIDER_CONFIGS["deepseek"]["cost_per_1k_tokens"]

        return ModelResponse(
            content=response.choices[0].message.content,
            model_used=PROVIDER_CONFIGS["deepseek"]["model"],
            provider="deepseek",
            latency_ms=latency_ms,
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_ollama(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int, start_time: datetime
    ) -> ModelResponse:
        """Call Ollama local API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.ollama_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["ollama"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        tokens = {
            "prompt": response.usage.prompt_tokens if response.usage else 0,
            "completion": response.usage.completion_tokens if response.usage else 0,
            "total": response.usage.total_tokens if response.usage else 0
        }

        return ModelResponse(
            content=response.choices[0].message.content,
            model_used=PROVIDER_CONFIGS["ollama"]["model"],
            provider="ollama",
            latency_ms=latency_ms,
            cost_usd=0.0,  # Local, free
            tokens_used=tokens
        )

    async def _stream_cerebras(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from Cerebras."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.cerebras_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["cerebras"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        full_content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_content += content
                yield {"content": content, "done": False}

        # Final chunk with metadata
        tokens = len(full_content.split())  # Rough estimate
        cost = (tokens / 1000) * PROVIDER_CONFIGS["cerebras"]["cost_per_1k_tokens"]
        yield {"content": "", "done": True, "cost_usd": cost}

    async def _stream_claude(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from Claude."""
        async with self.anthropic_client.messages.stream(
            model=PROVIDER_CONFIGS["claude"]["model"],
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield {"content": text, "done": False}

            # Get final message for token count
            message = await stream.get_final_message()
            tokens = message.usage.input_tokens + message.usage.output_tokens
            cost = (tokens / 1000) * PROVIDER_CONFIGS["claude"]["cost_per_1k_tokens"]
            yield {"content": "", "done": True, "cost_usd": cost}

    async def _stream_deepseek(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from DeepSeek via OpenRouter."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.openrouter_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["deepseek"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        full_content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_content += content
                yield {"content": content, "done": False}

        tokens = len(full_content.split())
        cost = (tokens / 1000) * PROVIDER_CONFIGS["deepseek"]["cost_per_1k_tokens"]
        yield {"content": "", "done": True, "cost_usd": cost}

    async def _stream_ollama(
        self, prompt: str, system_prompt: Optional[str],
        temperature: float, max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from Ollama."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.ollama_async_client.chat.completions.create(
            model=PROVIDER_CONFIGS["ollama"]["model"],
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {"content": chunk.choices[0].delta.content, "done": False}

        yield {"content": "", "done": True, "cost_usd": 0.0}

    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================

    def _update_stats(
        self,
        task_type: TaskType,
        strategy: RoutingStrategy,
        provider: str,
        cost: float,
        latency: int,
        fallback: bool,
        error: bool
    ):
        """Update usage statistics."""
        self.usage_stats["total_requests"] += 1

        if not error:
            self.usage_stats["provider_usage"][provider] += 1
            self.usage_stats["total_cost"] += cost
            self.usage_stats["total_latency_ms"] += latency

            # Track by strategy
            strategy_key = strategy.value
            self.usage_stats["strategy_usage"][strategy_key] = \
                self.usage_stats["strategy_usage"].get(strategy_key, 0) + 1

            # Track by task type
            task_key = task_type.value
            self.usage_stats["task_type_usage"][task_key] = \
                self.usage_stats["task_type_usage"].get(task_key, 0) + 1

        if fallback:
            self.usage_stats["fallback_count"] += 1

        if error:
            self.usage_stats["error_count"] += 1

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive router status.

        Returns:
            Dict with:
            - circuit_breaker_states: State of each provider's circuit breaker
            - provider_availability: Which providers are configured
            - current_strategy_map: Auto task-to-strategy mappings
            - usage_stats: Request counts, costs, latencies
            - cost_savings: Estimated savings vs using premium provider
            - health_status: Overall system health
        """
        # Circuit breaker states
        cb_states = {}
        for provider, cb in self.circuit_breakers.items():
            cb_states[provider] = {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "threshold": cb.failure_threshold,
                "recovery_timeout": cb.recovery_timeout
            }

        # Calculate cost savings
        total_requests = self.usage_stats["total_requests"]
        actual_cost = self.usage_stats["total_cost"]

        # Cost if all went to Claude (most expensive)
        claude_only_cost = total_requests * (500 / 1000) * PROVIDER_CONFIGS["claude"]["cost_per_1k_tokens"]

        cost_savings = {
            "actual_cost_usd": actual_cost,
            "claude_only_cost_usd": claude_only_cost,
            "savings_usd": claude_only_cost - actual_cost,
            "savings_percent": ((claude_only_cost - actual_cost) / claude_only_cost * 100) if claude_only_cost > 0 else 0
        }

        # Health status
        error_rate = (self.usage_stats["error_count"] / total_requests * 100) if total_requests > 0 else 0
        health = "healthy" if error_rate < 5 else "degraded" if error_rate < 20 else "unhealthy"

        # Average metrics
        avg_latency = (
            self.usage_stats["total_latency_ms"] / total_requests
            if total_requests > 0 else 0
        )
        avg_cost = actual_cost / total_requests if total_requests > 0 else 0

        return {
            "circuit_breaker_states": cb_states,
            "provider_availability": list(self.available_providers.keys()),
            "current_strategy_map": {
                task.value: strategy.value
                for task, strategy in DEFAULT_STRATEGY_MAP.items()
            },
            "usage_stats": {
                **self.usage_stats,
                "average_latency_ms": avg_latency,
                "average_cost_usd": avg_cost,
                "error_rate_percent": error_rate
            },
            "cost_savings": cost_savings,
            "health_status": health
        }
