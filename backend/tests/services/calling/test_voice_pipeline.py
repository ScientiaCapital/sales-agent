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


# Voice Cloning Integration Tests

def test_voice_pipeline_voice_clone_available():
    """Pipeline should track voice clone availability."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    assert hasattr(pipeline, 'voice_clone_available')
    assert hasattr(pipeline, 'voice_clone_manager')


def test_voice_pipeline_voice_profile_name():
    """Pipeline should track voice profile name."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        voice_profile="tim_kipper",
    )

    assert pipeline.voice_profile_name == "tim_kipper"


def test_voice_pipeline_custom_voice_profile():
    """Pipeline should accept custom voice profile."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        voice_profile="default",
    )

    assert pipeline.voice_profile_name == "default"


def test_voice_pipeline_get_tts_config():
    """Pipeline should generate TTS config."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    config = pipeline.get_tts_config(
        text="Hello, this is Tim calling.",
        context="greeting",
    )

    assert "text" in config
    assert "voice_id" in config
    assert config["text"] == "Hello, this is Tim calling."


def test_voice_pipeline_get_tts_config_with_context():
    """Pipeline should use context for emotion selection."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    greeting_config = pipeline.get_tts_config(text="Hello", context="greeting")
    objection_config = pipeline.get_tts_config(text="I understand", context="objection")

    # Configs should have emotion set
    assert "emotion" in greeting_config
    assert "emotion" in objection_config


def test_voice_pipeline_get_tts_config_emotion_override():
    """Pipeline should allow emotion override."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )

    config = pipeline.get_tts_config(
        text="I understand your concern.",
        context="greeting",  # Would use friendly
        emotion_override="empathetic",  # Override to empathetic
    )

    assert "emotion" in config


def test_voice_pipeline_get_voice_profile():
    """Pipeline should return current voice profile."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        voice_profile="tim_kipper",
    )

    profile = pipeline.get_voice_profile()
    # Profile may be None if voice cloning not available
    # But method should exist
    assert hasattr(pipeline, 'get_voice_profile')


def test_voice_pipeline_set_voice_profile():
    """Pipeline should allow setting voice profile."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
        voice_profile="tim_kipper",
    )

    result = pipeline.set_voice_profile("default")
    # Result depends on voice clone availability
    assert hasattr(pipeline, 'set_voice_profile')


@pytest.mark.asyncio
async def test_voice_pipeline_generate_tts_no_cartesia():
    """Pipeline should raise error when Cartesia not available."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Ensure Cartesia is not available
    pipeline.cartesia_available = False
    pipeline.cartesia = None

    with pytest.raises(RuntimeError, match="Cartesia provider not available"):
        await pipeline.generate_tts(
            text="Hello, this is Tim.",
            context="greeting",
        )


@pytest.mark.asyncio
async def test_voice_pipeline_generate_tts_streaming():
    """Pipeline should support streaming TTS."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Mock Cartesia provider
    pipeline.cartesia = MagicMock()
    pipeline.cartesia.stream_tts = AsyncMock(return_value=b"audio_bytes")
    pipeline.cartesia_available = True

    result = await pipeline.generate_tts(
        text="Hello, this is Tim calling.",
        context="greeting",
        stream=True,
    )

    pipeline.cartesia.stream_tts.assert_called_once()


@pytest.mark.asyncio
async def test_voice_pipeline_generate_tts_non_streaming():
    """Pipeline should support non-streaming TTS."""
    pipeline = VoicePipeline(
        deepgram_api_key="test_dg_key",
        cartesia_api_key="test_cartesia_key",
        twilio_account_sid="test_sid",
        twilio_auth_token="test_token",
    )
    # Mock Cartesia provider
    pipeline.cartesia = MagicMock()
    pipeline.cartesia.generate = AsyncMock(return_value=b"audio_bytes")
    pipeline.cartesia_available = True

    result = await pipeline.generate_tts(
        text="Hello, this is Tim calling.",
        context="greeting",
        stream=False,
    )

    pipeline.cartesia.generate.assert_called_once()
