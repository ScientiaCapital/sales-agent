"""
VLM Preprocessing Module

Image preprocessing utilities to improve VLM extraction accuracy
on challenging images (faded, small text, low contrast).

Based on audit findings:
- Faded/small images scored 2-4/10
- Preprocessing can improve to 6-8/10

Usage:
    from vlm_core.preprocessing import preprocess_image, PreprocessConfig

    # Auto-detect and apply appropriate preprocessing
    processed_bytes = preprocess_image(image_bytes)

    # Custom configuration
    config = PreprocessConfig(upscale_small=True, enhance_contrast=True)
    processed_bytes = preprocess_image(image_bytes, config)

@module vlm_core.preprocessing
@version 1.0.0
@license Proprietary - Scientia Capital
"""

from .image_processor import (
    preprocess_image,
    detect_image_issues,
    upscale_image,
    enhance_contrast,
    sharpen_text,
    denoise_image,
)
from .config import PreprocessConfig, ImageIssues

__all__ = [
    "preprocess_image",
    "detect_image_issues",
    "upscale_image",
    "enhance_contrast",
    "sharpen_text",
    "denoise_image",
    "PreprocessConfig",
    "ImageIssues",
]
