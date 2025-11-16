"""
Unit tests for ContextAnalyzer service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.services.social.context_analyzer import ContextAnalyzer


@pytest.mark.unit
class TestContextAnalyzerInitialization:
    """Test analyzer initialization."""

    def test_initialization(self, mock_database_url):
        """Test analyzer initializes with API keys."""
        analyzer = ContextAnalyzer(
            "test_deepseek_key",
            "test_anthropic_key",
            mock_database_url
        )

        assert analyzer.deepseek_key == "test_deepseek_key"
        assert analyzer.anthropic_key == "test_anthropic_key"
        assert analyzer.database_url == mock_database_url


@pytest.mark.unit
@pytest.mark.asyncio
class TestModelSelection:
    """Test intelligent model tiering."""

    @patch('app.services.social.context_analyzer.httpx.AsyncClient')
    @patch('app.services.social.context_analyzer.psycopg.AsyncConnection.connect')
    async def test_simple_post_uses_deepseek(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test simple posts use DeepSeek."""
        # Mock database to return simple post
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                'id': 1,
                'contact_id': 'test',
                'platform': 'linkedin',
                'post_text': 'Short post!',  # <200 chars
                'post_url': 'https://test.com',
                'posted_at': datetime.now()
            }
        ])

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value={
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'pain_points': ['test'],
                        'urgency_signals': [],
                        'talking_points': ['test'],
                        'quality_score': 5
                    })
                }
            }],
            'usage': {'total_tokens': 100}
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        analyzer = ContextAnalyzer("test_ds", "test_anthrop", mock_database_url)

        # Analyze posts
        results = await analyzer.analyze_posts([1])

        # Verify DeepSeek was used (not Claude)
        assert len(results) > 0
        assert results[0]['model_used'] == 'deepseek'

    @patch('app.services.social.context_analyzer.httpx.AsyncClient')
    @patch('app.services.social.context_analyzer.psycopg.AsyncConnection.connect')
    async def test_complex_post_uses_claude(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test complex posts use Claude."""
        # Mock database with long post
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                'id': 1,
                'contact_id': 'test',
                'platform': 'linkedin',
                'post_text': 'This is a much longer post with complex content ' * 10,  # >200 chars
                'post_url': 'https://test.com',
                'posted_at': datetime.now()
            }
        ])

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value={
            'content': [{
                'text': json.dumps({
                    'pain_points': ['complex issue'],
                    'urgency_signals': ['ASAP'],
                    'talking_points': ['solution'],
                    'quality_score': 9
                })
            }],
            'usage': {'input_tokens': 200}
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        analyzer = ContextAnalyzer("test_ds", "test_anthrop", mock_database_url)

        results = await analyzer.analyze_posts([1])

        assert len(results) > 0
        assert results[0]['model_used'] == 'claude'


@pytest.mark.unit
@pytest.mark.asyncio
class TestAnalysisOutput:
    """Test analysis output structure."""

    @patch('app.services.social.context_analyzer.httpx.AsyncClient')
    @patch('app.services.social.context_analyzer.psycopg.AsyncConnection.connect')
    async def test_analysis_output_format(
        self,
        mock_db_connect,
        mock_http,
        mock_database_url
    ):
        """Test analysis output has correct structure."""
        # Mock database
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                'id': 1,
                'contact_id': 'test',
                'platform': 'linkedin',
                'post_text': 'Test post',
                'post_url': 'https://test.com',
                'posted_at': datetime.now()
            }
        ])

        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_db_connect.return_value = mock_conn

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value={
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'pain_points': ['manual work', 'slow process'],
                        'urgency_signals': ['urgent', 'ASAP'],
                        'talking_points': ['automation', 'efficiency'],
                        'quality_score': 8
                    })
                }
            }],
            'usage': {'total_tokens': 100}
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        analyzer = ContextAnalyzer("test_ds", "test_anthrop", mock_database_url)

        results = await analyzer.analyze_posts([1])

        # Verify output format
        assert len(results) > 0
        result = results[0]
        assert 'pain_points' in result
        assert 'urgency_signals' in result
        assert 'talking_points' in result
        assert 'quality_score' in result
        assert isinstance(result['pain_points'], list)
        assert isinstance(result['quality_score'], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
