"""Tests for SMSFollowupHandler."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.voice.sms_handler import (
    SMSFollowupHandler,
    SMSFollowupResult,
    CallOutcome,
    SMSTemplate,
    SMS_TEMPLATES,
)


class TestSMSFollowupHandler:
    """Tests for SMSFollowupHandler."""

    @pytest.fixture
    def mock_sms_client(self):
        """Create mock SMS client."""
        client = MagicMock()
        client.send_sms = AsyncMock(return_value={
            "id": "sms_123",
            "status": "sent",
            "phone": "+15551234567"
        })
        return client

    @pytest.fixture
    def handler(self, mock_sms_client):
        """Create handler instance."""
        return SMSFollowupHandler(
            close_sms_client=mock_sms_client,
            company_name="Test Company",
            escalation_phone="+15559999999"
        )

    def test_init(self, handler):
        """Test handler initialization."""
        assert handler is not None
        assert handler.company_name == "Test Company"
        assert handler.escalation_phone == "+15559999999"

    def test_init_without_client(self):
        """Test init without SMS client."""
        handler = SMSFollowupHandler()
        assert handler.sms_client is None

    def test_render_template_basic(self, handler):
        """Test basic template rendering."""
        message = handler._render_template(
            SMSTemplate.POST_CALL_THANKYOU,
            {"name": "John"}
        )

        assert "John" in message
        assert "Test Company" in message

    def test_render_template_missing_vars(self, handler):
        """Test template rendering with missing variables."""
        # Should not raise, uses empty string for missing
        message = handler._render_template(
            SMSTemplate.POST_CALL_MEETING,
            {}  # Missing name and meeting_time
        )

        assert isinstance(message, str)

    @pytest.mark.asyncio
    async def test_send_post_call_sms_answered(self, handler, mock_sms_client):
        """Test post-call SMS for answered call."""
        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.ANSWERED,
            phone="+15551234567",
            contact_name="Jane"
        )

        assert result.success is True
        assert result.template == SMSTemplate.POST_CALL_THANKYOU
        assert "Jane" in result.message
        mock_sms_client.send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_post_call_sms_meeting_scheduled(self, handler, mock_sms_client):
        """Test post-call SMS for scheduled meeting."""
        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.MEETING_SCHEDULED,
            phone="+15551234567",
            contact_name="Bob",
            meeting_time="Tuesday at 2 PM"
        )

        assert result.success is True
        assert result.template == SMSTemplate.POST_CALL_MEETING
        assert "Tuesday at 2 PM" in result.message

    @pytest.mark.asyncio
    async def test_send_post_call_sms_voicemail(self, handler, mock_sms_client):
        """Test post-call SMS after voicemail."""
        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.VOICEMAIL,
            phone="+15551234567",
            contact_name="Alice"
        )

        assert result.success is True
        assert result.template == SMSTemplate.VOICEMAIL_FOLLOWUP

    @pytest.mark.asyncio
    async def test_send_post_call_sms_no_answer(self, handler, mock_sms_client):
        """Test post-call SMS for missed call."""
        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.NO_ANSWER,
            phone="+15551234567"
        )

        assert result.success is True
        assert result.template == SMSTemplate.MISSED_CALL

    @pytest.mark.asyncio
    async def test_send_post_call_sms_failed(self, handler):
        """Test no SMS for failed calls."""
        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.FAILED
        )

        assert result.success is True
        assert result.template is None
        assert "No SMS required" in result.message

    @pytest.mark.asyncio
    async def test_send_post_call_sms_no_client(self):
        """Test post-call SMS without SMS client."""
        handler = SMSFollowupHandler()

        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.ANSWERED
        )

        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_post_call_sms_api_error(self, handler, mock_sms_client):
        """Test post-call SMS with API error."""
        mock_sms_client.send_sms = AsyncMock(side_effect=Exception("API Error"))

        result = await handler.send_post_call_sms(
            lead_id="lead_123",
            call_outcome=CallOutcome.ANSWERED,
            phone="+15551234567"
        )

        assert result.success is False
        assert "API Error" in result.error

    @pytest.mark.asyncio
    async def test_send_missed_call_sms(self, handler, mock_sms_client):
        """Test missed call SMS shortcut."""
        result = await handler.send_missed_call_sms(
            lead_id="lead_123",
            phone="+15551234567",
            contact_name="Charlie"
        )

        assert result.success is True
        assert result.template == SMSTemplate.MISSED_CALL

    @pytest.mark.asyncio
    async def test_send_voicemail_followup_sms(self, handler, mock_sms_client):
        """Test voicemail follow-up SMS."""
        result = await handler.send_voicemail_followup_sms(
            lead_id="lead_123",
            phone="+15551234567",
            contact_name="Dana",
            topic="our pricing plans"
        )

        assert result.success is True
        assert result.template == SMSTemplate.VOICEMAIL_FOLLOWUP
        assert "pricing plans" in result.message

    @pytest.mark.asyncio
    async def test_escalate_to_human(self, handler, mock_sms_client):
        """Test human escalation SMS."""
        result = await handler.escalate_to_human(
            lead_id="lead_123",
            reason="High-value lead needs immediate callback",
            lead_name="VIP Customer",
            lead_company="Big Corp",
            lead_phone="+15551234567"
        )

        assert result.success is True
        assert result.template == SMSTemplate.ESCALATION_ALERT
        assert result.phone == "+15559999999"  # Escalation phone
        assert "VIP Customer" in result.message
        assert "Big Corp" in result.message

    @pytest.mark.asyncio
    async def test_escalate_to_human_urgent(self, handler, mock_sms_client):
        """Test urgent escalation."""
        result = await handler.escalate_to_human(
            lead_id="lead_123",
            reason="Competitor mention",
            lead_name="Hot Lead",
            priority="urgent"
        )

        assert result.success is True
        assert "[URGENT]" in result.message

    @pytest.mark.asyncio
    async def test_escalate_to_human_no_phone(self):
        """Test escalation without configured phone."""
        handler = SMSFollowupHandler(
            close_sms_client=MagicMock(),
            escalation_phone=None
        )

        result = await handler.escalate_to_human(
            lead_id="lead_123",
            reason="Test"
        )

        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_callback_confirmation(self, handler, mock_sms_client):
        """Test callback confirmation SMS."""
        result = await handler.send_callback_confirmation(
            lead_id="lead_123",
            phone="+15551234567",
            contact_name="Eve",
            callback_timeframe="2 hours"
        )

        assert result.success is True
        assert result.template == SMSTemplate.CALLBACK_REQUEST
        assert "2 hours" in result.message

    def test_get_available_templates(self, handler):
        """Test getting available templates."""
        templates = handler.get_available_templates()

        assert len(templates) == len(SMSTemplate)
        assert "post_call_thankyou" in templates
        assert "escalation_alert" in templates

    @pytest.mark.asyncio
    async def test_preview_message(self, handler):
        """Test message preview."""
        preview = await handler.preview_message(
            SMSTemplate.POST_CALL_THANKYOU,
            {"name": "Preview Test"}
        )

        assert "Preview Test" in preview
        assert isinstance(preview, str)


class TestCallOutcome:
    """Tests for CallOutcome enum."""

    def test_all_outcomes(self):
        """Test all call outcomes are defined."""
        outcomes = [
            CallOutcome.ANSWERED,
            CallOutcome.VOICEMAIL,
            CallOutcome.NO_ANSWER,
            CallOutcome.BUSY,
            CallOutcome.FAILED,
            CallOutcome.MEETING_SCHEDULED,
            CallOutcome.TRANSFERRED,
            CallOutcome.QUALIFIED,
        ]

        assert len(outcomes) == 8

    def test_outcome_values(self):
        """Test outcome values."""
        assert CallOutcome.ANSWERED.value == "answered"
        assert CallOutcome.VOICEMAIL.value == "voicemail"
        assert CallOutcome.MEETING_SCHEDULED.value == "meeting_scheduled"


class TestSMSTemplate:
    """Tests for SMS template enum."""

    def test_all_templates_have_content(self):
        """Test all templates have content defined."""
        for template in SMSTemplate:
            assert template in SMS_TEMPLATES
            assert len(SMS_TEMPLATES[template]) > 0

    def test_templates_contain_placeholders(self):
        """Test templates contain expected placeholders."""
        # Thank you template should have name placeholder
        assert "{name}" in SMS_TEMPLATES[SMSTemplate.POST_CALL_THANKYOU]

        # Meeting template should have meeting_time
        assert "{meeting_time}" in SMS_TEMPLATES[SMSTemplate.POST_CALL_MEETING]

        # Escalation should have lead info
        assert "{reason}" in SMS_TEMPLATES[SMSTemplate.ESCALATION_ALERT]


class TestSMSFollowupResult:
    """Tests for SMSFollowupResult dataclass."""

    def test_success_result(self):
        """Test successful result creation."""
        result = SMSFollowupResult(
            success=True,
            sms_id="sms_123",
            phone="+15551234567",
            lead_id="lead_123",
            template=SMSTemplate.POST_CALL_THANKYOU,
            message="Test message",
            timestamp=datetime.utcnow()
        )

        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Test failure result creation."""
        result = SMSFollowupResult(
            success=False,
            error="API Error",
            timestamp=datetime.utcnow()
        )

        assert result.success is False
        assert result.sms_id is None
