"""
TriggerRule and TriggerExecution models.

Represents automation rules that trigger actions based on signals:
- call_insight: Triggered when call analysis completes
- email_reply: Triggered on email reply classification
- signal: Triggered on lead/account signals
- lead_update: Triggered on lead status changes
- deal_update: Triggered on deal stage changes
"""
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, Float, ForeignKey,
    DateTime, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.database import Base


class TriggerType(str, Enum):
    """Types of events that can trigger rules."""
    CALL_INSIGHT = "call_insight"
    EMAIL_REPLY = "email_reply"
    SIGNAL = "signal"
    LEAD_UPDATE = "lead_update"
    DEAL_UPDATE = "deal_update"


class ActionType(str, Enum):
    """Types of actions that rules can execute."""
    PAUSE_SEQUENCE = "pause_sequence"
    RESUME_SEQUENCE = "resume_sequence"
    NOTIFY_SLACK = "notify_slack"
    UPDATE_LEAD_STAGE = "update_lead_stage"
    CREATE_TASK = "create_task"
    ESCALATE_TO_REP = "escalate_to_rep"
    SEND_EMAIL = "send_email"
    UPDATE_CRM = "update_crm"
    WEBHOOK = "webhook"


class ConditionOperator(str, Enum):
    """Operators for rule conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "neq"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class TriggerRule(Base):
    """
    Automation rule definition.

    Defines when to trigger (conditions) and what to do (actions).
    """
    __tablename__ = "trigger_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=50, nullable=False)

    # Trigger definition
    trigger_type = Column(String(50), nullable=False)
    conditions = Column(JSONB, nullable=False, default=list)

    # Actions to execute
    actions = Column(JSONB, nullable=False, default=list)

    # Execution stats
    times_triggered = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow,
                       onupdate=datetime.utcnow)

    # Relationships
    executions = relationship("TriggerExecution", back_populates="rule",
                             cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "priority": self.priority,
            "trigger_type": self.trigger_type,
            "conditions": self.conditions,
            "actions": self.actions,
            "times_triggered": self.times_triggered,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def matches(self, event_data: Dict[str, Any]) -> bool:
        """
        Check if event data matches all rule conditions.

        Args:
            event_data: Dictionary of event attributes

        Returns:
            True if all conditions match
        """
        for condition in self.conditions:
            if not self._evaluate_condition(condition, event_data):
                return False
        return True

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> bool:
        """Evaluate a single condition against event data."""
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        # Get actual value from event data (supports nested paths)
        actual = self._get_nested_value(event_data, field)

        if operator == ConditionOperator.EQUALS.value:
            return actual == value
        elif operator == ConditionOperator.NOT_EQUALS.value:
            return actual != value
        elif operator == ConditionOperator.GREATER_THAN.value:
            return actual is not None and actual > value
        elif operator == ConditionOperator.LESS_THAN.value:
            return actual is not None and actual < value
        elif operator == ConditionOperator.GREATER_THAN_OR_EQUAL.value:
            return actual is not None and actual >= value
        elif operator == ConditionOperator.LESS_THAN_OR_EQUAL.value:
            return actual is not None and actual <= value
        elif operator == ConditionOperator.CONTAINS.value:
            return value in actual if actual else False
        elif operator == ConditionOperator.NOT_CONTAINS.value:
            return value not in actual if actual else True
        elif operator == ConditionOperator.IN.value:
            return actual in value if isinstance(value, list) else False
        elif operator == ConditionOperator.NOT_IN.value:
            return actual not in value if isinstance(value, list) else True
        elif operator == ConditionOperator.EXISTS.value:
            return actual is not None
        elif operator == ConditionOperator.NOT_EXISTS.value:
            return actual is None

        return False

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation (e.g., 'insight.sentiment')."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value


class TriggerExecution(Base):
    """
    Record of a trigger rule execution.

    Tracks what happened when a rule was triggered.
    """
    __tablename__ = "trigger_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(UUID(as_uuid=True),
                    ForeignKey("trigger_rules.id", ondelete="CASCADE"),
                    nullable=False)

    # Execution context
    trigger_data = Column(JSONB, nullable=True)
    matched_conditions = Column(JSONB, nullable=True)
    entity_type = Column(String(50), nullable=True)  # lead, deal, call
    entity_id = Column(String(255), nullable=True)

    # Actions executed
    actions_executed = Column(JSONB, nullable=True)
    action_results = Column(JSONB, nullable=True)

    # Status
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timing
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    duration_ms = Column(Integer, nullable=True)

    # Relationships
    rule = relationship("TriggerRule", back_populates="executions")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "id": str(self.id),
            "rule_id": str(self.rule_id),
            "trigger_data": self.trigger_data,
            "matched_conditions": self.matched_conditions,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "actions_executed": self.actions_executed,
            "action_results": self.action_results,
            "success": self.success,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "duration_ms": self.duration_ms,
        }
