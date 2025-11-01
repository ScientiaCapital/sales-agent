"""Agent conversation models for Claude Agent SDK."""
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, Index, JSON
from sqlalchemy.sql import func

from app.models.database import Base


class AgentConversation(Base):
    """
    Archived agent conversations for analytics and compliance.

    Conversations are archived from Redis after session TTL expires (24h).
    Provides long-term storage for conversation history, tool usage, and cost tracking.
    """
    __tablename__ = "agent_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False, index=True)  # 'sr_bdr', 'pipeline_manager', 'cs_agent'

    # Conversation data (JSONB for analytics queries)
    messages = Column(JSON, nullable=False)  # Full conversation history
    tool_results = Column(JSON)  # All tool calls and results

    # Metrics
    message_count = Column(Integer, default=0)
    tool_call_count = Column(Integer, default=0)
    total_cost_usd = Column(DECIMAL(10, 6))
    avg_response_time_ms = Column(Integer)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True), server_default=func.now())

    # Extra metadata (user feedback, tags, etc.)
    extra_metadata = Column(JSON)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_user_agent', 'user_id', 'agent_type'),
        Index('idx_started_at', 'started_at'),
        Index('idx_archived_at', 'archived_at'),
    )

    def __repr__(self):
        return (
            f"<AgentConversation(id={self.id}, "
            f"session_id={self.session_id}, "
            f"agent_type={self.agent_type}, "
            f"message_count={self.message_count})>"
        )
