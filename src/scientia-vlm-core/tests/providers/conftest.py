"""
Shared fixtures for VLM provider unit tests.

TDD fixtures with zero shared state between tests.
All fixtures are function-scoped for test isolation.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

# =============================================================================
# IMAGE FIXTURES - Fresh bytes for each test
# =============================================================================


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Create fresh JPEG bytes for each test."""
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Create fresh PNG bytes for each test."""
    img = Image.new("RGB", (100, 100), color=(64, 64, 64))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def sample_webp_bytes() -> bytes:
    """Create fresh WebP bytes for each test."""
    img = Image.new("RGB", (100, 100), color=(32, 32, 32))
    buffer = io.BytesIO()
    img.save(buffer, format="WEBP")
    return buffer.getvalue()


@pytest.fixture
def sample_gif_bytes() -> bytes:
    """Create fresh GIF bytes for each test."""
    img = Image.new("P", (100, 100), color=64)
    buffer = io.BytesIO()
    img.save(buffer, format="GIF")
    return buffer.getvalue()


@pytest.fixture
def temp_jpeg_path(tmp_path: Path, sample_jpeg_bytes: bytes) -> Path:
    """Create temporary JPEG file - unique per test via tmp_path."""
    img_path = tmp_path / "test_image.jpg"
    img_path.write_bytes(sample_jpeg_bytes)
    return img_path


@pytest.fixture
def temp_png_path(tmp_path: Path, sample_png_bytes: bytes) -> Path:
    """Create temporary PNG file - unique per test via tmp_path."""
    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(sample_png_bytes)
    return img_path


@pytest.fixture
def corrupt_image_bytes() -> bytes:
    """Invalid image bytes for error testing."""
    return b"not a valid image file at all"


@pytest.fixture
def temp_corrupt_path(tmp_path: Path, corrupt_image_bytes: bytes) -> Path:
    """Create temporary corrupt image file."""
    img_path = tmp_path / "corrupt.bin"
    img_path.write_bytes(corrupt_image_bytes)
    return img_path


# =============================================================================
# MOCK API RESPONSE FIXTURES
# =============================================================================


@pytest.fixture
def mock_openai_response() -> MagicMock:
    """Mock OpenAI/OpenRouter chat completion response."""
    response = MagicMock()
    response.id = "chatcmpl-test-123"
    response.choices = [MagicMock()]
    json_content = '{"image_type": "blueprint", "trade": "solar"}'
    response.choices[0].message.content = f"```json\n{json_content}\n```"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 1000
    response.usage.completion_tokens = 500
    return response


@pytest.fixture
def mock_anthropic_response() -> MagicMock:
    """Mock Anthropic message response."""
    response = MagicMock()
    response.id = "msg-test-123"
    text_block = MagicMock()
    text_block.text = '```json\n{"image_type": "blueprint", "trade": "electrical"}\n```'
    response.content = [text_block]
    response.usage = MagicMock()
    response.usage.input_tokens = 1000
    response.usage.output_tokens = 500
    return response


@pytest.fixture
def mock_gemini_response() -> MagicMock:
    """Mock Gemini generate_content response."""
    response = MagicMock()
    response.text = '```json\n{"image_type": "field_photo", "trade": "hvac"}\n```'
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 1000
    response.usage_metadata.candidates_token_count = 500
    return response


# =============================================================================
# API ERROR FIXTURES
# =============================================================================


@pytest.fixture
def api_error() -> Exception:
    """Generic API error for error handling tests."""
    return Exception("API Error: Connection failed")


@pytest.fixture
def rate_limit_error() -> Exception:
    """Rate limit error for retry testing."""
    return Exception("Rate limit exceeded. Please retry after 60 seconds.")


@pytest.fixture
def auth_error() -> Exception:
    """Authentication error for key validation testing."""
    return Exception("Invalid API key provided")


# =============================================================================
# MOCK CLIENT FACTORIES
# =============================================================================


@pytest.fixture
def mock_async_openai_client(mock_openai_response: MagicMock) -> AsyncMock:
    """Create mocked AsyncOpenAI client."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
    return client


@pytest.fixture
def mock_async_anthropic_client(mock_anthropic_response: MagicMock) -> AsyncMock:
    """Create mocked AsyncAnthropic client."""
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=mock_anthropic_response)
    return client


@pytest.fixture
def mock_genai_client(mock_gemini_response: MagicMock) -> MagicMock:
    """Create mocked Google GenAI client."""
    client = MagicMock()
    model = MagicMock()
    model.generate_content = MagicMock(return_value=mock_gemini_response)
    client.models.generate_content = MagicMock(return_value=mock_gemini_response)
    return client


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_prompt() -> str:
    """Standard test prompt for analysis."""
    return "Analyze this construction image and extract structured data."


@pytest.fixture
def valid_api_key() -> str:
    """Valid test API key."""
    return "sk-test-api-key-12345"


@pytest.fixture
def empty_api_key() -> str:
    """Empty API key for validation testing."""
    return ""


@pytest.fixture
def whitespace_api_key() -> str:
    """Whitespace-only API key for validation testing."""
    return "   "
