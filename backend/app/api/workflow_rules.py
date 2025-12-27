"""
Workflow Rules API Endpoints

CRUD operations for workflow automation rules.
Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

Endpoints:
- GET /workflow-rules - List all rules (with filtering)
- GET /workflow-rules/{id} - Get single rule
- POST /workflow-rules - Create rule
- PUT /workflow-rules/{id} - Update rule
- DELETE /workflow-rules/{id} - Deactivate rule (soft delete)
- POST /workflow-rules/{id}/test - Test rule with sample data
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.logging import setup_logging
from app.models.database import get_db
from app.models.workflow import WorkflowRule, TriggerType, ActionType

logger = setup_logging(__name__)

router = APIRouter(prefix="/workflow-rules", tags=["workflow-automation"])


# ========== Pydantic Models ==========

class WorkflowRuleCreate(BaseModel):
    """Request model for creating a workflow rule."""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    trigger_type: str = Field(
        ...,
        description="Trigger type: stage_change, lead_created, opportunity_won, opportunity_lost, days_in_stage, icp_tier_change"
    )
    trigger_conditions: Dict[str, Any] = Field(
        ...,
        description="JSON conditions for trigger (e.g., {'to_stage': 'won'})"
    )
    action_type: str = Field(
        ...,
        description="Action type: create_task, send_alert, send_slack, trigger_agent, update_field"
    )
    action_config: Dict[str, Any] = Field(
        ...,
        description="JSON config for action (e.g., {'task_text': 'Follow up', 'due_days': 1})"
    )
    is_active: bool = Field(True, description="Whether rule is active")
    priority: int = Field(100, ge=1, le=1000, description="Priority (lower = higher priority)")
    created_by: Optional[str] = Field(None, description="User who created the rule")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Won Deal Onboarding",
                "description": "Create onboarding task when deal is won",
                "trigger_type": "stage_change",
                "trigger_conditions": {"to_stage": "won"},
                "action_type": "create_task",
                "action_config": {"task_text": "Schedule onboarding call", "due_days": 1},
                "is_active": True,
                "priority": 100
            }
        }


class WorkflowRuleUpdate(BaseModel):
    """Request model for updating a workflow rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    action_type: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)


class WorkflowRuleResponse(BaseModel):
    """Response model for a workflow rule."""
    id: int
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_conditions: Dict[str, Any]
    action_type: str
    action_config: Dict[str, Any]
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    execution_count: int
    last_executed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowRuleListResponse(BaseModel):
    """Response model for listing workflow rules."""
    total: int
    page: int
    page_size: int
    rules: List[WorkflowRuleResponse]


class WorkflowRuleTestRequest(BaseModel):
    """Request model for testing a workflow rule."""
    sample_data: Dict[str, Any] = Field(
        ...,
        description="Sample event data to test rule against"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sample_data": {
                    "event_type": "stage_change",
                    "lead_id": "lead_abc123",
                    "from_stage": "proposal",
                    "to_stage": "won",
                    "opportunity_id": "oppo_xyz789"
                }
            }
        }


class WorkflowRuleTestResponse(BaseModel):
    """Response model for rule test results."""
    rule_id: int
    rule_name: str
    would_trigger: bool
    matched_conditions: Dict[str, Any]
    action_preview: Dict[str, Any]


# ========== Helper Functions ==========

def _validate_trigger_type(trigger_type: str) -> None:
    """Validate trigger type against allowed values."""
    valid_types = [t.value for t in TriggerType]
    if trigger_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type: {trigger_type}. Must be one of: {valid_types}"
        )


def _validate_action_type(action_type: str) -> None:
    """Validate action type against allowed values."""
    valid_types = [a.value for a in ActionType]
    if action_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type: {action_type}. Must be one of: {valid_types}"
        )


def _rule_to_response(rule: WorkflowRule) -> WorkflowRuleResponse:
    """Convert SQLAlchemy model to Pydantic response."""
    return WorkflowRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        trigger_type=rule.trigger_type,
        trigger_conditions=rule.trigger_conditions or {},
        action_type=rule.action_type,
        action_config=rule.action_config or {},
        is_active=rule.is_active,
        priority=rule.priority,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        created_by=rule.created_by,
        execution_count=rule.execution_count or 0,
        last_executed_at=rule.last_executed_at
    )


# ========== API Endpoints ==========

