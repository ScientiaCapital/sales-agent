"""
Image Processor

Core image preprocessing functions using Pillow.

Why preprocessing matters:
- Faded/small images scored 2-4/10 in VLM audit
- Preprocessing can improve to 6-8/10
- VLMs struggle with low contrast text and small details

@module vlm_core.preprocessing
@version 1.0.0
@license Proprietary - Scientia Capital
"""

import io
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageStat

from .config import PreprocessConfig, ImageIssues, PreprocessResult


def preprocess_image(
    image_bytes: bytes,
    config: Optional[PreprocessConfig] = None,
) -> bytes:
    """
    Preprocess an image to improve VLM extraction accuracy.

    This is the main entry point for image preprocessing.
    It auto-detects issues and applies appropriate fixes.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.)
        config: Optional preprocessing configuration

    Returns:
        Processed image bytes (PNG format by default)

    Example:
        >>> with open("faded_blueprint.jpg", "rb") as f:
        ...     processed = preprocess_image(f.read())
        >>> # processed is now enhanced for VLM analysis
    """
    if config is None:
        config = PreprocessConfig()

    # Open image
    img = Image.open(io.BytesIO(image_bytes))
    original_size = img.size
    original_bytes = len(image_bytes)

    # Convert to RGB if needed (handles RGBA, P mode, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Detect issues
    issues = detect_image_issues(img, config)
    transformations: list[str] = []

    # Apply preprocessing based on detected issues or config
    if config.auto_detect:
        if issues.is_small and config.upscale_small:
            img = upscale_image(img, config.upscale_factor)
            transformations.append(f"upscale_{config.upscale_factor}x")

        if issues.is_faded and config.enhance_contrast:
            img = enhance_contrast(img, config.contrast_factor)
            transformations.append(f"contrast_{config.contrast_factor}x")

        if issues.has_small_text and config.sharpen_text:
            img = sharpen_text(img, config.sharpness_factor)
            transformations.append(f"sharpen_{config.sharpness_factor}x")

        if issues.is_noisy and config.denoise:
            img = denoise_image(img, config.denoise_strength)
            transformations.append(f"denoise_{config.denoise_strength}")

        if issues.is_dark and config.fix_exposure:
            img = fix_underexposure(img)
            transformations.append("brighten")

        if issues.is_bright and config.fix_exposure:
            img = fix_overexposure(img)
            transformations.append("darken")
    else:
        # Apply all enabled transformations regardless of detection
        if config.upscale_small:
            img = upscale_image(img, config.upscale_factor)
            transformations.append(f"upscale_{config.upscale_factor}x")

        if config.enhance_contrast:
            img = enhance_contrast(img, config.contrast_factor)
            transformations.append(f"contrast_{config.contrast_factor}x")

        if config.sharpen_text:
            img = sharpen_text(img, config.sharpness_factor)
            transformations.append(f"sharpen_{config.sharpness_factor}x")

        if config.denoise:
            img = denoise_image(img, config.denoise_strength)
            transformations.append(f"denoise_{config.denoise_strength}")

    # Convert to bytes
    output = io.BytesIO()
    if config.output_format == "JPEG":
        img.save(output, format="JPEG", quality=config.jpeg_quality)
    elif config.output_format == "WEBP":
        img.save(output, format="WEBP", quality=config.jpeg_quality)
    else:
        img.save(output, format="PNG")

    processed_bytes = output.getvalue()

    if config.verbose:
        print(f"[Preprocessing] Original: {original_size}, {original_bytes} bytes")
        print(f"[Preprocessing] Processed: {img.size}, {len(processed_bytes)} bytes")
        print(f"[Preprocessing] Issues: {issues}")
        print(f"[Preprocessing] Applied: {transformations}")

    return processed_bytes


def preprocess_image_detailed(
    image_bytes: bytes,
    config: Optional[PreprocessConfig] = None,
) -> PreprocessResult:
    """
    Preprocess an image and return detailed results.

    Same as preprocess_image but returns a PreprocessResult
    with metadata about what was detected and applied.
    """
    if config is None:
        config = PreprocessConfig()

    img = Image.open(io.BytesIO(image_bytes))
    original_size = img.size
    original_bytes_count = len(image_bytes)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    issues = detect_image_issues(img, config)
    transformations: list[str] = []

    # Apply preprocessing (same logic as preprocess_image)
    if config.auto_detect:
        if issues.is_small and config.upscale_small:
            img = upscale_image(img, config.upscale_factor)
            transformations.append(f"upscale_{config.upscale_factor}x")

        if issues.is_faded and config.enhance_contrast:
            img = enhance_contrast(img, config.contrast_factor)
            transformations.append(f"contrast_{config.contrast_factor}x")

        if issues.has_small_text and config.sharpen_text:
            img = sharpen_text(img, config.sharpness_factor)
            transformations.append(f"sharpen_{config.sharpness_factor}x")

        if issues.is_noisy and config.denoise:
            img = denoise_image(img, config.denoise_strength)
            transformations.append(f"denoise_{config.denoise_strength}")

        if issues.is_dark and config.fix_exposure:
            img = fix_underexposure(img)
            transformations.append("brighten")

        if issues.is_bright and config.fix_exposure:
            img = fix_overexposure(img)
            transformations.append("darken")

    output = io.BytesIO()
    if config.output_format == "JPEG":
        img.save(output, format="JPEG", quality=config.jpeg_quality)
    else:
        img.save(output, format="PNG")

    processed_bytes = output.getvalue()

    return PreprocessResult(
        image_bytes=processed_bytes,
        original_size=original_size,
        processed_size=img.size,
        issues_detected=issues,
        transformations_applied=transformations,
        original_bytes=original_bytes_count,
        processed_bytes=len(processed_bytes),
    )


