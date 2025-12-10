"""
Integration tests for Voice API endpoints.

Tests Twilio webhook integration for voice calling:
- POST /voice/incoming - Handle incoming calls with TwiML
- POST /voice/outbound - Initiate outbound calls
- POST /voice/status - Call status callbacks

Uses TDD approach with mocked Twilio client and database.
"""

import os
# Set DATABASE_URL before importing any app modules to prevent import errors
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test_db")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


# ========== Fixtures ==========

@pytest.fixture
def test_client():
    """Create a test client with voice routes."""
    from app.api.voice_routes import router

    app = FastAPI()
    app.include_router(router)

    return TestClient(app)


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio REST client."""
    mock_client = MagicMock()

    # Mock calls.create() response
    mock_call = MagicMock()
    mock_call.sid = "CA" + "1234567890abcdef" * 2
    mock_call.status = "queued"
    mock_call.direction = "outbound-api"
    mock_call.to = "+15551234567"
    mock_call.from_ = "+15559876543"

    mock_client.calls.create.return_value = mock_call

    return mock_client


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()
    return mock_session


@pytest.fixture
def sample_incoming_webhook_data():
    """Sample Twilio incoming call webhook data."""
    return {
        "CallSid": "CAtestcallsid00000000000000000000",
        "AccountSid": "ACtestaccountsid000000000000000000",
        "From": "+15551234567",
        "To": "+15559876543",
        "CallStatus": "ringing",
        "Direction": "inbound",
        "CallerName": "",
        "FromCity": "SAN FRANCISCO",
        "FromState": "CA",
        "FromCountry": "US",
        "ToCity": "NEW YORK",
        "ToState": "NY",
        "ToCountry": "US"
    }


@pytest.fixture
def sample_status_callback_data():
    """Sample Twilio status callback data."""
    return {
        "CallSid": "CAtestcallsid00000000000000000000",
        "AccountSid": "ACtestaccountsid000000000000000000",
        "CallStatus": "completed",
        "CallDuration": "45",
        "Direction": "outbound-api",
        "From": "+15559876543",
        "To": "+15551234567",
        "RecordingUrl": "",
        "RecordingSid": "",
        "RecordingDuration": "",
        "Timestamp": "Mon, 09 Dec 2024 12:34:56 +0000"
    }


# ========== Router Configuration Tests ==========

class TestRouterConfiguration:
    """Test voice router exists and is properly configured."""

    def test_router_prefix_and_tags(self):
        """Verify router has correct prefix and tags."""
        from app.api.voice_routes import router

        assert router.prefix == "/voice"
        assert "voice" in router.tags

    def test_incoming_endpoint_exists(self, test_client):
        """Verify /voice/incoming endpoint exists."""
        # Should return 422 without form data, not 404
        response = test_client.post("/voice/incoming")
        assert response.status_code != 404

    def test_outbound_endpoint_exists(self, test_client):
        """Verify /voice/outbound endpoint exists."""
        response = test_client.post("/voice/outbound", json={"to": "+15551234567"})
        assert response.status_code != 404

    def test_status_endpoint_exists(self, test_client):
        """Verify /voice/status endpoint exists."""
        response = test_client.post("/voice/status")
        assert response.status_code != 404


# ========== Incoming Call Tests ==========

class TestIncomingCallEndpoint:
    """Test POST /voice/incoming endpoint."""

    def test_incoming_call_accepts_form_data(self, test_client, sample_incoming_webhook_data):
        """Test incoming call accepts Twilio form-encoded webhook."""
        response = test_client.post(
            "/voice/incoming",
            data=sample_incoming_webhook_data
        )
        assert response.status_code == 200

    def test_incoming_call_returns_twiml(self, test_client, sample_incoming_webhook_data):
        """Test incoming call returns valid TwiML response."""
        response = test_client.post(
            "/voice/incoming",
            data=sample_incoming_webhook_data
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"

        # Verify TwiML structure
        xml_content = response.text
        assert "<?xml version" in xml_content
        assert "<Response>" in xml_content
        assert "</Response>" in xml_content

    @patch("app.api.voice_routes.get_db_session")
    def test_incoming_call_includes_greeting(self, mock_get_db, test_client,
                                             sample_incoming_webhook_data, mock_db_session):
        """Test TwiML includes greeting message."""
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/incoming",
            data=sample_incoming_webhook_data
        )
        xml_content = response.text
        # Check for proper greeting (not error message)
        # TwiML contains: "Thank you for calling. Connecting you to our AI sales agent."
        assert "Thank you" in xml_content or "Hello" in xml_content or "Welcome" in xml_content

    @patch("app.api.voice_routes.get_db_session")
    def test_incoming_call_connects_to_websocket(self, mock_get_db, test_client,
                                                 sample_incoming_webhook_data, mock_db_session):
        """Test TwiML includes WebSocket stream connection."""
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/incoming",
            data=sample_incoming_webhook_data
        )
        xml_content = response.text
        assert "<Connect>" in xml_content or "<Stream>" in xml_content

    @patch("app.api.voice_routes.get_db_session")
    def test_incoming_call_logs_session(self, mock_get_db, test_client,
                                        sample_incoming_webhook_data, mock_db_session):
        """Test incoming call creates voice_session log in database."""
        # Use MagicMock as context manager
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_db_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db.return_value = mock_context

        response = test_client.post(
            "/voice/incoming",
            data=sample_incoming_webhook_data
        )
        assert response.status_code == 200

        # Verify database was accessed (context manager entered)
        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once()

    def test_incoming_call_requires_call_sid(self, test_client):
        """Test incoming call requires CallSid parameter."""
        response = test_client.post(
            "/voice/incoming",
            data={"From": "+15551234567"}
        )
        assert response.status_code in [400, 422]

    def test_incoming_call_requires_from_number(self, test_client):
        """Test incoming call requires From parameter."""
        response = test_client.post(
            "/voice/incoming",
            data={"CallSid": "CA123"}
        )
        assert response.status_code in [400, 422]


# ========== Outbound Call Tests ==========

class TestOutboundCallEndpoint:
    """Test POST /voice/outbound endpoint."""

    @patch("app.api.voice_routes.get_db_session")
    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_creates_call(self, mock_get_twilio, mock_get_db,
                                        test_client, mock_twilio_client, mock_db_session):
        """Test outbound call creates Twilio call."""
        mock_get_twilio.return_value = mock_twilio_client
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567", "lead_id": "lead_123"}
        )
        assert response.status_code == 200

        # Verify Twilio client was called
        mock_twilio_client.calls.create.assert_called_once()

    @patch("app.api.voice_routes.get_db_session")
    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_returns_call_sid(self, mock_get_twilio, mock_get_db,
                                            test_client, mock_twilio_client, mock_db_session):
        """Test outbound call returns call_sid."""
        mock_get_twilio.return_value = mock_twilio_client
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567"}
        )
        assert response.status_code == 200
        data = response.json()

        assert "call_sid" in data
        assert data["call_sid"].startswith("CA")
        assert "status" in data

    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_validates_phone_format(self, mock_get_twilio, test_client, mock_twilio_client):
        """Test outbound call validates E.164 phone format."""
        mock_get_twilio.return_value = mock_twilio_client

        # Invalid phone formats
        invalid_phones = ["5551234567", "555-123-4567", "invalid"]

        for phone in invalid_phones:
            response = test_client.post(
                "/voice/outbound",
                json={"to": phone}
            )
            assert response.status_code in [400, 422], f"Failed for phone: {phone}"

    @patch("app.api.voice_routes.get_db_session")
    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_logs_session(self, mock_get_twilio, mock_get_db,
                                        test_client, mock_twilio_client, mock_db_session):
        """Test outbound call creates voice_session log."""
        mock_get_twilio.return_value = mock_twilio_client
        # Use MagicMock as context manager
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_db_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db.return_value = mock_context

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567", "lead_id": "lead_123"}
        )
        assert response.status_code == 200

        # Verify database was accessed (context manager entered)
        mock_context.__enter__.assert_called()
        mock_context.__exit__.assert_called()

    @patch("app.api.voice_routes.get_db_session")
    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_with_lead_id(self, mock_get_twilio, mock_get_db,
                                        test_client, mock_twilio_client, mock_db_session):
        """Test outbound call accepts optional lead_id."""
        mock_get_twilio.return_value = mock_twilio_client
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567", "lead_id": "lead_123"}
        )
        assert response.status_code == 200

    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_handles_twilio_error(self, mock_get_twilio, test_client):
        """Test outbound call handles Twilio API errors gracefully."""
        mock_client = MagicMock()
        mock_client.calls.create.side_effect = Exception("Twilio API error")
        mock_get_twilio.return_value = mock_client

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567"}
        )
        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "detail" in data


# ========== Status Callback Tests ==========

class TestStatusCallbackEndpoint:
    """Test POST /voice/status endpoint."""

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_accepts_form_data(self, mock_get_db, test_client,
                                                sample_status_callback_data, mock_db_session):
        """Test status callback accepts Twilio form-encoded data."""
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_get_db.return_value.__exit__.return_value = None

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        assert response.status_code == 200

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_updates_session(self, mock_get_db, test_client,
                                              sample_status_callback_data, mock_db_session):
        """Test status callback updates voice_session record."""
        # Mock existing session
        mock_session = MagicMock()
        mock_session.status = "active"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        # Use MagicMock as context manager
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_db_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db.return_value = mock_context

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        assert response.status_code == 200

        # Verify database was accessed (context manager entered)
        mock_context.__enter__.assert_called()
        mock_context.__exit__.assert_called()

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_handles_completed_status(self, mock_get_db, test_client,
                                                       sample_status_callback_data, mock_db_session):
        """Test status callback handles 'completed' status."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        data = sample_status_callback_data.copy()
        data["CallStatus"] = "completed"
        data["CallDuration"] = "60"

        response = test_client.post("/voice/status", data=data)
        assert response.status_code == 200

        # Verify session was marked as completed
        assert mock_session.status == "completed"

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_handles_failed_status(self, mock_get_db, test_client,
                                                    sample_status_callback_data, mock_db_session):
        """Test status callback handles 'failed' or 'busy' status."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        data = sample_status_callback_data.copy()
        data["CallStatus"] = "failed"

        response = test_client.post("/voice/status", data=data)
        assert response.status_code == 200

        # Verify session was marked as error
        assert mock_session.status in ["error", "failed"]

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_stores_duration(self, mock_get_db, test_client,
                                              sample_status_callback_data, mock_db_session):
        """Test status callback stores call duration."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        assert response.status_code == 200

        # Verify duration was stored (in milliseconds)
        assert mock_session.total_duration_ms == 45000

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_returns_success_message(self, mock_get_db, test_client,
                                                      sample_status_callback_data, mock_db_session):
        """Test status callback returns success response."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        assert response.status_code == 200
        data = response.json()

        assert "message" in data or "status" in data

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_handles_missing_session(self, mock_get_db, test_client,
                                                      sample_status_callback_data, mock_db_session):
        """Test status callback handles missing voice session gracefully."""
        # Mock no session found
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        # Should return 404 or 200 with warning
        assert response.status_code in [200, 404]


# ========== Integration Tests ==========

class TestVoiceWorkflow:
    """Test end-to-end voice workflows."""

    @patch("app.api.voice_routes.get_twilio_client")
    @patch("app.api.voice_routes.get_db_session")
    def test_outbound_call_to_completion_workflow(self, mock_get_db, mock_get_twilio,
                                                   test_client, mock_twilio_client, mock_db_session):
        """Test full workflow: outbound -> status callbacks -> completion."""
        mock_get_twilio.return_value = mock_twilio_client
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        # Step 1: Create outbound call
        response1 = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567", "lead_id": "lead_123"}
        )
        assert response1.status_code == 200
        call_sid = response1.json()["call_sid"]

        # Step 2: Status callback - ringing
        mock_session = MagicMock()
        mock_session.status = "active"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session

        response2 = test_client.post(
            "/voice/status",
            data={
                "CallSid": call_sid,
                "CallStatus": "ringing",
                "CallDuration": "0"
            }
        )
        assert response2.status_code == 200

        # Step 3: Status callback - in-progress
        response3 = test_client.post(
            "/voice/status",
            data={
                "CallSid": call_sid,
                "CallStatus": "in-progress",
                "CallDuration": "0"
            }
        )
        assert response3.status_code == 200

        # Step 4: Status callback - completed
        response4 = test_client.post(
            "/voice/status",
            data={
                "CallSid": call_sid,
                "CallStatus": "completed",
                "CallDuration": "120"
            }
        )
        assert response4.status_code == 200

        # Verify final state
        assert mock_session.status == "completed"
        assert mock_session.total_duration_ms == 120000


# ========== Error Handling Tests ==========

class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("app.api.voice_routes.get_twilio_client")
    def test_outbound_call_without_twilio_config(self, mock_get_twilio, test_client):
        """Test outbound call fails gracefully without Twilio config."""
        mock_get_twilio.return_value = None

        response = test_client.post(
            "/voice/outbound",
            json={"to": "+15551234567"}
        )
        assert response.status_code in [500, 503]

    def test_incoming_call_with_malformed_data(self, test_client):
        """Test incoming call handles malformed webhook data."""
        response = test_client.post(
            "/voice/incoming",
            data={"invalid": "data"}
        )
        assert response.status_code in [400, 422]

    @patch("app.api.voice_routes.get_db_session")
    def test_status_callback_with_database_error(self, mock_get_db, test_client,
                                                  sample_status_callback_data):
        """Test status callback handles database errors."""
        mock_get_db.side_effect = Exception("Database connection failed")

        response = test_client.post(
            "/voice/status",
            data=sample_status_callback_data
        )
        # Should not crash - return 500
        assert response.status_code == 500
