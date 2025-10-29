"""
LangGraph Database Models

SQLAlchemy models for tracking LangGraph agent executions, checkpoints, and tool calls.
Supports both LCEL chains and StateGraph workflows with Redis checkpointing.
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from app.models.database import Base


class LangGraphExecution(Base):
    """
    Track LangGraph agent executions (both chains and graphs).
    
    Supports:
    - LCEL chains (QualificationAgent, EnrichmentAgent)
    - StateGraphs (GrowthAgent, MarketingAgent, BDRAgent, ConversationAgent)
    """
    __tablename__ = "langgraph_executions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Execution metadata
    execution_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_type = Column(String(50), nullable=False, index=True)  # qualification, enrichment, growth, etc.
    thread_id = Column(String(36), nullable=False, index=True)  # LangGraph thread for state persistence
    
    # Execution status and timing
    status = Column(String(20), nullable=False, index=True)  # pending, running, success, failed, cancelled
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Total execution time
    
    # Performance metrics
    latency_ms = Column(Integer, nullable=True)  # First token latency for streaming
    cost_usd = Column(Float, nullable=True)  # Total cost for this execution
    tokens_used = Column(Integer, nullable=True)  # Total tokens consumed
    
    # Input/Output data
    input_data = Column(JSON, nullable=True)  # Agent input parameters
    output_data = Column(JSON, nullable=True)  # Agent output/result
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # LangGraph specific
    graph_type = Column(String(20), nullable=False)  # chain, graph
    nodes_executed = Column(JSON, nullable=True)  # List of nodes executed (for graphs)
    checkpoint_count = Column(Integer, default=0)  # Number of checkpoints created
    
    # Relationships
    tool_calls = relationship("LangGraphToolCall", back_populates="execution", cascade="all, delete-orphan")
    checkpoints = relationship("LangGraphCheckpoint", back_populates="execution", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LangGraphExecution(id={self.id}, agent_type='{self.agent_type}', status='{self.status}')>"


class LangGraphCheckpoint(Base):
    """
    Store LangGraph state checkpoints for resumable workflows.
    
    Used by StateGraph agents to persist conversation state and enable pause/resume.
    """
    __tablename__ = "langgraph_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    
    # Checkpoint metadata
    checkpoint_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(Integer, ForeignKey("langgraph_executions.id"), nullable=False)
    thread_id = Column(String(36), nullable=False, index=True)  # LangGraph thread
    
    # Checkpoint data
    checkpoint_data = Column(JSON, nullable=False)  # Serialized LangGraph state
    node_name = Column(String(100), nullable=True)  # Current node in graph
    step_count = Column(Integer, default=0)  # Number of steps executed
    
    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # TTL for cleanup
    
    # Relationships
    execution = relationship("LangGraphExecution", back_populates="checkpoints")

    def __repr__(self):
        return f"<LangGraphCheckpoint(id={self.id}, thread_id='{self.thread_id}', node='{self.node_name}')>"


class LangGraphToolCall(Base):
    """
    Track individual tool invocations within LangGraph agents.
    
    Provides detailed observability into tool usage patterns and performance.
    """
    __tablename__ = "langgraph_tool_calls"

    id = Column(Integer, primary_key=True, index=True)
    
    # Tool call metadata
    tool_call_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(Integer, ForeignKey("langgraph_executions.id"), nullable=False)
    
    # Tool information
    tool_name = Column(String(100), nullable=False, index=True)  # search_crm, enrich_with_apollo, etc.
    tool_type = Column(String(50), nullable=False)  # crm, enrichment, research, voice, etc.
    
    # Input/Output
    tool_input = Column(JSON, nullable=True)  # Tool input parameters
    tool_output = Column(JSON, nullable=True)  # Tool output/result
    error_message = Column(Text, nullable=True)  # Tool error if failed
    
    # Performance metrics
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)  # Cost for this specific tool call
    
    # Success tracking
    success = Column(Boolean, default=True)
    retry_count = Column(Integer, default=0)  # Number of retries attempted
    
    # Relationships
    execution = relationship("LangGraphExecution", back_populates="tool_calls")

    def __repr__(self):
        return f"<LangGraphToolCall(id={self.id}, tool='{self.tool_name}', success={self.success})>"


# Indexes for performance optimization
Index('idx_langgraph_execution_agent_status', LangGraphExecution.agent_type, LangGraphExecution.status)
Index('idx_langgraph_execution_thread', LangGraphExecution.thread_id)
Index('idx_langgraph_checkpoint_thread', LangGraphCheckpoint.thread_id)
Index('idx_langgraph_tool_execution', LangGraphToolCall.execution_id)
Index('idx_langgraph_tool_name_type', LangGraphToolCall.tool_name, LangGraphToolCall.tool_type)
