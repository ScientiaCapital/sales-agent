"""
Cost monitoring helper functions for AI usage tracking.

Provides utility functions for:
- Daily spend calculation
- Cost per lead averaging
- Cache hit rate analysis
- Budget alert checking
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date as date_type
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from app.models.ai_cost_tracking import AICostTracking
from app.core.logging import setup_logging

logger = setup_logging(__name__)


async def get_daily_spend(
    db: Session,
    date: Optional[date_type] = None
) -> Dict[str, Any]:
    """
    Get total spend for a specific day (defaults to today).

    Args:
        db: Database session
        date: Date to query (defaults to today)

    Returns:
        Dictionary with:
        - date: ISO format date string
        - total_cost_usd: Total spend in USD
        - total_requests: Total number of requests

    Example:
        {"date": "2025-01-15", "total_cost_usd": 0.0042, "total_requests": 127}
    """
    try:
        # Default to today if no date provided
        if date is None:
            date = datetime.utcnow().date()

        # Calculate day boundaries
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())

        # Query total cost and requests for the day
        result = db.query(
            func.sum(AICostTracking.cost_usd).label("total_cost"),
            func.count(AICostTracking.id).label("total_requests")
        ).filter(
            and_(
                AICostTracking.timestamp >= day_start,
                AICostTracking.timestamp <= day_end
            )
        ).first()

        total_cost = float(result.total_cost or Decimal("0.0"))
        total_requests = result.total_requests or 0

        logger.debug(
            f"Daily spend for {date.isoformat()}: ${total_cost:.6f} "
            f"({total_requests} requests)"
        )

        return {
            "date": date.isoformat(),
            "total_cost_usd": round(total_cost, 6),
            "total_requests": total_requests
        }

    except Exception as e:
        logger.error(f"Failed to get daily spend: {e}", exc_info=True)
        raise


async def get_cost_per_lead_avg(
    db: Session,
    days: int = 7
) -> float:
    """
    Calculate average cost per lead over last N days.

    Args:
        db: Database session
        days: Number of days to look back (default: 7)

    Returns:
        Average cost per lead in USD

    Example:
        0.000125  # $0.000125 per lead
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get total cost for the period
        total_cost_result = db.query(
            func.sum(AICostTracking.cost_usd).label("total_cost")
        ).filter(
            and_(
                AICostTracking.timestamp >= start_date,
                AICostTracking.timestamp <= end_date,
                AICostTracking.lead_id.isnot(None)
            )
        ).first()

        total_cost = float(total_cost_result.total_cost or Decimal("0.0"))

        # Get count of unique leads
        unique_leads_result = db.query(
            func.count(AICostTracking.lead_id.distinct()).label("unique_leads")
        ).filter(
            and_(
                AICostTracking.timestamp >= start_date,
                AICostTracking.timestamp <= end_date,
                AICostTracking.lead_id.isnot(None)
            )
        ).first()

        unique_leads = unique_leads_result.unique_leads or 0

        # Calculate average
        if unique_leads > 0:
            avg_cost = total_cost / unique_leads
        else:
            avg_cost = 0.0

        logger.debug(
            f"Cost per lead avg ({days} days): ${avg_cost:.6f} "
            f"(total: ${total_cost:.6f}, leads: {unique_leads})"
        )

        return round(avg_cost, 8)

    except Exception as e:
        logger.error(f"Failed to calculate cost per lead average: {e}", exc_info=True)
        raise


