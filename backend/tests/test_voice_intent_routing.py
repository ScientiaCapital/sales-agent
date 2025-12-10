"""Tests for intent-based routing in VoiceAgent.

Following TDD principles - these tests are written before implementation
to drive the design of the intent routing feature.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.voice_agent import (
    VoiceAgent,
    TalkingNode,
    VoiceSession,
    VoiceTurn,
    ConversationState,
    VoiceEmotion
)
from app.services.voice.intent_classifier import SalesIntent, SalesIntentClassifier
from app.services.cartesia_service import VoiceConfig


class MockCartesiaService:
    """Mock Cartesia service for testing."""

    def __init__(self):
        self.tts_latency = 180
        self.stt_latency = 140
        self._active_streams = {}

    async def speech_to_text(self, audio_data: bytes, sample_rate: int = 16000, language: str = "en"):
        """Mock STT with configurable latency."""
        await asyncio.sleep(self.stt_latency / 1000)
        return {
            "transcript": "Hello, I'm interested in your product",
            "confidence": 0.95,
            "language": language,
            "latency_ms": self.stt_latency,
            "duration_ms": len(audio_data) / (sample_rate * 2) * 1000
        }

    async def create_voice_session(self, session_id: str, voice_config: VoiceConfig):
        """Mock voice session creation."""
        self._active_streams[session_id] = {
            "websocket": None,
            "voice_config": voice_config,
            "message_count": 0
        }
        return {"session_id": session_id, "status": "active"}

    async def close_voice_session(self, session_id: str):
        """Mock voice session closure."""
        if session_id in self._active_streams:
            del self._active_streams[session_id]

    async def stream_to_session(self, session_id: str, text: str):
        """Mock streaming to session."""
        mock_audio = b"streamed_audio_" + text.encode()[:50]
        for i in range(3):
            await asyncio.sleep(0.01)
            yield mock_audio[i*10:(i+1)*10]

    def get_performance_stats(self):
        """Mock performance stats."""
        return {
            "total_operations": 100,
            "error_rate": 0.02,
            "tts_latency": {"p50": 180, "p95": 220, "p99": 250, "mean": 185},
            "stt_latency": {"p50": 140, "p95": 180, "p99": 200, "mean": 145},
            "total_cost_usd": 0.15
        }


class MockCerebrasService:
    """Mock Cerebras service for testing with intent-aware responses."""

    def __init__(self):
        self.inference_latency = 600

    async def generate(self, prompt: str, system_prompt: str, temperature: float = 0.7, max_tokens: int = 150):
        """Mock AI inference with intent-aware responses."""
        await asyncio.sleep(self.inference_latency / 1000)

        # Generate response based on intent in the prompt
        response_text = "Thank you for your interest! Our product can help streamline your sales process."

        # Check for intent markers in the prompt to generate appropriate responses
        if "[Intent: meeting_schedule]" in prompt:
            response_text = "I'd be happy to schedule a meeting with you. I have availability tomorrow at 2pm or Thursday at 10am. Which time works better for you?"
        elif "[Intent: pricing_inquiry]" in prompt:
            response_text = "Our pricing starts at $99 per month for our basic plan, with enterprise tiers available. I can walk you through the different pricing options."
        elif "[Intent: product_info]" in prompt:
            response_text = "Our product offers automated lead scoring, real-time analytics, and seamless CRM integration. These features help you close deals faster."
        elif "[Intent: lead_qualification]" in prompt:
            response_text = "I'd love to learn more about your company and how we can help. What industry are you in and what's your current team size?"
        elif "[Intent: warm_transfer]" in prompt:
            response_text = "I'd be happy to connect you with one of our sales representatives who can help you further. Let me transfer you now."
        elif "[Intent: objection]" in prompt:
            response_text = "I completely understand. Thank you for your time today. If you'd like to revisit this in the future, feel free to reach out."

        return {
            "text": response_text,
            "latency_ms": self.inference_latency
        }


@pytest.fixture
def mock_voice_agent(monkeypatch):
    """Create a voice agent with mocked services."""
    # Mock CartesiaService to avoid requiring the SDK
    monkeypatch.setattr(
        'app.services.voice_agent.CartesiaService',
        lambda: MockCartesiaService()
    )

    agent = VoiceAgent()
    agent.cartesia = MockCartesiaService()
    agent.cerebras = MockCerebrasService()
    agent.talking_node = TalkingNode(agent.cerebras)
    return agent


@pytest.mark.asyncio
async def test_intent_classifier_integration(mock_voice_agent):
    """Test that VoiceAgent has integrated SalesIntentClassifier."""
    agent = mock_voice_agent

    # Verify intent classifier is initialized
    assert hasattr(agent, 'intent_classifier')
    assert isinstance(agent.intent_classifier, SalesIntentClassifier)


@pytest.mark.asyncio
async def test_voice_turn_includes_intent(mock_voice_agent):
    """Test that VoiceTurn includes the classified intent."""
    agent = mock_voice_agent

    # Create a session
    session = await agent.create_session(
        voice_id="test_voice",
        language="en",
        emotion=VoiceEmotion.PROFESSIONAL
    )

    # Mock STT to return a meeting-related query
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Can we schedule a demo?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    # Process voice turn
    mock_audio = b"test_audio_data" * 100
    intent_captured = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio,
        sample_rate=16000
    ):
        if chunk["type"] == "intent":
            intent_captured = chunk["intent"]

    # Verify intent was captured and is MEETING_SCHEDULE
    assert intent_captured == SalesIntent.MEETING_SCHEDULE.value


@pytest.mark.asyncio
async def test_meeting_schedule_intent_routing(mock_voice_agent):
    """Test routing for MEETING_SCHEDULE intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return meeting request
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "I'd like to schedule a call",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response mentions scheduling/meeting
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["meeting", "schedule", "calendar", "time", "available"])


