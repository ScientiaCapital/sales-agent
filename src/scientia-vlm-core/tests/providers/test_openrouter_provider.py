"""
TDD Unit Tests for OpenRouter VLM Provider

Tests cover:
1. Initialization - class attributes, API key validation
2. Model Info - available models, pricing info
3. Cost Calculation - pricing accuracy, edge cases
4. analyze_image - mocked API calls, JSON parsing, error handling

All tests use mocks to avoid real API calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.audit.schema import CostMetrics, ModelTier, Provider
from shared.providers.openrouter import OpenRouterProvider

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestOpenRouterProviderInitialization:
    """Test provider initialization and class attributes."""

    def test_provider_class_attribute(self) -> None:
        """Provider class attribute should be Provider.OPENROUTER."""
        assert OpenRouterProvider.provider == Provider.OPENROUTER

    def test_is_chinese_vlm_true(self) -> None:
        """is_chinese_vlm class attribute should be True for OpenRouter."""
        assert OpenRouterProvider.is_chinese_vlm is True

    def test_init_with_valid_api_key(self, valid_api_key: str) -> None:
        """Provider should accept valid API key without raising."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        assert provider.api_key == valid_api_key
        assert provider._client is None
        assert provider.site_url == "https://scientia.capital"
        assert provider.app_name == "Scientia-VLM-Audit"

    def test_init_with_empty_api_key_raises(self, empty_api_key: str) -> None:
        """Provider should raise ValueError for empty API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            OpenRouterProvider(api_key=empty_api_key)

    def test_init_with_whitespace_api_key_raises(self, whitespace_api_key: str) -> None:
        """Provider should raise ValueError for whitespace-only API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            OpenRouterProvider(api_key=whitespace_api_key)

    def test_init_with_custom_site_url(self, valid_api_key: str) -> None:
        """Provider should accept custom site_url."""
        custom_url = "https://custom.example.com"
        provider = OpenRouterProvider(
            api_key=valid_api_key,
            site_url=custom_url,
        )

        assert provider.site_url == custom_url

    def test_init_with_custom_app_name(self, valid_api_key: str) -> None:
        """Provider should accept custom app_name."""
        custom_name = "Custom-App-Name"
        provider = OpenRouterProvider(
            api_key=valid_api_key,
            app_name=custom_name,
        )

        assert provider.app_name == custom_name


# =============================================================================
# MODEL INFO TESTS
# =============================================================================


class TestOpenRouterProviderModelInfo:
    """Test model information retrieval."""

    def test_get_available_models_returns_list(self, valid_api_key: str) -> None:
        """get_available_models should return a non-empty list."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_model_info_qwen_model(self, valid_api_key: str) -> None:
        """get_model_info should return correct pricing for qwen/qwen3-vl-30b-a3b-instruct."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        model_info = provider.get_model_info("qwen/qwen3-vl-30b-a3b-instruct")

        assert model_info["tier"] == ModelTier.COST_LEADER
        assert model_info["cost_per_1m_input"] == 0.22
        assert model_info["cost_per_1m_output"] == 0.22
        assert model_info["vision"] is True
        assert model_info["context_length"] == 32768

    def test_get_model_info_qwen2_5_vl_72b(self, valid_api_key: str) -> None:
        """get_model_info should return correct pricing for qwen/qwen2.5-vl-72b-instruct."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        model_info = provider.get_model_info("qwen/qwen2.5-vl-72b-instruct")

        assert model_info["tier"] == ModelTier.BUDGET
        assert model_info["cost_per_1m_input"] == 0.40
        assert model_info["cost_per_1m_output"] == 0.40
        assert model_info["vision"] is True

    def test_get_model_info_unknown_model(self, valid_api_key: str) -> None:
        """get_model_info should return default fallback for unknown model."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        model_info = provider.get_model_info("unknown/fake-model")

        # Should return fallback values
        assert model_info["tier"] == ModelTier.COST_LEADER
        assert model_info["cost_per_1m_input"] == 0.40
        assert model_info["cost_per_1m_output"] == 0.40
        assert model_info["vision"] is True
        assert model_info["context_length"] == 32768

    def test_get_available_models_all_have_provider(self, valid_api_key: str) -> None:
        """All items in get_available_models should have 'provider' field."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        models = provider.get_available_models()

        for model in models:
            assert "provider" in model, f"Model {model.get('model')} missing 'provider' field"
            assert model["provider"] == "openrouter"

    def test_get_available_models_all_have_model_name(self, valid_api_key: str) -> None:
        """All items in get_available_models should have 'model' field."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        models = provider.get_available_models()

        for model in models:
            assert "model" in model, "Model entry missing 'model' field"
            assert isinstance(model["model"], str)
            assert len(model["model"]) > 0


