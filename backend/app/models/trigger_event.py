"""
Trigger Event Model

Represents buying signals detected for ICP companies:
- Funding rounds
- Hiring activity
- News/press releases
- Executive changes
- Tech stack changes
- Partnerships/acquisitions
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib


class TriggerEventType(str, Enum):
    """Types of trigger events that can be detected."""
    FUNDING = "funding"
    HIRING = "hiring"
    NEWS = "news"
    EXECUTIVE_CHANGE = "executive_change"
    TECH_STACK_CHANGE = "tech_stack_change"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    PRODUCT_LAUNCH = "product_launch"
    EXPANSION = "expansion"
    AWARD = "award"


class TriggerEventSource(str, Enum):
    """Source of the trigger event detection."""
    WEB_SCRAPE = "web_scrape"
    API = "api"
    MANUAL = "manual"


class TriggerEvent(BaseModel):
    """
    Trigger event representing a buying signal for a company.

    Used by TriggerEventDetector to store detected signals in Supabase.
    """

    event_id: Optional[UUID] = None
    company_id: UUID

    # Event classification
    event_type: TriggerEventType
    event_date: Optional[date] = None
    signal_strength: int = Field(
        ge=1,
        le=10,
        description="Priority score 1-10 (10 = hottest, immediate action required)"
    )

    # Event details
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    # Source tracking
    source_url: Optional[str] = None
    source_type: TriggerEventSource = TriggerEventSource.WEB_SCRAPE
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    # Action tracking
    actioned: bool = False
    actioned_at: Optional[datetime] = None
    actioned_by: Optional[str] = None
    action_notes: Optional[str] = None

    # Deduplication
    content_hash: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }

    @field_validator('signal_strength')
    @classmethod
    def validate_signal_strength(cls, v: int) -> int:
        """Ensure signal strength is between 1-10."""
        if not 1 <= v <= 10:
            raise ValueError('signal_strength must be between 1 and 10')
        return v

    @model_validator(mode='after')
    def generate_content_hash(self):
        """
        Generate SHA256 hash for duplicate detection.

        Hash = SHA256(company_id + title + event_type)
        """
        if self.content_hash is not None:
            return self

        if self.company_id:
            content = f"{self.company_id}{self.title or ''}{self.event_type or ''}".encode('utf-8')
            self.content_hash = hashlib.sha256(content).hexdigest()

        return self

    def to_slack_message(self) -> str:
        """
        Format trigger event as Slack alert message.

        Returns:
            Markdown-formatted Slack message
        """
        emoji_map = {
            TriggerEventType.FUNDING: "💰",
            TriggerEventType.HIRING: "👥",
            TriggerEventType.NEWS: "📰",
            TriggerEventType.EXECUTIVE_CHANGE: "👔",
            TriggerEventType.TECH_STACK_CHANGE: "💻",
            TriggerEventType.PARTNERSHIP: "🤝",
            TriggerEventType.ACQUISITION: "🏢",
            TriggerEventType.PRODUCT_LAUNCH: "🚀",
            TriggerEventType.EXPANSION: "📈",
            TriggerEventType.AWARD: "🏆",
        }

        priority_label = "🔥 HOT" if self.signal_strength >= 8 else "⚡ WARM"
        emoji = emoji_map.get(self.event_type, "📌")

        msg = f"{priority_label} {emoji} *{self.title}*\n"
        msg += f"Event Type: {self.event_type.value.replace('_', ' ').title()}\n"
        msg += f"Signal Strength: {self.signal_strength}/10\n"

        if self.description:
            msg += f"\n{self.description}\n"

        # Add relevant details
        if self.details:
            if "amount" in self.details:
                msg += f"Amount: {self.details['amount']}\n"
            if "round" in self.details:
                msg += f"Round: {self.details['round']}\n"
            if "job_count" in self.details:
                msg += f"Jobs Posted: {self.details['job_count']}\n"

        if self.source_url:
            msg += f"\nSource: <{self.source_url}|View Details>\n"

        msg += f"\nDetected: {self.detected_at.strftime('%Y-%m-%d %H:%M UTC')}"

        return msg

    def calculate_signal_strength(self) -> int:
        """
        Calculate signal strength based on event type and details.

        Returns:
            Signal strength 1-10
        """
        base_scores = {
            TriggerEventType.FUNDING: 9,  # Highest priority
            TriggerEventType.EXECUTIVE_CHANGE: 8,
            TriggerEventType.HIRING: 7,
            TriggerEventType.ACQUISITION: 8,
            TriggerEventType.PARTNERSHIP: 6,
            TriggerEventType.PRODUCT_LAUNCH: 6,
            TriggerEventType.EXPANSION: 7,
            TriggerEventType.NEWS: 5,
            TriggerEventType.TECH_STACK_CHANGE: 6,
            TriggerEventType.AWARD: 4,
        }

        score = base_scores.get(self.event_type, 5)

        # Boost for recent events
        if self.event_date:
            days_old = (datetime.utcnow().date() - self.event_date).days
            if days_old <= 7:
                score = min(10, score + 1)
            elif days_old > 30:
                score = max(1, score - 1)

        # Boost for specific details
        if self.details:
            # Large funding rounds
            if "amount" in self.details and self.event_type == TriggerEventType.FUNDING:
                amount_str = str(self.details["amount"]).lower()
                if "series" in amount_str or "million" in amount_str:
                    score = min(10, score + 1)

            # Multiple job postings
            if "job_count" in self.details and self.details["job_count"] >= 5:
                score = min(10, score + 1)

        return max(1, min(10, score))


class TriggerEventCreate(BaseModel):
    """Schema for creating a new trigger event."""
    company_id: UUID
    event_type: TriggerEventType
    event_date: Optional[date] = None
    title: str
    description: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    source_url: Optional[str] = None
    source_type: TriggerEventSource = TriggerEventSource.WEB_SCRAPE

    class Config:
        use_enum_values = True


class TriggerEventUpdate(BaseModel):
    """Schema for updating an existing trigger event."""
    actioned: Optional[bool] = None
    actioned_by: Optional[str] = None
    action_notes: Optional[str] = None

    class Config:
        use_enum_values = True
