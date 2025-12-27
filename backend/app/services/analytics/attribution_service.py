"""
AttributionService - Multi-touch attribution calculation and analysis.

Provides:
- Touchpoint tracking for deals
- Multi-touch attribution models (first, last, linear, time-decay)
- Channel and rep performance analytics
- ROI calculations by activity type
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.sql import text

from app.models.deal_attribution import DealAttribution, TouchpointType

logger = logging.getLogger(__name__)

# Time decay half-life in days (touchpoints lose half their weight every N days)
TIME_DECAY_HALF_LIFE = 7


class AttributionService:
    """
    Service for deal attribution tracking and analytics.

    Usage:
        service = AttributionService(db)
        await service.create_attribution(
            deal_id="deal_123",
            deal_value=10000,
            touchpoints=[...]
        )
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def create_attribution(
        self,
        deal_id: str,
        deal_value: Optional[float] = None,
        lead_id: Optional[UUID] = None,
        deal_name: Optional[str] = None,
        touchpoints: Optional[List[Dict[str, Any]]] = None,
        closed_at: Optional[datetime] = None,
        rep_id: Optional[str] = None,
        rep_name: Optional[str] = None,
        primary_campaign: Optional[str] = None,
        primary_source: Optional[str] = None,
    ) -> DealAttribution:
        """
        Create or update attribution record for a deal.

        Args:
            deal_id: Unique deal identifier (from CRM)
            deal_value: Deal value in dollars
            lead_id: Associated lead ID
            deal_name: Deal name
            touchpoints: List of touchpoint dictionaries
            closed_at: Deal close date
            rep_id: Sales rep ID
            rep_name: Sales rep name
            primary_campaign: Primary marketing campaign
            primary_source: Primary lead source

        Returns:
            DealAttribution record with calculated attribution values
        """
        # Check if attribution already exists
        existing = await self.get_attribution_by_deal(deal_id)
        if existing:
            return await self.update_attribution(existing.id, touchpoints=touchpoints)

        touchpoints = touchpoints or []
        closed_at = closed_at or datetime.utcnow()

        # Calculate days in pipeline
        days_in_pipeline = None
        if touchpoints:
            first_touch = min(tp.get("timestamp", "") for tp in touchpoints)
            if first_touch:
                try:
                    first_dt = datetime.fromisoformat(first_touch.replace("Z", "+00:00"))
                    days_in_pipeline = (closed_at - first_dt).days
                except (ValueError, TypeError):
                    pass

        # Calculate attribution values
        attribution_values = self._calculate_attribution(touchpoints, deal_value or 0)

        attribution = DealAttribution(
            deal_id=deal_id,
            lead_id=lead_id,
            deal_name=deal_name,
            deal_value=Decimal(str(deal_value)) if deal_value else None,
            closed_at=closed_at,
            touchpoints=touchpoints,
            total_touches=len(touchpoints),
            days_in_pipeline=days_in_pipeline,
            first_touch_channel=attribution_values.get("first_touch_channel"),
            last_touch_channel=attribution_values.get("last_touch_channel"),
            first_touch_value=Decimal(str(attribution_values.get("first_touch_value", 0))),
            last_touch_value=Decimal(str(attribution_values.get("last_touch_value", 0))),
            linear_touch_value=Decimal(str(attribution_values.get("linear_touch_value", 0))),
            time_decay_value=Decimal(str(attribution_values.get("time_decay_value", 0))),
            rep_id=rep_id,
            rep_name=rep_name,
            primary_campaign=primary_campaign,
            primary_source=primary_source,
        )

        self.db.add(attribution)
        await self.db.commit()
        await self.db.refresh(attribution)

        logger.info(f"Created attribution for deal {deal_id}: {len(touchpoints)} touchpoints")
        return attribution

    async def add_touchpoint(
        self,
        deal_id: str,
        touchpoint_type: str,
        channel: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[DealAttribution]:
        """Add a touchpoint to an existing deal attribution."""
        attribution = await self.get_attribution_by_deal(deal_id)
        if not attribution:
            logger.warning(f"No attribution found for deal {deal_id}")
            return None

        timestamp = timestamp or datetime.utcnow()
        attribution.add_touchpoint(
            touchpoint_type=touchpoint_type,
            channel=channel,
            timestamp=timestamp,
            metadata=metadata,
        )

        # Recalculate attribution values
        deal_value = float(attribution.deal_value) if attribution.deal_value else 0
        values = self._calculate_attribution(attribution.touchpoints, deal_value)

        attribution.first_touch_channel = values.get("first_touch_channel")
        attribution.last_touch_channel = values.get("last_touch_channel")
        attribution.first_touch_value = Decimal(str(values.get("first_touch_value", 0)))
        attribution.last_touch_value = Decimal(str(values.get("last_touch_value", 0)))
        attribution.linear_touch_value = Decimal(str(values.get("linear_touch_value", 0)))
        attribution.time_decay_value = Decimal(str(values.get("time_decay_value", 0)))

        await self.db.commit()
        await self.db.refresh(attribution)

        return attribution

    def _calculate_attribution(
        self,
        touchpoints: List[Dict[str, Any]],
        deal_value: float,
    ) -> Dict[str, Any]:
        """
        Calculate multi-touch attribution values.

        Models:
        - First touch: 100% credit to first touchpoint
        - Last touch: 100% credit to last touchpoint
        - Linear: Equal credit to all touchpoints
        - Time decay: Exponential decay favoring recent touches
        """
        if not touchpoints or deal_value <= 0:
            return {
                "first_touch_channel": None,
                "last_touch_channel": None,
                "first_touch_value": 0,
                "last_touch_value": 0,
                "linear_touch_value": 0,
                "time_decay_value": 0,
            }

        # Sort by timestamp
        sorted_tps = sorted(
            touchpoints,
            key=lambda x: x.get("timestamp", "")
        )

        first_touch = sorted_tps[0]
        last_touch = sorted_tps[-1]

        # Linear value (per touchpoint)
        linear_value = deal_value / len(touchpoints)

        # Time decay calculation
        try:
            last_ts = datetime.fromisoformat(
                last_touch.get("timestamp", "").replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            last_ts = datetime.utcnow()

        decay_weights = []
        for tp in sorted_tps:
            try:
                tp_ts = datetime.fromisoformat(
                    tp.get("timestamp", "").replace("Z", "+00:00")
                )
                days_ago = (last_ts - tp_ts).days
                # Exponential decay: weight = 2^(-days/half_life)
                weight = 2 ** (-days_ago / TIME_DECAY_HALF_LIFE)
                decay_weights.append(weight)
            except (ValueError, TypeError):
                decay_weights.append(1.0)

        # Normalize decay weights
        total_weight = sum(decay_weights)
        if total_weight > 0:
            time_decay_value = deal_value * (decay_weights[-1] / total_weight)
        else:
            time_decay_value = linear_value

        return {
            "first_touch_channel": first_touch.get("channel"),
            "last_touch_channel": last_touch.get("channel"),
            "first_touch_value": deal_value,  # 100% to first touch
            "last_touch_value": deal_value,   # 100% to last touch
            "linear_touch_value": round(linear_value, 2),
            "time_decay_value": round(time_decay_value, 2),
        }

    async def update_attribution(
        self,
        attribution_id: UUID,
        **updates: Any
    ) -> Optional[DealAttribution]:
        """Update attribution record."""
        result = await self.db.execute(
            select(DealAttribution).where(DealAttribution.id == attribution_id)
        )
        attribution = result.scalar_one_or_none()

        if not attribution:
            return None

        for key, value in updates.items():
            if hasattr(attribution, key) and value is not None:
                setattr(attribution, key, value)

        # Recalculate if touchpoints changed
        if "touchpoints" in updates:
            deal_value = float(attribution.deal_value) if attribution.deal_value else 0
            values = self._calculate_attribution(attribution.touchpoints, deal_value)
            attribution.total_touches = len(attribution.touchpoints)
            attribution.first_touch_channel = values.get("first_touch_channel")
            attribution.last_touch_channel = values.get("last_touch_channel")

        await self.db.commit()
        await self.db.refresh(attribution)

        return attribution

    # Query methods
    async def get_attribution_by_deal(self, deal_id: str) -> Optional[DealAttribution]:
        """Get attribution by deal ID."""
        result = await self.db.execute(
            select(DealAttribution).where(DealAttribution.deal_id == deal_id)
        )
        return result.scalar_one_or_none()

    async def get_attribution_by_id(self, attribution_id: UUID) -> Optional[DealAttribution]:
        """Get attribution by primary key."""
        result = await self.db.execute(
            select(DealAttribution).where(DealAttribution.id == attribution_id)
        )
        return result.scalar_one_or_none()

    async def list_attributions(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        rep_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> List[DealAttribution]:
        """List attributions with optional filters."""
        query = select(DealAttribution).order_by(desc(DealAttribution.closed_at))

        if start_date:
            query = query.where(DealAttribution.closed_at >= start_date)
        if end_date:
            query = query.where(DealAttribution.closed_at <= end_date)
        if rep_id:
            query = query.where(DealAttribution.rep_id == rep_id)
        if channel:
            query = query.where(
                (DealAttribution.first_touch_channel == channel) |
                (DealAttribution.last_touch_channel == channel)
            )

        result = await self.db.execute(query.limit(limit).offset(offset))
        return list(result.scalars().all())

    # Analytics methods
    async def get_channel_performance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model: str = "last_touch",
    ) -> List[Dict[str, Any]]:
        """
        Get revenue attribution by channel.

        Args:
            start_date: Filter by close date start
            end_date: Filter by close date end
            model: Attribution model (first_touch, last_touch, linear, time_decay)
        """
        channel_col = {
            "first_touch": DealAttribution.first_touch_channel,
            "last_touch": DealAttribution.last_touch_channel,
        }.get(model, DealAttribution.last_touch_channel)

        value_col = {
            "first_touch": DealAttribution.first_touch_value,
            "last_touch": DealAttribution.last_touch_value,
            "linear": DealAttribution.linear_touch_value,
            "time_decay": DealAttribution.time_decay_value,
        }.get(model, DealAttribution.last_touch_value)

        query = select(
            channel_col.label("channel"),
            func.count(DealAttribution.id).label("deal_count"),
            func.sum(DealAttribution.deal_value).label("total_value"),
            func.sum(value_col).label("attributed_value"),
            func.avg(DealAttribution.days_in_pipeline).label("avg_days_to_close"),
        ).where(channel_col.isnot(None))

        if start_date:
            query = query.where(DealAttribution.closed_at >= start_date)
        if end_date:
            query = query.where(DealAttribution.closed_at <= end_date)

        query = query.group_by(channel_col).order_by(desc("total_value"))

        result = await self.db.execute(query)
        rows = result.fetchall()

        return [
            {
                "channel": row.channel,
                "deal_count": row.deal_count,
                "total_value": float(row.total_value) if row.total_value else 0,
                "attributed_value": float(row.attributed_value) if row.attributed_value else 0,
                "avg_days_to_close": round(row.avg_days_to_close, 1) if row.avg_days_to_close else None,
            }
            for row in rows
        ]

    async def get_rep_performance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get deal performance by sales rep."""
        query = select(
            DealAttribution.rep_id,
            DealAttribution.rep_name,
            func.count(DealAttribution.id).label("deal_count"),
            func.sum(DealAttribution.deal_value).label("total_value"),
            func.avg(DealAttribution.deal_value).label("avg_deal_value"),
            func.avg(DealAttribution.days_in_pipeline).label("avg_days_to_close"),
            func.avg(DealAttribution.total_touches).label("avg_touches"),
        ).where(DealAttribution.rep_id.isnot(None))

        if start_date:
            query = query.where(DealAttribution.closed_at >= start_date)
        if end_date:
            query = query.where(DealAttribution.closed_at <= end_date)

        query = query.group_by(
            DealAttribution.rep_id,
            DealAttribution.rep_name
        ).order_by(desc("total_value"))

        result = await self.db.execute(query)
        rows = result.fetchall()

        return [
            {
                "rep_id": row.rep_id,
                "rep_name": row.rep_name,
                "deal_count": row.deal_count,
                "total_value": float(row.total_value) if row.total_value else 0,
                "avg_deal_value": round(float(row.avg_deal_value), 2) if row.avg_deal_value else 0,
                "avg_days_to_close": round(row.avg_days_to_close, 1) if row.avg_days_to_close else None,
                "avg_touches": round(row.avg_touches, 1) if row.avg_touches else None,
            }
            for row in rows
        ]

    async def get_roi_by_activity(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate ROI metrics by activity type.

        Uses touchpoint data to calculate cost-per-touch effectiveness.
        """
        # Get all attributions in date range
        attributions = await self.list_attributions(
            limit=1000,
            start_date=start_date,
            end_date=end_date,
        )

        # Aggregate touchpoint stats
        activity_stats = {}
        for attr in attributions:
            deal_value = float(attr.deal_value) if attr.deal_value else 0
            num_touches = len(attr.touchpoints)
            linear_value = deal_value / num_touches if num_touches > 0 else 0

            for tp in attr.touchpoints:
                tp_type = tp.get("type", "unknown")
                if tp_type not in activity_stats:
                    activity_stats[tp_type] = {
                        "count": 0,
                        "deals_influenced": set(),
                        "total_attributed": 0,
                    }

                activity_stats[tp_type]["count"] += 1
                activity_stats[tp_type]["deals_influenced"].add(attr.deal_id)
                activity_stats[tp_type]["total_attributed"] += linear_value

        # Convert to response format
        return [
            {
                "activity_type": activity,
                "touch_count": stats["count"],
                "deals_influenced": len(stats["deals_influenced"]),
                "total_attributed_value": round(stats["total_attributed"], 2),
                "avg_value_per_touch": round(
                    stats["total_attributed"] / stats["count"], 2
                ) if stats["count"] > 0 else 0,
            }
            for activity, stats in sorted(
                activity_stats.items(),
                key=lambda x: x[1]["total_attributed"],
                reverse=True
            )
        ]

    async def get_touchpoint_types(self) -> List[TouchpointType]:
        """Get all touchpoint type definitions."""
        result = await self.db.execute(
            select(TouchpointType).order_by(TouchpointType.channel, TouchpointType.name)
        )
        return list(result.scalars().all())
