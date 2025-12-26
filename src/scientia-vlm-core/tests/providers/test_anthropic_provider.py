"""
TDD Unit Tests for Anthropic VLM Provider

Tests for AnthropicProvider - our PREMIUM WESTERN BASELINE.
All tests use mocked AsyncAnthropic client to avoid real API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the google genai module before importing providers to avoid ImportError
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()

from shared.audit.schema import Provider
from shared.providers.anthropic import AnthropicProvider

# =============================================================================
# INITIALIZATION TESTS (4 tests)
# =============================================================================


class TestAnthropicProviderInit:
    """Test provider initialization and class attributes."""

    def test_provider_class_attribute(self) -> None:
        """Verify provider class attribute equals Provider.ANTHROPIC."""
        assert AnthropicProvider.provider == Provider.ANTHROPIC

    def test_is_chinese_vlm_false(self) -> None:
        """Verify is_chinese_vlm is False - Anthropic is western baseline."""
        assert AnthropicProvider.is_chinese_vlm is False

    def test_init_with_valid_api_key(self, valid_api_key: str) -> None:
        """Provider accepts valid non-empty API key."""
        provider = AnthropicProvider(api_key=valid_api_key)
        assert provider.api_key == valid_api_key
        assert provider._client is None  # Client not initialized until used

    def test_init_with_empty_api_key_raises(self, empty_api_key: str) -> None:
        """Provider raises ValueError for empty API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            AnthropicProvider(api_key=empty_api_key)

    def test_init_with_whitespace_api_key_raises(self, whitespace_api_key: str) -> None:
        """Provider raises ValueError for whitespace-only API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            AnthropicProvider(api_key=whitespace_api_key)


# =============================================================================
# MODEL INFO TESTS (4 tests)
# =============================================================================


class TestAnthropicProviderModelInfo:
    """Test model info and available models methods."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    def test_get_available_models_returns_list(self, provider: AnthropicProvider) -> None:
        """get_available_models returns non-empty list of model dicts."""
        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0

        # Each model should have required keys
        for model in models:
            assert "model" in model
            assert "provider" in model
            assert model["provider"] == "anthropic"

    def test_get_model_info_claude_sonnet(self, provider: AnthropicProvider) -> None:
        """get_model_info returns correct pricing for Claude Sonnet ($3/$15)."""
        model_info = provider.get_model_info("claude-sonnet-4-20250514")

        assert model_info["cost_per_1m_input"] == 3.00
        assert model_info["cost_per_1m_output"] == 15.00
        assert model_info["vision"] is True

    def test_get_model_info_claude_opus(self, provider: AnthropicProvider) -> None:
        """get_model_info returns correct pricing for Claude Opus ($15/$75)."""
        model_info = provider.get_model_info("claude-opus-4-20250514")

        assert model_info["cost_per_1m_input"] == 15.00
        assert model_info["cost_per_1m_output"] == 75.00
        assert model_info["vision"] is True

    def test_get_model_info_claude_haiku(self, provider: AnthropicProvider) -> None:
        """get_model_info returns correct pricing for Claude Haiku ($1/$5)."""
        model_info = provider.get_model_info("claude-3-5-haiku-20241022")

        assert model_info["cost_per_1m_input"] == 1.00
        assert model_info["cost_per_1m_output"] == 5.00
        assert model_info["vision"] is True

    def test_get_model_info_unknown_model_returns_default(
        self, provider: AnthropicProvider
    ) -> None:
        """get_model_info returns Sonnet pricing fallback for unknown models."""
        model_info = provider.get_model_info("unknown-model-xyz")

        # Falls back to Sonnet pricing
        assert model_info["cost_per_1m_input"] == 3.00
        assert model_info["cost_per_1m_output"] == 15.00


# =============================================================================
# COST CALCULATION TESTS (4 tests)
# =============================================================================


