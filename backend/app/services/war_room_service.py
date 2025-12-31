"""
War Room Service - Unified Command Center Data Aggregator.

Aggregates real-time data from all sales intelligence systems:
- Call coaching (active calls, coaching metrics)
- Account layer (hot accounts, stakeholder engagement)
- Dealer intelligence (market trends, growth signals)
- Buyer intent (hot leads, momentum leaderboard)
- Elite team (agent status, pipeline metrics)

Performance targets:
- API responses: <100ms
- WebSocket updates: <50ms
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.services.account_service import AccountService
from app.services.dealer_analytics_service import DealerAnalyticsService
from app.services.intent_scoring_service import IntentScoringService
from app.models.coaching_session import CoachingSession

logger = logging.getLogger(__name__)


@dataclass
class ActiveCall:
    """Active call with coaching data."""
    call_sid: str
    agent_id: Optional[str]
    started_at: datetime
    duration_seconds: int
    suggestions_shown: int
    suggestions_used: int


@dataclass
class HotAccount:
    """Account with high engagement momentum."""
    id: str
    name: str
    domain: Optional[str]
    stage: str
    total_contacts: int
    engaged_contacts: int
    stakeholder_score: float
    deal_value: float
    activities_7d: int


@dataclass
class IntentLead:
    """Lead with high buyer intent."""
    id: str
    name: str
    state: Optional[str]
    icp_tier: Optional[str]
    intent_score: float
    recent_signals_7d: int
    last_signal_type: Optional[str]


@dataclass
class AgentStatus:
    """Elite team agent status."""
    agent_name: str
    status: str
    current_task: Optional[str]
    items_processed: int
    last_run: Optional[datetime]


@dataclass
class WarRoomState:
    """Complete War Room dashboard state."""
    # Call coaching data
    active_calls: List[ActiveCall] = field(default_factory=list)
    coaching_acceptance_rate: float = 0.0
    avg_coaching_latency_ms: int = 0

    # Account data
    hot_accounts: List[HotAccount] = field(default_factory=list)
    total_accounts: int = 0
    engaged_accounts: int = 0

    # Dealer intelligence
    total_dealers: int = 0
    market_trends: Dict[str, Any] = field(default_factory=dict)
    growth_signals_count: int = 0

    # Intent scoring
    intent_feed: List[IntentLead] = field(default_factory=list)
    leads_above_50_intent: int = 0
    avg_intent_score: float = 0.0

    # Elite team
    agent_statuses: List[AgentStatus] = field(default_factory=list)
    pipeline_flow: Dict[str, int] = field(default_factory=dict)

    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)


class WarRoomService:
    """
    War Room data aggregation service.

    Pulls data from all feature services and aggregates into
    a unified dashboard state. Uses parallel queries for performance.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db
        self.account_service = AccountService(db)
        self.dealer_service = DealerAnalyticsService(db)
        self.intent_service = IntentScoringService(db)

    async def get_full_state(self) -> WarRoomState:
        """
        Get complete War Room state.

        Runs all queries in parallel for <100ms response.
        """
        # Run all aggregations in parallel
        results = await asyncio.gather(
            self._get_active_calls(),
            self._get_coaching_metrics(),
            self._get_hot_accounts(),
            self._get_dealer_overview(),
            self._get_intent_leaderboard(),
            self._get_elite_team_status(),
            return_exceptions=True,
        )

        # Handle any errors gracefully
        active_calls = results[0] if not isinstance(results[0], Exception) else []
        coaching = results[1] if not isinstance(results[1], Exception) else {}
        accounts = results[2] if not isinstance(results[2], Exception) else {}
        dealers = results[3] if not isinstance(results[3], Exception) else {}
        intent = results[4] if not isinstance(results[4], Exception) else {}
        elite = results[5] if not isinstance(results[5], Exception) else {}

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"War room query {i} failed: {result}")

        return WarRoomState(
            # Calls
            active_calls=active_calls,
            coaching_acceptance_rate=coaching.get("acceptance_rate", 0.0),
            avg_coaching_latency_ms=coaching.get("avg_latency_ms", 0),

            # Accounts
            hot_accounts=accounts.get("hot_accounts", []),
            total_accounts=accounts.get("total", 0),
            engaged_accounts=accounts.get("engaged", 0),

            # Dealers
            total_dealers=dealers.get("total_dealers", 0),
            market_trends=dealers.get("trends", {}),
            growth_signals_count=dealers.get("growth_signals", 0),

            # Intent
            intent_feed=intent.get("top_leads", []),
            leads_above_50_intent=intent.get("above_50_count", 0),
            avg_intent_score=intent.get("avg_score", 0.0),

            # Elite team
            agent_statuses=elite.get("agents", []),
            pipeline_flow=elite.get("pipeline", {}),

            last_updated=datetime.utcnow(),
        )

    async def _get_active_calls(self) -> List[ActiveCall]:
        """Get currently active coaching sessions."""
        result = await self.db.execute(
            select(CoachingSession)
            .where(CoachingSession.is_active == True)
            .order_by(CoachingSession.started_at.desc())
            .limit(20)
        )
        sessions = result.scalars().all()

        return [
            ActiveCall(
                call_sid=s.call_sid,
                agent_id=s.agent_id,
                started_at=s.started_at,
                duration_seconds=s.duration_seconds or 0,
                suggestions_shown=s.suggestions_shown,
                suggestions_used=s.suggestions_used,
            )
            for s in sessions
        ]

    async def _get_coaching_metrics(self) -> Dict[str, Any]:
        """Get aggregate coaching metrics for today."""
        today = datetime.utcnow().date()

        result = await self.db.execute(
            select(
                func.avg(CoachingSession.overall_acceptance_rate).label("avg_rate"),
                func.avg(CoachingSession.avg_coaching_latency_ms).label("avg_latency"),
                func.count(CoachingSession.id).label("total_sessions"),
            )
            .where(func.date(CoachingSession.started_at) == today)
        )
        row = result.fetchone()

        return {
            "acceptance_rate": round(float(row.avg_rate or 0), 3),
            "avg_latency_ms": int(row.avg_latency or 0),
            "sessions_today": int(row.total_sessions or 0),
        }

    async def _get_hot_accounts(self) -> Dict[str, Any]:
        """Get accounts with high engagement."""
        result = await self.db.execute(text("""
            SELECT
                id, name, domain, account_stage,
                total_contacts, engaged_contacts,
                stakeholder_score, deal_value
            FROM dim_accounts
            WHERE stakeholder_score > 0.5 OR engaged_contacts > 0
            ORDER BY stakeholder_score DESC, deal_value DESC
            LIMIT 10
        """))
        rows = result.fetchall()

        # Get totals
        count_result = await self.db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE engaged_contacts > 0) as engaged
            FROM dim_accounts
        """))
        counts = count_result.fetchone()

        hot_accounts = [
            HotAccount(
                id=str(r.id),
                name=r.name,
                domain=r.domain,
                stage=r.account_stage or "prospect",
                total_contacts=r.total_contacts or 0,
                engaged_contacts=r.engaged_contacts or 0,
                stakeholder_score=float(r.stakeholder_score or 0),
                deal_value=float(r.deal_value or 0),
                activities_7d=0,  # Would need separate query
            )
            for r in rows
        ]

        return {
            "hot_accounts": hot_accounts,
            "total": int(counts.total or 0) if counts else 0,
            "engaged": int(counts.engaged or 0) if counts else 0,
        }

    async def _get_dealer_overview(self) -> Dict[str, Any]:
        """Get dealer market overview."""
        try:
            overview = await self.dealer_service.get_market_overview()

            # Count recent growth signals
            result = await self.db.execute(text("""
                SELECT COUNT(*) as count
                FROM mv_dealer_growth_signals
            """))
            growth_count = result.scalar() or 0

            return {
                "total_dealers": overview.get("total_dealers", 0),
                "trends": {
                    "tier_distribution": overview.get("tier_distribution", {}),
                    "capability_distribution": overview.get("capability_distribution", {}),
                },
                "growth_signals": int(growth_count),
            }
        except Exception as e:
            logger.warning(f"Dealer overview query failed: {e}")
            return {"total_dealers": 0, "trends": {}, "growth_signals": 0}

    async def _get_intent_leaderboard(self) -> Dict[str, Any]:
        """Get top intent leads and metrics."""
        # Get hot leads
        hot_leads_result = await self.intent_service.get_hot_leads(
            min_score=50.0,
            limit=10,
        )

        top_leads = [
            IntentLead(
                id=lead["id"],
                name=lead["name"],
                state=lead.get("state"),
                icp_tier=lead.get("icp_tier"),
                intent_score=lead["intent_score"],
                recent_signals_7d=lead.get("recent_signals_7d", 0),
                last_signal_type=lead.get("last_signal_type"),
            )
            for lead in hot_leads_result.get("leads", [])
        ]

        # Get aggregate metrics
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE intent_score >= 50) as above_50,
                AVG(intent_score) as avg_score
            FROM dim_companies
            WHERE intent_score > 0
        """))
        row = result.fetchone()

        return {
            "top_leads": top_leads,
            "above_50_count": int(row.above_50 or 0) if row else 0,
            "avg_score": round(float(row.avg_score or 0), 1) if row else 0.0,
        }

    async def _get_elite_team_status(self) -> Dict[str, Any]:
        """Get Elite Team agent statuses from Redis."""
        try:
            # Try to get from Redis cache
            import redis.asyncio as redis
            import os
            import json

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = await redis.from_url(redis_url)

            state_json = await client.get("elite_team:state")
            await client.close()

            if state_json:
                state = json.loads(state_json)
                agents = [
                    AgentStatus(
                        agent_name=name,
                        status=data.get("status", "idle"),
                        current_task=data.get("current_task"),
                        items_processed=data.get("items_processed", 0),
                        last_run=None,  # Parse if needed
                    )
                    for name, data in state.items()
                    if isinstance(data, dict)
                ]
                return {"agents": agents, "pipeline": {}}

        except Exception as e:
            logger.warning(f"Elite team status unavailable: {e}")

        # Return default if Redis unavailable
        return {
            "agents": [
                AgentStatus("signal_scout", "idle", None, 0, None),
                AgentStatus("deep_hunter", "idle", None, 0, None),
                AgentStatus("intake_commander", "idle", None, 0, None),
            ],
            "pipeline": {},
        }

    async def get_summary_metrics(self) -> Dict[str, Any]:
        """Get lightweight summary metrics for quick refresh."""
        result = await asyncio.gather(
            self._get_coaching_metrics(),
            self.db.execute(text(
                "SELECT COUNT(*) FROM dim_accounts WHERE engaged_contacts > 0"
            )),
            self.db.execute(text(
                "SELECT COUNT(*) FROM dim_companies WHERE intent_score >= 50"
            )),
            return_exceptions=True,
        )

        coaching = result[0] if not isinstance(result[0], Exception) else {}
        engaged = result[1].scalar() if not isinstance(result[1], Exception) else 0
        hot_leads = result[2].scalar() if not isinstance(result[2], Exception) else 0

        return {
            "active_calls": coaching.get("sessions_today", 0),
            "coaching_acceptance_rate": coaching.get("acceptance_rate", 0),
            "engaged_accounts": int(engaged or 0),
            "hot_leads_count": int(hot_leads or 0),
            "timestamp": datetime.utcnow().isoformat(),
        }
