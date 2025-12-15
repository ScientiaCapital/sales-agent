"""
OpenRouter VLM Provider for Audit Infrastructure

Chinese VLM stack - Qwen models via OpenRouter API.
This is our COST LEADER for the investor story.
"""

import json
import time
from pathlib import Path
from typing import Any

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError(
        "OpenAI SDK required for OpenRouter. Install with: pip install openai"
    )

from ..audit.schema import OPENROUTER_MODELS, ModelTier, Provider
from .base import BaseVLMProvider, ProviderRegistry


@ProviderRegistry.register(Provider.OPENROUTER)
class OpenRouterProvider(BaseVLMProvider):
    """
    OpenRouter provider for Chinese VLMs (Qwen).

    This is our COST LEADER - the margin story depends on these models
    delivering accuracy parity with Western models at 1/10th the cost.
    """

    provider = Provider.OPENROUTER
    is_chinese_vlm = True  # Key for margin analysis

    def __init__(
        self,
        api_key: str,
        site_url: str = "https://scientia.capital",
        app_name: str = "Scientia-VLM-Audit",
    ):
        super().__init__(api_key)
        self.site_url = site_url
        self.app_name = app_name
        self._client = None

    async def _init_client(self) -> None:
        """Initialize OpenRouter client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.app_name,
                }
            )

    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Analyze image using Qwen VL via OpenRouter.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            model: Model name (e.g., qwen/qwen2.5-vl-72b-instruct)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature

        Returns:
            Dict with response, tokens, latency, etc.
        """
        await self._init_client()

        # Load and encode image using TypedDict accessor pattern
        image_result = self._load_image_base64(image_path)
        base64_data = image_result["base64_data"]
        mime_type = image_result["mime_type"]
        data_url = f"data:{mime_type};base64,{base64_data}"

        # Prepare messages
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        start_time = time.time()

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = response.choices[0].message.content or ""

            # Parse JSON if present
            extracted = self._parse_json_response(content)

            # Get token counts
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            return {
                "response": {"content": content, "model": model},
                "extracted": extracted,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "ttft_ms": None,  # OpenRouter doesn't provide TTFT
                "request_id": response.id if hasattr(response, 'id') else None,
                "confidence": self._estimate_confidence(extracted),
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            raise RuntimeError(f"OpenRouter API error after {latency_ms}ms: {e}")

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from model response."""
        try:
            # Handle markdown code blocks
            if "```json" in content:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.index("```") + 3
                json_end = content.index("```", json_start)
                content = content[json_start:json_end].strip()

            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {"raw_text": content}

    def _estimate_confidence(self, extracted: dict) -> float:
        """Estimate confidence from extraction completeness."""
        if not extracted or "raw_text" in extracted:
            return 0.5

        # Count non-null values
        non_null = sum(1 for v in extracted.values() if v is not None and v != "")
        total = len(extracted) if extracted else 1

        return min(0.95, 0.5 + (non_null / total) * 0.45)

    def get_available_models(self) -> list[dict[str, Any]]:
        """Return list of available Qwen VL models."""
        return [
            {
                "model": model_name,
                "provider": "openrouter",
                **model_info,
            }
            for model_name, model_info in OPENROUTER_MODELS.items()
        ]

    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get pricing and capability info for a model."""
        if model in OPENROUTER_MODELS:
            return OPENROUTER_MODELS[model]

        # Default fallback
        return {
            "tier": ModelTier.COST_LEADER,
            "cost_per_1m_input": 0.40,
            "cost_per_1m_output": 0.40,
            "vision": True,
            "context_length": 32768,
        }


# Convenience function for quick testing
async def test_openrouter(api_key: str, image_path: Path, prompt: str) -> dict:
    """Quick test function for OpenRouter provider."""
    provider = OpenRouterProvider(api_key=api_key)
    result = await provider.analyze_image(
        image_path=image_path,
        prompt=prompt,
        model="qwen/qwen2.5-vl-72b-instruct",
    )
    return result
