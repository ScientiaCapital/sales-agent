"""
Dashboard Agents Module
========================
Agent health monitoring and status endpoints.

Endpoints:
- GET /agents - Agent health metrics
- GET /elite-team - Elite Squad status
- GET /revival-candidates - Lost deals ready for re-engagement

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from .shared import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class AgentMetric(BaseModel):
    """Agent health metric for dashboard."""
    agent_type: str
    display_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_latency_ms: float
    target_latency_ms: float
    avg_cost_usd: float
    success_rate: float
    status: str  # "healthy" | "degraded" | "failing" | "idle"
    last_execution_at: Optional[str] = None


class EliteAgentStatusModel(BaseModel):
    """Status for a single Elite Squad agent."""
    name: str
    icon: str
    status: str
    last_run: Optional[str] = None
    current_task: Optional[str] = None
    signals_detected: Optional[int] = None
    scraped_today: Optional[int] = None
    queue_size: Optional[int] = None
    unicorns_found: Optional[int] = None
    duplicates_blocked: Optional[int] = None
    routed_to_bdr: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class EliteTeamResponse(BaseModel):
    """Elite Squad status response."""
    signal_scout: EliteAgentStatusModel
    deep_hunter: EliteAgentStatusModel
    intake_commander: EliteAgentStatusModel
    summary: Dict[str, Any]
    updated_at: str


class RevivalCandidate(BaseModel):
    """A lost deal that's ready for re-engagement."""
    close_opportunity_id: str
    company_id: Optional[str] = None
    lead_name: str
    deal_value: float
    close_reason: Optional[str] = None
    date_lost: Optional[str] = None
    days_since_lost: Optional[int] = None
    revival_priority: str  # high, medium, low
    revival_score: int  # 0-100
    last_contact_date: Optional[str] = None
    competitor_lost_to: Optional[str] = None
    notes: Optional[str] = None


class RevivalCandidatesResponse(BaseModel):
    """Response for revival candidates endpoint."""
    candidates: List[RevivalCandidate]
    total_count: int
    total_value: float
    high_priority_count: int
    summary: Dict[str, Any]


# ============================================================================
# Constants
# ============================================================================

AGENT_DEFINITIONS = [
    {"type": "lead_scout", "name": "LeadScoutAgent", "schedule": "Every 30 min", "target_ms": 30000},
    {"type": "icp_checker", "name": "ICPCheckerAgent", "schedule": "Every 15 min", "target_ms": 15000},
    {"type": "prediction_agent", "name": "PredictionAgent", "schedule": "Every 5 min", "target_ms": 10000},
    {"type": "morning_briefing", "name": "MorningBriefingAgent", "schedule": "7 AM EST", "target_ms": 60000},
    {"type": "sales_intel", "name": "SalesIntelAgent", "schedule": "Hourly :30", "target_ms": 45000},
    {"type": "bdr_outreach", "name": "BDRAgent", "schedule": "Hourly :00", "target_ms": 30000},
]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/agents", response_model=List[AgentMetric])
async def get_agents():
    """Get agent health metrics for dashboard (no auth required)."""
    try:
        from app.services.agent_tracker import get_agent_tracker
        tracker = get_agent_tracker()

        metrics = []
        for agent_def in AGENT_DEFINITIONS:
            agent_type = agent_def["type"]

            # Get stats from tracker
            stats = tracker.get_agent_stats(agent_type)

            total_exec = stats.get("total_runs", 0)
            successful = stats.get("successful_runs", 0)
            failed = stats.get("failed_runs", 0)
            avg_latency = stats.get("avg_duration_ms", 0.0)
            success_rate = successful / total_exec if total_exec > 0 else 1.0

            # Determine status
            if total_exec == 0:
                status = "idle"
            elif success_rate < 0.8:
                status = "failing"
            elif success_rate < 0.95 or avg_latency > agent_def["target_ms"] * 1.5:
                status = "degraded"
            else:
                status = "healthy"

            metrics.append(AgentMetric(
                agent_type=agent_type,
                display_name=agent_def["name"],
                total_executions=total_exec,
                successful_executions=successful,
                failed_executions=failed,
                avg_latency_ms=avg_latency,
                target_latency_ms=float(agent_def["target_ms"]),
                avg_cost_usd=stats.get("total_cost", 0.0) / max(total_exec, 1),
                success_rate=success_rate,
                status=status,
                last_execution_at=stats.get("last_run")
            ))

        return metrics

    except Exception as e:
        logger.error(f"Error fetching agent metrics: {e}")
        # Return mock data on error
        return [
            AgentMetric(
                agent_type=a["type"],
                display_name=a["name"],
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                avg_latency_ms=0.0,
                target_latency_ms=float(a["target_ms"]),
                avg_cost_usd=0.0,
                success_rate=1.0,
                status="idle",
                last_execution_at=None
            )
            for a in AGENT_DEFINITIONS
        ]


