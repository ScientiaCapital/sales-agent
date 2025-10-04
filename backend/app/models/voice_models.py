"""
Database models for voice interaction tracking

Stores voice sessions, Cartesia API calls, and performance metrics.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
import enum

from .database import Base


class VoiceSessionStatus(str, enum.Enum):
    """Voice session status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"
    ABANDONED = "abandoned"


class VoiceSessionLog(Base):
    """
    Voice interaction session tracking.

    Stores session metadata, performance metrics, and conversation history.
    """
    __tablename__ = "voice_session_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)

    # Session configuration
    voice_id = Column(String, nullable=False)
    voice_name = Column(String)
    language = Column(String, default="en")
    initial_emotion = Column(String)

    # Session metadata
    status = Column(SQLEnum(VoiceSessionStatus), default=VoiceSessionStatus.ACTIVE)
    total_turns = Column(Integer, default=0)
    total_duration_ms = Column(Integer)

    # Performance metrics
    average_latency_ms = Column(Float)
    min_latency_ms = Column(Integer)
    max_latency_ms = Column(Integer)
    p50_latency_ms = Column(Integer)
    p95_latency_ms = Column(Integer)
    p99_latency_ms = Column(Integer)

    # Latency target compliance
    target_compliance_rate = Column(Float)  # % of turns under 2000ms

    # Cost tracking
    total_tts_cost_usd = Column(Float, default=0.0)
    total_stt_cost_usd = Column(Float, default=0.0)
    total_inference_cost_usd = Column(Float, default=0.0)

    # Conversation summary
    conversation_summary = Column(Text)
    final_outcome = Column(String)

    # Session context (JSON)
    context_data = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    # Relationships
    lead = relationship("Lead", back_populates="voice_sessions")
    api_calls = relationship("CartesiaAPICall", back_populates="voice_session", cascade="all, delete-orphan")
    voice_turns = relationship("VoiceTurn", back_populates="voice_session", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index("ix_voice_session_logs_lead_id", "lead_id"),
        Index("ix_voice_session_logs_status", "status"),
        Index("ix_voice_session_logs_created_at", "created_at"),
    )


class CartesiaAPICall(Base):
    """
    Track individual Cartesia API calls for cost and performance analysis.
    """
    __tablename__ = "cartesia_api_calls"

    id = Column(Integer, primary_key=True)
    voice_session_id = Column(String, ForeignKey("voice_session_logs.id", ondelete="CASCADE"))
    turn_id = Column(String, ForeignKey("voice_turns.id", ondelete="CASCADE"), nullable=True)

    # API details
    operation = Column(String)  # tts, stt, clone, mix
    model = Column(String)  # sonic-2, etc.

    # Performance
    latency_ms = Column(Integer)
    audio_duration_ms = Column(Integer, nullable=True)

    # Usage
    characters_processed = Column(Integer, nullable=True)  # For TTS
    audio_seconds_processed = Column(Float, nullable=True)  # For STT

    # Cost
    cost_usd = Column(Float)

    # Error tracking
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    voice_session = relationship("VoiceSessionLog", back_populates="api_calls")
    voice_turn = relationship("VoiceTurn", back_populates="cartesia_calls")

    # Indexes
    __table_args__ = (
        Index("ix_cartesia_api_calls_voice_session_id", "voice_session_id"),
        Index("ix_cartesia_api_calls_operation", "operation"),
        Index("ix_cartesia_api_calls_created_at", "created_at"),
    )


class VoiceTurn(Base):
    """
    Individual conversation turn in a voice session.

    Tracks user input, AI response, and per-turn metrics.
    """
    __tablename__ = "voice_turns"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    voice_session_id = Column(String, ForeignKey("voice_session_logs.id", ondelete="CASCADE"))

    # Turn sequence
    turn_number = Column(Integer)

    # User input
    user_transcript = Column(Text)
    user_audio_duration_ms = Column(Integer)
    stt_confidence = Column(Float)

    # AI response
    ai_response_text = Column(Text)
    ai_audio_duration_ms = Column(Integer)

    # Emotion/tone used
    response_emotion = Column(String)
    response_speed = Column(String)

    # Performance breakdown
    stt_latency_ms = Column(Integer)
    inference_latency_ms = Column(Integer)
    tts_latency_ms = Column(Integer)
    total_latency_ms = Column(Integer)

    # Quality metrics
    met_latency_target = Column(Boolean)  # Under 2000ms

    # Context
    turn_context = Column(JSON)  # Any turn-specific context

    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    voice_session = relationship("VoiceSessionLog", back_populates="voice_turns")
    cartesia_calls = relationship("CartesiaAPICall", back_populates="voice_turn")

    # Indexes
    __table_args__ = (
        Index("ix_voice_turns_voice_session_id", "voice_session_id"),
        Index("ix_voice_turns_total_latency_ms", "total_latency_ms"),
        Index("ix_voice_turns_started_at", "started_at"),
    )


class VoiceConfiguration(Base):
    """
    Store voice configurations and presets.
    """
    __tablename__ = "voice_configurations"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)

    # Voice settings
    voice_id = Column(String, nullable=False)
    voice_name = Column(String)
    language = Column(String, default="en")
    default_emotion = Column(String)
    default_speed = Column(String)

    # Audio settings
    sample_rate = Column(Integer, default=44100)
    encoding = Column(String, default="pcm_f32le")
    container = Column(String, default="raw")

    # Usage stats
    times_used = Column(Integer, default=0)
    average_satisfaction = Column(Float)

    # Active flag
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_voice_configurations_name", "name"),
        Index("ix_voice_configurations_is_active", "is_active"),
    )