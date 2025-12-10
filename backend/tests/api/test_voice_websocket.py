"""
Tests for Twilio Media Stream WebSocket handler

Tests real-time audio streaming with STT, LLM, and TTS pipeline.
Validates Twilio protocol compliance and latency targets.
"""

import asyncio
import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket


# Mock services
class MockDeepgramService:
    """Mock Deepgram STT service."""

    def __init__(self, config=None):
        self.config = config
        self.latency_ms = 150

    async def transcribe(self, audio_bytes: bytes):
        """Mock transcription with configurable latency."""
        await asyncio.sleep(self.latency_ms / 1000)

        return MagicMock(
            transcript="I'm interested in your product",
            confidence=0.95,
            latency_ms=self.latency_ms
        )


class MockCartesiaService:
    """Mock Cartesia TTS service."""

    def __init__(self):
        self.latency_ms = 180

    async def text_to_speech(self, text: str, voice_config, stream: bool = False):
        """Mock TTS with streaming support."""
        await asyncio.sleep(self.latency_ms / 1000)

        # Generate mock PCM audio (simulated)
        mock_pcm = b"mock_pcm_audio_data" * 100

        if stream:
            # Yield audio in chunks
            chunk_size = len(mock_pcm) // 3
            for i in range(3):
                yield mock_pcm[i * chunk_size:(i + 1) * chunk_size]
        else:
            yield mock_pcm


class MockCerebrasService:
    """Mock Cerebras LLM service."""

    def __init__(self):
        self.latency_ms = 600

    def qualify_lead(self, **kwargs):
        """Mock lead qualification."""
        import time
        time.sleep(self.latency_ms / 1000)
        return (
            75.0,
            "Strong fit based on company size and industry",
            self.latency_ms
        )


class MockIntentClassifier:
    """Mock intent classifier."""

    def classify_intent(self, query: str):
        """Mock intent classification."""
        from app.services.voice.intent_classifier import SalesIntent

        if "price" in query.lower() or "cost" in query.lower():
            return SalesIntent.PRICING_INQUIRY
        elif "meeting" in query.lower() or "schedule" in query.lower():
            return SalesIntent.MEETING_SCHEDULE
        else:
            return SalesIntent.GENERAL


# ==================== Audio Conversion Tests ====================

@pytest.mark.asyncio
async def test_mulaw_to_linear16_conversion():
    """Test mulaw to linear16 PCM conversion."""
    from app.api.voice_websocket import mulaw_to_linear16

    # Create mock mulaw audio (8kHz)
    mock_mulaw = b"\x00\x01\x02\x03\x04\x05" * 10

    # Convert to linear16
    linear16 = mulaw_to_linear16(mock_mulaw, target_sample_rate=16000)

    # Verify output is bytes
    assert isinstance(linear16, bytes)

    # Verify upsampling (should be ~2x size due to 8kHz -> 16kHz)
    # Linear16 is 16-bit (2 bytes per sample), mulaw is 8-bit (1 byte per sample)
    # So: 60 mulaw bytes * 2 (upsampling) * 2 (16-bit encoding) = 240 bytes
    assert len(linear16) > len(mock_mulaw)


@pytest.mark.asyncio
async def test_linear16_to_mulaw_conversion():
    """Test linear16 PCM to mulaw conversion."""
    from app.api.voice_websocket import linear16_to_mulaw

    # Create mock linear16 audio (16kHz, 16-bit)
    # 100 samples = 200 bytes (2 bytes per sample)
    mock_linear16 = b"\x00\x01" * 100

    # Convert to mulaw
    mulaw = linear16_to_mulaw(mock_linear16, source_sample_rate=16000)

    # Verify output is bytes
    assert isinstance(mulaw, bytes)

    # Verify downsampling (should be ~1/4 size due to 16kHz -> 8kHz + 16bit -> 8bit)
    assert len(mulaw) < len(mock_linear16)


@pytest.mark.asyncio
async def test_base64_mulaw_decoding():
    """Test decoding base64-encoded mulaw from Twilio."""
    from app.api.voice_websocket import decode_twilio_audio

    # Create base64-encoded mulaw
    mulaw_data = b"\x00\x01\x02\x03"
    base64_encoded = base64.b64encode(mulaw_data).decode('utf-8')

    # Decode
    decoded = decode_twilio_audio(base64_encoded)

    # Verify decoding
    assert decoded == mulaw_data


