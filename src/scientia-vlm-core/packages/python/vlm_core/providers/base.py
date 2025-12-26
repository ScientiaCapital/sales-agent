"""Abstract base classes for VLM providers.

Defines the contracts that all VLM providers must implement.
Following the plugin architecture pattern for extensibility.
"""
from abc import ABC, abstractmethod
from typing import Any

from ..types import VLMConfig, VLMResponse, ModelInfo


class VLMProvider(ABC):
    """Abstract base class for Vision-Language Model providers.

    All VLM providers (OpenRouter, Replicate, etc.) must implement this interface.
    This enables swappable providers and testing with mocks.
    """

    @abstractmethod
    async def analyze(
        self,
        image_base64: str,
        config: VLMConfig
    ) -> VLMResponse:
        """Analyze image with VLM and return structured extraction.

        Args:
            image_base64: Base64 encoded image (with or without data URL prefix).
            config: VLM configuration including model, prompt, and parameters.

        Returns:
            VLMResponse with extraction result and metadata.

        Raises:
            ProviderError: If analysis fails.
            RateLimitError: If rate limits are exceeded.
            ConfigurationError: If configuration is invalid.
        """
        pass

    @abstractmethod
    def get_models(self) -> list[ModelInfo]:
        """List available VLM models from this provider.

        Returns:
            List of ModelInfo with id, name, capabilities, and costs.
            Format: [ModelInfo(id="...", name="...", ...)]
        """
        pass

    def get_default_model(self, supports_pdf: bool = False) -> str | None:
        """Get default model ID for this provider.

        Provides a sensible default when no specific model is requested.
        Can be overridden by providers for custom logic.

        Args:
            supports_pdf: If True, only return models that support PDF analysis.

        Returns:
            Model ID string, or None if no models available.
        """
        models = self.get_models()

        if supports_pdf:
            models = [m for m in models if m.supports_pdf]

        return models[0].id if models else None

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float] | None:
        """Generate text embedding for RAG similarity search.

        Args:
            text: Text to embed (e.g., extraction result JSON).

        Returns:
            Embedding vector (typically 1536 dimensions), or None on error.

        Raises:
            ProviderError: If embedding generation fails.
        """
        pass

    @abstractmethod
    async def crop_to_roi(
        self,
        image_base64: str,
        bounding_box: dict[str, int],
        output_quality: float = 0.90,
        max_dimension: int = 2048
    ) -> dict[str, Any]:
        """Crop image to region of interest for re-analysis.

        Args:
            image_base64: Base64 encoded source image.
            bounding_box: Dict with x, y, width, height keys.
            output_quality: JPEG quality (0.0-1.0).
            max_dimension: Maximum width/height after cropping.

        Returns:
            Dict with cropped_image_base64, width, height, original_width, original_height.

        Raises:
            ProviderError: If cropping fails.
        """
        pass
