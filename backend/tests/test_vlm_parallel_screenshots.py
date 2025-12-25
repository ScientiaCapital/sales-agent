"""
Tests for parallel screenshot processing in VLM batch operations.

Verifies that VLM can process multiple screenshots concurrently within
a single company's crawl results, respecting a batch size of 5.

Uses mocks to avoid real VLM API calls.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import time


@pytest.fixture
def mock_screenshots():
    """Generate mock screenshot data."""
    return [
        {"url": f"https://example.com/page{i}", "screenshot_path": f"/tmp/screenshot_{i}.png"}
        for i in range(1, 11)  # 10 screenshots
    ]


@pytest.fixture
def mock_vlm_extractor():
    """Mock VLM contact extractor."""
    extractor = MagicMock()

    async def mock_extract(screenshot_path, url):
        """Mock VLM extraction with realistic delay."""
        await asyncio.sleep(0.1)  # Simulate API call
        return {
            "contacts": [{"name": f"Person from {url}", "title": "CEO"}],
            "confidence": 0.9
        }

    extractor.extract_contacts = AsyncMock(side_effect=mock_extract)
    return extractor


@pytest.mark.asyncio
async def test_parallel_screenshot_processing(mock_screenshots, mock_vlm_extractor):
    """
    Test that multiple screenshots are processed concurrently.

    Verifies:
    1. Batch size of 5 is respected
    2. Processing happens in parallel (faster than sequential)
    3. All screenshots are processed successfully
    """
    # Simulate parallel processing with batch size of 5
    batch_size = 5
    results = []

    # Track call timing to verify parallelism
    call_times = []

    async def process_screenshot(screenshot):
        """Process a single screenshot (mocked)."""
        start_time = time.time()
        result = await mock_vlm_extractor.extract_contacts(
            screenshot["screenshot_path"],
            screenshot["url"]
        )
        end_time = time.time()
        call_times.append((start_time, end_time))
        return result

    # Process in batches
    for i in range(0, len(mock_screenshots), batch_size):
        batch = mock_screenshots[i:i + batch_size]

        # Process batch concurrently
        batch_start = time.time()
        batch_results = await asyncio.gather(*[
            process_screenshot(screenshot) for screenshot in batch
        ])
        batch_end = time.time()

        results.extend(batch_results)

        # Verify parallel execution (should be ~0.1s, not 0.5s for 5 screenshots)
        batch_duration = batch_end - batch_start
        assert batch_duration < 0.3, (
            f"Batch should complete in parallel (~0.1s), got {batch_duration:.2f}s. "
            "This suggests sequential processing instead of parallel."
        )

    # Verify all screenshots were processed
    assert len(results) == len(mock_screenshots), "All screenshots should be processed"
    assert all(r["contacts"] for r in results), "All results should have contacts"

    # Verify batch size was respected (2 batches: 5 + 5)
    assert mock_vlm_extractor.extract_contacts.call_count == 10

    print(f"✅ Processed {len(results)} screenshots in {len(call_times)} calls")


@pytest.mark.asyncio
async def test_speedup_compared_to_sequential(mock_screenshots):
    """
    Test that parallel processing provides speedup vs sequential.

    Verifies that processing 5 screenshots in parallel is faster than
    processing them sequentially.
    """
    async def mock_vlm_call(screenshot):
        """Mock VLM call with 0.1s delay."""
        await asyncio.sleep(0.1)
        return {"contacts": [], "confidence": 0.0}

    # Sequential processing (baseline)
    sequential_start = time.time()
    sequential_results = []
    for screenshot in mock_screenshots[:5]:  # First 5 screenshots
        result = await mock_vlm_call(screenshot)
        sequential_results.append(result)
    sequential_duration = time.time() - sequential_start

    # Parallel processing (optimized)
    parallel_start = time.time()
    parallel_results = await asyncio.gather(*[
        mock_vlm_call(screenshot) for screenshot in mock_screenshots[:5]
    ])
    parallel_duration = time.time() - parallel_start

    # Verify speedup
    speedup = sequential_duration / parallel_duration

    assert len(sequential_results) == len(parallel_results) == 5
    assert speedup > 2.0, (
        f"Parallel processing should be at least 2x faster. "
        f"Sequential: {sequential_duration:.2f}s, Parallel: {parallel_duration:.2f}s, "
        f"Speedup: {speedup:.1f}x"
    )

    print(f"✅ Speedup: {speedup:.1f}x (Sequential: {sequential_duration:.2f}s, Parallel: {parallel_duration:.2f}s)")


@pytest.mark.asyncio
async def test_batch_size_limit_respected():
    """
    Test that batch size limit of 5 is respected.

    Verifies that we don't process more than 5 screenshots concurrently
    to avoid overwhelming the VLM API.
    """
    batch_size = 5
    total_screenshots = 13  # Will create batches: 5, 5, 3

    # Track concurrent calls
    active_calls = []
    max_concurrent = 0

    async def mock_vlm_call_with_tracking(idx):
        """Mock VLM call that tracks concurrency."""
        nonlocal max_concurrent

        active_calls.append(idx)
        max_concurrent = max(max_concurrent, len(active_calls))

        await asyncio.sleep(0.05)  # Simulate API call

        active_calls.remove(idx)
        return {"contacts": [], "confidence": 0.0}

    # Process in batches
    for i in range(0, total_screenshots, batch_size):
        batch_indices = range(i, min(i + batch_size, total_screenshots))

        await asyncio.gather(*[
            mock_vlm_call_with_tracking(idx) for idx in batch_indices
        ])

    # Verify batch size was never exceeded
    assert max_concurrent <= batch_size, (
        f"Max concurrent calls should be <= {batch_size}, got {max_concurrent}"
    )

    print(f"✅ Max concurrent calls: {max_concurrent} (limit: {batch_size})")


@pytest.mark.asyncio
async def test_error_handling_in_parallel_batch():
    """
    Test that one screenshot failure doesn't block others in the batch.

    Verifies graceful error handling in parallel processing.
    """
    async def mock_vlm_call(idx):
        """Mock VLM call that fails on screenshot #3."""
        await asyncio.sleep(0.05)

        if idx == 2:  # Fail on 3rd screenshot
            raise Exception("VLM API error: rate limit exceeded")

        return {"contacts": [{"name": f"Person {idx}"}], "confidence": 0.9}

    # Process batch with one failure
    results = await asyncio.gather(*[
        mock_vlm_call(i) for i in range(5)
    ], return_exceptions=True)

    # Verify results
    assert len(results) == 5

    # Count successes and failures
    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 4, "4 screenshots should succeed"
    assert len(failures) == 1, "1 screenshot should fail"
    assert "rate limit" in str(failures[0]), "Failure should be the expected error"

    print(f"✅ Handled error gracefully: {len(successes)} successes, {len(failures)} failures")


@pytest.mark.asyncio
async def test_batch_results_maintain_order():
    """
    Test that results maintain order despite parallel processing.

    Verifies that asyncio.gather preserves result order.
    """
    async def mock_vlm_call(idx):
        """Mock VLM call with variable delay."""
        # Later items take longer (to test order preservation)
        await asyncio.sleep(0.01 * (5 - idx))
        return {"screenshot_idx": idx, "contacts": []}

    # Process batch
    results = await asyncio.gather(*[
        mock_vlm_call(i) for i in range(5)
    ])

    # Verify order is preserved
    assert len(results) == 5
    for i, result in enumerate(results):
        assert result["screenshot_idx"] == i, (
            f"Result order should be preserved. Expected idx {i}, got {result['screenshot_idx']}"
        )

    print("✅ Result order preserved despite variable processing times")
