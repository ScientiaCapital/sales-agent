"""
TDD Unit Tests for Gemini VLM Provider

Tests for GeminiProvider class covering:
- Initialization and configuration
- Model info and pricing
- Cost calculation
- Image analysis with mocked API

All tests use fixtures from conftest.py for test isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from shared.audit.schema import GEMINI_MODELS, ModelTier, Provider
from shared.providers.base import CostMetrics
from shared.providers.gemini import GeminiProvider

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestGeminiProviderInitialization:
    """Test suite for GeminiProvider initialization."""

    def test_provider_class_attribute(self) -> None:
        """GeminiProvider.provider should be Provider.GEMINI."""
        assert GeminiProvider.provider == Provider.GEMINI

    def test_is_chinese_vlm_false(self) -> None:
        """GeminiProvider.is_chinese_vlm should be False (western baseline)."""
        assert GeminiProvider.is_chinese_vlm is False

    def test_init_with_valid_api_key(self, valid_api_key: str) -> None:
        """GeminiProvider should accept a valid API key."""
        provider = GeminiProvider(api_key=valid_api_key)
        assert provider.api_key == valid_api_key
        assert provider._client is None  # Client initialized lazily

    def test_init_with_empty_api_key_raises(self, empty_api_key: str) -> None:
        """GeminiProvider should raise ValueError for empty API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            GeminiProvider(api_key=empty_api_key)

    def test_init_with_whitespace_api_key_raises(self, whitespace_api_key: str) -> None:
        """GeminiProvider should raise ValueError for whitespace-only API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            GeminiProvider(api_key=whitespace_api_key)


# =============================================================================
# MODEL INFO TESTS
# =============================================================================


class TestGeminiProviderModelInfo:
    """Test suite for model information retrieval."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    def test_get_available_models_returns_list(self, provider: GeminiProvider) -> None:
        """get_available_models should return a non-empty list of models."""
        models = provider.get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0
        # Each model should have required keys
        for model in models:
            assert "model" in model
            assert "provider" in model
            assert model["provider"] == "gemini"

    def test_get_model_info_gemini_2_flash(self, provider: GeminiProvider) -> None:
        """get_model_info for gemini-2.0-flash should return correct pricing."""
        model_info = provider.get_model_info("gemini-2.0-flash")
        assert model_info["cost_per_1m_input"] == 0.10
        assert model_info["cost_per_1m_output"] == 0.40
        assert model_info["tier"] == ModelTier.STANDARD
        assert model_info["vision"] is True
        assert model_info["context_length"] == 1000000

    def test_get_model_info_gemini_2_5_pro(self, provider: GeminiProvider) -> None:
        """get_model_info for gemini-2.5-pro should return correct pricing."""
        model_info = provider.get_model_info("gemini-2.5-pro")
        assert model_info["cost_per_1m_input"] == 2.00
        assert model_info["cost_per_1m_output"] == 12.00
        assert model_info["tier"] == ModelTier.PREMIUM
        assert model_info["vision"] is True

    def test_get_model_info_gemini_flash_lite(self, provider: GeminiProvider) -> None:
        """get_model_info for gemini-2.0-flash-lite should return correct pricing."""
        model_info = provider.get_model_info("gemini-2.0-flash-lite")
        assert model_info["cost_per_1m_input"] == 0.075
        assert model_info["cost_per_1m_output"] == 0.30
        assert model_info["tier"] == ModelTier.BUDGET
        assert model_info["vision"] is True

    def test_get_model_info_unknown_model_returns_default(
        self, provider: GeminiProvider
    ) -> None:
        """get_model_info for unknown model should return Flash pricing default."""
        model_info = provider.get_model_info("unknown-model-xyz")
        # Default fallback should be Flash pricing
        assert model_info["cost_per_1m_input"] == 0.10
        assert model_info["cost_per_1m_output"] == 0.40
        assert model_info["tier"] == ModelTier.STANDARD

    def test_available_models_match_schema(self, provider: GeminiProvider) -> None:
        """Available models should match GEMINI_MODELS from schema."""
        models = provider.get_available_models()
        model_names = {m["model"] for m in models}
        schema_model_names = set(GEMINI_MODELS.keys())
        assert model_names == schema_model_names


