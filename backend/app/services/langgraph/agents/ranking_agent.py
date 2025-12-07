"""
RankingAgent - Unified ICP Scoring + Prediction Ranking
========================================================
Merges ICPCheckerAgent + PredictionAgent into a single consolidated agent.

This agent handles two related but distinct tasks:
1. ICP Scoring - Calculate ICP scores and tiers based on contact quality
2. Prediction Ranking - Rank leads by conversion probability for calling list

Schedule: Every 10 minutes (consolidated from 15 min + 5 min)
Event Trigger: company_enriched (when new data is added)
Emits: tier_upgraded (when ICP tier improves to HOT status)

Pipeline:
    ┌─────────────────┐
    │ check_needs     │ ─── Query companies needing rank recalculation
    │   _rerank       │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ calculate_icp   │ ─── Apply ICP scoring algorithm
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ calculate       │ ─── Apply prediction formula
    │  _prediction    │     (ICP + revenue + momentum + recency)
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ assign_ranks    │ ─── Sort by prediction score, assign ranks
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ notify_upgrades │ ─── Emit tier_upgraded events for Slack
    └─────────────────┘

Author: Claude + Tim (Agent Consolidation Phase 1)
Date: Dec 7, 2025
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from uuid import UUID
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# Output Schemas
# ============================================================================

class RankingResult(BaseModel):
    """Result from a single company ranking."""
    company_id: str
    company_name: str
    old_icp_score: float
    new_icp_score: float
    old_icp_tier: str
    new_icp_tier: str
    prediction_score: float
    prediction_rank: Optional[int] = None
    tier_upgraded: bool = False
    processing_time_ms: int


class BatchRankingResult(BaseModel):
    """Result from batch ranking operation."""
    total_processed: int
    total_changed: int
    total_upgrades: int
    top_10: List[Dict[str, Any]]
    upgrades: List[Dict[str, Any]]
    processing_time_ms: int


# ============================================================================
# Supabase Client
# ============================================================================
_supabase_client = None


def get_supabase_client():
    """Get or create Supabase client."""
    global _supabase_client

    if _supabase_client is None:
        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError("supabase package not installed")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized for RankingAgent")

    return _supabase_client


# ============================================================================
# ICP Scoring Constants (from icp_scorer.py)
# ============================================================================

# OEM Keywords for ICP scoring
SCHNEIDER_KEYWORDS = ['schneider', 'square d', 'apc']
GENERAC_KEYWORDS = ['generac']
CARRIER_KEYWORDS = ['carrier', 'bryant', 'payne']
TRANE_KEYWORDS = ['trane', 'american standard']
MITSUBISHI_KEYWORDS = ['mitsubishi']

# Ideal states for MEP+Energy contractors
IDEAL_STATE_SCORES = {
    # Tier 1: SREC + High Volume (15 pts)
    'CA': 15, 'TX': 15, 'FL': 15,
    # Tier 2: SREC States (10-12 pts)
    'NJ': 12, 'MA': 12, 'MD': 10, 'PA': 10,
    # Tier 3: High-Growth Markets (8 pts)
    'NY': 8, 'AZ': 8, 'NV': 8, 'CO': 8, 'NC': 8,
    # Tier 4: Emerging Markets (5 pts)
    'GA': 5, 'VA': 5, 'OH': 5, 'IL': 5, 'CT': 5,
    'SC': 5, 'MN': 5, 'WI': 5, 'MI': 5, 'IN': 5,
}


# ============================================================================
# Prediction Market Constants (from prediction_market.py)
# ============================================================================

# Signal weights for momentum scoring
SIGNAL_WEIGHTS = {
    'phone_added': 2.0,      # Direct phone discovered
    'email_added': 1.5,      # Email discovered
    'stage_change': 1.5,     # Lead progressed
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
# ICP Scoring Functions
# ============================================================================

def calculate_icp_score(company: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calculate ICP score and tier for a company.

    Formula (max ~115 points):
    - Contact Quality: 25 pts (phone=20, email=5)
    - Multi-Capability: 38 pts (OEM, trade, location, self-performing)
    - OEM Certification: 20 pts (Schneider=10, Generac=5, Carrier=5)
    - Business Maturity: 20 pts (website, employees, rating, reviews)
    - Ideal State Bonus: 15 pts (based on state)

    Args:
        company: Dict with company data from dim_companies

    Returns:
        (score, tier) tuple where tier is PLATINUM/GOLD/SILVER/BRONZE/LEAD
    """
    score = 0.0

    # Contact Quality (25 points)
    phone = company.get('phone') or ''
    email = company.get('email') or ''

    has_phone = bool(phone and str(phone).strip())
    has_email = bool(email and '@' in str(email))

    if has_phone:
        score += 20
    if has_email:
        score += 5

    # Multi-Capability Signals (38 points)
    oem_brands = company.get('oem_brands') or []
    if isinstance(oem_brands, str):
        oem_brands = [b.strip() for b in oem_brands.split(',') if b.strip()]
    oem_count = company.get('oem_count') or len(oem_brands)
    score += min(oem_count * 5, 15)

    trade_count = company.get('trade_count') or 0
    score += min(trade_count * 3, 12)

    is_self_performing = trade_count >= 2
    if is_self_performing:
        score += 3

    location_count = company.get('location_count') or 1
    if location_count > 1:
        score += min(location_count * 4, 8)

    # OEM Certification (20 points)
    oem_text = ' '.join(str(b).lower() for b in oem_brands)
    certifications = company.get('certifications') or []
    if isinstance(certifications, str):
        certifications = [certifications]
    cert_text = ' '.join(str(c).lower() for c in certifications)
    combined_text = f"{oem_text} {cert_text}"

    is_schneider = any(kw in combined_text for kw in SCHNEIDER_KEYWORDS)
    is_generac = any(kw in combined_text for kw in GENERAC_KEYWORDS)
    is_carrier = any(kw in combined_text for kw in CARRIER_KEYWORDS)

    if is_schneider:
        score += 10
    if is_generac:
        score += 5
    if is_carrier:
        score += 5

    is_oem_certified = is_schneider or is_generac or is_carrier

    # Business Maturity (20 points)
    has_website = bool(company.get('domain') or company.get('website'))
    if has_website:
        score += 5

    try:
        emp = int(company.get('employee_count') or 0)
        if emp >= 100:
            score += 5
        elif emp >= 50:
            score += 3
        elif emp >= 10:
            score += 2
    except (ValueError, TypeError):
        pass

    try:
        rating = float(company.get('google_rating') or 0)
        if rating >= 4.5:
            score += 5
        elif rating >= 4.0:
            score += 3
        elif rating >= 3.5:
            score += 2
    except (ValueError, TypeError):
        pass

    try:
        reviews = int(company.get('google_review_count') or 0)
        if reviews >= 100:
            score += 5
        elif reviews >= 50:
            score += 3
        elif reviews >= 10:
            score += 2
    except (ValueError, TypeError):
        pass

    # Ideal State Bonus (up to 15 points)
    state = str(company.get('state') or '').strip().upper()
    if len(state) > 2:
        state = state[:2]
    state_bonus = IDEAL_STATE_SCORES.get(state, 0)
    score += state_bonus

    # Determine tier
    tier = determine_tier(score, has_phone, has_email, is_oem_certified)

    return round(score, 1), tier


