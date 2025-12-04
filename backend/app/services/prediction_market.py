"""
Prediction Market Service
=========================
Algorithmic lead ranking service for prioritizing follow-up calls.

Uses multi-factor scoring to rank leads by conversion probability,
combining ICP score, revenue potential, momentum signals, and recency.

Formula:
    prediction_score = (icp_score × 0.35) + (revenue_potential × 0.25) +
                       (momentum_score × 0.25) + (recency_boost × 0.15)

Author: Claude + Tim
Date: Dec 3, 2025
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ============================================================================
# Supabase Client (local to avoid circular imports)
# ============================================================================
_supabase_client = None


def get_supabase_client():
    """Get or create Supabase client for prediction market."""
    global _supabase_client

    if _supabase_client is None:
        load_dotenv()

        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError("supabase package not installed. Run: pip install supabase")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized for prediction market")

    return _supabase_client


# ============================================================================
# Signal Weights (for momentum scoring)
# ============================================================================
SIGNAL_WEIGHTS = {
    'phone_added': 2.0,      # Direct phone discovered
    'email_added': 1.5,      # Email discovered
    'stage_change': 1.5,     # Lead progressed (COLD→WARM→HOT)
    'enrichment': 1.0,       # New data from any agent
    'bdr_note': 1.2,         # Manual BDR activity
    'email_open': 1.3,       # Outreach engagement
    'tier_upgrade': 1.8,     # ICP tier improved
}

# Revenue multipliers by employee count
REVENUE_EMPLOYEE_TIERS = [
    (100, 1.0),    # 100+ employees = full score
    (50, 0.7),     # 50-99 employees
    (20, 0.5),     # 20-49 employees
    (10, 0.3),     # 10-19 employees
    (0, 0.1),      # < 10 employees
]


# ============================================================================
# MOMENTUM SCORING
# ============================================================================

async def calculate_momentum_score(company_id: UUID) -> float:
    """
    Calculate momentum score from recent signals.

    Queries fact_lead_signals for company, applies weights,
    decays older signals (half-life = 3 days).

    Args:
        company_id: UUID of the company

    Returns:
        momentum_score (0-100)
    """
    supabase = get_supabase_client()

    # Query active signals (not expired)
    now = datetime.now(timezone.utc)
    result = supabase.table('fact_lead_signals').select(
        'signal_type, weight, created_at'
    ).eq(
        'company_id', str(company_id)
    ).gte(
        'expires_at', now.isoformat()
    ).execute()

    signals = result.data or []

    if not signals:
        return 0.0

    total_score = 0.0
    half_life_days = 3.0

    for signal in signals:
        # Get base weight from signal config
        signal_type = signal.get('signal_type', 'unknown')
        base_weight = SIGNAL_WEIGHTS.get(signal_type, 1.0)

        # Apply custom weight multiplier from signal
        custom_weight = signal.get('weight', 1.0)
        weight = base_weight * custom_weight

        # Apply time decay (half-life = 3 days)
        created_at_str = signal.get('created_at')
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                days_old = (now - created_at).total_seconds() / 86400
                decay_factor = 0.5 ** (days_old / half_life_days)
                weight *= decay_factor
            except (ValueError, TypeError):
                pass

        total_score += weight

    # Normalize to 0-100 range (cap at 10 weighted signals)
    max_possible = 10 * 2.0  # 10 signals at weight 2.0
    normalized = min(100.0, (total_score / max_possible) * 100)

    return round(normalized, 1)


# ============================================================================
# REVENUE POTENTIAL
# ============================================================================

async def calculate_revenue_potential(company: Dict[str, Any]) -> float:
    """
    Estimate revenue potential from company attributes.

    Factors:
    - employee_count (larger = bigger deal)
    - oem_count (more = multi-location/complex)
    - multi_location (more states = bigger footprint)
    - icp_tier (higher tier = better fit)

    Args:
        company: Dict with company data from dim_companies

    Returns:
        revenue_score (0-100)
    """
    score = 0.0

    # Employee count factor (up to 40 points)
    try:
        emp = int(company.get('employee_count') or 0)
        for threshold, multiplier in REVENUE_EMPLOYEE_TIERS:
            if emp >= threshold:
                score += 40 * multiplier
                break
    except (ValueError, TypeError):
        pass

    # OEM count factor (up to 20 points)
    # More OEMs = more complex installations = higher deal value
    oem_brands = company.get('oem_brands') or []
    if isinstance(oem_brands, str):
        oem_brands = [b.strip() for b in oem_brands.split(',') if b.strip()]
    oem_count = company.get('oem_count') or len(oem_brands)
    score += min(oem_count * 5, 20)

    # Multi-location factor (up to 20 points)
    location_count = company.get('location_count') or 1
    if location_count > 1:
        score += min(location_count * 5, 20)

    # ICP tier bonus (up to 20 points)
    tier_bonus = {
        'PLATINUM': 20,
        'GOLD': 15,
        'SILVER': 10,
        'BRONZE': 5,
        'LEAD': 0,
    }
    icp_tier = company.get('icp_tier', 'LEAD')
    score += tier_bonus.get(icp_tier, 0)

    return round(min(score, 100.0), 1)


# ============================================================================
# RECENCY BOOST
# ============================================================================

def calculate_recency_boost(company: Dict[str, Any]) -> float:
    """
    Calculate recency boost based on when lead was last updated.

    Newer leads get higher scores to prioritize fresh opportunities.

    Args:
        company: Dict with company data

    Returns:
        recency_score (0-100)
    """
    updated_at_str = company.get('updated_at')
    if not updated_at_str:
        return 0.0

    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days_old = (now - updated_at).total_seconds() / 86400

        # Score decays over 30 days
        if days_old <= 1:
            return 100.0
        elif days_old <= 7:
            return 80.0
        elif days_old <= 14:
            return 60.0
        elif days_old <= 30:
            return 40.0
        else:
            return max(0.0, 100 - (days_old * 2))

    except (ValueError, TypeError):
        return 0.0


# ============================================================================
# PREDICTION SCORE (Main Formula)
# ============================================================================

async def calculate_prediction_score(company: Dict[str, Any]) -> float:
    """
    Calculate overall prediction score.

    Formula:
        prediction_score =
            (icp_score × 0.35)           # Quality
          + (revenue_potential × 0.25)   # Size/deal value
          + (momentum_score × 0.25)      # Recent activity
          + (recency_boost × 0.15)       # Freshness

    Args:
        company: Dict with company data from dim_companies

    Returns:
        prediction_score (0-100)
    """
    company_id = company.get('company_id')

    # Get ICP score (normalized to 0-100 from max ~115)
    icp_score = company.get('icp_score') or 0
    icp_normalized = min(100, (icp_score / 115) * 100)

    # Calculate component scores
    revenue_potential = await calculate_revenue_potential(company)
    recency_boost = calculate_recency_boost(company)

    # Calculate momentum (requires company_id)
    momentum_score = 0.0
    if company_id:
        try:
            momentum_score = await calculate_momentum_score(UUID(company_id))
        except (ValueError, TypeError):
            pass

    # Apply weights
    prediction_score = (
        (icp_normalized * 0.35) +
        (revenue_potential * 0.25) +
        (momentum_score * 0.25) +
        (recency_boost * 0.15)
    )

    return round(prediction_score, 1)


# ============================================================================
# RANKINGS UPDATE
# ============================================================================

async def update_rankings(limit: int = 1000) -> Dict[str, Any]:
    """
    Recalculate and update prediction rankings for all active leads.

    Updates dim_companies:
    - prediction_score
    - prediction_rank
    - prediction_updated_at

    Args:
        limit: Maximum number of companies to rank

    Returns:
        {
            "updated": int,
            "top_10": List[{company_id, company_name, rank, score}]
        }
    """
    supabase = get_supabase_client()

    # Query active companies (with domain and ICP score > 0)
    result = supabase.table('dim_companies').select(
        'company_id, company_name, domain, icp_score, icp_tier, '
        'employee_count, oem_brands, oem_count, location_count, updated_at'
    ).not_.is_(
        'domain', 'null'
    ).gt(
        'icp_score', 0
    ).order('icp_score', desc=True).limit(limit).execute()

    companies = result.data or []

    if not companies:
        logger.info("No companies found for prediction ranking")
        return {"updated": 0, "top_10": []}

    logger.info(f"Calculating prediction scores for {len(companies)} companies...")

    # Calculate scores for all companies
    scored_companies = []
    for company in companies:
        try:
            score = await calculate_prediction_score(company)
            scored_companies.append({
                'company_id': company['company_id'],
                'company_name': company.get('company_name', 'Unknown'),
                'prediction_score': score
            })
        except Exception as e:
            logger.error(f"Error scoring {company.get('company_name')}: {e}")

    # Sort by score descending
    scored_companies.sort(key=lambda x: x['prediction_score'], reverse=True)

    # Assign ranks and update database
    now = datetime.now(timezone.utc).isoformat()
    updated = 0

    for rank, company in enumerate(scored_companies, start=1):
        try:
            supabase.table('dim_companies').update({
                'prediction_score': company['prediction_score'],
                'prediction_rank': rank,
                'prediction_updated_at': now
            }).eq('company_id', company['company_id']).execute()
            updated += 1
        except Exception as e:
            logger.error(f"Error updating rank for {company['company_id']}: {e}")

    # Get top 10 for return value
    top_10 = [
        {
            'company_id': c['company_id'],
            'company_name': c['company_name'],
            'rank': i + 1,
            'score': c['prediction_score']
        }
        for i, c in enumerate(scored_companies[:10])
    ]

    logger.info(f"Prediction rankings updated: {updated} companies ranked")

    return {
        "updated": updated,
        "top_10": top_10
    }


# ============================================================================
# SIGNAL LOGGING
# ============================================================================

async def log_signal(
    company_id: UUID,
    signal_type: str,
    signal_value: Dict[str, Any] = None,
    weight: float = 1.0
) -> None:
    """
    Log a momentum signal for a company.

    Called by other agents after significant events.

    Signal types: 'phone_added', 'email_added', 'stage_change',
                  'enrichment', 'bdr_note', 'email_open', 'tier_upgrade'

    Args:
        company_id: UUID of the company
        signal_type: Type of signal
        signal_value: Additional signal data (optional)
        weight: Custom weight multiplier (default 1.0)
    """
    supabase = get_supabase_client()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    signal_data = {
        'company_id': str(company_id),
        'signal_type': signal_type,
        'signal_value': signal_value or {},
        'weight': weight,
        'created_at': now.isoformat(),
        'expires_at': expires_at.isoformat()
    }

    try:
        supabase.table('fact_lead_signals').insert(signal_data).execute()
        logger.info(f"Logged signal '{signal_type}' for company {company_id}")
    except Exception as e:
        logger.error(f"Error logging signal for {company_id}: {e}")


# ============================================================================
# GET TOP LEADS
# ============================================================================

async def get_top_leads(limit: int = 10, include_why_now: bool = False) -> List[Dict[str, Any]]:
    """
    Get current top leads by prediction score.

    Args:
        limit: Number of leads to return (max 100)
        include_why_now: Include AI-generated reasoning (if available)

    Returns:
        List of lead dicts with ranking info
    """
    supabase = get_supabase_client()

    # Query top leads by prediction_rank
    result = supabase.table('dim_companies').select(
        'company_id, company_name, domain, phone, city, state, '
        'icp_score, icp_tier, prediction_score, prediction_rank, '
        'prediction_why_now, current_stage, ai_company_story'
    ).not_.is_(
        'prediction_rank', 'null'
    ).order('prediction_rank', desc=False).limit(min(limit, 100)).execute()

    leads = result.data or []

    # Format response
    formatted_leads = []
    for lead in leads:
        lead_data = {
            'rank': lead.get('prediction_rank'),
            'company_id': lead.get('company_id'),
            'company_name': lead.get('company_name'),
            'domain': lead.get('domain'),
            'phone': lead.get('phone'),
            'location': f"{lead.get('city', '')}, {lead.get('state', '')}".strip(', '),
            'icp_score': lead.get('icp_score'),
            'icp_tier': lead.get('icp_tier'),
            'prediction_score': lead.get('prediction_score'),
            'stage': lead.get('current_stage'),
        }

        if include_why_now:
            lead_data['why_now'] = lead.get('prediction_why_now') or 'No reasoning available'
            lead_data['company_story'] = lead.get('ai_company_story')

        formatted_leads.append(lead_data)

    return formatted_leads


# ============================================================================
# STATS
# ============================================================================

async def get_prediction_stats() -> Dict[str, Any]:
    """
    Get prediction market statistics.

    Returns:
        {
            "total_ranked": int,
            "avg_score": float,
            "top_score": float,
            "last_update": str
        }
    """
    supabase = get_supabase_client()

    # Get ranked companies
    result = supabase.table('dim_companies').select(
        'prediction_score, prediction_updated_at'
    ).not_.is_(
        'prediction_score', 'null'
    ).execute()

    companies = result.data or []

    if not companies:
        return {
            "total_ranked": 0,
            "avg_score": 0,
            "top_score": 0,
            "last_update": None
        }

    scores = [c.get('prediction_score', 0) for c in companies]
    updates = [c.get('prediction_updated_at') for c in companies if c.get('prediction_updated_at')]

    return {
        "total_ranked": len(companies),
        "avg_score": round(sum(scores) / len(scores), 1),
        "top_score": max(scores),
        "last_update": max(updates) if updates else None
    }
