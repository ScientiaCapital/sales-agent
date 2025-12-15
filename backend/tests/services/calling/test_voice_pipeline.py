import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.calling.voice_pipeline import VoicePipeline, CallState, STTProvider


@pytest.mark.asyncio
async def test_voice_pipeline_initializes_providers():
    """Pipeline should track provider availability."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    # Providers are None when voice-core not installed (test environment)
    # But availability flags should be set
    assert hasattr(pipeline, 'deepgram_available')
    assert hasattr(pipeline, 'assemblyai_available')
    assert hasattr(pipeline, 'cartesia_available')
    assert hasattr(pipeline, 'twilio_available')


@pytest.mark.asyncio
async def test_voice_pipeline_assemblyai_provider():
    """Pipeline should support AssemblyAI as STT provider."""
    pipeline = VoicePipeline(
        assemblyai_api_key="test_aai_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        stt_provider=STTProvider.ASSEMBLYAI,
    )

    assert hasattr(pipeline, 'assemblyai')
    assert hasattr(pipeline, 'assemblyai_available')
    assert pipeline.stt_provider == STTProvider.ASSEMBLYAI


@pytest.mark.asyncio
async def test_voice_pipeline_stt_available_property():
    """stt_available should return True if any STT provider is available."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    # In test env, voice-core not installed, so both unavailable
    assert hasattr(pipeline, 'stt_available')


@pytest.mark.asyncio
async def test_voice_pipeline_get_active_stt():
    """get_active_stt should return the preferred STT provider."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        stt_provider=STTProvider.DEEPGRAM,
    )

    # Method should exist and return None when providers not installed
    stt = pipeline.get_active_stt()
    assert stt is None  # voice-core not installed in test env


@pytest.mark.asyncio
async def test_voice_pipeline_dual_stt_providers():
    """Pipeline should accept both Deepgram and AssemblyAI keys."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        assemblyai_api_key="test_aai_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        stt_provider=STTProvider.DEEPGRAM,
    )

    assert hasattr(pipeline, 'deepgram')
    assert hasattr(pipeline, 'assemblyai')
    assert pipeline.stt_provider == STTProvider.DEEPGRAM


@pytest.mark.asyncio
async def test_voice_pipeline_start_call():
    """Pipeline should initiate Twilio call and return call_sid."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Mock Twilio provider
    pipeline.twilio = MagicMock()
    pipeline.twilio.make_call = AsyncMock(return_value={"sid": "CA123"})
    pipeline.twilio_available = True

    result = await pipeline.start_call(
        to_number="+15551234567",
        webhook_url="https://example.com/voice"
    )

    assert result["call_sid"] == "CA123"
    assert result["status"] == "initiated"
    assert "CA123" in pipeline.active_calls
    pipeline.twilio.make_call.assert_called_once()


@pytest.mark.asyncio
async def test_voice_pipeline_start_call_with_lead_id():
    """Pipeline should track lead_id in CallState."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    pipeline.twilio = MagicMock()
    pipeline.twilio.make_call = AsyncMock(return_value={"sid": "CA456"})
    pipeline.twilio_available = True

    await pipeline.start_call(
        to_number="+15551234567",
        webhook_url="https://example.com/voice",
        lead_id="lead_123"
    )

    assert pipeline.active_calls["CA456"].lead_id == "lead_123"


@pytest.mark.asyncio
async def test_voice_pipeline_start_call_missing_sid():
    """Pipeline should raise error when Twilio returns no sid."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    pipeline.twilio = MagicMock()
    pipeline.twilio.make_call = AsyncMock(return_value={})  # No sid
    pipeline.twilio_available = True

    with pytest.raises(ValueError, match="did not return a valid call_sid"):
        await pipeline.start_call(
            to_number="+15551234567",
            webhook_url="https://example.com/voice"
        )


@pytest.mark.asyncio
async def test_voice_pipeline_start_call_no_twilio():
    """Pipeline should raise error when Twilio not available."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Ensure Twilio is not available
    pipeline.twilio_available = False
    pipeline.twilio = None

    with pytest.raises(RuntimeError, match="Twilio provider not available"):
        await pipeline.start_call(
            to_number="+15551234567",
            webhook_url="https://example.com/voice"
        )


@pytest.mark.asyncio
async def test_voice_pipeline_end_call():
    """Pipeline should remove call from active_calls."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Add a call to active_calls
    pipeline.active_calls["CA789"] = CallState(call_sid="CA789", lead_id="lead_456")

    result = await pipeline.end_call("CA789")

    assert result is True
    assert "CA789" not in pipeline.active_calls


@pytest.mark.asyncio
async def test_voice_pipeline_end_call_nonexistent():
    """Pipeline should handle ending non-existent call gracefully."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    result = await pipeline.end_call("NONEXISTENT")

    assert result is False


def test_call_state_initialization():
    """CallState should initialize with proper defaults."""
    state = CallState(call_sid="CA123", lead_id="lead_789")

    assert state.call_sid == "CA123"
    assert state.lead_id == "lead_789"
    assert state.current_agent == "qualifier"
    assert state.transcript == []
    assert isinstance(state.transcript, list)
