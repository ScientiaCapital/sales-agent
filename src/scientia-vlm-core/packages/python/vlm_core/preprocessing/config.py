"""
Preprocessing Configuration

Configuration dataclasses for image preprocessing.

@module vlm_core.preprocessing
@version 1.0.0
@license Proprietary - Scientia Capital
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ImageIssues:
    """Detected issues in an image that may affect VLM accuracy."""

    is_small: bool = False  # Image < 50KB or < 800px dimension
    is_faded: bool = False  # Low contrast / washed out
    has_small_text: bool = False  # Text likely too small for VLM
    is_noisy: bool = False  # High noise level
    is_dark: bool = False  # Underexposed
    is_bright: bool = False  # Overexposed

    @property
    def needs_preprocessing(self) -> bool:
        """Check if any issues were detected."""
        return any([
            self.is_small,
            self.is_faded,
            self.has_small_text,
            self.is_noisy,
            self.is_dark,
            self.is_bright,
        ])

    @property
    def issue_count(self) -> int:
        """Count of detected issues."""
        return sum([
            self.is_small,
            self.is_faded,
            self.has_small_text,
            self.is_noisy,
            self.is_dark,
            self.is_bright,
        ])


@dataclass
class PreprocessConfig:
    """Configuration for image preprocessing."""

    # Auto-detection settings
    auto_detect: bool = True  # Automatically detect and fix issues

    # Individual preprocessing toggles
    upscale_small: bool = True  # Upscale images < 800px
    enhance_contrast: bool = True  # Fix faded/low contrast images
    sharpen_text: bool = True  # Sharpen for small text
    denoise: bool = True  # Remove noise
    fix_exposure: bool = True  # Fix under/overexposed images

    # Thresholds for auto-detection
    min_dimension_px: int = 800  # Minimum dimension before upscaling
    min_file_size_kb: int = 50  # Minimum file size before upscaling
    contrast_threshold: float = 0.3  # Std dev threshold for low contrast
    brightness_low: int = 50  # Below this is "dark"
    brightness_high: int = 200  # Above this is "bright"

    # Processing parameters
    upscale_factor: float = 2.0  # How much to upscale small images
    contrast_factor: float = 1.5  # Contrast enhancement multiplier
    sharpness_factor: float = 1.3  # Sharpening multiplier
    denoise_strength: int = 3  # Median filter kernel size (must be odd)

    # Output settings
    output_format: Literal["PNG", "JPEG", "WEBP"] = "PNG"
    jpeg_quality: int = 95  # Quality for JPEG output
    max_output_size_mb: float = 10.0  # Max output size in MB

    # Logging
    verbose: bool = False  # Print processing steps


@dataclass
class PreprocessResult:
    """Result of image preprocessing."""

    image_bytes: bytes
    original_size: tuple[int, int]  # (width, height)
    processed_size: tuple[int, int]
    issues_detected: ImageIssues
    transformations_applied: list[str] = field(default_factory=list)
    original_bytes: int = 0
    processed_bytes: int = 0

    @property
    def was_modified(self) -> bool:
        """Check if image was modified."""
        return len(self.transformations_applied) > 0

    @property
    def compression_ratio(self) -> float:
        """Ratio of processed to original size."""
        if self.original_bytes == 0:
            return 1.0
        return self.processed_bytes / self.original_bytes
