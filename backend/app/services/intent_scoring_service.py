"""
IntentScoringService - Buyer intent calculation and tracking.

Calculates buyer intent scores based on engagement signals:
- Email opens/clicks
- Reply sentiment and timing
- Call scheduling
- Website activity

Uses time decay (7-day half-life) to weight recent signals higher.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text, update
from sqlalchemy.dialects.postgresql import insert

from app.models.buyer_intent import (
    BuyerIntentSignal,
    IntentSignalType,
    IntentSignalSource,
    INTENT_SIGNAL_WEIGHTS,
)

logger = logging.getLogger(__name__)

# Time decay configuration
TIME_DECAY_HALF_LIFE_DAYS = 7.0  # Signals lose half their value every 7 days
SIGNAL_LOOKBACK_DAYS = 30  # Only consider signals from last 30 days
MAX_INTENT_SCORE = 100.0


class IntentScoringService:
    """
    Service for tracking and calculating buyer intent scores.

    Intent scores are calculated as a weighted sum of signals with
    exponential time decay. Recent signals contribute more to the score.

    Usage:
        service = IntentScoringService(db)
        await service.record_intent_signal(
            lead_id=lead_uuid,
            signal_type="reply_positive",
            source="email",
            metadata={"email_id": "123"}
        )
        score = await service.calculate_intent_score(lead_uuid)
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def record_intent_signal(
        self,
        lead_id: UUID,
        signal_type: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        weight_override: Optional[float] = None,
    ) -> BuyerIntentSignal:
        """
        Record a new intent signal for a lead.

        The lead's intent_score is automatically updated via database trigger.

        Args:
            lead_id: UUID of the lead (dim_companies.id)
            signal_type: Type of signal (from IntentSignalType enum)
            source: Source channel (from IntentSignalSource enum)
            metadata: Additional context (email_id, page_url, etc.)
            weight_override: Override default weight for signal type

        Returns:
            Created BuyerIntentSignal record
        """
        # Get weight from defaults or use override
        weight = weight_override
        if weight is None:
            weight = INTENT_SIGNAL_WEIGHTS.get(signal_type, 1.0)

        signal = BuyerIntentSignal(
            lead_id=lead_id,
            signal_type=signal_type,
            signal_weight=weight,
            source=source,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )

        self.db.add(signal)
        await self.db.commit()
        await self.db.refresh(signal)

        logger.info(
            f"Recorded intent signal: {signal_type} for lead {lead_id} "
            f"(weight={weight}, source={source})"
        )

        return signal

    async def calculate_intent_score(
        self,
        lead_id: UUID,
        force_update: bool = False
    ) -> float:
        """
        Calculate intent score for a lead with time decay.

        Formula: score = SUM(weight * 2^(-days_old / half_life))

        Args:
            lead_id: UUID of the lead
            force_update: If True, recalculate and update dim_companies

        Returns:
            Calculated intent score (0-100)
        """
        cutoff = datetime.utcnow() - timedelta(days=SIGNAL_LOOKBACK_DAYS)

        # Get all recent signals for the lead
        result = await self.db.execute(
            select(BuyerIntentSignal)
            .where(BuyerIntentSignal.lead_id == lead_id)
            .where(BuyerIntentSignal.created_at >= cutoff)
            .order_by(desc(BuyerIntentSignal.created_at))
        )
        signals = result.scalars().all()

        if not signals:
            return 0.0

        # Calculate weighted sum with time decay
        now = datetime.utcnow()
        score = 0.0

        for signal in signals:
            days_old = (now - signal.created_at).total_seconds() / 86400
            decay_factor = math.pow(2, -days_old / TIME_DECAY_HALF_LIFE_DAYS)
            score += signal.signal_weight * decay_factor

        # Cap at max score
        final_score = min(score, MAX_INTENT_SCORE)

        # Update dim_companies if requested
        if force_update:
            await self.db.execute(text("""
                UPDATE dim_companies
                SET intent_score = :score,
                    intent_updated_at = NOW()
                WHERE id = :lead_id
            """), {"score": final_score, "lead_id": lead_id})
            await self.db.commit()

        return round(final_score, 2)

    async def get_hot_leads(
        self,
        min_score: float = 50.0,
        limit: int = 50,
        offset: int = 0,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get leads with high intent scores.

        Args:
            min_score: Minimum intent score threshold
            limit: Maximum results to return
            offset: Pagination offset
            state: Filter by state (optional)

        Returns:
            Paginated list of hot leads with intent data
        """
        params = {
            "min_score": min_score,
            "limit": limit,
            "offset": offset,
        }

        state_filter = ""
        if state:
            state_filter = "AND state = :state"
            params["state"] = state.upper()

        # Count query
        count_result = await self.db.execute(text(f"""
            SELECT COUNT(*) as total
            FROM dim_companies
            WHERE intent_score >= :min_score
              AND source_type = 'dealer_scraper'
              {state_filter}
        """), params)
        total = count_result.scalar() or 0

        # Data query with recent signals
        result = await self.db.execute(text(f"""
            SELECT
                dc.id,
                dc.name,
                dc.state,
                dc.city,
                dc.icp_tier,
                dc.icp_score,
                dc.intent_score,
                dc.intent_updated_at,
                dc.phone,
                dc.website,
                (
                    SELECT COUNT(*)
                    FROM buyer_intent_signals bis
                    WHERE bis.lead_id = dc.id
                      AND bis.created_at >= NOW() - INTERVAL '7 days'
                ) as recent_signals_7d,
                (
                    SELECT bis.signal_type
                    FROM buyer_intent_signals bis
                    WHERE bis.lead_id = dc.id
                    ORDER BY bis.created_at DESC
                    LIMIT 1
                ) as last_signal_type,
                (
                    SELECT bis.created_at
                    FROM buyer_intent_signals bis
                    WHERE bis.lead_id = dc.id
                    ORDER BY bis.created_at DESC
                    LIMIT 1
                ) as last_signal_at
            FROM dim_companies dc
            WHERE dc.intent_score >= :min_score
              AND dc.source_type = 'dealer_scraper'
              {state_filter}
            ORDER BY dc.intent_score DESC
            LIMIT :limit OFFSET :offset
        """), params)

        rows = result.fetchall()

        leads = [
            {
                "id": str(row.id),
                "name": row.name,
                "state": row.state,
                "city": row.city,
                "icp_tier": row.icp_tier,
                "icp_score": float(row.icp_score) if row.icp_score else 0,
                "intent_score": round(float(row.intent_score), 2),
                "intent_updated_at": (
                    row.intent_updated_at.isoformat()
                    if row.intent_updated_at else None
                ),
                "phone": row.phone,
                "website": row.website,
                "recent_signals_7d": int(row.recent_signals_7d or 0),
                "last_signal_type": row.last_signal_type,
                "last_signal_at": (
                    row.last_signal_at.isoformat()
                    if row.last_signal_at else None
                ),
            }
            for row in rows
        ]

        return {
            "leads": leads,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    async def get_signals_for_lead(
        self,
        lead_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get all intent signals for a specific lead.

        Args:
            lead_id: UUID of the lead
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Paginated list of signals for the lead
        """
        # Count query
        count_result = await self.db.execute(
            select(func.count(BuyerIntentSignal.id))
            .where(BuyerIntentSignal.lead_id == lead_id)
        )
        total = count_result.scalar() or 0

        # Data query
        result = await self.db.execute(
            select(BuyerIntentSignal)
            .where(BuyerIntentSignal.lead_id == lead_id)
            .order_by(desc(BuyerIntentSignal.created_at))
            .limit(limit)
            .offset(offset)
        )
        signals = result.scalars().all()

        return {
            "signals": [s.to_dict() for s in signals],
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    async def get_signal_summary(
        self,
        lead_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get signal summary statistics for a lead.

        Args:
            lead_id: UUID of the lead
            days: Lookback period in days

        Returns:
            Summary of signal counts and types
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(text("""
            SELECT
                signal_type,
                COUNT(*) as count,
                SUM(signal_weight) as total_weight,
                MAX(created_at) as last_at
            FROM buyer_intent_signals
            WHERE lead_id = :lead_id
              AND created_at >= :cutoff
            GROUP BY signal_type
            ORDER BY count DESC
        """), {"lead_id": lead_id, "cutoff": cutoff})

        rows = result.fetchall()

        signals_by_type = {
            row.signal_type: {
                "count": int(row.count),
                "total_weight": round(float(row.total_weight), 2),
                "last_at": row.last_at.isoformat() if row.last_at else None,
            }
            for row in rows
        }

        # Calculate totals
        total_signals = sum(s["count"] for s in signals_by_type.values())
        total_weight = sum(s["total_weight"] for s in signals_by_type.values())

        return {
            "lead_id": str(lead_id),
            "period_days": days,
            "total_signals": total_signals,
            "total_weight": round(total_weight, 2),
            "signals_by_type": signals_by_type,
        }

    async def batch_recalculate_scores(
        self,
        lead_ids: Optional[List[UUID]] = None,
        min_signals: int = 1,
    ) -> Dict[str, Any]:
        """
        Recalculate intent scores for multiple leads.

        If lead_ids not provided, recalculates for all leads with signals.

        Args:
            lead_ids: Optional list of lead UUIDs to recalculate
            min_signals: Minimum signal count to include lead

        Returns:
            Summary of recalculation results
        """
        if lead_ids:
            # Use provided list
            leads_to_update = lead_ids
        else:
            # Get all leads with signals
            result = await self.db.execute(text("""
                SELECT DISTINCT lead_id
                FROM buyer_intent_signals
                WHERE created_at >= NOW() - MAKE_INTERVAL(days => :days)
                GROUP BY lead_id
                HAVING COUNT(*) >= :min_signals
            """), {"days": SIGNAL_LOOKBACK_DAYS, "min_signals": min_signals})
            leads_to_update = [row.lead_id for row in result.fetchall()]

        # Recalculate each lead's score
        updated_count = 0
        for lead_id in leads_to_update:
            await self.calculate_intent_score(lead_id, force_update=True)
            updated_count += 1

        logger.info(f"Recalculated intent scores for {updated_count} leads")

        return {
            "status": "success",
            "leads_updated": updated_count,
        }
