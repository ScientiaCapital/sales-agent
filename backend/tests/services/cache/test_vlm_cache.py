"""
Tests for VLM response caching.

Verifies that VLM responses are cached with 24-hour TTL to avoid redundant
expensive API calls when processing the same screenshot multiple times.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    return redis_mock


@pytest.mark.asyncio
async def test_cache_miss_returns_none(mock_redis):
    """
    Test that cache miss returns None.

    TDD: This test will FAIL until VLMCache is implemented.
    """
    from app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    # Mock redis.get to return None (cache miss)
    mock_redis.get.return_value = None

    screenshot_data = b"fake_screenshot_binary_data"
    result = await cache.get_vlm_response(screenshot_data)

    assert result is None, "Cache miss should return None"
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_hit_returns_data(mock_redis):
    """
    Test that cache hit returns cached VLM response.

    TDD: This test will FAIL until VLMCache is implemented.
    """
    from app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    # Cached VLM response
    cached_response = {
        "contacts": [
            {"name": "John Doe", "title": "CEO", "email": "john@example.com"}
        ],
        "confidence": 0.95,
        "source_url": "https://example.com/team"
    }

    # Mock redis.get to return cached data
    mock_redis.get.return_value = json.dumps(cached_response)

    screenshot_data = b"fake_screenshot_binary_data"
    result = await cache.get_vlm_response(screenshot_data)

    assert result is not None, "Cache hit should return data"
    assert result["contacts"] == cached_response["contacts"]
    assert result["confidence"] == cached_response["confidence"]
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_ttl_is_24_hours(mock_redis):
    """
    Test that VLM cache uses 24-hour TTL (86400 seconds).

    TDD: This test will FAIL until VLMCache is implemented with correct TTL.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    # Verify default TTL is 24 hours
    assert cache.default_ttl == 86400, (
        "VLM cache TTL should be 24 hours (86400 seconds)"
    )

    # Set a VLM response
    screenshot_data = b"fake_screenshot_binary_data"
    vlm_response = {
        "contacts": [{"name": "Jane Smith", "title": "CTO"}],
        "confidence": 0.92
    }

    await cache.set_vlm_response(screenshot_data, vlm_response)

    # Verify Redis setex was called with 86400 TTL
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == 86400, "TTL should be 24 hours"


@pytest.mark.asyncio
async def test_screenshot_hash_computation(mock_redis):
    """
    Test that screenshot binary is hashed with SHA256 for cache key.

    TDD: This test will FAIL until VLMCache implements proper hashing.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    screenshot_data = b"test_screenshot_binary_content_12345"

    # Compute expected hash
    expected_hash = hashlib.sha256(screenshot_data).hexdigest()

    # Set a response
    vlm_response = {"contacts": [], "confidence": 0.0}
    await cache.set_vlm_response(screenshot_data, vlm_response)

    # Verify the cache key contains the hash
    mock_redis.setex.assert_called_once()
    cache_key = mock_redis.setex.call_args[0][0]

    assert expected_hash in cache_key, (
        f"Cache key should contain SHA256 hash. "
        f"Expected hash: {expected_hash}, Got key: {cache_key}"
    )


@pytest.mark.asyncio
async def test_same_screenshot_same_key(mock_redis):
    """
    Test that identical screenshots produce identical cache keys.

    Verifies deterministic hashing for cache consistency.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    screenshot_data = b"identical_screenshot_data"
    vlm_response = {"contacts": [], "confidence": 0.0}

    # Set twice
    await cache.set_vlm_response(screenshot_data, vlm_response)
    await cache.set_vlm_response(screenshot_data, vlm_response)

    # Both calls should use the same cache key
    assert mock_redis.setex.call_count == 2
    key1 = mock_redis.setex.call_args_list[0][0][0]
    key2 = mock_redis.setex.call_args_list[1][0][0]

    assert key1 == key2, "Identical screenshots should produce identical cache keys"


@pytest.mark.asyncio
async def test_different_screenshots_different_keys(mock_redis):
    """
    Test that different screenshots produce different cache keys.

    Verifies cache isolation between different images.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    screenshot1 = b"screenshot_version_1"
    screenshot2 = b"screenshot_version_2"
    vlm_response = {"contacts": [], "confidence": 0.0}

    # Set both
    await cache.set_vlm_response(screenshot1, vlm_response)
    await cache.set_vlm_response(screenshot2, vlm_response)

    # Should use different cache keys
    assert mock_redis.setex.call_count == 2
    key1 = mock_redis.setex.call_args_list[0][0][0]
    key2 = mock_redis.setex.call_args_list[1][0][0]

    assert key1 != key2, "Different screenshots should produce different cache keys"


@pytest.mark.asyncio
async def test_cache_stats_tracking(mock_redis):
    """
    Test that cache hit/miss stats are tracked.

    Verifies integration with CacheBase hit/miss tracking.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    # Mock cache hit
    mock_redis.get.return_value = json.dumps({"contacts": [], "confidence": 0.0})
    screenshot_data = b"test_screenshot"
    await cache.get_vlm_response(screenshot_data)

    # Verify hit was tracked
    mock_redis.incr.assert_called()
    hit_calls = [call for call in mock_redis.incr.call_args_list
                 if "hits" in str(call)]
    assert len(hit_calls) > 0, "Cache hit should be tracked"


@pytest.mark.asyncio
async def test_custom_ttl_override(mock_redis):
    """
    Test that custom TTL can override the default 24-hour TTL.

    Allows flexibility for testing or special use cases.
    """
    from backend.app.services.cache.vlm_cache import VLMCache

    cache = VLMCache(redis_client=mock_redis)

    screenshot_data = b"test_screenshot"
    vlm_response = {"contacts": [], "confidence": 0.0}

    # Set with custom 1-hour TTL
    custom_ttl = 3600
    await cache.set_vlm_response(screenshot_data, vlm_response, ttl=custom_ttl)

    # Verify custom TTL was used
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == custom_ttl, "Custom TTL should override default"
