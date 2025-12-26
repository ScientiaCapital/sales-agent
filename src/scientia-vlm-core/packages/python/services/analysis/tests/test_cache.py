"""
TDD tests for AnalysisCache.

RED phase: These tests define the API we want.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add the services/analysis directory to path for imports
services_path = Path(__file__).parent.parent
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))

from cache import AnalysisCache, hash_image  # noqa: E402

# =============================================================================
# CACHE INITIALIZATION TESTS
# =============================================================================


class TestAnalysisCacheInit:
    """Test cache initialization."""

    def test_init_with_valid_url_and_key(self):
        """Should initialize with valid Supabase credentials."""
        cache = AnalysisCache(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key-12345",
        )
        assert cache.supabase_url == "https://test.supabase.co"

    def test_init_with_empty_url_raises(self):
        """Should raise ValueError for empty URL."""
        with pytest.raises(ValueError, match="Supabase URL"):
            AnalysisCache(supabase_url="", supabase_key="test-key")

    def test_init_with_empty_key_raises(self):
        """Should raise ValueError for empty key."""
        with pytest.raises(ValueError, match="Supabase key"):
            AnalysisCache(supabase_url="https://test.supabase.co", supabase_key="")


# =============================================================================
# HASH FUNCTION TESTS
# =============================================================================


class TestImageHash:
    """Test image hashing."""

    def test_hash_image_returns_sha256(self):
        """Should return SHA-256 hash of image content."""
        result = hash_image("SGVsbG8gV29ybGQ=")  # "Hello World" base64
        assert len(result) == 64  # SHA-256 hex is 64 chars
        assert result.isalnum()

    def test_hash_image_deterministic(self):
        """Same input should produce same hash."""
        hash1 = hash_image("dGVzdCBpbWFnZQ==")
        hash2 = hash_image("dGVzdCBpbWFnZQ==")
        assert hash1 == hash2

    def test_hash_image_different_inputs(self):
        """Different inputs should produce different hashes."""
        hash1 = hash_image("aW1hZ2UgMQ==")
        hash2 = hash_image("aW1hZ2UgMg==")
        assert hash1 != hash2


# =============================================================================
# CACHE GET TESTS
# =============================================================================


class TestAnalysisCacheGet:
    """Test cache retrieval."""

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def cache(self, mock_supabase):
        """Create cache with mocked client injected directly."""
        cache = AnalysisCache(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )
        # Inject mock client directly to bypass lazy initialization
        cache._client = mock_supabase
        return cache

    @pytest.mark.asyncio
    async def test_get_returns_cached_result(self, cache, mock_supabase):
        """Should return cached result for known hash."""
        mock_response = mock_supabase.table.return_value.select.return_value
        mock_response.eq.return_value.single.return_value.execute.return_value.data = {
            "result": {"trade": "solar", "confidence": 0.85},
            "model_used": "qwen/qwen2.5-vl-72b-instruct",
        }

        result = await cache.get("abc123hash")

        assert result is not None
        assert result["trade"] == "solar"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_cache_miss(self, cache, mock_supabase):
        """Should return None for unknown hash."""
        mock_response = mock_supabase.table.return_value.select.return_value
        mock_response.eq.return_value.single.return_value.execute.return_value.data = None

        result = await cache.get("unknown-hash")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self, cache, mock_supabase):
        """Should return None on connection error (graceful degradation)."""
        mock_response = mock_supabase.table.return_value.select.return_value
        mock_response.eq.return_value.single.return_value.execute.side_effect = (
            Exception("Connection failed")
        )

        result = await cache.get("any-hash")

        assert result is None  # Graceful degradation


# =============================================================================
# CACHE SET TESTS
# =============================================================================


class TestAnalysisCacheSet:
    """Test cache storage."""

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def cache(self, mock_supabase):
        """Create cache with mocked client injected directly."""
        cache = AnalysisCache(
            supabase_url="https://test.supabase.co",
            supabase_key="test-key",
        )
        # Inject mock client directly to bypass lazy initialization
        cache._client = mock_supabase
        return cache

    @pytest.mark.asyncio
    async def test_set_stores_result(self, cache, mock_supabase):
        """Should store result in cache."""
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        result = {"trade": "electrical", "confidence": 0.90}
        await cache.set(
            image_hash="def456hash",
            result=result,
            model="qwen/qwen2.5-vl-72b-instruct",
        )

        # Verify upsert was called
        mock_supabase.table.assert_called_with("analysis_cache")
        mock_supabase.table.return_value.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_includes_metadata(self, cache, mock_supabase):
        """Should include trade and confidence in stored data."""
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = (
            MagicMock()
        )

        result = {"trade": "hvac", "confidence": 0.75}
        await cache.set(
            image_hash="ghi789hash",
            result=result,
            model="qwen/qwen2.5-vl-72b-instruct",
            trade="hvac",
            confidence=0.75,
        )

        # Verify the upsert call includes metadata
        call_args = mock_supabase.table.return_value.upsert.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_set_handles_connection_error(self, cache, mock_supabase):
        """Should not raise on connection error (graceful degradation)."""
        mock_supabase.table.return_value.upsert.return_value.execute.side_effect = (
            Exception("Connection failed")
        )

        # Should not raise - graceful degradation
        await cache.set(
            image_hash="jkl012hash",
            result={"trade": "plumbing"},
            model="qwen/qwen2.5-vl-72b-instruct",
        )
