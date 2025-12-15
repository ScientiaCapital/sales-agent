import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.calling.gates.post_call import PostCallGate, MeetingConfirmation


@pytest.mark.asyncio
async def test_post_call_sends_meeting_confirmation():
    """Should send Slack with call summary and meeting details."""
    gate = PostCallGate(slack_webhook_url="https://hooks.slack.com/test")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = await gate.request_meeting_confirmation(
            call_summary={
                "company_name": "Solar Pros",
                "contact_name": "John Smith",
                "duration_seconds": 180,
                "outcome": "meeting_booked",
            },
            proposed_meeting={
                "datetime": "2024-12-17T14:00:00",
                "duration_minutes": 30,
            },
            call_id="call_123"
        )

        assert result["notification_sent"] is True


@pytest.mark.asyncio
async def test_post_call_creates_calendar_event_on_confirm():
    """Should create calendar event when confirmed."""
    gate = PostCallGate(slack_webhook_url="https://hooks.slack.com/test")
    gate._create_calendar_event = AsyncMock(return_value={"event_id": "evt123"})

    result = await gate.confirm_meeting(
        call_id="call123",
        meeting_time="2024-12-17T14:00:00",
        attendee_email="john@solarpros.com",
    )

    assert result["calendar_event_created"] is True
    gate._create_calendar_event.assert_called_once()


@pytest.mark.asyncio
async def test_post_call_handles_rejection():
    """Should handle rejected meeting."""
    gate = PostCallGate(slack_webhook_url="https://hooks.slack.com/test")

    gate.handle_slack_callback("call_123", "reject", "tim")

    result = gate._pending_confirmations.get("call_123")
    assert result is not None
    assert result.confirmed is False


@pytest.mark.asyncio
async def test_post_call_handles_reschedule():
    """Should handle reschedule request."""
    gate = PostCallGate(slack_webhook_url="https://hooks.slack.com/test")

    gate.handle_slack_callback("call_456", "reschedule", "tim")

    result = gate._pending_confirmations.get("call_456")
    assert result is not None
    assert result.reschedule_requested is True
