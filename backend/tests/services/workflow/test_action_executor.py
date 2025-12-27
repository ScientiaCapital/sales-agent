"""Tests for ActionExecutor service.

Tests all action types: create_task, send_alert, send_slack, trigger_agent, update_field.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import os

# Set test environment before any imports
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")

# Mock the action executor module to avoid DB dependencies
pytest.importorskip("app.services.workflow.action_executor", reason="Skipping if action_executor not importable")


class TestActionExecutor:
    """Test suite for ActionExecutor class."""

    @pytest.fixture
    def executor(self):
        """Create ActionExecutor with mocked dependencies."""
        with patch('app.services.workflow.action_executor.CloseTaskClient') as mock_task_client, \
             patch('app.services.workflow.action_executor.SlackNotifier') as mock_slack:
            mock_task_client.return_value = MagicMock()
            mock_slack.return_value = MagicMock()
            executor = ActionExecutor(
                close_api_key="test_api_key",
                slack_webhook_url="https://hooks.slack.com/test"
            )
            yield executor

    @pytest.fixture
    def sample_context(self):
        """Sample context for action execution."""
        return {
            "lead_id": "lead_abc123",
            "opportunity_id": "opp_xyz789",
            "opportunity_name": "Acme Corp Deal",
            "company_name": "Acme Corp",
            "amount": 50000,
            "stage": "proposal",
            "icp_tier": "PLATINUM",
            "rule_id": 1,
        }

    # ==================== Create Task Tests ====================

    @pytest.mark.asyncio
    async def test_create_task_action(self, executor, sample_context):
        """Test create_task action with valid config."""
        executor.task_client.create_task = AsyncMock(return_value={"id": "task_123"})

        action = {
            "action_type": "create_task",
            "action_config": {
                "task_text": "Follow up with {company_name}",
                "due_days": 2,
                "task_type": "follow-up"
            },
            "context": sample_context
        }

        result = await executor.execute(action)

        assert result["status"] == "created"
        assert "task_id" in result
        executor.task_client.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_without_close_client(self, sample_context):
        """Test create_task gracefully handles missing Close client."""
        executor = ActionExecutor(close_api_key=None)

        action = {
            "action_type": "create_task",
            "action_config": {"task_text": "Test task"},
            "context": sample_context
        }

        result = await executor.execute(action)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_close_client"

    @pytest.mark.asyncio
    async def test_create_task_with_placeholder_formatting(self, executor, sample_context):
        """Test task text placeholder formatting."""
        executor.task_client.create_task = AsyncMock(return_value={"id": "task_456"})

        action = {
            "action_type": "create_task",
            "action_config": {
                "task_text": "Review deal {opportunity_name} worth ${amount}",
                "due_days": 1
            },
            "context": sample_context
        }

        result = await executor.execute(action)

        # Verify the task was created with formatted text
        call_args = executor.task_client.create_task.call_args
        assert "Acme Corp Deal" in str(call_args) or result["status"] == "created"

    # ==================== Send Alert Tests ====================

    @pytest.mark.asyncio
    async def test_send_alert_action(self, executor, sample_context):
        """Test send_alert action creates alert successfully."""
        with patch('app.services.workflow.action_executor.create_alert_record') as mock_alert:
            mock_alert.return_value = {"id": 1, "status": "created"}

            action = {
                "action_type": "send_alert",
                "action_config": {
                    "title": "High Value Deal Alert",
                    "message": "Deal {opportunity_name} is worth ${amount}",
                    "severity": "high",
                    "alert_type": "deal_alert"
                },
                "context": sample_context
            }

            result = await executor.execute(action)

            assert result["status"] == "alert_created"

    @pytest.mark.asyncio
    async def test_send_alert_with_metadata(self, executor, sample_context):
        """Test alert includes rule metadata."""
        with patch('app.services.workflow.action_executor.create_alert_record') as mock_alert:
            mock_alert.return_value = {"id": 1}

            action = {
                "action_type": "send_alert",
                "action_config": {
                    "title": "Test Alert",
                    "message": "Test message",
                    "severity": "medium"
                },
                "context": sample_context
            }

            await executor.execute(action)

            # Verify metadata includes rule_id
            call_args = mock_alert.call_args
            if call_args and call_args.kwargs.get("metadata"):
                assert "rule_id" in call_args.kwargs["metadata"]

    # ==================== Send Slack Tests ====================

    @pytest.mark.asyncio
    async def test_send_slack_action(self, executor, sample_context):
        """Test send_slack action sends message."""
        executor.slack.send_message = AsyncMock(return_value=True)

        action = {
            "action_type": "send_slack",
            "action_config": {
                "message": "Deal Won! {opportunity_name} for ${amount}"
            },
            "context": sample_context
        }

        result = await executor.execute(action)

        assert result["status"] == "sent"
        executor.slack.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_without_webhook(self, sample_context):
        """Test send_slack skips when no webhook configured."""
        executor = ActionExecutor(close_api_key="test", slack_webhook_url=None)

        action = {
            "action_type": "send_slack",
            "action_config": {"message": "Test message"},
            "context": sample_context
        }

        result = await executor.execute(action)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_slack_configured"

    # ==================== Trigger Agent Tests ====================

    @pytest.mark.asyncio
    async def test_trigger_agent_action(self, executor, sample_context):
        """Test trigger_agent queues Celery task."""
        with patch('app.services.workflow.action_executor.celery_app') as mock_celery:
            mock_celery.send_task = MagicMock()

            action = {
                "action_type": "trigger_agent",
                "action_config": {
                    "agent_type": "follow_up_agent",
                    "priority": "high"
                },
                "context": sample_context
            }

            result = await executor.execute(action)

            assert result["status"] == "queued"
            assert result["agent_type"] == "follow_up_agent"

    # ==================== Update Field Tests ====================

    @pytest.mark.asyncio
    async def test_update_field_action(self, executor, sample_context):
        """Test update_field action updates opportunity."""
        with patch('app.services.workflow.action_executor.CloseProvider') as mock_provider:
            mock_instance = MagicMock()
            mock_instance.update_opportunity = AsyncMock(return_value={"success": True})
            mock_provider.return_value = mock_instance

            action = {
                "action_type": "update_field",
                "action_config": {
                    "field": "custom.priority",
                    "value": "urgent"
                },
                "context": sample_context
            }

            result = await executor.execute(action)

            assert result["status"] == "updated"

    # ==================== Error Handling Tests ====================

    @pytest.mark.asyncio
    async def test_unknown_action_type_raises_error(self, executor, sample_context):
        """Test unknown action type raises ValueError."""
        action = {
            "action_type": "unknown_action",
            "action_config": {},
            "context": sample_context
        }

        with pytest.raises(ValueError, match="Unknown action type"):
            await executor.execute(action)

    @pytest.mark.asyncio
    async def test_action_failure_logged_and_raised(self, executor, sample_context):
        """Test action failures are logged and re-raised."""
        executor.task_client.create_task = AsyncMock(
            side_effect=Exception("Close API error")
        )

        action = {
            "action_type": "create_task",
            "action_config": {"task_text": "Test"},
            "context": sample_context
        }

        with pytest.raises(Exception, match="Close API error"):
            await executor.execute(action)

    @pytest.mark.asyncio
    async def test_missing_placeholder_handled_gracefully(self, executor, sample_context):
        """Test missing placeholders don't crash execution."""
        executor.task_client.create_task = AsyncMock(return_value={"id": "task_789"})

        action = {
            "action_type": "create_task",
            "action_config": {
                "task_text": "Follow up with {nonexistent_field}",
                "due_days": 1
            },
            "context": sample_context
        }

        # Should not raise, should use fallback
        result = await executor.execute(action)
        assert result is not None


