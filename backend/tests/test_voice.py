"""
Tests for voice interaction features with mock Cartesia responses

Validates <2000ms latency targets and TalkingNode pattern.
"""

import asyncio
import json
import time
import base64
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocket

from app.services.voice_agent import (
    VoiceAgent,
    TalkingNode,
    VoiceSession,
    VoiceTurn,
    ConversationState,
    VoiceEmotion
)
from app.services.cartesia_service import CartesiaService, VoiceConfig, VoiceSpeed


class MockCartesiaService:
    """Mock Cartesia service for testing."""

    def __init__(self):
        self.tts_latency = 180  # Mock 180ms TTS latency
        self.stt_latency = 140  # Mock 140ms STT latency
        self._voice_cache = {}
        self._active_streams = {}
        self._metrics_buffer = []

    async def speech_to_text(self, audio_data: bytes, sample_rate: int = 16000, language: str = "en"):
        """Mock STT with configurable latency."""
        await asyncio.sleep(self.stt_latency / 1000)  # Simulate latency
        return {
            "transcript": "Hello, I'm interested in your product",
            "confidence": 0.95,
            "language": language,
            "latency_ms": self.stt_latency,
            "duration_ms": len(audio_data) / (sample_rate * 2) * 1000
        }

    async def text_to_speech(self, text: str, voice_config: VoiceConfig, stream: bool = False):
        """Mock TTS with configurable latency."""
        await asyncio.sleep(self.tts_latency / 1000)  # Simulate latency

        # Generate mock audio (just bytes for testing)
        mock_audio = b"mock_audio_data_" + text.encode()[:50]

        if stream:
            # Simulate streaming
            for i in range(3):
                await asyncio.sleep(0.01)  # Small delay between chunks
                yield mock_audio[i*10:(i+1)*10]
        else:
            yield mock_audio

    async def create_voice_session(self, session_id: str, voice_config: VoiceConfig):
        """Mock voice session creation."""
        self._active_streams[session_id] = {
            "websocket": None,
            "voice_config": voice_config,
            "created_at": time.time(),
            "message_count": 0
        }
        return {
            "session_id": session_id,
            "status": "active",
            "voice_id": voice_config.voice_id
        }

    async def close_voice_session(self, session_id: str):
        """Mock voice session closure."""
        if session_id in self._active_streams:
            del self._active_streams[session_id]

    async def stream_to_session(self, session_id: str, text: str):
        """Mock streaming to session."""
        # Simulate streaming audio chunks
        mock_audio = b"streamed_audio_" + text.encode()[:50]
        for i in range(3):
            await asyncio.sleep(0.01)
            yield mock_audio[i*10:(i+1)*10]

    async def list_voices(self):
        """Mock voice listing."""
        return [
            {"id": "voice1", "name": "Professional", "language": "en"},
            {"id": "voice2", "name": "Friendly", "language": "en"}
        ]

    def get_performance_stats(self):
        """Mock performance stats."""
        return {
            "total_operations": 100,
            "error_rate": 0.02,
            "tts_latency": {
                "p50": 180,
                "p95": 220,
                "p99": 250,
                "mean": 185
            },
            "stt_latency": {
                "p50": 140,
                "p95": 180,
                "p99": 200,
                "mean": 145
            },
            "total_cost_usd": 0.15
        }


class MockCerebrasService:
    """Mock Cerebras service for testing."""

    def __init__(self):
        self.inference_latency = 600  # Mock 600ms inference latency

    async def generate(self, prompt: str, system_prompt: str, temperature: float = 0.7, max_tokens: int = 150):
        """Mock AI inference with configurable latency."""
        await asyncio.sleep(self.inference_latency / 1000)  # Simulate latency
        return {
            "text": "Thank you for your interest! Our product can help streamline your sales process.",
            "latency_ms": self.inference_latency
        }


@pytest.fixture
def mock_voice_agent():
    """Create a voice agent with mocked services."""
    agent = VoiceAgent()
    agent.cartesia = MockCartesiaService()
    agent.cerebras = MockCerebrasService()
    agent.talking_node = TalkingNode(agent.cerebras)
    return agent


