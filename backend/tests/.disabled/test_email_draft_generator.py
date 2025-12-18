"""
Unit tests for EmailDraftGenerator service
"""

# Skip tests - requires langchain_core which is an optional dependency
import pytest



import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import json
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.services.social.email_draft_generator import EmailDraftGenerator


@pytest.mark.unit
class TestEmailDraftGeneratorInitialization:
    """Test generator initialization."""

    def test_initialization(self, mock_database_url):
        """Test generator initializes correctly."""
        generator = EmailDraftGenerator(
            "test_anthropic",
            "test_close",
            mock_database_url
        )

        assert generator.anthropic_key == "test_anthropic"
        assert generator.close_key == "test_close"
        assert generator.database_url == mock_database_url


@pytest.mark.unit
@pytest.mark.asyncio
class TestEmailGeneration:
    """Test email draft generation."""

    @patch('app.services.social.email_draft_generator.httpx.AsyncClient')
    @patch('app.services.social.email_draft_generator.psycopg.AsyncConnection.connect')
    async def test_generate_draft_success(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test successful email generation."""
        # Mock database with posts
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                'contact_id': 'test@linkedin.com',
                'posts': [
                    {
                        'post_text': 'Struggling with manual workflows',
                        'pain_points': ['manual work'],
                        'urgency_signals': ['ASAP'],
                        'talking_points': ['automation'],
                        'quality_score': 8
                    }
                ]
            }
        ])

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        # Mock Claude response
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value={
            'content': [{
                'text': json.dumps({
                    'subject': 'Saw your post about workflows',
                    'body': 'Hi, I noticed your post...',
                    'talking_points': ['automation', 'ROI']
                })
            }]
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        generator = EmailDraftGenerator("test_anthrop", "test_close", mock_database_url)

        drafts = await generator.generate_drafts(['test@linkedin.com'])

        assert len(drafts) > 0
        assert 'subject_line' in drafts[0]
        assert 'email_body' in drafts[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
