import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.calling.gates.pre_call import PreCallGate, ApprovalResult


@pytest.mark.asyncio
async def test_pre_call_sends_slack_notification():
    """Should send Slack message with lead info."""
    gate = PreCallGate(slack_webhook_url="https://hooks.slack.com/test")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = await gate.request_approval(
            lead={
                "company_name": "Solar Pros",
                "phone": "+15551234567",
                "contact_name": "John Smith",
            },
            script_preview="Hi John, this is Alex from...",
            call_id="call_123"
        )

        assert result["notification_sent"] is True


@pytest.mark.asyncio
async def test_pre_call_timeout_auto_skips():
    """Should return timeout when no response."""
    gate = PreCallGate(
        slack_webhook_url="https://hooks.slack.com/test",
        timeout_seconds=1,
    )
    gate._check_approval = AsyncMock(return_value=None)

    result = await gate.wait_for_approval(call_id="test123")

    assert result["approved"] is False
    assert result["reason"] == "timeout"


@pytest.mark.asyncio
async def test_pre_call_handles_approval():
    """Should process approval callback correctly."""
    gate = PreCallGate(slack_webhook_url="https://hooks.slack.com/test")

    gate.handle_slack_callback("call_123", "approve", "tim")

    result = gate._pending_approvals.get("call_123")
    assert result is not None
    assert result.approved is True
    assert result.approver == "tim"


@pytest.mark.asyncio
async def test_pre_call_handles_skip():
    """Should process skip callback correctly."""
    gate = PreCallGate(slack_webhook_url="https://hooks.slack.com/test")

    gate.handle_slack_callback("call_456", "skip", "tim")

    result = gate._pending_approvals.get("call_456")
    assert result is not None
    assert result.approved is False
