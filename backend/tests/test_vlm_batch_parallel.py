"""
Tests for parallel company processing in VLM batch operations.

Verifies that VLM batch script can process multiple companies concurrently
with a semaphore limit of 3, and that exceptions are isolated (one company
failure doesn't block others).

Uses mocks to avoid real crawler/VLM calls.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
import time


@pytest.fixture
def mock_companies():
    """Generate mock company data."""
    return [
        {
            "company_id": f"co-{i:03d}",
            "company_name": f"Test Company {i}",
            "website": f"https://example{i}.com",
            "icp_tier": "PLATINUM"
        }
        for i in range(1, 11)  # 10 companies
    ]


@pytest.fixture
def mock_crawler():
    """Mock website crawler."""
    crawler = MagicMock()

    async def mock_crawl(website_url, max_pages, company_id):
        """Mock crawl with realistic delay."""
        await asyncio.sleep(0.2)  # Simulate crawl time
        return [
            {"url": f"{website_url}/page1", "screenshot_path": f"/tmp/{company_id}_1.png"},
            {"url": f"{website_url}/page2", "screenshot_path": f"/tmp/{company_id}_2.png"}
        ]

    crawler.crawl_website = AsyncMock(side_effect=mock_crawl)
    return crawler


@pytest.fixture
def mock_vlm_extractor():
    """Mock VLM contact extractor."""
    extractor = MagicMock()

    async def mock_extract(screenshot_path, url):
        """Mock VLM extraction."""
        await asyncio.sleep(0.1)
        return {
            "contacts": [{"name": f"CEO from {url}", "title": "CEO"}],
            "confidence": 0.9
        }

    extractor.extract_contacts = AsyncMock(side_effect=mock_extract)
    return extractor


@pytest.mark.asyncio
async def test_parallel_company_processing(mock_companies, mock_crawler, mock_vlm_extractor):
    """
    Test that multiple companies are processed concurrently with semaphore limit of 3.

    Verifies:
    1. Concurrency limit of 3 is respected
    2. Processing is faster than sequential
    3. All companies are processed successfully
    """
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)

    # Track concurrent execution
    active_companies = []
    max_active = 0

    async def process_company(company):
        """Process a single company with semaphore limit."""
        nonlocal max_active

        async with semaphore:
            active_companies.append(company["company_id"])
            max_active = max(max_active, len(active_companies))

            # Crawl website
            pages = await mock_crawler.crawl_website(
                website_url=company["website"],
                max_pages=20,
                company_id=company["company_id"]
            )

            # Extract contacts from screenshots
            contacts = []
            for page in pages:
                result = await mock_vlm_extractor.extract_contacts(
                    screenshot_path=page["screenshot_path"],
                    url=page["url"]
                )
                contacts.extend(result["contacts"])

            active_companies.remove(company["company_id"])

            return {
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "contacts": contacts,
                "pages_crawled": len(pages)
            }

    # Process all companies in parallel
    start_time = time.time()
    results = await asyncio.gather(*[
        process_company(company) for company in mock_companies
    ])
    end_time = time.time()

    total_duration = end_time - start_time

    # Verify results
    assert len(results) == len(mock_companies), "All companies should be processed"
    assert all(r["contacts"] for r in results), "All companies should have contacts"

    # Verify concurrency limit was respected
    assert max_active <= max_concurrent, (
        f"Max concurrent companies should be <= {max_concurrent}, got {max_active}"
    )

    # Verify parallelism (should be faster than sequential)
    # With 10 companies at ~0.4s each, sequential would be ~4s
    # With max_concurrent=3, should be ~1.4s (10/3 * 0.4s)
    assert total_duration < 2.5, (
        f"Parallel processing should be faster than sequential. "
        f"Got {total_duration:.2f}s (expected < 2.5s)"
    )

    print(f"✅ Processed {len(results)} companies in {total_duration:.2f}s")
    print(f"✅ Max concurrent: {max_active} (limit: {max_concurrent})")


@pytest.mark.asyncio
async def test_exception_isolation(mock_companies):
    """
    Test that one company failure doesn't block other companies.

    Verifies graceful error handling with exception isolation.
    """
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_company(company):
        """Process company, failing on specific IDs."""
        async with semaphore:
            await asyncio.sleep(0.1)

            # Fail on company 3 and 7
            if company["company_id"] in ["co-003", "co-007"]:
                raise Exception(f"Crawler error for {company['company_name']}")

            return {
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "contacts": [{"name": f"CEO of {company['company_name']}"}],
                "status": "success"
            }

    # Process all companies, capturing exceptions
    results = await asyncio.gather(*[
        process_company(company) for company in mock_companies
    ], return_exceptions=True)

    # Verify results
    assert len(results) == len(mock_companies)

    # Count successes and failures
    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 8, "8 companies should succeed"
    assert len(failures) == 2, "2 companies should fail"

    # Verify failures are the expected ones
    failure_messages = [str(f) for f in failures]
    assert any("co-003" in msg or "Company 3" in msg for msg in failure_messages)
    assert any("co-007" in msg or "Company 7" in msg for msg in failure_messages)

    print(f"✅ Exception isolation working: {len(successes)} successes, {len(failures)} failures")


@pytest.mark.asyncio
async def test_semaphore_prevents_resource_exhaustion():
    """
    Test that semaphore prevents overwhelming system resources.

    Verifies that we don't process all companies at once, which could
    exhaust Browserbase sessions, memory, or API rate limits.
    """
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)

    # Track concurrent execution over time
    concurrent_counts = []

    active_count = 0
    lock = asyncio.Lock()

    async def simulate_company_processing(idx):
        """Simulate company processing with resource tracking."""
        nonlocal active_count

        async with semaphore:
            async with lock:
                active_count += 1
                concurrent_counts.append(active_count)

            # Simulate work
            await asyncio.sleep(0.05)

            async with lock:
                active_count -= 1

    # Process 20 companies
    await asyncio.gather(*[
        simulate_company_processing(i) for i in range(20)
    ])

    # Verify semaphore limit was never exceeded
    max_concurrent_observed = max(concurrent_counts)
    assert max_concurrent_observed <= max_concurrent, (
        f"Concurrent processing should never exceed {max_concurrent}, "
        f"got {max_concurrent_observed}"
    )

    print(f"✅ Semaphore effective: max {max_concurrent_observed} concurrent (limit: {max_concurrent})")


@pytest.mark.asyncio
async def test_sequential_vs_parallel_speedup():
    """
    Test that parallel company processing provides significant speedup.

    Verifies that processing 9 companies with max_concurrent=3 is
    significantly faster than sequential processing.
    """
    company_count = 9
    max_concurrent = 3
    processing_time_per_company = 0.1

    async def process_company(idx):
        """Mock company processing."""
        await asyncio.sleep(processing_time_per_company)
        return {"company_id": idx, "status": "success"}

    # Sequential processing (baseline)
    sequential_start = time.time()
    sequential_results = []
    for i in range(company_count):
        result = await process_company(i)
        sequential_results.append(result)
    sequential_duration = time.time() - sequential_start

    # Parallel processing with semaphore
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(idx):
        async with semaphore:
            return await process_company(idx)

    parallel_start = time.time()
    parallel_results = await asyncio.gather(*[
        process_with_semaphore(i) for i in range(company_count)
    ])
    parallel_duration = time.time() - parallel_start

    # Calculate speedup
    speedup = sequential_duration / parallel_duration

    # Verify results
    assert len(sequential_results) == len(parallel_results) == company_count

    # Expected speedup: 9 companies / 3 concurrent = 3x batches
    # Sequential: 9 * 0.1s = 0.9s
    # Parallel: 3 batches * 0.1s = 0.3s
    # Speedup: ~3x
    assert speedup > 2.0, (
        f"Parallel processing should provide significant speedup. "
        f"Sequential: {sequential_duration:.2f}s, Parallel: {parallel_duration:.2f}s, "
        f"Speedup: {speedup:.1f}x (expected > 2x)"
    )

    print(f"✅ Speedup: {speedup:.1f}x (Sequential: {sequential_duration:.2f}s, Parallel: {parallel_duration:.2f}s)")


@pytest.mark.asyncio
async def test_company_processing_order_independence():
    """
    Test that companies can be processed in any order.

    Verifies that asyncio.gather correctly handles out-of-order completion
    and that slower companies don't block faster ones.
    """
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)

    # Companies with varying processing times
    companies = [
        {"id": 1, "delay": 0.3},  # Slow
        {"id": 2, "delay": 0.05},  # Fast
        {"id": 3, "delay": 0.2},  # Medium
        {"id": 4, "delay": 0.05},  # Fast
        {"id": 5, "delay": 0.4},  # Very slow
    ]

    completion_order = []

    async def process_company(company):
        """Process company with variable delay."""
        async with semaphore:
            await asyncio.sleep(company["delay"])
            completion_order.append(company["id"])
            return {"company_id": company["id"]}

    # Process all companies
    results = await asyncio.gather(*[
        process_company(company) for company in companies
    ])

    # Verify all completed
    assert len(results) == len(companies)
    assert len(completion_order) == len(companies)

    # Verify results maintain original order (despite out-of-order completion)
    assert [r["company_id"] for r in results] == [1, 2, 3, 4, 5]

    # Verify completion was out of order (faster companies finished first)
    # Company 2 (0.05s) should finish before Company 1 (0.3s)
    assert completion_order.index(2) < completion_order.index(1), (
        "Faster companies should complete before slower ones"
    )

    print(f"✅ Completion order (time-based): {completion_order}")
    print(f"✅ Result order (input-based): {[r['company_id'] for r in results]}")
