"""
Gemini VLM Provider for Audit Infrastructure

Google Gemini 2.0/3.0 models - our ALTERNATIVE WESTERN BASELINE.
Used for cost comparison and diversity.
"""

import json
import time
from pathlib import Path
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError(
        "Google GenAI SDK required. Install with: pip install google-genai"
    )

from ..audit.schema import GEMINI_MODELS, ModelTier, Provider
from .base import BaseVLMProvider, ProviderRegistry


@ProviderRegistry.register(Provider.GEMINI)
class GeminiProvider(BaseVLMProvider):
    """
    Gemini provider for Google's vision models.

    This is our ALTERNATIVE WESTERN BASELINE - provides diversity
    in the comparison and often better pricing than Anthropic.

    Models:
    - gemini-2.0-flash (Standard)
    - gemini-3.0-flash (Latest)
    """

    provider = Provider.GEMINI
    is_chinese_vlm = False  # Western baseline

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = None

    async def _init_client(self) -> None:
        """Initialize Gemini client."""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)

    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Analyze image using Gemini vision.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            model: Model name (e.g., gemini-2.0-flash)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature

        Returns:
            Dict with response, tokens, latency, etc.
        """
        await self._init_client()

        # Load image bytes
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, "image/jpeg")

        # Create image part
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        start_time = time.time()

        try:
            # Use synchronous call (google-genai is sync by default)
            # Wrap in async context
            response = self._client.models.generate_content(
                model=model,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract content
            content = response.text if hasattr(response, 'text') else ""

            # Parse JSON if present
            extracted = self._parse_json_response(content)

            # Estimate tokens (Gemini doesn't always return exact counts)
            input_tokens = getattr(response, 'usage_metadata', {})
            if hasattr(input_tokens, 'prompt_token_count'):
                input_tokens = input_tokens.prompt_token_count
            else:
                input_tokens = len(prompt.split()) * 2  # Rough estimate

            output_tokens = getattr(response, 'usage_metadata', {})
            if hasattr(output_tokens, 'candidates_token_count'):
                output_tokens = output_tokens.candidates_token_count
            else:
                output_tokens = len(content.split()) * 2  # Rough estimate

            return {
                "response": {"content": content, "model": model},
                "extracted": extracted,
                "input_tokens": input_tokens if isinstance(input_tokens, int) else 500,
                "output_tokens": output_tokens if isinstance(output_tokens, int) else 500,
                "latency_ms": latency_ms,
                "ttft_ms": None,
                "request_id": None,  # Gemini doesn't provide request IDs
                "confidence": self._estimate_confidence(extracted),
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            raise RuntimeError(f"Gemini API error after {latency_ms}ms: {e}")

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
        """Return list of available Gemini models."""
        return [
            {
                "model": model_name,
                "provider": "gemini",
                **model_info,
            }
            for model_name, model_info in GEMINI_MODELS.items()
        ]

    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get pricing and capability info for a model."""
        if model in GEMINI_MODELS:
            return GEMINI_MODELS[model]

        # Default fallback (Flash pricing)
        return {
            "tier": ModelTier.STANDARD,
            "cost_per_1m_input": 0.10,
            "cost_per_1m_output": 0.40,
            "vision": True,
            "context_length": 1000000,
        }


# Convenience function for quick testing
async def test_gemini(api_key: str, image_path: Path, prompt: str) -> dict:
    """Quick test function for Gemini provider."""
    provider = GeminiProvider(api_key=api_key)
    result = await provider.analyze_image(
        image_path=image_path,
        prompt=prompt,
        model="gemini-2.0-flash",
    )
    return result