@pytest.mark.asyncio
async def test_voice_turn_latency(mock_voice_agent):
    """Test that voice turn completes within 2000ms target."""
    agent = mock_voice_agent

    # Create a session
    session = await agent.create_session(
        voice_id="test_voice",
        language="en",
        emotion=VoiceEmotion.PROFESSIONAL
    )

    # Mock audio data
    mock_audio = b"test_audio_data" * 100

    # Track metrics
    turn_metrics = {}

    # Process voice turn
    start_time = time.perf_counter()

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio,
        sample_rate=16000
    ):
        if chunk["type"] == "complete":
            turn_metrics = chunk["metrics"]

    total_time = (time.perf_counter() - start_time) * 1000

    # Verify latency targets
    assert turn_metrics["stt_latency_ms"] < 200, "STT latency exceeds 200ms target"
    assert turn_metrics["inference_latency_ms"] < 700, "Inference latency exceeds 700ms target"
    assert turn_metrics["tts_latency_ms"] < 250, "TTS latency exceeds 250ms target"
    assert turn_metrics["total_latency_ms"] < 2000, f"Total latency {turn_metrics['total_latency_ms']}ms exceeds 2000ms target"

    # Verify the actual measured time is close to the reported time
    assert abs(total_time - turn_metrics["total_latency_ms"]) < 100, "Reported latency doesn't match actual time"


@pytest.mark.asyncio
async def test_talking_node_reasoning():
    """Test the TalkingNode reasoning with context."""
    cerebras = MockCerebrasService()
    talking_node = TalkingNode(cerebras)

    # Test with lead context
    response = await talking_node.reason(
        transcript="Tell me about your pricing",
        context={
            "recent_turns": [
                {"user": "Hello", "assistant": "Hi there! How can I help?"}
            ]
        },
        lead_data={
            "company_name": "TechCorp",
            "industry": "Software"
        }
    )

    assert response is not None
    assert len(response) > 0
    assert "product" in response.lower() or "help" in response.lower()


@pytest.mark.asyncio
async def test_voice_session_management(mock_voice_agent):
    """Test voice session creation, management, and cleanup."""
    agent = mock_voice_agent

    # Create session
    session = await agent.create_session(
        lead_id=123,
        voice_id="test_voice",
        language="es",
        emotion=VoiceEmotion.EMPATHETIC
    )

    assert session.session_id is not None
    assert session.lead_id == 123
    assert session.voice_config.language == "es"
    assert session.voice_config.emotion == VoiceEmotion.EMPATHETIC
    assert session.state == ConversationState.IDLE

    # Get metrics (should be empty initially)
    metrics = await agent.get_session_metrics(session.session_id)
    assert metrics["total_turns"] == 0
    assert metrics["average_latency_ms"] == 0

    # Process a turn
    mock_audio = b"test_audio"
    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        pass  # Process the turn

    # Check updated metrics
    metrics = await agent.get_session_metrics(session.session_id)
    assert metrics["total_turns"] == 1
    assert metrics["average_latency_ms"] > 0

    # Close session
    await agent.close_session(session.session_id)

    # Verify session is closed
    assert session.session_id not in agent.sessions


@pytest.mark.asyncio
async def test_emotion_adjustment(mock_voice_agent):
    """Test dynamic emotion adjustment during conversation."""
    agent = mock_voice_agent

    # Create session with initial emotion
    session = await agent.create_session(
        voice_id="test_voice",
        emotion=VoiceEmotion.PROFESSIONAL
    )

    assert session.voice_config.emotion == VoiceEmotion.PROFESSIONAL

    # Adjust emotion
    await agent.adjust_voice_emotion(session.session_id, VoiceEmotion.EMPATHETIC)

    # Verify emotion changed
    assert agent.sessions[session.session_id].voice_config.emotion == VoiceEmotion.EMPATHETIC


