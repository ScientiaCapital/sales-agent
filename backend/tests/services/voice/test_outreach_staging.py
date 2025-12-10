"""Tests for OutreachStagingService."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.services.voice.outreach_staging import (
    OutreachStagingService,
    StagedAction,
    StagedActionType,
    StagedActionStatus,
    VMTranscription,
    ResponseOptions,
)


class TestOutreachStagingService:
    """Tests for OutreachStagingService."""

    @pytest.fixture
    def mock_sms_client(self):
        """Create mock SMS client."""
        client = MagicMock()
        client.send_sms = AsyncMock(return_value={"id": "sms_123"})
        return client

    @pytest.fixture
    def mock_calling_client(self):
        """Create mock calling client."""
        client = MagicMock()
        client.trigger_call = AsyncMock(return_value={"id": "call_123"})
        return client

    @pytest.fixture
    def mock_deepgram(self):
        """Create mock Deepgram service."""
        service = MagicMock()
        service.transcribe_url = AsyncMock(return_value={
            "transcript": "Hi, this is John calling about your product. Please call me back.",
            "duration": 15
        })
        return service

    @pytest.fixture
    def service(self, mock_sms_client, mock_calling_client, mock_deepgram):
        """Create service instance."""
        return OutreachStagingService(
            deepgram_service=mock_deepgram,
            close_sms_client=mock_sms_client,
            close_calling_client=mock_calling_client
        )

    def test_init(self, service):
        """Test service initialization."""
        assert service is not None
        assert service._staged_actions == {}
        assert service._vm_transcriptions == {}

    @pytest.mark.asyncio
    async def test_process_inbound_voicemail(self, service):
        """Test processing inbound voicemail."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        assert isinstance(options, ResponseOptions)
        assert options.vm_transcription is not None
        assert len(options.staged_actions) == 3  # SMS, Call, VM Drop
        assert options.recommended_action is not None

    @pytest.mark.asyncio
    async def test_process_voicemail_transcription(self, service):
        """Test VM transcription extraction."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        vm = options.vm_transcription
        assert vm.lead_id == "lead_123"
        assert vm.caller_phone == "+15551234567"
        assert "John" in vm.transcript or "call me back" in vm.transcript.lower()

    @pytest.mark.asyncio
    async def test_voicemail_analysis_callback_request(self, service, mock_deepgram):
        """Test VM analysis detects callback request."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "Hi, please call me back when you can.",
            "duration": 10
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        assert options.vm_transcription.intent == "callback_request"

    @pytest.mark.asyncio
    async def test_voicemail_analysis_pricing_inquiry(self, service, mock_deepgram):
        """Test VM analysis detects pricing inquiry."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "I'm interested in your pricing and cost information.",
            "duration": 8
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        assert options.vm_transcription.intent == "pricing_inquiry"

    @pytest.mark.asyncio
    async def test_voicemail_analysis_demo_request(self, service, mock_deepgram):
        """Test VM analysis detects demo request."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "I'd love to see a demo of your product.",
            "duration": 6
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        assert options.vm_transcription.intent == "demo_request"

    @pytest.mark.asyncio
    async def test_voicemail_analysis_urgency(self, service, mock_deepgram):
        """Test VM analysis detects urgency."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "This is urgent, please call me back ASAP!",
            "duration": 5
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        assert options.vm_transcription.urgency == "high"

    @pytest.mark.asyncio
    async def test_voicemail_analysis_negative_sentiment(self, service, mock_deepgram):
        """Test VM analysis detects negative sentiment."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "I'm frustrated with the issue I'm having.",
            "duration": 8
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        assert options.vm_transcription.sentiment == "negative"

    @pytest.mark.asyncio
    async def test_staged_actions_generated(self, service):
        """Test staged actions are generated correctly."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        action_types = [a.action_type for a in options.staged_actions]

        assert StagedActionType.SMS in action_types
        assert StagedActionType.CALL in action_types
        assert StagedActionType.VOICEMAIL_DROP in action_types

    @pytest.mark.asyncio
    async def test_staged_actions_have_content(self, service):
        """Test staged actions have proper content."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        for action in options.staged_actions:
            assert action.id is not None
            assert action.lead_id == "lead_123"
            assert action.status == StagedActionStatus.PENDING
            assert action.content is not None
            assert action.created_by == "ai"

    @pytest.mark.asyncio
    async def test_recommended_action_urgent_is_call(self, service, mock_deepgram):
        """Test urgent VMs recommend call action."""
        mock_deepgram.transcribe_url = AsyncMock(return_value={
            "transcript": "This is urgent, call me immediately!",
            "duration": 5
        })

        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        # Find recommended action
        recommended = next(
            (a for a in options.staged_actions if a.id == options.recommended_action),
            None
        )

        assert recommended is not None
        assert recommended.action_type == StagedActionType.CALL

    @pytest.mark.asyncio
    async def test_stage_response_options_from_transcript(self, service):
        """Test staging from pre-transcribed text."""
        options = await service.stage_response_options(
            lead_id="lead_456",
            vm_transcript="I'm interested in pricing.",
            lead_context={"phone": "+15551234567", "contact_name": "Jane"}
        )

        assert options.vm_transcription.transcript == "I'm interested in pricing."
        assert len(options.staged_actions) == 3

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, service):
        """Test getting pending approvals."""
        # Create some staged actions
        await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        pending = await service.get_pending_approvals()

        assert len(pending) > 0
        assert all(a.status == StagedActionStatus.PENDING for a in pending)

    @pytest.mark.asyncio
    async def test_get_staged_action(self, service):
        """Test getting specific staged action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        action_id = options.staged_actions[0].id

        retrieved = await service.get_staged_action(action_id)

        assert retrieved is not None
        assert retrieved.id == action_id

    @pytest.mark.asyncio
    async def test_get_staged_action_not_found(self, service):
        """Test getting non-existent staged action."""
        retrieved = await service.get_staged_action("nonexistent_id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_approve_and_execute_sms(self, service, mock_sms_client):
        """Test approving and executing SMS action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        # Find SMS action
        sms_action = next(
            (a for a in options.staged_actions if a.action_type == StagedActionType.SMS),
            None
        )

        result = await service.approve_and_execute(
            staged_id=sms_action.id,
            action="approve",
            reviewer_id="user_123"
        )

        assert result["success"] is True
        assert result["type"] == "sms"
        mock_sms_client.send_sms.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_and_execute_call(self, service, mock_calling_client):
        """Test approving and executing call action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        # Find call action
        call_action = next(
            (a for a in options.staged_actions if a.action_type == StagedActionType.CALL),
            None
        )

        result = await service.approve_and_execute(
            staged_id=call_action.id,
            action="approve"
        )

        assert result["success"] is True
        assert result["type"] == "call"
        mock_calling_client.trigger_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_and_execute_reject(self, service):
        """Test rejecting a staged action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        action_id = options.staged_actions[0].id

        result = await service.approve_and_execute(
            staged_id=action_id,
            action="reject",
            reviewer_id="user_123",
            notes="Not appropriate for this lead"
        )

        assert result["success"] is True
        assert result["status"] == "rejected"

        # Verify status updated
        action = await service.get_staged_action(action_id)
        assert action.status == StagedActionStatus.REJECTED

    @pytest.mark.asyncio
    async def test_approve_and_execute_edit(self, service, mock_sms_client):
        """Test editing and executing a staged action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123",
            caller_phone="+15551234567"
        )

        sms_action = next(
            (a for a in options.staged_actions if a.action_type == StagedActionType.SMS),
            None
        )

        edited_content = {
            "to": "+15551234567",
            "message": "Custom edited message from human reviewer"
        }

        result = await service.approve_and_execute(
            staged_id=sms_action.id,
            action="edit",
            reviewer_id="user_123",
            edited_content=edited_content
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_approve_and_execute_not_found(self, service):
        """Test approving non-existent action."""
        result = await service.approve_and_execute(
            staged_id="nonexistent",
            action="approve"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_trigger_outbound_with_vm_drop(self, service, mock_calling_client):
        """Test triggering outbound call with VM drop ready."""
        result = await service.trigger_outbound_with_vm_drop(
            lead_id="lead_123",
            phone="+15551234567",
            vm_preset="intro_enterprise",
            script_notes="Follow up on demo request"
        )

        assert result["success"] is True
        assert result["vm_preset"] == "intro_enterprise"
        mock_calling_client.trigger_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_outbound_no_client(self):
        """Test outbound without calling client."""
        service = OutreachStagingService()

        result = await service.trigger_outbound_with_vm_drop(
            lead_id="lead_123",
            phone="+15551234567",
            vm_preset="intro_smb"
        )

        assert result["success"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_cancel_staged_action(self, service):
        """Test cancelling a pending staged action."""
        options = await service.process_inbound_voicemail(
            recording_url="https://example.com/recording.mp3",
            lead_id="lead_123"
        )

        action_id = options.staged_actions[0].id

        success = await service.cancel_staged_action(action_id)

        assert success is True

        # Verify status updated
        action = await service.get_staged_action(action_id)
        assert action.status == StagedActionStatus.REJECTED

    @pytest.mark.asyncio
    async def test_cancel_staged_action_not_found(self, service):
        """Test cancelling non-existent action."""
        success = await service.cancel_staged_action("nonexistent")
        assert success is False


class TestStagedAction:
    """Tests for StagedAction dataclass."""

    def test_staged_action_creation(self):
        """Test StagedAction creation."""
        action = StagedAction(
            id="staged_123",
            lead_id="lead_456",
            action_type=StagedActionType.SMS,
            status=StagedActionStatus.PENDING,
            content={"message": "Test"},
            created_at=datetime.utcnow(),
            created_by="ai"
        )

        assert action.id == "staged_123"
        assert action.reviewed_by is None
        assert action.executed_at is None


class TestStagedActionType:
    """Tests for StagedActionType enum."""

    def test_action_types(self):
        """Test all action types."""
        assert StagedActionType.EMAIL.value == "email"
        assert StagedActionType.SMS.value == "sms"
        assert StagedActionType.CALL.value == "call"
        assert StagedActionType.VOICEMAIL_DROP.value == "voicemail_drop"


class TestStagedActionStatus:
    """Tests for StagedActionStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert StagedActionStatus.PENDING.value == "pending"
        assert StagedActionStatus.APPROVED.value == "approved"
        assert StagedActionStatus.REJECTED.value == "rejected"
        assert StagedActionStatus.EXECUTED.value == "executed"
        assert StagedActionStatus.EXPIRED.value == "expired"
        assert StagedActionStatus.EDITED.value == "edited"


class TestVMTranscription:
    """Tests for VMTranscription dataclass."""

    def test_transcription_creation(self):
        """Test VMTranscription creation."""
        vm = VMTranscription(
            id="vm_123",
            lead_id="lead_456",
            recording_url="https://example.com/vm.mp3",
            transcript="Hello, this is a test.",
            duration_seconds=10,
            caller_phone="+15551234567",
            sentiment="positive",
            intent="demo_request",
            urgency="medium"
        )

        assert vm.id == "vm_123"
        assert vm.sentiment == "positive"
        assert vm.intent == "demo_request"
