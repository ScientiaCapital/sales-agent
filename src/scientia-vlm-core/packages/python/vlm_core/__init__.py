"""VLM Core - Enterprise-grade Vision-Language Model services for Python.

Exports all public APIs for easy importing.
"""
from .exceptions import (
    VLMError,
    ProviderError,
    RateLimitError,
    CreditError,
    ConfigurationError,
    CircuitBreakerOpenError,
    RetryExhaustedError,
    NonRetryableError,
)

from .types import (
    VLMConfig,
    VLMResponse,
    ModelInfo,
    CacheEntry,
    ROIRegion,
    ROIAnalysisResult,
    BoundingBox,
    ConfidenceBreakdown,
    SmartVLMResult,
    Trade,
)

from .providers import VLMProvider

from .middleware import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerMetrics,
    withRetry,
    retry,
    makeRetryable,
    RetryConfig,
    RetryResult,
)

from .preprocessing import (
    preprocess_image,
    detect_image_issues,
    upscale_image,
    enhance_contrast,
    sharpen_text,
    denoise_image,
    PreprocessConfig,
    ImageIssues,
)

__version__ = "0.1.0"

__all__ = [
    # Exceptions
    "VLMError",
    "ProviderError",
    "RateLimitError",
    "CreditError",
    "ConfigurationError",
    "CircuitBreakerOpenError",
    "RetryExhaustedError",
    "NonRetryableError",
    # Types
    "VLMConfig",
    "VLMResponse",
    "ModelInfo",
    "CacheEntry",
    "ROIRegion",
    "ROIAnalysisResult",
    "BoundingBox",
    "ConfidenceBreakdown",
    "SmartVLMResult",
    "Trade",
    # Providers
    "VLMProvider",
    # Middleware
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitBreakerMetrics",
    "withRetry",
    "retry",
    "makeRetryable",
    "RetryConfig",
    "RetryResult",
    # Preprocessing
    "preprocess_image",
    "detect_image_issues",
    "upscale_image",
    "enhance_contrast",
    "sharpen_text",
    "denoise_image",
    "PreprocessConfig",
    "ImageIssues",
]
