"""
Real-time transcription service using Deepgram Nova-2

Handles audio-to-text transcription with streaming support and performance tracking.
Migrated from OpenAI Whisper to Deepgram for policy compliance.
"""

import os
import time
import logging
from typing import Optional, Dict, Any
import io

from app.services.deepgram_service import DeepgramService, DeepgramConfig

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service for real-time audio transcription using Deepgram Nova-2.

    Supports various audio formats and provides streaming-friendly transcription
    with performance tracking.

    Note: Migrated from OpenAI Whisper to Deepgram for policy compliance.
    API remains compatible with original implementation.
    """

    def __init__(self):
        """Initialize transcription service with Deepgram client."""
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.warning("DEEPGRAM_API_KEY not set. Transcription service will not function.")
            self.client = None
        else:
            self.client = DeepgramService(DeepgramConfig(
                model="nova-2",
                smart_format=True,
                punctuate=True,
            ))

        # Performance tracking
        self.total_transcriptions = 0
        self.total_latency_ms = 0
        self.total_audio_seconds = 0.0

    async def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (webm, mp3, wav, etc.)
            language: Optional language code (e.g., "en", "es")
            prompt: Optional context to guide transcription (not used with Deepgram)

        Returns:
            Dictionary containing:
            - text: Transcribed text
            - language: Detected language
            - confidence: Transcription confidence
            - latency_ms: Processing time
            - duration_seconds: Audio duration estimate

        Raises:
            Exception: If transcription fails
        """
        if not self.client:
            raise Exception("Deepgram API key not configured")

        start_time = time.time()

        try:
            # Configure for specific language if provided
            if language:
                self.client.config.language = language

            # Transcribe audio using Deepgram
            result = await self.client.transcribe(audio_data)

            latency_ms = int((time.time() - start_time) * 1000)

            # Update performance metrics
            self.total_transcriptions += 1
            self.total_latency_ms += latency_ms

            # Estimate duration from audio data size
            # Approximate: 16kHz, 16-bit mono = 32KB per second
            estimated_duration = len(audio_data) / 32000.0
            self.total_audio_seconds += estimated_duration

            response = {
                "text": result.transcript,
                "language": language or "en",
                "confidence": result.confidence,
                "latency_ms": latency_ms,
                "duration_seconds": estimated_duration,
                "timestamp": time.time(),
            }

            logger.info(f"Transcription completed: {len(result.transcript)} chars in {latency_ms}ms")

            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Transcription failed after {latency_ms}ms: {e}")
            raise

    async def transcribe_with_timestamps(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio with word-level timestamps.

        Useful for synchronizing transcription with audio playback or
        identifying specific moments in the conversation.

        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format
            language: Optional language code

        Returns:
            Dictionary containing text, segments, and word-level timestamps
        """
        if not self.client:
            raise Exception("Deepgram API key not configured")

        start_time = time.time()

        try:
            if language:
                self.client.config.language = language

            # Transcribe using Deepgram
            result = await self.client.transcribe(audio_data)

            latency_ms = int((time.time() - start_time) * 1000)

            # Build segments from words
            segments = []
            if result.words:
                current_segment = {"text": "", "start": 0, "end": 0}
                for word_info in result.words:
                    if not current_segment["text"]:
                        current_segment["start"] = word_info.start
                    current_segment["text"] += word_info.word + " "
                    current_segment["end"] = word_info.end

                    # Split segments on sentence boundaries
                    if word_info.word.rstrip().endswith(('.', '!', '?')):
                        current_segment["text"] = current_segment["text"].strip()
                        segments.append(current_segment)
                        current_segment = {"text": "", "start": 0, "end": 0}

                # Add any remaining segment
                if current_segment["text"].strip():
                    current_segment["text"] = current_segment["text"].strip()
                    segments.append(current_segment)

            # Build word list
            words = []
            if result.words:
                words = [
                    {
                        "word": word_info.word,
                        "start": word_info.start,
                        "end": word_info.end,
                    }
                    for word_info in result.words
                ]

            # Estimate duration
            estimated_duration = len(audio_data) / 32000.0

            response = {
                "text": result.transcript,
                "language": language or "en",
                "duration_seconds": estimated_duration,
                "segments": segments,
                "words": words,
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            }

            logger.info(f"Transcription with timestamps completed: {len(segments)} segments, {len(words)} words in {latency_ms}ms")

            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Timestamped transcription failed after {latency_ms}ms: {e}")
            raise

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for transcription service.

        Returns:
            Dictionary with average latency, throughput, etc.
        """
        if self.total_transcriptions == 0:
            return {
                "total_transcriptions": 0,
                "average_latency_ms": 0,
                "total_audio_seconds": 0.0,
                "average_audio_seconds": 0.0,
            }

        return {
            "total_transcriptions": self.total_transcriptions,
            "average_latency_ms": self.total_latency_ms // self.total_transcriptions,
            "total_audio_seconds": self.total_audio_seconds,
            "average_audio_seconds": self.total_audio_seconds / self.total_transcriptions,
        }

    def reset_metrics(self):
        """Reset performance metrics."""
        self.total_transcriptions = 0
        self.total_latency_ms = 0
        self.total_audio_seconds = 0.0
        logger.info("Transcription metrics reset")


# Global instance
_transcription_service = None


def get_transcription_service() -> TranscriptionService:
    """Get or create global transcription service instance."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
