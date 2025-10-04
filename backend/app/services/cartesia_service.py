"""
Cartesia Voice Service - Ultra-fast text-to-speech and speech-to-text

Provides real-time voice synthesis and recognition with <200ms latency per operation.
Implements WebSocket streaming, voice cloning, and emotion control.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, AsyncIterator, Dict, Any, List
import numpy as np

try:
    from cartesia import AsyncCartesia, Cartesia
    from cartesia.tts import OutputFormat_RawParams
    CARTESIA_AVAILABLE = True
except ImportError:
    CARTESIA_AVAILABLE = False
    logging.warning("Cartesia SDK not installed. Voice features will be unavailable.")

logger = logging.getLogger(__name__)


class VoiceEmotion(str, Enum):
    """Available voice emotions for synthesis."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    CURIOUS = "curious"
    CONFUSED = "confused"
    EXCITED = "excited"
    PROFESSIONAL = "professional"
    EMPATHETIC = "empathetic"


class VoiceSpeed(str, Enum):
    """Speech speed control."""
    SLOWEST = "slowest"
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    FASTEST = "fastest"


@dataclass
class VoiceConfig:
    """Voice configuration for synthesis."""
    voice_id: str
    language: str = "en"
    emotion: Optional[VoiceEmotion] = None
    speed: VoiceSpeed = VoiceSpeed.NORMAL
    sample_rate: int = 44100
    encoding: str = "pcm_f32le"
    container: str = "raw"


@dataclass
class VoiceMetrics:
    """Performance metrics for voice operations."""
    operation: str  # tts or stt
    latency_ms: int
    audio_duration_ms: Optional[int] = None
    tokens_generated: Optional[int] = None
    cost_usd: float = 0.0
    error: Optional[str] = None


