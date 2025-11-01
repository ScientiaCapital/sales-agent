"""Redis-based session storage for hot sessions."""
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, UTC

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
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity_at": datetime.now(UTC).isoformat(),
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

        # Add message (serialize to dict with string timestamps)
        session["messages"].append(message.model_dump(mode='json'))
        session["last_activity_at"] = datetime.now(UTC).isoformat()
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
            "cached_at": datetime.now(UTC).isoformat(),
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

        if (datetime.now(UTC) - cached_at).total_seconds() > ttl_seconds:
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
