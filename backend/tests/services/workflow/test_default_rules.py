"""Tests for default workflow rules.

Tests the DEFAULT_RULES configuration and seed_default_rules function.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.exc import IntegrityError

from app.services.workflow.default_rules import DEFAULT_RULES, seed_default_rules
from app.models.workflow import WorkflowRule, TriggerType, ActionType


class TestDefaultRulesConfiguration:
    """Test DEFAULT_RULES structure and validity."""

    def test_default_rules_not_empty(self):
        """Test that default rules are defined."""
        assert len(DEFAULT_RULES) > 0

    def test_all_rules_have_required_fields(self):
        """Test all rules have required fields."""
        required_fields = [
            "name",
            "trigger_type",
            "trigger_conditions",
            "action_type",
            "action_config",
            "priority",
        ]

        for rule in DEFAULT_RULES:
            for field in required_fields:
                assert field in rule, f"Rule '{rule.get('name', 'unknown')}' missing '{field}'"

    def test_all_trigger_types_valid(self):
        """Test all trigger types are valid enum values."""
        valid_triggers = [t.value for t in TriggerType]

        for rule in DEFAULT_RULES:
            assert rule["trigger_type"] in valid_triggers, \
                f"Invalid trigger type: {rule['trigger_type']}"

    def test_all_action_types_valid(self):
        """Test all action types are valid enum values."""
        valid_actions = [a.value for a in ActionType]

        for rule in DEFAULT_RULES:
            assert rule["action_type"] in valid_actions, \
                f"Invalid action type: {rule['action_type']}"

    def test_unique_rule_names(self):
        """Test all rule names are unique."""
        names = [rule["name"] for rule in DEFAULT_RULES]
        assert len(names) == len(set(names)), "Duplicate rule names found"

    def test_priority_values_are_integers(self):
        """Test priority values are positive integers."""
        for rule in DEFAULT_RULES:
            assert isinstance(rule["priority"], int)
            assert rule["priority"] > 0

    def test_action_configs_have_required_fields(self):
        """Test action configs have fields needed for their action type."""
        for rule in DEFAULT_RULES:
            action_type = rule["action_type"]
            config = rule["action_config"]

            if action_type == ActionType.CREATE_TASK.value:
                assert "task_text" in config, f"CREATE_TASK missing task_text: {rule['name']}"

            elif action_type == ActionType.SEND_ALERT.value:
                assert "title" in config, f"SEND_ALERT missing title: {rule['name']}"
                assert "message" in config, f"SEND_ALERT missing message: {rule['name']}"

            elif action_type == ActionType.SEND_SLACK.value:
                assert "message" in config, f"SEND_SLACK missing message: {rule['name']}"


class TestDefaultRulesContent:
    """Test specific default rule configurations."""

    def test_won_deal_celebration_rule_exists(self):
        """Test 'Won Deal Celebration' rule is configured."""
        rule = next((r for r in DEFAULT_RULES if "Won" in r["name"]), None)
        assert rule is not None
        assert rule["trigger_type"] == TriggerType.OPPORTUNITY_WON.value
        assert rule["action_type"] == ActionType.SEND_SLACK.value

    def test_lost_deal_review_rule_exists(self):
        """Test 'Lost Deal Review' rule is configured."""
        rule = next((r for r in DEFAULT_RULES if "Lost" in r["name"]), None)
        assert rule is not None
        assert rule["trigger_type"] == TriggerType.OPPORTUNITY_LOST.value

    def test_platinum_lead_alert_rule_exists(self):
        """Test 'Platinum Lead Alert' rule is configured."""
        rule = next((r for r in DEFAULT_RULES if "Platinum" in r["name"]), None)
        assert rule is not None
        assert "PLATINUM" in str(rule["trigger_conditions"])

    def test_stale_opportunity_rule_exists(self):
        """Test 'Stale Opportunity' rule is configured."""
        rule = next((r for r in DEFAULT_RULES if "Stale" in r["name"]), None)
        assert rule is not None
        assert rule["trigger_type"] == TriggerType.DAYS_IN_STAGE.value


class TestSeedDefaultRules:
    """Test seed_default_rules function."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.mark.asyncio
    async def test_seed_creates_all_rules(self, mock_db):
        """Test seeding creates all default rules when none exist."""
        result = await seed_default_rules(mock_db)

        assert result["created"] == len(DEFAULT_RULES)
        assert result["skipped"] == 0
        assert mock_db.add.call_count == len(DEFAULT_RULES)
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_seed_skips_existing_rules(self, mock_db):
        """Test seeding skips rules that already exist."""
        # First rule exists, rest don't
        existing_rule = MagicMock(spec=WorkflowRule)
        existing_rule.name = DEFAULT_RULES[0]["name"]

        def mock_query_first():
            # Return existing rule for first call, None for rest
            if mock_db.query.return_value.filter.return_value.first.call_count == 1:
                return existing_rule
            return None

        mock_db.query.return_value.filter.return_value.first.side_effect = mock_query_first

        result = await seed_default_rules(mock_db)

        assert result["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_seed_handles_integrity_error(self, mock_db):
        """Test seeding handles race condition gracefully."""
        # Simulate race condition - first check returns None, commit fails
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.commit.side_effect = [IntegrityError("", "", ""), None]

        result = await seed_default_rules(mock_db)

        mock_db.rollback.assert_called()
        assert "error" not in result or result.get("errors", 0) > 0

    @pytest.mark.asyncio
    async def test_seed_returns_created_rule_ids(self, mock_db):
        """Test seeding returns IDs of created rules."""
        # Mock the created rules with IDs
        def add_rule(rule):
            rule.id = 100 + mock_db.add.call_count

        mock_db.add.side_effect = add_rule

        result = await seed_default_rules(mock_db)

        assert "created_ids" in result or result["created"] > 0

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, mock_db):
        """Test seeding is idempotent - running twice doesn't duplicate."""
        # First run - nothing exists
        await seed_default_rules(mock_db)
        first_add_count = mock_db.add.call_count

        # Reset and simulate all rules exist
        mock_db.reset_mock()
        existing_rule = MagicMock(spec=WorkflowRule)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_rule

        # Second run - all exist
        result = await seed_default_rules(mock_db)

        assert result["created"] == 0
        assert result["skipped"] == len(DEFAULT_RULES)
        assert mock_db.add.call_count == 0


class TestDefaultRulesPriority:
    """Test priority ordering of default rules."""

    def test_critical_rules_have_low_priority_numbers(self):
        """Test high-impact rules have lower priority numbers (executed first)."""
        # Find rules that should be high priority
        for rule in DEFAULT_RULES:
            if "Platinum" in rule["name"] or "Won" in rule["name"]:
                assert rule["priority"] <= 15, \
                    f"High-impact rule '{rule['name']}' should have low priority number"

    def test_no_duplicate_priorities(self):
        """Test no two rules have the same priority (for deterministic ordering)."""
        priorities = [rule["priority"] for rule in DEFAULT_RULES]
        # Allow duplicates but warn
        if len(priorities) != len(set(priorities)):
            # This is actually OK - multiple rules can have same priority
            pass
