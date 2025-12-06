"""
Agent Control API Endpoints

Provides REST API for controlling and monitoring autonomous agents in Tim's BDR workflow.

Endpoints:
- POST /api/v1/agents/{name}/start - Trigger agent immediately
- POST /api/v1/agents/{name}/stop - Stop running agent
- GET /api/v1/agents/status - All agent statuses
- GET /api/v1/agents/{name}/history - Recent runs for agent
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime

from app.core.logging import setup_logging
from app.auth.dependencies import get_current_user
from app.celery_app import celery_app
from app.services.agent_tracker import get_agent_tracker
from app.tasks.agent_tasks import (
    run_lead_scout_task,
    generate_morning_report_task,
    run_sales_intel_batch_task,
    run_growth_campaigns_task,
    run_bdr_batch_task,
)
from app.tasks.icp_tasks import run_icp_checker_task
from app.tasks.prediction_tasks import run_prediction_market_task, run_morning_briefing_task

logger = setup_logging(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ========== Pydantic Models ==========

class AgentStatus(BaseModel):
    """Agent status information."""
    name: str
    status: Literal["running", "idle", "error", "disabled"]
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    runs_today: int = 0
    errors_today: int = 0
    current_task_id: Optional[str] = None


class AgentControlRequest(BaseModel):
    """Request schema for agent control actions."""
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional agent-specific configuration overrides"
    )


class AgentControlResponse(BaseModel):
    """Response schema for agent control actions."""
    status: str
    agent_name: str
    task_id: Optional[str] = None
    message: str


class AgentRun(BaseModel):
    """Single agent run record."""
    task_id: str
    agent_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentHistoryResponse(BaseModel):
    """Response with agent execution history."""
    agent_name: str
    total_runs: int
    runs: List[AgentRun]


# ========== Agent Task Mapping ==========

AGENT_TASKS = {
    "lead_scout": run_lead_scout_task,
    "morning_report": generate_morning_report_task,
    "sales_intel": run_sales_intel_batch_task,
    "growth_campaigns": run_growth_campaigns_task,
    "bdr_outreach": run_bdr_batch_task,
    "icp_checker": run_icp_checker_task,
    "prediction_market": run_prediction_market_task,
    "morning_briefing": run_morning_briefing_task,
}

AGENT_DISPLAY_NAMES = {
    "lead_scout": "Lead Scout",
    "morning_report": "Morning Report",
    "sales_intel": "Sales Intel",
    "growth_campaigns": "Growth Campaigns",
    "bdr_outreach": "BDR Outreach",
    "icp_checker": "ICP Checker",
    "prediction_market": "Prediction Market",
    "morning_briefing": "Morning Briefing",
}

AGENT_DEFAULT_ARGS = {
    "lead_scout": (10, True, None),  # limit, require_domain, icp_tier
    "morning_report": (24, 10, True),  # hours_back, top_n, save_to_file
    "sales_intel": (10,),  # limit
    "growth_campaigns": ("book_meeting", 5),  # goal, max_leads
    "bdr_outreach": (3,),  # limit
    "icp_checker": (100,),  # limit
    "prediction_market": (1000,),  # limit
    "morning_briefing": (10,),  # top_n
}


# ========== Helper Functions ==========

def get_agent_schedule_info(agent_name: str) -> Optional[Dict[str, Any]]:
    """
    Get schedule information for an agent from Celery Beat.

    Args:
        agent_name: Name of the agent

    Returns:
        Schedule info dict or None if not scheduled
    """
    # Map agent names to Celery Beat schedule keys
    schedule_keys = {
        "lead_scout": "lead-scout-every-30-min",
        "morning_report": "morning-report-9am-est",
        "sales_intel": "sales-intel-hourly",
        "growth_campaigns": "growth-campaigns-daily",
        "bdr_outreach": "bdr-outreach-hourly",
        "icp_checker": "icp-checker-every-15-min",
        "prediction_market": "prediction-market-every-5-min",
        "morning_briefing": "morning-briefing-7am-est",
    }

    schedule_key = schedule_keys.get(agent_name)
    if not schedule_key:
        return None

    # Get schedule from Celery Beat config
    beat_schedule = celery_app.conf.beat_schedule
    schedule_entry = beat_schedule.get(schedule_key)

    if not schedule_entry:
        return None

    return {
        "schedule_key": schedule_key,
        "schedule": schedule_entry.get("schedule"),
        "args": schedule_entry.get("args"),
        "queue": schedule_entry.get("options", {}).get("queue", "default"),
    }


def get_running_tasks(agent_name: str) -> List[str]:
    """
    Get currently running tasks for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        List of running task IDs
    """
    # Query Celery for active tasks
    # This requires celery inspect() which needs a running worker
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}

        # Find tasks matching this agent
        task_name = AGENT_TASKS[agent_name].name
        running_ids = []

        for worker, tasks in active_tasks.items():
            for task in tasks:
                if task.get("name") == task_name:
                    running_ids.append(task.get("id"))

        return running_ids
    except Exception as e:
        logger.warning(f"Failed to inspect Celery tasks: {e}")
        return []


# ========== API Endpoints ==========

@router.post("/{agent_name}/start", response_model=AgentControlResponse)
async def start_agent(
    agent_name: str,
    request: AgentControlRequest = AgentControlRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger an agent to run immediately.

    This endpoint starts an agent outside of its scheduled run time.
    Useful for manual testing or ad-hoc runs.

    Args:
        agent_name: Name of agent to start
        request: Optional configuration overrides
        current_user: Authenticated user (required)

    Returns:
        AgentControlResponse with task_id

    Example:
        ```bash
        curl -X POST http://localhost:8001/api/v1/agents/lead_scout/start \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{"config": {"limit": 5}}'
        ```
    """
    if agent_name not in AGENT_TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Valid agents: {', '.join(AGENT_TASKS.keys())}"
        )

    try:
        # Get agent task and default args
        task = AGENT_TASKS[agent_name]
        default_args = AGENT_DEFAULT_ARGS.get(agent_name, ())

        # Apply config overrides if provided
        args = default_args
        if request.config:
            # For now, use default args (future: merge config overrides)
            logger.info(f"Config overrides provided for {agent_name}: {request.config}")

        # Trigger the task
        result = task.apply_async(args=args)

        logger.info(
            f"Agent '{agent_name}' started by {current_user.get('email')} - task_id: {result.id}"
        )

        return AgentControlResponse(
            status="started",
            agent_name=agent_name,
            task_id=result.id,
            message=f"{AGENT_DISPLAY_NAMES[agent_name]} started successfully"
        )

    except Exception as e:
        logger.error(f"Failed to start agent '{agent_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start agent: {str(e)}"
        )


