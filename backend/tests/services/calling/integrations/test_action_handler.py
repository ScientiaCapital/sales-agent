"""Tests for action handler integration."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.calling.integrations.action_handler import (
    ActionHandler,
    ActionType,
    ActionResult,
    LeadContext,
    handle_agent_action,
)
from app.services.calling.integrations.sms import SMSMessage
from app.services.calling.integrations.email import EmailMessage


class TestLeadContext:
    """Tests for LeadContext dataclass."""

    def test_lead_context_creation(self):
        """Should create lead context with required fields."""
        lead = LeadContext(
            phone_number="+15551234567",
            email="john@example.com",
            first_name="John",
        )
        assert lead.phone_number == "+15551234567"
        assert lead.email == "john@example.com"
        assert lead.first_name == "John"
        assert lead.pain_points == []

    def test_full_name_with_last_name(self):
        """Should return full name when last name provided."""
        lead = LeadContext(
            phone_number="+15551234567",
            first_name="John",
            last_name="Smith",
        )
        assert lead.full_name == "John Smith"

    def test_full_name_without_last_name(self):
        """Should return first name only when no last name."""
        lead = LeadContext(
            phone_number="+15551234567",
            first_name="John",
        )
        assert lead.full_name == "John"


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_successful_result(self):
        """Should create successful action result."""
        result = ActionResult(
            action_type=ActionType.SEND_VIDEO_SMS,
            success=True,
            message_id="SM123",
        )
        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """Should create failed action result."""
        result = ActionResult(
            action_type=ActionType.SEND_VIDEO_SMS,
            success=False,
            error="Send failed",
        )
        assert result.success is False
        assert result.error == "Send failed"


class TestActionHandler:
    """Tests for ActionHandler class."""

    def test_handler_initializes_providers(self):
        """Should initialize SMS, email, and Calendly providers."""
        handler = ActionHandler()
        assert handler.sms is not None
        assert handler.email is not None
        assert handler.calendly is not None

    @pytest.mark.asyncio
    async def test_execute_send_video_sms(self):
        """Should route SEND_VIDEO_SMS to SMS sender."""
        handler = ActionHandler()
        handler.sms = MagicMock()
        handler.sms.send_video_link = AsyncMock(return_value=SMSMessage(
            to_number="+15551234567",
            body="Test",
            sid="SM123",
            status="queued",
        ))

        lead = LeadContext(phone_number="+15551234567", first_name="John")
        result = await handler.execute(ActionType.SEND_VIDEO_SMS, lead)

        assert result.success is True
        handler.sms.send_video_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_send_video_email(self):
        """Should route SEND_VIDEO_EMAIL to email sender."""
        handler = ActionHandler()
        handler.email = MagicMock()
        handler.email.send_video_link = AsyncMock(return_value=EmailMessage(
            to_email="john@example.com",
            to_name="John",
            subject="Test",
            body_html="<p>Test</p>",
            status="sent",
            message_id="msg123",
        ))

        lead = LeadContext(
            phone_number="+15551234567",
            email="john@example.com",
            first_name="John",
        )
        result = await handler.execute(ActionType.SEND_VIDEO_EMAIL, lead)

        assert result.success is True
        handler.email.send_video_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_send_video_email_without_email(self):
        """Should fail when no email provided."""
        handler = ActionHandler()

        lead = LeadContext(phone_number="+15551234567", first_name="John")
        result = await handler.execute(ActionType.SEND_VIDEO_EMAIL, lead)

        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_video_sms_channel(self):
        """Should send video via SMS when channel is 'sms'."""
        handler = ActionHandler()
        handler.sms = MagicMock()
        handler.sms.send_video_link = AsyncMock(return_value=SMSMessage(
            to_number="+15551234567",
            body="Test",
            sid="SM123",
            status="queued",
        ))

        lead = LeadContext(phone_number="+15551234567", first_name="John")
        result = await handler.send_video(lead, channel="sms")

        assert result.success is True
        handler.sms.send_video_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_video_email_channel(self):
        """Should send video via email when channel is 'email'."""
        handler = ActionHandler()
        handler.email = MagicMock()
        handler.email.send_video_link = AsyncMock(return_value=EmailMessage(
            to_email="john@example.com",
            to_name="John",
            subject="Test",
            body_html="<p>Test</p>",
            status="sent",
            message_id="msg123",
        ))

        lead = LeadContext(
            phone_number="+15551234567",
            email="john@example.com",
            first_name="John",
        )
        result = await handler.send_video(lead, channel="email")

        assert result.success is True
        handler.email.send_video_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_video_both_channels(self):
        """Should send video via both SMS and email when channel is 'both'."""
        handler = ActionHandler()
        handler.sms = MagicMock()
        handler.sms.send_video_link = AsyncMock(return_value=SMSMessage(
            to_number="+15551234567",
            body="Test",
            sid="SM123",
            status="queued",
        ))
        handler.email = MagicMock()
        handler.email.send_video_link = AsyncMock(return_value=EmailMessage(
            to_email="john@example.com",
            to_name="John",
            subject="Test",
            body_html="<p>Test</p>",
            status="sent",
            message_id="msg123",
        ))

        lead = LeadContext(
            phone_number="+15551234567",
            email="john@example.com",
            first_name="John",
        )
        result = await handler.send_video(lead, channel="both")

        assert result.success is True
        handler.sms.send_video_link.assert_called_once()
        handler.email.send_video_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_calendly_sms(self):
        """Should send Calendly link via SMS."""
        handler = ActionHandler()
        handler.sms = MagicMock()
        handler.sms.send_calendly_link = AsyncMock(return_value=SMSMessage(
            to_number="+15551234567",
            body="Test",
            sid="SM456",
            status="queued",
        ))

        lead = LeadContext(phone_number="+15551234567", first_name="John")
        result = await handler.send_calendly(lead, channel="sms")

        assert result.success is True
        handler.sms.send_calendly_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_demo_focus_from_pain_points(self):
        """Should generate demo focus text from pain points."""
        handler = ActionHandler()

        assert "dispatch" in handler._get_demo_focus(["dispatch"])
        assert "QuickBooks" in handler._get_demo_focus(["qbo"])
        assert "reports" in handler._get_demo_focus(["reporting"])
        assert "asset" in handler._get_demo_focus(["assets"])
        assert "Coperniq" in handler._get_demo_focus([])  # default


class TestHandleAgentAction:
    """Tests for handle_agent_action convenience function."""

    @pytest.mark.asyncio
    async def test_handle_send_video_action(self):
        """Should handle 'send_video' action string."""
        with patch.object(ActionHandler, "send_video", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = ActionResult(
                action_type=ActionType.SEND_VIDEO_SMS,
                success=True,
            )

            result = await handle_agent_action(
                action="send_video",
                lead_phone="+15551234567",
                lead_name="John Smith",
            )

            assert result.success is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_send_calendly_action(self):
        """Should handle 'send_calendly' action string."""
        with patch.object(ActionHandler, "send_calendly", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = ActionResult(
                action_type=ActionType.SEND_CALENDLY_SMS,
                success=True,
            )

            result = await handle_agent_action(
                action="send_calendly",
                lead_phone="+15551234567",
                lead_name="John Smith",
            )

            assert result.success is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self):
        """Should return error for unknown action."""
        result = await handle_agent_action(
            action="unknown_action",
            lead_phone="+15551234567",
            lead_name="John Smith",
        )

        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_parses_lead_name_into_parts(self):
        """Should split lead name into first/last."""
        with patch.object(ActionHandler, "send_video", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = ActionResult(
                action_type=ActionType.SEND_VIDEO_SMS,
                success=True,
            )

            await handle_agent_action(
                action="send_video",
                lead_phone="+15551234567",
                lead_name="John Michael Smith",
            )

            # Check the LeadContext was built correctly
            call_args = mock_send.call_args
            lead = call_args[0][0]  # First positional arg
            assert lead.first_name == "John"
            assert lead.last_name == "Michael Smith"
