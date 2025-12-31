"""
ActionExecutor - Executes automation actions.

Supported actions:
- pause_sequence: Pause an email sequence for a lead
- resume_sequence: Resume a paused sequence
- notify_slack: Send Slack notification
- update_lead_stage: Update lead pipeline stage
- create_task: Create a follow-up task
- escalate_to_rep: Assign to human rep
- send_email: Send an email via sequence
- update_crm: Update CRM fields
- webhook: Call external webhook
"""
import logging
import os
from typing import Dict, Any, Optional, Callable, Awaitable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trigger_rule import ActionType

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes automation actions triggered by rules.

    Each action type has a dedicated handler method.
    Actions receive params and context for execution.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self._handlers: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
            ActionType.PAUSE_SEQUENCE.value: self._pause_sequence,
            ActionType.RESUME_SEQUENCE.value: self._resume_sequence,
            ActionType.NOTIFY_SLACK.value: self._notify_slack,
            ActionType.UPDATE_LEAD_STAGE.value: self._update_lead_stage,
            ActionType.CREATE_TASK.value: self._create_task,
            ActionType.ESCALATE_TO_REP.value: self._escalate_to_rep,
            ActionType.SEND_EMAIL.value: self._send_email,
            ActionType.UPDATE_CRM.value: self._update_crm,
            ActionType.WEBHOOK.value: self._call_webhook,
        }

    async def execute(
        self,
        action_type: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute an action.

        Args:
            action_type: Type of action to execute
            params: Action-specific parameters
            context: Execution context (event_data, entity_type, entity_id)

        Returns:
            Action result dictionary
        """
        handler = self._handlers.get(action_type)
        if not handler:
            raise ValueError(f"Unknown action type: {action_type}")

        logger.info(f"Executing action: {action_type}")
        result = await handler(params, context)
        logger.info(f"Action {action_type} completed: {result}")

        return result

    async def _pause_sequence(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pause an email sequence for a lead."""
        from app.services.outreach.sequence_manager import SequenceManager

        lead_id = params.get("lead_id") or context.get("entity_id")
        sequence_id = params.get("sequence_id")
        reason = params.get("reason", "Trigger rule activated")

        if not lead_id:
            return {"success": False, "error": "No lead_id provided"}

        try:
            manager = SequenceManager(self.db)
            await manager.pause_lead_sequences(
                lead_id=lead_id,
                sequence_id=sequence_id,
                reason=reason,
            )
            return {
                "success": True,
                "lead_id": lead_id,
                "action": "sequence_paused",
            }
        except Exception as e:
            logger.error(f"Failed to pause sequence: {e}")
            return {"success": False, "error": str(e)}

    async def _resume_sequence(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resume a paused email sequence."""
        from app.services.outreach.sequence_manager import SequenceManager

        lead_id = params.get("lead_id") or context.get("entity_id")
        sequence_id = params.get("sequence_id")

        if not lead_id:
            return {"success": False, "error": "No lead_id provided"}

        try:
            manager = SequenceManager(self.db)
            await manager.resume_lead_sequences(
                lead_id=lead_id,
                sequence_id=sequence_id,
            )
            return {
                "success": True,
                "lead_id": lead_id,
                "action": "sequence_resumed",
            }
        except Exception as e:
            logger.error(f"Failed to resume sequence: {e}")
            return {"success": False, "error": str(e)}

    async def _notify_slack(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send a Slack notification."""
        webhook_url = params.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL")
        channel = params.get("channel")
        message = params.get("message", "Trigger rule activated")

        # Template message with context
        event_data = context.get("event_data", {})
        message = self._template_message(message, {
            **event_data,
            "rule_name": context.get("rule_name", "Unknown"),
            "entity_type": context.get("entity_type", ""),
            "entity_id": context.get("entity_id", ""),
        })

        if not webhook_url:
            return {"success": False, "error": "No Slack webhook URL configured"}

        try:
            payload = {"text": message}
            if channel:
                payload["channel"] = channel

            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()

            return {"success": True, "action": "slack_notified", "message": message}
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return {"success": False, "error": str(e)}

    async def _update_lead_stage(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update lead pipeline stage."""
        lead_id = params.get("lead_id") or context.get("entity_id")
        new_stage = params.get("stage")

        if not lead_id or not new_stage:
            return {"success": False, "error": "lead_id and stage required"}

        try:
            # Use Close CRM API to update lead
            from app.services.integrations.close_api import CloseAPIClient

            close_client = CloseAPIClient()
            await close_client.update_lead(
                lead_id=lead_id,
                data={"status_id": new_stage}
            )

            return {
                "success": True,
                "lead_id": lead_id,
                "new_stage": new_stage,
            }
        except Exception as e:
            logger.error(f"Failed to update lead stage: {e}")
            return {"success": False, "error": str(e)}

    async def _create_task(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a follow-up task."""
        lead_id = params.get("lead_id") or context.get("entity_id")
        title = params.get("title", "Follow-up task")
        description = params.get("description", "")
        assigned_to = params.get("assigned_to")
        due_days = params.get("due_days", 1)

        # Template title/description
        event_data = context.get("event_data", {})
        title = self._template_message(title, event_data)
        description = self._template_message(description, event_data)

        try:
            from app.services.integrations.close_api import CloseAPIClient
            from datetime import datetime, timedelta

            close_client = CloseAPIClient()
            due_date = datetime.utcnow() + timedelta(days=due_days)

            task = await close_client.create_task(
                lead_id=lead_id,
                text=title,
                assigned_to=assigned_to,
                date=due_date.strftime("%Y-%m-%d"),
            )

            return {
                "success": True,
                "task_id": task.get("id"),
                "lead_id": lead_id,
            }
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {"success": False, "error": str(e)}

    async def _escalate_to_rep(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Escalate lead to a human sales rep."""
        lead_id = params.get("lead_id") or context.get("entity_id")
        rep_id = params.get("rep_id")
        reason = params.get("reason", "Trigger rule escalation")

        if not lead_id:
            return {"success": False, "error": "lead_id required"}

        try:
            from app.services.integrations.close_api import CloseAPIClient

            close_client = CloseAPIClient()

            # Update lead owner
            await close_client.update_lead(
                lead_id=lead_id,
                data={"user_id": rep_id} if rep_id else {}
            )

            # Create high-priority task
            await close_client.create_task(
                lead_id=lead_id,
                text=f"ESCALATED: {reason}",
                assigned_to=rep_id,
                is_priority=True,
            )

            # Send Slack notification
            await self._notify_slack(
                params={
                    "message": f":rotating_light: Lead escalated: {reason}"
                },
                context=context,
            )

            return {
                "success": True,
                "lead_id": lead_id,
                "rep_id": rep_id,
                "reason": reason,
            }
        except Exception as e:
            logger.error(f"Failed to escalate to rep: {e}")
            return {"success": False, "error": str(e)}

    async def _send_email(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send an email (via sequence or direct)."""
        lead_id = params.get("lead_id") or context.get("entity_id")
        template_id = params.get("template_id")
        subject = params.get("subject")
        body = params.get("body")

        if not lead_id:
            return {"success": False, "error": "lead_id required"}

        try:
            from app.services.outreach.email_sender import EmailSender

            sender = EmailSender(self.db)
            result = await sender.send_email(
                lead_id=lead_id,
                template_id=template_id,
                subject=subject,
                body=body,
            )

            return {
                "success": True,
                "lead_id": lead_id,
                "email_id": result.get("id"),
            }
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}

    async def _update_crm(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update CRM fields for a lead."""
        lead_id = params.get("lead_id") or context.get("entity_id")
        fields = params.get("fields", {})

        if not lead_id or not fields:
            return {"success": False, "error": "lead_id and fields required"}

        try:
            from app.services.integrations.close_api import CloseAPIClient

            close_client = CloseAPIClient()
            await close_client.update_lead(
                lead_id=lead_id,
                data=fields,
            )

            return {
                "success": True,
                "lead_id": lead_id,
                "updated_fields": list(fields.keys()),
            }
        except Exception as e:
            logger.error(f"Failed to update CRM: {e}")
            return {"success": False, "error": str(e)}

    async def _call_webhook(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call an external webhook."""
        url = params.get("url")
        method = params.get("method", "POST").upper()
        headers = params.get("headers", {})
        payload = params.get("payload", {})

        if not url:
            return {"success": False, "error": "url required"}

        # Merge context into payload
        payload = {
            **payload,
            "trigger_context": {
                "rule_id": context.get("rule_id"),
                "rule_name": context.get("rule_name"),
                "entity_type": context.get("entity_type"),
                "entity_id": context.get("entity_id"),
                "event_data": context.get("event_data", {}),
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=payload)
                else:
                    response = await client.post(url, headers=headers, json=payload)

                return {
                    "success": response.is_success,
                    "status_code": response.status_code,
                    "url": url,
                }
        except Exception as e:
            logger.error(f"Webhook call failed: {e}")
            return {"success": False, "error": str(e)}

    def _template_message(
        self,
        template: str,
        data: Dict[str, Any],
    ) -> str:
        """Replace {{key}} placeholders in template with data values."""
        for key, value in data.items():
            if isinstance(value, (str, int, float)):
                template = template.replace(f"{{{{{key}}}}}", str(value))
        return template
