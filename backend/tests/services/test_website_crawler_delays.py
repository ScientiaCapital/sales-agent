"""
Tests for WebsiteCrawler delay configuration.

Verifies performance optimization: DELAY_BETWEEN_PAGES reduced from 5s to 2s.
"""

import os
import pytest


def test_delay_between_pages_default():
    """
    Test that DELAY_BETWEEN_PAGES defaults to 2.0 seconds.

    TDD: This test should FAIL initially (current value is 5.0),
    then PASS after we change the default in website_crawler.py.
    """
    # Import after test setup to get the actual configured value
    from backend.app.services.website_crawler import DELAY_BETWEEN_PAGES

    assert DELAY_BETWEEN_PAGES == 2.0, (
        f"Expected DELAY_BETWEEN_PAGES to be 2.0s, got {DELAY_BETWEEN_PAGES}s. "
        "Performance optimization requires reducing delay from 5s to 2s."
    )


def test_delay_between_pages_env_override():
    """
    Test that CRAWLER_PAGE_DELAY environment variable can override default.

    This ensures we can still configure delays for special cases without
    changing the code.
    """
    # Set env var temporarily
    original_value = os.getenv("CRAWLER_PAGE_DELAY")
    os.environ["CRAWLER_PAGE_DELAY"] = "3.5"

    try:
        # Force reload the module to pick up new env var
        import importlib
        from backend.app.services import website_crawler
        importlib.reload(website_crawler)

        assert website_crawler.DELAY_BETWEEN_PAGES == 3.5, (
            "CRAWLER_PAGE_DELAY env var should override default"
        )
    finally:
        # Restore original value
        if original_value is None:
            os.environ.pop("CRAWLER_PAGE_DELAY", None)
        else:
            os.environ["CRAWLER_PAGE_DELAY"] = original_value

        # Reload again to restore default
        import importlib
        from backend.app.services import website_crawler
        importlib.reload(website_crawler)


def test_delay_is_numeric():
    """
    Test that DELAY_BETWEEN_PAGES is a numeric type.

    Ensures the delay can be used in asyncio.sleep() calls.
    """
    from backend.app.services.website_crawler import DELAY_BETWEEN_PAGES

    assert isinstance(DELAY_BETWEEN_PAGES, (int, float)), (
        f"DELAY_BETWEEN_PAGES must be numeric, got {type(DELAY_BETWEEN_PAGES)}"
    )
    assert DELAY_BETWEEN_PAGES > 0, "Delay must be positive"
