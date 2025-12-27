"""
Trigger Rules API endpoints.

Provides REST endpoints for:
- CRUD operations on trigger rules
- Viewing execution history
- Testing rules against sample data
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.models.trigger_rule import TriggerType, ActionType
from app.services.automation import TriggerRuleEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triggers", tags=["automation"])


# Request/Response Models
class ConditionSchema(BaseModel):
    """Rule condition definition."""
    field: str = Field(..., description="Event field to check (supports dot notation)")
    operator: str = Field(..., description="Comparison operator (eq, neq, gt, lt, gte, lte, contains, in)")
    value: Any = Field(..., description="Value to compare against")


class ActionSchema(BaseModel):
    """Rule action definition."""
    type: str = Field(..., description="Action type (pause_sequence, notify_slack, etc.)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class CreateRuleRequest(BaseModel):
    """Request to create a trigger rule."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: str = Field(..., description="call_insight, email_reply, signal, lead_update, deal_update")
    conditions: List[ConditionSchema] = Field(..., min_length=1)
    actions: List[ActionSchema] = Field(..., min_length=1)
    priority: int = Field(default=50, ge=0, le=100)
    is_active: bool = True


class UpdateRuleRequest(BaseModel):
    """Request to update a trigger rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    conditions: Optional[List[ConditionSchema]] = None
    actions: Optional[List[ActionSchema]] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    """Trigger rule response."""
    id: str
    name: str
    description: Optional[str]
    trigger_type: str
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    priority: int
    is_active: bool
    times_triggered: int
    last_triggered_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class ExecutionResponse(BaseModel):
    """Trigger execution history response."""
    id: str
    rule_id: str
    trigger_data: Optional[Dict[str, Any]]
    matched_conditions: Optional[List[Dict[str, Any]]]
    entity_type: Optional[str]
    entity_id: Optional[str]
    actions_executed: Optional[List[str]]
    action_results: Optional[List[Dict[str, Any]]]
    success: bool
    error_message: Optional[str]
    executed_at: Optional[str]
    duration_ms: Optional[int]


class TestRuleRequest(BaseModel):
    """Request to test a rule against sample data."""
    test_data: Dict[str, Any] = Field(..., description="Sample event data to test against")


class TestRuleResponse(BaseModel):
    """Response from rule test."""
    rule_id: str
    rule_name: str
    matches: bool
    matched_conditions: List[Dict[str, Any]]
    actions_would_execute: List[Dict[str, Any]]


class RuleListResponse(BaseModel):
    """List of rules response."""
    rules: List[RuleResponse]
    total: int


class ExecutionListResponse(BaseModel):
    """List of executions response."""
    executions: List[ExecutionResponse]
    total: int


# Endpoints
@router.post("/rules", response_model=RuleResponse, status_code=201)
async def create_rule(
    request: CreateRuleRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new trigger rule.

    Example:
    ```json
    {
        "name": "Positive Call Alert",
        "trigger_type": "call_insight",
        "conditions": [
            {"field": "sentiment_label", "operator": "eq", "value": "positive"},
            {"field": "call_score", "operator": "gte", "value": 80}
        ],
        "actions": [
            {"type": "notify_slack", "params": {"message": "Great call! Score: {{call_score}}"}}
        ]
    }
    ```
    """
    try:
        trigger_type = TriggerType(request.trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type. Must be one of: {[t.value for t in TriggerType]}"
        )

    # Validate action types
    for action in request.actions:
        try:
            ActionType(action.type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action type '{action.type}'. Must be one of: {[a.value for a in ActionType]}"
            )

    engine = TriggerRuleEngine(db)
    rule = await engine.create_rule(
        name=request.name,
        description=request.description,
        trigger_type=trigger_type,
        conditions=[c.model_dump() for c in request.conditions],
        actions=[a.model_dump() for a in request.actions],
        priority=request.priority,
        is_active=request.is_active,
    )

    return RuleResponse(**rule.to_dict())


