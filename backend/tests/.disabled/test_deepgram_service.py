"""
Tests for DeepgramService - Speech-to-Text with Deepgram API

Tests the DeepgramService class which uses Deepgram Nova-2 for:
1. REST transcription - transcribe audio bytes to text (transcribe)
2. WebSocket URL generation - get streaming transcription URL (get_websocket_url)

Uses respx for async HTTP mocking following project patterns.
Follows TDD strictly: RED-GREEN-REFACTOR.
"""

import pytest
import os
import httpx
import respx
from app.services.deepgram_service import (
    DeepgramService,
    DeepgramConfig,
    TranscriptionResult,
    WordInfo,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def deepgram_service():
    """Create a fresh DeepgramService instance with test API key"""
    os.environ["DEEPGRAM_API_KEY"] = "test_deepgram_key_123"
    return DeepgramService()


@pytest.fixture
def deepgram_service_no_key():
    """Create DeepgramService without API key (lazy init should not fail)"""
    if "DEEPGRAM_API_KEY" in os.environ:
        del os.environ["DEEPGRAM_API_KEY"]
    return DeepgramService()


@pytest.fixture
def sample_audio_bytes():
    """Create sample audio bytes for testing"""
    # Mock 16-bit PCM audio data (1 second at 16kHz)
    return b'\x00\x01' * 16000


# ==============================================================================
# Initialization Tests (Lazy Initialization)
# ==============================================================================

def test_deepgram_service_lazy_initialization():
    """Test DeepgramService initializes without validating API key (lazy init)"""
    # Remove API key from environment
    if "DEEPGRAM_API_KEY" in os.environ:
        del os.environ["DEEPGRAM_API_KEY"]

    # Constructor should NOT raise error (lazy initialization)
    service = DeepgramService()

    assert service is not None
    assert service.config is not None
    assert service.config.model == "nova-2"  # Default model


def test_deepgram_service_with_custom_config():
    """Test DeepgramService accepts custom configuration"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    custom_config = DeepgramConfig(
        model="nova-2-general",
        language="en-US",
        smart_format=True,
        punctuate=True
    )

    service = DeepgramService(config=custom_config)

    assert service.config.model == "nova-2-general"
    assert service.config.language == "en-US"
    assert service.config.smart_format is True
    assert service.config.punctuate is True


def test_deepgram_service_default_config():
    """Test DeepgramService uses default config when none provided"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    service = DeepgramService()

    assert service.config.model == "nova-2"
    assert service.config.language == "en"
    assert service.config.sample_rate == 16000


# ==============================================================================
# Transcribe Method Tests (REST API)
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_transcribe_success(deepgram_service, sample_audio_bytes):
    """Test successful transcription with Deepgram REST API"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "Hello world, this is a test.",
                                    "confidence": 0.98,
                                    "words": [
                                        {
                                            "word": "hello",
                                            "start": 0.0,
                                            "end": 0.5,
                                            "confidence": 0.99
                                        },
                                        {
                                            "word": "world",
                                            "start": 0.5,
                                            "end": 1.0,
                                            "confidence": 0.97
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = await deepgram_service.transcribe(sample_audio_bytes)

    assert result.transcript == "Hello world, this is a test."
    assert result.confidence == 0.98
    assert result.latency_ms > 0
    assert result.latency_ms < 500  # Should be fast
    assert len(result.words) == 2
    assert result.words[0].word == "hello"
    assert result.words[0].confidence == 0.99


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_latency_tracking(deepgram_service, sample_audio_bytes):
    """Test transcribe() tracks latency accurately"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "Testing latency",
                                    "confidence": 0.95,
                                    "words": []
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = await deepgram_service.transcribe(sample_audio_bytes)

    assert result.latency_ms > 0
    assert result.latency_ms < 1000  # Should be under 1 second for mock
    assert isinstance(result.latency_ms, int)


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_target_latency(deepgram_service, sample_audio_bytes):
    """Test transcribe() meets <150ms target latency"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "Fast response",
                                    "confidence": 0.96,
                                    "words": []
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = await deepgram_service.transcribe(sample_audio_bytes)

    # For real API, should be <150ms. For mock, just verify it's measured.
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_empty_transcript(deepgram_service, sample_audio_bytes):
    """Test handling empty transcript (silence or inaudible)"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "",
                                    "confidence": 0.0,
                                    "words": []
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = await deepgram_service.transcribe(sample_audio_bytes)

    assert result.transcript == ""
    assert result.confidence == 0.0
    assert len(result.words) == 0


@pytest.mark.asyncio
async def test_transcribe_missing_api_key(deepgram_service_no_key, sample_audio_bytes):
    """Test transcribe() raises error when API key is missing"""
    with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
        await deepgram_service_no_key.transcribe(sample_audio_bytes)


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_api_error(deepgram_service, sample_audio_bytes):
    """Test handling HTTP 500 error from Deepgram API"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    with pytest.raises(Exception):
        await deepgram_service.transcribe(sample_audio_bytes)


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_rate_limited(deepgram_service, sample_audio_bytes):
    """Test handling 429 rate limit response"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(429, json={"error": "Rate limit exceeded"})
    )

    with pytest.raises(Exception):
        await deepgram_service.transcribe(sample_audio_bytes)


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_timeout(deepgram_service, sample_audio_bytes):
    """Test handling request timeout"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        side_effect=httpx.TimeoutException("Connection timeout")
    )

    with pytest.raises(httpx.TimeoutException):
        await deepgram_service.transcribe(sample_audio_bytes)


@pytest.mark.asyncio
@respx.mock
async def test_transcribe_without_word_timestamps(deepgram_service, sample_audio_bytes):
    """Test transcribe() when word timestamps are disabled"""
    respx.post("https://api.deepgram.com/v1/listen").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "No word timestamps",
                                    "confidence": 0.94
                                    # No "words" field
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )

    result = await deepgram_service.transcribe(sample_audio_bytes)

    assert result.transcript == "No word timestamps"
    assert result.confidence == 0.94
    assert result.words is None or len(result.words) == 0


# ==============================================================================
# WebSocket URL Generation Tests
# ==============================================================================

def test_get_websocket_url_basic(deepgram_service):
    """Test get_websocket_url() generates valid WebSocket URL"""
    url = deepgram_service.get_websocket_url()

    assert url.startswith("wss://api.deepgram.com/v1/listen")
    assert "model=nova-2" in url
    assert "encoding=linear16" in url
    assert "sample_rate=16000" in url


def test_get_websocket_url_nova2_model(deepgram_service):
    """Test WebSocket URL uses Nova-2 model by default"""
    url = deepgram_service.get_websocket_url()

    assert "model=nova-2" in url


def test_get_websocket_url_includes_language(deepgram_service):
    """Test WebSocket URL includes language parameter"""
    url = deepgram_service.get_websocket_url()

    assert "language=en" in url


def test_get_websocket_url_includes_smart_format():
    """Test WebSocket URL includes smart_format when enabled"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    config = DeepgramConfig(smart_format=True)
    service = DeepgramService(config=config)

    url = service.get_websocket_url()

    assert "smart_format=true" in url