@pytest.mark.asyncio
async def test_global_metrics_tracking(mock_voice_agent):
    """Test global performance metrics across sessions."""
    agent = mock_voice_agent

    # Process multiple turns across different sessions
    for i in range(3):
        session = await agent.create_session()

        mock_audio = b"test_audio" * 10
        async for chunk in agent.process_audio_turn(
            session_id=session.session_id,
            audio_data=mock_audio
        ):
            pass

    # Get global metrics
    global_metrics = agent.get_global_metrics()

    assert global_metrics["total_turns"] == 3
    assert global_metrics["average_latency_ms"] > 0
    assert "latency_p50" in global_metrics
    assert "latency_p95" in global_metrics
    assert "target_compliance_rate" in global_metrics

    # Verify Cartesia stats are included
    assert "cartesia_stats" in global_metrics
    assert global_metrics["cartesia_stats"]["total_operations"] > 0


@pytest.mark.asyncio
async def test_streaming_audio_chunks():
    """Test streaming audio output in chunks."""
    cartesia = MockCartesiaService()
    voice_config = VoiceConfig(
        voice_id="test_voice",
        language="en",
        emotion=VoiceEmotion.PROFESSIONAL
    )

    chunks_received = []

    async for chunk in cartesia.text_to_speech(
        text="Hello world",
        voice_config=voice_config,
        stream=True
    ):
        chunks_received.append(chunk)

    # Verify we received multiple chunks
    assert len(chunks_received) > 0

    # Verify total audio data
    total_audio = b"".join(chunks_received)
    assert len(total_audio) > 0


@pytest.mark.asyncio
async def test_conversation_context_management(mock_voice_agent):
    """Test that conversation context is properly maintained."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Process multiple turns
    for i in range(3):
        mock_audio = b"test_audio" * 10
        async for chunk in agent.process_audio_turn(
            session_id=session.session_id,
            audio_data=mock_audio
        ):
            pass

    # Check context is maintained
    session = agent.sessions[session.session_id]
    assert "recent_turns" in session.context
    assert len(session.context["recent_turns"]) == 3

    # Verify each turn has user and assistant parts
    for turn in session.context["recent_turns"]:
        assert "user" in turn
        assert "assistant" in turn


@pytest.mark.asyncio
async def test_error_handling(mock_voice_agent):
    """Test error handling in voice processing."""
    agent = mock_voice_agent

    # Create session
    session = await agent.create_session()

    # Mock an error in STT
    original_stt = agent.cartesia.speech_to_text
    agent.cartesia.speech_to_text = AsyncMock(side_effect=Exception("STT failed"))

    # Process turn and expect error
    error_received = False
    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=b"test"
    ):
        if chunk["type"] == "error":
            error_received = True
            assert "STT failed" in chunk["error"]

    assert error_received
    assert session.state == ConversationState.ERROR

    # Restore original method
    agent.cartesia.speech_to_text = original_stt


@pytest.mark.asyncio
async def test_latency_compliance():
    """Test that we meet latency targets consistently."""
    # Create agent with specific latencies
    agent = VoiceAgent()
    agent.cartesia = MockCartesiaService()
    agent.cartesia.tts_latency = 190  # Just under 200ms target
    agent.cartesia.stt_latency = 145  # Just under 150ms target
    agent.cerebras = MockCerebrasService()
    agent.cerebras.inference_latency = 620  # Just under 633ms target
    agent.talking_node = TalkingNode(agent.cerebras)

    # Run multiple turns
    compliant_turns = 0
    total_turns = 10

    session = await agent.create_session()

    for _ in range(total_turns):
        mock_audio = b"test_audio" * 50

        async for chunk in agent.process_audio_turn(
            session_id=session.session_id,
            audio_data=mock_audio
        ):
            if chunk["type"] == "complete":
                if chunk["metrics"]["total_latency_ms"] < 2000:
                    compliant_turns += 1

    # Calculate compliance rate
    compliance_rate = compliant_turns / total_turns

    # We should have very high compliance with these latencies
    assert compliance_rate >= 0.9, f"Compliance rate {compliance_rate} is below 90%"

    # Verify global metrics reflect this
    global_metrics = agent.get_global_metrics()
    assert global_metrics["target_compliance_rate"] >= 0.9