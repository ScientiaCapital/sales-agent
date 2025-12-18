"""
Unit tests for EngagementTracker service
"""

# Skip tests - requires langchain_core which is an optional dependency
import pytest



import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.services.social.engagement_tracker import EngagementTracker


@pytest.mark.unit
class TestEngagementTrackerInitialization:
    """Test tracker initialization."""

    def test_initialization(self, mock_database_url):
        """Test tracker initializes correctly."""
        tracker = EngagementTracker("test_close_key", mock_database_url)

        assert tracker.close_key == "test_close_key"
        assert tracker.database_url == mock_database_url
        assert tracker.HIGH_INTENT_THRESHOLD == 3


@pytest.mark.unit
@pytest.mark.asyncio
class TestEngagementChecking:
    """Test email engagement checking."""

    @patch('app.services.social.engagement_tracker.httpx.AsyncClient')
    @patch('app.services.social.engagement_tracker.psycopg.AsyncConnection.connect')
    async def test_check_engagement_high_intent(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test high-intent contact detection (3+ opens)."""
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

        # Mock HTTP responses
        # 1. Fetch sent emails
        emails_response = AsyncMock()
        emails_response.json = Mock(return_value={
            'data': [{
                'id': 'email_123',
                'contact_id': 'contact_456',
                'lead_id': 'lead_789',
                'subject': 'Test',
                'date_sent': datetime.now().isoformat()
            }]
        })
        emails_response.raise_for_status = Mock()

        # 2. Fetch email opens (3 opens = high intent!)
        opens_response = AsyncMock()
        opens_response.json = Mock(return_value={
            'opens': [
                {'date': datetime.now().isoformat()},
                {'date': (datetime.now() - timedelta(hours=12)).isoformat()},
                {'date': (datetime.now() - timedelta(hours=24)).isoformat()}
            ]
        })
        opens_response.raise_for_status = Mock()

        # 3. Update contact (set high intent flag)
        update_response = AsyncMock()
        update_response.status_code = 200
        update_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[emails_response, opens_response])
        mock_client.put = AsyncMock(return_value=update_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        tracker = EngagementTracker("test_close", mock_database_url)

        summary = await tracker.check_engagement()

        # Verify high-intent contact was flagged
        assert summary['total_checked'] == 1
        assert summary['high_intent_count'] == 1
        assert len(summary['updated_contacts']) == 1

    @patch('app.services.social.engagement_tracker.httpx.AsyncClient')
    @patch('app.services.social.engagement_tracker.psycopg.AsyncConnection.connect')
    async def test_check_engagement_low_opens(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test contacts with <3 opens are NOT flagged."""
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

        # Mock HTTP - only 1 open (not high intent)
        emails_response = AsyncMock()
        emails_response.json = Mock(return_value={
            'data': [{
                'id': 'email_123',
                'contact_id': 'contact_456',
                'subject': 'Test'
            }]
        })
        emails_response.raise_for_status = Mock()

        opens_response = AsyncMock()
        opens_response.json = Mock(return_value={
            'opens': [{'date': datetime.now().isoformat()}]  # Only 1 open
        })
        opens_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[emails_response, opens_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        tracker = EngagementTracker("test_close", mock_database_url)

        summary = await tracker.check_engagement()

        # Verify NO high-intent contacts
        assert summary['high_intent_count'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