def determine_tier(score: float, has_phone: bool, has_email: bool, is_oem_certified: bool) -> str:
    """
    Determine tier based on score and contact quality.

    Tiers:
    - PLATINUM (80+): Score + phone + OEM certified
    - GOLD (65+): Score + phone + email
    - SILVER (50+): Score + phone
    - BRONZE (35+): Score + (phone OR email)
    - LEAD: Default
    """
    if score >= 80 and has_phone and is_oem_certified:
        return 'PLATINUM'
    elif score >= 65 and has_phone and has_email:
        return 'GOLD'
    elif score >= 50 and has_phone:
        return 'SILVER'
    elif score >= 35 and (has_phone or has_email):
        return 'BRONZE'
    else:
        return 'LEAD'


# ============================================================================
# Prediction Market Functions
# ============================================================================

async def calculate_momentum_score(company_id: UUID) -> float:
    """
    Calculate momentum score from recent signals.

    Queries fact_lead_signals, applies weights, decays older signals.

    Args:
        company_id: UUID of the company

    Returns:
        momentum_score (0-100)
    """
    supabase = get_supabase_client()

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
        signal_type = signal.get('signal_type', 'unknown')
        base_weight = SIGNAL_WEIGHTS.get(signal_type, 1.0)
        custom_weight = signal.get('weight', 1.0)
        weight = base_weight * custom_weight

        # Apply time decay
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
    max_possible = 10 * 2.0
    normalized = min(100.0, (total_score / max_possible) * 100)

    return round(normalized, 1)


