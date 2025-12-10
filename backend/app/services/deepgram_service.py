"""
Deepgram Speech-to-Text Service - Ultra-fast transcription with Nova-2

Uses Deepgram Nova-2 model for high-accuracy, low-latency speech-to-text.
Provides both REST API transcription and WebSocket streaming.

Features:
- <150ms target latency with Nova-2 model
- Word-level timestamps and confidence scores
- Smart formatting and punctuation
- Multi-language support
- WebSocket streaming for real-time transcription
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WordInfo:
    """Word-level transcription data with timestamps."""
    word: str
    start: float  # Start time in seconds
    end: float    # End time in seconds
    confidence: float


@dataclass
class TranscriptionResult:
    """Result from speech-to-text transcription."""
    transcript: str
    confidence: float
    latency_ms: int
    words: Optional[List[WordInfo]] = None


@dataclass
class DeepgramConfig:
    """Configuration for Deepgram transcription."""
    model: str = "nova-2"  # Nova-2 for best accuracy/speed balance
    language: str = "en"
    sample_rate: int = 16000
    encoding: str = "linear16"  # PCM 16-bit
    channels: int = 1
    smart_format: bool = True   # Auto-formatting (punctuation, capitalization)
    punctuate: bool = True      # Add punctuation
    interim_results: bool = False  # For WebSocket streaming
    utterance_end_ms: int = 1000  # Silence detection for utterances


class DeepgramService:
    """
    High-performance speech-to-text service using Deepgram Nova-2.

    Features:
    - Ultra-fast transcription with <150ms latency
    - REST API for batch transcription
    - WebSocket URL generation for streaming
    - Word-level timestamps and confidence
    - Smart formatting and punctuation
    - Multi-language support
    """

    # Deepgram API configuration
    BASE_URL = "https://api.deepgram.com/v1"
    TIMEOUT_SECONDS = 10.0

    # Performance targets
    TARGET_LATENCY_MS = 150

    def __init__(self, config: Optional[DeepgramConfig] = None):
        """
        Initialize Deepgram service with lazy API key loading.

        Args:
            config: Optional DeepgramConfig for customization

        Note:
            API key is NOT validated in constructor (lazy initialization).
            Validation happens on first API call.
        """
        self.config = config or DeepgramConfig()
        # Lazy init - don't load API key yet
        self._api_key: Optional[str] = None

        logger.info("DeepgramService initialized with lazy loading")

    def _get_api_key(self) -> str:
        """
        Get API key from environment (lazy loading).

        Returns:
            API key string

        Raises:
            ValueError: If DEEPGRAM_API_KEY not found in environment
        """
        if self._api_key is None:
            api_key = os.getenv("DEEPGRAM_API_KEY")
            if not api_key:
                raise ValueError(
                    "DEEPGRAM_API_KEY environment variable not set. "
                    "Get your API key from https://console.deepgram.com/"
                )
            self._api_key = api_key

        return self._api_key

    async def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        """
        Transcribe audio bytes to text using Deepgram REST API.

        Args:
            audio_bytes: Raw audio data (PCM 16-bit, 16kHz recommended)

        Returns:
            TranscriptionResult with transcript, confidence, and latency

        Raises:
            ValueError: If API key is missing
            httpx.HTTPError: If API request fails
        """
        start_time = time.perf_counter()

        try:
            # Get API key (lazy loading)
            api_key = self._get_api_key()

            # Build query parameters
            params = {
                "model": self.config.model,
                "language": self.config.language,
                "encoding": self.config.encoding,
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
            }

            # Add optional features
            if self.config.smart_format:
                params["smart_format"] = "true"
            if self.config.punctuate:
                params["punctuate"] = "true"

            # Make REST API request
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": f"audio/{self.config.encoding}"
            }

            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.BASE_URL}/listen",
                    params=params,
                    headers=headers,
                    content=audio_bytes
                )

                # Raise for HTTP errors (4xx, 5xx)
                response.raise_for_status()

                # Parse response
                data = response.json()

            # Calculate latency
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract transcript and confidence
            results = data.get("results", {})
            channels = results.get("channels", [])

            if not channels:
                # Empty response - return empty transcript
                return TranscriptionResult(
                    transcript="",
                    confidence=0.0,
                    latency_ms=latency_ms,
                    words=None
                )

            # Get first channel's best alternative
            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                return TranscriptionResult(
                    transcript="",
                    confidence=0.0,
                    latency_ms=latency_ms,
                    words=None
                )

            alternative = alternatives[0]
            transcript = alternative.get("transcript", "")
            confidence = alternative.get("confidence", 0.0)

            # Extract word-level timestamps if available
            words = None
            if "words" in alternative:
                words = [
                    WordInfo(
                        word=w.get("word", ""),
                        start=w.get("start", 0.0),
                        end=w.get("end", 0.0),
                        confidence=w.get("confidence", 0.0)
                    )
                    for w in alternative["words"]
                ]

            # Log performance
            if latency_ms > self.TARGET_LATENCY_MS:
                logger.warning(
                    f"Transcription latency {latency_ms}ms exceeds target "
                    f"{self.TARGET_LATENCY_MS}ms"
                )
            else:
                logger.debug(f"Transcription completed in {latency_ms}ms")

            return TranscriptionResult(
                transcript=transcript,
                confidence=confidence,
                latency_ms=latency_ms,
                words=words
            )

        except httpx.HTTPError as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Deepgram API error after {latency_ms}ms: {e}")
            raise

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Transcription failed after {latency_ms}ms: {e}")
            raise

    def get_websocket_url(self) -> str:
        """
        Generate WebSocket URL for streaming transcription.

        Returns:
            WebSocket URL with query parameters for Deepgram streaming

        Example:
            wss://api.deepgram.com/v1/listen?model=nova-2&encoding=linear16&sample_rate=16000
        """
        # Build query parameters
        params = {
            "model": self.config.model,
            "language": self.config.language,
            "encoding": self.config.encoding,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
        }

        # Add optional features
        if self.config.smart_format:
            params["smart_format"] = "true"
        if self.config.punctuate:
            params["punctuate"] = "true"
        if self.config.interim_results:
            params["interim_results"] = "true"

        # Build WebSocket URL
        query_string = urlencode(params)
        url = f"wss://api.deepgram.com/v1/listen?{query_string}"

        logger.debug(f"Generated WebSocket URL: {url}")

        return url