@router.get("", response_model=WorkflowRuleListResponse)
async def list_workflow_rules(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    trigger_type: Optional[str] = Query(default=None, description="Filter by trigger type"),
    action_type: Optional[str] = Query(default=None, description="Filter by action type"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    db: Session = Depends(get_db)
):
    """
    List all workflow rules with optional filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (1-100)
        trigger_type: Filter by trigger type
        action_type: Filter by action type
        is_active: Filter by active status

    Returns:
        WorkflowRuleListResponse with paginated rules

    Example:
        GET /api/v1/workflow-rules?is_active=true&trigger_type=stage_change
    """
    try:
        query = db.query(WorkflowRule)

        # Apply filters
        if trigger_type:
            _validate_trigger_type(trigger_type)
            query = query.filter(WorkflowRule.trigger_type == trigger_type)
        if action_type:
            _validate_action_type(action_type)
            query = query.filter(WorkflowRule.action_type == action_type)
        if is_active is not None:
            query = query.filter(WorkflowRule.is_active == is_active)

        # Get total count
        total = query.count()

        # Order by priority (ascending) and created_at (descending)
        query = query.order_by(WorkflowRule.priority.asc(), WorkflowRule.created_at.desc())

        # Paginate
        offset = (page - 1) * page_size
        rules = query.offset(offset).limit(page_size).all()

        return WorkflowRuleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            rules=[_rule_to_response(rule) for rule in rules]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workflow rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list workflow rules: {str(e)}"
        )


@router.get("/{rule_id}", response_model=WorkflowRuleResponse)
async def get_workflow_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single workflow rule by ID.

    Args:
        rule_id: The workflow rule ID

    Returns:
        WorkflowRuleResponse

    Example:
        GET /api/v1/workflow-rules/123
    """
    try:
        rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow rule not found: {rule_id}"
            )
        return _rule_to_response(rule)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workflow rule: {str(e)}"
        )


@router.post("", response_model=WorkflowRuleResponse, status_code=201)
async def create_workflow_rule(
    rule_data: WorkflowRuleCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new workflow rule.

    Args:
        rule_data: The workflow rule data

    Returns:
        Created WorkflowRuleResponse

    Example:
        POST /api/v1/workflow-rules
        {
            "name": "Won Deal Onboarding",
            "trigger_type": "stage_change",
            "trigger_conditions": {"to_stage": "won"},
            "action_type": "create_task",
            "action_config": {"task_text": "Schedule onboarding call", "due_days": 1}
        }
    """
    try:
        # Validate types
        _validate_trigger_type(rule_data.trigger_type)
        _validate_action_type(rule_data.action_type)

        # Create rule
        rule = WorkflowRule(
            name=rule_data.name,
            description=rule_data.description,
            trigger_type=rule_data.trigger_type,
            trigger_conditions=rule_data.trigger_conditions,
            action_type=rule_data.action_type,
            action_config=rule_data.action_config,
            is_active=rule_data.is_active,
            priority=rule_data.priority,
            created_by=rule_data.created_by,
            execution_count=0
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        logger.info(f"Created workflow rule: {rule.id} - {rule.name}")
        return _rule_to_response(rule)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create workflow rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workflow rule: {str(e)}"
        )


