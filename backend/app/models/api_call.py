"""
API Call tracking model for cost management and performance monitoring
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from .database import Base


class CerebrasAPICall(Base):
    """
    Tracks all Cerebras API calls for cost management and performance monitoring
    """
    __tablename__ = "cerebras_api_calls"

    id = Column(Integer, primary_key=True, index=True)

    # Request Details
    endpoint = Column(String(200), nullable=False, index=True)  # e.g., '/chat/completions'
    model = Column(String(100), nullable=False, index=True)  # e.g., 'llama3.1-8b'
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)

    # Performance Metrics
    latency_ms = Column(Integer, nullable=False)  # Response time in milliseconds
    cache_hit = Column(Boolean, default=False, index=True)  # Whether cache was used

    # Cost Tracking (calculated at time of call)
    cost_usd = Column(Float, nullable=False)  # Cost in USD
    input_cost_usd = Column(Float)  # Separate tracking for input cost
    output_cost_usd = Column(Float)  # Separate tracking for output cost

    # Context
    operation_type = Column(String(100), index=True)  # e.g., 'lead_qualification', 'research'
    success = Column(Boolean, default=True, nullable=False, index=True)
    error_message = Column(Text)  # If call failed

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<CerebrasAPICall(id={self.id}, model='{self.model}', cost=${self.cost_usd:.4f}, latency={self.latency_ms}ms)>"