async def calculate_revenue_potential(company: Dict[str, Any]) -> float:
    """
    Estimate revenue potential from company attributes.

    Factors: employee_count, oem_count, multi_location, icp_tier

    Args:
        company: Dict with company data

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


def calculate_recency_boost(company: Dict[str, Any]) -> float:
    """
    Calculate recency boost based on when lead was last updated.

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
        company: Dict with company data

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

    # Calculate momentum
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
# RankingAgent - Main Class
# ============================================================================

class RankingAgent:
    """
    Unified agent for ICP scoring and prediction ranking.

    Consolidates:
    - ICPCheckerAgent (ICP scoring algorithm)
    - PredictionAgent (prediction market ranking)

    Usage:
        agent = RankingAgent()
        result = await agent.rank_company(company_id)
        batch_result = await agent.rank_batch(limit=100)
    """

    def __init__(self):
        """Initialize RankingAgent."""
        self.supabase = get_supabase_client()
        logger.info("RankingAgent initialized")

    async def rank_company(self, company_id: UUID) -> RankingResult:
        """
        Rank a single company (ICP + prediction).

        Pipeline:
        1. Fetch company data
        2. Calculate ICP score and tier
        3. Calculate prediction score
        4. Update database
        5. Return result with tier_upgraded flag

        Args:
            company_id: UUID of the company

        Returns:
            RankingResult with scores, tiers, and upgrade status
        """
        start_time = time.time()

        # Fetch company data
        result = self.supabase.table('dim_companies').select('*').eq(
            'company_id', str(company_id)
        ).execute()

        if not result.data:
            raise ValueError(f"Company not found: {company_id}")

        company = result.data[0]
        old_icp_score = company.get('icp_score') or 0
        old_icp_tier = company.get('icp_tier') or 'LEAD'

        # Calculate ICP
        new_icp_score, new_icp_tier = calculate_icp_score(company)

        # Update company dict with new ICP for prediction calculation
        company['icp_score'] = new_icp_score
        company['icp_tier'] = new_icp_tier

        # Calculate prediction score
        prediction_score = await calculate_prediction_score(company)

        # Update database
        now = datetime.now(timezone.utc).isoformat()
        self.supabase.table('dim_companies').update({
            'icp_score': int(new_icp_score),
            'icp_tier': new_icp_tier,
            'icp_score_previous': int(old_icp_score) if old_icp_score else 0,
            'icp_last_checked': now,
            'prediction_score': prediction_score,
            'prediction_updated_at': now
        }).eq('company_id', str(company_id)).execute()

        # Check for tier upgrade
        tier_order = ['LEAD', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
        old_idx = tier_order.index(old_icp_tier) if old_icp_tier in tier_order else 0
        new_idx = tier_order.index(new_icp_tier) if new_icp_tier in tier_order else 0
        tier_upgraded = new_idx > old_idx

        processing_time = int((time.time() - start_time) * 1000)

        return RankingResult(
            company_id=str(company_id),
            company_name=company.get('company_name', 'Unknown'),
            old_icp_score=old_icp_score,
            new_icp_score=new_icp_score,
            old_icp_tier=old_icp_tier,
            new_icp_tier=new_icp_tier,
            prediction_score=prediction_score,
            tier_upgraded=tier_upgraded,
            processing_time_ms=processing_time
        )

    async def rank_batch(self, limit: int = 100) -> BatchRankingResult:
        """
        Rank a batch of companies and assign global ranks.

        Pipeline:
        1. Query companies needing rerank
        2. Calculate ICP + prediction for each
        3. Sort by prediction score
        4. Assign global ranks
        5. Update database
        6. Return results with upgrades

        Args:
            limit: Maximum number of companies to rank

        Returns:
            BatchRankingResult with stats and top 10
        """
        start_time = time.time()

        # Query companies needing rerank
        # Priority: updated_at > icp_last_checked OR icp_last_checked is null
        result = self.supabase.table('dim_companies').select(
            'company_id, company_name, updated_at, icp_last_checked'
        ).order('updated_at', desc=True).limit(limit * 2).execute()

        # Filter for companies needing check
        all_companies = result.data or []
        companies_to_check = []
        for c in all_companies:
            if c.get('icp_last_checked') is None:
                companies_to_check.append(c)
            elif c.get('updated_at') and c.get('icp_last_checked'):
                updated = c['updated_at']
                checked = c['icp_last_checked']
                if updated > checked:
                    companies_to_check.append(c)
            if len(companies_to_check) >= limit:
                break

        if not companies_to_check:
            logger.info("No companies need reranking")
            return BatchRankingResult(
                total_processed=0,
                total_changed=0,
                total_upgrades=0,
                top_10=[],
                upgrades=[],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        logger.info(f"Ranking {len(companies_to_check)} companies...")

        # Rank each company
        ranked_companies = []
        total_changed = 0
        upgrades = []

        for company_meta in companies_to_check:
            company_id = company_meta['company_id']
            try:
                result = await self.rank_company(UUID(company_id))

                ranked_companies.append({
                    'company_id': result.company_id,
                    'company_name': result.company_name,
                    'prediction_score': result.prediction_score
                })

                if result.old_icp_score != result.new_icp_score:
                    total_changed += 1

                if result.tier_upgraded:
                    upgrades.append({
                        'company_id': result.company_id,
                        'company_name': result.company_name,
                        'old_tier': result.old_icp_tier,
                        'new_tier': result.new_icp_tier,
                        'old_score': result.old_icp_score,
                        'new_score': result.new_icp_score
                    })

            except Exception as e:
                logger.error(f"Error ranking {company_id}: {e}")

        # Sort by prediction score and assign ranks
        ranked_companies.sort(key=lambda x: x['prediction_score'], reverse=True)

        now = datetime.now(timezone.utc).isoformat()
        for rank, company in enumerate(ranked_companies, start=1):
            try:
                self.supabase.table('dim_companies').update({
                    'prediction_rank': rank,
                    'prediction_updated_at': now
                }).eq('company_id', company['company_id']).execute()
            except Exception as e:
                logger.error(f"Error updating rank for {company['company_id']}: {e}")

        # Get top 10
        top_10 = [
            {
                'company_id': c['company_id'],
                'company_name': c['company_name'],
                'rank': i + 1,
                'score': c['prediction_score']
            }
            for i, c in enumerate(ranked_companies[:10])
        ]

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"Batch ranking complete: {len(companies_to_check)} processed, "
            f"{total_changed} changed, {len(upgrades)} upgrades in {processing_time}ms"
        )

        return BatchRankingResult(
            total_processed=len(companies_to_check),
            total_changed=total_changed,
            total_upgrades=len(upgrades),
            top_10=top_10,
            upgrades=upgrades,
            processing_time_ms=processing_time
        )


# ============================================================================
# Convenience Functions
# ============================================================================

async def rank_single_company(company_id: UUID) -> Dict[str, Any]:
    """
    Convenience function to rank a single company.

    Args:
        company_id: UUID of the company

    Returns:
        Dict with ranking result
    """
    agent = RankingAgent()
    result = await agent.rank_company(company_id)
    return result.model_dump()


async def rank_companies_batch(limit: int = 100) -> Dict[str, Any]:
    """
    Convenience function to rank a batch of companies.

    Args:
        limit: Maximum companies to rank

    Returns:
        Dict with batch ranking result
    """
    agent = RankingAgent()
    result = await agent.rank_batch(limit)
    return result.model_dump()