@router.get("/rules", response_model=RuleListResponse)
async def list_rules(
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    """List trigger rules with optional filters."""
    engine = TriggerRuleEngine(db)

    tt = None
    if trigger_type:
        try:
            tt = TriggerType(trigger_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid trigger_type: {trigger_type}")

    rules = await engine.list_rules(trigger_type=tt, is_active=is_active, limit=limit)

    return RuleListResponse(
        rules=[RuleResponse(**r.to_dict()) for r in rules],
        total=len(rules),
    )


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific trigger rule by ID."""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    engine = TriggerRuleEngine(db)
    rule = await engine.get_rule(rule_uuid)

    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return RuleResponse(**rule.to_dict())


@router.put("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    request: UpdateRuleRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Update an existing trigger rule."""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    # Validate action types if provided
    if request.actions:
        for action in request.actions:
            try:
                ActionType(action.type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid action type '{action.type}'"
                )

    engine = TriggerRuleEngine(db)

    updates = request.model_dump(exclude_unset=True)
    if "conditions" in updates:
        updates["conditions"] = [c.model_dump() if hasattr(c, 'model_dump') else c for c in updates["conditions"]]
    if "actions" in updates:
        updates["actions"] = [a.model_dump() if hasattr(a, 'model_dump') else a for a in updates["actions"]]

    rule = await engine.update_rule(rule_uuid, **updates)

    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return RuleResponse(**rule.to_dict())


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a trigger rule."""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    engine = TriggerRuleEngine(db)
    deleted = await engine.delete_rule(rule_uuid)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")


@router.post("/rules/{rule_id}/test", response_model=TestRuleResponse)
async def test_rule(
    rule_id: str,
    request: TestRuleRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test a rule against sample data without executing actions.

    Returns whether the rule would match and what actions would execute.
    """
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    engine = TriggerRuleEngine(db)
    result = await engine.test_rule(rule_uuid, request.test_data)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return TestRuleResponse(**result)


@router.get("/history", response_model=ExecutionListResponse)
async def get_execution_history(
    rule_id: Optional[str] = Query(None, description="Filter by rule ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
):
    """Get trigger execution history with optional filters."""
    engine = TriggerRuleEngine(db)

    rule_uuid = None
    if rule_id:
        try:
            rule_uuid = UUID(rule_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid rule ID format")

    executions = await engine.get_execution_history(
        rule_id=rule_uuid,
        entity_type=entity_type,
        entity_id=entity_id,
        success=success,
        limit=limit,
    )

    return ExecutionListResponse(
        executions=[ExecutionResponse(**e.to_dict()) for e in executions],
        total=len(executions),
    )


@router.get("/action-types")
async def list_action_types():
    """List all supported action types with descriptions."""
    return {
        "action_types": [
            {"type": ActionType.PAUSE_SEQUENCE.value, "description": "Pause email sequence for a lead"},
            {"type": ActionType.RESUME_SEQUENCE.value, "description": "Resume paused email sequence"},
            {"type": ActionType.NOTIFY_SLACK.value, "description": "Send Slack notification"},
            {"type": ActionType.UPDATE_LEAD_STAGE.value, "description": "Update lead pipeline stage"},
            {"type": ActionType.CREATE_TASK.value, "description": "Create follow-up task"},
            {"type": ActionType.ESCALATE_TO_REP.value, "description": "Escalate to human sales rep"},
            {"type": ActionType.SEND_EMAIL.value, "description": "Send email via template"},
            {"type": ActionType.UPDATE_CRM.value, "description": "Update CRM fields"},
            {"type": ActionType.WEBHOOK.value, "description": "Call external webhook"},
        ]
    }


@router.get("/trigger-types")
async def list_trigger_types():
    """List all supported trigger types with descriptions."""
    return {
        "trigger_types": [
            {"type": TriggerType.CALL_INSIGHT.value, "description": "Triggered when call analysis completes"},
            {"type": TriggerType.EMAIL_REPLY.value, "description": "Triggered on email reply classification"},
            {"type": TriggerType.SIGNAL.value, "description": "Triggered on lead/account signals"},
            {"type": TriggerType.LEAD_UPDATE.value, "description": "Triggered on lead status changes"},
            {"type": TriggerType.DEAL_UPDATE.value, "description": "Triggered on deal stage changes"},
        ]
    }
