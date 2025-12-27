"""Tests for WorkflowRuleEngine service.

Tests rule evaluation logic including condition matching and action generation.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.services.workflow.rule_engine import WorkflowRuleEngine
from app.models.workflow import WorkflowRule, TriggerType, ActionType


class TestWorkflowRuleEngine:
    """Test suite for WorkflowRuleEngine class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        return db

    @pytest.fixture
    def engine(self, mock_db):
        """Create WorkflowRuleEngine with mock db."""
        return WorkflowRuleEngine(db_session=mock_db)

    @pytest.fixture
    def sample_rule(self):
        """Create sample workflow rule for testing."""
        rule = MagicMock(spec=WorkflowRule)
        rule.id = 1
        rule.name = "Test Rule"
        rule.trigger_type = TriggerType.STAGE_CHANGE.value
        rule.trigger_conditions = {"stage": "proposal"}
        rule.action_type = ActionType.CREATE_TASK.value
        rule.action_config = {"task_text": "Follow up", "due_days": 1}
        rule.is_active = True
        rule.priority = 10
        return rule

    # ==================== Rule Fetching Tests ====================

    @pytest.mark.asyncio
    async def test_get_active_rules_filters_by_trigger_type(self, engine, mock_db, sample_rule):
        """Test fetching rules filters by trigger type."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_rule]

        rules = await engine.get_active_rules(TriggerType.STAGE_CHANGE.value)

        assert len(rules) == 1
        mock_db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_rules_returns_empty_when_none_match(self, engine, mock_db):
        """Test no rules returned when none match trigger type."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        rules = await engine.get_active_rules("nonexistent_trigger")

        assert len(rules) == 0

    # ==================== Condition Evaluation Tests ====================

    def test_evaluate_conditions_exact_match(self, engine, sample_rule):
        """Test condition evaluation with exact match."""
        context = {"stage": "proposal", "amount": 10000}

        result = engine.evaluate_conditions(sample_rule, context)

        assert result is True

    def test_evaluate_conditions_no_match(self, engine, sample_rule):
        """Test condition evaluation when no match."""
        context = {"stage": "negotiation", "amount": 10000}

        result = engine.evaluate_conditions(sample_rule, context)

        assert result is False

    def test_evaluate_conditions_missing_key(self, engine, sample_rule):
        """Test condition evaluation with missing context key."""
        context = {"amount": 10000}  # Missing 'stage'

        result = engine.evaluate_conditions(sample_rule, context)

        assert result is False

    def test_evaluate_conditions_list_match(self, engine):
        """Test condition evaluation with list values (any match)."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {"stage": ["proposal", "negotiation"]}

        context = {"stage": "negotiation"}

        result = engine.evaluate_conditions(rule, context)

        assert result is True

    def test_evaluate_conditions_list_no_match(self, engine):
        """Test condition evaluation with list values (no match)."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {"stage": ["proposal", "negotiation"]}

        context = {"stage": "closed_won"}

        result = engine.evaluate_conditions(rule, context)

        assert result is False

    def test_evaluate_conditions_multiple_conditions(self, engine):
        """Test evaluation with multiple conditions (all must match)."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {
            "stage": "proposal",
            "icp_tier": "PLATINUM",
            "amount": 50000
        }

        # All match
        context_all = {"stage": "proposal", "icp_tier": "PLATINUM", "amount": 50000}
        assert engine.evaluate_conditions(rule, context_all) is True

        # One mismatch
        context_partial = {"stage": "proposal", "icp_tier": "GOLD", "amount": 50000}
        assert engine.evaluate_conditions(rule, context_partial) is False

    def test_evaluate_conditions_empty_conditions(self, engine):
        """Test evaluation with empty conditions (always matches)."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {}

        context = {"stage": "anything", "amount": 100}

        result = engine.evaluate_conditions(rule, context)

        assert result is True

    def test_evaluate_conditions_operator_gte(self, engine):
        """Test evaluation with gte operator."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {"amount": {"gte": 10000}}

        assert engine.evaluate_conditions(rule, {"amount": 15000}) is True
        assert engine.evaluate_conditions(rule, {"amount": 10000}) is True
        assert engine.evaluate_conditions(rule, {"amount": 5000}) is False

    def test_evaluate_conditions_operator_lte(self, engine):
        """Test evaluation with lte operator."""
        rule = MagicMock(spec=WorkflowRule)
        rule.trigger_conditions = {"days": {"lte": 7}}

        assert engine.evaluate_conditions(rule, {"days": 5}) is True
        assert engine.evaluate_conditions(rule, {"days": 7}) is True
        assert engine.evaluate_conditions(rule, {"days": 10}) is False

    # ==================== Event Evaluation Tests ====================

    @pytest.mark.asyncio
    async def test_evaluate_event_returns_matching_actions(self, engine, mock_db, sample_rule):
        """Test event evaluation returns actions for matching rules."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_rule]

        context = {"stage": "proposal", "lead_id": "lead_123"}
        actions = await engine.evaluate_event(TriggerType.STAGE_CHANGE.value, context)

        assert len(actions) == 1
        assert actions[0]["rule_id"] == 1
        assert actions[0]["action_type"] == ActionType.CREATE_TASK.value

    @pytest.mark.asyncio
    async def test_evaluate_event_multiple_rules(self, engine, mock_db):
        """Test event evaluation with multiple matching rules."""
        rule1 = MagicMock(spec=WorkflowRule)
        rule1.id = 1
        rule1.name = "Rule 1"
        rule1.trigger_conditions = {"stage": "proposal"}
        rule1.action_type = ActionType.CREATE_TASK.value
        rule1.action_config = {"task_text": "Task 1"}

        rule2 = MagicMock(spec=WorkflowRule)
        rule2.id = 2
        rule2.name = "Rule 2"
        rule2.trigger_conditions = {"stage": "proposal"}
        rule2.action_type = ActionType.SEND_ALERT.value
        rule2.action_config = {"title": "Alert 2"}

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rule1, rule2]

        context = {"stage": "proposal"}
        actions = await engine.evaluate_event(TriggerType.STAGE_CHANGE.value, context)

        assert len(actions) == 2
        action_types = [a["action_type"] for a in actions]
        assert ActionType.CREATE_TASK.value in action_types
        assert ActionType.SEND_ALERT.value in action_types

    @pytest.mark.asyncio
    async def test_evaluate_event_no_matching_rules(self, engine, mock_db, sample_rule):
        """Test event evaluation with no matching rules."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_rule]

        # Context doesn't match rule conditions
        context = {"stage": "closed_won", "lead_id": "lead_123"}
        actions = await engine.evaluate_event(TriggerType.STAGE_CHANGE.value, context)

        assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_evaluate_event_preserves_context(self, engine, mock_db, sample_rule):
        """Test event evaluation preserves context in action."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [sample_rule]

        context = {"stage": "proposal", "lead_id": "lead_123", "amount": 50000}
        actions = await engine.evaluate_event(TriggerType.STAGE_CHANGE.value, context)

        assert actions[0]["context"]["lead_id"] == "lead_123"
        assert actions[0]["context"]["amount"] == 50000


