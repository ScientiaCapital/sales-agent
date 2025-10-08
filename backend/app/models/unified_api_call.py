"""
Unified API Call tracking model for multi-provider usage monitoring

Tracks API calls across all LLM providers (Cerebras, OpenRouter, Ollama, Anthropic)
with comprehensive cost, performance, and operational metrics.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum as SQLEnum, Index
from sqlalchemy.sql import func
from enum import Enum
from .database import Base


class ProviderType(str, Enum):
    """Supported LLM providers"""
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"


class OperationType(str, Enum):
    """Common operation types for categorization"""
    QUALIFICATION = "qualification"
    RESEARCH = "research"
    ENRICHMENT = "enrichment"
    OUTREACH = "outreach"
    CONVERSATION = "conversation"
    SYNTHESIS = "synthesis"
    ANALYSIS = "analysis"
    OTHER = "other"


class APICallLog(Base):
    """
    Unified API call tracking for all LLM providers.

    Replaces provider-specific tracking models with a single unified schema
    supporting cost aggregations, performance analytics, and usage monitoring.
    """
    __tablename__ = "api_call_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Provider & Model Info
    provider = Column(SQLEnum(ProviderType), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)  # e.g., 'llama3.1-8b', 'claude-3-sonnet'
    endpoint = Column(String(200), nullable=False)  # e.g., '/chat/completions', '/v1/messages'

    # Token Usage
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cost Tracking (in USD)
    cost_usd = Column(Float, nullable=False, default=0.0)
    input_cost_usd = Column(Float, nullable=True)  # Separate input cost if available
    output_cost_usd = Column(Float, nullable=True)  # Separate output cost if available

    # Performance Metrics
    latency_ms = Column(Integer, nullable=False)  # Response time in milliseconds
    cache_hit = Column(Boolean, default=False, index=True)  # Whether cached response used

    # Operational Context
    user_id = Column(String(100), nullable=True, index=True)  # User or system identifier
    operation_type = Column(SQLEnum(OperationType), nullable=False, index=True)
    success = Column(Boolean, default=True, nullable=False, index=True)
    error_message = Column(Text, nullable=True)  # Error details if call failed

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Composite indexes for common query patterns
    __table_args__ = (
        # Time-series aggregations by provider
        Index('idx_provider_created', 'provider', 'created_at'),
        # Cost analysis by operation
        Index('idx_operation_created', 'operation_type', 'created_at'),
        # Performance monitoring by model
        Index('idx_model_created', 'model', 'created_at'),
        # User-specific queries
        Index('idx_user_created', 'user_id', 'created_at'),
        # Success rate tracking
        Index('idx_success_created', 'success', 'created_at'),
    )

    def __repr__(self):
        return (
            f"<APICallLog(id={self.id}, provider={self.provider.value}, "
            f"model='{self.model}', cost=${self.cost_usd:.6f}, latency={self.latency_ms}ms)>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "provider": self.provider.value,
            "model": self.model,
            "endpoint": self.endpoint,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "user_id": self.user_id,
            "operation_type": self.operation_type.value,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