class CartesiaService:
    """
    High-performance voice service using Cartesia AI.

    Features:
    - Ultra-fast TTS with <200ms latency
    - Real-time WebSocket streaming
    - Voice cloning and mixing
    - Emotion and speed control
    - Multi-language support
    - Optimized audio buffering
    """

    # Cartesia pricing (estimated)
    TTS_COST_PER_CHAR = 0.000006  # $6 per 1M characters
    STT_COST_PER_SECOND = 0.0004  # $0.40 per 1000 seconds

    # Performance targets
    MAX_TTS_LATENCY_MS = 200
    MAX_STT_LATENCY_MS = 300

    # Audio buffer settings for minimal jitter
    BUFFER_SIZE_SAMPLES = 512
    PREBUFFER_MS = 50  # Pre-buffer before playback

    def __init__(self):
        """Initialize Cartesia service with optimized settings."""
        if not CARTESIA_AVAILABLE:
            raise RuntimeError(
                "Cartesia SDK not installed. Install with: pip install cartesia"
            )

        api_key = os.getenv("CARTESIA_API_KEY")
        if not api_key:
            raise ValueError("CARTESIA_API_KEY environment variable not set")

        # Initialize sync and async clients
        self.client = Cartesia(api_key=api_key)
        self.async_client = AsyncCartesia(api_key=api_key)

        # Cache for voice embeddings
        self._voice_cache: Dict[str, Any] = {}

        # WebSocket connections for streaming
        self._active_streams: Dict[str, Any] = {}

        # Performance tracking
        self._metrics_buffer: List[VoiceMetrics] = []
        self._max_metrics_buffer = 1000

        logger.info("CartesiaService initialized with ultra-fast settings")

    async def text_to_speech(
        self,
        text: str,
        voice_config: VoiceConfig,
        stream: bool = False
    ) -> AsyncIterator[bytes]:
        """
        Convert text to speech with ultra-low latency.

        Args:
            text: Text to synthesize
            voice_config: Voice configuration
            stream: Whether to stream audio chunks

        Yields:
            Audio chunks in configured format
        """
        start_time = time.perf_counter()

        try:
            # Build voice parameters with experimental controls
            voice_params = {
                "id": voice_config.voice_id
            }

            # Add experimental controls for emotion and speed
            experimental_controls = {}
            if voice_config.speed != VoiceSpeed.NORMAL:
                experimental_controls["speed"] = voice_config.speed.value
            if voice_config.emotion:
                # Map emotion to Cartesia emotion controls
                emotion_mapping = self._map_emotion(voice_config.emotion)
                if emotion_mapping:
                    experimental_controls["emotion"] = emotion_mapping

            if experimental_controls:
                voice_params["experimental_controls"] = experimental_controls

            # Configure output format for minimal latency
            output_format = {
                "container": voice_config.container,
                "encoding": voice_config.encoding,
                "sample_rate": voice_config.sample_rate
            }

            if stream:
                # Use WebSocket for lowest latency streaming
                yield_time = None
                audio_chunks = []

                # Open WebSocket connection
                ws = await self.async_client.tts.websocket()

                try:
                    # Send TTS request
                    async for output in ws.send(
                        model_id="sonic-2",  # Latest ultra-fast model
                        transcript=text,
                        voice=voice_params,
                        language=voice_config.language,
                        output_format=output_format,
                        stream=True,
                        add_timestamps=False  # Skip for lower latency
                    ):
                        if output.audio:
                            if yield_time is None:
                                yield_time = time.perf_counter()
                                first_chunk_latency = int((yield_time - start_time) * 1000)
                                logger.debug(f"TTS first chunk latency: {first_chunk_latency}ms")

                            audio_chunks.append(output.audio)
                            yield output.audio

                finally:
                    await ws.close()

                # Track metrics
                total_latency = int((time.perf_counter() - start_time) * 1000)
                metric = VoiceMetrics(
                    operation="tts_stream",
                    latency_ms=total_latency,
                    tokens_generated=len(text),
                    cost_usd=len(text) * self.TTS_COST_PER_CHAR
                )
                self._record_metric(metric)

            else:
                # Non-streaming: Get complete audio at once
                response = await self.async_client.tts.bytes(
                    model_id="sonic-2",
                    transcript=text,
                    voice=voice_params,
                    language=voice_config.language,
                    output_format=output_format
                )

                total_latency = int((time.perf_counter() - start_time) * 1000)

                # Verify latency target
                if total_latency > self.MAX_TTS_LATENCY_MS:
                    logger.warning(
                        f"TTS latency {total_latency}ms exceeds target {self.MAX_TTS_LATENCY_MS}ms"
                    )

                metric = VoiceMetrics(
                    operation="tts_bytes",
                    latency_ms=total_latency,
                    tokens_generated=len(text),
                    cost_usd=len(text) * self.TTS_COST_PER_CHAR
                )
                self._record_metric(metric)

                yield response

        except Exception as e:
            total_latency = int((time.perf_counter() - start_time) * 1000)
            metric = VoiceMetrics(
                operation="tts_error",
                latency_ms=total_latency,
                error=str(e)
            )
            self._record_metric(metric)
            logger.error(f"TTS failed after {total_latency}ms: {e}")
            raise

    async def speech_to_text(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Convert speech to text with ultra-low latency.

        Note: Cartesia primarily focuses on TTS. For STT, we would integrate
        with a specialized service like Deepgram or AssemblyAI for optimal performance.
        This is a placeholder for the integration pattern.

        Args:
            audio_data: Raw audio bytes
            sample_rate: Audio sample rate
            language: Language code

        Returns:
            Dict with transcript and metadata
        """
        start_time = time.perf_counter()

        try:
            # TODO: Integrate with Deepgram/AssemblyAI for actual STT
            # For now, return a mock response to demonstrate the pattern

            # Simulate STT processing
            await asyncio.sleep(0.15)  # Simulate 150ms STT latency

            transcript = "Mock transcript for audio input"
            confidence = 0.95

            total_latency = int((time.perf_counter() - start_time) * 1000)

            # Calculate audio duration
            audio_duration_seconds = len(audio_data) / (sample_rate * 2)  # 16-bit audio

            metric = VoiceMetrics(
                operation="stt",
                latency_ms=total_latency,
                audio_duration_ms=int(audio_duration_seconds * 1000),
                cost_usd=audio_duration_seconds * self.STT_COST_PER_SECOND
            )
            self._record_metric(metric)

            return {
                "transcript": transcript,
                "confidence": confidence,
                "language": language,
                "latency_ms": total_latency,
                "duration_ms": int(audio_duration_seconds * 1000)
            }

        except Exception as e:
            total_latency = int((time.perf_counter() - start_time) * 1000)
            metric = VoiceMetrics(
                operation="stt_error",
                latency_ms=total_latency,
                error=str(e)
            )
            self._record_metric(metric)
            logger.error(f"STT failed after {total_latency}ms: {e}")
            raise

    async def clone_voice(
        self,
        audio_file_path: str,
        name: str,
        description: str = "",
        mode: str = "similarity"
    ) -> str:
        """
        Clone a voice from an audio sample.

        Args:
            audio_file_path: Path to audio file for cloning
            name: Name for the cloned voice
            description: Optional description
            mode: "similarity" for closest match, "stability" for consistent output

        Returns:
            Voice ID of the cloned voice
        """
        start_time = time.perf_counter()

        try:
            with open(audio_file_path, "rb") as audio_file:
                cloned_voice = await self.async_client.voices.clone(
                    clip=audio_file,
                    name=name,
                    description=description,
                    mode=mode,
                    enhance=True,  # Clean and denoise
                    language="en"
                )

            voice_id = cloned_voice.id

            # Cache the voice embedding
            self._voice_cache[voice_id] = cloned_voice

            total_latency = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Voice cloned in {total_latency}ms: {voice_id}")

            return voice_id

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise

    async def mix_voices(
        self,
        voice_weights: List[Dict[str, Any]]
    ) -> str:
        """
        Mix multiple voices with specified weights.

        Args:
            voice_weights: List of dicts with "id" and "weight" keys

        Returns:
            Voice ID of the mixed voice
        """
        try:
            mixed_voice = await self.async_client.voices.mix(
                voices=voice_weights
            )

            voice_id = mixed_voice.id
            self._voice_cache[voice_id] = mixed_voice

            logger.info(f"Created mixed voice: {voice_id}")
            return voice_id

        except Exception as e:
            logger.error(f"Voice mixing failed: {e}")
            raise

    async def list_voices(self) -> List[Dict[str, Any]]:
        """
        List all available voices.

        Returns:
            List of voice metadata dicts
        """
        try:
            voices = []
            async for voice in self.async_client.voices.list():
                voices.append({
                    "id": voice.id,
                    "name": voice.name,
                    "description": voice.description if hasattr(voice, 'description') else "",
                    "language": voice.language if hasattr(voice, 'language') else "en"
                })

            logger.info(f"Retrieved {len(voices)} available voices")
            return voices

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            raise

    def _map_emotion(self, emotion: VoiceEmotion) -> List[str]:
        """
        Map our emotion enum to Cartesia emotion controls.

        Args:
            emotion: VoiceEmotion enum value

        Returns:
            List of Cartesia emotion strings
        """
        emotion_map = {
            VoiceEmotion.HAPPY: ["joy:high", "energy:high"],
            VoiceEmotion.SAD: ["sadness:high", "energy:low"],
            VoiceEmotion.ANGRY: ["anger:high", "energy:high"],
            VoiceEmotion.SURPRISED: ["surprise:high", "curiosity:high"],
            VoiceEmotion.CURIOUS: ["curiosity:high"],
            VoiceEmotion.CONFUSED: ["confusion:high"],
            VoiceEmotion.EXCITED: ["excitement:high", "energy:high"],
            VoiceEmotion.PROFESSIONAL: ["seriousness:high", "energy:medium"],
            VoiceEmotion.EMPATHETIC: ["empathy:high", "warmth:high"]
        }

        return emotion_map.get(emotion, [])

    def _record_metric(self, metric: VoiceMetrics):
        """Record performance metric for analysis."""
        self._metrics_buffer.append(metric)

        # Trim buffer if too large
        if len(self._metrics_buffer) > self._max_metrics_buffer:
            self._metrics_buffer = self._metrics_buffer[-self._max_metrics_buffer:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Dict with latency percentiles and operation counts
        """
        if not self._metrics_buffer:
            return {
                "total_operations": 0,
                "error_rate": 0.0
            }

        # Separate by operation type
        tts_latencies = []
        stt_latencies = []
        errors = 0

        for metric in self._metrics_buffer:
            if metric.error:
                errors += 1
            elif "tts" in metric.operation:
                tts_latencies.append(metric.latency_ms)
            elif "stt" in metric.operation:
                stt_latencies.append(metric.latency_ms)

        def calculate_percentiles(latencies):
            if not latencies:
                return {}
            latencies_sorted = sorted(latencies)
            return {
                "p50": latencies_sorted[len(latencies_sorted) // 2],
                "p95": latencies_sorted[int(len(latencies_sorted) * 0.95)],
                "p99": latencies_sorted[int(len(latencies_sorted) * 0.99)],
                "mean": sum(latencies) / len(latencies)
            }

        return {
            "total_operations": len(self._metrics_buffer),
            "error_rate": errors / len(self._metrics_buffer),
            "tts_latency": calculate_percentiles(tts_latencies),
            "stt_latency": calculate_percentiles(stt_latencies),
            "total_cost_usd": sum(m.cost_usd for m in self._metrics_buffer)
        }

    async def create_voice_session(
        self,
        session_id: str,
        voice_config: VoiceConfig
    ) -> Dict[str, Any]:
        """
        Create a persistent voice session for continuous interaction.

        Args:
            session_id: Unique session identifier
            voice_config: Voice configuration for the session

        Returns:
            Session metadata
        """
        try:
            # Open WebSocket for the session
            ws = await self.async_client.tts.websocket()

            self._active_streams[session_id] = {
                "websocket": ws,
                "voice_config": voice_config,
                "created_at": time.time(),
                "message_count": 0
            }

            logger.info(f"Created voice session: {session_id}")

            return {
                "session_id": session_id,
                "status": "active",
                "voice_id": voice_config.voice_id
            }

        except Exception as e:
            logger.error(f"Failed to create voice session: {e}")
            raise

    async def close_voice_session(self, session_id: str):
        """Close an active voice session."""
        if session_id in self._active_streams:
            session = self._active_streams[session_id]
            if "websocket" in session:
                await session["websocket"].close()

            del self._active_streams[session_id]
            logger.info(f"Closed voice session: {session_id}")

    async def stream_to_session(
        self,
        session_id: str,
        text: str
    ) -> AsyncIterator[bytes]:
        """
        Stream TTS to an existing session for minimal latency.

        Args:
            session_id: Session identifier
            text: Text to synthesize

        Yields:
            Audio chunks
        """
        if session_id not in self._active_streams:
            raise ValueError(f"Session {session_id} not found")

        session = self._active_streams[session_id]
        ws = session["websocket"]
        voice_config = session["voice_config"]

        start_time = time.perf_counter()

        # Build voice params
        voice_params = {"id": voice_config.voice_id}

        experimental_controls = {}
        if voice_config.speed != VoiceSpeed.NORMAL:
            experimental_controls["speed"] = voice_config.speed.value
        if voice_config.emotion:
            emotion_mapping = self._map_emotion(voice_config.emotion)
            if emotion_mapping:
                experimental_controls["emotion"] = emotion_mapping

        if experimental_controls:
            voice_params["experimental_controls"] = experimental_controls

        # Stream audio
        async for output in ws.send(
            model_id="sonic-2",
            transcript=text,
            voice=voice_params,
            language=voice_config.language,
            output_format={
                "container": voice_config.container,
                "encoding": voice_config.encoding,
                "sample_rate": voice_config.sample_rate
            },
            stream=True
        ):
            if output.audio:
                yield output.audio

        # Update session stats
        session["message_count"] += 1

        total_latency = int((time.perf_counter() - start_time) * 1000)
        logger.debug(f"Session {session_id} TTS: {total_latency}ms")