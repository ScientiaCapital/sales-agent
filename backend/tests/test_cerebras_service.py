"""Unit tests for Cerebras service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import time

from app.services.cerebras import CerebrasService
from app.core.exceptions import CerebrasAPIError


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for Cerebras."""
    with patch('app.services.cerebras.OpenAI') as mock_client:
        yield mock_client


@pytest.fixture
def cerebras_service(mock_openai_client):
    """Create CerebrasService instance with mocked OpenAI client."""
    with patch.dict('os.environ', {'CEREBRAS_API_KEY': 'test-key'}):
        service = CerebrasService()
        return service


class TestCerebrasService:
    """Test suite for CerebrasService."""

    def test_init_success(self, mock_openai_client):
        """Test successful initialization with API key."""
        with patch.dict('os.environ', {'CEREBRAS_API_KEY': 'test-key'}):
            service = CerebrasService()
            assert service.api_key == 'test-key'
            assert service.api_base == "https://api.cerebras.ai/v1"
            assert service.default_model == "llama3.1-8b"

    def test_init_missing_api_key(self, mock_openai_client):
        """Test initialization fails without API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="CEREBRAS_API_KEY environment variable not set"):
                CerebrasService()

    def test_init_custom_config(self, mock_openai_client):
        """Test initialization with custom configuration."""
        with patch.dict('os.environ', {
            'CEREBRAS_API_KEY': 'custom-key',
            'CEREBRAS_API_BASE': 'https://custom.api.com',
            'CEREBRAS_DEFAULT_MODEL': 'llama3.1-70b'
        }):
            service = CerebrasService()
            assert service.api_key == 'custom-key'
            assert service.api_base == 'https://custom.api.com'
            assert service.default_model == 'llama3.1-70b'

    def test_qualify_lead_success(self, cerebras_service):
        """Test successful lead qualification."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 85,
            "reasoning": "High-quality lead with strong company fit and decision-maker contact."
        })

        cerebras_service.client.chat.completions.create = Mock(return_value=mock_response)

        # Execute
        score, reasoning, latency = cerebras_service.qualify_lead(
            company_name="Acme Corp",
            company_website="https://acme.com",
            company_size="500-1000",
            industry="SaaS",
            contact_name="John Doe",
            contact_title="CTO"
        )

        # Assertions
        assert score == 85.0
        assert "High-quality lead" in reasoning
        assert isinstance(latency, int)
        assert latency > 0

    def test_qualify_lead_minimal_data(self, cerebras_service):
        """Test lead qualification with minimal data."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 50,
            "reasoning": "Limited information available for qualification."
        })

        cerebras_service.client.chat.completions.create = Mock(return_value=mock_response)

        score, reasoning, latency = cerebras_service.qualify_lead(
            company_name="Unknown Corp"
        )

        assert 0 <= score <= 100
        assert isinstance(reasoning, str)
        assert latency > 0

    def test_qualify_lead_invalid_json(self, cerebras_service):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is not JSON"

        cerebras_service.client.chat.completions.create = Mock(return_value=mock_response)

        score, reasoning, latency = cerebras_service.qualify_lead(
            company_name="Test Corp"
        )

        # Should fallback to medium score
        assert score == 50.0
        assert "Unable to parse response" in reasoning
        assert latency > 0

    def test_qualify_lead_out_of_range_score(self, cerebras_service):
        """Test handling of score outside valid range."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 150,  # Invalid score
            "reasoning": "Test reasoning"
        })

        cerebras_service.client.chat.completions.create = Mock(return_value=mock_response)

        score, reasoning, latency = cerebras_service.qualify_lead(
            company_name="Test Corp"
        )

        # Should fallback to medium score
        assert score == 50.0
        assert "Invalid response format" in reasoning

    def test_qualify_lead_missing_fields(self, cerebras_service):
        """Test handling of response missing required fields."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 75
            # Missing 'reasoning' field
        })

        cerebras_service.client.chat.completions.create = Mock(return_value=mock_response)

        score, reasoning, latency = cerebras_service.qualify_lead(
            company_name="Test Corp"
        )

        assert score == 50.0
        assert "Invalid response format" in reasoning

    def test_qualify_lead_api_error(self, cerebras_service):
        """Test handling of API errors."""
        cerebras_service.client.chat.completions.create = Mock(
            side_effect=Exception("API connection failed")
        )

        with pytest.raises(CerebrasAPIError) as exc_info:
            cerebras_service.qualify_lead(company_name="Test Corp")

        assert exc_info.value.status_code == 500
        assert "Lead qualification service unavailable" in exc_info.value.message

    def test_calculate_cost_default_model(self, cerebras_service):
        """Test cost calculation with default model."""
        cost = cerebras_service.calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500
        )

        assert cost["input_cost_usd"] == 0.0001  # 1000/1M * 0.10
        assert cost["output_cost_usd"] == 0.00005  # 500/1M * 0.10
        assert cost["total_cost_usd"] == 0.00015

    def test_calculate_cost_70b_model(self, cerebras_service):
        """Test cost calculation with 70B model."""
        cost = cerebras_service.calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="llama3.1-70b"
        )

        assert cost["input_cost_usd"] == 0.0006  # 1000/1M * 0.60
        assert cost["output_cost_usd"] == 0.0003  # 500/1M * 0.60
        assert cost["total_cost_usd"] == 0.0009

    def test_calculate_cost_unknown_model(self, cerebras_service):
        """Test cost calculation defaults for unknown model."""
        cost = cerebras_service.calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="unknown-model"
        )

        # Should use default pricing
        assert cost["input_cost_usd"] == 0.0001
        assert cost["output_cost_usd"] == 0.00005
        assert cost["total_cost_usd"] == 0.00015

    def test_qualify_lead_latency_tracking(self, cerebras_service):
        """Test that latency is accurately tracked."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 75,
            "reasoning": "Test reasoning"
        })

        # Simulate API delay
        def mock_create(*args, **kwargs):
            time.sleep(0.1)  # 100ms delay
            return mock_response

        cerebras_service.client.chat.completions.create = mock_create

        _, _, latency = cerebras_service.qualify_lead(company_name="Test Corp")

        # Should be around 100ms (allow some margin)
        assert 90 <= latency <= 200

    def test_qualify_lead_temperature_setting(self, cerebras_service):
        """Test that temperature is set correctly for consistent scoring."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "score": 75,
            "reasoning": "Test"
        })

        mock_create = Mock(return_value=mock_response)
        cerebras_service.client.chat.completions.create = mock_create

        cerebras_service.qualify_lead(company_name="Test Corp")

        # Verify temperature was set to 0.3
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs['temperature'] == 0.3
        assert call_kwargs['max_tokens'] == 200
        assert call_kwargs['model'] == 'llama3.1-8b'


class TestCerebrasServiceIntegration:
    """Integration tests for CerebrasService (require actual API key)."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Integration tests require --run-integration flag"
    )
    def test_real_api_call(self):
        """Test actual API call to Cerebras (requires real API key)."""
        import os
        if not os.getenv("CEREBRAS_API_KEY"):
            pytest.skip("CEREBRAS_API_KEY not set")

        service = CerebrasService()
        score, reasoning, latency = service.qualify_lead(
            company_name="Anthropic",
            industry="AI/ML",
            company_size="50-200",
            contact_title="CEO"
        )

        assert 0 <= score <= 100
        assert len(reasoning) > 20
        assert latency > 0
        print(f"\n✓ Real API call completed in {latency}ms")
        print(f"  Score: {score}")
        print(f"  Reasoning: {reasoning}")


def pytest_configure(config):
    """Add custom command line option for integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def pytest_addoption(parser):
    """Add command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require real API calls"
    )