class TestAnthropicProviderCostCalculation:
    """Test cost calculation functionality."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    def test_calculate_cost_sonnet(self, provider: AnthropicProvider) -> None:
        """Calculate cost correctly for Claude Sonnet with $3/$15 pricing."""
        # 1000 input tokens = 1000/1M * $3 = $0.003
        # 500 output tokens = 500/1M * $15 = $0.0075
        # Total = $0.0105
        cost = provider.calculate_cost(
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
        )

        assert cost.input_cost_usd == pytest.approx(0.003, rel=1e-6)
        assert cost.output_cost_usd == pytest.approx(0.0075, rel=1e-6)
        assert cost.total_cost_usd == pytest.approx(0.0105, rel=1e-6)

    def test_calculate_cost_opus(self, provider: AnthropicProvider) -> None:
        """Calculate cost correctly for Claude Opus with $15/$75 pricing."""
        # 1000 input tokens = 1000/1M * $15 = $0.015
        # 500 output tokens = 500/1M * $75 = $0.0375
        # Total = $0.0525
        cost = provider.calculate_cost(
            model="claude-opus-4-20250514",
            input_tokens=1000,
            output_tokens=500,
        )

        assert cost.input_cost_usd == pytest.approx(0.015, rel=1e-6)
        assert cost.output_cost_usd == pytest.approx(0.0375, rel=1e-6)
        assert cost.total_cost_usd == pytest.approx(0.0525, rel=1e-6)
        # Opus should trigger cost alert (> $0.03)
        assert cost.cost_alert_triggered is True

    def test_calculate_cost_zero_tokens(self, provider: AnthropicProvider) -> None:
        """Calculate cost returns zero for zero tokens."""
        cost = provider.calculate_cost(
            model="claude-sonnet-4-20250514",
            input_tokens=0,
            output_tokens=0,
        )

        assert cost.input_cost_usd == 0.0
        assert cost.output_cost_usd == 0.0
        assert cost.total_cost_usd == 0.0
        assert cost.cost_alert_triggered is False

    def test_calculate_cost_negative_tokens_raises(
        self, provider: AnthropicProvider
    ) -> None:
        """Calculate cost raises ValueError for negative token counts."""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="claude-sonnet-4-20250514",
                input_tokens=-100,
                output_tokens=500,
            )

        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="claude-sonnet-4-20250514",
                input_tokens=1000,
                output_tokens=-50,
            )


# =============================================================================
# ANALYZE IMAGE TESTS (4 tests - mocked)
# =============================================================================


class TestAnthropicProviderAnalyzeImage:
    """Test analyze_image method with mocked API client."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    @pytest.mark.asyncio
    async def test_analyze_image_success(
        self,
        provider: AnthropicProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
        mock_async_anthropic_client: AsyncMock,
    ) -> None:
        """analyze_image returns AnalyzeImageResult on success."""
        with patch.object(provider, "_client", mock_async_anthropic_client):
            # Skip client initialization since we're patching
            provider._client = mock_async_anthropic_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="claude-sonnet-4-20250514",
            )

            # Verify result structure matches AnalyzeImageResult
            assert "response" in result
            assert "extracted" in result
            assert "input_tokens" in result
            assert "output_tokens" in result
            assert "latency_ms" in result
            assert "request_id" in result
            assert "confidence" in result

            # Verify token counts from mock
            assert result["input_tokens"] == 1000
            assert result["output_tokens"] == 500

    @pytest.mark.asyncio
    async def test_analyze_image_extracts_content_blocks(
        self,
        provider: AnthropicProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
        mock_async_anthropic_client: AsyncMock,
    ) -> None:
        """analyze_image correctly parses TextBlock content from response."""
        with patch.object(provider, "_client", mock_async_anthropic_client):
            provider._client = mock_async_anthropic_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="claude-sonnet-4-20250514",
            )

            # Verify content was extracted from TextBlock
            assert "response" in result
            assert "content" in result["response"]
            # Mock returns JSON with image_type and trade
            assert "image_type" in result["extracted"]
            assert result["extracted"]["image_type"] == "blueprint"
            assert result["extracted"]["trade"] == "electrical"

    @pytest.mark.asyncio
    async def test_analyze_image_api_error(
        self,
        provider: AnthropicProvider,
        temp_jpeg_path: Path,
        sample_prompt: str,
        api_error: Exception,
    ) -> None:
        """analyze_image raises RuntimeError on API error."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=api_error)

        with patch.object(provider, "_client", mock_client):
            provider._client = mock_client

            with pytest.raises(RuntimeError, match="Anthropic API error"):
                await provider.analyze_image(
                    image_path=temp_jpeg_path,
                    prompt=sample_prompt,
                    model="claude-sonnet-4-20250514",
                )

    @pytest.mark.asyncio
    async def test_analyze_image_file_not_found(
        self,
        provider: AnthropicProvider,
        sample_prompt: str,
        mock_async_anthropic_client: AsyncMock,
    ) -> None:
        """analyze_image raises FileNotFoundError for non-existent image."""
        provider._client = mock_async_anthropic_client

        non_existent_path = Path("/path/to/nonexistent/image.jpg")

        with pytest.raises(FileNotFoundError, match="Image not found"):
            await provider.analyze_image(
                image_path=non_existent_path,
                prompt=sample_prompt,
                model="claude-sonnet-4-20250514",
            )


# =============================================================================
# CLIENT INITIALIZATION TESTS
# =============================================================================


class TestAnthropicProviderClientInit:
    """Test async client initialization."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    @pytest.mark.asyncio
    async def test_init_client_creates_async_anthropic(
        self, provider: AnthropicProvider
    ) -> None:
        """_init_client creates AsyncAnthropic client with API key."""
        with patch(
            "shared.providers.anthropic.AsyncAnthropic"
        ) as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            await provider._init_client()

            mock_client_class.assert_called_once_with(api_key=provider.api_key)
            assert provider._client == mock_instance

    @pytest.mark.asyncio
    async def test_init_client_idempotent(
        self, provider: AnthropicProvider
    ) -> None:
        """_init_client is idempotent - only creates client once."""
        with patch(
            "shared.providers.anthropic.AsyncAnthropic"
        ) as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            # Call twice
            await provider._init_client()
            await provider._init_client()

            # Should only create client once
            mock_client_class.assert_called_once()


