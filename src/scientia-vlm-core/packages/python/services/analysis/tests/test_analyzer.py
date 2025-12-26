"""
TDD tests for BlueprintAnalyzer.

RED phase: These tests define the pipeline API we want.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the services/analysis directory to path for imports
services_path = Path(__file__).parent.parent
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))

from analyzer import (  # noqa: E402
    AnalysisResult,
    BlueprintAnalyzer,
    calculate_confidence,
)

# =============================================================================
# CONFIDENCE CALCULATION TESTS
# =============================================================================


class TestCalculateConfidence:
    """Test confidence calculation from extraction completeness."""

    def test_empty_dict_returns_minimum(self):
        """Empty extraction should return minimum confidence."""
        result = calculate_confidence({})
        assert result == 0.5

    def test_all_null_returns_minimum(self):
        """All null values should return minimum confidence."""
        result = calculate_confidence({"a": None, "b": None, "c": None})
        assert result == 0.5

    def test_all_values_returns_near_maximum(self):
        """All populated values should return near-maximum confidence."""
        result = calculate_confidence({"a": "value1", "b": "value2", "c": "value3"})
        assert result >= 0.90
        assert result <= 0.95  # Cap at 0.95

    def test_partial_values_returns_proportional(self):
        """Partial values should return proportional confidence."""
        result = calculate_confidence({"a": "value", "b": None})
        # 1 out of 2 = 50% completeness
        # 0.5 + (0.5 * 0.45) = 0.725
        assert 0.70 <= result <= 0.75

    def test_confidence_capped_at_95(self):
        """Confidence should never exceed 0.95."""
        large_dict = {f"field_{i}": f"value_{i}" for i in range(100)}
        result = calculate_confidence(large_dict)
        assert result <= 0.95


# =============================================================================
# ANALYZER INITIALIZATION TESTS
# =============================================================================


class TestBlueprintAnalyzerInit:
    """Test analyzer initialization."""

    def test_init_with_cache_and_provider(self):
        """Should initialize with cache and provider."""
        mock_cache = MagicMock()
        mock_provider = MagicMock()

        analyzer = BlueprintAnalyzer(cache=mock_cache, provider=mock_provider)

        assert analyzer.cache is mock_cache
        assert analyzer.provider is mock_provider

    def test_init_without_cache(self):
        """Should work without cache (cache-less mode)."""
        mock_provider = MagicMock()

        analyzer = BlueprintAnalyzer(cache=None, provider=mock_provider)

        assert analyzer.cache is None
        assert analyzer.provider is mock_provider


# =============================================================================
# ANALYSIS RESULT TESTS
# =============================================================================


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_result_structure(self):
        """Should have expected fields."""
        result = AnalysisResult(
            extraction={"trade": "solar"},
            confidence=0.85,
            cache_hit=False,
            model_used="qwen/qwen2.5-vl-72b-instruct",
            image_hash="abc123",
        )

        assert result.extraction == {"trade": "solar"}
        assert result.confidence == 0.85
        assert result.cache_hit is False
        assert result.model_used == "qwen/qwen2.5-vl-72b-instruct"
        assert result.image_hash == "abc123"


# =============================================================================
# ANALYZE METHOD TESTS
# =============================================================================


class TestBlueprintAnalyzerAnalyze:
    """Test the main analyze method."""

    @pytest.fixture
    def mock_cache(self):
        """Mock cache with async methods."""
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        return cache

    @pytest.fixture
    def mock_provider(self):
        """Mock VLM provider."""
        provider = MagicMock()
        provider.analyze_base64 = AsyncMock(
            return_value={
                "content": '{"trade": "solar", "equipment": ["panels", "inverter"]}',
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
            }
        )
        return provider

    @pytest.fixture
    def analyzer(self, mock_cache, mock_provider):
        """Create analyzer with mocks."""
        return BlueprintAnalyzer(cache=mock_cache, provider=mock_provider)

    @pytest.mark.asyncio
    async def test_returns_cached_result_on_hit(self, mock_cache, mock_provider):
        """Should return cached result when cache hit."""
        cached = {"trade": "solar", "equipment": ["panels"]}
        mock_cache.get = AsyncMock(return_value=cached)

        analyzer = BlueprintAnalyzer(cache=mock_cache, provider=mock_provider)
        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.cache_hit is True
        assert result.extraction == cached
        # Provider should not be called on cache hit
        mock_provider.analyze_base64.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_provider_on_cache_miss(self, analyzer, mock_provider):
        """Should call provider when cache miss."""
        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.cache_hit is False
        mock_provider.analyze_base64.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_result_in_cache(self, analyzer, mock_cache):
        """Should store result in cache after VLM call."""
        await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_parses_json_from_provider_response(self, analyzer):
        """Should parse JSON from provider response."""
        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.extraction["trade"] == "solar"
        assert "equipment" in result.extraction

    @pytest.mark.asyncio
    async def test_calculates_confidence(self, analyzer):
        """Should calculate confidence from extraction."""
        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        # With 2 fields populated, should get proportional confidence
        assert result.confidence > 0.5
        assert result.confidence <= 0.95

    @pytest.mark.asyncio
    async def test_works_without_cache(self, mock_provider):
        """Should work in cache-less mode."""
        analyzer = BlueprintAnalyzer(cache=None, provider=mock_provider)

        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.cache_hit is False
        assert result.extraction["trade"] == "solar"

    @pytest.mark.asyncio
    async def test_includes_image_hash(self, analyzer):
        """Should include image hash in result."""
        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.image_hash is not None
        assert len(result.image_hash) == 64  # SHA-256

    @pytest.mark.asyncio
    async def test_handles_markdown_json_response(self, mock_cache, mock_provider):
        """Should parse JSON wrapped in markdown code blocks."""
        mock_provider.analyze_base64 = AsyncMock(
            return_value={
                "content": '```json\n{"trade": "electrical"}\n```',
                "usage": {"prompt_tokens": 1000, "completion_tokens": 50},
            }
        )
        analyzer = BlueprintAnalyzer(cache=mock_cache, provider=mock_provider)

        result = await analyzer.analyze(
            image_base64="dGVzdCBpbWFnZQ==",
            prompt="Analyze this blueprint",
        )

        assert result.extraction["trade"] == "electrical"
