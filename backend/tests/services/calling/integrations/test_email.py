"""Tests for email sender integration."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.calling.integrations.email import (
    EmailSender,
    EmailMessage,
    EmailTemplate,
    EMAIL_TEMPLATES,
    send_video_email,
    send_calendly_email,
)


class TestEmailMessage:
    """Tests for EmailMessage dataclass."""

    def test_email_message_creation(self):
        """Should create email message with required fields."""
        msg = EmailMessage(
            to_email="john@example.com",
            to_name="John Smith",
            subject="Test Subject",
            body_html="<p>Test</p>",
        )
        assert msg.to_email == "john@example.com"
        assert msg.to_name == "John Smith"
        assert msg.subject == "Test Subject"
        assert msg.body_html == "<p>Test</p>"
        assert msg.from_email == "tim@coperniq.ai"
        assert msg.from_name == "Tim Kipper"


class TestEmailTemplates:
    """Tests for email templates."""

    def test_video_link_template_exists(self):
        """Should have video link template with HTML and text."""
        assert EmailTemplate.VIDEO_LINK in EMAIL_TEMPLATES
        template = EMAIL_TEMPLATES[EmailTemplate.VIDEO_LINK]
        assert "subject" in template
        assert "body_html" in template
        assert "body_text" in template
        assert "{name}" in template["body_html"]
        assert "{video_url}" in template["body_html"]

    def test_calendly_link_template_exists(self):
        """Should have Calendly link template."""
        assert EmailTemplate.CALENDLY_LINK in EMAIL_TEMPLATES
        template = EMAIL_TEMPLATES[EmailTemplate.CALENDLY_LINK]
        assert "{calendly_url}" in template["body_html"]
        assert "{demo_focus}" in template["body_html"]

    def test_meeting_confirmation_template_exists(self):
        """Should have meeting confirmation template."""
        assert EmailTemplate.MEETING_CONFIRMATION in EMAIL_TEMPLATES
        template = EMAIL_TEMPLATES[EmailTemplate.MEETING_CONFIRMATION]
        assert "{meeting_time}" in template["body_html"]

    def test_not_interested_template_exists(self):
        """Should have graceful exit template."""
        assert EmailTemplate.NOT_INTERESTED in EMAIL_TEMPLATES
        template = EMAIL_TEMPLATES[EmailTemplate.NOT_INTERESTED]
        assert "thank" in template["body_html"].lower()


class TestEmailSender:
    """Tests for EmailSender class."""

    def test_sender_initializes_without_credentials(self):
        """Should initialize but mark unavailable without API key."""
        sender = EmailSender()
        assert sender.available is False

    @patch.dict("os.environ", {"SENDGRID_API_KEY": "test_key"})
    def test_sender_initializes_with_env_credentials(self):
        """Should read API key from environment."""
        with patch("app.services.calling.integrations.email.SENDGRID_AVAILABLE", True):
            with patch("app.services.calling.integrations.email.SendGridAPIClient") as mock_client:
                sender = EmailSender()
                assert sender.api_key == "test_key"

    @pytest.mark.asyncio
    async def test_send_returns_error_when_unavailable(self):
        """Should return error when SendGrid not configured."""
        sender = EmailSender()
        msg = EmailMessage(
            to_email="john@example.com",
            to_name="John",
            subject="Test",
            body_html="<p>Test</p>",
        )

        result = await sender.send(msg)

        assert result.status == "failed"
        assert result.error == "SendGrid not available"

    @pytest.mark.asyncio
    async def test_send_video_link_formats_template(self):
        """Should format video link email correctly."""
        sender = EmailSender()

        # Mock the send method directly to avoid SendGrid SDK issues
        async def mock_send(msg):
            assert "John" in msg.to_name
            assert "example.com/video" in msg.body_html
            msg.status = "sent"
            msg.message_id = "msg123"
            return msg

        sender.send = mock_send

        result = await sender.send_video_link(
            to_email="john@example.com",
            to_name="John Smith",
            video_url="https://example.com/video",
        )

        assert result.status == "sent"
        assert result.message_id == "msg123"

    @pytest.mark.asyncio
    async def test_send_calendly_link_with_prefill(self):
        """Should add prefill params to Calendly URL."""
        sender = EmailSender()

        # Mock the send method directly
        async def mock_send(msg):
            # Verify Calendly URL has prefill params
            assert "john@example.com" in msg.body_html
            assert "dispatch workflows" in msg.body_html
            msg.status = "sent"
            msg.message_id = "msg456"
            return msg

        sender.send = mock_send

        result = await sender.send_calendly_link(
            to_email="john@example.com",
            to_name="John Smith",
            demo_focus="dispatch workflows",
        )

        assert result.status == "sent"

    @pytest.mark.asyncio
    async def test_send_meeting_confirmation(self):
        """Should send meeting confirmation email."""
        sender = EmailSender()

        # Mock the send method directly
        async def mock_send(msg):
            assert "Tuesday at 2pm" in msg.body_html
            assert "dispatch workflows" in msg.body_html
            msg.status = "sent"
            msg.message_id = "msg789"
            return msg

        sender.send = mock_send

        result = await sender.send_meeting_confirmation(
            to_email="john@example.com",
            to_name="John Smith",
            meeting_time="Tuesday at 2pm",
            demo_focus="dispatch workflows",
        )

        assert result.status == "sent"
        assert "Tuesday at 2pm" in result.subject

    @pytest.mark.asyncio
    async def test_send_not_interested(self):
        """Should send graceful exit email."""
        sender = EmailSender()

        # Mock the send method directly
        async def mock_send(msg):
            assert "thank" in msg.body_html.lower() or "time" in msg.body_html.lower()
            msg.status = "sent"
            msg.message_id = "msg000"
            return msg

        sender.send = mock_send

        result = await sender.send_not_interested(
            to_email="john@example.com",
            to_name="John Smith",
        )

        assert result.status == "sent"


class TestHelperFunctions:
    """Tests for quick helper functions."""

    @pytest.mark.asyncio
    async def test_send_video_email_helper(self):
        """Should create sender and send video email."""
        with patch.object(EmailSender, "send_video_link", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = EmailMessage(
                to_email="john@example.com",
                to_name="John",
                subject="Test",
                body_html="<p>Test</p>",
                status="sent",
            )

            result = await send_video_email("john@example.com", "John")

            mock_send.assert_called_once_with("john@example.com", "John")

    @pytest.mark.asyncio
    async def test_send_calendly_email_helper(self):
        """Should create sender and send Calendly email."""
        with patch.object(EmailSender, "send_calendly_link", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = EmailMessage(
                to_email="john@example.com",
                to_name="John",
                subject="Test",
                body_html="<p>Test</p>",
                status="sent",
            )

            result = await send_calendly_email("john@example.com", "John")

            mock_send.assert_called_once_with("john@example.com", "John")