# =============================================================================
# COST CALCULATION TESTS
# =============================================================================


class TestGeminiProviderCostCalculation:
    """Test suite for cost calculation."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    def test_calculate_cost_gemini_flash(self, provider: GeminiProvider) -> None:
        """calculate_cost for gemini-2.0-flash should compute correctly."""
        # 1000 input tokens @ $0.10/1M = $0.0001
        # 500 output tokens @ $0.40/1M = $0.0002
        # Total = $0.0003
        cost = provider.calculate_cost(
            model="gemini-2.0-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        assert isinstance(cost, CostMetrics)
        assert cost.input_cost_usd == pytest.approx(0.0001, rel=1e-6)
        assert cost.output_cost_usd == pytest.approx(0.0002, rel=1e-6)
        assert cost.total_cost_usd == pytest.approx(0.0003, rel=1e-6)

    def test_calculate_cost_gemini_pro(self, provider: GeminiProvider) -> None:
        """calculate_cost for gemini-2.5-pro should compute correctly."""
        # 1000 input tokens @ $2.00/1M = $0.002
        # 500 output tokens @ $12.00/1M = $0.006
        # Total = $0.008
        cost = provider.calculate_cost(
            model="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
        )
        assert isinstance(cost, CostMetrics)
        assert cost.input_cost_usd == pytest.approx(0.002, rel=1e-6)
        assert cost.output_cost_usd == pytest.approx(0.006, rel=1e-6)
        assert cost.total_cost_usd == pytest.approx(0.008, rel=1e-6)

    def test_calculate_cost_zero_tokens(self, provider: GeminiProvider) -> None:
        """calculate_cost with zero tokens should return zero cost."""
        cost = provider.calculate_cost(
            model="gemini-2.0-flash",
            input_tokens=0,
            output_tokens=0,
        )
        assert cost.input_cost_usd == 0.0
        assert cost.output_cost_usd == 0.0
        assert cost.total_cost_usd == 0.0

    def test_calculate_cost_negative_tokens_raises(
        self, provider: GeminiProvider
    ) -> None:
        """calculate_cost with negative tokens should raise ValueError."""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="gemini-2.0-flash",
                input_tokens=-100,
                output_tokens=500,
            )

    def test_calculate_cost_negative_output_tokens_raises(
        self, provider: GeminiProvider
    ) -> None:
        """calculate_cost with negative output tokens should raise ValueError."""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="gemini-2.0-flash",
                input_tokens=100,
                output_tokens=-500,
            )

    def test_calculate_cost_large_token_counts(self, provider: GeminiProvider) -> None:
        """calculate_cost should handle large token counts correctly."""
        # 1M input tokens @ $0.10/1M = $0.10
        # 1M output tokens @ $0.40/1M = $0.40
        cost = provider.calculate_cost(
            model="gemini-2.0-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost.input_cost_usd == pytest.approx(0.10, rel=1e-6)
        assert cost.output_cost_usd == pytest.approx(0.40, rel=1e-6)
        assert cost.total_cost_usd == pytest.approx(0.50, rel=1e-6)

    def test_calculate_cost_alert_triggered(self, provider: GeminiProvider) -> None:
        """calculate_cost should trigger alert when cost exceeds threshold."""
        # Use enough tokens to exceed $0.03 threshold
        # At gemini-2.5-pro pricing: need significant tokens
        cost = provider.calculate_cost(
            model="gemini-2.5-pro",
            input_tokens=10000,  # $0.02
            output_tokens=5000,  # $0.06
        )
        # Total should be $0.08, which exceeds $0.03 threshold
        assert cost.total_cost_usd > 0.03
        assert cost.cost_alert_triggered is True

    def test_calculate_cost_no_alert_below_threshold(
        self, provider: GeminiProvider
    ) -> None:
        """calculate_cost should not trigger alert when cost is below threshold."""
        cost = provider.calculate_cost(
            model="gemini-2.0-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        # Total is $0.0003, well below $0.03 threshold
        assert cost.total_cost_usd < 0.03
        assert cost.cost_alert_triggered is False


# =============================================================================
# ANALYZE IMAGE TESTS (MOCKED)
# =============================================================================


class TestGeminiProviderAnalyzeImage:
    """Test suite for analyze_image method with mocked API."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    @pytest.fixture
    def mock_client(self, mock_gemini_response: MagicMock) -> MagicMock:
        """Create a mocked genai.Client."""
        client = MagicMock()
        client.models.generate_content = MagicMock(return_value=mock_gemini_response)
        return client

    @pytest.mark.asyncio
    async def test_analyze_image_success(
        self,
        provider: GeminiProvider,
        mock_client: MagicMock,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should return AnalyzeImageResult on success."""
        with patch.object(provider, "_client", mock_client):
            # Skip _init_client by setting _client directly
            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

        assert isinstance(result, dict)
        assert "response" in result
        assert "extracted" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "latency_ms" in result
        assert "confidence" in result
        assert result["response"]["model"] == "gemini-2.0-flash"

    @pytest.mark.asyncio
    async def test_analyze_image_extracts_text(
        self,
        provider: GeminiProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should parse response.text correctly."""
        # Create mock response with specific text
        mock_response = MagicMock()
        mock_response.text = '```json\n{"image_type": "blueprint", "trade": "solar"}\n```'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 1000
        mock_response.usage_metadata.candidates_token_count = 500

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        with patch.object(provider, "_client", mock_client):
            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

        # Verify extracted data parsed correctly
        assert result["extracted"]["image_type"] == "blueprint"
        assert result["extracted"]["trade"] == "solar"
        # Verify response content preserved
        assert "blueprint" in result["response"]["content"]

    @pytest.mark.asyncio
    async def test_analyze_image_api_error(
        self,
        provider: GeminiProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
        api_error: Exception,
    ) -> None:
        """analyze_image should raise RuntimeError on API failure."""
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(side_effect=api_error)

        with patch.object(provider, "_client", mock_client):
            with pytest.raises(RuntimeError, match="Gemini API error"):
                await provider.analyze_image(
                    image_path=temp_jpeg_path,
                    prompt=sample_prompt,
                    model="gemini-2.0-flash",
                )

    @pytest.mark.asyncio
    async def test_analyze_image_file_not_found(
        self,
        provider: GeminiProvider,
        sample_prompt: str,
    ) -> None:
        """analyze_image should raise FileNotFoundError for missing image."""
        nonexistent_path = Path("/nonexistent/image.jpg")

        with pytest.raises(FileNotFoundError):
            await provider.analyze_image(
                image_path=nonexistent_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

    @pytest.mark.asyncio
    async def test_analyze_image_token_extraction_from_usage_metadata(
        self,
        provider: GeminiProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should extract tokens from usage_metadata."""
        mock_response = MagicMock()
        mock_response.text = '{"data": "test"}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 1500
        mock_response.usage_metadata.candidates_token_count = 750

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        with patch.object(provider, "_client", mock_client):
            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

        assert result["input_tokens"] == 1500
        assert result["output_tokens"] == 750

    @pytest.mark.asyncio
    async def test_analyze_image_handles_plain_text_response(
        self,
        provider: GeminiProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should handle non-JSON text response."""
        mock_response = MagicMock()
        mock_response.text = "This is a plain text response without JSON."
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 500
        mock_response.usage_metadata.candidates_token_count = 200

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        with patch.object(provider, "_client", mock_client):
            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

        # Non-JSON text should be stored in raw_text
        assert "raw_text" in result["extracted"]
        assert "plain text response" in result["extracted"]["raw_text"]

    @pytest.mark.asyncio
    async def test_analyze_image_different_image_formats(
        self,
        provider: GeminiProvider,
        temp_png_path: Path,
        sample_prompt: str,
        mock_gemini_response: MagicMock,
    ) -> None:
        """analyze_image should handle PNG files correctly."""
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            return_value=mock_gemini_response
        )

        with patch.object(provider, "_client", mock_client):
            result = await provider.analyze_image(
                image_path=temp_png_path,
                prompt=sample_prompt,
                model="gemini-2.0-flash",
            )

        assert isinstance(result, dict)
        assert "response" in result


# =============================================================================
# CLIENT INITIALIZATION TESTS
# =============================================================================


class TestGeminiProviderClientInit:
    """Test suite for client initialization."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    @pytest.mark.asyncio
    async def test_init_client_creates_genai_client(
        self, provider: GeminiProvider
    ) -> None:
        """_init_client should create a genai.Client."""
        with patch("shared.providers.gemini.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            await provider._init_client()

            mock_client_class.assert_called_once_with(api_key=provider.api_key)
            assert provider._client is mock_client

    @pytest.mark.asyncio
    async def test_init_client_idempotent(self, provider: GeminiProvider) -> None:
        """_init_client should be idempotent - only create client once."""
        with patch("shared.providers.gemini.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Call init twice
            await provider._init_client()
            await provider._init_client()

            # Should only create client once
            mock_client_class.assert_called_once()


# =============================================================================
# JSON PARSING TESTS
# =============================================================================


class TestGeminiProviderJsonParsing:
    """Test suite for JSON response parsing."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    def test_parse_json_response_with_markdown(self, provider: GeminiProvider) -> None:
        """_parse_json_response should handle markdown code blocks."""
        content = '```json\n{"key": "value"}\n```'
        result = provider._parse_json_response(content)
        assert result == {"key": "value"}

    def test_parse_json_response_plain_json(self, provider: GeminiProvider) -> None:
        """_parse_json_response should handle plain JSON."""
        content = '{"key": "value"}'
        result = provider._parse_json_response(content)
        assert result == {"key": "value"}

    def test_parse_json_response_generic_code_block(
        self, provider: GeminiProvider
    ) -> None:
        """_parse_json_response should handle generic code blocks."""
        content = '```\n{"key": "value"}\n```'
        result = provider._parse_json_response(content)
        assert result == {"key": "value"}

    def test_parse_json_response_invalid_json(self, provider: GeminiProvider) -> None:
        """_parse_json_response should return raw_text for invalid JSON."""
        content = "This is not JSON at all"
        result = provider._parse_json_response(content)
        assert "raw_text" in result
        assert result["raw_text"] == content


# =============================================================================
# CONFIDENCE ESTIMATION TESTS
# =============================================================================


class TestGeminiProviderConfidenceEstimation:
    """Test suite for confidence score estimation."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> GeminiProvider:
        """Create a GeminiProvider instance for testing."""
        return GeminiProvider(api_key=valid_api_key)

    def test_estimate_confidence_full_extraction(
        self, provider: GeminiProvider
    ) -> None:
        """_estimate_confidence should return high score for full extraction."""
        extracted = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }
        confidence = provider._estimate_confidence(extracted)
        assert confidence >= 0.9
        assert confidence <= 0.95

    def test_estimate_confidence_partial_extraction(
        self, provider: GeminiProvider
    ) -> None:
        """_estimate_confidence should return medium score for partial extraction."""
        extracted = {
            "field1": "value1",
            "field2": None,
            "field3": "",
        }
        confidence = provider._estimate_confidence(extracted)
        assert confidence >= 0.5
        assert confidence < 0.9

    def test_estimate_confidence_empty_extraction(
        self, provider: GeminiProvider
    ) -> None:
        """_estimate_confidence should return low score for empty extraction."""
        extracted = {}
        confidence = provider._estimate_confidence(extracted)
        assert confidence == 0.5

    def test_estimate_confidence_raw_text_fallback(
        self, provider: GeminiProvider
    ) -> None:
        """_estimate_confidence should return 0.5 for raw_text fallback."""
        extracted = {"raw_text": "Some unstructured text"}
        confidence = provider._estimate_confidence(extracted)
        assert confidence == 0.5
