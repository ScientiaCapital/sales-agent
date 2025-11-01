"""Session manager coordinating Redis and PostgreSQL stores."""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents_sdk.sessions.redis_store import RedisSessionStore
from app.agents_sdk.sessions.postgres_store import PostgreSQLSessionStore
from app.agents_sdk.schemas.chat import ChatMessage
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class SessionManager:
    """
    Hybrid session manager using Redis for hot storage and PostgreSQL for archive.

    Hot Sessions (Redis):
    - Active conversations (<24h)
    - Fast access for agent interactions
    - Automatic TTL-based eviction

    Cold Storage (PostgreSQL):
    - Archived conversations (>24h or manually archived)
    - Long-term analytics and compliance
    - Queryable conversation history
    """

    def __init__(self, redis_store: RedisSessionStore, postgres_store: PostgreSQLSessionStore):
        self.redis = redis_store
        self.postgres = postgres_store

    @classmethod
    async def create(cls):
        """Factory method to create manager with stores."""
        redis_store = await RedisSessionStore.create()
        postgres_store = PostgreSQLSessionStore()
        return cls(redis_store, postgres_store)

    async def get_or_create_session(
        self,
        user_id: str,
        agent_type: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get existing session or create new one.

        Args:
            user_id: User identifier
            agent_type: Agent type (sr_bdr, pipeline_manager, cs_agent)
            session_id: Optional existing session ID

        Returns:
            session_id: Session ID (existing or newly created)
        """
        # If session_id provided, try to load from Redis
        if session_id:
            session = await self.redis.get_session(session_id)
            if session:
                logger.debug(f"Found existing session {session_id}")
                return session_id

            # Not in Redis - might be archived
            logger.warning(f"Session {session_id} not found in Redis (may be archived)")

        # Create new session in Redis
        new_session_id = await self.redis.create_session(user_id, agent_type)
        logger.info(f"Created new session {new_session_id} for user {user_id}")
        return new_session_id

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session from Redis.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        return await self.redis.get_session(session_id)

    async def add_message(
        self,
        session_id: str,
        message: ChatMessage
    ):
        """
        Add message to session in Redis.

        Args:
            session_id: Session ID
            message: ChatMessage to add
        """
        await self.redis.add_message(session_id, message)

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
            args: Tool arguments
            result: Tool result
            ttl: Optional TTL override
        """
        await self.redis.cache_tool_result(session_id, tool_name, args, result, ttl)

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
            Cached result or None
        """
        return await self.redis.get_cached_tool_result(session_id, tool_name, args)

    async def archive_session(
        self,
        session_id: str,
        db: AsyncSession
    ) -> int:
        """
        Archive session from Redis to PostgreSQL.

        Args:
            session_id: Session ID to archive
            db: Database session

        Returns:
            conversation_id: ID of archived conversation

        Raises:
            ValueError: If session not found in Redis
        """
        # Load from Redis
        session_data = await self.redis.get_session(session_id)
        if session_data is None:
            raise ValueError(f"Session {session_id} not found in Redis")

        # Archive to PostgreSQL
        conversation_id = await self.postgres.archive_session(session_data, db)

        # Delete from Redis (keep it lean)
        await self.redis.delete_session(session_id)

        logger.info(
            f"Archived session {session_id} to PostgreSQL "
            f"(conversation_id={conversation_id})"
        )

        return conversation_id

    async def get_archived_session(
        self,
        session_id: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve archived session from PostgreSQL.

        Args:
            session_id: Session ID
            db: Database session

        Returns:
            Archived session data or None
        """
        return await self.postgres.get_archived_session(session_id, db)

    async def get_session_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for session in Redis.

        Args:
            session_id: Session ID

        Returns:
            TTL in seconds (-1 if no expiry, -2 if not found)
        """
        return await self.redis.get_ttl(session_id)
