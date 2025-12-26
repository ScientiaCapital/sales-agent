"""
Unit tests for vlm_core.preprocessing module.

Tests cover:
- Image issue detection
- Preprocessing functions (upscale, contrast, sharpen, denoise)
- Configuration options
- Edge cases

@module vlm_core.preprocessing
@version 1.0.0
"""

import io
import pytest
from PIL import Image

from vlm_core.preprocessing import (
    preprocess_image,
    detect_image_issues,
    upscale_image,
    enhance_contrast,
    sharpen_text,
    denoise_image,
    PreprocessConfig,
    ImageIssues,
)
from vlm_core.preprocessing.image_processor import (
    preprocess_image_detailed,
    fix_underexposure,
    fix_overexposure,
)


def create_test_image(
    width: int = 100,
    height: int = 100,
    color: tuple = (128, 128, 128),
    mode: str = "RGB",
) -> bytes:
    """Create a test image and return as bytes."""
    img = Image.new(mode, (width, height), color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_low_contrast_image(width: int = 100, height: int = 100) -> bytes:
    """Create a low contrast (faded) test image."""
    img = Image.new("RGB", (width, height), (128, 128, 128))
    # Fill with very similar colors to simulate low contrast
    pixels = img.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (125 + (x % 6), 125 + (y % 6), 125)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_dark_image(width: int = 100, height: int = 100) -> bytes:
    """Create an underexposed (dark) test image."""
    img = Image.new("RGB", (width, height), (30, 30, 30))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_bright_image(width: int = 100, height: int = 100) -> bytes:
    """Create an overexposed (bright) test image."""
    img = Image.new("RGB", (width, height), (230, 230, 230))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestImageIssues:
    """Tests for ImageIssues dataclass."""

    def test_needs_preprocessing_false_by_default(self):
        """Default ImageIssues should not need preprocessing."""
        issues = ImageIssues()
        assert issues.needs_preprocessing is False

    def test_needs_preprocessing_true_when_small(self):
        """Should need preprocessing when image is small."""
        issues = ImageIssues(is_small=True)
        assert issues.needs_preprocessing is True

    def test_needs_preprocessing_true_when_faded(self):
        """Should need preprocessing when image is faded."""
        issues = ImageIssues(is_faded=True)
        assert issues.needs_preprocessing is True

    def test_issue_count_returns_correct_count(self):
        """Should correctly count issues."""
        issues = ImageIssues(is_small=True, is_faded=True, is_dark=True)
        assert issues.issue_count == 3


class TestPreprocessConfig:
    """Tests for PreprocessConfig dataclass."""

    def test_default_config_has_auto_detect_enabled(self):
        """Default config should have auto_detect enabled."""
        config = PreprocessConfig()
        assert config.auto_detect is True

    def test_default_upscale_factor_is_2(self):
        """Default upscale factor should be 2.0."""
        config = PreprocessConfig()
        assert config.upscale_factor == 2.0

    def test_default_output_format_is_png(self):
        """Default output format should be PNG."""
        config = PreprocessConfig()
        assert config.output_format == "PNG"


class TestDetectImageIssues:
    """Tests for detect_image_issues function."""

    def test_detects_small_image(self):
        """Should detect images smaller than threshold."""
        img_bytes = create_test_image(400, 400)
        img = Image.open(io.BytesIO(img_bytes))
        config = PreprocessConfig(min_dimension_px=800)

        issues = detect_image_issues(img, config)
        assert issues.is_small is True

    def test_large_image_not_small(self):
        """Should not flag large images as small."""
        img_bytes = create_test_image(1000, 1000)
        img = Image.open(io.BytesIO(img_bytes))
        config = PreprocessConfig(min_dimension_px=800)

        issues = detect_image_issues(img, config)
        assert issues.is_small is False

    def test_detects_dark_image(self):
        """Should detect underexposed images."""
        img_bytes = create_dark_image()
        img = Image.open(io.BytesIO(img_bytes))
        config = PreprocessConfig(brightness_low=50)

        issues = detect_image_issues(img, config)
        assert issues.is_dark is True

    def test_detects_bright_image(self):
        """Should detect overexposed images."""
        img_bytes = create_bright_image()
        img = Image.open(io.BytesIO(img_bytes))
        config = PreprocessConfig(brightness_high=200)

        issues = detect_image_issues(img, config)
        assert issues.is_bright is True


class TestUpscaleImage:
    """Tests for upscale_image function."""

    def test_upscale_doubles_dimensions(self):
        """Upscale with factor 2 should double dimensions."""
        img_bytes = create_test_image(100, 100)
        img = Image.open(io.BytesIO(img_bytes))

        result = upscale_image(img, factor=2.0)
        assert result.size == (200, 200)

    def test_upscale_custom_factor(self):
        """Should support custom upscale factors."""
        img_bytes = create_test_image(100, 100)
        img = Image.open(io.BytesIO(img_bytes))

        result = upscale_image(img, factor=1.5)
        assert result.size == (150, 150)

    def test_upscale_preserves_mode(self):
        """Should preserve image mode."""
        img_bytes = create_test_image(100, 100)
        img = Image.open(io.BytesIO(img_bytes))

        result = upscale_image(img, factor=2.0)
        assert result.mode == img.mode


class TestEnhanceContrast:
    """Tests for enhance_contrast function."""

    def test_enhance_returns_image(self):
        """Should return a PIL Image."""
        img_bytes = create_test_image()
        img = Image.open(io.BytesIO(img_bytes))

        result = enhance_contrast(img)
        assert isinstance(result, Image.Image)

    def test_enhance_preserves_size(self):
        """Should preserve image dimensions."""
        img_bytes = create_test_image(200, 150)
        img = Image.open(io.BytesIO(img_bytes))

        result = enhance_contrast(img)
        assert result.size == (200, 150)


class TestSharpenText:
    """Tests for sharpen_text function."""

    def test_sharpen_returns_image(self):
        """Should return a PIL Image."""
        img_bytes = create_test_image()
        img = Image.open(io.BytesIO(img_bytes))

        result = sharpen_text(img)
        assert isinstance(result, Image.Image)

    def test_sharpen_preserves_size(self):
        """Should preserve image dimensions."""
        img_bytes = create_test_image(200, 150)
        img = Image.open(io.BytesIO(img_bytes))

        result = sharpen_text(img)
        assert result.size == (200, 150)


class TestDenoiseImage:
    """Tests for denoise_image function."""

    def test_denoise_returns_image(self):
        """Should return a PIL Image."""
        img_bytes = create_test_image()
        img = Image.open(io.BytesIO(img_bytes))

        result = denoise_image(img)
        assert isinstance(result, Image.Image)

    def test_denoise_even_strength_becomes_odd(self):
        """Even kernel size should be converted to odd."""
        img_bytes = create_test_image()
        img = Image.open(io.BytesIO(img_bytes))

        # Should not raise error with even strength
        result = denoise_image(img, strength=4)
        assert isinstance(result, Image.Image)


class TestPreprocessImage:
    """Tests for main preprocess_image function."""

    def test_returns_bytes(self):
        """Should return bytes."""
        img_bytes = create_test_image()
        result = preprocess_image(img_bytes)
        assert isinstance(result, bytes)

    def test_small_image_is_upscaled(self):
        """Small images should be upscaled."""
        img_bytes = create_test_image(400, 400)
        config = PreprocessConfig(
            auto_detect=True,
            min_dimension_px=800,
            upscale_factor=2.0,
        )

        result = preprocess_image(img_bytes, config)
        result_img = Image.open(io.BytesIO(result))

        # Should be upscaled to 800x800
        assert result_img.size == (800, 800)

    def test_handles_rgba_images(self):
        """Should handle RGBA images by converting to RGB."""
        img = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        result = preprocess_image(buffer.getvalue())
        assert isinstance(result, bytes)

    def test_handles_palette_images(self):
        """Should handle palette mode images."""
        img = Image.new("P", (100, 100))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        result = preprocess_image(buffer.getvalue())
        assert isinstance(result, bytes)

    def test_verbose_mode_doesnt_crash(self):
        """Verbose mode should not crash."""
        img_bytes = create_test_image(400, 400)
        config = PreprocessConfig(verbose=True)

        # Should not raise
        result = preprocess_image(img_bytes, config)
        assert isinstance(result, bytes)

    def test_jpeg_output_format(self):
        """Should support JPEG output."""
        img_bytes = create_test_image()
        config = PreprocessConfig(output_format="JPEG")

        result = preprocess_image(img_bytes, config)
        # JPEG should be smaller or at least valid
        result_img = Image.open(io.BytesIO(result))
        assert result_img.format == "JPEG"


class TestPreprocessImageDetailed:
    """Tests for preprocess_image_detailed function."""

    def test_returns_preprocess_result(self):
        """Should return PreprocessResult."""
        img_bytes = create_test_image()
        from vlm_core.preprocessing.config import PreprocessResult

        result = preprocess_image_detailed(img_bytes)
        assert isinstance(result, PreprocessResult)

    def test_tracks_original_size(self):
        """Should track original image size."""
        img_bytes = create_test_image(300, 200)

        result = preprocess_image_detailed(img_bytes)
        assert result.original_size == (300, 200)

    def test_tracks_transformations(self):
        """Should track applied transformations."""
        img_bytes = create_test_image(400, 400)
        config = PreprocessConfig(
            auto_detect=True,
            min_dimension_px=800,
        )

        result = preprocess_image_detailed(img_bytes, config)
        assert "upscale_2.0x" in result.transformations_applied

    def test_was_modified_false_when_no_changes(self):
        """was_modified should be False when no transformations applied."""
        img_bytes = create_test_image(1000, 1000)  # Large enough
        config = PreprocessConfig(
            auto_detect=True,
            min_dimension_px=800,
            enhance_contrast=False,
            sharpen_text=False,
            denoise=False,
            fix_exposure=False,
        )

        result = preprocess_image_detailed(img_bytes, config)
        assert result.was_modified is False


class TestExposureFixes:
    """Tests for exposure fix functions."""

    def test_fix_underexposure_returns_image(self):
        """Should return a PIL Image."""
        img_bytes = create_dark_image()
        img = Image.open(io.BytesIO(img_bytes))

        result = fix_underexposure(img)
        assert isinstance(result, Image.Image)

    def test_fix_overexposure_returns_image(self):
        """Should return a PIL Image."""
        img_bytes = create_bright_image()
        img = Image.open(io.BytesIO(img_bytes))

        result = fix_overexposure(img)
        assert isinstance(result, Image.Image)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_grayscale_image(self):
        """Should handle grayscale images."""
        img = Image.new("L", (100, 100), 128)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        result = preprocess_image(buffer.getvalue())
        assert isinstance(result, bytes)

    def test_very_small_image(self):
        """Should handle very small images."""
        img_bytes = create_test_image(10, 10)

        result = preprocess_image(img_bytes)
        assert isinstance(result, bytes)

    def test_rectangular_image(self):
        """Should handle non-square images."""
        img_bytes = create_test_image(100, 500)

        result = preprocess_image(img_bytes)
        assert isinstance(result, bytes)
