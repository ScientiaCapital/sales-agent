"""
Unit tests for TwitterMonitor service
"""

# Skip tests - requires langchain_core which is an optional dependency
import pytest



import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.services.social.twitter_monitor import TwitterMonitor


@pytest.mark.unit
class TestTwitterMonitorInitialization:
    """Test monitor initialization."""

    def test_initialization(self, mock_database_url):
        """Test monitor initializes correctly."""
        monitor = TwitterMonitor("test_bearer_token", mock_database_url)

        assert monitor.database_url == mock_database_url
        assert monitor.client is not None


@pytest.mark.unit
@pytest.mark.asyncio
class TestTwitterMonitoring:
    """Test Twitter account monitoring."""

    @patch('app.services.social.twitter_monitor.tweepy.Client')
    async def test_monitor_single_account_success(
        self,
        mock_tweepy_client,
        mock_database_url
    ):
        """Test successful account monitoring."""
        # Setup mocks
        mock_client = Mock()

        # Mock user lookup
        user_data = Mock()
        user_data.id = '123456789'
        user_response = Mock()
        user_response.data = user_data
        mock_client.get_user = Mock(return_value=user_response)

        # Mock tweets
        tweet1 = Mock()
        tweet1.id = '1111'
        tweet1.text = "Test tweet"
        tweet1.created_at = datetime.now()

        tweets_response = Mock()
        tweets_response.data = [tweet1]
        mock_client.get_users_tweets = Mock(return_value=tweets_response)

        mock_tweepy_client.return_value = mock_client

        monitor = TwitterMonitor("test_token", mock_database_url)
        monitor.client = mock_client

        # Monitor account
        tweets = await monitor._get_user_tweets("testuser")

        # Verify
        assert len(tweets) > 0
        assert tweets[0]['platform'] == 'twitter'
        mock_client.get_user.assert_called_once()

    @patch('app.services.social.twitter_monitor.tweepy.Client')
    async def test_monitor_private_account(
        self,
        mock_tweepy_client,
        mock_database_url
    ):
        """Test handling of private accounts."""
        import tweepy

        mock_client = Mock()
        mock_client.get_user = Mock(side_effect=tweepy.errors.Forbidden("Private account"))

        mock_tweepy_client.return_value = mock_client

        monitor = TwitterMonitor("test_token", mock_database_url)
        monitor.client = mock_client

        # Should return empty list, not raise
        tweets = await monitor._get_user_tweets("private_user")

        assert tweets == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestTwitterDataPersistence:
    """Test tweet saving."""

    @patch('app.services.social.twitter_monitor.psycopg.AsyncConnection.connect')
    async def test_save_tweets(self, mock_db_connect, mock_database_url):
        """Test saving tweets to database."""
        # Mock database
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        monitor = TwitterMonitor("test_token", mock_database_url)

        tweets = [
            {
                'contact_id': 'testuser',
                'platform': 'twitter',
                'post_text': 'Test tweet',
                'post_url': 'https://twitter.com/testuser/status/123',
                'posted_at': datetime.now(),
                'scraped_at': datetime.now()
            }
        ]

        saved_count = await monitor.save_tweets(tweets)

        assert saved_count == 1
        mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