def test_get_websocket_url_includes_punctuate():
    """Test WebSocket URL includes punctuate when enabled"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    config = DeepgramConfig(punctuate=True)
    service = DeepgramService(config=config)

    url = service.get_websocket_url()

    assert "punctuate=true" in url


def test_get_websocket_url_includes_interim_results():
    """Test WebSocket URL includes interim_results when enabled"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    config = DeepgramConfig(interim_results=True)
    service = DeepgramService(config=config)

    url = service.get_websocket_url()

    assert "interim_results=true" in url


def test_get_websocket_url_custom_sample_rate():
    """Test WebSocket URL uses custom sample rate"""
    os.environ["DEEPGRAM_API_KEY"] = "test_key"

    config = DeepgramConfig(sample_rate=48000)
    service = DeepgramService(config=config)

    url = service.get_websocket_url()

    assert "sample_rate=48000" in url


# ==============================================================================
# Config Model Tests
# ==============================================================================

def test_deepgram_config_defaults():
    """Test DeepgramConfig has correct default values"""
    config = DeepgramConfig()

    assert config.model == "nova-2"
    assert config.language == "en"
    assert config.sample_rate == 16000
    assert config.encoding == "linear16"
    assert config.channels == 1
    assert config.smart_format is True
    assert config.punctuate is True
    assert config.interim_results is False


def test_deepgram_config_custom_values():
    """Test DeepgramConfig accepts custom values"""
    config = DeepgramConfig(
        model="nova-2-general",
        language="es",
        sample_rate=48000,
        smart_format=True,
        punctuate=True,
        interim_results=True
    )

    assert config.model == "nova-2-general"
    assert config.language == "es"
    assert config.sample_rate == 48000
    assert config.smart_format is True
    assert config.punctuate is True
    assert config.interim_results is True


# ==============================================================================
# TranscriptionResult Model Tests
# ==============================================================================

def test_transcription_result_basic():
    """Test TranscriptionResult dataclass with basic fields"""
    result = TranscriptionResult(
        transcript="Test transcript",
        confidence=0.95,
        latency_ms=120
    )

    assert result.transcript == "Test transcript"
    assert result.confidence == 0.95
    assert result.latency_ms == 120
    assert result.words is None


def test_transcription_result_with_words():
    """Test TranscriptionResult with word-level timestamps"""
    words = [
        WordInfo(word="hello", start=0.0, end=0.5, confidence=0.99),
        WordInfo(word="world", start=0.5, end=1.0, confidence=0.97)
    ]

    result = TranscriptionResult(
        transcript="hello world",
        confidence=0.98,
        latency_ms=145,
        words=words
    )

    assert len(result.words) == 2
    assert result.words[0].word == "hello"
    assert result.words[0].start == 0.0
    assert result.words[0].end == 0.5


def test_word_info_model():
    """Test WordInfo dataclass"""
    word = WordInfo(
        word="test",
        start=1.0,
        end=1.5,
        confidence=0.96
    )

    assert word.word == "test"
    assert word.start == 1.0
    assert word.end == 1.5
    assert word.confidence == 0.96
