"""
Workflow Rule Engine

Evaluates workflow rules against events and contexts to determine
which actions should be executed.

This is the core of the workflow automation system, responsible for:
1. Fetching active rules for a given trigger type
2. Evaluating rule conditions against event context
3. Returning matched actions for execution

Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Example usage:
    engine = WorkflowRuleEngine(db_session)
    actions = await engine.evaluate_event(
        trigger_type="stage_change",
        context={
            "opportunity_id": "oppo_123",
            "to_stage": "won",
            "lead_id": "lead_456",
            "amount": 50000
        }
    )
    # actions = [{"rule_id": 1, "action_type": "create_task", ...}]
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import operator

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowRule, TriggerType, ActionType

logger = logging.getLogger(__name__)


class WorkflowRuleEngine:
    """
    Evaluates workflow rules against events and contexts.

    The rule engine is the central component of the workflow automation system.
    It queries for active rules matching a trigger type, evaluates each rule's
    conditions against the provided context, and returns a list of actions
    to execute for matched rules.

    Attributes:
        db: SQLAlchemy database session for querying rules

    Example:
        >>> engine = WorkflowRuleEngine(db_session)
        >>> actions = await engine.evaluate_event("stage_change", {"to_stage": "won"})
        >>> for action in actions:
        ...     print(f"Execute: {action['action_type']} from rule {action['rule_name']}")
    """

    # Supported comparison operators for condition evaluation
    OPERATORS = {
        "eq": operator.eq,      # Equal: {"field": {"eq": "value"}}
        "ne": operator.ne,      # Not equal: {"field": {"ne": "value"}}
        "gt": operator.gt,      # Greater than: {"amount": {"gt": 10000}}
        "gte": operator.ge,     # Greater or equal: {"amount": {"gte": 10000}}
        "lt": operator.lt,      # Less than: {"amount": {"lt": 10000}}
        "lte": operator.le,     # Less or equal: {"amount": {"lte": 10000}}
        "in": lambda a, b: a in b,  # In list: {"stage": {"in": ["won", "closed"]}}
        "contains": lambda a, b: b in a if a else False,  # Contains: {"name": {"contains": "inc"}}
    }

    def __init__(self, db_session: Session):
        """
        Initialize the rule engine with a database session.

        Args:
            db_session: SQLAlchemy session for querying workflow rules
        """
        self.db = db_session

    async def get_active_rules(self, trigger_type: str) -> List[WorkflowRule]:
        """
        Fetch active rules for a trigger type, ordered by priority.

        Lower priority values are evaluated first (priority 1 before priority 100).
        Only rules with is_active=True are returned.

        Args:
            trigger_type: The trigger type to fetch rules for (e.g., "stage_change")

        Returns:
            List of WorkflowRule objects matching the trigger type, ordered by priority
        """
        try:
            rules = self.db.query(WorkflowRule).filter(
                WorkflowRule.trigger_type == trigger_type,
                WorkflowRule.is_active == True
            ).order_by(WorkflowRule.priority).all()

            logger.debug(f"Found {len(rules)} active rules for trigger type: {trigger_type}")
            return rules

        except Exception as e:
            logger.error(f"Failed to fetch rules for trigger type {trigger_type}: {e}")
            return []

    def evaluate_conditions(
        self,
        rule: WorkflowRule,
        context: Dict[str, Any]
    ) -> bool:
        """
        Check if rule conditions match the context.

        Supports multiple condition formats:
        1. Simple equality: {"stage": "won"} - matches if context["stage"] == "won"
        2. List matching: {"stage": ["won", "closed"]} - matches if context["stage"] in list
        3. Operator-based: {"amount": {"gt": 10000}} - uses comparison operators

        All conditions must match (AND logic).

        Args:
            rule: The WorkflowRule to evaluate
            context: Dictionary of event context values

        Returns:
            True if all conditions match, False otherwise

        Examples:
            # Simple equality
            conditions = {"to_stage": "won"}
            context = {"to_stage": "won", "amount": 50000}
            # Returns True

            # List matching
            conditions = {"icp_tier": ["PLATINUM", "GOLD"]}
            context = {"icp_tier": "PLATINUM"}
            # Returns True

            # Operator-based
            conditions = {"amount": {"gte": 10000}}
            context = {"amount": 50000}
            # Returns True
        """
        conditions = rule.trigger_conditions or {}

        if not conditions:
            # No conditions means rule always matches for this trigger type
            logger.debug(f"Rule {rule.name} has no conditions - auto-match")
            return True

        for key, expected in conditions.items():
            actual = context.get(key)

            # Handle operator-based conditions: {"field": {"gt": value}}
            if isinstance(expected, dict):
                if not self._evaluate_operator_condition(actual, expected):
                    logger.debug(
                        f"Rule {rule.name} condition failed: {key} "
                        f"(actual={actual}, expected={expected})"
                    )
                    return False

            # Handle list conditions: {"field": ["value1", "value2"]}
            elif isinstance(expected, list):
                if actual not in expected:
                    logger.debug(
                        f"Rule {rule.name} condition failed: {key} not in {expected} "
                        f"(actual={actual})"
                    )
                    return False

            # Handle simple equality: {"field": "value"}
            elif actual != expected:
                logger.debug(
                    f"Rule {rule.name} condition failed: {key} != {expected} "
                    f"(actual={actual})"
                )
                return False

        logger.debug(f"Rule {rule.name} all conditions matched")
        return True

    def _evaluate_operator_condition(
        self,
        actual: Any,
        condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a condition using comparison operators.

        Args:
            actual: The actual value from context
            condition: Dict with operator key and expected value, e.g., {"gt": 10000}

        Returns:
            True if condition is satisfied, False otherwise
        """
        for op_name, expected in condition.items():
            op_func = self.OPERATORS.get(op_name)
            if not op_func:
                logger.warning(f"Unknown operator: {op_name}")
                return False

            try:
                if not op_func(actual, expected):
                    return False
            except (TypeError, ValueError) as e:
                logger.warning(f"Operator evaluation failed: {op_name}({actual}, {expected}): {e}")
                return False

        return True

    async def evaluate_event(
        self,
        trigger_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all matching rules for an event.

        This is the main entry point for the rule engine. It:
        1. Fetches all active rules for the trigger type
        2. Evaluates each rule's conditions against the context
        3. Returns a list of actions to execute for matched rules

        Args:
            trigger_type: The type of trigger event (e.g., "stage_change", "lead_created")
            context: Dictionary containing event data for condition evaluation

        Returns:
            List of action dictionaries containing:
            - rule_id: ID of the matched rule
            - rule_name: Name of the matched rule
            - action_type: Type of action to execute
            - action_config: Configuration for the action
            - context: The event context (for action execution)

        Example:
            >>> actions = await engine.evaluate_event(
            ...     trigger_type="opportunity_won",
            ...     context={
            ...         "opportunity_id": "oppo_123",
            ...         "lead_id": "lead_456",
            ...         "amount": 50000,
            ...         "stage": "won"
            ...     }
            ... )
            >>> # Returns:
            >>> # [
            >>> #     {
            >>> #         "rule_id": 1,
            >>> #         "rule_name": "Won Deal Onboarding",
            >>> #         "action_type": "create_task",
            >>> #         "action_config": {"task_text": "Schedule onboarding", "due_days": 1},
            >>> #         "context": {...}
            >>> #     }
            >>> # ]
        """
        rules = await self.get_active_rules(trigger_type)

        if not rules:
            logger.info(f"No active rules found for trigger type: {trigger_type}")
            return []

        actions = []
        for rule in rules:
            try:
                if self.evaluate_conditions(rule, context):
                    action = {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "action_type": rule.action_type,
                        "action_config": rule.action_config or {},
                        "context": context,
                        "triggered_at": datetime.utcnow().isoformat()
                    }
                    actions.append(action)
                    logger.info(
                        f"Rule matched: {rule.name} (ID: {rule.id}) "
                        f"for trigger {trigger_type} - action: {rule.action_type}"
                    )

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id} ({rule.name}): {e}")
                continue

        logger.info(f"Evaluated {len(rules)} rules for {trigger_type}: {len(actions)} matched")
        return actions

    async def record_execution(
        self,
        rule_id: int,
        success: bool = True
    ) -> None:
        """
        Record that a rule was executed (for tracking/analytics).

        Updates the rule's execution_count and last_executed_at fields.

        Args:
            rule_id: ID of the executed rule
            success: Whether the execution was successful
        """
        try:
            rule = self.db.query(WorkflowRule).filter(
                WorkflowRule.id == rule_id
            ).first()

            if rule:
                rule.execution_count = (rule.execution_count or 0) + 1
                rule.last_executed_at = datetime.utcnow()
                self.db.commit()
                logger.debug(f"Recorded execution for rule {rule_id}")

        except Exception as e:
            logger.error(f"Failed to record execution for rule {rule_id}: {e}")
            self.db.rollback()


# ========== HELPER FUNCTIONS ==========

def map_close_event_to_trigger(close_event: str) -> Optional[str]:
    """
    Map Close CRM webhook event types to workflow trigger types.

    Args:
        close_event: Close CRM event type (e.g., "opportunity.status_changed")

    Returns:
        Corresponding workflow trigger type, or None if not mapped
    """
    trigger_map = {
        # Opportunity events
        "opportunity.status_changed": TriggerType.STAGE_CHANGE.value,
        "opportunity.won": TriggerType.OPPORTUNITY_WON.value,
        "opportunity.lost": TriggerType.OPPORTUNITY_LOST.value,
        # Lead events
        "lead.created": TriggerType.LEAD_CREATED.value,
        "lead.status_changed": TriggerType.STAGE_CHANGE.value,
    }
    return trigger_map.get(close_event)


def build_context_from_close_event(
    event_type: str,
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build a workflow context dictionary from Close CRM event data.

    Extracts relevant fields from Close webhook payload and normalizes
    them for workflow rule evaluation.

    Args:
        event_type: Close CRM event type
        event_data: Event data from Close webhook

    Returns:
        Context dictionary suitable for rule evaluation
    """
    context = {
        "event_type": event_type,
        "close_event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Common fields
    context["opportunity_id"] = event_data.get("id")
    context["lead_id"] = event_data.get("lead_id")

    # Status/stage fields
    context["stage"] = event_data.get("status_label") or event_data.get("status")
    context["to_stage"] = context["stage"]  # Alias for stage_change rules
    context["from_stage"] = event_data.get("old_status_label") or event_data.get("old_status")

    # Value/amount fields
    context["amount"] = event_data.get("value")
    context["value_period"] = event_data.get("value_period")

    # Contact/organization fields
    context["contact_id"] = event_data.get("contact_id")
    context["organization_id"] = event_data.get("organization_id")

    # Metadata
    context["note"] = event_data.get("note")
    context["confidence"] = event_data.get("confidence")

    return context
