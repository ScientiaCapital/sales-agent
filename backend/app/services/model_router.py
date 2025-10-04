"""Intelligent model routing with circuit breaker and retry patterns.

Routes AI requests to optimal models based on task type, latency, and cost constraints.
Implements resilience patterns to handle service failures gracefully.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, AsyncIterator

import aiohttp
from openai import OpenAI, AsyncOpenAI

from .circuit_breaker import CircuitBreaker, CircuitBreakerError
from .retry_handler import RetryWithBackoff, RetryStrategies, RetryExhaustedError

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of AI tasks with different optimization requirements."""
    QUALIFICATION = "qualification"           # Fast inference, low cost
    CONTENT_GENERATION = "content_generation" # High quality, moderate cost
    RESEARCH = "research"                     # Cost-effective, comprehensive
    SIMPLE_PARSING = "simple_parsing"         # Local/cheap, basic extraction


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


class ModelRouter:
    """
    Intelligent routing of AI requests to optimal models.

    Features:
    - Task-based routing with performance constraints
    - Circuit breaker pattern for fault tolerance
    - Exponential backoff retry for transient failures
    - Automatic fallback on primary model failure
    - Cost and latency tracking
    """

    def __init__(self):
        """Initialize model router with configurations and clients."""
        # Circuit breakers for each provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            "cerebras": CircuitBreaker("cerebras", failure_threshold=5, recovery_timeout=60),
            "anthropic": CircuitBreaker("anthropic", failure_threshold=3, recovery_timeout=120),
            "deepseek": CircuitBreaker("deepseek", failure_threshold=5, recovery_timeout=90),
            "ollama": CircuitBreaker("ollama", failure_threshold=10, recovery_timeout=30),
        }

        # Retry strategies for each provider
        self.retry_strategies: Dict[str, RetryWithBackoff] = {
            "cerebras": RetryStrategies.standard(),
            "anthropic": RetryStrategies.conservative(),  # Rate limits
            "deepseek": RetryStrategies.standard(),
            "ollama": RetryStrategies.aggressive(),  # Local, can retry fast
        }

        # Task-based routing rules
        self.routing_rules: Dict[TaskType, List[ModelConfig]] = {
            TaskType.QUALIFICATION: [
                ModelConfig(
                    provider="cerebras",
                    model="llama3.1-8b",
                    max_latency_ms=1000,
                    max_cost_usd=0.0001
                )
            ],
            TaskType.CONTENT_GENERATION: [
                ModelConfig(
                    provider="anthropic",
                    model="claude-3-sonnet-20240229",
                    max_latency_ms=5000,
                    max_cost_usd=0.01
                ),
                ModelConfig(
                    provider="cerebras",
                    model="llama3.1-70b",
                    max_latency_ms=2000,
                    max_cost_usd=0.001,
                    fallback=True
                )
            ],
            TaskType.RESEARCH: [
                ModelConfig(
                    provider="deepseek",
                    model="deepseek/deepseek-chat",
                    via="openrouter",
                    max_latency_ms=10000,
                    max_cost_usd=0.001
                )
            ],
            TaskType.SIMPLE_PARSING: [
                ModelConfig(
                    provider="ollama",
                    model="llama3.2",
                    local=True,
                    max_latency_ms=3000,
                    max_cost_usd=0.0
                )
            ]
        }

        # Initialize API clients
        self._init_clients()

        logger.info("ModelRouter initialized with circuit breakers and retry handlers")

    def _init_clients(self):
        """Initialize API clients for each provider."""
        # Cerebras client (OpenAI-compatible)
        self.cerebras_client = None
        if os.getenv("CEREBRAS_API_KEY"):
            self.cerebras_client = AsyncOpenAI(
                api_key=os.getenv("CEREBRAS_API_KEY"),
                base_url=os.getenv("CEREBRAS_API_BASE", "https://api.cerebras.ai/v1")
            )
            logger.info("Cerebras client initialized")

        # Anthropic client
        self.anthropic_client = None
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                from anthropic import AsyncAnthropic
                self.anthropic_client = AsyncAnthropic(
                    api_key=os.getenv("ANTHROPIC_API_KEY")
                )
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.warning("Anthropic SDK not installed, Claude models unavailable")

        # DeepSeek via OpenRouter
        self.openrouter_client = None
        if os.getenv("OPENROUTER_API_KEY"):
            self.openrouter_client = AsyncOpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("OpenRouter client initialized for DeepSeek")

        # Ollama local endpoint
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"Ollama configured at {self.ollama_base_url}")

    async def route_request(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> ModelResponse:
        """
        Route a request to the optimal model with resilience patterns.

        Args:
            task_type: Type of task (determines model selection)
            prompt: User prompt/content
            system_prompt: Optional system prompt
            max_latency_ms: Override max latency constraint
            max_cost_usd: Override max cost constraint
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum response tokens

        Returns:
            ModelResponse with result and metadata

        Raises:
            CircuitBreakerError: If all models are unavailable
            RetryExhaustedError: If retries exhausted
        """
        # Get routing rules for task type
        models = self.routing_rules.get(task_type, [])
        if not models:
            raise ValueError(f"No routing rules defined for task type: {task_type}")

        # Filter by constraints
        filtered_models = self._filter_by_constraints(
            models,
            max_latency_ms or 10000,
            max_cost_usd or 1.0
        )

        if not filtered_models:
            raise ValueError(
                f"No models available for {task_type} with constraints: "
                f"latency<={max_latency_ms}ms, cost<=${max_cost_usd}"
            )

        # Separate primary and fallback models
        primary_models = [m for m in filtered_models if not m.fallback]
        fallback_models = [m for m in filtered_models if m.fallback]

        # Try primary models first
        for model_config in primary_models:
            try:
                response = await self._call_model(
                    model_config,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens
                )
                response.fallback_used = False
                return response

            except (CircuitBreakerError, RetryExhaustedError) as e:
                logger.warning(
                    f"Primary model {model_config.provider}/{model_config.model} failed: {e}"
                )
                continue

        # Try fallback models if primary failed
        for model_config in fallback_models:
            try:
                logger.info(
                    f"Attempting fallback: {model_config.provider}/{model_config.model}"
                )
                response = await self._call_model(
                    model_config,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens
                )
                response.fallback_used = True
                return response

            except (CircuitBreakerError, RetryExhaustedError) as e:
                logger.error(
                    f"Fallback model {model_config.provider}/{model_config.model} failed: {e}"
                )
                continue

        # All models failed
        raise RuntimeError(
            f"All models failed for task type {task_type}. "
            f"Check circuit breaker status."
        )

    async def stream_request(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_latency_ms: Optional[int] = None,
        max_cost_usd: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a request to the optimal model with progressive token delivery.

        Args:
            task_type: Type of task (determines model selection)
            prompt: User prompt/content
            system_prompt: Optional system prompt
            max_latency_ms: Override max latency constraint
            max_cost_usd: Override max cost constraint
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum response tokens

        Yields:
            Dict with type="token" for progressive tokens, type="complete" for final metadata

        Raises:
            CircuitBreakerError: If all models are unavailable
            RetryExhaustedError: If retries exhausted
        """
        # Get routing rules for task type
        models = self.routing_rules.get(task_type, [])
        if not models:
            raise ValueError(f"No routing rules defined for task type: {task_type}")

        # Filter by constraints
        filtered_models = self._filter_by_constraints(
            models,
            max_latency_ms or 10000,
            max_cost_usd or 1.0
        )

        if not filtered_models:
            raise ValueError(
                f"No models available for {task_type} with constraints: "
                f"latency<={max_latency_ms}ms, cost<=${max_cost_usd}"
            )

        # Separate primary and fallback models
        primary_models = [m for m in filtered_models if not m.fallback]
        fallback_models = [m for m in filtered_models if m.fallback]

        # Try primary models first
        for model_config in primary_models:
            try:
                async for chunk in self._stream_model(
                    model_config,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens
                ):
                    chunk["fallback_used"] = False
                    yield chunk
                return  # Success, exit

            except (CircuitBreakerError, RetryExhaustedError) as e:
                logger.warning(
                    f"Primary streaming model {model_config.provider}/{model_config.model} failed: {e}"
                )
                continue

        # Try fallback models if primary failed
        for model_config in fallback_models:
            try:
                logger.info(
                    f"Attempting fallback stream: {model_config.provider}/{model_config.model}"
                )
                async for chunk in self._stream_model(
                    model_config,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens
                ):
                    chunk["fallback_used"] = True
                    yield chunk
                return  # Success, exit

            except (CircuitBreakerError, RetryExhaustedError) as e:
                logger.error(
                    f"Fallback streaming model {model_config.provider}/{model_config.model} failed: {e}"
                )
                continue

        # All models failed
        raise RuntimeError(
            f"All streaming models failed for task type {task_type}. "
            f"Check circuit breaker status."
        )

    def _filter_by_constraints(
        self,
        models: List[ModelConfig],
        max_latency_ms: int,
        max_cost_usd: float
    ) -> List[ModelConfig]:
        """Filter models by latency and cost constraints."""
        return [
            m for m in models
            if m.max_latency_ms <= max_latency_ms and m.max_cost_usd <= max_cost_usd
        ]

    async def _call_model(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """
        Call a specific model with circuit breaker and retry.

        Args:
            config: Model configuration
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Model temperature
            max_tokens: Maximum tokens

        Returns:
            ModelResponse with result and metadata
        """
        circuit_breaker = self.circuit_breakers[config.provider]
        retry_handler = self.retry_strategies[config.provider]

        # Wrap the model call with retry logic
        async def call_with_retry():
            return await retry_handler.execute(
                self._execute_model_call,
                config,
                prompt,
                system_prompt,
                temperature,
                max_tokens
            )

        # Execute with circuit breaker protection
        return await circuit_breaker.call(call_with_retry)

    async def _stream_model(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream from a specific model with circuit breaker and retry.

        Args:
            config: Model configuration
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Model temperature
            max_tokens: Maximum tokens

        Yields:
            Dict chunks with progressive tokens and final metadata
        """
        circuit_breaker = self.circuit_breakers[config.provider]
        retry_handler = self.retry_strategies[config.provider]

        # Wrap the streaming call with retry logic
        async def stream_with_retry():
            async for chunk in retry_handler.execute_streaming(
                self._execute_streaming_call,
                config,
                prompt,
                system_prompt,
                temperature,
                max_tokens
            ):
                yield chunk

        # Execute with circuit breaker protection
        async for chunk in circuit_breaker.call_streaming(stream_with_retry):
            yield chunk

    async def _execute_streaming_call(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute the actual streaming model API call."""
        start_time = time.time()

        try:
            if config.provider == "cerebras":
                stream = self._call_cerebras_streaming(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "anthropic":
                stream = self._call_claude_streaming(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "deepseek":
                stream = self._call_deepseek_streaming(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "ollama":
                stream = self._call_ollama_streaming(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            else:
                raise ValueError(f"Unknown provider: {config.provider}")

            # Stream chunks and track latency
            async for chunk in stream:
                chunk["provider"] = config.provider
                chunk["model"] = config.model
                yield chunk

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Streaming call completed: {config.provider}/{config.model} ({latency_ms}ms)"
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Streaming call failed: {config.provider}/{config.model} "
                f"after {latency_ms}ms - {type(e).__name__}: {str(e)}"
            )
            raise

    async def _execute_model_call(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Execute the actual model API call."""
        start_time = time.time()

        try:
            if config.provider == "cerebras":
                response = await self._call_cerebras(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "anthropic":
                response = await self._call_claude(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "deepseek":
                response = await self._call_deepseek_via_openrouter(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            elif config.provider == "ollama":
                response = await self._call_local_ollama(
                    config.model, prompt, system_prompt, temperature, max_tokens
                )
            else:
                raise ValueError(f"Unknown provider: {config.provider}")

            latency_ms = int((time.time() - start_time) * 1000)
            response.latency_ms = latency_ms

            logger.info(
                f"Model call succeeded: {config.provider}/{config.model} "
                f"({latency_ms}ms, ${response.cost_usd:.6f})"
            )

            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                f"Model call failed: {config.provider}/{config.model} "
                f"after {latency_ms}ms - {type(e).__name__}: {str(e)}"
            )
            raise

    async def _call_cerebras(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Call Cerebras API using OpenAI-compatible client."""
        if not self.cerebras_client:
            raise RuntimeError("Cerebras client not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.cerebras_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }

        # Cerebras pricing: $0.10/M tokens (both input/output)
        cost = (tokens["total"] / 1_000_000) * 0.10

        return ModelResponse(
            content=content,
            model_used=model,
            provider="cerebras",
            latency_ms=0,  # Set by caller
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_claude(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Call Anthropic Claude API."""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")

        message = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}]
        )

        content = message.content[0].text
        tokens = {
            "prompt": message.usage.input_tokens,
            "completion": message.usage.output_tokens,
            "total": message.usage.input_tokens + message.usage.output_tokens
        }

        # Claude 3 Sonnet pricing: $3/M input, $15/M output
        cost = (
            (tokens["prompt"] / 1_000_000) * 3.0 +
            (tokens["completion"] / 1_000_000) * 15.0
        )

        return ModelResponse(
            content=content,
            model_used=model,
            provider="anthropic",
            latency_ms=0,
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_deepseek_via_openrouter(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Call DeepSeek via OpenRouter."""
        if not self.openrouter_client:
            raise RuntimeError("OpenRouter client not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.openrouter_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content
        tokens = {
            "prompt": response.usage.prompt_tokens,
            "completion": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }

        # DeepSeek v3 via OpenRouter: $0.27/M input, $1.10/M output
        cost = (
            (tokens["prompt"] / 1_000_000) * 0.27 +
            (tokens["completion"] / 1_000_000) * 1.10
        )

        return ModelResponse(
            content=content,
            model_used=model,
            provider="deepseek",
            latency_ms=0,
            cost_usd=cost,
            tokens_used=tokens
        )

    async def _call_local_ollama(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> ModelResponse:
        """Call local Ollama API."""
        url = f"{self.ollama_base_url}/api/generate"

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": model,
            "prompt": full_prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "stream": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

        content = data.get("response", "")
        
        return ModelResponse(
            content=content,
            model_used=model,
            provider="ollama",
            latency_ms=0,
            cost_usd=0.0,  # Local = free
            tokens_used={}
        )

    async def _call_cerebras_streaming(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from Cerebras API using OpenAI-compatible client."""
        if not self.cerebras_client:
            raise RuntimeError("Cerebras client not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        accumulated_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        stream = await self.cerebras_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated_text += token
                completion_tokens += 1

                yield {
                    "type": "token",
                    "content": token,
                    "accumulated": accumulated_text
                }

        # Estimate tokens (Cerebras doesn't provide in streaming)
        prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
        total_tokens = prompt_tokens + completion_tokens
        cost = (total_tokens / 1_000_000) * 0.10

        yield {
            "type": "complete",
            "metadata": {
                "tokens_used": {
                    "prompt": int(prompt_tokens),
                    "completion": completion_tokens,
                    "total": int(total_tokens)
                },
                "cost_usd": cost
            }
        }

    async def _call_claude_streaming(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from Anthropic Claude API."""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")

        accumulated_text = ""

        async with self.anthropic_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt if system_prompt else None
        ) as stream:
            async for text in stream.text_stream:
                accumulated_text += text
                yield {
                    "type": "token",
                    "content": text,
                    "accumulated": accumulated_text
                }

            # Get final message for usage stats
            final_message = await stream.get_final_message()
            tokens = {
                "prompt": final_message.usage.input_tokens,
                "completion": final_message.usage.output_tokens,
                "total": final_message.usage.input_tokens + final_message.usage.output_tokens
            }

            # Claude 3 Sonnet pricing: $3/M input, $15/M output
            cost = (
                (tokens["prompt"] / 1_000_000) * 3.0 +
                (tokens["completion"] / 1_000_000) * 15.0
            )

            yield {
                "type": "complete",
                "metadata": {
                    "tokens_used": tokens,
                    "cost_usd": cost
                }
            }

    async def _call_deepseek_streaming(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from DeepSeek via OpenRouter."""
        if not self.openrouter_client:
            raise RuntimeError("OpenRouter client not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        accumulated_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        stream = await self.openrouter_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated_text += token
                completion_tokens += 1

                yield {
                    "type": "token",
                    "content": token,
                    "accumulated": accumulated_text
                }

        # Estimate tokens
        prompt_tokens = len(prompt.split()) * 1.3
        total_tokens = prompt_tokens + completion_tokens

        # DeepSeek v3 via OpenRouter: $0.27/M input, $1.10/M output
        cost = (
            (prompt_tokens / 1_000_000) * 0.27 +
            (completion_tokens / 1_000_000) * 1.10
        )

        yield {
            "type": "complete",
            "metadata": {
                "tokens_used": {
                    "prompt": int(prompt_tokens),
                    "completion": completion_tokens,
                    "total": int(total_tokens)
                },
                "cost_usd": cost
            }
        }

    async def _call_ollama_streaming(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream from local Ollama API."""
        url = f"{self.ollama_base_url}/api/generate"

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": model,
            "prompt": full_prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "stream": True
        }

        accumulated_text = ""

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        data = json.loads(line)
                        if "response" in data:
                            token = data["response"]
                            accumulated_text += token
                            
                            yield {
                                "type": "token",
                                "content": token,
                                "accumulated": accumulated_text
                            }
                        
                        if data.get("done"):
                            yield {
                                "type": "complete",
                                "metadata": {
                                    "tokens_used": {},
                                    "cost_usd": 0.0  # Local = free
                                }
                            }
                            break

    def get_status(self) -> Dict[str, Any]:
        """Get router status including circuit breaker states."""
        return {
            "circuit_breakers": {
                name: cb.get_status()
                for name, cb in self.circuit_breakers.items()
            },
            "retry_configs": {
                name: strategy.get_config()
                for name, strategy in self.retry_strategies.items()
            },
            "routing_rules": {
                task_type.value: [
                    {
                        "provider": m.provider,
                        "model": m.model,
                        "fallback": m.fallback
                    }
                    for m in models
                ]
                for task_type, models in self.routing_rules.items()
            }
        }
