"""PostgreSQL-based session archive for cold storage."""
from typing import Optional, Dict, Any, List
from datetime import datetime, UTC
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentConversation
from app.models.database import get_db
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class PostgreSQLSessionStore:
    """PostgreSQL storage for archived agent sessions (cold storage)."""

    async def archive_session(
        self,
        session_data: Dict[str, Any],
        db: AsyncSession
    ) -> int:
        """
        Archive session from Redis to PostgreSQL.

        Args:
            session_data: Session data dict from Redis
            db: Database session

        Returns:
            conversation_id: ID of archived conversation
        """
        # Extract tool results from tool_results_cache
        tool_results = []
        if "tool_results_cache" in session_data:
            for cache_key, cached_data in session_data["tool_results_cache"].items():
                tool_results.append({
                    "cache_key": cache_key,
                    "result": cached_data["result"],
                    "cached_at": cached_data["cached_at"]
                })

        # Calculate metrics
        message_count = session_data.get("metadata", {}).get("message_count", 0)
        tool_call_count = len(tool_results)
        total_cost = session_data.get("metadata", {}).get("total_cost_usd", 0.0)

        # Calculate average response time from messages
        avg_response_time = None
        if "messages" in session_data and session_data["messages"]:
            response_times = []
            for msg in session_data["messages"]:
                if msg.get("role") == "assistant" and "response_time_ms" in msg:
                    response_times.append(msg["response_time_ms"])
            if response_times:
                avg_response_time = sum(response_times) // len(response_times)

        # Parse timestamps
        started_at = datetime.fromisoformat(session_data["created_at"])
        ended_at = datetime.fromisoformat(session_data["last_activity_at"])

        # Create archived conversation
        conversation = AgentConversation(
            session_id=session_data["session_id"],
            user_id=session_data["user_id"],
            agent_type=session_data["agent_type"],
            messages=session_data["messages"],
            tool_results=tool_results if tool_results else None,
            message_count=message_count,
            tool_call_count=tool_call_count,
            total_cost_usd=total_cost,
            avg_response_time_ms=avg_response_time,
            started_at=started_at,
            ended_at=ended_at,
            extra_metadata=session_data.get("metadata", {})
        )

        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        logger.info(
            f"Archived session {conversation.session_id} to PostgreSQL "
            f"(id={conversation.id}, messages={message_count}, tools={tool_call_count})"
        )

        return conversation.id

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
            Session data dict or None if not found
        """
        stmt = select(AgentConversation).where(
            AgentConversation.session_id == session_id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation is None:
            logger.warning(f"Archived session {session_id} not found")
            return None

        # Convert to dict format
        return {
            "id": conversation.id,
            "session_id": conversation.session_id,
            "user_id": conversation.user_id,
            "agent_type": conversation.agent_type,
            "messages": conversation.messages,
            "tool_results": conversation.tool_results,
            "message_count": conversation.message_count,
            "tool_call_count": conversation.tool_call_count,
            "total_cost_usd": float(conversation.total_cost_usd) if conversation.total_cost_usd else None,
            "avg_response_time_ms": conversation.avg_response_time_ms,
            "started_at": conversation.started_at.isoformat(),
            "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
            "archived_at": conversation.archived_at.isoformat(),
            "extra_metadata": conversation.extra_metadata
        }

    async def get_user_conversations(
        self,
        user_id: str,
        agent_type: Optional[str] = None,
        limit: int = 10,
        db: AsyncSession = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's conversation history.

        Args:
            user_id: User ID
            agent_type: Optional agent type filter
            limit: Maximum conversations to return
            db: Database session (required)

        Returns:
            List of conversation summaries

        Raises:
            ValueError: If db is None
        """
        if db is None:
            raise ValueError("Database session (db) is required for get_user_conversations")

        conditions = [AgentConversation.user_id == user_id]
        if agent_type:
            conditions.append(AgentConversation.agent_type == agent_type)

        stmt = (
            select(AgentConversation)
            .where(and_(*conditions))
            .order_by(AgentConversation.started_at.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        conversations = result.scalars().all()

        return [
            {
                "session_id": conv.session_id,
                "agent_type": conv.agent_type,
                "message_count": conv.message_count,
                "tool_call_count": conv.tool_call_count,
                "total_cost_usd": float(conv.total_cost_usd) if conv.total_cost_usd else None,
                "started_at": conv.started_at.isoformat(),
                "ended_at": conv.ended_at.isoformat() if conv.ended_at else None
            }
            for conv in conversations
        ]

    async def get_analytics(
        self,
        agent_type: Optional[str] = None,
        days: int = 7,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Get conversation analytics.

        Args:
            agent_type: Optional agent type filter
            days: Number of days to analyze
            db: Database session (required)

        Returns:
            Analytics dict with metrics

        Raises:
            ValueError: If db is None
        """
        if db is None:
            raise ValueError("Database session (db) is required for get_analytics")

        from sqlalchemy import func

        # Build base query
        conditions = [
            AgentConversation.started_at >= func.now() - func.cast(f'{days} days', func.Interval)
        ]
        if agent_type:
            conditions.append(AgentConversation.agent_type == agent_type)

        stmt = select(
            func.count(AgentConversation.id).label('total_conversations'),
            func.avg(AgentConversation.message_count).label('avg_messages'),
            func.avg(AgentConversation.tool_call_count).label('avg_tools'),
            func.sum(AgentConversation.total_cost_usd).label('total_cost'),
            func.avg(AgentConversation.avg_response_time_ms).label('avg_response_time')
        ).where(and_(*conditions))

        result = await db.execute(stmt)
        row = result.one()

        return {
            "total_conversations": row.total_conversations or 0,
            "avg_messages_per_conversation": float(row.avg_messages) if row.avg_messages else 0.0,
            "avg_tools_per_conversation": float(row.avg_tools) if row.avg_tools else 0.0,
            "total_cost_usd": float(row.total_cost) if row.total_cost else 0.0,
            "avg_response_time_ms": int(row.avg_response_time) if row.avg_response_time else 0,
            "agent_type": agent_type,
            "days": days
        }
