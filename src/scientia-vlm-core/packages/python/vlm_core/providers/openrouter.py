"""OpenRouter VLM provider implementation.

Supports Qwen VL, DeepSeek, and other vision models via OpenRouter API.
Uses OpenAI SDK for compatibility.
"""
import io
import base64
import json
from typing import Any
from PIL import Image

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError(
        "OpenAI SDK required for OpenRouter provider. "
        "Install with: pip install 'scientia-vlm-core[openrouter]'"
    )

from ..types import VLMConfig, VLMResponse, ModelInfo
from ..exceptions import ProviderError, RateLimitError, ConfigurationError
from .base import VLMProvider


class OpenRouterProvider(VLMProvider):
    """OpenRouter VLM provider using OpenAI SDK compatibility layer.

    Supports:
    - Qwen 2.5 VL (72B, 30B, 8B)
    - DeepSeek Chat (text normalization)
    - Qwen3 Embedding (RAG)
    """

    # Model catalog (proprietary knowledge from FieldVault.ai)
    MODELS = [
        ModelInfo(
            id="qwen/qwen2.5-vl-72b-instruct",
            name="Qwen 2.5 VL 72B",
            context_length=32768,
            cost_per_image=0.0015,
            supports_pdf=True,
            max_image_size=4096,
        ),
        ModelInfo(
            id="qwen/qwen2.5-vl-30b-instruct",
            name="Qwen 2.5 VL 30B",
            context_length=32768,
            cost_per_image=0.0008,
            supports_pdf=True,
            max_image_size=4096,
        ),
        ModelInfo(
            id="qwen/qwen2.5-vl-8b-instruct",
            name="Qwen 2.5 VL 8B",
            context_length=32768,
            cost_per_image=0.0003,
            supports_pdf=True,
            max_image_size=4096,
        ),
    ]

    def __init__(
        self,
        api_key: str,
        site_url: str = "https://app.fieldvault.ai",
        app_name: str = "FieldVault",
    ):
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key.
            site_url: Site URL for OpenRouter tracking.
            app_name: Application name for OpenRouter tracking.
        """
        if not api_key:
            raise ConfigurationError("OpenRouter API key is required")

        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": site_url,
                "X-Title": app_name,
            }
        )

    def get_models(self) -> list[ModelInfo]:
        """Get available VLM models."""
        return self.MODELS.copy()

    async def analyze(
        self,
        image_base64: str,
        config: VLMConfig
    ) -> VLMResponse:
        """Analyze image with VLM.

        Args:
            image_base64: Base64 encoded image (with or without data URL prefix).
            config: VLM configuration.

        Returns:
            VLMResponse with extraction and metadata.

        Raises:
            ProviderError: If API call fails.
            RateLimitError: If rate limited.
        """
        import time

        # Ensure data URL format
        if not image_base64.startswith('data:'):
            # Detect image format from base64 header
            if image_base64.startswith('/9j/'):
                image_base64 = f'data:image/jpeg;base64,{image_base64}'
            elif image_base64.startswith('iVBORw'):
                image_base64 = f'data:image/png;base64,{image_base64}'
            else:
                # Default to jpeg
                image_base64 = f'data:image/jpeg;base64,{image_base64}'

        # Prepare messages
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_base64}
                    },
                    {
                        "type": "text",
                        "text": config.prompt
                    }
                ]
            }
        ]

        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=config.model,
                messages=messages,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse extraction from response
            content = response.choices[0].message.content or ""

            # Try to extract JSON from response
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

                extraction = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                # If not JSON, return as text field
                extraction = {"text": content}

            return VLMResponse(
                extraction=extraction,
                model=config.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                latency_ms=latency_ms,
                confidence=0.85,  # Default confidence, should be calculated properly
            )

        except Exception as e:
            error_msg = str(e).lower()

            # Check for rate limit errors
            if "429" in error_msg or "rate limit" in error_msg:
                raise RateLimitError(f"OpenRouter rate limit exceeded: {e}")

            # Check for authentication errors
            if "401" in error_msg or "unauthorized" in error_msg:
                raise ConfigurationError(f"OpenRouter authentication failed: {e}")

            # Generic provider error
            raise ProviderError(f"OpenRouter API error: {e}")

    async def generate_embedding(self, text: str) -> list[float] | None:
        """Generate text embedding using Qwen3 Embedding 8B.

        Args:
            text: Text to embed.

        Returns:
            1536-dimension embedding vector, or None on error.
        """
        try:
            response = await self.client.embeddings.create(
                model="qwen/qwen3-embedding-8b",
                input=text,
                dimensions=1536,  # Matryoshka truncation for pgvector HNSW
            )

            embedding = response.data[0].embedding

            if not embedding or len(embedding) != 1536:
                return None

            return embedding

        except Exception as e:
            print(f"[OpenRouter] Embedding generation error: {e}")
            return None

    async def crop_to_roi(
        self,
        image_base64: str,
        bounding_box: dict[str, int],
        output_quality: float = 0.90,
        max_dimension: int = 2048
    ) -> dict[str, Any]:
        """Crop image to bounding box.

        Args:
            image_base64: Base64 encoded source image.
            bounding_box: Dict with x, y, width, height.
            output_quality: JPEG quality (0.0-1.0).
            max_dimension: Max width/height after cropping.

        Returns:
            Dict with cropped_image_base64, width, height, etc.
        """
        try:
            # Remove data URL prefix if present
            if ',' in image_base64:
                image_base64 = image_base64.split(',', 1)[1]

            # Decode base64
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))

            # Get original dimensions
            original_width, original_height = image.size

            # Extract bounding box
            x = bounding_box['x']
            y = bounding_box['y']
            width = bounding_box['width']
            height = bounding_box['height']

            # Crop image
            cropped = image.crop((x, y, x + width, y + height))

            # Resize if needed
            crop_width, crop_height = cropped.size
            if crop_width > max_dimension or crop_height > max_dimension:
                ratio = min(max_dimension / crop_width, max_dimension / crop_height)
                new_width = int(crop_width * ratio)
                new_height = int(crop_height * ratio)
                cropped = cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)
                crop_width, crop_height = new_width, new_height

            # Convert to base64
            buffer = io.BytesIO()
            cropped.save(buffer, format="JPEG", quality=int(output_quality * 100))
            cropped_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return {
                "cropped_image_base64": f"data:image/jpeg;base64,{cropped_base64}",
                "width": crop_width,
                "height": crop_height,
                "original_width": original_width,
                "original_height": original_height,
            }

        except Exception as e:
            raise ProviderError(f"Image cropping failed: {e}")