@router.post("/{agent_name}/stop", response_model=AgentControlResponse)
async def stop_agent(
    agent_name: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Stop a running agent.

    Sends a revoke signal to all running tasks for this agent.

    Args:
        agent_name: Name of agent to stop
        current_user: Authenticated user (required)

    Returns:
        AgentControlResponse with revoked task count

    Example:
        ```bash
        curl -X POST http://localhost:8001/api/v1/agents/lead_scout/stop \\
          -H "Authorization: Bearer <token>"
        ```
    """
    if agent_name not in AGENT_TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found"
        )

    try:
        # Get running tasks for this agent
        running_task_ids = get_running_tasks(agent_name)

        if not running_task_ids:
            return AgentControlResponse(
                status="already_stopped",
                agent_name=agent_name,
                message=f"No running tasks found for {AGENT_DISPLAY_NAMES[agent_name]}"
            )

        # Revoke all running tasks
        for task_id in running_task_ids:
            celery_app.control.revoke(task_id, terminate=True)

        logger.info(
            f"Agent '{agent_name}' stopped by {current_user.get('email')} - "
            f"revoked {len(running_task_ids)} tasks"
        )

        return AgentControlResponse(
            status="stopped",
            agent_name=agent_name,
            message=f"Stopped {len(running_task_ids)} running task(s) for {AGENT_DISPLAY_NAMES[agent_name]}"
        )

    except Exception as e:
        logger.error(f"Failed to stop agent '{agent_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop agent: {str(e)}"
        )


@router.get("/status", response_model=List[AgentStatus])
async def get_all_agent_statuses(
    current_user: dict = Depends(get_current_user),
):
    """
    Get status of all agents.

    Returns current status, last run time, next scheduled run, and task counts.
    Status is tracked in Redis for real-time accuracy.

    Args:
        current_user: Authenticated user (required)

    Returns:
        List of AgentStatus objects

    Example:
        ```bash
        curl http://localhost:8001/api/v1/agents/status \\
          -H "Authorization: Bearer <token>"
        ```
    """
    statuses = []
    tracker = get_agent_tracker()

    for agent_name in AGENT_TASKS.keys():
        try:
            # Get tracked status from Redis
            tracked = await tracker.get_agent_status(agent_name)

            # Get running tasks from Celery (live check)
            running_tasks = get_running_tasks(agent_name)

            # Get schedule info
            schedule_info = get_agent_schedule_info(agent_name)

            # Determine status (Celery live check takes precedence)
            if running_tasks:
                status = "running"
                current_task_id = running_tasks[0]
            elif tracked.get("status") == "running":
                # Redis says running but Celery doesn't - might have crashed
                status = "idle"
                current_task_id = None
            elif schedule_info:
                status = tracked.get("status", "idle")
                current_task_id = tracked.get("current_task_id")
            else:
                status = "disabled"
                current_task_id = None

            # Parse last run time from tracked data
            last_run = None
            if tracked.get("last_run_at"):
                try:
                    last_run = datetime.fromisoformat(tracked["last_run_at"].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

            # TODO: Calculate next_run from schedule (requires schedule parsing)
            next_run = None

            statuses.append(AgentStatus(
                name=agent_name,
                status=status,
                last_run=last_run,
                next_run=next_run,
                runs_today=tracked.get("runs_today", 0),
                errors_today=tracked.get("errors_today", 0),
                current_task_id=current_task_id,
            ))

        except Exception as e:
            logger.error(f"Failed to get status for agent '{agent_name}': {e}")
            statuses.append(AgentStatus(
                name=agent_name,
                status="error",
            ))

    return statuses


@router.get("/{agent_name}/history", response_model=AgentHistoryResponse)
async def get_agent_history(
    agent_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    Get execution history for an agent.

    Returns recent task runs with results and errors from Redis tracking.

    Args:
        agent_name: Name of agent
        limit: Maximum number of runs to return (1-100)
        current_user: Authenticated user (required)

    Returns:
        AgentHistoryResponse with run history

    Example:
        ```bash
        curl http://localhost:8001/api/v1/agents/lead_scout/history?limit=10 \\
          -H "Authorization: Bearer <token>"
        ```
    """
    if agent_name not in AGENT_TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found"
        )

    try:
        tracker = get_agent_tracker()
        history = await tracker.get_agent_history(agent_name, limit=limit)

        # Convert to AgentRun objects
        runs = []
        for record in history:
            try:
                started_at = datetime.fromisoformat(record["started_at"].replace('Z', '+00:00'))
                completed_at = None
                if record.get("completed_at"):
                    completed_at = datetime.fromisoformat(record["completed_at"].replace('Z', '+00:00'))

                runs.append(AgentRun(
                    task_id=record["task_id"],
                    agent_name=record["agent_name"],
                    status=record.get("status", "unknown"),
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=record.get("duration_ms"),
                    result=record.get("result"),
                    error=record.get("error")
                ))
            except Exception as e:
                logger.warning(f"Failed to parse history record: {e}")
                continue

        return AgentHistoryResponse(
            agent_name=agent_name,
            total_runs=len(runs),
            runs=runs
        )

    except Exception as e:
        logger.error(f"Failed to get history for agent '{agent_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent history: {str(e)}"
        )


# ========== Exports ==========

__all__ = [
    "router",
    "AgentStatus",
    "AgentControlRequest",
    "AgentControlResponse",
    "AgentRun",
    "AgentHistoryResponse",
]
