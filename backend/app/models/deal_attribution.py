"""
DealAttribution model for multi-touch attribution tracking.

Tracks all touchpoints that contributed to closed deals:
- First touch (awareness)
- Last touch (conversion)
- Linear (equal credit)
- Time decay (recent touches weighted higher)
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Text, ForeignKey,
    DateTime, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.database import Base


class DealAttribution(Base):
    """
    Attribution record for a closed deal.

    Stores touchpoints and pre-calculated attribution values
    for fast dashboard queries.
    """
    __tablename__ = "fact_deal_attribution"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Deal identification
    deal_id = Column(String(100), nullable=False, unique=True)
    lead_id = Column(UUID(as_uuid=True),
                    ForeignKey("dim_companies.id", ondelete="SET NULL"),
                    nullable=True)
    deal_name = Column(String(255), nullable=True)

    # Deal value and timing
    deal_value = Column(Numeric(12, 2), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Touchpoint tracking
    touchpoints = Column(JSONB, nullable=False, default=list)
    total_touches = Column(Integer, default=0, nullable=False)
    days_in_pipeline = Column(Integer, nullable=True)

    # Multi-touch attribution (pre-calculated)
    first_touch_channel = Column(String(100), nullable=True)
    last_touch_channel = Column(String(100), nullable=True)
    first_touch_value = Column(Numeric(12, 2), nullable=True)
    last_touch_value = Column(Numeric(12, 2), nullable=True)
    linear_touch_value = Column(Numeric(12, 2), nullable=True)
    time_decay_value = Column(Numeric(12, 2), nullable=True)

    # Sales rep
    rep_id = Column(String(100), nullable=True)
    rep_name = Column(String(255), nullable=True)

    # Campaign/source
    primary_campaign = Column(String(255), nullable=True)
    primary_source = Column(String(100), nullable=True)

    # Metadata
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow,
                       onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "id": str(self.id),
            "deal_id": self.deal_id,
            "lead_id": str(self.lead_id) if self.lead_id else None,
            "deal_name": self.deal_name,
            "deal_value": float(self.deal_value) if self.deal_value else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "touchpoints": self.touchpoints,
            "total_touches": self.total_touches,
            "days_in_pipeline": self.days_in_pipeline,
            "first_touch_channel": self.first_touch_channel,
            "last_touch_channel": self.last_touch_channel,
            "first_touch_value": float(self.first_touch_value) if self.first_touch_value else None,
            "last_touch_value": float(self.last_touch_value) if self.last_touch_value else None,
            "linear_touch_value": float(self.linear_touch_value) if self.linear_touch_value else None,
            "time_decay_value": float(self.time_decay_value) if self.time_decay_value else None,
            "rep_id": self.rep_id,
            "rep_name": self.rep_name,
            "primary_campaign": self.primary_campaign,
            "primary_source": self.primary_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def add_touchpoint(
        self,
        touchpoint_type: str,
        channel: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a touchpoint to the deal."""
        touchpoint = {
            "type": touchpoint_type,
            "channel": channel,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }
        self.touchpoints = self.touchpoints + [touchpoint]
        self.total_touches = len(self.touchpoints)

    @property
    def touchpoint_summary(self) -> Dict[str, int]:
        """Get count of touchpoints by channel."""
        summary = {}
        for tp in self.touchpoints:
            channel = tp.get("channel", "unknown")
            summary[channel] = summary.get(channel, 0) + 1
        return summary


class TouchpointType(Base):
    """Standardized touchpoint type definitions."""
    __tablename__ = "touchpoint_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, unique=True)
    channel = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    default_weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "channel": self.channel,
            "description": self.description,
            "default_weight": self.default_weight,
        }
