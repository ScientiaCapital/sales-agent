"""
Campaign and Outreach Models

Database models for personalized outreach campaigns with A/B testing support.
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Enum as SQLEnum, CheckConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from app.models.database import Base


class CampaignStatus(str, Enum):
    """Campaign status enum"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignChannel(str, Enum):
    """Campaign communication channel enum"""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    SMS = "sms"
    CUSTOM = "custom"


class MessageStatus(str, Enum):
    """Message delivery status enum"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


class MessageTone(str, Enum):
    """Message tone/style enum"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    DIRECT = "direct"


class Campaign(Base):
    """
    Campaign model for outreach campaigns.

    Supports multi-channel outreach with A/B testing and performance tracking.
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False, index=True)
    channel = Column(SQLEnum(CampaignChannel), default=CampaignChannel.EMAIL, nullable=False)

    # Target audience filters
    min_qualification_score = Column(Float, nullable=True)
    target_industries = Column(JSON, nullable=True)  # List of industry filters
    target_company_sizes = Column(JSON, nullable=True)  # List of size filters

    # Message template
    message_template = Column(Text, nullable=True)  # Template with {{variables}}
    custom_context = Column(Text, nullable=True)  # Additional context for generation

    # Performance metrics
    total_messages = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)

    # Cost tracking
    total_cost = Column(Float, default=0.0)  # USD

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    messages = relationship("CampaignMessage", back_populates="campaign", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_campaign_status_channel', 'status', 'channel'),
        CheckConstraint('total_sent <= total_messages', name='check_sent_messages'),
        CheckConstraint('total_cost >= 0', name='check_positive_cost'),
    )

    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', status='{self.status}', channel='{self.channel}')>"

    @property
    def open_rate(self) -> float:
        """Calculate email open rate"""
        if self.total_delivered == 0:
            return 0.0
        return (self.total_opened / self.total_delivered) * 100

    @property
    def click_rate(self) -> float:
        """Calculate click-through rate"""
        if self.total_delivered == 0:
            return 0.0
        return (self.total_clicked / self.total_delivered) * 100

    @property
    def reply_rate(self) -> float:
        """Calculate reply rate"""
        if self.total_delivered == 0:
            return 0.0
        return (self.total_replied / self.total_delivered) * 100

    @property
    def delivery_rate(self) -> float:
        """Calculate delivery success rate"""
        if self.total_sent == 0:
            return 0.0
        return (self.total_delivered / self.total_sent) * 100


class CampaignMessage(Base):
    """
    Individual message in a campaign with 3 variants for A/B testing.
    """
    __tablename__ = "campaign_messages"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    # Message variants (3 versions with different tones)
    variants = Column(JSON, nullable=False)  # List of 3 variant dicts
    selected_variant = Column(Integer, default=0, nullable=False)  # 0, 1, or 2

    # Message status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.PENDING, nullable=False, index=True)

    # Personalization context
    personalization_data = Column(JSON, nullable=True)  # Lead context used for generation

    # Performance tracking
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)

    # Cost tracking
    generation_cost = Column(Float, default=0.0)  # USD for AI generation

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="messages")
    lead = relationship("Lead", backref="campaign_messages")
    analytics = relationship("MessageVariantAnalytics", back_populates="message", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_campaign_message_status', 'campaign_id', 'status'),
        Index('idx_message_lead', 'lead_id', 'status'),
        CheckConstraint('selected_variant >= 0 AND selected_variant <= 2', name='check_variant_range'),
        CheckConstraint('generation_cost >= 0', name='check_positive_generation_cost'),
    )

    def __repr__(self):
        return f"<CampaignMessage(id={self.id}, campaign_id={self.campaign_id}, lead_id={self.lead_id}, status='{self.status}')>"


class MessageVariantAnalytics(Base):
    """
    A/B testing analytics for message variants.

    Tracks performance of each variant (professional, friendly, direct) for data-driven optimization.
    """
    __tablename__ = "message_variant_analytics"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("campaign_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_number = Column(Integer, nullable=False)  # 0, 1, or 2
    tone = Column(SQLEnum(MessageTone), nullable=False)

    # Variant content
    subject = Column(String(255), nullable=True)  # For email
    body = Column(Text, nullable=False)

    # Performance metrics (when this variant is selected)
    times_selected = Column(Integer, default=0)
    times_opened = Column(Integer, default=0)
    times_clicked = Column(Integer, default=0)
    times_replied = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    message = relationship("CampaignMessage", back_populates="analytics")

    # Indexes
    __table_args__ = (
        Index('idx_variant_analytics', 'message_id', 'variant_number'),
        CheckConstraint('variant_number >= 0 AND variant_number <= 2', name='check_analytics_variant_range'),
        CheckConstraint('times_selected >= 0', name='check_positive_selected'),
        CheckConstraint('times_opened >= 0', name='check_positive_opened'),
        CheckConstraint('times_clicked >= 0', name='check_positive_clicked'),
        CheckConstraint('times_replied >= 0', name='check_positive_replied'),
    )

    def __repr__(self):
        return f"<MessageVariantAnalytics(id={self.id}, message_id={self.message_id}, variant={self.variant_number}, tone='{self.tone}')>"

    @property
    def open_rate(self) -> float:
        """Calculate open rate for this variant"""
        if self.times_selected == 0:
            return 0.0
        return (self.times_opened / self.times_selected) * 100

    @property
    def click_rate(self) -> float:
        """Calculate click rate for this variant"""
        if self.times_selected == 0:
            return 0.0
        return (self.times_clicked / self.times_selected) * 100

    @property
    def reply_rate(self) -> float:
        """Calculate reply rate for this variant"""
        if self.times_selected == 0:
            return 0.0
        return (self.times_replied / self.times_selected) * 100
