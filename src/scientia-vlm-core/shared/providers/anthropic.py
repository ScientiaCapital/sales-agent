"""
Anthropic VLM Provider for Audit Infrastructure

Claude 4.5 models - our PREMIUM WESTERN BASELINE.
Used to prove accuracy parity with Chinese VLMs.
"""

import json
import time
from pathlib import Path
from typing import Any

try:
    from anthropic import AsyncAnthropic
except ImportError:
    raise ImportError(
        "Anthropic SDK required. Install with: pip install anthropic"
    )

from ..audit.schema import ANTHROPIC_MODELS, ModelTier, Provider
from .base import BaseVLMProvider, ProviderRegistry


@ProviderRegistry.register(Provider.ANTHROPIC)
class AnthropicProvider(BaseVLMProvider):
    """
    Anthropic provider for Claude 4.5 models.

    This is our PREMIUM WESTERN BASELINE - the accuracy standard
    we need to match with Chinese VLMs for the investor story.

    Models:
    - claude-sonnet-4-5-20250514 (Premium)
    - claude-opus-4-5-20250514 (Ultra)
    - claude-haiku-4-5-20250514 (Fast)
    """

    provider = Provider.ANTHROPIC
    is_chinese_vlm = False  # Western baseline

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = None

    async def _init_client(self) -> None:
        """Initialize Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)

    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Analyze image using Claude 4.5 vision.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            model: Model name (e.g., claude-sonnet-4-5-20250514)
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

        # Prepare message with vision
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_data,
                        }
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
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                temperature=temperature,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

            # Parse JSON if present
            extracted = self._parse_json_response(content)

            # Get token counts from usage
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0

            return {
                "response": {"content": content, "model": model},
                "extracted": extracted,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "ttft_ms": None,
                "request_id": response.id if hasattr(response, 'id') else None,
                "confidence": self._estimate_confidence(extracted),
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            raise RuntimeError(f"Anthropic API error after {latency_ms}ms: {e}")

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

        non_null = sum(1 for v in extracted.values() if v is not None and v != "")
        total = len(extracted) if extracted else 1

        return min(0.95, 0.5 + (non_null / total) * 0.45)

    def get_available_models(self) -> list[dict[str, Any]]:
        """Return list of available Claude 4.5 models."""
        return [
            {
                "model": model_name,
                "provider": "anthropic",
                **model_info,
            }
            for model_name, model_info in ANTHROPIC_MODELS.items()
        ]

    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get pricing and capability info for a model."""
        if model in ANTHROPIC_MODELS:
            return ANTHROPIC_MODELS[model]

        # Default fallback (Sonnet pricing)
        return {
            "tier": ModelTier.PREMIUM,
            "cost_per_1m_input": 3.00,
            "cost_per_1m_output": 15.00,
            "vision": True,
            "context_length": 200000,
        }


# Convenience function for quick testing
async def test_anthropic(api_key: str, image_path: Path, prompt: str) -> dict:
    """Quick test function for Anthropic provider."""
    provider = AnthropicProvider(api_key=api_key)
    result = await provider.analyze_image(
        image_path=image_path,
        prompt=prompt,
        model="claude-sonnet-4-5-20250514",
    )
    return result
