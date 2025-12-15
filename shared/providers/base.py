"""
Base Provider Interface for VLM Audit Infrastructure

Enterprise-Grade Type Safety for Tier-1 VC Due Diligence
All providers implement this interface for consistent:
- Image analysis with strict type contracts
- Token/cost tracking with validated metrics
- Audit record generation with full type safety

Type Safety Features:
- TypedDict for structured return types
- Literal types for constrained enums
- Protocol classes for interface contracts
- Runtime validation via Pydantic
- Full mypy strict mode compliance
"""

from __future__ import annotations

import base64
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Final,
    Literal,
    Optional,
    TypedDict,
    TypeVar,
    final,
)

from ..audit.schema import (
    AccuracyMetrics,
    AuditMetadata,
    AuditRecord,
    CostMetrics,
    HashInfo,
    LatencyMetrics,
    ModelInfo,
    ModelTier,
    OperationalMetrics,
    Provider,
    TokenMetrics,
)

# =============================================================================
# TYPE DEFINITIONS - Enterprise Grade
# =============================================================================

# Supported image MIME types (strict)
ImageMimeType = Literal[
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
]

# Magic byte signatures for format detection
JPEG_MAGIC: Final[bytes] = b'\xff\xd8\xff'
PNG_MAGIC: Final[bytes] = b'\x89PNG\r\n\x1a\n'
WEBP_MAGIC_RIFF: Final[bytes] = b'RIFF'
WEBP_MAGIC_WEBP: Final[bytes] = b'WEBP'
GIF_MAGIC_87: Final[bytes] = b'GIF87a'
GIF_MAGIC_89: Final[bytes] = b'GIF89a'

# Minimum bytes needed for format detection
MIN_MAGIC_BYTES: Final[int] = 12


class ImageLoadResult(TypedDict):
    """Strict type for image loading results."""
    base64_data: str
    mime_type: ImageMimeType
    content_hash: str
    byte_size: int


class AnalyzeImageResult(TypedDict):
    """Strict type for analyze_image return value."""
    response: dict[str, Any]
    extracted: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    ttft_ms: Optional[int]
    request_id: Optional[str]
    confidence: Optional[float]


class ModelInfoDict(TypedDict, total=False):
    """Model capability and pricing info."""
    tier: ModelTier
    cost_per_1m_input: float
    cost_per_1m_output: float
    vision: bool
    context_length: int
    avg_score: float
    specialty: str
    is_chinese_vlm: bool


class ModelListItem(TypedDict):
    """Single model in available models list."""
    model: str
    provider: str


# Type variable for provider subclasses
ProviderT = TypeVar('ProviderT', bound='BaseVLMProvider')


# =============================================================================
# BASE PROVIDER - Abstract Interface
# =============================================================================

