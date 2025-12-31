"""
War Room API - Unified Command Center Dashboard.

Provides REST endpoints for the War Room dashboard:
- Full state (complete dashboard data)
- Summary metrics (lightweight refresh)
- Individual component data

Performance targets: <100ms for all endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.services.war_room_service import WarRoomService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/war-room", tags=["war-room"])


# Response Models
class ActiveCallResponse(BaseModel):
    """Active call with coaching data."""
    call_sid: str
    agent_id: Optional[str]
    started_at: datetime
    duration_seconds: int
    suggestions_shown: int
    suggestions_used: int


class HotAccountResponse(BaseModel):
    """Account with high engagement."""
    id: str
    name: str
    domain: Optional[str]
    stage: str
    total_contacts: int
    engaged_contacts: int
    stakeholder_score: float
    deal_value: float
    activities_7d: int


class IntentLeadResponse(BaseModel):
    """Lead with high buyer intent."""
    id: str
    name: str
    state: Optional[str]
    icp_tier: Optional[str]
    intent_score: float
    recent_signals_7d: int
    last_signal_type: Optional[str]


class AgentStatusResponse(BaseModel):
    """Elite team agent status."""
    agent_name: str
    status: str
    current_task: Optional[str]
    items_processed: int
    last_run: Optional[datetime]


class CoachingMetrics(BaseModel):
    """Coaching aggregate metrics."""
    active_calls_count: int
    acceptance_rate: float
    avg_latency_ms: int


class AccountMetrics(BaseModel):
    """Account aggregate metrics."""
    total_accounts: int
    engaged_accounts: int
    hot_accounts: List[HotAccountResponse]


class DealerMetrics(BaseModel):
    """Dealer intelligence metrics."""
    total_dealers: int
    growth_signals_count: int
    tier_distribution: Dict[str, int]
    capability_distribution: Dict[str, int]


class IntentMetrics(BaseModel):
    """Intent scoring metrics."""
    leads_above_50: int
    avg_intent_score: float
    top_leads: List[IntentLeadResponse]


class EliteTeamMetrics(BaseModel):
    """Elite team metrics."""
    agents: List[AgentStatusResponse]
    pipeline_flow: Dict[str, int]


class WarRoomStateResponse(BaseModel):
    """Complete War Room state."""
    # Call coaching
    coaching: CoachingMetrics

    # Accounts
    accounts: AccountMetrics

    # Dealers
    dealers: DealerMetrics

    # Intent
    intent: IntentMetrics

    # Elite team
    elite_team: EliteTeamMetrics

    # Metadata
    last_updated: datetime


class SummaryMetricsResponse(BaseModel):
    """Lightweight summary for quick refresh."""
    active_calls: int
    coaching_acceptance_rate: float
    engaged_accounts: int
    hot_leads_count: int
    timestamp: str


# Endpoints
@router.get("/state", response_model=WarRoomStateResponse)
async def get_war_room_state(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get complete War Room state.

    Returns aggregated data from all intelligence systems:
    - Active calls with coaching
    - Hot accounts with engagement
    - Dealer market trends
    - Buyer intent leaderboard
    - Elite team agent status

    Performance target: <100ms
    """
    service = WarRoomService(db)
    state = await service.get_full_state()

    return WarRoomStateResponse(
        coaching=CoachingMetrics(
            active_calls_count=len(state.active_calls),
            acceptance_rate=state.coaching_acceptance_rate,
            avg_latency_ms=state.avg_coaching_latency_ms,
        ),
        accounts=AccountMetrics(
            total_accounts=state.total_accounts,
            engaged_accounts=state.engaged_accounts,
            hot_accounts=[
                HotAccountResponse(
                    id=a.id,
                    name=a.name,
                    domain=a.domain,
                    stage=a.stage,
                    total_contacts=a.total_contacts,
                    engaged_contacts=a.engaged_contacts,
                    stakeholder_score=a.stakeholder_score,
                    deal_value=a.deal_value,
                    activities_7d=a.activities_7d,
                )
                for a in state.hot_accounts
            ],
        ),
        dealers=DealerMetrics(
            total_dealers=state.total_dealers,
            growth_signals_count=state.growth_signals_count,
            tier_distribution=state.market_trends.get("tier_distribution", {}),
            capability_distribution=state.market_trends.get(
                "capability_distribution", {}
            ),
        ),
        intent=IntentMetrics(
            leads_above_50=state.leads_above_50_intent,
            avg_intent_score=state.avg_intent_score,
            top_leads=[
                IntentLeadResponse(
                    id=l.id,
                    name=l.name,
                    state=l.state,
                    icp_tier=l.icp_tier,
                    intent_score=l.intent_score,
                    recent_signals_7d=l.recent_signals_7d,
                    last_signal_type=l.last_signal_type,
                )
                for l in state.intent_feed
            ],
        ),
        elite_team=EliteTeamMetrics(
            agents=[
                AgentStatusResponse(
                    agent_name=a.agent_name,
                    status=a.status,
                    current_task=a.current_task,
                    items_processed=a.items_processed,
                    last_run=a.last_run,
                )
                for a in state.agent_statuses
            ],
            pipeline_flow=state.pipeline_flow,
        ),
        last_updated=state.last_updated,
    )


@router.get("/summary", response_model=SummaryMetricsResponse)
async def get_summary_metrics(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get lightweight summary metrics.

    Use for quick dashboard refresh (e.g., every 5 seconds).
    Full state refresh can be less frequent.
    """
    service = WarRoomService(db)
    metrics = await service.get_summary_metrics()

    return SummaryMetricsResponse(**metrics)


@router.get("/active-calls", response_model=List[ActiveCallResponse])
async def get_active_calls(
    db: AsyncSession = Depends(get_async_db),
):
    """Get currently active calls with coaching."""
    service = WarRoomService(db)
    calls = await service._get_active_calls()

    return [
        ActiveCallResponse(
            call_sid=c.call_sid,
            agent_id=c.agent_id,
            started_at=c.started_at,
            duration_seconds=c.duration_seconds,
            suggestions_shown=c.suggestions_shown,
            suggestions_used=c.suggestions_used,
        )
        for c in calls
    ]


@router.get("/hot-accounts", response_model=List[HotAccountResponse])
async def get_hot_accounts(
    db: AsyncSession = Depends(get_async_db),
):
    """Get accounts with high engagement momentum."""
    service = WarRoomService(db)
    result = await service._get_hot_accounts()

    return [
        HotAccountResponse(
            id=a.id,
            name=a.name,
            domain=a.domain,
            stage=a.stage,
            total_contacts=a.total_contacts,
            engaged_contacts=a.engaged_contacts,
            stakeholder_score=a.stakeholder_score,
            deal_value=a.deal_value,
            activities_7d=a.activities_7d,
        )
        for a in result.get("hot_accounts", [])
    ]


@router.get("/intent-leaderboard", response_model=List[IntentLeadResponse])
async def get_intent_leaderboard(
    db: AsyncSession = Depends(get_async_db),
):
    """Get top leads by intent score."""
    service = WarRoomService(db)
    result = await service._get_intent_leaderboard()

    return [
        IntentLeadResponse(
            id=l.id,
            name=l.name,
            state=l.state,
            icp_tier=l.icp_tier,
            intent_score=l.intent_score,
            recent_signals_7d=l.recent_signals_7d,
            last_signal_type=l.last_signal_type,
        )
        for l in result.get("top_leads", [])
    ]
