"""
ICP Scorer Service
==================
Pure Python service for calculating ICP scores and tiers.

Extracted from create_gold_standard_lists.py for use by Celery tasks
when lead data is enriched by agents or manual BDR updates.

Author: Claude + Tim
Date: Dec 3, 2025
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# ============================================================================
# Supabase Client (local to avoid circular imports)
# ============================================================================
_supabase_client = None


def get_supabase_client():
    """
    Get or create Supabase client for ICP scoring.

    Returns:
        Supabase client instance

    Raises:
        RuntimeError: If Supabase credentials not configured
    """
    global _supabase_client

    if _supabase_client is None:
        import os
        from dotenv import load_dotenv
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
        logger.info("Supabase client initialized for ICP scoring")

    return _supabase_client

# ============================================================================
# OEM Keywords for ICP scoring (case-insensitive matching)
# ============================================================================
SCHNEIDER_KEYWORDS = ['schneider', 'square d', 'apc']
GENERAC_KEYWORDS = ['generac']
CARRIER_KEYWORDS = ['carrier', 'bryant', 'payne']
TRANE_KEYWORDS = ['trane', 'american standard']
MITSUBISHI_KEYWORDS = ['mitsubishi']

# ============================================================================
# IDEAL STATES for MEP+Energy Contractors (priority markets)
# ============================================================================
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


def calculate_icp_score(company: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calculate ICP score and tier for a company.

    Tim's ICP scoring formula (max ~115 points):
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

    # =========================================================================
    # CONTACT QUALITY (25 points)
    # =========================================================================
    phone = company.get('phone') or ''
    email = company.get('email') or ''

    has_phone = bool(phone and str(phone).strip())
    has_email = bool(email and '@' in str(email))

    if has_phone:
        score += 20
    if has_email:
        score += 5

    # =========================================================================
    # MULTI-CAPABILITY SIGNALS (38 points)
    # =========================================================================

    # Multi-OEM (up to 15 points)
    oem_brands = company.get('oem_brands') or []
    if isinstance(oem_brands, str):
        oem_brands = [b.strip() for b in oem_brands.split(',') if b.strip()]
    oem_count = company.get('oem_count') or len(oem_brands)
    score += min(oem_count * 5, 15)

    # Multi-Trade (up to 12 points)
    trade_count = company.get('trade_count') or 0
    score += min(trade_count * 3, 12)

    # Self-performing bonus (3 points)
    # Inferred from having multiple trades and not being a GC
    is_self_performing = trade_count >= 2
    if is_self_performing:
        score += 3

    # Multi-Location (up to 8 points)
    location_count = company.get('location_count') or 1
    if location_count > 1:
        score += min(location_count * 4, 8)

    # =========================================================================
    # OEM CERTIFICATION (20 points)
    # =========================================================================
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

    # =========================================================================
    # BUSINESS MATURITY (20 points)
    # =========================================================================

    # Website/Domain (5 points)
    has_website = bool(company.get('domain') or company.get('website'))
    if has_website:
        score += 5

    # Employee tier (5 points)
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

    # Rating (5 points)
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

    # Review count (5 points)
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

    # =========================================================================
    # IDEAL STATE BONUS (up to 15 points)
    # =========================================================================
    state = str(company.get('state') or '').strip().upper()
    if len(state) > 2:
        state = state[:2]
    state_bonus = IDEAL_STATE_SCORES.get(state, 0)
    score += state_bonus

    # =========================================================================
    # DETERMINE TIER
    # =========================================================================
    tier = determine_tier(score, has_phone, has_email, is_oem_certified)

    return round(score, 1), tier


def determine_tier(score: float, has_phone: bool, has_email: bool, is_oem_certified: bool) -> str:
    """
    Determine tier based on score and contact quality.

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


