# 04-01 Summary: Workflow Rule Model

## Completed: 2025-12-26

## Objective
Create workflow rule model and schema for defining automation triggers and actions.

## What Was Done

### Task 1: WorkflowRule SQLAlchemy Model
Created `/backend/app/models/workflow.py` with:
- `TriggerType` enum: stage_change, lead_created, opportunity_won, opportunity_lost, days_in_stage, icp_tier_change
- `ActionType` enum: create_task, send_alert, send_slack, trigger_agent, update_field
- `WorkflowRule` model with all fields for automation rules:
  - Core: id, name, description
  - Trigger: trigger_type, trigger_conditions (JSON)
  - Action: action_type, action_config (JSON)
  - Control: is_active, priority
  - Tracking: execution_count, last_executed_at
  - Audit: created_by, created_at, updated_at

Added exports to `/backend/app/models/__init__.py`.

### Task 2: Alembic Migration
Created `/backend/alembic/versions/019_add_workflow_rules_table.py`:
- Creates workflow_rules table with all columns
- Indexes on trigger_type, is_active, priority
- Composite index on (is_active, trigger_type) for common query pattern
- Proper down_revision linking to 018_close_opportunities_pipelines

### Task 3: Workflow Rules API Router
Created `/backend/app/api/workflow_rules.py` with CRUD endpoints:
- `GET /workflow-rules` - List rules with filtering (trigger_type, action_type, is_active)
- `GET /workflow-rules/{id}` - Get single rule
- `POST /workflow-rules` - Create rule with validation
- `PUT /workflow-rules/{id}` - Update rule
- `DELETE /workflow-rules/{id}` - Soft delete (deactivate) or hard delete
- `POST /workflow-rules/{id}/test` - Test rule against sample data

Mounted router in `/backend/app/main.py` at prefix="/api/v1".

## Files Modified
- `backend/app/models/workflow.py` (NEW)
- `backend/app/models/__init__.py` (UPDATED - added exports)
- `backend/alembic/versions/019_add_workflow_rules_table.py` (NEW)
- `backend/app/api/workflow_rules.py` (NEW)
- `backend/app/main.py` (UPDATED - added router)

## Verification
- [x] WorkflowRule model exists with trigger/action enums
- [x] Alembic migration created for workflow_rules table
- [x] API router with CRUD endpoints
- [x] Router mounted in main.py at /api/v1/workflow-rules
- [x] No syntax errors in created files

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/workflow-rules | List all rules (paginated, filterable) |
| GET | /api/v1/workflow-rules/{id} | Get single rule |
| POST | /api/v1/workflow-rules | Create new rule |
| PUT | /api/v1/workflow-rules/{id} | Update rule |
| DELETE | /api/v1/workflow-rules/{id} | Deactivate/delete rule |
| POST | /api/v1/workflow-rules/{id}/test | Test rule with sample data |

## Example Usage

### Create a workflow rule
```bash
curl -X POST http://localhost:8001/api/v1/workflow-rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Won Deal Onboarding",
    "description": "Create onboarding task when deal is won",
    "trigger_type": "stage_change",
    "trigger_conditions": {"to_stage": "won"},
    "action_type": "create_task",
    "action_config": {"task_text": "Schedule onboarding call", "due_days": 1}
  }'
```

### Test a rule
```bash
curl -X POST http://localhost:8001/api/v1/workflow-rules/1/test \
  -H "Content-Type: application/json" \
  -d '{
    "sample_data": {
      "event_type": "stage_change",
      "to_stage": "won",
      "opportunity_id": "oppo_xyz789"
    }
  }'
```

## Next Steps
- 04-02: Rule Engine & Stage Detection (WorkflowRuleEngine, webhook enhancement, polling)
- 04-03: Action Executor (create_task, send_alert, send_slack, default rules)
