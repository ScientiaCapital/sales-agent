"""
LangChain-compatible wrapper for Cerebras Cloud API

Provides ultra-fast inference (633ms target) with full LangChain integration
including streaming, callbacks, and cost tracking.
"""

import os
import time
import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.outputs import GenerationChunk, LLMResult, Generation
from pydantic import Field, SecretStr, field_validator
from openai import OpenAI, AsyncOpenAI

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError, MissingAPIKeyError

logger = setup_logging(__name__)


class CerebrasLLM(LLM):
    """LangChain wrapper for Cerebras Inference API.

    Uses OpenAI SDK with custom base_url for ultra-fast inference.
    Target latency: 633ms for llama3.1-8b model.
    Cost: $0.10/M input tokens, $0.10/M output tokens.

    Features:
    - Streaming support with real-time token delivery
    - LangSmith callback integration for tracing
    - Cost and latency tracking
    - Both sync and async operations
    - Compatible with LCEL chains and LangGraph nodes

    Example:
        ```python
        from app.services.langchain.cerebras_llm import CerebrasLLM

        # Initialize
        llm = CerebrasLLM(
            api_key="csk-...",
            model="llama3.1-8b",
            temperature=0.7,
            streaming=True
        )

        # Synchronous call
        response = llm.invoke("Explain quantum computing in one sentence")

        # Streaming
        for chunk in llm.stream("Write a haiku about AI"):
            print(chunk, end="", flush=True)

        # Use in LCEL chain
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        prompt = PromptTemplate.from_template("Qualify this lead: {lead_info}")
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"lead_info": "Company: Acme Corp, Industry: SaaS"})
        ```
    """

    # ========== Configuration ==========

    api_key: SecretStr = Field(
        description="Cerebras API key (starts with 'csk-')",
        alias="cerebras_api_key"
    )

    base_url: str = Field(
        default="https://api.cerebras.ai/v1",
        description="Cerebras API base URL"
    )

    model: str = Field(
        default="llama3.1-8b",
        description="Model name (llama3.1-8b for ultra-fast, llama3.1-70b for quality)"
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 = deterministic, 2.0 = creative)"
    )

    max_tokens: int = Field(
        default=500,
        gt=0,
        description="Maximum tokens to generate"
    )

    streaming: bool = Field(
        default=True,
        description="Enable streaming for real-time token delivery"
    )

    timeout: Optional[int] = Field(
        default=30,
        description="Request timeout in seconds"
    )

    max_retries: int = Field(
        default=2,
        description="Maximum retries for failed requests"
    )

    # ========== Internal State ==========

    _client: Optional[OpenAI] = None
    _async_client: Optional[AsyncOpenAI] = None

    # ========== Pydantic Configuration ==========

    model_config = {
        "populate_by_name": True,  # Allow alias population
        "arbitrary_types_allowed": True,  # Allow OpenAI client types
        "extra": "forbid"  # Prevent typos in configuration
    }

    # ========== Validators ==========

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: Any) -> SecretStr:
        """Validate API key is present and has correct format."""
        if isinstance(v, SecretStr):
            key = v.get_secret_value()
        else:
            key = v

        if not key:
            raise MissingAPIKeyError(
                "CEREBRAS_API_KEY environment variable not set",
                context={"api_key": "CEREBRAS_API_KEY"}
            )

        if not key.startswith("csk-"):
            logger.warning(
                f"Cerebras API key should start with 'csk-'. "
                f"Current key starts with: {key[:4]}..."
            )

        return SecretStr(key) if not isinstance(v, SecretStr) else v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model name is supported."""
        supported_models = ["llama3.1-8b", "llama3.1-70b"]
        if v not in supported_models:
            logger.warning(
                f"Model '{v}' may not be supported. "
                f"Supported models: {supported_models}"
            )
        return v

    # ========== Client Initialization ==========

    @property
    def client(self) -> OpenAI:
        """Lazy-load synchronous OpenAI client with Cerebras base URL."""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key.get_secret_value(),
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
        return self._client

    @property
    def async_client(self) -> AsyncOpenAI:
        """Lazy-load asynchronous OpenAI client with Cerebras base URL."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key.get_secret_value(),
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
        return self._async_client

    # ========== Required LangChain Methods ==========

    @property
    def _llm_type(self) -> str:
        """Return LLM type for logging purposes."""
        return "cerebras"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters for LangSmith monitoring.

        Used for token pricing and model tracking in LangSmith dashboard.
        """
        return {
            "model_name": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "streaming": self.streaming,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Synchronous call to Cerebras API.

        Args:
            prompt: The prompt to generate from
            stop: Stop words to use when generating
            run_manager: Callback manager for LangSmith tracing
            **kwargs: Additional parameters to pass to API

        Returns:
            Generated text (completion only, without prompt)

        Raises:
            CerebrasAPIError: If API call fails
        """
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop,
                stream=False,
                **kwargs
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = response.choices[0].message.content or ""

            # Log metrics
            if response.usage:
                cost_info = self.calculate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
                logger.info(
                    f"Cerebras API call completed - "
                    f"latency={latency_ms}ms, "
                    f"tokens={response.usage.total_tokens}, "
                    f"cost=${cost_info['total_cost_usd']:.6f}"
                )

            return content

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Cerebras API error after {latency_ms}ms: {e}", exc_info=True)
            raise CerebrasAPIError(
                message="Cerebras inference failed",
                details={
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Stream tokens from Cerebras API in real-time.

        Args:
            prompt: The prompt to generate from
            stop: Stop words to use when generating
            run_manager: Callback manager for LangSmith tracing
            **kwargs: Additional parameters to pass to API

        Yields:
            GenerationChunk objects containing individual tokens

        Raises:
            CerebrasAPIError: If streaming fails
        """
        start_time = time.time()

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop,
                stream=True,
                **kwargs
            )

            for chunk in stream:
                # Extract token from delta
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    generation_chunk = GenerationChunk(text=token)

                    # CRITICAL: Notify callback manager for LangSmith tracing
                    if run_manager:
                        run_manager.on_llm_new_token(token, chunk=generation_chunk)

                    yield generation_chunk

            # Log completion
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Cerebras streaming completed - latency={latency_ms}ms")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Cerebras streaming error after {latency_ms}ms: {e}", exc_info=True)
            raise CerebrasAPIError(
                message="Cerebras streaming failed",
                details={
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    # ========== Async Methods ==========

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Asynchronous call to Cerebras API.

        Args:
            prompt: The prompt to generate from
            stop: Stop words to use when generating
            run_manager: Async callback manager for LangSmith tracing
            **kwargs: Additional parameters to pass to API

        Returns:
            Generated text (completion only, without prompt)

        Raises:
            CerebrasAPIError: If API call fails
        """
        start_time = time.time()

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop,
                stream=False,
                **kwargs
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = response.choices[0].message.content or ""

            # Log metrics
            if response.usage:
                cost_info = self.calculate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
                logger.info(
                    f"Cerebras async API call completed - "
                    f"latency={latency_ms}ms, "
                    f"tokens={response.usage.total_tokens}, "
                    f"cost=${cost_info['total_cost_usd']:.6f}"
                )

            return content

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Cerebras async API error after {latency_ms}ms: {e}", exc_info=True)
            raise CerebrasAPIError(
                message="Cerebras async inference failed",
                details={
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    async def _astream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk]:
        """Asynchronously stream tokens from Cerebras API.

        Args:
            prompt: The prompt to generate from
            stop: Stop words to use when generating
            run_manager: Async callback manager for LangSmith tracing
            **kwargs: Additional parameters to pass to API

        Yields:
            GenerationChunk objects containing individual tokens

        Raises:
            CerebrasAPIError: If streaming fails
        """
        start_time = time.time()

        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                # Extract token from delta
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    generation_chunk = GenerationChunk(text=token)

                    # CRITICAL: Notify callback manager for LangSmith tracing
                    if run_manager:
                        await run_manager.on_llm_new_token(token, chunk=generation_chunk)

                    yield generation_chunk

            # Log completion
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Cerebras async streaming completed - latency={latency_ms}ms")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Cerebras async streaming error after {latency_ms}ms: {e}", exc_info=True)
            raise CerebrasAPIError(
                message="Cerebras async streaming failed",
                details={
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    # ========== Cost Calculation ==========

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Dict[str, float]:
        """Calculate API call cost based on token usage.

        Cerebras pricing (as of January 2025):
        - llama3.1-8b: $0.10/M input, $0.10/M output
        - llama3.1-70b: $0.60/M input, $0.60/M output

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Dict with input_cost_usd, output_cost_usd, and total_cost_usd
        """
        # Pricing per million tokens
        pricing = {
            "llama3.1-8b": {"input": 0.10, "output": 0.10},
            "llama3.1-70b": {"input": 0.60, "output": 0.60}
        }

        prices = pricing.get(self.model, {"input": 0.10, "output": 0.10})

        input_cost = (prompt_tokens / 1_000_000) * prices["input"]
        output_cost = (completion_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost

        return {
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6)
        }


def get_cerebras_llm(
    model: str = "llama3.1-8b",
    temperature: float = 0.7,
    max_tokens: int = 500,
    streaming: bool = True,
    **kwargs
) -> CerebrasLLM:
    """Convenience function to create CerebrasLLM instance.

    Automatically loads API key from environment variable CEREBRAS_API_KEY.

    Args:
        model: Model name (llama3.1-8b or llama3.1-70b)
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        streaming: Enable streaming
        **kwargs: Additional parameters for CerebrasLLM

    Returns:
        Configured CerebrasLLM instance

    Example:
        ```python
        from app.services.langchain.cerebras_llm import get_cerebras_llm

        # Quick setup
        llm = get_cerebras_llm(temperature=0.3, max_tokens=200)
        response = llm.invoke("Qualify this lead...")
        ```
    """
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "CEREBRAS_API_KEY environment variable not set",
            context={"api_key": "CEREBRAS_API_KEY"}
        )

    return CerebrasLLM(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        **kwargs
    )