@router.get("/elite-team", response_model=EliteTeamResponse)
async def get_elite_team_status():
    """
    Get Elite Squad status for dashboard.
    """
    try:
        from app.services.langgraph.agents.elite_team.elite_team_hub import get_elite_hub

        hub = get_elite_hub()
        dashboard_data = hub.get_dashboard_status()

        # Transform to response model
        return EliteTeamResponse(
            signal_scout=EliteAgentStatusModel(**dashboard_data["signal_scout"]),
            deep_hunter=EliteAgentStatusModel(**dashboard_data["deep_hunter"]),
            intake_commander=EliteAgentStatusModel(**dashboard_data["intake_commander"]),
            summary=dashboard_data["summary"],
            updated_at=dashboard_data["updated_at"]
        )

    except Exception as e:
        logger.error(f"Error fetching elite team status: {e}", exc_info=True)
        # Return idle state on error
        now = datetime.now(timezone.utc)
        return EliteTeamResponse(
            signal_scout=EliteAgentStatusModel(
                name="Signal Scout",
                icon="telescope",
                status="idle",
                signals_detected=0
            ),
            deep_hunter=EliteAgentStatusModel(
                name="Deep Hunter",
                icon="search",
                status="idle",
                scraped_today=0
            ),
            intake_commander=EliteAgentStatusModel(
                name="Intake Commander",
                icon="shield-check",
                status="idle",
                queue_size=0,
                unicorns_found=0,
                duplicates_blocked=0,
                routed_to_bdr=0
            ),
            summary={
                "signals_today": 0,
                "scraped_today": 0,
                "unicorns_today": 0,
                "bdr_routed_today": 0,
                "duplicates_blocked": 0,
                "pending_orders": 0,
                "intake_queue": 0
            },
            updated_at=now.isoformat()
        )


@router.get("/revival-candidates", response_model=RevivalCandidatesResponse)
async def get_revival_candidates(
    priority: Optional[str] = Query(None, description="Filter by priority: high, medium, low"),
    min_value: Optional[float] = Query(None, description="Minimum deal value"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get lost deals ready for re-engagement (6+ months since last contact).

    These are deals from fact_lost_opportunities where is_revival_candidate=true.
    Sorted by revival_score DESC, deal_value DESC.
    """
    try:
        from app.core.supabase import get_supabase_client
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("fact_lost_opportunities").select("*").eq("is_revival_candidate", True)

        # Apply filters
        if priority:
            query = query.eq("revival_priority", priority)
        if min_value:
            query = query.gte("deal_value", min_value)

        # Get total count first (for pagination info)
        count_result = supabase.table("fact_lost_opportunities").select(
            "close_opportunity_id", count="exact"
        ).eq("is_revival_candidate", True).execute()
        total_count = count_result.count or 0

        # Get paginated results sorted by score and value
        result = query.order(
            "revival_score", desc=True
        ).order(
            "deal_value", desc=True
        ).range(offset, offset + limit - 1).execute()

        candidates = []
        total_value = 0.0
        high_priority_count = 0

        for row in (result.data or []):
            total_value += row.get("deal_value", 0) or 0
            if row.get("revival_priority") == "high":
                high_priority_count += 1

            candidates.append(RevivalCandidate(
                close_opportunity_id=row.get("close_opportunity_id", ""),
                company_id=row.get("company_id"),
                lead_name=row.get("lead_name", "Unknown"),
                deal_value=row.get("deal_value", 0) or 0,
                close_reason=row.get("close_reason"),
                date_lost=row.get("date_lost"),
                days_since_lost=row.get("days_since_lost"),
                revival_priority=row.get("revival_priority", "low"),
                revival_score=row.get("revival_score", 0) or 0,
                last_contact_date=row.get("last_contact_date"),
                competitor_lost_to=row.get("competitor_lost_to"),
                notes=row.get("notes")[:200] if row.get("notes") else None  # Truncate notes
            ))

        # Get summary stats
        summary_result = supabase.table("fact_lost_opportunities").select(
            "revival_priority"
        ).eq("is_revival_candidate", True).execute()

        priority_counts = {"high": 0, "medium": 0, "low": 0}
        for row in (summary_result.data or []):
            p = row.get("revival_priority", "low")
            if p in priority_counts:
                priority_counts[p] += 1

        return RevivalCandidatesResponse(
            candidates=candidates,
            total_count=total_count,
            total_value=total_value,
            high_priority_count=high_priority_count,
            summary={
                "by_priority": priority_counts,
                "avg_score": sum(c.revival_score for c in candidates) / len(candidates) if candidates else 0,
                "filters_applied": {
                    "priority": priority,
                    "min_value": min_value,
                    "limit": limit,
                    "offset": offset
                }
            }
        )

    except Exception as e:
        logger.error(f"Error fetching revival candidates: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
