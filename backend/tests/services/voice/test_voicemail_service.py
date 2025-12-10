"""Tests for VoicemailDropService."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.voice.voicemail_service import (
    VoicemailDropService,
    VMPreset,
    VMDropResult,
    VMDropStatus,
    AMDResult,
    DEFAULT_VM_PRESETS,
)


class TestVoicemailDropService:
    """Tests for VoicemailDropService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return VoicemailDropService(
            twilio_account_sid="AC_test_sid",
            twilio_auth_token="test_token"
        )

    def test_init(self, service):
        """Test service initialization."""
        assert service is not None
        assert service.account_sid == "AC_test_sid"
        assert service.auth_token == "test_token"

    def test_init_without_credentials(self):
        """Test init without credentials uses env vars."""
        with patch.dict("os.environ", {}, clear=True):
            service = VoicemailDropService()
            assert service.account_sid is None
            assert service.auth_token is None

    @pytest.mark.asyncio
    async def test_detect_answering_machine_human(self, service):
        """Test AMD detection for human answer."""
        is_machine = await service.detect_answering_machine("CA123", "human")
        assert is_machine is False

    @pytest.mark.asyncio
    async def test_detect_answering_machine_beep(self, service):
        """Test AMD detection for machine with beep."""
        is_machine = await service.detect_answering_machine("CA123", "machine_end_beep")
        assert is_machine is True

    @pytest.mark.asyncio
    async def test_detect_answering_machine_silence(self, service):
        """Test AMD detection for machine end silence."""
        is_machine = await service.detect_answering_machine("CA123", "machine_end_silence")
        assert is_machine is True

    @pytest.mark.asyncio
    async def test_detect_answering_machine_other(self, service):
        """Test AMD detection for machine end other."""
        is_machine = await service.detect_answering_machine("CA123", "machine_end_other")
        assert is_machine is True

    @pytest.mark.asyncio
    async def test_detect_answering_machine_start(self, service):
        """Test AMD detection for machine start (still talking)."""
        is_machine = await service.detect_answering_machine("CA123", "machine_start")
        assert is_machine is False  # Wait for end

    @pytest.mark.asyncio
    async def test_detect_answering_machine_fax(self, service):
        """Test AMD detection for fax."""
        is_machine = await service.detect_answering_machine("CA123", "fax")
        assert is_machine is False

    @pytest.mark.asyncio
    async def test_detect_answering_machine_unknown(self, service):
        """Test AMD detection for unknown status."""
        is_machine = await service.detect_answering_machine("CA123", "unknown")
        assert is_machine is False

    @pytest.mark.asyncio
    async def test_detect_answering_machine_invalid_status(self, service):
        """Test AMD detection for invalid status."""
        is_machine = await service.detect_answering_machine("CA123", "invalid_status")
        assert is_machine is False

    @pytest.mark.asyncio
    async def test_drop_voicemail_preset_not_found(self, service):
        """Test VM drop with invalid preset."""
        result = await service.drop_voicemail("CA123", "nonexistent_preset")

        assert result.status == VMDropStatus.FAILED
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_drop_voicemail_no_audio_url(self, service):
        """Test VM drop when preset has no audio URL."""
        # Default presets have empty audio URLs
        result = await service.drop_voicemail("CA123", "intro_enterprise")

        assert result.status == VMDropStatus.FAILED
        assert "No audio URL" in result.error

    @pytest.mark.asyncio
    async def test_drop_voicemail_no_credentials(self):
        """Test VM drop without Twilio credentials."""
        service = VoicemailDropService()

        # Add a preset with audio URL
        await service.update_preset_audio_url("intro_smb", "https://example.com/audio.mp3")

        result = await service.drop_voicemail("CA123", "intro_smb")

        assert result.status == VMDropStatus.FAILED
        assert "credentials" in result.error.lower()

    @pytest.mark.asyncio
    async def test_drop_voicemail_success(self, service):
        """Test successful VM drop."""
        # Configure preset with audio URL
        await service.update_preset_audio_url("intro_smb", "https://example.com/audio.mp3")

        # Mock Twilio API
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.drop_voicemail("CA123", "intro_smb")

            assert result.status == VMDropStatus.PLAYING
            assert result.call_sid == "CA123"
            assert result.preset_id == "intro_smb"

    @pytest.mark.asyncio
    async def test_drop_voicemail_twilio_error(self, service):
        """Test VM drop with Twilio API error."""
        await service.update_preset_audio_url("intro_smb", "https://example.com/audio.mp3")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await service.drop_voicemail("CA123", "intro_smb")

            assert result.status == VMDropStatus.FAILED
            assert "400" in result.error

    @pytest.mark.asyncio
    async def test_get_vm_preset_by_segment(self, service):
        """Test VM preset selection by segment."""
        preset_id = await service.get_vm_preset("lead_123", lead_segment="enterprise")
        assert preset_id == "intro_enterprise"

        preset_id = await service.get_vm_preset("lead_456", lead_segment="smb")
        assert preset_id == "intro_smb"

        preset_id = await service.get_vm_preset("lead_789", lead_segment="demo")
        assert preset_id == "followup_demo"

    @pytest.mark.asyncio
    async def test_get_vm_preset_reengagement(self, service):
        """Test VM preset selection for cold leads."""
        preset_id = await service.get_vm_preset("lead_123", previous_interactions=5)
        assert preset_id == "reengagement"

    @pytest.mark.asyncio
    async def test_get_vm_preset_default(self, service):
        """Test default VM preset selection."""
        preset_id = await service.get_vm_preset("lead_123")
        assert preset_id == "intro_smb"

    @pytest.mark.asyncio
    async def test_get_vm_preset_ab_test(self, service):
        """Test VM preset selection with A/B test."""
        # Register A/B test
        await service.register_ab_test(
            test_name="intro_test",
            preset_ids=["intro_enterprise", "intro_smb"],
            lead_ids=["lead_123", "lead_456"]
        )

        # Should return A/B test assignment
        preset_id = await service.get_vm_preset("lead_123")
        assert preset_id == "intro_enterprise"

    @pytest.mark.asyncio
    async def test_register_ab_test(self, service):
        """Test A/B test registration."""
        assignments = await service.register_ab_test(
            test_name="test_intro",
            preset_ids=["intro_enterprise", "intro_smb"],
            lead_ids=["lead_1", "lead_2", "lead_3", "lead_4"]
        )

        assert len(assignments) == 4
        assert assignments["lead_1"] == "intro_enterprise"
        assert assignments["lead_2"] == "intro_smb"
        assert assignments["lead_3"] == "intro_enterprise"
        assert assignments["lead_4"] == "intro_smb"

    @pytest.mark.asyncio
    async def test_get_preset(self, service):
        """Test getting a preset by ID."""
        preset = await service.get_preset("intro_enterprise")

        assert preset is not None
        assert preset.id == "vm_intro_enterprise"
        assert preset.segment == "enterprise"

    @pytest.mark.asyncio
    async def test_get_preset_not_found(self, service):
        """Test getting non-existent preset."""
        preset = await service.get_preset("nonexistent")
        assert preset is None

    @pytest.mark.asyncio
    async def test_list_presets(self, service):
        """Test listing all presets."""
        presets = await service.list_presets()

        assert len(presets) >= 5  # Default presets
        assert all(p.active for p in presets)

    @pytest.mark.asyncio
    async def test_list_presets_include_inactive(self, service):
        """Test listing presets including inactive."""
        # Add inactive preset
        inactive = VMPreset(
            id="vm_inactive",
            name="Inactive",
            description="Test",
            audio_url="",
            duration_seconds=10,
            segment="test",
            active=False
        )
        await service.add_preset(inactive)

        all_presets = await service.list_presets(active_only=False)
        active_presets = await service.list_presets(active_only=True)

        assert len(all_presets) > len(active_presets)

    @pytest.mark.asyncio
    async def test_add_preset(self, service):
        """Test adding a new preset."""
        new_preset = VMPreset(
            id="vm_custom",
            name="Custom Preset",
            description="Custom VM",
            audio_url="https://example.com/custom.mp3",
            duration_seconds=15,
            segment="custom"
        )

        result = await service.add_preset(new_preset)

        assert result.id == "vm_custom"

        # Verify it's retrievable
        retrieved = await service.get_preset("vm_custom")
        assert retrieved.name == "Custom Preset"

    @pytest.mark.asyncio
    async def test_update_preset_audio_url(self, service):
        """Test updating preset audio URL."""
        new_url = "https://example.com/new_audio.mp3"

        result = await service.update_preset_audio_url("intro_enterprise", new_url)

        assert result is not None
        assert result.audio_url == new_url

    @pytest.mark.asyncio
    async def test_update_preset_audio_url_not_found(self, service):
        """Test updating non-existent preset."""
        result = await service.update_preset_audio_url("nonexistent", "https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_track_vm_result(self, service):
        """Test VM result tracking."""
        result = VMDropResult(
            call_sid="CA123",
            preset_id="intro_smb",
            status=VMDropStatus.COMPLETED,
            amd_result=AMDResult.MACHINE_END_BEEP,
            duration_played=25,
            timestamp=datetime.utcnow()
        )

        tracking_data = await service.track_vm_result(
            result=result,
            lead_id="lead_123",
            callback_received=False
        )

        assert tracking_data["call_sid"] == "CA123"
        assert tracking_data["preset_id"] == "intro_smb"
        assert tracking_data["status"] == "completed"
        assert tracking_data["amd_result"] == "machine_end_beep"


class TestDefaultVMPresets:
    """Tests for default VM presets."""

    def test_all_default_presets_exist(self):
        """Test all expected presets are defined."""
        expected = ["intro_enterprise", "intro_smb", "followup_demo",
                   "followup_pricing", "reengagement"]

        for preset_name in expected:
            assert preset_name in DEFAULT_VM_PRESETS

    def test_presets_have_required_fields(self):
        """Test presets have all required fields."""
        for name, preset in DEFAULT_VM_PRESETS.items():
            assert preset.id is not None
            assert preset.name is not None
            assert preset.description is not None
            assert preset.segment is not None
            assert preset.duration_seconds > 0


class TestAMDResult:
    """Tests for AMD result enum."""

    def test_amd_values(self):
        """Test all AMD result values."""
        assert AMDResult.HUMAN.value == "human"
        assert AMDResult.MACHINE_START.value == "machine_start"
        assert AMDResult.MACHINE_END_BEEP.value == "machine_end_beep"
        assert AMDResult.MACHINE_END_SILENCE.value == "machine_end_silence"
        assert AMDResult.FAX.value == "fax"
        assert AMDResult.UNKNOWN.value == "unknown"


class TestVMDropStatus:
    """Tests for VM drop status enum."""

    def test_status_values(self):
        """Test all status values."""
        assert VMDropStatus.PENDING.value == "pending"
        assert VMDropStatus.PLAYING.value == "playing"
        assert VMDropStatus.COMPLETED.value == "completed"
        assert VMDropStatus.FAILED.value == "failed"
        assert VMDropStatus.SKIPPED.value == "skipped"
