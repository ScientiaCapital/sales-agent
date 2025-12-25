"""
Tests for VLMWebsiteAnalyzer - VLM-based website screenshot analysis.

Tests cover:
- Screenshot analysis with file path and base64 input
- Homepage and team page analysis
- Batch processing
- Image format detection (PNG/JPEG/WEBP)
- Cost calculation
- Circuit breaker failure handling
- Error handling for missing images
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import base64


# Mock vlm_core imports at module level
@pytest.fixture(autouse=True)
def mock_vlm_core_imports():
    """Mock vlm_core imports for all tests."""
    with patch.dict('sys.modules', {
        'vlm_core': Mock(),
        'vlm_core.providers': Mock(),
        'vlm_core.providers.openrouter': Mock(),
    }):
        yield


class TestVLMWebsiteAnalyzer:
    """Tests for VLMWebsiteAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create a VLMWebsiteAnalyzer instance with test API key."""
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer
        return VLMWebsiteAnalyzer(
            api_key="test-openrouter-key",
            model_tier="balanced"
        )

    @pytest.fixture
    def mock_vlm_result(self):
        """Create a mock VLM analysis result."""
        result = MagicMock()
        result.extraction = {
            "company_name": "ACME Corp",
            "tagline": "Building Tomorrow",
            "value_proposition": "We build amazing things",
            "industry": "Construction",
            "services": ["Commercial HVAC", "Design-Build"],
            "contact_info": {
                "phone": "555-1234",
                "email": "info@acme.com"
            },
            "team_members": [
                {"name": "John Smith", "title": "CEO"}
            ],
            "confidence": 0.9
        }
        result.tokens_used = 1200
        result.latency_ms = 1500
        return result

    @pytest.mark.asyncio
    async def test_analyze_screenshot_with_path(
        self,
        analyzer,
        mock_screenshot_path,
        mock_vlm_result
    ):
        """
        Test analyzing a screenshot using file path.

        The analyzer should load an image from disk, encode it to base64,
        and pass it to the VLM provider.
        """
        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=mock_vlm_result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        # Mock VLMConfig and withRetry at vlm_core module level
        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            result = await analyzer.analyze_screenshot(
                image_path=str(mock_screenshot_path),
                analysis_type="website"
            )

            # Verify successful extraction
            assert result["company_name"] == "ACME Corp"
            assert result["industry"] == "Construction"
            assert result["confidence"] == 0.9
            assert len(result["services"]) == 2
            assert len(result["team_members"]) == 1

            # Verify provider was called
            mock_provider.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_screenshot_with_base64(
        self,
        analyzer,
        mock_vlm_result
    ):
        """
        Test analyzing a screenshot using base64 input.

        This tests the alternative input method where the image is already
        encoded to base64 (e.g., from a web upload or API).
        """
        # Create a minimal base64-encoded PNG
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        base64_image = f"data:image/png;base64,{base64.b64encode(png_data).decode('utf-8')}"

        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=mock_vlm_result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            result = await analyzer.analyze_screenshot(
                image_base64=base64_image,
                analysis_type="website"
            )

            # Verify successful extraction
            assert result["company_name"] == "ACME Corp"
            assert result["confidence"] == 0.9

            # Verify provider was called
            mock_provider.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_screenshot_missing_image(self, analyzer):
        """
        Test handling of missing image file.

        Should raise FileNotFoundError when image_path doesn't exist.
        """
        # Mock vlm_core imports
        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry'):

            with pytest.raises(FileNotFoundError, match="Image not found"):
                await analyzer.analyze_screenshot(
                    image_path="/nonexistent/path/to/image.png",
                    analysis_type="website"
                )

    @pytest.mark.asyncio
    async def test_analyze_homepage(
        self,
        analyzer,
        mock_screenshot_path,
        mock_vlm_result
    ):
        """
        Test convenience method for homepage analysis.

        This is a shorthand for analyze_screenshot with analysis_type="website".
        """
        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=mock_vlm_result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            result = await analyzer.analyze_homepage(str(mock_screenshot_path))

            # Verify it returns website analysis
            assert result["company_name"] == "ACME Corp"
            assert result["value_proposition"] == "We build amazing things"
            assert "services" in result

    @pytest.mark.asyncio
    async def test_analyze_team_page(
        self,
        analyzer,
        mock_screenshot_path
    ):
        """
        Test convenience method for team page analysis.

        This uses a different prompt (TEAM_PAGE_PROMPT) focused on
        extracting executive information.
        """
        # Create team page result
        team_result = MagicMock()
        team_result.extraction = {
            "team_members": [
                {"name": "Jane Doe", "title": "CEO"},
                {"name": "Bob Smith", "title": "CTO"}
            ],
            "company_name": "Tech Corp",
            "confidence": 0.85
        }
        team_result.tokens_used = 800
        team_result.latency_ms = 1200

        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=team_result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            result = await analyzer.analyze_team_page(str(mock_screenshot_path))

            # Verify team page analysis
            assert result["company_name"] == "Tech Corp"
            assert len(result["team_members"]) == 2
            assert result["team_members"][0]["title"] == "CEO"
            assert result["team_members"][1]["title"] == "CTO"

    @pytest.mark.asyncio
    async def test_batch_analyze(
        self,
        analyzer,
        mock_screenshot_path,
        tmp_path,
        mock_vlm_result
    ):
        """
        Test batch processing of multiple screenshots.

        The analyzer should process each image sequentially with a small
        delay between requests to avoid rate limits.
        """
        # Create additional test images
        screenshot2 = tmp_path / "test2.png"
        screenshot3 = tmp_path / "test3.png"

        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        screenshot2.write_bytes(png_data)
        screenshot3.write_bytes(png_data)

        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=mock_vlm_result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        images = [
            {"path": str(mock_screenshot_path)},
            {"path": str(screenshot2)},
            {"path": str(screenshot3)}
        ]

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            results = await analyzer.batch_analyze(images, analysis_type="website")

            # Verify all images were processed
            assert len(results) == 3
            for result in results:
                assert result["company_name"] == "ACME Corp"
                assert result["confidence"] == 0.9

            # Verify provider was called 3 times
            assert mock_provider.analyze.call_count == 3

    def test_load_image_formats(self, analyzer, tmp_path):
        """
        Test image format detection for PNG, JPEG, and WEBP.

        The analyzer should correctly detect the MIME type from magic bytes
        and encode the image to base64 with the proper data URL format.
        """
        # Test PNG
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
            b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        png_file = tmp_path / "test.png"
        png_file.write_bytes(png_data)

        result = analyzer._load_image(str(png_file))
        assert result.startswith("data:image/png;base64,")

        # Test JPEG
        jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG magic bytes
        jpeg_file = tmp_path / "test.jpg"
        jpeg_file.write_bytes(jpeg_data)

        result = analyzer._load_image(str(jpeg_file))
        assert result.startswith("data:image/jpeg;base64,")

        # Test WEBP
        webp_data = b'RIFF\x00\x00\x00\x00WEBP'  # WEBP magic bytes
        webp_file = tmp_path / "test.webp"
        webp_file.write_bytes(webp_data)

        result = analyzer._load_image(str(webp_file))
        assert result.startswith("data:image/webp;base64,")

    def test_estimate_cost(self, analyzer):
        """
        Test cost estimation for different models and image counts.

        Cost is based on per-image pricing:
        - fast (8b): $0.0003/image
        - balanced (30b): $0.0008/image
        - best (72b): $0.0015/image
        """
        # Test balanced model (default)
        cost = analyzer.estimate_cost(100)
        assert cost == 0.08  # 100 * 0.0008

        # Test fast model
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer
        fast_analyzer = VLMWebsiteAnalyzer(
            api_key="test-key",
            model_tier="fast"
        )
        cost = fast_analyzer.estimate_cost(100)
        assert cost == 0.03  # 100 * 0.0003

        # Test best model
        best_analyzer = VLMWebsiteAnalyzer(
            api_key="test-key",
            model_tier="best"
        )
        cost = best_analyzer.estimate_cost(100)
        assert cost == 0.15  # 100 * 0.0015

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure(
        self,
        analyzer,
        mock_screenshot_path
    ):
        """
        Test circuit breaker failure handling.

        When the circuit breaker is open (service unavailable),
        the analyzer should gracefully handle the failure and return
        an error response with confidence 0.0.
        """
        # Create a circuit breaker that fails
        mock_provider = AsyncMock()
        failing_breaker = AsyncMock()

        async def mock_execute_fail(func):
            raise Exception("Circuit breaker open - service unavailable")

        failing_breaker.execute = AsyncMock(side_effect=mock_execute_fail)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = failing_breaker

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            result = await analyzer.analyze_screenshot(
                image_path=str(mock_screenshot_path),
                analysis_type="website"
            )

            # Verify error response
            assert "error" in result
            assert result["confidence"] == 0.0
            assert "Circuit breaker" in result["error"] or "service unavailable" in result["error"]


class TestVLMWebsiteAnalyzerEdgeCases:
    """Edge case tests for VLMWebsiteAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer
        return VLMWebsiteAnalyzer(api_key="test-key")

    @pytest.mark.asyncio
    async def test_analyze_without_image_input(self, analyzer):
        """Test that either image_path or image_base64 is required."""
        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry'):

            with pytest.raises(ValueError, match="Either image_path or image_base64 required"):
                await analyzer.analyze_screenshot()

    @pytest.mark.asyncio
    async def test_batch_analyze_with_base64(self, analyzer):
        """Test batch analysis with base64-encoded images."""
        # Create mock provider
        result = MagicMock()
        result.extraction = {"company_name": "Test Co", "confidence": 0.8}
        result.tokens_used = 500
        result.latency_ms = 800

        mock_provider = AsyncMock()
        mock_provider.analyze = AsyncMock(return_value=result)

        mock_breaker = AsyncMock()
        async def execute_passthrough(func):
            return await func()
        mock_breaker.execute = AsyncMock(side_effect=execute_passthrough)

        analyzer._provider = mock_provider
        analyzer._circuit_breaker = mock_breaker

        # Test with base64 images
        images = [
            {"base64": "data:image/png;base64,iVBORw0KGgo="},
            {"base64": "data:image/png;base64,iVBORw0KGgo="}
        ]

        with patch('vlm_core.VLMConfig'), \
             patch('vlm_core.withRetry', side_effect=lambda f: f()):

            results = await analyzer.batch_analyze(images)

            assert len(results) == 2
            for result_item in results:
                assert result_item["company_name"] == "Test Co"

    @pytest.mark.asyncio
    async def test_batch_analyze_with_errors(self, analyzer, tmp_path):
        """Test that batch processing continues even if some images fail."""
        # Create one valid image
        png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
        )
        valid_image = tmp_path / "valid.png"
        valid_image.write_bytes(png_data)

        images = [
            {"path": str(valid_image)},
            {"path": "/nonexistent/image.png"},  # This will fail
            {"path": str(valid_image)}
        ]

        results = await analyzer.batch_analyze(images)

        # Should have 3 results (2 success, 1 error)
        assert len(results) == 3

        # Middle result should be an error
        assert "error" in results[1]
        assert results[1]["confidence"] == 0.0

    def test_load_image_missing_file(self, analyzer):
        """Test loading a non-existent image file."""
        with pytest.raises(FileNotFoundError, match="Image not found"):
            analyzer._load_image("/nonexistent/image.png")

    def test_model_tier_selection(self):
        """Test that model tier is correctly mapped to model name."""
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer

        # Test all valid tiers
        fast = VLMWebsiteAnalyzer(api_key="test", model_tier="fast")
        assert fast.model == "qwen/qwen2.5-vl-8b-instruct"

        balanced = VLMWebsiteAnalyzer(api_key="test", model_tier="balanced")
        assert balanced.model == "qwen/qwen2.5-vl-30b-instruct"

        best = VLMWebsiteAnalyzer(api_key="test", model_tier="best")
        assert best.model == "qwen/qwen2.5-vl-72b-instruct"

        # Test invalid tier defaults to balanced
        invalid = VLMWebsiteAnalyzer(api_key="test", model_tier="invalid")
        assert invalid.model == "qwen/qwen2.5-vl-30b-instruct"

    def test_lazy_provider_loading(self):
        """Test that provider is not initialized until first use."""
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer

        analyzer = VLMWebsiteAnalyzer(api_key="test-key")

        # Provider should be None initially
        assert analyzer._provider is None
        assert analyzer._circuit_breaker is None

        # Calling _get_provider should initialize it
        with patch('vlm_core.providers.openrouter.OpenRouterProvider') as mock_provider, \
             patch('vlm_core.CircuitBreaker') as mock_breaker, \
             patch('vlm_core.CircuitBreakerConfig') as mock_config:

            provider = analyzer._get_provider()

            # Should be initialized now
            assert analyzer._provider is not None
            assert analyzer._circuit_breaker is not None
