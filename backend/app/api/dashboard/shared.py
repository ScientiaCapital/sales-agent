"""
Dashboard Shared Utilities
===========================
Common utilities, Close CRM API helpers, and Supabase client.

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
import os
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Close CRM API configuration
CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
CLOSE_API_BASE = "https://api.close.com/api/v1"

# Business Metrics Configuration (Override via environment variables)
ESTIMATED_COST_PER_LEAD = float(os.getenv("DASHBOARD_COST_PER_LEAD", "0.002"))
ESTIMATED_AVG_DEAL_SIZE = float(os.getenv("DASHBOARD_AVG_DEAL_SIZE", "15000"))
ESTIMATED_QUALIFICATION_TIME_MS = float(os.getenv("DASHBOARD_AVG_QUALIFICATION_MS", "850"))

# Post-pivot date (Sep 9, 2025 - strategic pivot date)
POST_PIVOT_DATE = os.getenv("DASHBOARD_POST_PIVOT_DATE", "2025-09-09")

# Fiscal quarter definitions for 2025
FISCAL_QUARTERS = {
    "Q3_2025": {"start": "2025-07-01", "end": "2025-09-30", "label": "Q3 2025"},
    "Q4_2025": {"start": "2025-10-01", "end": "2025-12-31", "label": "Q4 2025"},
}

# Cache TTL in seconds (5 minutes - balance between freshness and performance)
CLOSE_CACHE_TTL = int(os.getenv("CLOSE_CACHE_TTL_SECONDS", "300"))

# In-memory cache for Close CRM opportunities
_close_opportunities_cache: Dict[str, Any] = {
    "data": [],
    "last_fetched": None,
}


# ============================================================================
# Close CRM API Helper (with caching)
# ============================================================================
def fetch_close_opportunities_filtered(
    status_type: str = None,
    date_won_gte: str = None,
    date_won_lte: str = None,
    date_lost_gte: str = None,
    date_lost_lte: str = None,
    force_refresh: bool = False,
    aggregate_only: bool = False
) -> Tuple[List[Dict], Dict]:
    """
    Fetch opportunities from Close CRM API with server-side filtering.

    Uses Close's native filtering to reduce API calls and data transfer.
    Close API returns aggregates (total_value, total_results) in response.

    Args:
        status_type: Filter by status ('won', 'lost', 'active') or None for all
        date_won_gte: Filter won deals on/after this date (YYYY-MM-DD)
        date_won_lte: Filter won deals on/before this date (YYYY-MM-DD)
        date_lost_gte: Filter lost deals on/after this date (YYYY-MM-DD)
        date_lost_lte: Filter lost deals on/before this date (YYYY-MM-DD)
        force_refresh: If True, bypass cache
        aggregate_only: If True, skip pagination and just return aggregates (faster!)

    Returns:
        Tuple of (list of opportunities, aggregates dict)
    """
    global _close_opportunities_cache

    if not CLOSE_API_KEY:
        logger.warning("CLOSE_API_KEY not configured - cannot fetch opportunities")
        return [], {}

    # Build cache key based on filters
    cache_key = f"{status_type}_{date_won_gte}_{date_won_lte}_{date_lost_gte}_{date_lost_lte}_{aggregate_only}"

    # Check cache
    if not force_refresh:
        cached = _close_opportunities_cache.get(cache_key)
        if cached:
            last_fetched = cached.get("last_fetched")
            if last_fetched:
                cache_age = (datetime.now(timezone.utc) - last_fetched).total_seconds()
                if cache_age < CLOSE_CACHE_TTL:
                    logger.debug(f"Using cached Close opportunities for {cache_key} ({cache_age:.0f}s old)")
                    return cached.get("data", []), cached.get("aggregates", {})

    all_opps = []
    aggregates = {}
    cursor = None

    try:
        while True:
            # For aggregate_only, just fetch 1 record to get totals
            params = {"_limit": 1 if aggregate_only else 100}
            if status_type:
                params["status_type"] = status_type
            if date_won_gte:
                params["date_won__gte"] = date_won_gte
            if date_won_lte:
                params["date_won__lte"] = date_won_lte
            if date_lost_gte:
                params["date_lost__gte"] = date_lost_gte
            if date_lost_lte:
                params["date_lost__lte"] = date_lost_lte
            if cursor:
                params["_cursor"] = cursor

            response = requests.get(
                f"{CLOSE_API_BASE}/opportunity/",
                auth=(CLOSE_API_KEY, ""),
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Close API error: {response.status_code} - {response.text}")
                break

            data = response.json()
            opps = data.get("data", [])

            # Capture aggregates from first response (Close returns these with list)
            if not aggregates:
                aggregates = {
                    "total_results": data.get("total_results", 0),
                    "total_value_one_time": data.get("total_value_one_time", 0) / 100,  # cents to dollars
                    "total_value_monthly": data.get("total_value_monthly", 0) / 100,
                    "total_value_annual": data.get("total_value_annual", 0) / 100,
                    "total_value_annualized": data.get("total_value_annualized", 0) / 100,
                }

            # Convert values from cents to dollars
            for opp in opps:
                if opp.get("value"):
                    opp["value_dollars"] = opp["value"] / 100
                else:
                    opp["value_dollars"] = 0

            all_opps.extend(opps)

            # For aggregate_only, break after first call (we have totals from response)
            if aggregate_only:
                logger.info(f"Got aggregates from Close CRM (status={status_type}, total={aggregates.get('total_results', 0)})")
                break

            if not data.get("has_more"):
                break
            cursor = data.get("cursor")

        logger.info(f"Fetched {len(all_opps)} opportunities from Close CRM (status={status_type}, won>={date_won_gte})")

        # Update cache
        _close_opportunities_cache[cache_key] = {
            "data": all_opps,
            "aggregates": aggregates,
            "last_fetched": datetime.now(timezone.utc)
        }

        return all_opps, aggregates

    except Exception as e:
        logger.error(f"Error fetching Close opportunities: {e}")
        # Return stale cache if available
        cached = _close_opportunities_cache.get(cache_key)
        if cached:
            logger.warning("Returning stale cache due to API error")
            return cached.get("data", []), cached.get("aggregates", {})
        return [], {}


def fetch_close_opportunities(status_type: str = None, force_refresh: bool = False) -> List[Dict]:
    """
    Legacy wrapper for backward compatibility.
    Fetches all opportunities without date filtering.
    """
    opps, _ = fetch_close_opportunities_filtered(status_type=status_type, force_refresh=force_refresh)
    return opps


# ============================================================================
# Supabase Client
# ============================================================================
_supabase_client = None


def get_supabase():
    """Get or create Supabase client for dashboard."""
    global _supabase_client

    if _supabase_client is None:
        from dotenv import load_dotenv
        load_dotenv()

        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError("supabase package not installed")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized for dashboard")

    return _supabase_client
