"""
Workflow Action Executor

Executes workflow rule actions such as creating tasks, sending alerts,
sending Slack notifications, and triggering agents.

This is the action execution layer of the workflow automation system.
When rules match, the ActionExecutor is responsible for:
1. Routing actions to appropriate handlers
2. Executing actions with the provided configuration
3. Logging execution results for audit
4. Handling errors gracefully

Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Example usage:
    executor = ActionExecutor(
        close_api_key=settings.CLOSE_API_KEY,
        slack_webhook_url=settings.SLACK_BDR_WEBHOOK
    )
    result = await executor.execute({
        "rule_id": 1,
        "rule_name": "Won Deal Celebration",
        "action_type": "send_slack",
        "action_config": {"message": "Deal Won! {opportunity_name} for ${amount}"},
        "context": {"opportunity_name": "Acme Corp", "amount": 50000}
    })
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os

from app.services.crm.close_tasks import CloseTaskClient
from app.services.slack_notifier import SlackNotifier
from app.api.alerts import create_alert

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes workflow rule actions.

    The ActionExecutor is the action layer of the workflow automation system.
    It routes actions to appropriate handlers and executes them with the
    provided configuration and context.

    Supported action types:
    - create_task: Creates a task in Close CRM
    - send_alert: Creates an alert in dim_alerts table
    - send_slack: Sends a Slack notification
    - trigger_agent: Queues an agent task for execution
    - update_field: Updates a field on the opportunity/lead

    Attributes:
        task_client: CloseTaskClient for CRM task operations
        slack: SlackNotifier for Slack notifications

    Example:
        >>> executor = ActionExecutor(close_api_key="api_xxx")
        >>> result = await executor.execute({
        ...     "action_type": "create_task",
        ...     "action_config": {"task_text": "Follow up", "due_days": 2},
        ...     "context": {"lead_id": "lead_xxx"}
        ... })
        >>> print(result)  # {"task_id": "task_xxx", "status": "created"}
    """

    def __init__(
        self,
        close_api_key: Optional[str] = None,
        slack_webhook_url: Optional[str] = None
    ):
        """
        Initialize the action executor with required clients.

        Args:
            close_api_key: Close CRM API key (falls back to CLOSE_API_KEY env var)
            slack_webhook_url: Slack webhook URL (falls back to SLACK_BDR_WEBHOOK env var)
        """
        # Initialize Close task client
        try:
            api_key = close_api_key or os.getenv("CLOSE_API_KEY")
            if api_key:
                self.task_client = CloseTaskClient(api_key=api_key)
            else:
                self.task_client = None
                logger.warning("Close API key not configured - task actions will be skipped")
        except Exception as e:
            self.task_client = None
            logger.warning(f"Failed to initialize CloseTaskClient: {e}")

        # Initialize Slack notifier
        webhook_url = slack_webhook_url or os.getenv("SLACK_BDR_WEBHOOK")
        if webhook_url:
            self.slack = SlackNotifier(webhook_url=webhook_url)
        else:
            self.slack = None
            logger.warning("Slack webhook not configured - Slack actions will be logged only")

    async def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route action to appropriate handler and execute.

        This is the main entry point for action execution. It:
        1. Extracts action type, config, and context
        2. Routes to the appropriate handler method
        3. Returns execution result
        4. Logs execution for audit

        Args:
            action: Action dictionary containing:
                - rule_id: ID of the matched rule
                - rule_name: Name of the matched rule
                - action_type: Type of action to execute
                - action_config: Configuration for the action
                - context: Event context for action execution

        Returns:
            Dict with execution result:
            - status: Execution status (created, sent, queued, skipped, error)
            - Additional fields depending on action type

        Raises:
            ValueError: If action type is unknown

        Example:
            >>> result = await executor.execute({
            ...     "rule_id": 1,
            ...     "rule_name": "Won Deal Task",
            ...     "action_type": "create_task",
            ...     "action_config": {"task_text": "Schedule onboarding"},
            ...     "context": {"lead_id": "lead_123"}
            ... })
        """
        action_type = action.get("action_type")
        config = action.get("action_config", {})
        context = action.get("context", {})
        rule_id = action.get("rule_id")
        rule_name = action.get("rule_name", "Unknown Rule")

        logger.info(f"Executing action: {action_type} from rule '{rule_name}' (ID: {rule_id})")

        # Map action types to handlers
        handlers = {
            "create_task": self._create_task,
            "send_alert": self._send_alert,
            "send_slack": self._send_slack,
            "trigger_agent": self._trigger_agent,
            "update_field": self._update_field,
        }

        handler = handlers.get(action_type)
        if not handler:
            error_msg = f"Unknown action type: {action_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Execute the action
            result = await handler(config, context)

            # Add rule metadata to result
            result["rule_id"] = rule_id
            result["rule_name"] = rule_name
            result["action_type"] = action_type

            # Log execution
            await self._log_execution(action, result, success=True)

            logger.info(
                f"Action executed successfully: {action_type} from rule '{rule_name}' "
                f"-> {result.get('status', 'completed')}"
            )

            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "rule_id": rule_id,
                "rule_name": rule_name,
                "action_type": action_type,
            }

            # Log failed execution
            await self._log_execution(action, error_result, success=False)

            logger.error(f"Action execution failed: {action_type} from rule '{rule_name}' - {e}")
            raise

    async def _create_task(self, config: Dict, context: Dict) -> Dict[str, Any]:
        """
        Create a task in Close CRM.

        Creates a follow-up task associated with a lead for workflow automation.

        Args:
            config: Task configuration:
                - task_text: Task description (supports {variable} placeholders)
                - due_days: Days until due (default: 1)
                - task_type: Type of task (default: "follow-up")
            context: Event context:
                - lead_id: Close lead ID (required)
                - opportunity_id, company_name, etc. for placeholders

        Returns:
            Dict with task creation result:
            - task_id: Created task ID
            - status: "created" or "skipped"
        """
        if not self.task_client:
            logger.warning("CloseTaskClient not available - skipping task creation")
            return {"status": "skipped", "reason": "no_close_client"}

        lead_id = context.get("lead_id")
        if not lead_id:
            logger.warning("No lead_id in context - skipping task creation")
            return {"status": "skipped", "reason": "no_lead_id"}

        # Calculate due date
        due_days = config.get("due_days", 1)
        due_date = (datetime.now() + timedelta(days=due_days)).date()

        # Format task text with context variables
        task_text = config.get("task_text", "Follow up required")
        try:
            task_text = task_text.format(**context)
        except KeyError as e:
            logger.debug(f"Missing placeholder in task_text: {e}")
            # Keep original text if placeholder is missing

        task_type = config.get("task_type", "follow-up")

        try:
            task = await self.task_client.create_task(
                lead_id=lead_id,
                text=task_text,
                due_date=due_date,
                task_type=task_type
            )

            return {
                "status": "created",
                "task_id": task.get("id"),
                "lead_id": lead_id,
                "due_date": due_date.isoformat(),
                "task_text": task_text
            }

        except Exception as e:
            logger.error(f"Failed to create task in Close CRM: {e}")
            raise

    async def _send_alert(self, config: Dict, context: Dict) -> Dict[str, Any]:
        """
        Create alert in dim_alerts table.

        Creates a system alert that will be displayed in the BDR Cockpit
        and optionally broadcast via WebSocket.

        Args:
            config: Alert configuration:
                - title: Alert title
                - message: Alert message (supports {variable} placeholders)
                - severity: Alert severity (low, medium, high, critical)
                - alert_type: Alert category (default: "workflow")
            context: Event context for placeholders

        Returns:
            Dict with alert creation result:
            - status: "alert_created"
            - alert_id: Created alert ID
        """
        # Format message with context variables
        message = config.get("message", "Workflow alert triggered")
        try:
            message = message.format(**context)
        except KeyError as e:
            logger.debug(f"Missing placeholder in alert message: {e}")
            # Keep original message if placeholder is missing

        title = config.get("title", "Workflow Alert")
        try:
            title = title.format(**context)
        except KeyError:
            pass

        severity = config.get("severity", "medium")
        alert_type = config.get("alert_type", "workflow")

        # Build metadata from context and rule info
        metadata = {
            "rule_id": context.get("rule_id"),
            "trigger_type": context.get("event_type"),
            "source": "workflow_automation",
        }
        # Add relevant context fields
        for key in ["opportunity_id", "lead_id", "stage", "amount"]:
            if key in context:
                metadata[key] = context[key]

        try:
            alert = await create_alert(
                title=title,
                message=message,
                severity=severity,
                alert_type=alert_type,
                company_id=context.get("lead_id"),  # Map lead_id to company_id
                agent_name="workflow_automation",
                metadata=metadata,
                broadcast=True  # Broadcast to WebSocket clients
            )

            return {
                "status": "alert_created",
                "alert_id": alert.id,
                "severity": severity,
                "title": title
            }

        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            raise

    async def _send_slack(self, config: Dict, context: Dict) -> Dict[str, Any]:
        """
        Send Slack notification.

        Sends a formatted message to the configured Slack webhook.
        If no webhook is configured, the message is logged instead.

        Args:
            config: Slack notification configuration:
                - message: Message text (supports {variable} placeholders)
            context: Event context for placeholders

        Returns:
            Dict with Slack notification result:
            - status: "sent", "skipped", or "logged"
        """
        # Format message with context variables
        message = config.get("message", "Workflow notification")
        try:
            message = message.format(**context)
        except KeyError as e:
            logger.debug(f"Missing placeholder in Slack message: {e}")
            # Keep original message if placeholder is missing

        if not self.slack:
            # Log the message if no Slack webhook configured
            logger.info(f"[SLACK LOG] Workflow notification: {message}")
            return {
                "status": "logged",
                "reason": "no_slack_configured",
                "message": message
            }

        try:
            # Use the internal _send_message method with workflow context
            rule_id = context.get("rule_id", "workflow")
            rule_name = context.get("rule_name", "Workflow Rule")

            success = await self.slack._send_message(
                payload={
                    "text": message,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": message
                            }
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"Triggered by: {rule_name}"
                                }
                            ]
                        }
                    ]
                },
                draft_id=str(rule_id),
                context=f"Workflow: {rule_name}"
            )

            if success:
                return {"status": "sent", "message": message}
            else:
                return {"status": "failed", "message": message}

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            raise

    async def _trigger_agent(self, config: Dict, context: Dict) -> Dict[str, Any]:
        """
        Queue an agent task for execution.

        Queues a Celery task to run an agent (e.g., BDR agent, research agent).

        Args:
            config: Agent configuration:
                - agent_type: Type of agent to trigger (e.g., "bdr", "research")
            context: Event context to pass to the agent

        Returns:
            Dict with agent trigger result:
            - status: "queued"
            - agent_type: Type of agent triggered
        """
        agent_type = config.get("agent_type")
        if not agent_type:
            logger.warning("No agent_type specified - skipping agent trigger")
            return {"status": "skipped", "reason": "no_agent_type"}

        try:
            # Import here to avoid circular imports
            from app.tasks.agent_tasks import execute_agent_task

            # Queue the agent task
            # Note: We use delay() for async execution
            task = execute_agent_task.delay(
                agent_type=agent_type,
                lead_id=context.get("lead_id"),
                input_data=context
            )

            logger.info(f"Agent task queued: {agent_type} (task_id: {task.id})")

            return {
                "status": "queued",
                "agent_type": agent_type,
                "task_id": task.id
            }

        except Exception as e:
            logger.error(f"Failed to queue agent task: {e}")
            raise

    async def _update_field(self, config: Dict, context: Dict) -> Dict[str, Any]:
        """
        Update a field on the opportunity/lead.

        Updates fields in Close CRM via the CloseProvider.
        Currently a placeholder for future implementation.

        Args:
            config: Field update configuration:
                - field_name: Name of field to update
                - field_value: New value for the field
            context: Event context with entity IDs

        Returns:
            Dict with field update result:
            - status: "updated" or "not_implemented"
        """
        field_name = config.get("field_name")
        field_value = config.get("field_value")

        if not field_name or field_value is None:
            logger.warning("Missing field_name or field_value - skipping field update")
            return {"status": "skipped", "reason": "missing_field_config"}

        # TODO: Implement field updates via CloseProvider
        # This would involve:
        # 1. Determining entity type (opportunity, lead, contact)
        # 2. Getting entity ID from context
        # 3. Calling appropriate CloseProvider update method

        logger.info(
            f"Field update action: {field_name}={field_value} "
            f"(opportunity_id={context.get('opportunity_id')})"
        )

        return {
            "status": "not_implemented",
            "field_name": field_name,
            "field_value": field_value,
            "note": "Field updates will be implemented in a future release"
        }

    async def _log_execution(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        success: bool = True
    ) -> None:
        """
        Log action execution to audit trail.

        Logs execution details for monitoring and debugging.
        In the future, this could also store to a database for analytics.

        Args:
            action: The executed action
            result: Execution result
            success: Whether execution was successful
        """
        log_level = logging.INFO if success else logging.ERROR
        status = result.get("status", "unknown")

        logger.log(
            log_level,
            f"Workflow action executed: type={action.get('action_type')}, "
            f"rule_id={action.get('rule_id')}, "
            f"rule_name={action.get('rule_name')}, "
            f"status={status}, "
            f"success={success}"
        )


# Convenience function to get an executor instance
def get_action_executor() -> ActionExecutor:
    """
    Get an ActionExecutor instance with default configuration.

    Uses environment variables for API keys and webhook URLs.

    Returns:
        Configured ActionExecutor instance
    """
    return ActionExecutor(
        close_api_key=os.getenv("CLOSE_API_KEY"),
        slack_webhook_url=os.getenv("SLACK_BDR_WEBHOOK")
    )


__all__ = ["ActionExecutor", "get_action_executor"]