@pytest.mark.asyncio
async def test_base64_mulaw_encoding():
    """Test encoding mulaw to base64 for Twilio."""
    from app.api.voice_websocket import encode_twilio_audio

    # Create mulaw data
    mulaw_data = b"\x00\x01\x02\x03"

    # Encode
    encoded = encode_twilio_audio(mulaw_data)

    # Verify it's base64 string
    assert isinstance(encoded, str)

    # Verify round-trip
    decoded = base64.b64decode(encoded)
    assert decoded == mulaw_data


# ==================== WebSocket Connection Tests ====================

@pytest.mark.asyncio
async def test_websocket_connection_handling():
    """Test WebSocket connection accept and setup."""
    from app.api.voice_websocket import handle_voice_websocket

    # Create mock WebSocket
    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.receive_json = AsyncMock(side_effect=[
        # First message: connected event
        {"event": "connected", "protocol": "Call", "version": "1.0.0"},
        # Second message: start event
        {
            "event": "start",
            "streamSid": "MZ123456789",
            "start": {
                "streamSid": "MZ123456789",
                "accountSid": "AC123",
                "callSid": "CA123"
            }
        },
        # Then stop
        {"event": "stop"}
    ])
    mock_ws.send_json = AsyncMock()

    # Handle WebSocket (should process events)
    with patch('app.api.voice_websocket.DeepgramService', MockDeepgramService), \
         patch('app.api.voice_websocket.CartesiaService', MockCartesiaService), \
         patch('app.api.voice_websocket.CerebrasService', MockCerebrasService), \
         patch('app.api.voice_websocket.SalesIntentClassifier', MockIntentClassifier):

        await handle_voice_websocket(mock_ws)

    # Verify WebSocket was accepted
    mock_ws.accept.assert_called_once()

    # Verify we sent messages back
    assert mock_ws.send_json.call_count >= 1


@pytest.mark.asyncio
async def test_websocket_media_event_processing():
    """Test processing of Twilio media events with audio."""
    from app.api.voice_websocket import handle_voice_websocket

    # Create mock mulaw audio and encode to base64
    mock_mulaw = b"\x00\x01\x02\x03" * 20  # 80 bytes of mulaw
    base64_payload = base64.b64encode(mock_mulaw).decode('utf-8')

    # Create mock WebSocket
    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()

    # Simulate Twilio event sequence
    mock_ws.receive_json = AsyncMock(side_effect=[
        {"event": "connected", "protocol": "Call", "version": "1.0.0"},
        {
            "event": "start",
            "streamSid": "MZ123",
            "start": {"streamSid": "MZ123", "accountSid": "AC123", "callSid": "CA123"}
        },
        # Media event with audio payload
        {
            "event": "media",
            "streamSid": "MZ123",
            "media": {
                "payload": base64_payload,
                "timestamp": "1234567890"
            }
        },
        {"event": "stop"}
    ])
    mock_ws.send_json = AsyncMock()

    # Mock services
    with patch('app.api.voice_websocket.DeepgramService', MockDeepgramService), \
         patch('app.api.voice_websocket.CartesiaService', MockCartesiaService), \
         patch('app.api.voice_websocket.CerebrasService', MockCerebrasService), \
         patch('app.api.voice_websocket.SalesIntentClassifier', MockIntentClassifier):

        await handle_voice_websocket(mock_ws)

    # Verify we processed the audio and sent response
    # Should have sent at least: mark event + media event with TTS audio
    assert mock_ws.send_json.call_count >= 2


@pytest.mark.asyncio
async def test_websocket_stop_event():
    """Test proper handling of stop event."""
    from app.api.voice_websocket import handle_voice_websocket

    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.receive_json = AsyncMock(side_effect=[
        {"event": "connected", "protocol": "Call", "version": "1.0.0"},
        {"event": "start", "streamSid": "MZ123", "start": {}},
        {"event": "stop", "streamSid": "MZ123"}
    ])
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    with patch('app.api.voice_websocket.DeepgramService', MockDeepgramService), \
         patch('app.api.voice_websocket.CartesiaService', MockCartesiaService), \
         patch('app.api.voice_websocket.CerebrasService', MockCerebrasService), \
         patch('app.api.voice_websocket.SalesIntentClassifier', MockIntentClassifier):

        await handle_voice_websocket(mock_ws)

    # Verify WebSocket was closed cleanly
    mock_ws.close.assert_called_once()


# ==================== Audio Pipeline Tests ====================

