"""
Database models for real-time conversation intelligence

Stores conversation sessions, turns, sentiment analysis, suggestions, and battle cards.
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


class ConversationStatus(str, enum.Enum):
    """Conversation session status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ERROR = "error"
    ABANDONED = "abandoned"


class SpeakerRole(str, enum.Enum):
    """Speaker role in conversation."""
    AGENT = "agent"
    PROSPECT = "prospect"
    SYSTEM = "system"


class SentimentType(str, enum.Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class BattleCardType(str, enum.Enum):
    """Battle card category."""
    PRICING = "pricing"
    COMPETITOR = "competitor"
    FEATURE = "feature"
    OBJECTION = "objection"
    CASE_STUDY = "case_study"
    TECHNICAL = "technical"
    GENERAL = "general"


class Conversation(Base):
    """
    Real-time conversation session tracking.

    Stores conversation metadata, performance metrics, and intelligence insights.
    """
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)

    # Session metadata
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE)
    title = Column(String, nullable=True)  # Auto-generated title

    # Timing
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Audio metadata
    total_audio_seconds = Column(Float, default=0.0)
    audio_quality_score = Column(Float, nullable=True)  # 0.0 - 1.0

    # Conversation metrics
    total_turns = Column(Integer, default=0)
    agent_turns = Column(Integer, default=0)
    prospect_turns = Column(Integer, default=0)

    # Sentiment analysis
    overall_sentiment = Column(SQLEnum(SentimentType), nullable=True)
    average_sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_trend = Column(String, nullable=True)  # improving, declining, stable

    # Intelligence insights
    detected_topics = Column(JSON, nullable=True)  # List of topics discussed
    key_objections = Column(JSON, nullable=True)  # List of objections raised
    engagement_score = Column(Float, nullable=True)  # 0.0 - 1.0

    # Suggestions metrics
    total_suggestions_shown = Column(Integer, default=0)
    total_suggestions_used = Column(Integer, default=0)
    suggestion_usage_rate = Column(Float, nullable=True)

    # Battle cards metrics
    total_battle_cards_shown = Column(Integer, default=0)
    total_battle_cards_used = Column(Integer, default=0)
    battle_card_usage_rate = Column(Float, nullable=True)

    # Performance metrics
    average_transcription_latency_ms = Column(Integer, nullable=True)
    average_analysis_latency_ms = Column(Integer, nullable=True)
    average_total_latency_ms = Column(Integer, nullable=True)

    # Outcome
    final_outcome = Column(String, nullable=True)  # scheduled_demo, sent_proposal, objection_unresolved, etc.
    next_action = Column(Text, nullable=True)  # Recommended next steps

    # Summary
    ai_summary = Column(Text, nullable=True)  # AI-generated conversation summary
    agent_notes = Column(Text, nullable=True)  # Manual notes from agent

    # Context
    context_data = Column(JSON, nullable=True)  # Additional context

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    lead = relationship("Lead", back_populates="conversations")
    turns = relationship("ConversationTurn", back_populates="conversation", cascade="all, delete-orphan")
    battle_cards = relationship("ConversationBattleCard", back_populates="conversation", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_conversations_lead_id", "lead_id"),
        Index("ix_conversations_status", "status"),
        Index("ix_conversations_started_at", "started_at"),
        Index("ix_conversations_overall_sentiment", "overall_sentiment"),
    )


