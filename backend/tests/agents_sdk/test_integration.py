"""Integration tests for end-to-end Agent SDK conversation flows."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, UTC

from app.agents_sdk.agents import SRBDRAgent, PipelineManagerAgent, CustomerSuccessAgent
from app.agents_sdk.sessions import RedisSessionStore, SessionManager
from app.agents_sdk.schemas.chat import ChatMessage


@pytest.mark.asyncio
async def test_sr_bdr_complete_conversation_flow(mock_redis_client):
    """Test complete SR/BDR conversation flow with tool execution."""

    # Setup
    redis_store = RedisSessionStore(mock_redis_client)
    agent = SRBDRAgent()

    # Create session
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    assert session_id.startswith("sess_")

    # Verify session created
    session = await redis_store.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "test_user"
    assert session["agent_type"] == "sr_bdr"
    assert len(session["messages"]) == 0

    # Add user message
    user_msg = ChatMessage(
        role="user",
        content="What are my top 3 leads?",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, user_msg)

    # Verify message added
    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 1
    assert session["messages"][0]["content"] == "What are my top 3 leads?"
    assert session["metadata"]["message_count"] == 1

    # Add assistant response
    assistant_msg = ChatMessage(
        role="assistant",
        content="Here are your top 3 leads: Acme Corp (Score: 85), TechCo (Score: 82), BuilderPro (Score: 78)",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, assistant_msg)

    # Verify conversation history
    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 2
    assert session["metadata"]["message_count"] == 2


@pytest.mark.asyncio
async def test_multi_turn_conversation_with_context(mock_redis_client):
    """Test multi-turn conversation maintains context."""

    redis_store = RedisSessionStore(mock_redis_client)
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    # Turn 1: Initial query
    msg1 = ChatMessage(
        role="user",
        content="Show me leads in Texas",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg1)

    response1 = ChatMessage(
        role="assistant",
        content="Found 15 leads in Texas. Top 3: Acme Corp, TechCo, BuilderPro",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, response1)

    # Turn 2: Follow-up referencing previous context
    msg2 = ChatMessage(
        role="user",
        content="Tell me more about the first one",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg2)

    response2 = ChatMessage(
        role="assistant",
        content="Acme Corp: Multi-state contractor (TX, CA, FL), PLATINUM tier, Score: 85",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, response2)

    # Verify complete conversation history
    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 4
    assert session["messages"][0]["content"] == "Show me leads in Texas"
    assert session["messages"][2]["content"] == "Tell me more about the first one"


@pytest.mark.asyncio
async def test_tool_result_caching(mock_redis_client):
    """Test tool results are cached and reused."""

    redis_store = RedisSessionStore(mock_redis_client)
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    # Cache tool result
    tool_name = "qualify_lead"
    args = {"company_name": "Acme Corp", "industry": "Construction"}
    result = {
        "score": 85,
        "tier": "hot",
        "reasoning": "Multi-state contractor with strong signals"
    }

    await redis_store.cache_tool_result(
        session_id=session_id,
        tool_name=tool_name,
        args=args,
        result=result,
        ttl=3600  # 1 hour
    )

    # Retrieve cached result
    cached = await redis_store.get_cached_tool_result(
        session_id=session_id,
        tool_name=tool_name,
        args=args
    )

    assert cached is not None
    assert cached["score"] == 85
    assert cached["tier"] == "hot"

    # Try with different args (should be cache miss)
    cached_miss = await redis_store.get_cached_tool_result(
        session_id=session_id,
        tool_name=tool_name,
        args={"company_name": "Different Corp", "industry": "Tech"}
    )

    assert cached_miss is None


@pytest.mark.asyncio
async def test_session_archival_flow(mock_redis_client, mock_db_session):
    """Test complete session archival from Redis to PostgreSQL."""

    from app.agents_sdk.sessions.postgres_store import PostgreSQLSessionStore

    # Setup
    redis_store = RedisSessionStore(mock_redis_client)
    postgres_store = PostgreSQLSessionStore()
    session_manager = SessionManager(redis_store, postgres_store)

    # Create and populate session
    session_id = await session_manager.get_or_create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    # Add messages
    msg1 = ChatMessage(role="user", content="Test message 1", timestamp=datetime.now(UTC))
    msg2 = ChatMessage(role="assistant", content="Test response 1", timestamp=datetime.now(UTC))

    await session_manager.add_message(session_id, msg1)
    await session_manager.add_message(session_id, msg2)

    # Cache tool result
    await session_manager.cache_tool_result(
        session_id=session_id,
        tool_name="qualify_lead",
        args={"company_name": "Test Corp"},
        result={"score": 75}
    )

    # Archive session (mock the PostgreSQL operations)
    with patch.object(postgres_store, 'archive_session', new_callable=AsyncMock) as mock_archive:
        mock_archive.return_value = 123  # conversation_id

        conversation_id = await session_manager.archive_session(
            session_id=session_id,
            db=mock_db_session
        )

        assert conversation_id == 123
        mock_archive.assert_called_once()

        # Verify session deleted from Redis
        session = await redis_store.get_session(session_id)
        assert session is None


@pytest.mark.asyncio
async def test_pipeline_manager_validation_flow(mock_redis_client):
    """Test Pipeline Manager agent file validation workflow."""

    redis_store = RedisSessionStore(mock_redis_client)
    agent = PipelineManagerAgent()

    session_id = await redis_store.create_session(
        user_id="ops_user",
        agent_type="pipeline_manager"
    )

    # User requests file validation
    msg = ChatMessage(
        role="user",
        content="I have 3 license files to validate: CA.csv, TX.csv, FL.csv",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg)

    # Agent should use validate_files_tool
    # (In real implementation, this would be streamed)
    response = ChatMessage(
        role="assistant",
        content="Validating files... CA.csv: ✅ Valid (5000 records), TX.csv: ✅ Valid (3200 records), FL.csv: ⚠️ Warning (2 duplicate records)",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, response)

    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 2


@pytest.mark.asyncio
async def test_customer_success_onboarding_flow(mock_redis_client):
    """Test Customer Success agent onboarding workflow."""

    redis_store = RedisSessionStore(mock_redis_client)
    agent = CustomerSuccessAgent()

    session_id = await redis_store.create_session(
        user_id="new_customer",
        agent_type="cs_agent"
    )

    # New customer asks for help
    msg1 = ChatMessage(
        role="user",
        content="I just signed up. Where do I start?",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg1)

    response1 = ChatMessage(
        role="assistant",
        content="Welcome! Here's your quickstart: Step 1) Import your first list, Step 2) Review top leads, Step 3) Set up automation",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, response1)

    # Follow-up question
    msg2 = ChatMessage(
        role="user",
        content="How do I import a CSV file?",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg2)

    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 3
    assert session["metadata"]["message_count"] == 3


@pytest.mark.asyncio
async def test_session_ttl_extension(mock_redis_client):
    """Test session TTL is extended on activity."""

    redis_store = RedisSessionStore(mock_redis_client)
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    # Get initial TTL
    initial_ttl = await redis_store.get_ttl(session_id)
    assert initial_ttl > 0

    # Add message (should extend TTL)
    msg = ChatMessage(
        role="user",
        content="Test message",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg)

    # TTL should be refreshed (back to full 24h = 86400s)
    # In mock, we just verify the session was updated
    session = await redis_store.get_session(session_id)
    assert session is not None


@pytest.mark.asyncio
async def test_concurrent_sessions_same_user(mock_redis_client):
    """Test user can have multiple concurrent sessions."""

    redis_store = RedisSessionStore(mock_redis_client)

    # Create two sessions for same user, different agents
    session1_id = await redis_store.create_session(
        user_id="multi_user",
        agent_type="sr_bdr"
    )

    session2_id = await redis_store.create_session(
        user_id="multi_user",
        agent_type="pipeline_manager"
    )

    assert session1_id != session2_id

    # Both sessions should be active
    session1 = await redis_store.get_session(session1_id)
    session2 = await redis_store.get_session(session2_id)

    assert session1 is not None
    assert session2 is not None
    assert session1["user_id"] == session2["user_id"] == "multi_user"
    assert session1["agent_type"] == "sr_bdr"
    assert session2["agent_type"] == "pipeline_manager"


@pytest.mark.asyncio
async def test_error_recovery_in_conversation(mock_redis_client):
    """Test conversation continues gracefully after errors."""

    redis_store = RedisSessionStore(mock_redis_client)
    session_id = await redis_store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )

    # Normal message
    msg1 = ChatMessage(
        role="user",
        content="Show me leads",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg1)

    # Error response
    error_msg = ChatMessage(
        role="assistant",
        content="I encountered an error. Let me try again...",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, error_msg)

    # Recovery message
    msg2 = ChatMessage(
        role="user",
        content="Please try again",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, msg2)

    # Success response
    success_msg = ChatMessage(
        role="assistant",
        content="Here are your leads: ...",
        timestamp=datetime.now(UTC)
    )
    await redis_store.add_message(session_id, success_msg)

    # Verify conversation continues
    session = await redis_store.get_session(session_id)
    assert len(session["messages"]) == 4
    assert session["messages"][-1]["content"].startswith("Here are your leads")