@pytest.mark.asyncio
async def test_pricing_inquiry_intent_routing(mock_voice_agent):
    """Test routing for PRICING_INQUIRY intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return pricing question
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "How much does it cost?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response addresses pricing
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["price", "cost", "pricing", "plan", "tier"])


@pytest.mark.asyncio
async def test_product_info_intent_routing(mock_voice_agent):
    """Test routing for PRODUCT_INFO intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return product question
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Tell me about your product features",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response describes product/features
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["product", "feature", "offer", "help", "solution"])


@pytest.mark.asyncio
async def test_lead_qualification_intent_routing(mock_voice_agent):
    """Test routing for LEAD_QUALIFICATION intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return qualifying question
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Tell me about your company",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response asks qualifying questions
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["company", "business", "industry", "team", "size"])


@pytest.mark.asyncio
async def test_warm_transfer_intent_routing(mock_voice_agent):
    """Test routing for WARM_TRANSFER intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return transfer request
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "I'd like to speak to a human",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response offers to transfer
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["transfer", "connect", "representative", "colleague", "team member"])


@pytest.mark.asyncio
async def test_objection_intent_routing(mock_voice_agent):
    """Test routing for OBJECTION intent."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return objection
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Not interested, thanks",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]

    # Verify response acknowledges objection professionally
    assert response_text is not None
    assert any(keyword in response_text.lower() for keyword in ["understand", "respect", "appreciate", "thank"])


@pytest.mark.asyncio
async def test_general_intent_routing(mock_voice_agent):
    """Test routing for GENERAL intent (fallback)."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT to return general greeting
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Hello there",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"
    response_text = None
    intent_captured = None

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "response":
            response_text = chunk["text"]
        if chunk["type"] == "intent":
            intent_captured = chunk["intent"]

    # Verify GENERAL intent is used as fallback
    assert intent_captured == SalesIntent.GENERAL.value
    assert response_text is not None


@pytest.mark.asyncio
async def test_intent_logged_in_voice_turn(mock_voice_agent):
    """Test that intent is properly logged in VoiceTurn."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "What are your prices?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio"

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        pass  # Process all chunks

    # Verify the turn has intent recorded
    session_obj = agent.sessions[session.session_id]
    assert len(session_obj.turns) > 0

    last_turn = session_obj.turns[-1]
    assert hasattr(last_turn, 'intent')
    assert last_turn.intent == SalesIntent.PRICING_INQUIRY


@pytest.mark.asyncio
async def test_intent_context_in_talking_node(mock_voice_agent):
    """Test that intent is passed to TalkingNode for context-aware responses."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT with product inquiry
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "What features do you offer?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    # Spy on TalkingNode.reason to verify intent is passed
    original_reason = agent.talking_node.reason
    reason_calls = []

    async def spy_reason(transcript: str, context: dict, lead_data=None, intent=None):
        reason_calls.append({
            "transcript": transcript,
            "context": context,
            "intent": intent
        })
        return await original_reason(transcript, context, lead_data)

    agent.talking_node.reason = spy_reason

    mock_audio = b"test_audio"

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        pass

    # Verify reason was called with intent
    assert len(reason_calls) > 0
    assert reason_calls[0]["intent"] == SalesIntent.PRODUCT_INFO


@pytest.mark.asyncio
async def test_multiple_intents_in_conversation(mock_voice_agent):
    """Test that multiple intents can be handled in a single conversation."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Turn 1: Product inquiry
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Tell me about your product",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=b"audio1"
    ):
        pass

    # Turn 2: Pricing inquiry
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "How much does it cost?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=b"audio2"
    ):
        pass

    # Turn 3: Meeting request
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "Let's schedule a demo",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=b"audio3"
    ):
        pass

    # Verify all turns have different intents
    session_obj = agent.sessions[session.session_id]
    assert len(session_obj.turns) == 3

    assert session_obj.turns[0].intent == SalesIntent.PRODUCT_INFO
    assert session_obj.turns[1].intent == SalesIntent.PRICING_INQUIRY
    assert session_obj.turns[2].intent == SalesIntent.MEETING_SCHEDULE


@pytest.mark.asyncio
async def test_intent_routing_performance(mock_voice_agent):
    """Test that intent classification doesn't significantly impact latency."""
    agent = mock_voice_agent

    session = await agent.create_session()

    # Mock STT
    agent.cartesia.speech_to_text = AsyncMock(return_value={
        "transcript": "What are your prices?",
        "confidence": 0.95,
        "language": "en",
        "latency_ms": 140,
        "duration_ms": 1000
    })

    mock_audio = b"test_audio" * 100
    turn_metrics = {}

    async for chunk in agent.process_audio_turn(
        session_id=session.session_id,
        audio_data=mock_audio
    ):
        if chunk["type"] == "complete":
            turn_metrics = chunk["metrics"]

    # Intent classification should add negligible latency (< 10ms)
    # Overall latency should still meet 2000ms target
    assert turn_metrics["total_latency_ms"] < 2000
