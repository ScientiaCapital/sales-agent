"""
Workflow Automation Database Models

SQLAlchemy models for workflow rules that define automation triggers and actions.
Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Example workflow rules:
- When opportunity stage changes to "Won" -> Create task for onboarding
- When lead is created with PLATINUM ICP tier -> Send Slack alert
- When deal is in "Proposal" stage for > 7 days -> Trigger follow-up agent
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, JSON, Text, Index
)
from sqlalchemy.sql import func
from datetime import datetime
from app.models.database import Base
import enum


class TriggerType(enum.Enum):
    """Enumeration of event types that can trigger workflow rules."""
    STAGE_CHANGE = "stage_change"
    LEAD_CREATED = "lead_created"
    OPPORTUNITY_WON = "opportunity_won"
    OPPORTUNITY_LOST = "opportunity_lost"
    DAYS_IN_STAGE = "days_in_stage"
    ICP_TIER_CHANGE = "icp_tier_change"


class ActionType(enum.Enum):
    """Enumeration of actions that can be performed when a rule triggers."""
    CREATE_TASK = "create_task"
    SEND_ALERT = "send_alert"
    SEND_SLACK = "send_slack"
    TRIGGER_AGENT = "trigger_agent"
    UPDATE_FIELD = "update_field"


class WorkflowRule(Base):
    """
    Automation rule that triggers actions on events.

    Workflow rules allow declarative automation in the sales pipeline.
    Each rule has:
    - A trigger type (what event fires the rule)
    - Trigger conditions (JSON filters to match specific cases)
    - An action type (what to do when triggered)
    - Action config (JSON parameters for the action)

    Examples:
        Rule 1: Stage change to "Won" -> Create onboarding task
        {
            "name": "Won Deal Onboarding",
            "trigger_type": "stage_change",
            "trigger_conditions": {"to_stage": "won"},
            "action_type": "create_task",
            "action_config": {"task_text": "Schedule onboarding call", "due_days": 1}
        }

        Rule 2: PLATINUM lead created -> Slack alert
        {
            "name": "PLATINUM Lead Alert",
            "trigger_type": "lead_created",
            "trigger_conditions": {"icp_tier": "PLATINUM"},
            "action_type": "send_slack",
            "action_config": {"channel": "#high-value-leads", "mention": "@tim"}
        }
    """

    __tablename__ = "workflow_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Trigger configuration
    trigger_type = Column(String(50), nullable=False, index=True)
    trigger_conditions = Column(JSON, nullable=False)  # {"stage": "won", "icp_tier": "PLATINUM"}

    # Action configuration
    action_type = Column(String(50), nullable=False)
    action_config = Column(JSON, nullable=False)  # {"task_text": "Follow up", "due_days": 1}

    # Rule control
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=100)  # Lower = higher priority

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Audit
    created_by = Column(String(255), nullable=True)

    # Execution tracking
    execution_count = Column(Integer, default=0)
    last_executed_at = Column(DateTime, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_workflow_rules_trigger_type', 'trigger_type'),
        Index('idx_workflow_rules_is_active', 'is_active'),
        Index('idx_workflow_rules_priority', 'priority'),
        Index('idx_workflow_rules_active_trigger', 'is_active', 'trigger_type'),
    )

    def __repr__(self):
        return f"<WorkflowRule(id={self.id}, name='{self.name}', trigger_type='{self.trigger_type}', is_active={self.is_active})>"
