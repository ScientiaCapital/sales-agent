# 04-02 Summary: Rule Engine & Stage Detection

## Completed: 2025-12-26

## Objective
Create workflow rule engine for evaluating triggers and detecting stage changes.

## What Was Done

### Task 1: WorkflowRuleEngine Service
Created `/backend/app/services/workflow/rule_engine.py` with:
- `WorkflowRuleEngine` class for evaluating workflow rules against events
- `get_active_rules()` - Fetches active rules for a trigger type, ordered by priority
- `evaluate_conditions()` - Checks if rule conditions match the context
- `evaluate_event()` - Main entry point for rule evaluation
- `record_execution()` - Records rule execution for analytics
- Support for multiple condition formats:
  - Simple equality: `{"stage": "won"}`
  - List matching: `{"stage": ["won", "closed"]}`
  - Operator-based: `{"amount": {"gt": 10000}}`
- Comparison operators: eq, ne, gt, gte, lt, lte, in, contains
- Helper functions:
  - `map_close_event_to_trigger()` - Maps Close webhook events to trigger types
  - `build_context_from_close_event()` - Builds context from Close event data

Added `__init__.py` to `/backend/app/services/workflow/` with exports.

### Task 2: Enhanced Close Webhook for Rule Evaluation
Updated `/backend/app/api/webhooks/close.py`:
- Added imports for WorkflowRuleEngine and helper functions
- Added `evaluate_workflow_rules_for_event()` function that:
  - Maps Close event type to workflow trigger type
  - Builds context from event data
  - Queues Celery task for rule evaluation
- Modified `process_webhook_event()` to call `evaluate_workflow_rules_for_event()`
- Event mapping:
  - `opportunity.status_changed` -> `stage_change`
  - `opportunity.won` -> `opportunity_won`
  - `opportunity.lost` -> `opportunity_lost`
  - `lead.created` -> `lead_created`
  - `lead.status_changed` -> `stage_change`

### Task 3: Stage Change Polling Task
Created `/backend/app/tasks/workflow_tasks.py` with two Celery tasks:

1. `evaluate_workflow_rules` task:
   - Evaluates rules for a trigger type and context
   - Queues matched actions for execution
   - Records execution in database
   - Returns evaluation results

2. `poll_stage_changes` task:
   - Polls for opportunity stage changes since last check (fallback to webhook)
   - Uses Redis for last poll timestamp and distributed locking
   - Queries `crm_opportunities` for updated opportunities
   - Compares current stage vs previous stage (tracked in `raw_data`)
   - Triggers workflow rules for detected changes
   - Handles won/lost specific triggers

Updated `/backend/app/celery_app.py`:
- Added `app.tasks.workflow_tasks` to include list
- Added task routing to `workflows` queue
- Added Celery Beat schedule for `poll_stage_changes` (every 15 minutes at :07, :22, :37, :52)
- Added tasks to TRACKED_AGENTS for BDR Cockpit tracking

## Files Modified
- `backend/app/services/workflow/rule_engine.py` (existing - already created)
- `backend/app/services/workflow/__init__.py` (existing - already created)
- `backend/app/api/webhooks/close.py` (UPDATED - added rule evaluation)
- `backend/app/tasks/workflow_tasks.py` (existing - already created)
- `backend/app/celery_app.py` (UPDATED - added task config and schedule)

## Verification
- [x] WorkflowRuleEngine evaluates conditions correctly (supports multiple formats)
- [x] Close webhook queues rule evaluation for mapped events
- [x] Polling task runs on schedule (every 15 minutes)
- [x] No import errors

## API Endpoints (Unchanged from 04-01)
The workflow rules API endpoints remain at `/api/v1/workflow-rules`.

## Celery Beat Schedule

| Task | Schedule | Queue | Description |
|------|----------|-------|-------------|
| poll_stage_changes | */15 min (:07, :22, :37, :52) | workflows | Fallback stage change detection |

## Event-to-Trigger Mapping

| Close Event | Trigger Type |
|-------------|--------------|
| opportunity.status_changed | stage_change |
| opportunity.won | opportunity_won |
| opportunity.lost | opportunity_lost |
| lead.created | lead_created |
| lead.status_changed | stage_change |

## Example Flow

1. Close CRM sends webhook for `opportunity.won` event
2. Webhook handler calls `evaluate_workflow_rules_for_event()`
3. Maps event to `opportunity_won` trigger type
4. Builds context from event data (opportunity_id, lead_id, stage, amount, etc.)
5. Queues `evaluate_workflow_rules` Celery task
6. Task evaluates active rules for trigger type
7. For matched rules, logs action and records execution
8. (Plan 04-03 will implement actual action execution)

## Next Steps
- 04-03: Action Executor (create_task, send_alert, send_slack, default rules)
