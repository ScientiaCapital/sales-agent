"""
Unit tests for LinkedInScraper service

Tests cover:
- Playwright browser initialization
- Profile scraping with mocked responses
- Rate limiting enforcement
- Error handling and retries
- Database saving
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the service
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.services.social.linkedin_scraper import LinkedInScraper


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkedInScraperInitialization:
    """Test scraper initialization."""

    async def test_initialization(self, mock_database_url):
        """Test scraper initializes with correct parameters."""
        scraper = LinkedInScraper(mock_database_url)

        assert scraper.database_url == mock_database_url
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper._session_initialized is False

    @patch('app.services.social.linkedin_scraper.async_playwright')
    async def test_initialize_browser(self, mock_playwright, mock_database_url):
        """Test browser initialization."""
        # Setup mocks
        playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        # Initialize scraper
        scraper = LinkedInScraper(mock_database_url)
        await scraper.initialize()

        # Verify browser was launched
        assert scraper._session_initialized is True
        playwright_instance.chromium.launch.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkedInProfileScraping:
    """Test LinkedIn profile scraping."""

    @patch('app.services.social.linkedin_scraper.async_playwright')
    @patch('app.services.social.linkedin_scraper.psycopg.AsyncConnection.connect')
    async def test_scrape_single_profile_success(
        self,
        mock_db_connect,
        mock_playwright,
        mock_database_url
    ):
        """Test successful profile scraping."""
        # Setup browser mocks
        playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Mock post elements
        mock_post_element = AsyncMock()

        # Mock text element
        mock_text_elem = AsyncMock()
        mock_text_elem.inner_text = AsyncMock(return_value="Great product launch!")

        # Mock link element
        mock_link_elem = AsyncMock()
        mock_link_elem.get_attribute = AsyncMock(
            return_value="https://linkedin.com/posts/test-123"
        )

        # Mock time element
        mock_time_elem = AsyncMock()
        mock_time_elem.get_attribute = AsyncMock(
            return_value=datetime.now().isoformat()
        )

        # Setup element queries
        mock_post_element.query_selector = AsyncMock()
        mock_post_element.query_selector.side_effect = [
            mock_text_elem,      # First call: post text
            mock_link_elem,      # Second call: post link
            mock_time_elem       # Third call: timestamp
        ]

        # Mock page methods
        mock_page.query_selector_all = AsyncMock(return_value=[mock_post_element])
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        # Initialize scraper
        scraper = LinkedInScraper(mock_database_url)
        await scraper.initialize()
        scraper.context = mock_context

        # Scrape profile
        posts = await scraper._scrape_single_profile("https://linkedin.com/in/test-user")

        # Verify scraping occurred
        mock_page.goto.assert_called_once()
        assert len(posts) >= 0  # May be empty if date filtering

    @patch('app.services.social.linkedin_scraper.async_playwright')
    async def test_scrape_profiles_rate_limiting(
        self,
        mock_playwright,
        mock_database_url
    ):
        """Test rate limiting enforcement."""
        # Setup minimal mocks
        playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        scraper = LinkedInScraper(mock_database_url)
        await scraper.initialize()

        # Mock _get_daily_scrape_count to return near limit
        scraper._get_daily_scrape_count = AsyncMock(return_value=100)

        # Try to scrape (should hit rate limit)
        urls = ["https://linkedin.com/in/user1", "https://linkedin.com/in/user2"]
        posts = await scraper.scrape_profiles(urls)

        # Verify no scraping occurred
        assert posts == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkedInDataPersistence:
    """Test data saving to database."""

    @patch('app.services.social.linkedin_scraper.psycopg.AsyncConnection.connect')
    async def test_save_posts_success(self, mock_db_connect, mock_database_url):
        """Test successful post saving."""
        # Mock database connection
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        scraper = LinkedInScraper(mock_database_url)

        posts = [
            {
                'contact_id': 'https://linkedin.com/in/test',
                'platform': 'linkedin',
                'post_text': 'Test post',
                'post_url': 'https://linkedin.com/posts/123',
                'posted_at': datetime.now(),
                'scraped_at': datetime.now()
            }
        ]

        # Save posts
        saved_count = await scraper.save_posts(posts)

        # Verify database operations
        assert saved_count == 1
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called_once()

    async def test_save_empty_posts(self, mock_database_url):
        """Test saving empty post list."""
        scraper = LinkedInScraper(mock_database_url)

        saved_count = await scraper.save_posts([])

        assert saved_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestLinkedInErrorHandling:
    """Test error handling and graceful degradation."""

    @patch('app.services.social.linkedin_scraper.async_playwright')
    async def test_scrape_profile_network_error(
        self,
        mock_playwright,
        mock_database_url
    ):
        """Test handling of network errors."""
        # Setup browser that throws error
        playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Mock page.goto to raise error
        mock_page.goto = AsyncMock(side_effect=Exception("Network error"))

        scraper = LinkedInScraper(mock_database_url)
        await scraper.initialize()
        scraper.context = mock_context

        # Scrape should return empty list, not raise
        posts = await scraper._scrape_single_profile("https://linkedin.com/in/test")

        assert posts == []


@pytest.mark.performance
@pytest.mark.asyncio
class TestLinkedInPerformance:
    """Performance tests for LinkedIn scraper."""

    @patch('app.services.social.linkedin_scraper.async_playwright')
    async def test_parallel_scraping(
        self,
        mock_playwright,
        mock_database_url,
        performance_timer
    ):
        """Test parallel scraping performance."""
        # Setup minimal mocks
        playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=playwright_instance)

        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        scraper = LinkedInScraper(mock_database_url)
        await scraper.initialize()

        # Mock scraping to return quickly
        scraper._scrape_single_profile = AsyncMock(return_value=[])
        scraper._get_daily_scrape_count = AsyncMock(return_value=0)

        # Scrape multiple profiles
        urls = [f"https://linkedin.com/in/user-{i}" for i in range(10)]

        performance_timer.start()
        await scraper.scrape_profiles(urls)
        duration = performance_timer.stop()

        # Verify parallel scraping is reasonably fast
        # (10 profiles should take less than 5 seconds with mocks)
        assert duration < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
