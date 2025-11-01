"""Test chat schemas."""
import pytest
from datetime import datetime, UTC


def test_chat_message_creation():
    """Test ChatMessage can be created."""
    from app.agents_sdk.schemas.chat import ChatMessage

    msg = ChatMessage(
        role="user",
        content="Test message",
        timestamp=datetime.now(UTC)
    )

    assert msg.role == "user"
    assert msg.content == "Test message"
    assert msg.timestamp is not None


def test_chat_request_validation():
    """Test ChatRequest validates required fields."""
    from app.agents_sdk.schemas.chat import ChatRequest

    # Valid request
    req = ChatRequest(
        user_id="test_user",
        message="Hello",
        stream=True
    )
    assert req.user_id == "test_user"

    # Missing user_id should fail
    with pytest.raises(Exception):  # Pydantic ValidationError
        ChatRequest(message="Hello")


def test_sse_chunk_formatting():
    """Test SSE chunk can be created."""
    from app.agents_sdk.schemas.chat import SSEChunk

    chunk = SSEChunk(
        event="message",
        data={"content": "Hello"}
    )

    formatted = chunk.format_sse()
    assert "event: message" in formatted
    assert "data: " in formatted