class ConversationTurn(Base):
    """
    Individual turn in a conversation with transcription, sentiment, and suggestions.
    """
    __tablename__ = "conversation_turns"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"))

    # Turn metadata
    turn_number = Column(Integer)
    speaker = Column(SQLEnum(SpeakerRole))

    # Transcription
    text = Column(Text, nullable=False)
    transcription_confidence = Column(Float, nullable=True)  # 0.0 - 1.0

    # Audio metadata
    audio_duration_ms = Column(Integer, nullable=True)
    audio_url = Column(String, nullable=True)  # S3/storage URL if stored

    # Sentiment analysis
    sentiment = Column(SQLEnum(SentimentType), nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    detected_emotions = Column(JSON, nullable=True)  # List of detected emotions

    # Content analysis
    detected_topics = Column(JSON, nullable=True)  # Topics in this turn
    detected_keywords = Column(JSON, nullable=True)  # Important keywords
    is_objection = Column(Boolean, default=False)
    is_question = Column(Boolean, default=False)
    is_commitment = Column(Boolean, default=False)  # Buying signal

    # Suggestions generated
    suggestions = Column(JSON, nullable=True)  # List of suggestions for agent
    suggestion_shown = Column(Boolean, default=False)
    suggestion_used = Column(Boolean, default=False)
    suggestion_used_index = Column(Integer, nullable=True)  # Which suggestion was used

    # Performance metrics
    transcription_latency_ms = Column(Integer, nullable=True)
    sentiment_analysis_latency_ms = Column(Integer, nullable=True)
    suggestion_generation_latency_ms = Column(Integer, nullable=True)
    total_latency_ms = Column(Integer, nullable=True)

    # Timestamps
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="turns")

    # Indexes
    __table_args__ = (
        Index("ix_conversation_turns_conversation_id", "conversation_id"),
        Index("ix_conversation_turns_speaker", "speaker"),
        Index("ix_conversation_turns_sentiment", "sentiment"),
        Index("ix_conversation_turns_started_at", "started_at"),
    )


class ConversationBattleCard(Base):
    """
    Battle cards triggered during conversation with usage tracking.
    """
    __tablename__ = "conversation_battle_cards"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"))

    # Battle card metadata
    card_type = Column(SQLEnum(BattleCardType), nullable=False)
    trigger_keyword = Column(String, nullable=True)  # Keyword that triggered the card
    trigger_turn_id = Column(String, nullable=True)  # Turn that triggered it

    # Content
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    talking_points = Column(JSON, nullable=True)  # List of key points
    response_template = Column(Text, nullable=True)  # Suggested response

    # Context
    relevance_score = Column(Float, nullable=True)  # How relevant to current conversation
    context = Column(JSON, nullable=True)  # Additional context data

    # Usage tracking
    suggested_at = Column(DateTime, server_default=func.now())
    viewed_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    was_helpful = Column(Boolean, nullable=True)  # Agent feedback

    # Performance
    time_to_view_seconds = Column(Integer, nullable=True)
    time_to_use_seconds = Column(Integer, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="battle_cards")

    # Indexes
    __table_args__ = (
        Index("ix_conversation_battle_cards_conversation_id", "conversation_id"),
        Index("ix_conversation_battle_cards_card_type", "card_type"),
        Index("ix_conversation_battle_cards_suggested_at", "suggested_at"),
    )


class BattleCardTemplate(Base):
    """
    Reusable battle card templates.
    """
    __tablename__ = "battle_card_templates"

    id = Column(Integer, primary_key=True)

    # Template metadata
    name = Column(String, nullable=False, unique=True)
    card_type = Column(SQLEnum(BattleCardType), nullable=False)
    description = Column(Text, nullable=True)

    # Content
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    talking_points = Column(JSON, nullable=True)
    response_template = Column(Text, nullable=True)

    # Triggers
    trigger_keywords = Column(JSON, nullable=False)  # List of keywords that trigger this card
    trigger_phrases = Column(JSON, nullable=True)  # List of phrases
    trigger_topics = Column(JSON, nullable=True)  # List of topics

    # Usage stats
    times_triggered = Column(Integer, default=0)
    times_used = Column(Integer, default=0)
    average_helpfulness_score = Column(Float, nullable=True)
    usage_rate = Column(Float, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority cards shown first

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_battle_card_templates_card_type", "card_type"),
        Index("ix_battle_card_templates_is_active", "is_active"),
        Index("ix_battle_card_templates_priority", "priority"),
    )
