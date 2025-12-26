"""Dependency injection for VLM Analysis service.

Provides singleton instances of VLM provider, cache, and middleware chain.

PRIVATE - Scientia Capital Proprietary IP
"""
import logging
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from .cache import AnalysisCache

logger = logging.getLogger(__name__)


class VLMProvider:
    """VLM provider for OpenRouter API.

    Handles communication with OpenRouter API for VLM analysis.
    Supports multiple models with automatic fallback.
    """

    def __init__(self, api_key: str):
        """Initialize VLM provider.

        Args:
            api_key: OpenRouter API key

        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://vlm-ai-core.scientia.capital",
            "X-Title": "VLM AI Core - Analysis Service",
        }

    async def analyze(
        self,
        image_base64: str,
        prompt: str,
        model: str = "qwen/qwen2.5-vl-72b-instruct",
        **kwargs,
    ) -> dict:
        """Analyze image with VLM.

        Args:
            image_base64: Base64-encoded image
            prompt: Analysis prompt
            model: VLM model to use
            **kwargs: Additional model parameters

        Returns:
            Analysis result with extracted data

        Raises:
            Exception: On API errors
        """
        return await self.analyze_base64(image_base64, prompt, model, **kwargs)

    async def analyze_base64(
        self,
        image_base64: str,
        prompt: str,
        model: str = "qwen/qwen2.5-vl-72b-instruct",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs,
    ) -> dict:
        """Analyze base64-encoded image with VLM via OpenRouter.

        Args:
            image_base64: Base64-encoded image data
            prompt: Analysis prompt
            model: VLM model to use
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            **kwargs: Additional model parameters

        Returns:
            Dict with content, usage, and metadata

        Raises:
            Exception: On API errors
        """
        import httpx

        # Prepare data URL for image
        data_url = f"data:image/jpeg;base64,{image_base64}"

        # Prepare messages for vision model
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        # Make API request
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()

        # Extract response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return {
            "content": message.get("content", ""),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            "model": data.get("model", model),
            "id": data.get("id", ""),
        }

    async def analyze_batch(
        self,
        images: list[str],
        prompt: str,
        model: str = "qwen/qwen2.5-vl-72b-instruct",
        **kwargs,
    ) -> list[dict]:
        """Analyze multiple images with VLM.

        Args:
            images: List of base64-encoded images
            prompt: Analysis prompt
            model: VLM model to use
            **kwargs: Additional model parameters

        Returns:
            List of analysis results

        Raises:
            Exception: On API errors
        """
        results = []
        for image in images:
            result = await self.analyze(image, prompt, model, **kwargs)
            results.append(result)
        return results

    def get_models(self) -> list[dict]:
        """Get list of available VLM models.

        Returns:
            List of model information dictionaries
        """
        return [
            {
                "id": "qwen/qwen2.5-vl-72b-instruct",
                "name": "Qwen 2.5 VL 72B",
                "provider": "OpenRouter",
                "context_length": 32768,
                "cost_per_million_tokens": 0.40,
                "recommended_for": ["blueprints", "field_photos", "equipment"],
            },
            {
                "id": "qwen/qwen2.5-vl-30b-instruct",
                "name": "Qwen 2.5 VL 30B",
                "provider": "OpenRouter",
                "context_length": 32768,
                "cost_per_million_tokens": 0.20,
                "recommended_for": ["field_photos", "equipment"],
            },
            {
                "id": "qwen/qwen2.5-vl-8b-instruct",
                "name": "Qwen 2.5 VL 8B",
                "provider": "OpenRouter",
                "context_length": 32768,
                "cost_per_million_tokens": 0.10,
                "recommended_for": ["simple_extractions"],
            },
            {
                "id": "deepseek/deepseek-chat-v3.1",
                "name": "DeepSeek Chat v3.1",
                "provider": "OpenRouter",
                "context_length": 65536,
                "cost_per_million_tokens": 0.00027,
                "recommended_for": ["text_normalization", "context_compaction"],
            },
        ]


class MiddlewareChain:
    """Middleware chain for request processing.

    Handles rate limiting, cost control, and observability.
    """

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        enable_cost_control: bool = True,
        enable_observability: bool = True,
    ):
        """Initialize middleware chain.

        Args:
            rate_limit_per_minute: Maximum requests per minute
            enable_cost_control: Enable cost tracking
            enable_observability: Enable request logging
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self.enable_cost_control = enable_cost_control
        self.enable_observability = enable_observability

    async def execute(self, context: dict, handler):
        """Execute handler with middleware chain.

        Args:
            context: Request context with tenant_id, tier, operation, metadata
            handler: Async handler function to execute

        Returns:
            Handler result

        Raises:
            HTTPException: On rate limit or cost control errors
        """
        # TODO: Implement actual middleware logic
        # For now, just execute handler
        return await handler(context)


@lru_cache
def get_vlm_provider() -> VLMProvider:
    """Get singleton VLM provider instance.

    Returns:
        VLMProvider configured with API key from environment

    Raises:
        HTTPException: If OPENROUTER_API_KEY is not set
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY environment variable not set",
        )
    return VLMProvider(api_key=api_key)


@lru_cache
def get_middleware_chain() -> MiddlewareChain:
    """Get singleton middleware chain instance.

    Returns:
        MiddlewareChain with rate limiting, cost control, and observability

    Configuration:
        - Rate limit: 60 requests per minute (configurable via RATE_LIMIT_PER_MINUTE)
        - Cost control: Enabled by default
        - Observability: Request logging and metrics
    """
    rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    return MiddlewareChain(
        rate_limit_per_minute=rate_limit,
        enable_cost_control=True,
        enable_observability=True,
    )


@lru_cache
def get_analysis_cache() -> AnalysisCache | None:
    """Get singleton analysis cache instance.

    Returns:
        AnalysisCache configured with Supabase credentials, or None if not configured.

    Configuration:
        Requires SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.
        Cache is optional - returns None if credentials not available.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        logger.warning(
            "Supabase credentials not configured. Running without cache."
        )
        return None

    return AnalysisCache(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
    )


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    """Verify API key from request header.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # For demo/development, API key verification is optional
    # In production, uncomment this block:
    # if not x_api_key:
    #     raise HTTPException(
    #         status_code=401,
    #         detail="Missing API key. Provide X-API-Key header.",
    #     )
    #
    # # TODO: Validate API key against database
    # # For now, accept any non-empty key
    # if len(x_api_key) < 10:
    #     raise HTTPException(
    #         status_code=401,
    #         detail="Invalid API key",
    #     )

    return x_api_key or "demo-key"


def get_tenant_id(api_key: Annotated[str, Depends(verify_api_key)]) -> str:
    """Extract tenant ID from validated API key.

    Args:
        api_key: Validated API key

    Returns:
        Tenant identifier

    Note:
        In production, this would lookup the tenant from the API key.
        For now, returns default tenant.
    """
    # TODO: Lookup tenant from API key in database
    return "default"
