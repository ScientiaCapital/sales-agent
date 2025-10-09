"""
Real-time transcription service using OpenAI Whisper API

Handles audio-to-text transcription with streaming support and performance tracking.
"""

import os
import time
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
import io

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service for real-time audio transcription using OpenAI Whisper API.

    Supports various audio formats and provides streaming-friendly transcription
    with performance tracking.
    """

    def __init__(self):
        """Initialize transcription service with OpenAI client."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Transcription service will not function.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        self.model = "whisper-1"

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
            prompt: Optional context to guide transcription

        Returns:
            Dictionary containing:
            - text: Transcribed text
            - language: Detected language
            - confidence: Transcription confidence (if available)
            - latency_ms: Processing time
            - duration_seconds: Audio duration estimate

        Raises:
            Exception: If transcription fails
        """
        if not self.client:
            raise Exception("OpenAI API key not configured")

        start_time = time.time()

        try:
            # Create a file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"audio.{audio_format}"

            # Prepare transcription parameters
            params = {
                "model": self.model,
                "file": audio_file,
                "response_format": "verbose_json",  # Get detailed response with timestamps
            }

            if language:
                params["language"] = language

            if prompt:
                params["prompt"] = prompt

            # Transcribe audio
            response = await self.client.audio.transcriptions.create(**params)

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response data
            text = response.text
            detected_language = getattr(response, 'language', language or 'unknown')
            duration_seconds = getattr(response, 'duration', None)

            # Update performance metrics
            self.total_transcriptions += 1
            self.total_latency_ms += latency_ms
            if duration_seconds:
                self.total_audio_seconds += duration_seconds

            # Calculate confidence (not directly provided by Whisper, use heuristics)
            confidence = self._estimate_confidence(text, len(audio_data))

            result = {
                "text": text,
                "language": detected_language,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "duration_seconds": duration_seconds,
                "timestamp": time.time(),
            }

            logger.info(f"Transcription completed: {len(text)} chars in {latency_ms}ms")

            return result

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
            raise Exception("OpenAI API key not configured")

        start_time = time.time()

        try:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"audio.{audio_format}"

            # Request verbose JSON with timestamps
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"],
                language=language,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract segments and words if available
            segments = []
            if hasattr(response, 'segments'):
                segments = [
                    {
                        "text": seg.text,
                        "start": seg.start,
                        "end": seg.end,
                    }
                    for seg in response.segments
                ]

            words = []
            if hasattr(response, 'words'):
                words = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                    }
                    for word in response.words
                ]

            result = {
                "text": response.text,
                "language": getattr(response, 'language', language or 'unknown'),
                "duration_seconds": getattr(response, 'duration', None),
                "segments": segments,
                "words": words,
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            }

            logger.info(f"Transcription with timestamps completed: {len(segments)} segments, {len(words)} words in {latency_ms}ms")

            return result

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Timestamped transcription failed after {latency_ms}ms: {e}")
            raise

    def _estimate_confidence(self, text: str, audio_size_bytes: int) -> float:
        """
        Estimate transcription confidence based on heuristics.

        Whisper API doesn't directly provide confidence scores, so we use
        heuristics like text length vs audio size.

        Args:
            text: Transcribed text
            audio_size_bytes: Size of audio data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not text or audio_size_bytes == 0:
            return 0.0

        # Heuristic: longer text relative to audio size suggests better quality
        # Typical speech is ~150 words per minute, ~5 chars per word = 750 chars/min
        # Typical audio compression: ~100KB per minute for WebM
        expected_ratio = 750 / 100_000  # chars per byte
        actual_ratio = len(text) / audio_size_bytes

        # Calculate confidence based on how close to expected ratio
        confidence = min(1.0, actual_ratio / expected_ratio)

        # Boost confidence if text seems coherent (has spaces, punctuation)
        if ' ' in text and any(c in text for c in '.,!?'):
            confidence = min(1.0, confidence * 1.2)

        return round(confidence, 2)

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
