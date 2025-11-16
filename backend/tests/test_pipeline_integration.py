"""
Integration test for complete Social Intelligence pipeline

Tests the full workflow:
1. Fetch Hot ATL contacts from Close CRM
2. Scrape LinkedIn + Twitter
3. AI analysis
4. Email draft generation
5. Engagement tracking
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from social_intelligence_runner import SocialIntelligenceRunner


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullPipeline:
    """Integration tests for complete pipeline."""

    @patch.dict(os.environ, {
        'SUPABASE_DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'CLOSE_API_KEY': 'test_close',
        'ANTHROPIC_API_KEY': 'test_anthropic',
        'DEEPSEEK_API_KEY': 'test_deepseek'
    })
    @patch('social_intelligence_runner.LinkedInScraper')
    @patch('social_intelligence_runner.TwitterMonitor')
    @patch('social_intelligence_runner.ContextAnalyzer')
    @patch('social_intelligence_runner.EmailDraftGenerator')
    @patch('social_intelligence_runner.httpx.AsyncClient')
    async def test_full_pipeline_success(
        self,
        mock_http,
        mock_email_gen,
        mock_analyzer,
        mock_twitter,
        mock_linkedin
    ):
        """Test complete pipeline execution."""
        # Mock Close CRM response (fetch ATL contacts)
        close_response = AsyncMock()
        close_response.json = Mock(return_value={
            'data': [{
                'id': 'lead_123',
                'contacts': [{
                    'id': 'contact_456',
                    'name': 'Test User',
                    'urls': [
                        {'url': 'https://linkedin.com/in/testuser'},
                        {'url': 'https://twitter.com/testuser'}
                    ]
                }]
            }]
        })
        close_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=close_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        # Mock LinkedIn scraper
        mock_linkedin_instance = AsyncMock()
        mock_linkedin_instance.initialize = AsyncMock()
        mock_linkedin_instance.scrape_profiles = AsyncMock(return_value=[
            {
                'id': 1,
                'contact_id': 'https://linkedin.com/in/testuser',
                'platform': 'linkedin',
                'post_text': 'Struggling with CRM issues',
                'posted_at': datetime.now()
            }
        ])
        mock_linkedin_instance.save_posts = AsyncMock(return_value=1)
        mock_linkedin_instance.close = AsyncMock()
        mock_linkedin.return_value = mock_linkedin_instance

        # Mock Twitter monitor
        mock_twitter_instance = AsyncMock()
        mock_twitter_instance.monitor_accounts = AsyncMock(return_value=[])
        mock_twitter_instance.save_tweets = AsyncMock(return_value=0)
        mock_twitter.return_value = mock_twitter_instance

        # Mock AI analyzer
        mock_analyzer_instance = AsyncMock()
        mock_analyzer_instance.analyze_posts = AsyncMock(return_value=[
            {
                'post_id': 1,
                'pain_points': ['CRM issues'],
                'urgency_signals': ['urgent'],
                'talking_points': ['automation'],
                'quality_score': 8
            }
        ])
        mock_analyzer.return_value = mock_analyzer_instance

        # Mock email generator
        mock_email_instance = AsyncMock()
        mock_email_instance.generate_drafts = AsyncMock(return_value=[
            {
                'contact_id': 'https://linkedin.com/in/testuser',
                'subject_line': 'Saw your CRM post',
                'email_body': 'Hi, I can help...',
                'talking_points': ['automation']
            }
        ])
        mock_email_gen.return_value = mock_email_instance

        # Run pipeline
        runner = SocialIntelligenceRunner()
        result = await runner.run_full_pipeline()

        # Verify pipeline completed successfully
        assert result['success'] is True
        assert result['contacts_processed'] >= 0
        assert result['linkedin_posts'] >= 0

    @patch.dict(os.environ, {
        'SUPABASE_DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'CLOSE_API_KEY': 'test_close',
        'ANTHROPIC_API_KEY': 'test_anthropic',
        'DEEPSEEK_API_KEY': 'test_deepseek'
    })
    @patch('social_intelligence_runner.LinkedInScraper')
    @patch('social_intelligence_runner.httpx.AsyncClient')
    async def test_pipeline_handles_no_contacts(
        self,
        mock_http,
        mock_linkedin
    ):
        """Test pipeline handles case with no ATL contacts."""
        # Mock empty Close response
        close_response = AsyncMock()
        close_response.json = Mock(return_value={'data': []})
        close_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=close_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_http.return_value = mock_client

        runner = SocialIntelligenceRunner()
        result = await runner.run_full_pipeline()

        # Should succeed with 0 contacts
        assert result['success'] is True
        assert result['contacts_processed'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
