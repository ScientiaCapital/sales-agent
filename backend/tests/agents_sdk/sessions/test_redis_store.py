"""Test Redis session storage."""
import pytest
from datetime import datetime, timedelta, UTC


@pytest.fixture(scope="function")
async def redis_store():
    """Create a fresh RedisSessionStore for each test."""
    from app.agents_sdk.sessions.redis_store import RedisSessionStore
    import redis.asyncio as redis
    import os

    # Create a new Redis client for each test to avoid event loop issues
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(
        redis_url,
        decode_responses=True,
        encoding="utf-8"
    )

    # Create store with the new client
    store = RedisSessionStore(redis_client)
    yield store

    # Cleanup
    await redis_client.aclose()


@pytest.mark.asyncio
async def test_create_and_retrieve_session(redis_store):
    """Test session creation and retrieval from Redis."""
    from app.agents_sdk.schemas.chat import ChatMessage

    # Create session
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    assert session_id.startswith("sess_")

    # Retrieve session
    session = await redis_store.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "test_user"
    assert session["agent_type"] == "sr_bdr"
    assert len(session["messages"]) == 0


@pytest.mark.asyncio
async def test_add_message_to_session(redis_store):
    """Test adding messages to session."""
    from app.agents_sdk.schemas.chat import ChatMessage

    session_id = await redis_store.create_session("user_123", "sr_bdr")

    # Add message
    message = ChatMessage(role="user", content="Hello", timestamp=datetime.now(UTC))
    await redis_store.add_message(session_id, message)

    # Verify
    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 1
    assert session["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_session_expiry(redis_store):
    """Test session TTL expiration."""
    session_id = await redis_store.create_session("user_123", "sr_bdr")

    # Check TTL is set
    ttl = await redis_store.get_ttl(session_id)
    assert ttl > 0
    assert ttl <= 86400  # 24 hours


@pytest.mark.asyncio
async def test_cache_and_retrieve_tool_result(redis_store):
    """Test tool result caching and retrieval."""
    session_id = await redis_store.create_session("user_456", "sr_bdr")

    # Cache a tool result
    tool_name = "search_contacts"
    args = {"query": "test@example.com"}
    result = {"contact_id": "123", "name": "John Doe"}

    await redis_store.cache_tool_result(session_id, tool_name, args, result)

    # Retrieve cached result
    cached_result = await redis_store.get_cached_tool_result(session_id, tool_name, args)
    assert cached_result is not None
    assert cached_result["contact_id"] == "123"
    assert cached_result["name"] == "John Doe"


@pytest.mark.asyncio
async def test_cached_tool_result_expiration(redis_store):
    """Test cache expiration logic."""
    import asyncio

    session_id = await redis_store.create_session("user_789", "sr_bdr")

    # Cache with short TTL (1 second)
    tool_name = "fetch_company_data"
    args = {"company_id": "456"}
    result = {"company": "Acme Corp"}

    await redis_store.cache_tool_result(session_id, tool_name, args, result, ttl=1)

    # Should be available immediately
    cached_result = await redis_store.get_cached_tool_result(session_id, tool_name, args)
    assert cached_result is not None
    assert cached_result["company"] == "Acme Corp"

    # Wait for expiration (slightly longer than TTL)
    await asyncio.sleep(1.1)

    # Should be expired now
    expired_result = await redis_store.get_cached_tool_result(session_id, tool_name, args)
    assert expired_result is None


@pytest.mark.asyncio
async def test_delete_session(redis_store):
    """Test session deletion."""
    from app.agents_sdk.schemas.chat import ChatMessage

    # Create session with data
    session_id = await redis_store.create_session("user_delete", "sr_bdr")
    message = ChatMessage(role="user", content="Test message", timestamp=datetime.now(UTC))
    await redis_store.add_message(session_id, message)

    # Verify session exists
    session = await redis_store.get_session(session_id)
    assert session is not None
    assert len(session["messages"]) == 1

    # Delete session
    await redis_store.delete_session(session_id)

    # Verify session is gone
    deleted_session = await redis_store.get_session(session_id)
    assert deleted_session is None
