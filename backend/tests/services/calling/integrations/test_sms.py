"""Tests for SMS sender integration."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.calling.integrations.sms import (
    SMSSender,
    SMSMessage,
    SMSTemplate,
    SMS_TEMPLATES,
    send_video_sms,
    send_calendly_sms,
)


class TestSMSMessage:
    """Tests for SMSMessage dataclass."""

    def test_sms_message_creation(self):
        """Should create SMS message with required fields."""
        msg = SMSMessage(
            to_number="+15551234567",
            body="Test message",
        )
        assert msg.to_number == "+15551234567"
        assert msg.body == "Test message"
        assert msg.sid is None
        assert msg.status is None
        assert msg.error is None


class TestSMSTemplates:
    """Tests for SMS templates."""

    def test_video_link_template_exists(self):
        """Should have video link template."""
        assert SMSTemplate.VIDEO_LINK in SMS_TEMPLATES
        template = SMS_TEMPLATES[SMSTemplate.VIDEO_LINK]
        assert "{name}" in template
        assert "{video_url}" in template

    def test_calendly_link_template_exists(self):
        """Should have Calendly link template."""
        assert SMSTemplate.CALENDLY_LINK in SMS_TEMPLATES
        template = SMS_TEMPLATES[SMSTemplate.CALENDLY_LINK]
        assert "{name}" in template
        assert "{calendly_url}" in template

    def test_thank_you_template_exists(self):
        """Should have thank you template."""
        assert SMSTemplate.THANK_YOU in SMS_TEMPLATES
        template = SMS_TEMPLATES[SMSTemplate.THANK_YOU]
        assert "{name}" in template


class TestSMSSender:
    """Tests for SMSSender class."""

    def test_sender_initializes_without_credentials(self):
        """Should initialize but mark unavailable without credentials."""
        sender = SMSSender()
        assert sender.available is False

    @patch.dict("os.environ", {
        "TWILIO_ACCOUNT_SID": "test_sid",
        "TWILIO_AUTH_TOKEN": "test_token",
    })
    def test_sender_initializes_with_env_credentials(self):
        """Should read credentials from environment."""
        with patch("app.services.calling.integrations.sms.TWILIO_AVAILABLE", True):
            with patch("app.services.calling.integrations.sms.TwilioClient") as mock_client:
                sender = SMSSender()
                assert sender.account_sid == "test_sid"
                assert sender.auth_token == "test_token"

    @pytest.mark.asyncio
    async def test_send_returns_error_when_unavailable(self):
        """Should return error when Twilio not configured."""
        sender = SMSSender()
        msg = SMSMessage(to_number="+15551234567", body="Test")

        result = await sender.send(msg)

        assert result.status == "failed"
        assert result.error == "Twilio not available"

    @pytest.mark.asyncio
    async def test_send_video_link_formats_template(self):
        """Should format video link template correctly."""
        sender = SMSSender()
        sender.available = True
        sender.client = MagicMock()
        sender.client.messages.create = MagicMock(return_value=MagicMock(
            sid="SM123",
            status="queued",
        ))

        result = await sender.send_video_link(
            to_number="+15551234567",
            lead_name="John",
            video_url="https://example.com/video",
        )

        assert "John" in sender.client.messages.create.call_args.kwargs["body"]
        assert "https://example.com/video" in sender.client.messages.create.call_args.kwargs["body"]
        assert result.sid == "SM123"

    @pytest.mark.asyncio
    async def test_send_calendly_link_with_prefill(self):
        """Should add prefill params to Calendly URL."""
        sender = SMSSender()
        sender.available = True
        sender.client = MagicMock()
        sender.client.messages.create = MagicMock(return_value=MagicMock(
            sid="SM456",
            status="queued",
        ))

        result = await sender.send_calendly_link(
            to_number="+15551234567",
            lead_name="John Smith",
            lead_email="john@example.com",
        )

        body = sender.client.messages.create.call_args.kwargs["body"]
        assert "John Smith" in body or "John%20Smith" in body
        assert "john@example.com" in body

    @pytest.mark.asyncio
    async def test_send_thank_you(self):
        """Should send thank you message."""
        sender = SMSSender()
        sender.available = True
        sender.client = MagicMock()
        sender.client.messages.create = MagicMock(return_value=MagicMock(
            sid="SM789",
            status="queued",
        ))

        result = await sender.send_thank_you(
            to_number="+15551234567",
            lead_name="John",
        )

        body = sender.client.messages.create.call_args.kwargs["body"]
        assert "John" in body
        assert "thank" in body.lower() or "Tim" in body


class TestHelperFunctions:
    """Tests for quick helper functions."""

    @pytest.mark.asyncio
    async def test_send_video_sms_helper(self):
        """Should create sender and send video SMS."""
        with patch.object(SMSSender, "send_video_link", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SMSMessage(
                to_number="+15551234567",
                body="Test",
                sid="SM123",
                status="queued",
            )

            result = await send_video_sms("+15551234567", "John")

            mock_send.assert_called_once_with("+15551234567", "John", None)

    @pytest.mark.asyncio
    async def test_send_calendly_sms_helper(self):
        """Should create sender and send Calendly SMS."""
        with patch.object(SMSSender, "send_calendly_link", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SMSMessage(
                to_number="+15551234567",
                body="Test",
                sid="SM456",
                status="queued",
            )

            result = await send_calendly_sms("+15551234567", "John")

            mock_send.assert_called_once_with("+15551234567", "John")