@pytest.mark.asyncio
async def test_stt_pipeline():
    """Test speech-to-text pipeline with Deepgram."""
    from app.api.voice_websocket import process_stt

    # Mock mulaw audio
    mock_mulaw = b"\x00\x01\x02" * 100

    # Mock Deepgram service
    mock_deepgram = MockDeepgramService()

    # Process STT
    transcript, confidence, latency_ms = await process_stt(mock_mulaw, mock_deepgram)

    # Verify results
    assert isinstance(transcript, str)
    assert len(transcript) > 0
    assert 0.0 <= confidence <= 1.0
    assert latency_ms > 0
    assert latency_ms < 300  # Should be under 300ms


@pytest.mark.asyncio
async def test_tts_pipeline():
    """Test text-to-speech pipeline with Cartesia."""
    from app.api.voice_websocket import process_tts

    text = "Thank you for your interest in our product"

    # Mock Cartesia service
    mock_cartesia = MockCartesiaService()

    # Mock voice config
    from app.services.cartesia_service import VoiceConfig
    voice_config = VoiceConfig(
        voice_id="test_voice_id",
        model="sonic-turbo",
        sample_rate=8000  # Twilio uses 8kHz
    )

    # Process TTS
    mulaw_audio, latency_ms = await process_tts(text, voice_config, mock_cartesia)

    # Verify results
    assert isinstance(mulaw_audio, bytes)
    assert len(mulaw_audio) > 0
    assert latency_ms > 0
    assert latency_ms < 300  # Should be under 300ms


@pytest.mark.asyncio
async def test_intent_classification():
    """Test intent classification integration."""
    from app.api.voice_websocket import classify_and_route
    from app.services.voice.intent_classifier import SalesIntent

    # Test pricing inquiry
    intent, response = await classify_and_route(
        transcript="How much does it cost?",
        classifier=MockIntentClassifier(),
        cerebras=MockCerebrasService()
    )

    assert intent == SalesIntent.PRICING_INQUIRY
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_llm_response_generation():
    """Test LLM response generation with Cerebras."""
    from app.api.voice_websocket import generate_llm_response
    from app.services.voice.intent_classifier import SalesIntent

    # Generate response for general inquiry
    response, latency_ms = await generate_llm_response(
        transcript="Tell me about your company",
        intent=SalesIntent.GENERAL,
        cerebras=MockCerebrasService()
    )

    # Verify response
    assert isinstance(response, str)
    assert len(response) > 0
    assert latency_ms > 0


# ==================== End-to-End Pipeline Tests ====================

@pytest.mark.asyncio
async def test_full_turn_pipeline():
    """Test complete turn: STT -> Intent -> LLM -> TTS."""
    from app.api.voice_websocket import process_audio_turn
    from app.services.cartesia_service import VoiceConfig

    # Mock audio input (mulaw from Twilio)
    mock_mulaw_input = b"\x00\x01\x02" * 200

    # Mock services
    deepgram = MockDeepgramService()
    cartesia = MockCartesiaService()
    cerebras = MockCerebrasService()
    classifier = MockIntentClassifier()

    voice_config = VoiceConfig(
        voice_id="test_voice",
        model="sonic-turbo",
        sample_rate=8000
    )

    # Process complete turn
    result = await process_audio_turn(
        audio_mulaw=mock_mulaw_input,
        deepgram=deepgram,
        cartesia=cartesia,
        cerebras=cerebras,
        classifier=classifier,
        voice_config=voice_config
    )

    # Verify result structure
    assert "transcript" in result
    assert "intent" in result
    assert "response_text" in result
    assert "response_audio" in result  # mulaw audio
    assert "latency_breakdown" in result

    # Verify audio output is mulaw
    assert isinstance(result["response_audio"], bytes)

    # Verify latency tracking
    latency = result["latency_breakdown"]
    assert "stt_ms" in latency
    assert "llm_ms" in latency
    assert "tts_ms" in latency
    assert "total_ms" in latency

    # Verify total latency is reasonable
    assert latency["total_ms"] < 2000  # Under 2 seconds target


