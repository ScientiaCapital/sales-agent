"""
Tests for Close CRM SMS/Voice Integration

Comprehensive test suite covering:
- SMS sending and history
- Voice call triggers and logging
- Lead sync operations
- API endpoint behavior
- Error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from httpx import Response, HTTPStatusError, Request
import json

from app.services.crm.close_sms import CloseSMSClient
from app.services.crm.close_calling import CloseCallingClient
from app.services.cold_reach_client import trigger_interested_reply_call


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_close_api_key():
    """Mock Close API key."""
    return "test_api_key_12345"


@pytest.fixture
def mock_sms_client(mock_close_api_key):
    """Create CloseSMSClient instance with mocked API key."""
    with patch.dict('os.environ', {'CLOSE_API_KEY': mock_close_api_key}):
        return CloseSMSClient(api_key=mock_close_api_key)


@pytest.fixture
def mock_calling_client(mock_close_api_key):
    """Create CloseCallingClient instance with mocked API key."""
    with patch.dict('os.environ', {'CLOSE_API_KEY': mock_close_api_key}):
        return CloseCallingClient(api_key=mock_close_api_key)


@pytest.fixture
def mock_sms_response():
    """Mock successful SMS API response."""
    return {
        "id": "acti_sms123",
        "status": "sent",
        "direction": "outbound",
        "text": "Hello from test",
        "remote_phone": "+12125551234",
        "lead_id": "lead_test123",
        "date_created": "2024-12-06T12:00:00Z",
        "user_id": "user_test123",
    }


@pytest.fixture
def mock_call_response():
    """Mock successful call API response."""
    return {
        "id": "acti_call123",
        "status": "scheduled",
        "direction": "outbound",
        "phone": "+12125551234",
        "lead_id": "lead_test123",
        "note": "Test call script",
        "date_created": "2024-12-06T12:00:00Z",
        "user_id": "user_test123",
    }


# ============================================================================
# SMS CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_send_sms_success(mock_sms_client, mock_sms_response):
    """Test successful SMS send via Close CRM."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_sms_response
        mock_response.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_sms_client.send_sms(
            phone="+12125551234",
            message="Hello from test",
            lead_id="lead_test123",
        )

        assert result["id"] == "acti_sms123"
        assert result["status"] == "sent"
        assert result["phone"] == "+12125551234"
        assert result["message"] == "Hello from test"
        assert result["lead_id"] == "lead_test123"


@pytest.mark.asyncio
async def test_send_sms_missing_phone(mock_sms_client):
    """Test SMS send fails with missing phone number."""
    with pytest.raises(ValueError, match="Phone number and message are required"):
        await mock_sms_client.send_sms(
            phone="",
            message="Hello",
            lead_id="lead_test123",
        )


@pytest.mark.asyncio
async def test_send_sms_missing_message(mock_sms_client):
    """Test SMS send fails with missing message."""
    with pytest.raises(ValueError, match="Phone number and message are required"):
        await mock_sms_client.send_sms(
            phone="+12125551234",
            message="",
            lead_id="lead_test123",
        )


