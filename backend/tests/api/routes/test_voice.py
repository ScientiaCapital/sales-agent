import pytest
import os
# Set env vars before any app imports to prevent errors
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test_db")
os.environ.setdefault("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def test_app():
    """Create a minimal test app with just the voice router."""
    from app.api.routes.voice import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)


def test_twilio_webhook_endpoint_exists(test_client):
    """Twilio webhook should accept POST."""
    response = test_client.post("/api/v1/voice/twilio-webhook", data={
        "CallSid": "CA123",
        "From": "+15551234567",
        "To": "+15559876543",
    })

    # Should return TwiML
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "").lower()


@patch("app.services.calling.gates.pre_call.PreCallGate")
@patch("app.services.calling.gates.post_call.PostCallGate")
def test_slack_callback_endpoint_exists(mock_post_gate, mock_pre_gate, test_client):
    """Slack callback should accept POST."""
    # Mock the gate instances
    mock_pre_instance = MagicMock()
    mock_post_instance = MagicMock()
    mock_pre_gate.return_value = mock_pre_instance
    mock_post_gate.return_value = mock_post_instance

    response = test_client.post("/api/v1/voice/slack-callback", json={
        "type": "block_actions",
        "actions": [{"action_id": "approve_call_123"}],
        "user": {"id": "U123", "name": "tim"},
    })

    assert response.status_code == 200