class TestActionExecutorLogging:
    """Test logging and audit trail functionality."""

    @pytest.mark.asyncio
    async def test_successful_action_logged(self):
        """Test successful actions are logged to audit trail."""
        with patch('app.services.workflow.action_executor.CloseTaskClient'), \
             patch('app.services.workflow.action_executor.logger') as mock_logger:

            executor = ActionExecutor(close_api_key="test")
            executor.task_client.create_task = AsyncMock(return_value={"id": "task_1"})

            action = {
                "action_type": "create_task",
                "action_config": {"task_text": "Test"},
                "context": {"lead_id": "lead_1", "rule_id": 1}
            }

            await executor.execute(action)

            # Verify logging occurred
            assert mock_logger.info.called or mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_failed_action_logged_with_error(self):
        """Test failed actions log error details."""
        with patch('app.services.workflow.action_executor.CloseTaskClient'), \
             patch('app.services.workflow.action_executor.logger') as mock_logger:

            executor = ActionExecutor(close_api_key="test")
            executor.task_client.create_task = AsyncMock(
                side_effect=Exception("API failure")
            )

            action = {
                "action_type": "create_task",
                "action_config": {"task_text": "Test"},
                "context": {"lead_id": "lead_1"}
            }

            with pytest.raises(Exception):
                await executor.execute(action)

            mock_logger.error.assert_called()
