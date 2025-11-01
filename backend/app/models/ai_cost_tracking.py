"""AI Cost Tracking model for monitoring LLM usage."""
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, Index, DECIMAL, ForeignKey
from sqlalchemy.sql import func
from app.models.database import Base


class AICostTracking(Base):
    """
    Track all AI/LLM API calls for cost analysis and optimization.

    Captures:
    - Request context (agent_type, lead_id, session_id)
    - Prompt and response details
    - Provider and model used
    - Cost and performance metrics
    - Quality feedback
    """
    __tablename__ = "ai_cost_tracking"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Request identification
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Context tagging
    agent_type = Column(String(50), nullable=False, index=True)
    agent_mode = Column(String(20))  # "passthrough" or "smart_router"
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), index=True)
    session_id = Column(String(255), index=True)
    user_id = Column(String(255))

    # Request details
    prompt_text = Column(Text)
    prompt_tokens = Column(Integer, nullable=False)
    prompt_complexity = Column(String(20))  # "simple", "medium", "complex"

    # Response details
    completion_text = Column(Text)
    completion_tokens = Column(Integer, nullable=False)

    # Provider & cost
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    cost_usd = Column(DECIMAL(10, 8), nullable=False)

    # Performance
    latency_ms = Column(Integer)
    cache_hit = Column(Boolean, default=False)

    # Quality (for learning)
    quality_score = Column(Float)
    feedback_count = Column(Integer, default=0)

    # Indexes
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_cache_hit', 'cache_hit'),
    )

    def __repr__(self):
        return (
            f"<AICostTracking(id={self.id}, agent={self.agent_type}, "
            f"provider={self.provider}, cost=${self.cost_usd})>"
        )