class TestRuleEnginePriority:
    """Test rule priority ordering."""

    @pytest.fixture
    def engine(self):
        """Create engine with mock db."""
        mock_db = MagicMock()
        return WorkflowRuleEngine(db_session=mock_db)

    @pytest.mark.asyncio
    async def test_rules_ordered_by_priority(self, engine):
        """Test rules are returned ordered by priority (lower = higher priority)."""
        # Create rules with different priorities
        high_priority = MagicMock(spec=WorkflowRule)
        high_priority.id = 1
        high_priority.name = "High Priority"
        high_priority.priority = 5
        high_priority.trigger_conditions = {}
        high_priority.action_type = ActionType.SEND_ALERT.value
        high_priority.action_config = {}

        low_priority = MagicMock(spec=WorkflowRule)
        low_priority.id = 2
        low_priority.name = "Low Priority"
        low_priority.priority = 100
        low_priority.trigger_conditions = {}
        low_priority.action_type = ActionType.CREATE_TASK.value
        low_priority.action_config = {}

        engine.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            high_priority, low_priority
        ]

        actions = await engine.evaluate_event("test_trigger", {})

        # High priority should be first
        assert actions[0]["rule_name"] == "High Priority"
        assert actions[1]["rule_name"] == "Low Priority"


class TestRuleEngineExecutionTracking:
    """Test execution count and timestamp tracking."""

    @pytest.fixture
    def engine(self):
        """Create engine with mock db."""
        mock_db = MagicMock()
        return WorkflowRuleEngine(db_session=mock_db)

    @pytest.mark.asyncio
    async def test_record_execution_updates_count(self, engine):
        """Test recording execution updates rule count."""
        rule = MagicMock(spec=WorkflowRule)
        rule.id = 1
        rule.execution_count = 5
        rule.last_executed_at = None

        engine.db.query.return_value.filter.return_value.first.return_value = rule

        await engine.record_execution(1)

        assert rule.execution_count == 6
        assert rule.last_executed_at is not None
        engine.db.commit.assert_called_once()