async def check_and_update_icp(company_id: UUID) -> Dict[str, Any]:
    """
    Check if company needs ICP recalculation, update if changed.

    Args:
        company_id: UUID of the company to check

    Returns:
        {
            "changed": bool,
            "old_score": float,
            "new_score": float,
            "old_tier": str,
            "new_tier": str,
            "tier_upgraded": bool
        }
    """
    supabase = get_supabase_client()

    # Fetch company data
    result = supabase.table('dim_companies').select('*').eq(
        'company_id', str(company_id)
    ).execute()

    if not result.data:
        logger.warning(f"Company not found: {company_id}")
        return {"changed": False, "error": "Company not found"}

    company = result.data[0]
    old_score = company.get('icp_score') or 0
    old_tier = company.get('icp_tier') or 'LEAD'

    # Calculate new score
    new_score, new_tier = calculate_icp_score(company)

    # Check if changed
    score_changed = abs(new_score - old_score) >= 0.1
    tier_changed = new_tier != old_tier

    if not score_changed and not tier_changed:
        # Just update the last checked timestamp
        supabase.table('dim_companies').update({
            'icp_last_checked': datetime.now(timezone.utc).isoformat()
        }).eq('company_id', str(company_id)).execute()

        return {
            "changed": False,
            "old_score": old_score,
            "new_score": new_score,
            "old_tier": old_tier,
            "new_tier": new_tier,
            "tier_upgraded": False
        }

    # Update the company (cast scores to int for Supabase integer column)
    supabase.table('dim_companies').update({
        'icp_score': int(new_score),
        'icp_tier': new_tier,
        'icp_score_previous': int(old_score) if old_score else 0,
        'icp_last_checked': datetime.now(timezone.utc).isoformat()
    }).eq('company_id', str(company_id)).execute()

    # Determine if tier upgraded
    tier_order = ['LEAD', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
    old_idx = tier_order.index(old_tier) if old_tier in tier_order else 0
    new_idx = tier_order.index(new_tier) if new_tier in tier_order else 0
    tier_upgraded = new_idx > old_idx

    logger.info(
        f"ICP updated for {company.get('company_name', company_id)}: "
        f"{old_score} ({old_tier}) -> {new_score} ({new_tier})"
        f"{' UPGRADED!' if tier_upgraded else ''}"
    )

    return {
        "changed": True,
        "old_score": old_score,
        "new_score": new_score,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "tier_upgraded": tier_upgraded,
        "company_name": company.get('company_name'),
        "company_id": str(company_id)
    }


async def batch_check_icp(limit: int = 100) -> Dict[str, Any]:
    """
    Check ICP for recently modified companies.

    Queries companies where updated_at > icp_last_checked (or never checked).

    Args:
        limit: Maximum number of companies to check

    Returns:
        {
            "checked": int,
            "changed": int,
            "upgrades": List[{company_id, company_name, old_tier, new_tier}]
        }
    """
    supabase = get_supabase_client()

    # Query companies that need checking:
    # 1. Never checked (icp_last_checked is null)
    # 2. Updated since last check (updated_at > icp_last_checked)
    # Note: PostgREST doesn't support column-to-column comparisons,
    # so we fetch all recent and filter in Python
    result = supabase.table('dim_companies').select(
        'company_id, company_name, updated_at, icp_last_checked'
    ).order('updated_at', desc=True).limit(limit * 2).execute()  # Fetch extra to filter

    # Filter for companies needing check: null or updated_at > icp_last_checked
    from datetime import datetime
    all_companies = result.data or []
    companies_to_check = []
    for c in all_companies:
        if c.get('icp_last_checked') is None:
            companies_to_check.append(c)
        elif c.get('updated_at') and c.get('icp_last_checked'):
            # Compare timestamps
            updated = c['updated_at']
            checked = c['icp_last_checked']
            if updated > checked:
                companies_to_check.append(c)
        if len(companies_to_check) >= limit:
            break

    if not companies_to_check:
        logger.info("No companies need ICP rechecking")
        return {"checked": 0, "changed": 0, "upgrades": []}

    logger.info(f"Checking ICP for {len(companies_to_check)} companies...")

    checked = 0
    changed = 0
    upgrades = []

    for company in companies_to_check:
        company_id = company['company_id']
        try:
            result = await check_and_update_icp(UUID(company_id))
            checked += 1

            if result.get('changed'):
                changed += 1

                if result.get('tier_upgraded'):
                    upgrades.append({
                        'company_id': company_id,
                        'company_name': result.get('company_name', company.get('company_name')),
                        'old_tier': result['old_tier'],
                        'new_tier': result['new_tier'],
                        'old_score': result['old_score'],
                        'new_score': result['new_score']
                    })
        except Exception as e:
            logger.error(f"Error checking ICP for {company_id}: {e}")

    logger.info(f"ICP batch check complete: {checked} checked, {changed} changed, {len(upgrades)} upgrades")

    return {
        "checked": checked,
        "changed": changed,
        "upgrades": upgrades
    }


async def get_icp_stats() -> Dict[str, Any]:
    """
    Get current ICP tier distribution and stats.

    Returns:
        {
            "total": int,
            "by_tier": {"PLATINUM": int, "GOLD": int, ...},
            "avg_score": float,
            "needs_recheck": int
        }
    """
    supabase = get_supabase_client()

    # Get total and tier distribution
    result = supabase.table('dim_companies').select(
        'icp_tier', count='exact'
    ).execute()

    total = result.count or 0

    # Get tier counts
    tier_counts = {}
    for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
        tier_result = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('icp_tier', tier).execute()
        tier_counts[tier] = tier_result.count or 0

    # Get average score
    score_result = supabase.table('dim_companies').select('icp_score').execute()
    scores = [c.get('icp_score') or 0 for c in (score_result.data or [])]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Get count needing recheck
    recheck_result = supabase.table('dim_companies').select(
        'company_id', count='exact'
    ).or_(
        'icp_last_checked.is.null,updated_at.gt.icp_last_checked'
    ).execute()
    needs_recheck = recheck_result.count or 0

    return {
        "total": total,
        "by_tier": tier_counts,
        "avg_score": round(avg_score, 1),
        "needs_recheck": needs_recheck
    }