@pytest.mark.asyncio
async def test_send_sms_api_error(mock_sms_client):
    """Test SMS send handles API errors gracefully."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(spec=Request),
            response=mock_response
        )

        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPStatusError):
            await mock_sms_client.send_sms(
                phone="+12125551234",
                message="Test",
                lead_id="lead_test123",
            )


@pytest.mark.asyncio
async def test_get_sms_history_success(mock_sms_client):
    """Test retrieving SMS history for a lead."""
    mock_history = {
        "data": [
            {
                "id": "acti_sms1",
                "direction": "outbound",
                "text": "First message",
                "remote_phone": "+12125551234",
                "status": "sent",
            },
            {
                "id": "acti_sms2",
                "direction": "inbound",
                "text": "Reply message",
                "remote_phone": "+12125551234",
                "status": "received",
            },
        ]
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history
        mock_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_sms_client.get_sms_history(
            lead_id="lead_test123",
            limit=50,
        )

        assert len(result) == 2
        assert result[0]["id"] == "acti_sms1"
        assert result[1]["id"] == "acti_sms2"


@pytest.mark.asyncio
async def test_send_sms_batch(mock_sms_client, mock_sms_response):
    """Test batch SMS sending."""
    messages = [
        {
            "phone": "+12125551234",
            "message": "Message 1",
            "lead_id": "lead_1",
        },
        {
            "phone": "+12125555678",
            "message": "Message 2",
            "lead_id": "lead_2",
        },
    ]

    with patch.object(mock_sms_client, 'send_sms', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {
            "id": "acti_sms123",
            "status": "sent",
        }

        results = await mock_sms_client.send_sms_batch(messages)

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert results[0]["phone"] == "+12125551234"
        assert results[1]["phone"] == "+12125555678"


# ============================================================================
# CALLING CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_trigger_call_success(mock_calling_client, mock_call_response):
    """Test successful call trigger via Close CRM."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_call_response
        mock_response.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_calling_client.trigger_call(
            phone="+12125551234",
            lead_id="lead_test123",
            script_notes="Test call script",
        )

        assert result["id"] == "acti_call123"
        assert result["status"] == "scheduled"
        assert result["phone"] == "+12125551234"
        assert result["lead_id"] == "lead_test123"


@pytest.mark.asyncio
async def test_trigger_call_missing_params(mock_calling_client):
    """Test call trigger fails with missing required params."""
    with pytest.raises(ValueError, match="Phone number and lead_id are required"):
        await mock_calling_client.trigger_call(
            phone="",
            lead_id="lead_test123",
        )