@router.put("/{rule_id}", response_model=WorkflowRuleResponse)
async def update_workflow_rule(
    rule_id: int,
    rule_data: WorkflowRuleUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing workflow rule.

    Args:
        rule_id: The workflow rule ID
        rule_data: The fields to update

    Returns:
        Updated WorkflowRuleResponse

    Example:
        PUT /api/v1/workflow-rules/123
        {"is_active": false}
    """
    try:
        rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow rule not found: {rule_id}"
            )

        # Update fields that are provided
        update_data = rule_data.model_dump(exclude_unset=True)

        # Validate types if being updated
        if "trigger_type" in update_data:
            _validate_trigger_type(update_data["trigger_type"])
        if "action_type" in update_data:
            _validate_action_type(update_data["action_type"])

        for field, value in update_data.items():
            setattr(rule, field, value)

        db.commit()
        db.refresh(rule)

        logger.info(f"Updated workflow rule: {rule.id} - {rule.name}")
        return _rule_to_response(rule)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update workflow rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow rule: {str(e)}"
        )


@router.delete("/{rule_id}")
async def delete_workflow_rule(
    rule_id: int,
    hard_delete: bool = Query(default=False, description="Permanently delete instead of deactivate"),
    db: Session = Depends(get_db)
):
    """
    Delete (deactivate) a workflow rule.

    By default, this performs a soft delete by setting is_active=False.
    Use hard_delete=true to permanently remove the rule.

    Args:
        rule_id: The workflow rule ID
        hard_delete: If true, permanently delete the rule

    Returns:
        Deletion confirmation

    Example:
        DELETE /api/v1/workflow-rules/123
        DELETE /api/v1/workflow-rules/123?hard_delete=true
    """
    try:
        rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow rule not found: {rule_id}"
            )

        rule_name = rule.name

        if hard_delete:
            db.delete(rule)
            db.commit()
            logger.info(f"Hard deleted workflow rule: {rule_id} - {rule_name}")
            return {
                "status": "deleted",
                "rule_id": rule_id,
                "rule_name": rule_name,
                "delete_type": "hard"
            }
        else:
            rule.is_active = False
            db.commit()
            logger.info(f"Soft deleted (deactivated) workflow rule: {rule_id} - {rule_name}")
            return {
                "status": "deactivated",
                "rule_id": rule_id,
                "rule_name": rule_name,
                "delete_type": "soft"
            }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete workflow rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workflow rule: {str(e)}"
        )


@router.post("/{rule_id}/test", response_model=WorkflowRuleTestResponse)
async def test_workflow_rule(
    rule_id: int,
    test_request: WorkflowRuleTestRequest,
    db: Session = Depends(get_db)
):
    """
    Test a workflow rule with sample data.

    This endpoint evaluates whether the rule would trigger
    given the sample event data, without actually executing any actions.

    Args:
        rule_id: The workflow rule ID
        test_request: Sample event data to test against

    Returns:
        WorkflowRuleTestResponse with trigger evaluation

    Example:
        POST /api/v1/workflow-rules/123/test
        {
            "sample_data": {
                "event_type": "stage_change",
                "to_stage": "won",
                "opportunity_id": "oppo_xyz789"
            }
        }
    """
    try:
        rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow rule not found: {rule_id}"
            )

        sample_data = test_request.sample_data
        trigger_conditions = rule.trigger_conditions or {}

        # Simple condition matching logic
        matched_conditions = {}
        would_trigger = True

        for key, expected_value in trigger_conditions.items():
            actual_value = sample_data.get(key)
            if actual_value == expected_value:
                matched_conditions[key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                    "match": True
                }
            else:
                matched_conditions[key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                    "match": False
                }
                would_trigger = False

        # Build action preview
        action_preview = {
            "action_type": rule.action_type,
            "action_config": rule.action_config,
            "would_execute": would_trigger and rule.is_active,
            "rule_is_active": rule.is_active
        }

        logger.info(
            f"Tested workflow rule {rule_id}: would_trigger={would_trigger}, "
            f"is_active={rule.is_active}"
        )

        return WorkflowRuleTestResponse(
            rule_id=rule.id,
            rule_name=rule.name,
            would_trigger=would_trigger,
            matched_conditions=matched_conditions,
            action_preview=action_preview
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test workflow rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test workflow rule: {str(e)}"
        )


# ========== Default Rules Management ==========

@router.post("/seed-defaults")
async def seed_default_workflow_rules(
    db: Session = Depends(get_db)
):
    """
    Seed default workflow rules into the database.

    This endpoint creates the pre-configured workflow rules that ship
    with the system. It only creates rules that don't already exist,
    so it's safe to call multiple times.

    Default rules include:
    - Won Deal Celebration (send_slack)
    - Lost Deal Review Task (create_task)
    - Platinum Lead Meeting Alert (send_alert)
    - Stale Proposal Alert (send_alert)
    - New Lead Outreach Task (create_task)
    - High-Value Stage Change (send_alert)
    - ICP Tier Upgrade Notification (send_slack)

    Returns:
        Dict with seeding results:
        - created: Number of rules created
        - skipped: Number of rules that already existed
        - rules_created: List of created rule names

    Example:
        POST /api/v1/workflow-rules/seed-defaults
    """
    try:
        from app.services.workflow.default_rules import seed_default_rules

        result = await seed_default_rules(db)

        logger.info(
            f"Seeded default rules: {result['created']} created, "
            f"{result['skipped']} already existed"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to seed default workflow rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to seed default workflow rules: {str(e)}"
        )


@router.get("/defaults/info")
async def get_default_rules_info():
    """
    Get information about available default workflow rules.

    Returns the list of default rules that can be seeded,
    without actually creating them.

    Returns:
        Dict with default rules information

    Example:
        GET /api/v1/workflow-rules/defaults/info
    """
    try:
        from app.services.workflow.default_rules import DEFAULT_RULES, get_default_rule_names

        return {
            "total_default_rules": len(DEFAULT_RULES),
            "rule_names": get_default_rule_names(),
            "rules": [
                {
                    "name": rule["name"],
                    "description": rule.get("description"),
                    "trigger_type": rule["trigger_type"],
                    "action_type": rule["action_type"],
                    "priority": rule.get("priority", 100)
                }
                for rule in DEFAULT_RULES
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get default rules info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get default rules info: {str(e)}"
        )


# ========== Exports ==========

__all__ = [
    "router",
    "WorkflowRuleCreate",
    "WorkflowRuleUpdate",
    "WorkflowRuleResponse",
    "WorkflowRuleListResponse",
    "WorkflowRuleTestRequest",
    "WorkflowRuleTestResponse",
]