@pytest.mark.asyncio
async def test_turn_latency_targets():
    """Test that we meet latency targets for real-time conversation."""
    from app.api.voice_websocket import process_audio_turn
    from app.services.cartesia_service import VoiceConfig

    # Create services with realistic latencies
    deepgram = MockDeepgramService()
    deepgram.latency_ms = 140  # Deepgram Nova-2 target

    cartesia = MockCartesiaService()
    cartesia.latency_ms = 90  # Cartesia sonic-turbo target

    cerebras = MockCerebrasService()
    cerebras.latency_ms = 600  # Cerebras llama3.1-8b target

    classifier = MockIntentClassifier()

    voice_config = VoiceConfig(
        voice_id="test_voice",
        model="sonic-turbo",
        sample_rate=8000
    )

    # Process turn
    mock_audio = b"\x00" * 200
    result = await process_audio_turn(
        audio_mulaw=mock_audio,
        deepgram=deepgram,
        cartesia=cartesia,
        cerebras=cerebras,
        classifier=classifier,
        voice_config=voice_config
    )

    latency = result["latency_breakdown"]

    # Verify individual component targets
    assert latency["stt_ms"] < 200, f"STT latency {latency['stt_ms']}ms exceeds 200ms target"
    assert latency["llm_ms"] < 700, f"LLM latency {latency['llm_ms']}ms exceeds 700ms target"
    assert latency["tts_ms"] < 150, f"TTS latency {latency['tts_ms']}ms exceeds 150ms target"

    # Verify total latency target (STT + LLM + TTS + overhead < 1200ms)
    assert latency["total_ms"] < 1200, f"Total latency {latency['total_ms']}ms exceeds 1200ms target"


@pytest.mark.asyncio
async def test_error_handling_in_pipeline():
    """Test graceful error handling in audio pipeline."""
    from app.api.voice_websocket import process_audio_turn
    from app.services.cartesia_service import VoiceConfig

    # Mock Deepgram to raise error
    deepgram = MockDeepgramService()
    deepgram.transcribe = AsyncMock(side_effect=Exception("STT failed"))

    cartesia = MockCartesiaService()
    cerebras = MockCerebrasService()
    classifier = MockIntentClassifier()

    voice_config = VoiceConfig(voice_id="test", model="sonic-turbo", sample_rate=8000)

    # Process turn (should handle error gracefully)
    with pytest.raises(Exception) as exc_info:
        await process_audio_turn(
            audio_mulaw=b"\x00" * 100,
            deepgram=deepgram,
            cartesia=cartesia,
            cerebras=cerebras,
            classifier=classifier,
            voice_config=voice_config
        )

    assert "STT failed" in str(exc_info.value)


# ==================== Twilio Protocol Tests ====================

@pytest.mark.asyncio
async def test_twilio_media_event_format():
    """Test Twilio media event format compliance."""
    from app.api.voice_websocket import create_media_event

    # Create audio payload
    mulaw_audio = b"\x00\x01\x02\x03"
    stream_sid = "MZ123456"

    # Create media event
    event = create_media_event(stream_sid, mulaw_audio)

    # Verify Twilio format
    assert event["event"] == "media"
    assert event["streamSid"] == stream_sid
    assert "media" in event
    assert "payload" in event["media"]

    # Verify payload is base64
    payload = event["media"]["payload"]
    decoded = base64.b64decode(payload)
    assert decoded == mulaw_audio


@pytest.mark.asyncio
async def test_twilio_mark_event_format():
    """Test Twilio mark event format for timing."""
    from app.api.voice_websocket import create_mark_event

    stream_sid = "MZ123456"
    mark_name = "audio_complete"

    # Create mark event
    event = create_mark_event(stream_sid, mark_name)

    # Verify Twilio format
    assert event["event"] == "mark"
    assert event["streamSid"] == stream_sid
    assert event["mark"]["name"] == mark_name


@pytest.mark.asyncio
async def test_multiple_media_events():
    """Test handling multiple consecutive media events (continuous speech)."""
    from app.api.voice_websocket import handle_voice_websocket

    # Create multiple media events (simulating continuous speech)
    mock_mulaw = b"\x00\x01" * 40
    base64_payload = base64.b64encode(mock_mulaw).decode('utf-8')

    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.receive_json = AsyncMock(side_effect=[
        {"event": "connected", "protocol": "Call", "version": "1.0.0"},
        {"event": "start", "streamSid": "MZ123", "start": {}},
        # Multiple media events
        {"event": "media", "streamSid": "MZ123", "media": {"payload": base64_payload}},
        {"event": "media", "streamSid": "MZ123", "media": {"payload": base64_payload}},
        {"event": "media", "streamSid": "MZ123", "media": {"payload": base64_payload}},
        {"event": "stop"}
    ])
    mock_ws.send_json = AsyncMock()

    with patch('app.api.voice_websocket.DeepgramService', MockDeepgramService), \
         patch('app.api.voice_websocket.CartesiaService', MockCartesiaService), \
         patch('app.api.voice_websocket.CerebrasService', MockCerebrasService), \
         patch('app.api.voice_websocket.SalesIntentClassifier', MockIntentClassifier):

        await handle_voice_websocket(mock_ws)

    # Should have processed media events (may buffer before processing)
    assert mock_ws.send_json.call_count >= 1