# =============================================================================
# COST CALCULATION TESTS
# =============================================================================


class TestOpenRouterProviderCostCalculation:
    """Test cost calculation accuracy."""

    def test_calculate_cost_qwen3_vl_30b(self, valid_api_key: str) -> None:
        """Cost calculation for qwen3-vl-30b should use $0.22/1M pricing."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        model = "qwen/qwen3-vl-30b-a3b-instruct"

        # 1000 input tokens, 500 output tokens
        cost = provider.calculate_cost(
            model=model,
            input_tokens=1000,
            output_tokens=500,
        )

        assert isinstance(cost, CostMetrics)

        # Expected costs at $0.22/1M tokens
        expected_input_cost = (1000 / 1_000_000) * 0.22  # $0.00022
        expected_output_cost = (500 / 1_000_000) * 0.22  # $0.00011
        expected_total = expected_input_cost + expected_output_cost  # $0.00033

        assert abs(cost.input_cost_usd - expected_input_cost) < 1e-9
        assert abs(cost.output_cost_usd - expected_output_cost) < 1e-9
        assert abs(cost.total_cost_usd - expected_total) < 1e-9

    def test_calculate_cost_qwen2_5_vl_72b(self, valid_api_key: str) -> None:
        """Cost calculation for qwen2.5-vl-72b should use $0.40/1M pricing."""
        provider = OpenRouterProvider(api_key=valid_api_key)
        model = "qwen/qwen2.5-vl-72b-instruct"

        # 10000 input tokens, 2000 output tokens
        cost = provider.calculate_cost(
            model=model,
            input_tokens=10000,
            output_tokens=2000,
        )

        assert isinstance(cost, CostMetrics)

        # Expected costs at $0.40/1M tokens
        expected_input_cost = (10000 / 1_000_000) * 0.40  # $0.004
        expected_output_cost = (2000 / 1_000_000) * 0.40  # $0.0008
        expected_total = expected_input_cost + expected_output_cost  # $0.0048

        assert abs(cost.input_cost_usd - expected_input_cost) < 1e-9
        assert abs(cost.output_cost_usd - expected_output_cost) < 1e-9
        assert abs(cost.total_cost_usd - expected_total) < 1e-9

    def test_calculate_cost_zero_tokens(self, valid_api_key: str) -> None:
        """Cost calculation with zero tokens should return zero cost."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        cost = provider.calculate_cost(
            model="qwen/qwen3-vl-30b-a3b-instruct",
            input_tokens=0,
            output_tokens=0,
        )

        assert cost.input_cost_usd == 0.0
        assert cost.output_cost_usd == 0.0
        assert cost.total_cost_usd == 0.0
        assert cost.cost_alert_triggered is False

    def test_calculate_cost_negative_tokens_raises(self, valid_api_key: str) -> None:
        """Cost calculation with negative tokens should raise ValueError."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="qwen/qwen3-vl-30b-a3b-instruct",
                input_tokens=-100,
                output_tokens=500,
            )

        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            provider.calculate_cost(
                model="qwen/qwen3-vl-30b-a3b-instruct",
                input_tokens=100,
                output_tokens=-500,
            )

    def test_calculate_cost_alert_triggered(self, valid_api_key: str) -> None:
        """Cost alert should trigger when cost exceeds $0.03."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Use enough tokens to trigger alert (> $0.03)
        # At $0.22/1M, need > 136,363 tokens total
        cost = provider.calculate_cost(
            model="qwen/qwen3-vl-30b-a3b-instruct",
            input_tokens=100_000,
            output_tokens=100_000,
        )

        # 200,000 tokens * $0.22/1M = $0.044 > $0.03
        assert cost.cost_alert_triggered is True


# =============================================================================
# ANALYZE IMAGE TESTS (MOCKED)
# =============================================================================