def detect_image_issues(
    img: Image.Image,
    config: PreprocessConfig,
) -> ImageIssues:
    """
    Detect potential issues in an image that may affect VLM accuracy.

    Args:
        img: PIL Image object
        config: Configuration with thresholds

    Returns:
        ImageIssues dataclass with detected problems
    """
    issues = ImageIssues()

    # Check size
    width, height = img.size
    min_dim = min(width, height)
    issues.is_small = min_dim < config.min_dimension_px

    # Analyze image statistics
    if img.mode == "L":
        stat = ImageStat.Stat(img)
        mean_brightness = stat.mean[0]
        std_brightness = stat.stddev[0]
    else:
        # Convert to grayscale for analysis
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        mean_brightness = stat.mean[0]
        std_brightness = stat.stddev[0]

    # Check contrast (low std dev = low contrast = faded)
    # Normalize std dev to 0-1 range (max std dev for 8-bit is ~128)
    normalized_std = std_brightness / 128.0
    issues.is_faded = normalized_std < config.contrast_threshold

    # Check exposure
    issues.is_dark = mean_brightness < config.brightness_low
    issues.is_bright = mean_brightness > config.brightness_high

    # Estimate if text might be too small
    # Heuristic: if image is small AND has low contrast, text is likely hard to read
    issues.has_small_text = issues.is_small and (issues.is_faded or normalized_std < 0.4)

    # Noise detection (simplified: high local variance in smooth areas)
    # This is a rough heuristic - true noise detection is more complex
    issues.is_noisy = _detect_noise(img)

    return issues


def _detect_noise(img: Image.Image) -> bool:
    """
    Simple noise detection heuristic.

    Compares local variance in image patches. High variance in
    areas that should be smooth indicates noise.
    """
    # Simplified approach: apply median filter and compare
    # If significant difference, image is noisy
    if img.mode != "L":
        gray = img.convert("L")
    else:
        gray = img

    # Downsample for speed
    small = gray.resize((100, 100), Image.Resampling.BILINEAR)
    filtered = small.filter(ImageFilter.MedianFilter(3))

    # Compare histograms
    hist1 = small.histogram()
    hist2 = filtered.histogram()

    # Calculate difference
    diff = sum(abs(h1 - h2) for h1, h2 in zip(hist1, hist2))
    total = sum(hist1)

    # If difference is > 10% of total, consider noisy
    return diff > total * 0.1


def upscale_image(img: Image.Image, factor: float = 2.0) -> Image.Image:
    """
    Upscale an image using high-quality resampling.

    Args:
        img: PIL Image object
        factor: Upscale multiplier (default 2x)

    Returns:
        Upscaled PIL Image
    """
    width, height = img.size
    new_size = (int(width * factor), int(height * factor))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def enhance_contrast(img: Image.Image, factor: float = 1.5) -> Image.Image:
    """
    Enhance image contrast.

    Args:
        img: PIL Image object
        factor: Contrast multiplier (1.0 = no change, >1 = more contrast)

    Returns:
        Contrast-enhanced PIL Image
    """
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(factor)


def sharpen_text(img: Image.Image, factor: float = 1.3) -> Image.Image:
    """
    Sharpen image to improve text legibility.

    Args:
        img: PIL Image object
        factor: Sharpness multiplier (1.0 = no change, >1 = sharper)

    Returns:
        Sharpened PIL Image
    """
    enhancer = ImageEnhance.Sharpness(img)
    return enhancer.enhance(factor)


def denoise_image(img: Image.Image, strength: int = 3) -> Image.Image:
    """
    Remove noise using median filter.

    Args:
        img: PIL Image object
        strength: Filter kernel size (must be odd, default 3)

    Returns:
        Denoised PIL Image
    """
    # Ensure odd kernel size
    if strength % 2 == 0:
        strength += 1
    return img.filter(ImageFilter.MedianFilter(strength))


def fix_underexposure(img: Image.Image) -> Image.Image:
    """
    Fix underexposed (dark) images.

    Uses a combination of brightness and contrast enhancement.
    """
    # Increase brightness
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(1.3)

    # Increase contrast to compensate
    contrast = ImageEnhance.Contrast(img)
    return contrast.enhance(1.2)


def fix_overexposure(img: Image.Image) -> Image.Image:
    """
    Fix overexposed (bright/washed out) images.

    Reduces brightness and increases contrast.
    """
    # Reduce brightness
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(0.8)

    # Increase contrast
    contrast = ImageEnhance.Contrast(img)
    return contrast.enhance(1.3)