# =============================================================================
# JSON PARSING TESTS
# =============================================================================


class TestAnthropicProviderJsonParsing:
    """Test JSON response parsing utility."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    def test_parse_json_response_with_markdown_block(
        self, provider: AnthropicProvider
    ) -> None:
        """Parse JSON from markdown code block."""
        content = '```json\n{"key": "value", "count": 42}\n```'
        result = provider._parse_json_response(content)

        assert result == {"key": "value", "count": 42}

    def test_parse_json_response_with_generic_block(
        self, provider: AnthropicProvider
    ) -> None:
        """Parse JSON from generic code block."""
        content = '```\n{"key": "value"}\n```'
        result = provider._parse_json_response(content)

        assert result == {"key": "value"}

    def test_parse_json_response_invalid_json(
        self, provider: AnthropicProvider
    ) -> None:
        """Return raw_text for invalid JSON."""
        content = "This is not valid JSON at all"
        result = provider._parse_json_response(content)

        assert "raw_text" in result
        assert result["raw_text"] == content


# =============================================================================
# CONFIDENCE ESTIMATION TESTS
# =============================================================================


class TestAnthropicProviderConfidenceEstimation:
    """Test confidence estimation utility."""

    @pytest.fixture
    def provider(self, valid_api_key: str) -> AnthropicProvider:
        """Create provider instance for tests."""
        return AnthropicProvider(api_key=valid_api_key)

    def test_estimate_confidence_empty_extraction(
        self, provider: AnthropicProvider
    ) -> None:
        """Empty extraction returns 0.5 confidence."""
        assert provider._estimate_confidence({}) == 0.5

    def test_estimate_confidence_raw_text_fallback(
        self, provider: AnthropicProvider
    ) -> None:
        """raw_text fallback returns 0.5 confidence."""
        assert provider._estimate_confidence({"raw_text": "some text"}) == 0.5

    def test_estimate_confidence_full_extraction(
        self, provider: AnthropicProvider
    ) -> None:
        """Full extraction returns high confidence."""
        extracted = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }
        confidence = provider._estimate_confidence(extracted)

        # All fields non-null should give confidence close to 0.95
        assert confidence >= 0.9
        assert confidence <= 0.95

    def test_estimate_confidence_partial_extraction(
        self, provider: AnthropicProvider
    ) -> None:
        """Partial extraction returns medium confidence."""
        extracted = {
            "field1": "value1",
            "field2": None,
            "field3": "",
        }
        confidence = provider._estimate_confidence(extracted)

        # 1/3 fields filled = lower confidence
        assert confidence > 0.5
        assert confidence < 0.9