@pytest.mark.asyncio
async def test_log_call_result_success(mock_calling_client):
    """Test logging call result successfully."""
    mock_result = {
        "id": "acti_call123",
        "status": "answered",
        "duration": 180,
        "note": "Discussed pricing",
        "date_updated": "2024-12-06T12:05:00Z",
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_result
        mock_response.raise_for_status = MagicMock()

        mock_client.put = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_calling_client.log_call_result(
            call_id="acti_call123",
            result="answered",
            notes="Discussed pricing",
            duration_seconds=180,
        )

        assert result["id"] == "acti_call123"
        assert result["status"] == "answered"
        assert result["duration"] == 180


@pytest.mark.asyncio
async def test_log_call_result_invalid_status(mock_calling_client):
    """Test call result logging fails with invalid status."""
    with pytest.raises(ValueError, match="Invalid call result"):
        await mock_calling_client.log_call_result(
            call_id="acti_call123",
            result="invalid_status",
            notes="Test",
        )


@pytest.mark.asyncio
async def test_get_call_history_success(mock_calling_client):
    """Test retrieving call history for a lead."""
    mock_history = {
        "data": [
            {
                "id": "acti_call1",
                "direction": "outbound",
                "status": "answered",
                "phone": "+12125551234",
                "duration": 120,
            },
            {
                "id": "acti_call2",
                "direction": "outbound",
                "status": "voicemail",
                "phone": "+12125551234",
                "duration": 30,
            },
        ]
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history
        mock_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_calling_client.get_call_history(
            lead_id="lead_test123",
            limit=50,
        )

        assert len(result) == 2
        assert result[0]["status"] == "answered"
        assert result[1]["status"] == "voicemail"


@pytest.mark.asyncio
async def test_log_call_directly_success(mock_calling_client):
    """Test logging a completed call directly (single-step)."""
    mock_result = {
        "id": "acti_call123",
        "status": "answered",
        "phone": "+12125551234",
        "lead_id": "lead_test123",
        "duration": 180,
        "note": "Discussed pricing",
        "date_created": "2024-12-06T12:00:00Z",
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_result
        mock_response.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await mock_calling_client.log_call_directly(
            phone="+12125551234",
            lead_id="lead_test123",
            result="answered",
            notes="Discussed pricing",
            duration_seconds=180,
        )

        assert result["id"] == "acti_call123"
        assert result["status"] == "answered"
        assert result["duration"] == 180


# ============================================================================
# COLD REACH CLIENT INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_trigger_interested_reply_call_success():
    """Test triggering call for interested email reply."""
    with patch('app.services.cold_reach_client.CloseCallingClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.trigger_call = AsyncMock(return_value={
            "id": "acti_call123",
            "status": "scheduled",
            "phone": "+12125551234",
            "lead_id": "lead_test123",
            "created_at": "2024-12-06T12:00:00Z",
        })
        mock_client_class.return_value = mock_client

        result = await trigger_interested_reply_call(
            email="john@solarpros.com",
            lead_id="lead_test123",
            phone="+12125551234",
            reply_text="Yes, I'm interested in learning more",
            qualification_score=85,
        )

        assert result["success"] is True
        assert result["activity_id"] == "acti_call123"
        assert result["method"] == "close_crm"
        assert result["phone"] == "+12125551234"


@pytest.mark.asyncio
async def test_trigger_interested_reply_call_error():
    """Test error handling when call trigger fails."""
    with patch('app.services.cold_reach_client.CloseCallingClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.trigger_call = AsyncMock(side_effect=Exception("API error"))
        mock_client_class.return_value = mock_client

        result = await trigger_interested_reply_call(
            email="john@solarpros.com",
            lead_id="lead_test123",
            phone="+12125551234",
        )

        assert result["success"] is False
        assert "error" in result
        assert result["method"] == "close_crm"


# ============================================================================
# API ENDPOINT TESTS (using FastAPI TestClient)
# ============================================================================

from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    from app.main import app
    return TestClient(app)


def test_send_sms_endpoint(test_client):
    """Test POST /api/v1/close/sms endpoint."""
    with patch('app.api.close_outreach.get_sms_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.send_sms = AsyncMock(return_value={
            "id": "acti_sms123",
            "status": "sent",
            "phone": "+12125551234",
            "message": "Test message",
            "lead_id": "lead_test123",
            "created_at": "2024-12-06T12:00:00Z",
        })
        mock_get_client.return_value = mock_client

        response = test_client.post(
            "/api/v1/close/sms",
            json={
                "phone": "+12125551234",
                "message": "Test message",
                "lead_id": "lead_test123",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["activity_id"] == "acti_sms123"


def test_trigger_call_endpoint(test_client):
    """Test POST /api/v1/close/call endpoint."""
    with patch('app.api.close_outreach.get_calling_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.trigger_call = AsyncMock(return_value={
            "id": "acti_call123",
            "status": "scheduled",
            "phone": "+12125551234",
            "lead_id": "lead_test123",
            "created_at": "2024-12-06T12:00:00Z",
        })
        mock_get_client.return_value = mock_client

        response = test_client.post(
            "/api/v1/close/call",
            json={
                "phone": "+12125551234",
                "lead_id": "lead_test123",
                "script_notes": "Test call",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["activity_id"] == "acti_call123"


def test_get_sms_history_endpoint(test_client):
    """Test GET /api/v1/close/sms/history/{lead_id} endpoint."""
    with patch('app.api.close_outreach.get_sms_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_sms_history = AsyncMock(return_value=[
            {"id": "acti_sms1", "text": "Message 1"},
            {"id": "acti_sms2", "text": "Message 2"},
        ])
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/v1/close/sms/history/lead_test123")

        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == "lead_test123"
        assert data["activity_type"] == "sms"
        assert data["count"] == 2


def test_get_call_history_endpoint(test_client):
    """Test GET /api/v1/close/call/history/{lead_id} endpoint."""
    with patch('app.api.close_outreach.get_calling_client') as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_call_history = AsyncMock(return_value=[
            {"id": "acti_call1", "status": "answered"},
            {"id": "acti_call2", "status": "voicemail"},
        ])
        mock_get_client.return_value = mock_client

        response = test_client.get("/api/v1/close/call/history/lead_test123")

        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == "lead_test123"
        assert data["activity_type"] == "call"
        assert data["count"] == 2
