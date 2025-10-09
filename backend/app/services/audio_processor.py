"""
Real-time audio processing service for conversation intelligence

Handles audio buffering, format conversion, and coordination with transcription service.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable
from collections import deque
import io

logger = logging.getLogger(__name__)


class AudioChunk:
    """Represents a chunk of audio data with metadata."""

    def __init__(self, data: bytes, timestamp: float, sequence_number: int, format: str = "webm"):
        self.data = data
        self.timestamp = timestamp
        self.sequence_number = sequence_number
        self.format = format
        self.size_bytes = len(data)


class AudioBuffer:
    """
    Buffer for accumulating audio chunks before transcription.

    Manages sliding window of audio data to ensure we have enough context
    for accurate transcription.
    """

    def __init__(self, min_duration_ms: int = 2000, max_duration_ms: int = 5000):
        """
        Initialize audio buffer.

        Args:
            min_duration_ms: Minimum audio duration before triggering transcription
            max_duration_ms: Maximum audio duration before forcing transcription
        """
        self.min_duration_ms = min_duration_ms
        self.max_duration_ms = max_duration_ms

        self.chunks: deque[AudioChunk] = deque()
        self.total_bytes = 0
        self.total_duration_ms = 0
        self.first_chunk_timestamp: Optional[float] = None

    def add_chunk(self, chunk: AudioChunk):
        """Add an audio chunk to the buffer."""
        self.chunks.append(chunk)
        self.total_bytes += chunk.size_bytes

        if self.first_chunk_timestamp is None:
            self.first_chunk_timestamp = chunk.timestamp

        # Estimate duration based on typical bitrate (100KB/sec for WebM)
        estimated_duration_ms = (self.total_bytes / 100_000) * 1000
        self.total_duration_ms = estimated_duration_ms

    def is_ready_for_transcription(self) -> bool:
        """Check if buffer has enough audio for transcription."""
        return self.total_duration_ms >= self.min_duration_ms

    def should_force_transcription(self) -> bool:
        """Check if buffer should be forcibly transcribed (too full)."""
        return self.total_duration_ms >= self.max_duration_ms

    def get_combined_audio(self) -> bytes:
        """Combine all chunks into a single audio buffer."""
        return b''.join(chunk.data for chunk in self.chunks)

    def clear(self):
        """Clear the buffer."""
        self.chunks.clear()
        self.total_bytes = 0
        self.total_duration_ms = 0
        self.first_chunk_timestamp = None

    def get_info(self) -> Dict[str, Any]:
        """Get buffer information."""
        return {
            "num_chunks": len(self.chunks),
            "total_bytes": self.total_bytes,
            "estimated_duration_ms": self.total_duration_ms,
            "is_ready": self.is_ready_for_transcription(),
            "should_force": self.should_force_transcription(),
        }


class AudioProcessor:
    """
    Real-time audio processor for conversation intelligence.

    Manages audio buffering, transcription triggering, and coordination
    with downstream services (sentiment analysis, suggestion engine).
    """

    def __init__(
        self,
        conversation_id: str,
        transcription_service,
        on_transcription_callback: Optional[Callable] = None,
        min_buffer_duration_ms: int = 2000,
        max_buffer_duration_ms: int = 5000,
    ):
        """
        Initialize audio processor.

        Args:
            conversation_id: Unique conversation identifier
            transcription_service: TranscriptionService instance
            on_transcription_callback: Async callback when transcription completes
            min_buffer_duration_ms: Minimum audio duration before transcription
            max_buffer_duration_ms: Maximum audio duration before forcing transcription
        """
        self.conversation_id = conversation_id
        self.transcription_service = transcription_service
        self.on_transcription_callback = on_transcription_callback

        self.buffer = AudioBuffer(min_buffer_duration_ms, max_buffer_duration_ms)

        self.sequence_number = 0
        self.is_processing = False
        self.is_active = True

        # Performance tracking
        self.total_chunks_received = 0
        self.total_transcriptions = 0
        self.total_audio_bytes = 0

        logger.info(f"AudioProcessor initialized for conversation {conversation_id}")

    async def process_audio_chunk(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        force_transcribe: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Process an incoming audio chunk.

        Buffers the chunk and triggers transcription when appropriate.

        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (webm, mp3, wav, etc.)
            force_transcribe: Force immediate transcription

        Returns:
            Transcription result if triggered, None otherwise
        """
        if not self.is_active:
            logger.warning(f"AudioProcessor {self.conversation_id} is inactive")
            return None

        # Create audio chunk
        chunk = AudioChunk(
            data=audio_data,
            timestamp=time.time(),
            sequence_number=self.sequence_number,
            format=audio_format,
        )

        self.sequence_number += 1
        self.total_chunks_received += 1
        self.total_audio_bytes += len(audio_data)

        # Add to buffer
        self.buffer.add_chunk(chunk)

        logger.debug(f"Audio chunk {chunk.sequence_number} added: {len(audio_data)} bytes. Buffer: {self.buffer.get_info()}")

        # Check if we should transcribe
        should_transcribe = force_transcribe or self.buffer.is_ready_for_transcription() or self.buffer.should_force_transcription()

        if should_transcribe and not self.is_processing:
            return await self._trigger_transcription(audio_format)

        return None

    async def _trigger_transcription(self, audio_format: str) -> Dict[str, Any]:
        """
        Trigger transcription of buffered audio.

        Args:
            audio_format: Audio format

        Returns:
            Transcription result
        """
        if self.is_processing:
            logger.warning(f"Transcription already in progress for {self.conversation_id}")
            return None

        self.is_processing = True

        try:
            # Get combined audio from buffer
            audio_data = self.buffer.get_combined_audio()
            buffer_info = self.buffer.get_info()

            logger.info(f"Triggering transcription for {self.conversation_id}: {buffer_info}")

            # Transcribe audio
            result = await self.transcription_service.transcribe_audio(
                audio_data=audio_data,
                audio_format=audio_format,
            )

            self.total_transcriptions += 1

            # Add metadata
            result["conversation_id"] = self.conversation_id
            result["sequence_number"] = self.sequence_number - len(self.buffer.chunks)
            result["buffer_info"] = buffer_info

            # Clear buffer
            self.buffer.clear()

            # Call callback if provided
            if self.on_transcription_callback:
                try:
                    await self.on_transcription_callback(result)
                except Exception as e:
                    logger.error(f"Transcription callback error: {e}")

            logger.info(f"Transcription completed: '{result['text'][:50]}...' ({result['latency_ms']}ms)")

            return result

        except Exception as e:
            logger.error(f"Transcription failed for {self.conversation_id}: {e}")
            # Don't clear buffer on error - might retry
            raise

        finally:
            self.is_processing = False

    async def flush(self, audio_format: str = "webm") -> Optional[Dict[str, Any]]:
        """
        Force transcription of any remaining buffered audio.

        Useful when conversation ends or pauses.

        Args:
            audio_format: Audio format

        Returns:
            Transcription result if buffer not empty, None otherwise
        """
        if len(self.buffer.chunks) == 0:
            return None

        logger.info(f"Flushing audio buffer for {self.conversation_id}")
        return await self._trigger_transcription(audio_format)

    def stop(self):
        """Stop processing audio."""
        self.is_active = False
        logger.info(f"AudioProcessor stopped for {self.conversation_id}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "conversation_id": self.conversation_id,
            "total_chunks_received": self.total_chunks_received,
            "total_transcriptions": self.total_transcriptions,
            "total_audio_bytes": self.total_audio_bytes,
            "total_audio_mb": round(self.total_audio_bytes / (1024 * 1024), 2),
            "current_buffer": self.buffer.get_info(),
            "is_active": self.is_active,
            "is_processing": self.is_processing,
        }


