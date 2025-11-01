# Claude Agent SDK Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add conversational intelligence layer (3 agents) using Claude Agent SDK over existing LangGraph automation.

**Architecture:** Modular monolith - SDK agents as FastAPI modules with direct LangGraph imports via MCP tools. Hybrid session management (Redis hot + PostgreSQL archive).

**Tech Stack:** Claude Agent SDK 0.1.5, FastAPI, Redis, PostgreSQL, Pydantic 2.12+

---

## Task 1: Module Structure Setup

**Files:**
- Create: `backend/app/agents_sdk/__init__.py`
- Create: `backend/app/agents_sdk/config.py`
- Create: `backend/app/agents_sdk/schemas/__init__.py`

**Step 1: Write basic imports test**

File: `backend/tests/agents_sdk/test_imports.py`

```python
"""Test that agents_sdk module imports correctly."""
import pytest


def test_agents_sdk_module_imports():
    """Test agents_sdk package can be imported."""
    from app.agents_sdk import __version__
    assert __version__ == "0.1.0"


def test_config_imports():
    """Test config module imports."""
    from app.agents_sdk.config import AgentSDKConfig
    assert AgentSDKConfig is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/agents_sdk/test_imports.py -v`  
Expected: FAIL - "ModuleNotFoundError: No module named 'app.agents_sdk'"

**Step 3: Create module structure**

File: `backend/app/agents_sdk/__init__.py`

```python
"""
Claude Agent SDK Integration Layer

Conversational agents built with Claude Agent SDK that provide
natural language interfaces over existing LangGraph automation.

Architecture:
    - Conversational Layer: Claude Agent SDK (session management, NL)
    - Automation Layer: LangGraph Agents (qualification, enrichment, etc.)
    - Integration Layer: MCP Tools (bridge between SDK and LangGraph)

Agents:
    - SR/BDR Agent: Sales rep conversational assistant
    - Pipeline Manager: Interactive license import orchestration
    - Customer Success: Onboarding and support assistant
"""

__version__ = "0.1.0"

__all__ = [
    "SRBDRAgent",
    "PipelineManagerAgent",
    "CustomerSuccessAgent",
]
```

File: `backend/app/agents_sdk/config.py`

```python
"""Configuration for Claude Agent SDK agents."""
import os
from typing import Optional
from pydantic import BaseModel, Field


class AgentSDKConfig(BaseModel):
    """Configuration for Claude Agent SDK."""
    
    # Claude API
    anthropic_api_key: str = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    
    # Model settings
    default_model: str = "claude-sonnet-4-0-20250514"
    temperature: float = 0.3
    max_tokens: int = 2000
    
    # Session management
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    session_ttl_seconds: int = 86400  # 24 hours
    
    # Cost optimization
    enable_caching: bool = True
    enable_compression: bool = True
    tool_result_cache_ttl: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"


# Global config instance
config = AgentSDKConfig()
```

File: `backend/app/agents_sdk/schemas/__init__.py`

```python
"""Pydantic schemas for Agent SDK."""

__all__ = []
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/agents_sdk/test_imports.py -v`  
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/agents_sdk/ backend/tests/agents_sdk/
git commit -m "feat(agents-sdk): Add module structure and configuration

- Create agents_sdk package with version 0.1.0
- Add AgentSDKConfig with Claude API and session settings
- Add basic import tests
- Support .env configuration

Part of Claude Agent SDK integration (Task 1/15)"
```

---

## Task 2: Chat Schemas (Pydantic Models)

**Files:**
- Create: `backend/app/agents_sdk/schemas/chat.py`
- Create: `backend/tests/agents_sdk/schemas/test_chat_schemas.py`

**Step 1: Write failing test**

File: `backend/tests/agents_sdk/schemas/test_chat_schemas.py`

```python
"""Test chat schemas."""
import pytest
from datetime import datetime


