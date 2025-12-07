"""
Tests for Slack /enrich command handler

Verifies:
- Form data parsing (application/x-www-form-urlencoded)
- 3-second response requirement
- Background task queueing
- Response format
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    with patch("app.api.slack_commands.run_dropin_enrichment") as mock:
        # Mock the .delay() method
        mock_task = MagicMock()
        mock_task.id = "test-task-123"
        mock.delay.return_value = mock_task
        yield mock


def test_slack_enrich_command_with_url(client: TestClient, mock_celery_task):
    """Test /enrich command with URL input."""
    response = client.post(
        "/api/v1/slack/commands/enrich",
        data={
            "command": "/enrich",
            "text": "https://acme-hvac.com",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "channel_id": "C123ABC",
            "channel_name": "sales",
            "team_id": "T123ABC",
            "response_url": "https://hooks.slack.com/commands/123/456/abc"
        }
    )

    # Should return 200 immediately
    assert response.status_code == 200

    # Check response format
    data = response.json()
    assert data["response_type"] == "in_channel"
    assert "Enriching" in data["text"]
    assert "https://acme-hvac.com" in data["text"]

    # Verify Celery task was queued
    mock_celery_task.delay.assert_called_once()
    call_kwargs = mock_celery_task.delay.call_args[1]
    assert call_kwargs["input"] == "https://acme-hvac.com"
    assert call_kwargs["input_type"] == "auto"
    assert call_kwargs["source"] == "slack"


def test_slack_enrich_command_with_company_name(client: TestClient, mock_celery_task):
    """Test /enrich command with company name."""
    response = client.post(
        "/api/v1/slack/commands/enrich",
        data={
            "command": "/enrich",
            "text": "Acme HVAC",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "channel_id": "C123ABC",
            "channel_name": "sales",
            "team_id": "T123ABC",
            "response_url": "https://hooks.slack.com/commands/123/456/abc"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "Acme HVAC" in data["text"]

    # Verify task was queued with correct input
    call_kwargs = mock_celery_task.delay.call_args[1]
    assert call_kwargs["input"] == "Acme HVAC"


def test_slack_enrich_command_with_close_id(client: TestClient, mock_celery_task):
    """Test /enrich command with Close lead ID."""
    response = client.post(
        "/api/v1/slack/commands/enrich",
        data={
            "command": "/enrich",
            "text": "lead_abc123",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "channel_id": "C123ABC",
            "channel_name": "sales",
            "team_id": "T123ABC",
            "response_url": "https://hooks.slack.com/commands/123/456/abc"
        }
    )

    assert response.status_code == 200
    call_kwargs = mock_celery_task.delay.call_args[1]
    assert call_kwargs["input"] == "lead_abc123"


def test_slack_enrich_command_empty_input(client: TestClient, mock_celery_task):
    """Test /enrich command with no input (should show usage)."""
    response = client.post(
        "/api/v1/slack/commands/enrich",
        data={
            "command": "/enrich",
            "text": "",  # Empty input
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "channel_id": "C123ABC",
            "channel_name": "sales",
            "team_id": "T123ABC",
            "response_url": "https://hooks.slack.com/commands/123/456/abc"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Should be ephemeral (only visible to user)
    assert data["response_type"] == "ephemeral"

    # Should show usage examples
    assert "Usage" in data["text"]
    assert "/enrich" in data["text"]
    assert "Examples" in data["text"]

    # Should NOT queue task
    mock_celery_task.delay.assert_not_called()


def test_slack_enrich_command_invalid_token(client: TestClient, mock_celery_task, monkeypatch):
    """Test /enrich command with invalid verification token."""
    # Set expected token in environment
    monkeypatch.setenv("SLACK_VERIFICATION_TOKEN", "valid_token_123")

    response = client.post(
        "/api/v1/slack/commands/enrich",
        data={
            "command": "/enrich",
            "text": "https://acme-hvac.com",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "channel_id": "C123ABC",
            "channel_name": "sales",
            "team_id": "T123ABC",
            "response_url": "https://hooks.slack.com/commands/123/456/abc",
            "token": "invalid_token_456"  # Wrong token
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Should be ephemeral
    assert data["response_type"] == "ephemeral"
    assert "Invalid" in data["text"]

    # Should NOT queue task
    mock_celery_task.delay.assert_not_called()


def test_slack_health_endpoint(client: TestClient):
    """Test Slack integration health check."""
    response = client.get("/api/v1/slack/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["integration"] == "slack"
    assert len(data["commands"]) > 0

    # Check /enrich command is documented
    enrich_cmd = data["commands"][0]
    assert enrich_cmd["command"] == "/enrich"
    assert "examples" in enrich_cmd


@pytest.mark.asyncio
async def test_post_result_to_slack_duplicate():
    """Test posting duplicate result to Slack."""
    from app.api.slack_commands import post_result_to_slack

    result = {
        "status": "success",
        "source": "slack",
        "result": {
            "exists_in_close": True,
            "existing_lead": {
                "company_name": "Acme HVAC",
                "close_url": "https://app.close.com/lead/lead_123/",
                "confidence": 95.5
            }
        }
    }

    # Mock httpx client
    with patch("app.api.slack_commands.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        # Call function
        await post_result_to_slack(
            response_url="https://hooks.slack.com/test",
            result=result
        )

        # Verify HTTP request was made
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check payload
        assert call_args[0][0] == "https://hooks.slack.com/test"
        json_data = call_args[1]["json"]
        assert json_data["response_type"] == "in_channel"
        assert "Already Exists" in json_data["text"]
        assert "Acme HVAC" in json_data["text"]
        assert "95.5%" in json_data["text"]


@pytest.mark.asyncio
async def test_post_result_to_slack_enriched():
    """Test posting enriched result to Slack."""
    from app.api.slack_commands import post_result_to_slack

    result = {
        "status": "success",
        "source": "slack",
        "result": {
            "exists_in_close": False,
            "company_name": "Acme HVAC",
            "domain": "acme-hvac.com",
            "icp_score": 85,
            "icp_tier": "PLATINUM",
            "priority": "HOT",
            "duration_ms": 2500
        }
    }

    with patch("app.api.slack_commands.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        await post_result_to_slack(
            response_url="https://hooks.slack.com/test",
            result=result
        )

        # Verify payload
        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        assert "Enriched Successfully" in json_data["text"]
        assert "Acme HVAC" in json_data["text"]
        assert "85/100" in json_data["text"]
        assert "PLATINUM" in json_data["text"]
        assert "🔥 HOT" in json_data["text"]


@pytest.mark.asyncio
async def test_post_result_to_slack_error():
    """Test posting error result to Slack."""
    from app.api.slack_commands import post_result_to_slack

    result = {
        "status": "error",
        "error": "Network timeout after 30s",
        "input": "https://acme-hvac.com"
    }

    with patch("app.api.slack_commands.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        await post_result_to_slack(
            response_url="https://hooks.slack.com/test",
            result=result
        )

        # Verify payload
        call_args = mock_post.call_args
        json_data = call_args[1]["json"]
        assert "Enrichment Failed" in json_data["text"]
        assert "Network timeout" in json_data["text"]
        assert "https://acme-hvac.com" in json_data["text"]