class BaseVLMProvider(ABC):
    """
    Abstract base class for VLM providers.

    All providers (OpenRouter, Anthropic, Gemini) implement this interface
    to ensure consistent audit logging and comparison.

    Type Safety:
    - All methods have strict type annotations
    - Return types use TypedDict for structure
    - Runtime validation via Pydantic models
    - Literal types for constrained values

    Enterprise Requirements:
    - Thread-safe client initialization
    - Consistent error handling
    - Full audit trail generation
    - Cost calculation accuracy
    """

    # Class-level type hints (overridden by subclasses)
    provider: ClassVar[Provider]
    is_chinese_vlm: ClassVar[bool] = False

    __slots__ = ('api_key', '_client')

    def __init__(self, api_key: str) -> None:
        """
        Initialize provider with API key.

        Args:
            api_key: Provider API key (validated non-empty)

        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        self.api_key: str = api_key
        self._client: Any = None

    @abstractmethod
    async def _init_client(self) -> None:
        """Initialize the provider-specific client. Must be idempotent."""
        ...

    @abstractmethod
    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AnalyzeImageResult:
        """
        Analyze an image and return structured response.

        Args:
            image_path: Path to image file (must exist)
            prompt: Analysis prompt (non-empty)
            model: Model name string (provider-specific)
            max_tokens: Maximum output tokens (1-32768)
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            AnalyzeImageResult with all required fields

        Raises:
            FileNotFoundError: If image_path doesn't exist
            ValueError: If prompt is empty or params out of range
            RuntimeError: If API call fails
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[dict[str, Any]]:
        """Return list of available models with metadata."""
        ...

    @abstractmethod
    def get_model_info(self, model: str) -> ModelInfoDict:
        """
        Get pricing and capability info for a model.

        Args:
            model: Model name string

        Returns:
            ModelInfoDict with pricing and capabilities
        """
        ...

    @final
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> CostMetrics:
        """
        Calculate cost for a request.

        Uses per-1M token pricing for accuracy.

        Args:
            model: Model name for pricing lookup
            input_tokens: Number of input tokens (non-negative)
            output_tokens: Number of output tokens (non-negative)

        Returns:
            CostMetrics with calculated costs

        Raises:
            ValueError: If token counts are negative
        """
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts cannot be negative")

        model_info = self.get_model_info(model)

        # Pricing is per 1M tokens - use float division for accuracy
        input_cost: float = (input_tokens / 1_000_000) * model_info.get("cost_per_1m_input", 0.0)
        output_cost: float = (output_tokens / 1_000_000) * model_info.get("cost_per_1m_output", 0.0)
        total_cost: float = input_cost + output_cost

        return CostMetrics(
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            cost_alert_triggered=total_cost > 0.03,
        )

    @staticmethod
    @final
    def _hash_content(content: bytes) -> str:
        """
        Generate SHA-256 hash of content.

        Args:
            content: Bytes to hash

        Returns:
            Lowercase hex digest string
        """
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    @final
    def _detect_image_format(image_bytes: bytes) -> ImageMimeType:
        """
        Detect actual image format from magic bytes (file signature).

        This fixes the WebP-labeled-as-JPEG issue where file extension
        doesn't match actual content. Anthropic is strict about MIME types
        matching actual data - this ensures we always send the correct type.

        Magic byte signatures:
        - JPEG: FF D8 FF
        - PNG: 89 50 4E 47 0D 0A 1A 0A
        - WebP: RIFF....WEBP
        - GIF: GIF87a or GIF89a

        Args:
            image_bytes: Raw image file bytes

        Returns:
            Correct MIME type based on actual content
        """
        if len(image_bytes) < MIN_MAGIC_BYTES:
            return "image/jpeg"  # Fallback for tiny/corrupt files

        # Check magic bytes in order of likelihood
        if image_bytes[:3] == JPEG_MAGIC:
            return "image/jpeg"
        elif image_bytes[:8] == PNG_MAGIC:
            return "image/png"
        elif image_bytes[:4] == WEBP_MAGIC_RIFF and image_bytes[8:12] == WEBP_MAGIC_WEBP:
            return "image/webp"
        elif image_bytes[:6] in (GIF_MAGIC_87, GIF_MAGIC_89):
            return "image/gif"
        else:
            # Fallback - assume JPEG for unknown formats
            return "image/jpeg"

    @final
    def _load_image_base64(self, image_path: Path) -> ImageLoadResult:
        """
        Load image and return base64 + metadata.

        Uses magic byte detection to determine actual format,
        not just file extension. This prevents MIME type mismatches
        that cause Anthropic to return 0 tokens.

        Args:
            image_path: Path to image file

        Returns:
            ImageLoadResult with base64 data, MIME type, hash, and size

        Raises:
            FileNotFoundError: If image doesn't exist
            PermissionError: If file can't be read
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            image_bytes: bytes = f.read()

        # Detect actual format from magic bytes, not extension
        mime_type: ImageMimeType = self._detect_image_format(image_bytes)
        content_hash: str = self._hash_content(image_bytes)
        base64_data: str = base64.b64encode(image_bytes).decode("utf-8")

        return ImageLoadResult(
            base64_data=base64_data,
            mime_type=mime_type,
            content_hash=content_hash,
            byte_size=len(image_bytes),
        )

    @final
    async def audit_analyze(
        self,
        image_path: Path,
        prompt: str,
        model: str,
        trade: Optional[str] = None,
        session_id: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AuditRecord:
        """
        Analyze image with full audit logging.

        This is the primary method for audit runs - wraps analyze_image
        with complete audit record generation.

        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            model: Model name string
            trade: Trade type (hvac, electrical, solar, plumbing, roofing)
            session_id: Session ID for grouping related calls
            max_tokens: Maximum output tokens
            temperature: Sampling temperature

        Returns:
            Complete AuditRecord with all metrics

        Type Safety:
            - Returns validated Pydantic model
            - All fields strictly typed
            - Automatic cost calculation
        """
        start_time: datetime = datetime.utcnow()
        model_info: ModelInfoDict = self.get_model_info(model)

        # Initialize metadata with strict typing
        metadata = AuditMetadata(
            session_id=session_id,
            trade=trade,
        )

        # Build model info record
        model_record = ModelInfo(
            provider=self.provider,
            model_name=model,
            model_tier=ModelTier(model_info.get("tier", "standard")),
            is_vision_model=model_info.get("vision", True),
            is_chinese_vlm=self.is_chinese_vlm,
            context_length=model_info.get("context_length", 0),
        )

        # Load image for hashing
        image_result: ImageLoadResult = self._load_image_base64(image_path)
        image_hash: str = image_result["content_hash"]
        prompt_hash: str = self._hash_content(prompt.encode("utf-8"))

        try:
            # Call the provider
            result: AnalyzeImageResult = await self.analyze_image(
                image_path=image_path,
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Build metrics from result
            input_tokens: int = result.get("input_tokens", 0)
            output_tokens: int = result.get("output_tokens", 0)

            tokens = TokenMetrics(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )

            cost: CostMetrics = self.calculate_cost(
                model=model,
                input_tokens=tokens.input_tokens,
                output_tokens=tokens.output_tokens,
            )

            latency = LatencyMetrics(
                total_latency_ms=result.get("latency_ms", 0),
                ttft_ms=result.get("ttft_ms"),
            )

            # Count extracted fields
            extracted: dict[str, Any] = result.get("extracted", {})
            fields_extracted: int = len([v for v in extracted.values() if v is not None])

            accuracy = AccuracyMetrics(
                success=True,
                fields_extracted=fields_extracted,
                confidence_score=result.get("confidence"),
            )

            operational = OperationalMetrics(
                request_id=result.get("request_id"),
            )

            hashes = HashInfo(
                input_hash=image_hash,
                prompt_hash=prompt_hash,
            )

            record = AuditRecord(
                metadata=metadata,
                model=model_record,
                tokens=tokens,
                cost=cost,
                latency=latency,
                accuracy=accuracy,
                operational=operational,
                hashes=hashes,
                raw_response=result.get("response"),
                extracted_data=extracted,
            )

        except Exception as e:
            # Record failure with type-safe error handling
            latency_ms: int = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            accuracy = AccuracyMetrics(
                success=False,
                error_type=type(e).__name__,
                error_message=str(e)[:500],  # Truncate long errors
                accuracy_label="failed",
            )

            record = AuditRecord(
                metadata=metadata,
                model=model_record,
                latency=LatencyMetrics(total_latency_ms=latency_ms),
                accuracy=accuracy,
                hashes=HashInfo(input_hash=image_hash, prompt_hash=prompt_hash),
            )

        # Calculate savings vs Western baseline
        record.calculate_cost_savings()

        return record


# =============================================================================
# PROVIDER REGISTRY - Type-Safe Singleton
# =============================================================================

class ProviderRegistry:
    """
    Registry of available providers.

    Type Safety:
    - Generic registration with provider type validation
    - Strict lookup with KeyError on missing
    - Immutable after registration
    """

    _providers: ClassVar[dict[Provider, type[BaseVLMProvider]]] = {}

    @classmethod
    def register(cls, provider_type: Provider) -> Any:
        """
        Decorator to register a provider class.

        Args:
            provider_type: Provider enum value

        Returns:
            Decorator function

        Example:
            @ProviderRegistry.register(Provider.OPENROUTER)
            class OpenRouterProvider(BaseVLMProvider):
                ...
        """
        def decorator(provider_class: type[ProviderT]) -> type[ProviderT]:
            if provider_type in cls._providers:
                raise ValueError(f"Provider {provider_type} already registered")
            cls._providers[provider_type] = provider_class
            return provider_class
        return decorator

    @classmethod
    def get(cls, provider_type: Provider) -> type[BaseVLMProvider]:
        """
        Get provider class by type.

        Args:
            provider_type: Provider enum value

        Returns:
            Provider class

        Raises:
            KeyError: If provider not registered
        """
        if provider_type not in cls._providers:
            raise KeyError(f"Unknown provider: {provider_type}. Available: {list(cls._providers.keys())}")
        return cls._providers[provider_type]

    @classmethod
    def list_providers(cls) -> list[Provider]:
        """List all registered providers."""
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, provider_type: Provider) -> bool:
        """Check if a provider is registered."""
        return provider_type in cls._providers