def test_chat_message_creation():
    """Test ChatMessage can be created."""
    from app.agents_sdk.schemas.chat import ChatMessage
    
    msg = ChatMessage(
        role="user",
        content="Test message",
        timestamp=datetime.utcnow()
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/agents_sdk/schemas/test_chat_schemas.py -v`  
Expected: FAIL - "ModuleNotFoundError: No module named 'app.agents_sdk.schemas.chat'"

**Step 3: Implement chat schemas**

File: `backend/app/agents_sdk/schemas/chat.py`

```python
"""Chat-related Pydantic schemas for Agent SDK."""
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import json


class ChatMessage(BaseModel):
    """A single message in a conversation."""
    
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request to chat with an agent."""
    
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(None, description="Existing session ID")
    stream: bool = Field(True, description="Stream response via SSE")
    metadata: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    
    session_id: str
    message: str
    agent_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class SSEChunk(BaseModel):
    """Server-Sent Event chunk for streaming."""
    
    event: str = Field("message", description="SSE event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    id: Optional[str] = None
    
    def format_sse(self) -> str:
        """Format as SSE protocol string."""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        lines.append(f"event: {self.event}")
        lines.append(f"data: {json.dumps(self.data)}")
        lines.append("")  # Empty line terminates event
        
        return "\n".join(lines)


class SessionInfo(BaseModel):
    """Session metadata."""
    
    session_id: str
    user_id: str
    agent_type: str
    created_at: datetime
    last_activity_at: datetime
    message_count: int = 0
    total_cost_usd: float = 0.0
```

Update: `backend/app/agents_sdk/schemas/__init__.py`

```python
"""Pydantic schemas for Agent SDK."""
from .chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SSEChunk,
    SessionInfo,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "SSEChunk",
    "SessionInfo",
]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/agents_sdk/schemas/test_chat_schemas.py -v`  
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/app/agents_sdk/schemas/
git commit -m "feat(agents-sdk): Add chat Pydantic schemas

- ChatMessage, ChatRequest, ChatResponse models
- SSEChunk for streaming with format_sse()
- SessionInfo metadata model
- Comprehensive validation tests

Part of Claude Agent SDK integration (Task 2/15)"
```

---

## Task 3: Session Management - Redis Store

**Files:**
- Create: `backend/app/agents_sdk/sessions/__init__.py`
- Create: `backend/app/agents_sdk/sessions/redis_store.py`
- Create: `backend/tests/agents_sdk/sessions/test_redis_store.py`

**Step 1: Write failing test**

File: `backend/tests/agents_sdk/sessions/test_redis_store.py`

```python
"""Test Redis session storage."""
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_create_and_retrieve_session():
    """Test session creation and retrieval from Redis."""
    from app.agents_sdk.sessions.redis_store import RedisSessionStore
    from app.agents_sdk.schemas.chat import ChatMessage
    
    store = await RedisSessionStore.create()
    
    # Create session
    session_id = await store.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )
    
    assert session_id.startswith("sess_")
    
    # Retrieve session
    session = await store.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "test_user"
    assert session["agent_type"] == "sr_bdr"
    assert len(session["messages"]) == 0


@pytest.mark.asyncio
async def test_add_message_to_session():
    """Test adding messages to session."""
    from app.agents_sdk.sessions.redis_store import RedisSessionStore
    from app.agents_sdk.schemas.chat import ChatMessage
    
    store = await RedisSessionStore.create()
    session_id = await store.create_session("user_123", "sr_bdr")
    
    # Add message
    message = ChatMessage(role="user", content="Hello", timestamp=datetime.utcnow())
    await store.add_message(session_id, message)
    
    # Verify
    session = await store.get_session(session_id)
    assert len(session["messages"]) == 1
    assert session["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_session_expiry():
    """Test session TTL expiration."""
    from app.agents_sdk.sessions.redis_store import RedisSessionStore
    
    store = await RedisSessionStore.create()
    session_id = await store.create_session("user_123", "sr_bdr")
    
    # Check TTL is set
    ttl = await store.get_ttl(session_id)
    assert ttl > 0
    assert ttl <= 86400  # 24 hours
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/agents_sdk/sessions/test_redis_store.py -v`  
Expected: FAIL - "ModuleNotFoundError"

**Step 3: Implement Redis store**

File: `backend/app/agents_sdk/sessions/redis_store.py`

```python
"""Redis-based session storage for hot sessions."""
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.cache.base import get_redis_client
from app.agents_sdk.schemas.chat import ChatMessage
from app.agents_sdk.config import config
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class RedisSessionStore:
    """Redis storage for active agent sessions (hot storage)."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = config.session_ttl_seconds
    
    @classmethod
    async def create(cls):
        """Factory method to create store with Redis client."""
        redis_client = await get_redis_client()
        return cls(redis_client)
    
    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"agent_session:{session_id}"
    
    async def create_session(
        self,
        user_id: str,
        agent_type: str
    ) -> str:
        """
        Create new session in Redis.
        
        Args:
            user_id: User identifier
            agent_type: Agent type (sr_bdr, pipeline_manager, cs_agent)
            
        Returns:
            session_id: Generated session ID
        """
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity_at": datetime.utcnow().isoformat(),
            "messages": [],
            "tool_results_cache": {},
            "metadata": {
                "message_count": 0,
                "tool_calls": 0,
                "total_cost_usd": 0.0
            }
        }
        
        # Store in Redis with TTL
        key = self._session_key(session_id)
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(session_data)
        )
        
        logger.info(f"Created session {session_id} for user {user_id}, agent {agent_type}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session from Redis.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data dict or None if not found
        """
        key = self._session_key(session_id)
        data = await self.redis.get(key)
        
        if data is None:
            logger.warning(f"Session {session_id} not found in Redis")
            return None
        
        return json.loads(data)
    
    async def add_message(
        self,
        session_id: str,
        message: ChatMessage
    ):
        """
        Add message to session.
        
        Args:
            session_id: Session ID
            message: ChatMessage to add
        """
        session = await self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        # Add message
        session["messages"].append(message.model_dump())
        session["last_activity_at"] = datetime.utcnow().isoformat()
        session["metadata"]["message_count"] += 1
        
        # Update Redis with extended TTL
        key = self._session_key(session_id)
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(session)
        )
        
        logger.debug(f"Added message to session {session_id}")
    
    async def cache_tool_result(
        self,
        session_id: str,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache tool result in session.
        
        Args:
            session_id: Session ID
            tool_name: Tool name
            args: Tool arguments (used as cache key)
            result: Tool result to cache
            ttl: Cache TTL (defaults to config value)
        """
        session = await self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        # Create cache key from tool name + args
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        
        session["tool_results_cache"][cache_key] = {
            "result": result,
            "cached_at": datetime.utcnow().isoformat(),
            "ttl": ttl or config.tool_result_cache_ttl
        }
        
        # Update Redis
        key = self._session_key(session_id)
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(session)
        )
        
        logger.debug(f"Cached tool result for {tool_name} in session {session_id}")
    
    async def get_cached_tool_result(
        self,
        session_id: str,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached tool result from session.
        
        Args:
            session_id: Session ID
            tool_name: Tool name
            args: Tool arguments
            
        Returns:
            Cached result or None if not found/expired
        """
        session = await self.get_session(session_id)
        if session is None:
            return None
        
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        cached = session["tool_results_cache"].get(cache_key)
        
        if cached is None:
            return None
        
        # Check if expired
        cached_at = datetime.fromisoformat(cached["cached_at"])
        ttl_seconds = cached["ttl"]
        
        if (datetime.utcnow() - cached_at).total_seconds() > ttl_seconds:
            logger.debug(f"Cached tool result expired for {tool_name}")
            return None
        
        logger.debug(f"Cache hit for {tool_name} in session {session_id}")
        return cached["result"]
    
    async def get_ttl(self, session_id: str) -> int:
        """Get remaining TTL for session in seconds."""
        key = self._session_key(session_id)
        ttl = await self.redis.ttl(key)
        return ttl
    
    async def delete_session(self, session_id: str):
        """Delete session from Redis."""
        key = self._session_key(session_id)
        await self.redis.delete(key)
        logger.info(f"Deleted session {session_id} from Redis")
```

File: `backend/app/agents_sdk/sessions/__init__.py`

```python
"""Session management for Agent SDK."""
from .redis_store import RedisSessionStore

__all__ = ["RedisSessionStore"]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/agents_sdk/sessions/test_redis_store.py -v`  
Expected: PASS (3 tests) - requires Redis running

**Step 5: Commit**

```bash
git add backend/app/agents_sdk/sessions/
git commit -m "feat(agents-sdk): Add Redis session store

- RedisSessionStore for hot session storage (24h TTL)
- Session creation, retrieval, message adding
- Tool result caching with per-tool TTL
- Auto-extend TTL on activity
- Comprehensive async tests

Part of Claude Agent SDK integration (Task 3/15)"
```

---

## Task 4: MCP Tools - Qualification Tool

**Files:**
- Create: `backend/app/agents_sdk/tools/__init__.py`
- Create: `backend/app/agents_sdk/tools/qualification_tools.py`
- Create: `backend/tests/agents_sdk/tools/test_qualification_tools.py`

**Step 1: Write failing test**

File: `backend/tests/agents_sdk/tools/test_qualification_tools.py`

```python
"""Test qualification MCP tools."""
import pytest
from unittest.mock import AsyncMock, patch, Mock


@pytest.mark.asyncio
async def test_qualify_lead_tool_success():
    """Test qualify_lead tool calls QualificationAgent successfully."""
    from app.agents_sdk.tools.qualification_tools import qualify_lead_tool
    from app.services.langgraph.agents.qualification_agent import LeadQualificationResult
    
    # Mock QualificationAgent
    mock_result = LeadQualificationResult(
        qualification_score=85.0,
        tier="hot",
        qualification_reasoning="Multi-state contractor with strong ICP fit",
        fit_assessment="Excellent company size and industry match",
        contact_quality="Decision-maker level contact",
        sales_potential="High - recent expansion signals"
    )
    
    with patch('app.agents_sdk.tools.qualification_tools.QualificationAgent') as MockAgent:
        mock_agent = MockAgent.return_value
        mock_agent.qualify = AsyncMock(return_value=(mock_result, 633, {}))
        
        # Call tool
        result = await qualify_lead_tool({
            "company_name": "Acme Corp",
            "industry": "Construction"
        })
        
        # Verify
        assert result["status"] == "success"
        assert result["data"]["score"] == 85.0
        assert result["data"]["tier"] == "hot"
        assert "latency_ms" in result


@pytest.mark.asyncio
async def test_qualify_lead_tool_fallback():
    """Test tool falls back to Claude when Cerebras fails."""
    from app.agents_sdk.tools.qualification_tools import qualify_lead_tool
    from app.core.exceptions import CerebrasAPIError
    
    with patch('app.agents_sdk.tools.qualification_tools.QualificationAgent') as MockAgent:
        # First call (Cerebras) fails
        mock_agent_cerebras = MockAgent.return_value
        mock_agent_cerebras.qualify = AsyncMock(
            side_effect=CerebrasAPIError("Cerebras unavailable")
        )
        
        # Second call (Claude) succeeds
        from app.services.langgraph.agents.qualification_agent import LeadQualificationResult
        mock_result = LeadQualificationResult(
            qualification_score=80.0,
            tier="hot",
            qualification_reasoning="Good fit",
            fit_assessment="Good",
            contact_quality="Good",
            sales_potential="Good"
        )
        mock_agent_claude = Mock()
        mock_agent_claude.qualify = AsyncMock(return_value=(mock_result, 4000, {}))
        
        # Setup mock to return different instances
        MockAgent.side_effect = [mock_agent_cerebras, mock_agent_claude]
        
        # Call tool
        result = await qualify_lead_tool({"company_name": "Test Corp"})
        
        # Verify fallback worked
        assert result["status"] == "success_fallback"
        assert result["data"]["score"] == 80.0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/agents_sdk/tools/test_qualification_tools.py -v`  
Expected: FAIL - "ModuleNotFoundError"

**Step 3: Implement qualification tool**

File: `backend/app/agents_sdk/tools/qualification_tools.py`

```python
"""MCP tools for lead qualification."""
from typing import Dict, Any
from mcp import tool

from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.core.exceptions import CerebrasAPIError
from app.core.logging import setup_logging

logger = setup_logging(__name__)


@tool("qualify_lead", "Qualify and score a lead using ICP criteria")
async def qualify_lead_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Qualify a lead using the QualificationAgent.
    
    This tool wraps the existing LangGraph QualificationAgent and calls it
    via direct Python import (no HTTP overhead).
    
    Args:
        args: Tool arguments
            - company_name (required): Company name
            - company_website (optional): Company website URL
            - company_size (optional): Company size (e.g., "50-200 employees")
            - industry (optional): Industry sector
            - contact_name (optional): Contact person's name
            - contact_title (optional): Contact person's job title
            - notes (optional): Additional context
            
    Returns:
        Dict with:
            - status: "success", "success_fallback", or "error"
            - data: Qualification result (score, tier, reasoning, etc.)
            - latency_ms: Execution time
            - provider: LLM provider used
    """
    try:
        # Try primary provider (Cerebras - ultra-fast)
        logger.info(f"Qualifying lead: {args.get('company_name')}")
        
        agent = QualificationAgent(provider="cerebras", model="llama3.1-8b")
        result, latency, metadata = await agent.qualify(
            company_name=args["company_name"],
            company_website=args.get("company_website"),
            company_size=args.get("company_size"),
            industry=args.get("industry"),
            contact_name=args.get("contact_name"),
            contact_title=args.get("contact_title"),
            notes=args.get("notes")
        )
        
        return {
            "status": "success",
            "data": {
                "score": result.qualification_score,
                "tier": result.tier,
                "reasoning": result.qualification_reasoning,
                "fit_assessment": result.fit_assessment,
                "contact_quality": result.contact_quality,
                "sales_potential": result.sales_potential,
                "recommendations": result.recommendations
            },
            "latency_ms": latency,
            "provider": "cerebras"
        }
        
    except CerebrasAPIError as e:
        # Fallback to Claude if Cerebras unavailable
        logger.warning(f"Cerebras unavailable, falling back to Claude: {e}")
        
        try:
            agent = QualificationAgent(provider="claude", model="claude-3-haiku-20240307")
            result, latency, metadata = await agent.qualify(
                company_name=args["company_name"],
                company_website=args.get("company_website"),
                company_size=args.get("company_size"),
                industry=args.get("industry"),
                contact_name=args.get("contact_name"),
                contact_title=args.get("contact_title"),
                notes=args.get("notes")
            )
            
            return {
                "status": "success_fallback",
                "data": {
                    "score": result.qualification_score,
                    "tier": result.tier,
                    "reasoning": result.qualification_reasoning,
                    "fit_assessment": result.fit_assessment,
                    "contact_quality": result.contact_quality,
                    "sales_potential": result.sales_potential,
                    "recommendations": result.recommendations
                },
                "latency_ms": latency,
                "provider": "claude"
            }
            
        except Exception as fallback_error:
            logger.error(f"Claude fallback also failed: {fallback_error}")
            raise
    
    except Exception as e:
        # Complete failure
        logger.error(f"Qualification tool failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Unable to qualify lead: {str(e)}",
            "suggestion": "Try enrichment tool to gather more data first"
        }


@tool("search_leads", "Search for leads matching criteria")
async def search_leads_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for leads in the database.
    
    Args:
        args: Search criteria
            - tier (optional): Filter by tier (hot, warm, cold)
            - min_score (optional): Minimum qualification score
            - max_score (optional): Maximum qualification score
            - industry (optional): Filter by industry
            - state (optional): Filter by state
            - limit (optional): Max results (default: 10)
            
    Returns:
        List of matching leads with basic info
    """
    # TODO: Implement in Task 8
    return {
        "status": "not_implemented",
        "message": "search_leads tool will be implemented in Task 8"
    }
```

File: `backend/app/agents_sdk/tools/__init__.py`

```python
"""MCP tools for Agent SDK."""
from .qualification_tools import qualify_lead_tool, search_leads_tool

__all__ = [
    "qualify_lead_tool",
    "search_leads_tool",
]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/agents_sdk/tools/test_qualification_tools.py -v`  
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/agents_sdk/tools/
git commit -m "feat(agents-sdk): Add qualification MCP tool

- qualify_lead_tool wraps QualificationAgent
- Direct Python import (no HTTP overhead)
- Automatic fallback: Cerebras → Claude
- search_leads_tool placeholder
- Comprehensive tests with mocking

Part of Claude Agent SDK integration (Task 4/15)"
```

---

## Task 5: Base Agent Class

**Files:**
- Create: `backend/app/agents_sdk/agents/__init__.py`
- Create: `backend/app/agents_sdk/agents/base_agent.py`
- Create: `backend/tests/agents_sdk/agents/test_base_agent.py`

**Step 1: Write failing test**

File: `backend/tests/agents_sdk/agents/test_base_agent.py`

```python
"""Test base agent functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_base_agent_initialization():
    """Test BaseAgent can be initialized."""
    from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig
    
    # Create concrete subclass for testing
    class TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "Test agent"
        
        def get_tools(self) -> list:
            return []
    
    config = AgentConfig(
        name="test_agent",
        description="Test agent for unit tests"
    )
    
    agent = TestAgent(config)
    assert agent.name == "test_agent"
    assert agent.config.description == "Test agent for unit tests"


@pytest.mark.asyncio
async def test_base_agent_session_management():
    """Test agent can create and manage sessions."""
    from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig
    
    class TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "Test"
        
        def get_tools(self) -> list:
            return []
    
    config = AgentConfig(name="test", description="Test")
    agent = TestAgent(config)
    
    # Mock session store
    with patch('app.agents_sdk.agents.base_agent.RedisSessionStore') as MockStore:
        mock_store = AsyncMock()
        mock_store.create_session = AsyncMock(return_value="sess_123")
        MockStore.create = AsyncMock(return_value=mock_store)
        
        # Initialize session store
        await agent._init_session_store()
        
        # Create session
        session_id = await agent.create_session("user_123")
        assert session_id == "sess_123"
        mock_store.create_session.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/agents_sdk/agents/test_base_agent.py -v`  
Expected: FAIL - "ModuleNotFoundError"

**Step 3: Implement base agent**

File: `backend/app/agents_sdk/agents/base_agent.py`

```python
"""Base agent class for Claude Agent SDK agents."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from dataclasses import dataclass

from mcp import create_sdk_mcp_server
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from app.agents_sdk.sessions.redis_store import RedisSessionStore
from app.agents_sdk.schemas.chat import ChatMessage, SSEChunk
from app.agents_sdk.config import config
from app.core.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model: str = config.default_model
    temperature: float = config.temperature
    max_tokens: int = config.max_tokens


class BaseAgent(ABC):
    """
    Base class for all Claude Agent SDK agents.
    
    Provides:
    - Session management (Redis)
    - Tool execution
    - Streaming responses
    - Error handling
    
    Subclasses must implement:
    - get_system_prompt(): Return agent-specific system prompt
    - get_tools(): Return list of MCP tools
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize base agent."""
        self.config = config
        self.name = config.name
        self.session_store: Optional[RedisSessionStore] = None
        
        logger.info(f"Initialized {self.name} agent")
    
    async def _init_session_store(self):
        """Initialize Redis session store (lazy)."""
        if self.session_store is None:
            self.session_store = await RedisSessionStore.create()
            logger.debug(f"{self.name}: Session store initialized")
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get agent-specific system prompt.
        
        Returns:
            System prompt string
        """
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Any]:
        """
        Get agent-specific MCP tools.
        
        Returns:
            List of tool functions decorated with @tool
        """
        pass
    
    async def create_session(self, user_id: str) -> str:
        """
        Create new conversation session.
        
        Args:
            user_id: User identifier
            
        Returns:
            session_id: Generated session ID
        """
        await self._init_session_store()
        
        session_id = await self.session_store.create_session(
            user_id=user_id,
            agent_type=self.name
        )
        
        logger.info(f"{self.name}: Created session {session_id} for user {user_id}")
        return session_id
    
    async def get_or_create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get existing session or create new one.
        
        Args:
            user_id: User identifier
            session_id: Optional existing session ID
            
        Returns:
            session_id: Session ID (existing or new)
        """
        await self._init_session_store()
        
        if session_id:
            # Check if exists
            session = await self.session_store.get_session(session_id)
            if session:
                logger.debug(f"{self.name}: Using existing session {session_id}")
                return session_id
        
        # Create new session
        return await self.create_session(user_id)
    
    async def chat(
        self,
        session_id: str,
        message: str
    ) -> AsyncIterator[str]:
        """
        Chat with agent (streaming).
        
        Args:
            session_id: Session ID
            message: User message
            
        Yields:
            SSE-formatted chunks
        """
        await self._init_session_store()
        
        # Load session
        session = await self.session_store.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        # Add user message to session
        user_msg = ChatMessage(role="user", content=message)
        await self.session_store.add_message(session_id, user_msg)
        
        # Build Claude Agent SDK options
        system_prompt = self.get_system_prompt()
        tools = self.get_tools()
        
        # Create MCP server with tools
        mcp_server = create_sdk_mcp_server(
            name=f"{self.name}_tools",
            tools=tools
        )
        
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={self.name: mcp_server},
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        # Stream response
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(message)
                
                async for chunk in client.receive_messages():
                    # Format as SSE
                    sse_chunk = SSEChunk(
                        event="message",
                        data={"content": str(chunk)}
                    )
                    yield sse_chunk.format_sse()
                
                # Add assistant response to session
                # Note: In real implementation, accumulate chunks
                # For now, placeholder
                assistant_msg = ChatMessage(role="assistant", content="[streamed response]")
                await self.session_store.add_message(session_id, assistant_msg)
                
        except Exception as e:
            logger.error(f"{self.name}: Chat failed: {e}", exc_info=True)
            
            # Send error chunk
            error_chunk = SSEChunk(
                event="error",
                data={
                    "message": f"Agent error: {str(e)}",
                    "suggestion": "Try rephrasing your question"
                }
            )
            yield error_chunk.format_sse()
```

File: `backend/app/agents_sdk/agents/__init__.py`

```python
"""Agent SDK agents."""
from .base_agent import BaseAgent, AgentConfig

__all__ = ["BaseAgent", "AgentConfig"]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/agents_sdk/agents/test_base_agent.py -v`  
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/app/agents_sdk/agents/
git commit -m "feat(agents-sdk): Add BaseAgent abstract class

- Abstract base for all SDK agents
- Session management integration (Redis)
- Streaming chat with Claude Agent SDK
- Tool execution via MCP servers
- Error handling and SSE formatting
- Comprehensive tests

Part of Claude Agent SDK integration (Task 5/15)"
```

---

**Due to length constraints, I'll provide a summary of remaining tasks:**

## Remaining Tasks Summary

**Task 6: SR/BDR Agent Implementation** - Concrete agent with system prompt and qualification/enrichment tools

**Task 7: Pipeline Manager Agent** - Interactive orchestrator for license import pipeline

**Task 8: Customer Success Agent** - Onboarding and support assistant

**Task 9: FastAPI Endpoints** - `/api/chat/*` endpoints with streaming

**Task 10: PostgreSQL Session Archive** - Cold storage migration from Redis

**Task 11: CLI Testing Tool** - Interactive CLI for development testing

**Task 12: Integration Tests** - End-to-end conversation flows

**Task 13: Error Handling** - Circuit breakers, graceful degradation

**Task 14: Cost Optimization** - Caching, compression, interruption

**Task 15: Documentation** - README, API docs, deployment guide

---

## Testing & Verification

After implementing all tasks:

```bash
# Run all tests
cd backend && pytest tests/agents_sdk/ -v

# Start services
docker-compose up -d

# Test CLI
python -m app.agents_sdk.cli

# Test API
curl -X POST http://localhost:8001/api/chat/sr-bdr \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "What are my top leads?"}'
```

---

**Plan Status**: Tasks 1-5 detailed, Tasks 6-15 summarized  
**Next**: Execute using superpowers:executing-plans or subagent-driven-development
