"""
Voice Agent with TalkingNode Pattern - Real-time conversational AI

Implements the TalkingNode architecture for sub-2000ms voice turns:
1. Speech-to-text (Cartesia/Deepgram)
2. AI reasoning (Cerebras ultra-fast)
3. Text-to-speech (Cartesia)
4. WebSocket streaming

Based on Cerebras's ReasoningNode pattern for minimal latency.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, AsyncIterator, List
from uuid import uuid4

import redis.asyncio as redis

from .cartesia_service import CartesiaService, VoiceConfig, VoiceEmotion, VoiceSpeed
from .cerebras import CerebrasService
from app.core.exceptions import VoiceSessionNotFoundError

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """Voice conversation states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceTurn:
    """A single turn in the voice conversation."""
    turn_id: str
    user_audio: Optional[bytes] = None
    user_transcript: Optional[str] = None
    ai_response: Optional[str] = None
    ai_audio: Optional[bytes] = None
    stt_latency_ms: Optional[int] = None
    inference_latency_ms: Optional[int] = None
    tts_latency_ms: Optional[int] = None
    total_latency_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class VoiceSession:
    """Voice conversation session."""
    session_id: str
    lead_id: Optional[int] = None
    voice_config: Optional[VoiceConfig] = None
    state: ConversationState = ConversationState.IDLE
    turns: List[VoiceTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    total_turns: int = 0
    average_latency_ms: float = 0.0


class TalkingNode:
    """
    The core reasoning node for voice conversations.

    Implements ultra-fast decision making based on conversation context,
    similar to Cerebras's ReasoningNode pattern but optimized for voice.
    """

    def __init__(self, cerebras_service: CerebrasService):
        """Initialize the TalkingNode."""
        self.cerebras = cerebras_service
        self.system_prompt = """You are a friendly and professional AI sales assistant having a voice conversation.
Keep responses concise and natural for speech - typically 1-3 sentences.
Be conversational and avoid long monologues.
Focus on understanding the customer's needs and providing helpful information.
If you don't understand something, ask for clarification naturally."""

    async def reason(
        self,
        transcript: str,
        context: Dict[str, Any],
        lead_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate AI response with ultra-fast reasoning.

        Args:
            transcript: User's speech transcript
            context: Conversation context
            lead_data: Optional lead information

        Returns:
            AI response text optimized for speech
        """
        # Build context-aware prompt
        prompt = self._build_prompt(transcript, context, lead_data)

        # Use Cerebras for ultra-fast inference
        response = await self.cerebras.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=0.7,
            max_tokens=150  # Keep responses concise for voice
        )

        return response.get("text", "I'm sorry, I didn't catch that. Could you repeat?")

    def _build_prompt(
        self,
        transcript: str,
        context: Dict[str, Any],
        lead_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build context-aware prompt for reasoning."""
        prompt_parts = []

        # Add lead context if available
        if lead_data:
            prompt_parts.append(f"Customer: {lead_data.get('company_name', 'Unknown')}")
            prompt_parts.append(f"Industry: {lead_data.get('industry', 'Unknown')}")
            prompt_parts.append("")

        # Add recent conversation history
        if "recent_turns" in context:
            prompt_parts.append("Recent conversation:")
            for turn in context["recent_turns"][-3:]:  # Last 3 turns
                if turn.get("user"):
                    prompt_parts.append(f"User: {turn['user']}")
                if turn.get("assistant"):
                    prompt_parts.append(f"Assistant: {turn['assistant']}")
            prompt_parts.append("")

        # Add current user input
        prompt_parts.append(f"User says: {transcript}")
        prompt_parts.append("")
        prompt_parts.append("Respond naturally and concisely:")

        return "\n".join(prompt_parts)


class VoiceAgent:
    """
    Real-time voice agent orchestrating the complete voice pipeline.

    Architecture:
    1. Audio Input → STT (150ms)
    2. STT → AI Reasoning (633ms)
    3. AI → TTS (200ms)
    4. TTS → Audio Output
    Total target: <2000ms turn latency
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize voice agent with all required services."""
        # Initialize services
        self.cartesia = CartesiaService()
        self.cerebras = CerebrasService()
        self.talking_node = TalkingNode(self.cerebras)

        # Redis for session management
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.redis_client: Optional[redis.Redis] = None

        # Active sessions
        self.sessions: Dict[str, VoiceSession] = {}

        # Performance tracking
        self.latency_buffer: List[int] = []
        self.max_buffer_size = 100

        logger.info("VoiceAgent initialized with TalkingNode pattern")

    async def initialize(self):
        """Initialize async resources."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(self.redis_url)
            logger.info("Redis client initialized for session management")

    async def create_session(
        self,
        session_id: Optional[str] = None,
        lead_id: Optional[int] = None,
        voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",  # Default voice
        language: str = "en",
        emotion: Optional[VoiceEmotion] = VoiceEmotion.PROFESSIONAL
    ) -> VoiceSession:
        """
        Create a new voice session.

        Args:
            session_id: Optional session ID (generated if not provided)
            lead_id: Optional lead ID for context
            voice_id: Cartesia voice ID
            language: Language code
            emotion: Initial voice emotion

        Returns:
            Created VoiceSession
        """
        if not session_id:
            session_id = str(uuid4())

        # Configure voice
        voice_config = VoiceConfig(
            voice_id=voice_id,
            language=language,
            emotion=emotion,
            speed=VoiceSpeed.NORMAL
        )

        # Create Cartesia voice session
        await self.cartesia.create_voice_session(session_id, voice_config)

        # Create session object
        session = VoiceSession(
            session_id=session_id,
            lead_id=lead_id,
            voice_config=voice_config,
            state=ConversationState.IDLE
        )

        # Store session
        self.sessions[session_id] = session

        # Persist to Redis
        await self._save_session_to_redis(session)

        logger.info(f"Created voice session: {session_id}")
        return session

    async def process_audio_turn(
        self,
        session_id: str,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Process a complete voice turn with streaming response.

        This is the main entry point for voice interaction, implementing
        the complete TalkingNode pattern with minimal latency.

        Args:
            session_id: Session identifier
            audio_data: User's audio input
            sample_rate: Audio sample rate

        Yields:
            Dict chunks with status updates and audio data
        """
        if session_id not in self.sessions:
            raise VoiceSessionNotFoundError(f"Session {session_id} not found", context={"session_id": session_id})

        session = self.sessions[session_id]
        turn_id = str(uuid4())
        turn = VoiceTurn(turn_id=turn_id, user_audio=audio_data)

        # Track total turn time
        turn_start = time.perf_counter()

        try:
            # Update state
            session.state = ConversationState.LISTENING
            yield {
                "type": "state",
                "state": "listening",
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat()
            }

            # 1. Speech-to-Text (target: 150ms)
            stt_start = time.perf_counter()
            stt_result = await self.cartesia.speech_to_text(
                audio_data=audio_data,
                sample_rate=sample_rate,
                language=session.voice_config.language
            )
            turn.user_transcript = stt_result["transcript"]
            turn.stt_latency_ms = stt_result["latency_ms"]

            yield {
                "type": "transcript",
                "text": turn.user_transcript,
                "confidence": stt_result["confidence"],
                "latency_ms": turn.stt_latency_ms
            }

            # Update state
            session.state = ConversationState.PROCESSING
            yield {
                "type": "state",
                "state": "processing"
            }

            # 2. AI Reasoning (target: 633ms)
            inference_start = time.perf_counter()

            # Get lead data if available
            lead_data = None
            if session.lead_id:
                lead_data = await self._get_lead_data(session.lead_id)

            # Generate response using TalkingNode
            ai_response = await self.talking_node.reason(
                transcript=turn.user_transcript,
                context=session.context,
                lead_data=lead_data
            )

            turn.ai_response = ai_response
            turn.inference_latency_ms = int((time.perf_counter() - inference_start) * 1000)

            yield {
                "type": "response",
                "text": ai_response,
                "latency_ms": turn.inference_latency_ms
            }

            # Update conversation context
            if "recent_turns" not in session.context:
                session.context["recent_turns"] = []

            session.context["recent_turns"].append({
                "user": turn.user_transcript,
                "assistant": ai_response
            })

            # Keep only last 10 turns in context
            session.context["recent_turns"] = session.context["recent_turns"][-10:]

            # Update state
            session.state = ConversationState.SPEAKING
            yield {
                "type": "state",
                "state": "speaking"
            }

            # 3. Text-to-Speech (target: 200ms)
            tts_start = time.perf_counter()
            first_audio_chunk = True

            async for audio_chunk in self.cartesia.stream_to_session(
                session_id=session_id,
                text=ai_response
            ):
                if first_audio_chunk:
                    turn.tts_latency_ms = int((time.perf_counter() - tts_start) * 1000)
                    first_audio_chunk = False

                    # Calculate total turn latency
                    turn.total_latency_ms = int((time.perf_counter() - turn_start) * 1000)

                    # Track latency
                    self._record_latency(turn.total_latency_ms)

                    # Log performance
                    logger.info(
                        f"Voice turn {turn_id} completed: "
                        f"STT={turn.stt_latency_ms}ms, "
                        f"Inference={turn.inference_latency_ms}ms, "
                        f"TTS={turn.tts_latency_ms}ms, "
                        f"Total={turn.total_latency_ms}ms"
                    )

                    # Verify <2000ms target
                    if turn.total_latency_ms > 2000:
                        logger.warning(
                            f"Turn latency {turn.total_latency_ms}ms exceeds 2000ms target"
                        )

                yield {
                    "type": "audio",
                    "data": audio_chunk,
                    "format": {
                        "encoding": session.voice_config.encoding,
                        "sample_rate": session.voice_config.sample_rate,
                        "container": session.voice_config.container
                    }
                }

            # Update state
            session.state = ConversationState.IDLE
            yield {
                "type": "state",
                "state": "idle"
            }

            # Save turn to session
            session.turns.append(turn)
            session.total_turns += 1
            session.updated_at = datetime.now()

            # Update average latency
            if session.total_turns > 0:
                total_latency = sum(t.total_latency_ms for t in session.turns if t.total_latency_ms)
                session.average_latency_ms = total_latency / session.total_turns

            # Persist to Redis
            await self._save_session_to_redis(session)

            # Final completion message
            yield {
                "type": "complete",
                "turn_id": turn_id,
                "metrics": {
                    "stt_latency_ms": turn.stt_latency_ms,
                    "inference_latency_ms": turn.inference_latency_ms,
                    "tts_latency_ms": turn.tts_latency_ms,
                    "total_latency_ms": turn.total_latency_ms,
                    "session_average_ms": session.average_latency_ms
                }
            }

        except Exception as e:
            # Handle errors
            session.state = ConversationState.ERROR
            turn.error = str(e)
            session.turns.append(turn)

            logger.error(f"Voice turn failed: {e}")

            yield {
                "type": "error",
                "error": str(e),
                "turn_id": turn_id
            }

    async def adjust_voice_emotion(
        self,
        session_id: str,
        emotion: VoiceEmotion
    ):
        """
        Dynamically adjust voice emotion during conversation.

        Args:
            session_id: Session identifier
            emotion: New emotion setting
        """
        if session_id not in self.sessions:
            raise VoiceSessionNotFoundError(f"Session {session_id} not found", context={"session_id": session_id})

        session = self.sessions[session_id]
        session.voice_config.emotion = emotion

        logger.info(f"Session {session_id} emotion changed to {emotion.value}")

    async def close_session(self, session_id: str):
        """
        Close a voice session and cleanup resources.

        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]

            # Close Cartesia session
            await self.cartesia.close_voice_session(session_id)

            # Final save to Redis
            await self._save_session_to_redis(session)

            # Remove from active sessions
            del self.sessions[session_id]

            logger.info(f"Closed voice session: {session_id}")

    async def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with session metrics
        """
        if session_id not in self.sessions:
            # Try to load from Redis
            session = await self._load_session_from_redis(session_id)
            if not session:
                raise VoiceSessionNotFoundError(f"Session {session_id} not found", context={"session_id": session_id})
        else:
            session = self.sessions[session_id]

        # Calculate latency percentiles
        latencies = [t.total_latency_ms for t in session.turns if t.total_latency_ms]

        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if len(latencies_sorted) > 1 else p50
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)] if len(latencies_sorted) > 1 else p95
        else:
            p50 = p95 = p99 = 0

        return {
            "session_id": session_id,
            "total_turns": session.total_turns,
            "average_latency_ms": session.average_latency_ms,
            "latency_p50": p50,
            "latency_p95": p95,
            "latency_p99": p99,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "state": session.state.value
        }

    def get_global_metrics(self) -> Dict[str, Any]:
        """
        Get global performance metrics across all sessions.

        Returns:
            Dict with global metrics
        """
        if not self.latency_buffer:
            return {
                "total_turns": 0,
                "average_latency_ms": 0,
                "target_compliance_rate": 0.0
            }

        latencies_sorted = sorted(self.latency_buffer)

        # Calculate compliance with 2000ms target
        compliant = sum(1 for l in self.latency_buffer if l <= 2000)
        compliance_rate = compliant / len(self.latency_buffer)

        return {
            "total_turns": len(self.latency_buffer),
            "average_latency_ms": sum(self.latency_buffer) / len(self.latency_buffer),
            "latency_p50": latencies_sorted[len(latencies_sorted) // 2],
            "latency_p95": latencies_sorted[int(len(latencies_sorted) * 0.95)],
            "latency_p99": latencies_sorted[int(len(latencies_sorted) * 0.99)],
            "target_compliance_rate": compliance_rate,
            "cartesia_stats": self.cartesia.get_performance_stats()
        }

    def _record_latency(self, latency_ms: int):
        """Record latency for tracking."""
        self.latency_buffer.append(latency_ms)
        if len(self.latency_buffer) > self.max_buffer_size:
            self.latency_buffer = self.latency_buffer[-self.max_buffer_size:]

    async def _save_session_to_redis(self, session: VoiceSession):
        """Save session to Redis for persistence."""
        if not self.redis_client:
            return

        # Serialize session (simplified - in production use proper serialization)
        session_data = {
            "session_id": session.session_id,
            "lead_id": session.lead_id,
            "state": session.state.value,
            "total_turns": session.total_turns,
            "average_latency_ms": session.average_latency_ms,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "context": json.dumps(session.context)
        }

        await self.redis_client.hset(
            f"voice_session:{session.session_id}",
            mapping=session_data
        )

        # Set expiry (24 hours)
        await self.redis_client.expire(f"voice_session:{session.session_id}", 86400)

    async def _load_session_from_redis(self, session_id: str) -> Optional[VoiceSession]:
        """Load session from Redis."""
        if not self.redis_client:
            return None

        session_data = await self.redis_client.hgetall(f"voice_session:{session_id}")
        if not session_data:
            return None

        # Deserialize (simplified)
        session = VoiceSession(
            session_id=session_data[b"session_id"].decode(),
            lead_id=int(session_data[b"lead_id"].decode()) if session_data.get(b"lead_id") else None,
            state=ConversationState(session_data[b"state"].decode()),
            total_turns=int(session_data[b"total_turns"].decode()),
            average_latency_ms=float(session_data[b"average_latency_ms"].decode())
        )

        if session_data.get(b"context"):
            session.context = json.loads(session_data[b"context"].decode())

        return session

    async def _get_lead_data(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Get lead data for context (placeholder for actual DB query)."""
        # TODO: Integrate with actual database
        return {
            "company_name": "Example Corp",
            "industry": "Technology",
            "company_size": "100-500"
        }