class TestOpenRouterProviderAnalyzeImage:
    """Test analyze_image with mocked API calls."""

    @pytest.mark.asyncio
    async def test_analyze_image_success(
        self,
        valid_api_key: str,
        temp_jpeg_path: Path,
        sample_prompt: str,
        mock_async_openai_client: AsyncMock,
    ) -> None:
        """analyze_image should return AnalyzeImageResult on success."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_async_openai_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="qwen/qwen3-vl-30b-a3b-instruct",
            )

        # Verify result structure
        assert "response" in result
        assert "extracted" in result
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "latency_ms" in result
        assert "confidence" in result

        # Verify token counts from mock
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500

    @pytest.mark.asyncio
    async def test_analyze_image_extracts_json(
        self,
        valid_api_key: str,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should correctly parse markdown JSON response."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Create mock response with JSON in markdown code block
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-test-456"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''```json
{"image_type": "blueprint", "trade": "solar", "equipment_visible": ["inverter", "panels"]}
```'''
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 800
        mock_response.usage.completion_tokens = 200

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="qwen/qwen3-vl-30b-a3b-instruct",
            )

        # Verify JSON was extracted correctly
        assert result["extracted"]["image_type"] == "blueprint"
        assert result["extracted"]["trade"] == "solar"
        assert "inverter" in result["extracted"]["equipment_visible"]
        assert "panels" in result["extracted"]["equipment_visible"]

    @pytest.mark.asyncio
    async def test_analyze_image_api_error(
        self,
        valid_api_key: str,
        temp_jpeg_path: Path,
        sample_prompt: str,
        api_error: Exception,
    ) -> None:
        """analyze_image should raise RuntimeError on API error."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=api_error)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_client

            with pytest.raises(RuntimeError, match="OpenRouter API error"):
                await provider.analyze_image(
                    image_path=temp_jpeg_path,
                    prompt=sample_prompt,
                    model="qwen/qwen3-vl-30b-a3b-instruct",
                )

    @pytest.mark.asyncio
    async def test_analyze_image_file_not_found(
        self,
        valid_api_key: str,
        sample_prompt: str,
    ) -> None:
        """analyze_image should raise FileNotFoundError for missing image."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Create mock client to ensure _init_client doesn't fail
        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            with pytest.raises(FileNotFoundError, match="Image not found"):
                await provider.analyze_image(
                    image_path=Path("/nonexistent/image.jpg"),
                    prompt=sample_prompt,
                    model="qwen/qwen3-vl-30b-a3b-instruct",
                )

    @pytest.mark.asyncio
    async def test_analyze_image_with_png(
        self,
        valid_api_key: str,
        temp_png_path: Path,
        sample_prompt: str,
        mock_async_openai_client: AsyncMock,
    ) -> None:
        """analyze_image should work with PNG images."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_async_openai_client

            result = await provider.analyze_image(
                image_path=temp_png_path,
                prompt=sample_prompt,
                model="qwen/qwen2.5-vl-72b-instruct",
            )

        assert "response" in result
        assert result["input_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_analyze_image_raw_text_fallback(
        self,
        valid_api_key: str,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should return raw_text when JSON parsing fails."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Create mock response with non-JSON content
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-test-789"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is plain text, not JSON."
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 100

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="qwen/qwen3-vl-30b-a3b-instruct",
            )

        # Verify fallback to raw_text
        assert "raw_text" in result["extracted"]
        assert result["extracted"]["raw_text"] == "This is plain text, not JSON."

    @pytest.mark.asyncio
    async def test_analyze_image_confidence_score(
        self,
        valid_api_key: str,
        temp_jpeg_path: Path,
        sample_prompt: str,
    ) -> None:
        """analyze_image should estimate confidence from extraction completeness."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Create mock response with complete JSON
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-test-conf"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''```json
{
    "image_type": "field_photo",
    "trade": "hvac",
    "manufacturer": "Carrier",
    "model": "58MVC"
}
```'''
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 900
        mock_response.usage.completion_tokens = 150

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_init_client", new_callable=AsyncMock):
            provider._client = mock_client

            result = await provider.analyze_image(
                image_path=temp_jpeg_path,
                prompt=sample_prompt,
                model="qwen/qwen3-vl-30b-a3b-instruct",
            )

        # Confidence should be high for complete extraction
        assert result["confidence"] is not None
        assert result["confidence"] > 0.5
        assert result["confidence"] <= 0.95


# =============================================================================
# CLIENT INITIALIZATION TESTS
# =============================================================================


class TestOpenRouterProviderClientInit:
    """Test client initialization behavior."""

    @pytest.mark.asyncio
    async def test_init_client_creates_async_openai(
        self,
        valid_api_key: str,
    ) -> None:
        """_init_client should create AsyncOpenAI with correct config."""
        provider = OpenRouterProvider(
            api_key=valid_api_key,
            site_url="https://test.example.com",
            app_name="Test-App",
        )

        with patch("shared.providers.openrouter.AsyncOpenAI") as mock_openai:
            await provider._init_client()

            mock_openai.assert_called_once_with(
                base_url="https://openrouter.ai/api/v1",
                api_key=valid_api_key,
                default_headers={
                    "HTTP-Referer": "https://test.example.com",
                    "X-Title": "Test-App",
                },
            )

    @pytest.mark.asyncio
    async def test_init_client_idempotent(
        self,
        valid_api_key: str,
    ) -> None:
        """_init_client should only create client once (idempotent)."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        with patch("shared.providers.openrouter.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Call twice
            await provider._init_client()
            await provider._init_client()

            # Should only be called once
            assert mock_openai.call_count == 1