async def get_cache_hit_rate(
    db: Session,
    hours: int = 24
) -> Dict[str, Any]:
    """
    Get cache effectiveness over last N hours.

    Args:
        db: Database session
        hours: Number of hours to look back (default: 24)

    Returns:
        Dictionary with:
        - cache_hit_rate: Percentage of requests that hit cache (0.0-1.0)
        - total_requests: Total number of requests
        - cache_hits: Number of cache hits

    Example:
        {"cache_hit_rate": 0.23, "total_requests": 450, "cache_hits": 104}
    """
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Query cache statistics
        result = db.query(
            func.count(AICostTracking.id).label("total_requests"),
            func.sum(case((AICostTracking.cache_hit == True, 1), else_=0)).label("cache_hits")
        ).filter(
            and_(
                AICostTracking.timestamp >= start_time,
                AICostTracking.timestamp <= end_time
            )
        ).first()

        total_requests = result.total_requests or 0
        cache_hits = int(result.cache_hits or 0)

        # Calculate hit rate
        if total_requests > 0:
            cache_hit_rate = cache_hits / total_requests
        else:
            cache_hit_rate = 0.0

        logger.debug(
            f"Cache hit rate ({hours}h): {cache_hit_rate:.2%} "
            f"({cache_hits}/{total_requests})"
        )

        return {
            "cache_hit_rate": round(cache_hit_rate, 4),
            "total_requests": total_requests,
            "cache_hits": cache_hits
        }

    except Exception as e:
        logger.error(f"Failed to get cache hit rate: {e}", exc_info=True)
        raise


async def check_cost_alerts(
    db: Session,
    daily_budget: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Check for budget threshold violations.

    Args:
        db: Database session
        daily_budget: Daily budget limit in USD (default: $10.00)

    Returns:
        List of alert dictionaries with:
        - severity: "info", "warning", "critical", "error"
        - message: Human-readable alert message
        - current_spend: Current spending amount

    Thresholds:
    - 80%+ of budget: WARNING
    - 95%+ of budget: CRITICAL
    - 100%+ of budget: ERROR

    Example:
        [
            {
                "severity": "warning",
                "message": "Daily spend at 85% of budget",
                "current_spend": 8.50
            }
        ]
    """
    try:
        # Get today's spend
        today = datetime.utcnow().date()
        daily_spend_result = await get_daily_spend(db, date=today)
        current_spend = daily_spend_result["total_cost_usd"]

        alerts = []

        # Calculate budget utilization
        if daily_budget > 0:
            utilization = current_spend / daily_budget
        else:
            utilization = 0.0

        # Check thresholds
        if utilization >= 1.0:
            # Budget exceeded
            alerts.append({
                "severity": "critical",
                "message": (
                    f"Daily budget exceeded! Current spend: ${current_spend:.4f} "
                    f"(Budget: ${daily_budget:.2f}, {utilization:.1%})"
                ),
                "current_spend": current_spend,
                "budget": daily_budget,
                "utilization": round(utilization, 4)
            })
        elif utilization >= 0.95:
            # Critical threshold
            alerts.append({
                "severity": "critical",
                "message": (
                    f"Daily spend at {utilization:.1%} of budget "
                    f"(${current_spend:.4f}/${daily_budget:.2f})"
                ),
                "current_spend": current_spend,
                "budget": daily_budget,
                "utilization": round(utilization, 4)
            })
        elif utilization >= 0.80:
            # Warning threshold
            alerts.append({
                "severity": "warning",
                "message": (
                    f"Daily spend at {utilization:.1%} of budget "
                    f"(${current_spend:.4f}/${daily_budget:.2f})"
                ),
                "current_spend": current_spend,
                "budget": daily_budget,
                "utilization": round(utilization, 4)
            })
        else:
            # Within budget
            alerts.append({
                "severity": "info",
                "message": (
                    f"Daily spend within budget: ${current_spend:.4f}/${daily_budget:.2f} "
                    f"({utilization:.1%})"
                ),
                "current_spend": current_spend,
                "budget": daily_budget,
                "utilization": round(utilization, 4)
            })

        logger.info(
            f"Cost alerts checked: {len(alerts)} alerts, "
            f"current_spend=${current_spend:.4f}, budget=${daily_budget:.2f}"
        )

        return alerts

    except Exception as e:
        logger.error(f"Failed to check cost alerts: {e}", exc_info=True)
        raise