class AudioProcessorManager:
    """
    Manages multiple AudioProcessor instances for concurrent conversations.
    """

    def __init__(self, transcription_service):
        """
        Initialize manager.

        Args:
            transcription_service: TranscriptionService instance
        """
        self.transcription_service = transcription_service
        self.processors: Dict[str, AudioProcessor] = {}

    def create_processor(
        self,
        conversation_id: str,
        on_transcription_callback: Optional[Callable] = None,
        min_buffer_duration_ms: int = 2000,
        max_buffer_duration_ms: int = 5000,
    ) -> AudioProcessor:
        """Create a new audio processor for a conversation."""
        if conversation_id in self.processors:
            logger.warning(f"AudioProcessor already exists for {conversation_id}")
            return self.processors[conversation_id]

        processor = AudioProcessor(
            conversation_id=conversation_id,
            transcription_service=self.transcription_service,
            on_transcription_callback=on_transcription_callback,
            min_buffer_duration_ms=min_buffer_duration_ms,
            max_buffer_duration_ms=max_buffer_duration_ms,
        )

        self.processors[conversation_id] = processor
        logger.info(f"Created AudioProcessor for conversation {conversation_id}")

        return processor

    def get_processor(self, conversation_id: str) -> Optional[AudioProcessor]:
        """Get an existing audio processor."""
        return self.processors.get(conversation_id)

    async def remove_processor(self, conversation_id: str):
        """Remove and cleanup an audio processor."""
        processor = self.processors.get(conversation_id)
        if processor:
            # Flush any remaining audio
            await processor.flush()
            processor.stop()
            del self.processors[conversation_id]
            logger.info(f"Removed AudioProcessor for conversation {conversation_id}")

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all active processors."""
        return [processor.get_metrics() for processor in self.processors.values()]


# Global instance
_audio_processor_manager = None


def get_audio_processor_manager(transcription_service) -> AudioProcessorManager:
    """Get or create global audio processor manager."""
    global _audio_processor_manager
    if _audio_processor_manager is None:
        _audio_processor_manager = AudioProcessorManager(transcription_service)
    return _audio_processor_manager