# =============================================================================
# JSON PARSING TESTS
# =============================================================================


class TestOpenRouterProviderJsonParsing:
    """Test JSON response parsing edge cases."""

    def test_parse_json_response_markdown_json(self, valid_api_key: str) -> None:
        """_parse_json_response should handle ```json blocks."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        content = '''```json
{"key": "value", "number": 42}
```'''

        result = provider._parse_json_response(content)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_parse_json_response_plain_code_block(self, valid_api_key: str) -> None:
        """_parse_json_response should handle plain ``` blocks."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        content = '''```
{"key": "value"}
```'''

        result = provider._parse_json_response(content)

        assert result["key"] == "value"

    def test_parse_json_response_invalid_json(self, valid_api_key: str) -> None:
        """_parse_json_response should return raw_text for invalid JSON."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        content = "This is not valid JSON at all"

        result = provider._parse_json_response(content)

        assert "raw_text" in result
        assert result["raw_text"] == content

    def test_parse_json_response_pure_json(self, valid_api_key: str) -> None:
        """_parse_json_response should handle pure JSON without code blocks."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        content = '{"pure": "json", "no_blocks": true}'

        result = provider._parse_json_response(content)

        assert result["pure"] == "json"
        assert result["no_blocks"] is True


# =============================================================================
# CONFIDENCE ESTIMATION TESTS
# =============================================================================


class TestOpenRouterProviderConfidenceEstimation:
    """Test confidence score estimation."""

    def test_estimate_confidence_empty_dict(self, valid_api_key: str) -> None:
        """_estimate_confidence should return 0.5 for empty dict."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        confidence = provider._estimate_confidence({})

        assert confidence == 0.5

    def test_estimate_confidence_raw_text(self, valid_api_key: str) -> None:
        """_estimate_confidence should return 0.5 for raw_text fallback."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        confidence = provider._estimate_confidence({"raw_text": "some text"})

        assert confidence == 0.5

    def test_estimate_confidence_partial_extraction(self, valid_api_key: str) -> None:
        """_estimate_confidence should scale with extraction completeness."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # 2 out of 4 fields populated
        extracted = {
            "field1": "value1",
            "field2": "value2",
            "field3": None,
            "field4": "",
        }

        confidence = provider._estimate_confidence(extracted)

        # 2/4 = 0.5 -> 0.5 + (0.5 * 0.45) = 0.725
        assert 0.7 < confidence < 0.8

    def test_estimate_confidence_full_extraction(self, valid_api_key: str) -> None:
        """_estimate_confidence should approach 0.95 for full extraction."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # All fields populated
        extracted = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }

        confidence = provider._estimate_confidence(extracted)

        # All fields filled -> max 0.95
        assert confidence == 0.95

    def test_estimate_confidence_capped_at_95(self, valid_api_key: str) -> None:
        """_estimate_confidence should never exceed 0.95."""
        provider = OpenRouterProvider(api_key=valid_api_key)

        # Many fields all populated
        extracted = {f"field{i}": f"value{i}" for i in range(100)}

        confidence = provider._estimate_confidence(extracted)

        assert confidence == 0.95
