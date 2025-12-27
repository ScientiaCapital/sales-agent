"""Pytest fixtures for workflow tests.

These tests use mocks to avoid database dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
import enum
import os

# Set test environment before any imports
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


# Mock the workflow enums for testing without DB dependency
class TriggerType(enum.Enum):
    """Mock TriggerType enum for testing."""
    STAGE_CHANGE = "stage_change"
    LEAD_CREATED = "lead_created"
    OPPORTUNITY_WON = "opportunity_won"
    OPPORTUNITY_LOST = "opportunity_lost"
    DAYS_IN_STAGE = "days_in_stage"
    ICP_TIER_CHANGE = "icp_tier_change"


class ActionType(enum.Enum):
    """Mock ActionType enum for testing."""
    CREATE_TASK = "create_task"
    SEND_ALERT = "send_alert"
    SEND_SLACK = "send_slack"
    TRIGGER_AGENT = "trigger_agent"
    UPDATE_FIELD = "update_field"


class WorkflowRule:
    """Mock WorkflowRule for testing."""
    pass


@pytest.fixture
def mock_db_session():
    """Create a mock database session with common query patterns."""
    db = MagicMock()

    # Setup query chain
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []
    query.first.return_value = None

    return db


@pytest.fixture
def sample_workflow_rule():
    """Create a sample WorkflowRule for testing."""
    rule = MagicMock(spec=WorkflowRule)
    rule.id = 1
    rule.name = "Test Workflow Rule"
    rule.description = "A test rule for unit testing"
    rule.trigger_type = TriggerType.STAGE_CHANGE.value
    rule.trigger_conditions = {"stage": "proposal"}
    rule.action_type = ActionType.CREATE_TASK.value
    rule.action_config = {
        "task_text": "Follow up with lead",
        "due_days": 2,
        "task_type": "follow-up"
    }
    rule.is_active = True
    rule.priority = 50
    rule.created_at = datetime.now()
    rule.updated_at = datetime.now()
    rule.execution_count = 0
    rule.last_executed_at = None
    return rule


@pytest.fixture
def sample_opportunity_context():
    """Create sample opportunity context for action execution."""
    return {
        "opportunity_id": "opp_abc123",
        "opportunity_name": "Acme Corp - Enterprise Deal",
        "lead_id": "lead_xyz789",
        "company_name": "Acme Corporation",
        "contact_name": "John Smith",
        "contact_email": "john@acme.com",
        "amount": 75000,
        "stage": "proposal",
        "previous_stage": "qualification",
        "icp_tier": "PLATINUM",
        "days_in_stage": 5,
        "rule_id": 1,
        "rule_name": "Test Rule",
    }


@pytest.fixture
def sample_stage_change_context():
    """Create sample context for stage change events."""
    return {
        "event_type": "opportunity.status_changed",
        "opportunity_id": "opp_def456",
        "opportunity_name": "BigCo Deal",
        "lead_id": "lead_ghi012",
        "previous_stage": "meeting_booked",
        "stage": "proposal",
        "amount": 100000,
        "icp_tier": "GOLD",
        "changed_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_won_deal_context():
    """Create sample context for won deal events."""
    return {
        "event_type": "opportunity.won",
        "opportunity_id": "opp_won123",
        "opportunity_name": "Victory Corp",
        "lead_id": "lead_win789",
        "company_name": "Victory Corporation",
        "amount": 250000,
        "stage": "closed_won",
        "won_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_lost_deal_context():
    """Create sample context for lost deal events."""
    return {
        "event_type": "opportunity.lost",
        "opportunity_id": "opp_lost456",
        "opportunity_name": "Lost Opportunity",
        "lead_id": "lead_lost012",
        "company_name": "Lost Corp",
        "amount": 50000,
        "stage": "closed_lost",
        "lost_reason": "Competitor",
        "lost_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_close_task_client():
    """Create mock Close task client."""
    client = MagicMock()
    client.create_task = AsyncMock(return_value={"id": "task_mock123"})
    client.update_task = AsyncMock(return_value={"id": "task_mock123", "is_complete": True})
    client.delete_task = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_slack_notifier():
    """Create mock Slack notifier."""
    notifier = MagicMock()
    notifier.send_message = AsyncMock(return_value={"ok": True})
    notifier.send_block_message = AsyncMock(return_value={"ok": True})
    return notifier


@pytest.fixture
def mock_redis():
    """Create mock Redis client for Celery tasks."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.close = AsyncMock()
    return redis


@pytest.fixture
def workflow_rules_list(sample_workflow_rule):
    """Create list of multiple workflow rules for testing."""
    rules = []

    # Stage change rule
    rule1 = MagicMock(spec=WorkflowRule)
    rule1.id = 1
    rule1.name = "Stage Change Alert"
    rule1.trigger_type = TriggerType.STAGE_CHANGE.value
    rule1.trigger_conditions = {"stage": "proposal"}
    rule1.action_type = ActionType.SEND_ALERT.value
    rule1.action_config = {"title": "Stage Changed", "message": "Deal moved to proposal"}
    rule1.is_active = True
    rule1.priority = 10
    rules.append(rule1)

    # Won deal rule
    rule2 = MagicMock(spec=WorkflowRule)
    rule2.id = 2
    rule2.name = "Won Deal Celebration"
    rule2.trigger_type = TriggerType.OPPORTUNITY_WON.value
    rule2.trigger_conditions = {}
    rule2.action_type = ActionType.SEND_SLACK.value
    rule2.action_config = {"message": "Deal Won! :tada:"}
    rule2.is_active = True
    rule2.priority = 5
    rules.append(rule2)

    # High value task rule
    rule3 = MagicMock(spec=WorkflowRule)
    rule3.id = 3
    rule3.name = "High Value Follow Up"
    rule3.trigger_type = TriggerType.STAGE_CHANGE.value
    rule3.trigger_conditions = {"amount": {"gte": 100000}}
    rule3.action_type = ActionType.CREATE_TASK.value
    rule3.action_config = {"task_text": "High value deal - prioritize!", "due_days": 1}
    rule3.is_active = True
    rule3.priority = 15
    rules.append(rule3)

    return rules
