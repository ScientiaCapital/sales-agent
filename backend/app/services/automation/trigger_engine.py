"""
TriggerRuleEngine - Evaluates and executes automation rules.

Orchestrates the signal → condition → action pipeline:
1. Receives trigger events (call insights, email replies, signals)
2. Finds matching rules based on conditions
3. Executes actions via ActionExecutor
4. Records execution results
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.trigger_rule import TriggerRule, TriggerExecution, TriggerType

logger = logging.getLogger(__name__)


class TriggerRuleEngine:
    """
    Engine for evaluating and executing trigger rules.

    Usage:
        engine = TriggerRuleEngine(db, action_executor)
        results = await engine.process_event(
            trigger_type=TriggerType.CALL_INSIGHT,
            event_data={"sentiment": "positive", "call_score": 85},
            entity_type="call",
            entity_id="vs_123"
        )
    """

    def __init__(self, db: AsyncSession, action_executor=None):
        """
        Initialize with database session and optional action executor.

        Args:
            db: Async database session
            action_executor: ActionExecutor instance (lazy loaded if None)
        """
        self.db = db
        self._action_executor = action_executor

    @property
    def action_executor(self):
        """Lazy load ActionExecutor to avoid circular imports."""
        if self._action_executor is None:
            from app.services.automation.action_executor import ActionExecutor
            self._action_executor = ActionExecutor(self.db)
        return self._action_executor

    async def process_event(
        self,
        trigger_type: TriggerType,
        event_data: Dict[str, Any],
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> List[TriggerExecution]:
        """
        Process an event against all matching rules.

        Args:
            trigger_type: Type of trigger (call_insight, email_reply, etc.)
            event_data: Dictionary of event attributes for condition matching
            entity_type: Optional entity type (lead, deal, call)
            entity_id: Optional entity ID

        Returns:
            List of TriggerExecution records
        """
        logger.info(f"Processing {trigger_type.value} event for {entity_type}:{entity_id}")

        # Find matching rules
        matching_rules = await self._find_matching_rules(trigger_type, event_data)

        if not matching_rules:
            logger.debug(f"No matching rules for {trigger_type.value} event")
            return []

        logger.info(f"Found {len(matching_rules)} matching rules")

        # Execute each matching rule
        executions = []
        for rule in matching_rules:
            execution = await self._execute_rule(
                rule=rule,
                event_data=event_data,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            executions.append(execution)

        return executions

    async def _find_matching_rules(
        self,
        trigger_type: TriggerType,
        event_data: Dict[str, Any],
    ) -> List[TriggerRule]:
        """Find all active rules that match the event."""
        # Get active rules for this trigger type, ordered by priority
        result = await self.db.execute(
            select(TriggerRule)
            .where(
                and_(
                    TriggerRule.trigger_type == trigger_type.value,
                    TriggerRule.is_active == True,
                )
            )
            .order_by(TriggerRule.priority.desc())
        )
        rules = list(result.scalars().all())

        # Filter to rules that match conditions
        matching = []
        for rule in rules:
            if rule.matches(event_data):
                matching.append(rule)

        return matching

    async def _execute_rule(
        self,
        rule: TriggerRule,
        event_data: Dict[str, Any],
        entity_type: Optional[str],
        entity_id: Optional[str],
    ) -> TriggerExecution:
        """Execute a single rule and record the result."""
        start_time = time.time()
        actions_executed = []
        action_results = []
        success = True
        error_message = None

        try:
            # Execute each action in the rule
            for action in rule.actions:
                action_type = action.get("type")
                action_params = action.get("params", {})

                logger.info(f"Executing action {action_type} for rule {rule.name}")

                try:
                    result = await self.action_executor.execute(
                        action_type=action_type,
                        params=action_params,
                        context={
                            "event_data": event_data,
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "rule_id": str(rule.id),
                            "rule_name": rule.name,
                        }
                    )
                    actions_executed.append(action_type)
                    action_results.append({
                        "action": action_type,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"Action {action_type} failed: {e}")
                    actions_executed.append(action_type)
                    action_results.append({
                        "action": action_type,
                        "success": False,
                        "error": str(e),
                    })
                    # Continue with other actions even if one fails

            # Check if any action failed
            success = all(r.get("success", False) for r in action_results)

        except Exception as e:
            logger.error(f"Rule execution failed for {rule.name}: {e}")
            success = False
            error_message = str(e)

        duration_ms = int((time.time() - start_time) * 1000)

        # Create execution record
        execution = TriggerExecution(
            rule_id=rule.id,
            trigger_data=event_data,
            matched_conditions=rule.conditions,
            entity_type=entity_type,
            entity_id=entity_id,
            actions_executed=actions_executed,
            action_results=action_results,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        self.db.add(execution)

        # Update rule stats
        rule.times_triggered += 1
        rule.last_triggered_at = datetime.utcnow()

        await self.db.commit()

        logger.info(
            f"Rule '{rule.name}' executed: success={success}, "
            f"actions={len(actions_executed)}, duration={duration_ms}ms"
        )

        return execution

    # CRUD operations for rules
    async def create_rule(
        self,
        name: str,
        trigger_type: TriggerType,
        conditions: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        description: Optional[str] = None,
        priority: int = 50,
        is_active: bool = True,
    ) -> TriggerRule:
        """Create a new trigger rule."""
        rule = TriggerRule(
            name=name,
            description=description,
            trigger_type=trigger_type.value,
            conditions=conditions,
            actions=actions,
            priority=priority,
            is_active=is_active,
        )

        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        logger.info(f"Created trigger rule: {name} ({rule.id})")
        return rule

    async def get_rule(self, rule_id: UUID) -> Optional[TriggerRule]:
        """Get a rule by ID."""
        result = await self.db.execute(
            select(TriggerRule).where(TriggerRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        trigger_type: Optional[TriggerType] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
    ) -> List[TriggerRule]:
        """List rules with optional filters."""
        query = select(TriggerRule).order_by(
            TriggerRule.priority.desc(),
            TriggerRule.created_at.desc()
        )

        if trigger_type:
            query = query.where(TriggerRule.trigger_type == trigger_type.value)
        if is_active is not None:
            query = query.where(TriggerRule.is_active == is_active)

        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def update_rule(
        self,
        rule_id: UUID,
        **updates: Any
    ) -> Optional[TriggerRule]:
        """Update a rule's fields."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in updates.items():
            if hasattr(rule, key) and value is not None:
                setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)

        return rule

    async def delete_rule(self, rule_id: UUID) -> bool:
        """Delete a rule."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.commit()
        return True

    async def get_execution_history(
        self,
        rule_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[TriggerExecution]:
        """Get execution history with optional filters."""
        query = select(TriggerExecution).order_by(
            TriggerExecution.executed_at.desc()
        )

        if rule_id:
            query = query.where(TriggerExecution.rule_id == rule_id)
        if entity_type:
            query = query.where(TriggerExecution.entity_type == entity_type)
        if entity_id:
            query = query.where(TriggerExecution.entity_id == entity_id)
        if success is not None:
            query = query.where(TriggerExecution.success == success)

        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def test_rule(
        self,
        rule_id: UUID,
        test_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Test a rule against sample data without executing actions.

        Returns:
            Dict with match result and matched conditions
        """
        rule = await self.get_rule(rule_id)
        if not rule:
            return {"error": "Rule not found"}

        matches = rule.matches(test_data)
        matched_conditions = []

        if matches:
            for condition in rule.conditions:
                matched_conditions.append({
                    "condition": condition,
                    "matched": True,
                })

        return {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "matches": matches,
            "matched_conditions": matched_conditions,
            "actions_would_execute": rule.actions if matches else [],
        }
