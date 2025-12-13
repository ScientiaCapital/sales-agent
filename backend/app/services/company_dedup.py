"""
Company Deduplication Helper
============================
Provides functions to safely upsert companies while preventing duplicates.

This module provides a safe abstraction layer for inserting/updating companies
that works both before and after migration 025_prevent_duplicates.sql is applied.

After the migration:
- Uses database RPC functions (sync_company_from_close, upsert_company)
- UNIQUE constraint on normalized_name enforces deduplication at DB level

Before the migration:
- Falls back to Python-based check-then-insert pattern
- Less safe but functional during transition period
"""

import os
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Common suffixes to strip for normalization
COMPANY_SUFFIXES = [
    r'\s+inc\.?$', r'\s+llc\.?$', r'\s+corp\.?$', r'\s+co\.?$',
    r'\s+ltd\.?$', r'\s+limited$', r'\s+incorporated$',
    r'\s+company$', r'\s+corporation$', r'\s+enterprises?$',
    r'\s+services?$', r'\s+systems?$', r'\s+solutions?$',
    r'\s+group$', r'\s+holdings?$', r',?\s+llc\.?$', r',?\s+inc\.?$',
    r'\s+pbc$', r'\s+dba\s+.*$',
]


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for comparison.

    This should match the normalize_company_name() function in migration 025.
    """
    if not name:
        return ""

    normalized = str(name).lower().strip()

    # Remove punctuation except hyphens
    normalized = re.sub(r'[^\w\s-]', '', normalized)

    # Strip common suffixes
    for suffix in COMPANY_SUFFIXES:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


async def upsert_company_safe(
    supabase_client,
    company_name: str,
    close_lead_id: Optional[str] = None,
    domain: Optional[str] = None,
    website: Optional[str] = None,
    phone: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    icp_score: Optional[int] = None,
    icp_tier: Optional[str] = None,
    source_type: str = 'api',
) -> Optional[str]:
    """
    Safely upsert a company, preventing duplicates.

    Returns the company_id (UUID string) of the inserted or existing company.

    First tries the RPC function (requires migration 025), falls back to
    Python-based check-then-insert if RPC not available.
    """
    try:
        # Try RPC function first (after migration 025)
        if close_lead_id:
            result = supabase_client.rpc(
                'sync_company_from_close',
                {
                    'p_close_lead_id': close_lead_id,
                    'p_company_name': company_name,
                    'p_domain': domain,
                    'p_website': website,
                    'p_phone': phone,
                    'p_city': city,
                    'p_state': state,
                    'p_zip': zip_code,
                    'p_icp_score': icp_score,
                    'p_icp_tier': icp_tier,
                }
            ).execute()
        else:
            result = supabase_client.rpc(
                'upsert_company',
                {
                    'p_company_name': company_name,
                    'p_domain': domain,
                    'p_website': website,
                    'p_phone': phone,
                    'p_city': city,
                    'p_state': state,
                    'p_zip': zip_code,
                    'p_icp_score': icp_score,
                    'p_icp_tier': icp_tier,
                    'p_source_type': source_type,
                }
            ).execute()

        if result.data:
            return str(result.data)
        return None

    except Exception as e:
        error_msg = str(e)
        # If RPC function doesn't exist, fall back to Python-based approach
        if 'function' in error_msg.lower() and ('not exist' in error_msg.lower() or '42883' in error_msg):
            logger.warning("RPC functions not available, using Python fallback")
            return await _upsert_company_python_fallback(
                supabase_client, company_name, close_lead_id, domain, website,
                phone, city, state, zip_code, icp_score, icp_tier, source_type
            )
        else:
            logger.error(f"Error upserting company: {e}")
            raise


async def _upsert_company_python_fallback(
    supabase_client,
    company_name: str,
    close_lead_id: Optional[str],
    domain: Optional[str],
    website: Optional[str],
    phone: Optional[str],
    city: Optional[str],
    state: Optional[str],
    zip_code: Optional[str],
    icp_score: Optional[int],
    icp_tier: Optional[str],
    source_type: str,
) -> Optional[str]:
    """
    Python-based check-then-insert pattern.

    Used when migration 025 hasn't been applied yet.
    Less safe due to race conditions, but functional.
    """
    normalized = normalize_company_name(company_name)

    # Check for existing by close_lead_id first
    if close_lead_id:
        result = supabase_client.table('dim_companies').select('company_id').eq(
            'close_lead_id', close_lead_id
        ).limit(1).execute()

        if result.data:
            company_id = result.data[0]['company_id']
            # Update the existing record
            supabase_client.table('dim_companies').update({
                'company_name': company_name,
                'normalized_name': normalized,
                'domain': domain,
                'website': website,
                'phone': phone,
                'city': city,
                'state': state,
                'zip': zip_code,
                'icp_score': icp_score,
                'icp_tier': icp_tier,
            }).eq('company_id', company_id).execute()
            return company_id

    # Check for existing by normalized name
    result = supabase_client.table('dim_companies').select('company_id').eq(
        'normalized_name', normalized
    ).limit(1).execute()

    if result.data:
        company_id = result.data[0]['company_id']
        # Update with new data if we have better info
        update_data = {}
        if close_lead_id:
            update_data['close_lead_id'] = close_lead_id
        if domain:
            update_data['domain'] = domain
        if website:
            update_data['website'] = website
        if phone:
            update_data['phone'] = phone
        if city:
            update_data['city'] = city
        if state:
            update_data['state'] = state
        if icp_score:
            update_data['icp_score'] = icp_score
        if icp_tier:
            update_data['icp_tier'] = icp_tier

        if update_data:
            supabase_client.table('dim_companies').update(update_data).eq(
                'company_id', company_id
            ).execute()

        return company_id

    # Insert new company
    insert_data = {
        'company_name': company_name,
        'normalized_name': normalized,
        'close_lead_id': close_lead_id,
        'domain': domain,
        'website': website,
        'phone': phone,
        'city': city,
        'state': state,
        'zip': zip_code,
        'icp_score': icp_score,
        'icp_tier': icp_tier,
        'source_type': source_type,
    }
    # Remove None values
    insert_data = {k: v for k, v in insert_data.items() if v is not None}

    result = supabase_client.table('dim_companies').insert(insert_data).execute()

    if result.data:
        return result.data[0]['company_id']

    return None


def sync_upsert_company_safe(
    supabase_client,
    company_name: str,
    close_lead_id: Optional[str] = None,
    domain: Optional[str] = None,
    website: Optional[str] = None,
    phone: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    icp_score: Optional[int] = None,
    icp_tier: Optional[str] = None,
    source_type: str = 'api',
) -> Optional[str]:
    """
    Synchronous version of upsert_company_safe.

    Use this in non-async contexts.
    """
    try:
        # Try RPC function first
        if close_lead_id:
            result = supabase_client.rpc(
                'sync_company_from_close',
                {
                    'p_close_lead_id': close_lead_id,
                    'p_company_name': company_name,
                    'p_domain': domain,
                    'p_website': website,
                    'p_phone': phone,
                    'p_city': city,
                    'p_state': state,
                    'p_zip': zip_code,
                    'p_icp_score': icp_score,
                    'p_icp_tier': icp_tier,
                }
            ).execute()
        else:
            result = supabase_client.rpc(
                'upsert_company',
                {
                    'p_company_name': company_name,
                    'p_domain': domain,
                    'p_website': website,
                    'p_phone': phone,
                    'p_city': city,
                    'p_state': state,
                    'p_zip': zip_code,
                    'p_icp_score': icp_score,
                    'p_icp_tier': icp_tier,
                    'p_source_type': source_type,
                }
            ).execute()

        if result.data:
            return str(result.data)
        return None

    except Exception as e:
        error_msg = str(e)
        # If RPC function doesn't exist, fall back to Python approach
        if 'function' in error_msg.lower() and ('not exist' in error_msg.lower() or '42883' in error_msg):
            logger.warning("RPC functions not available, using Python fallback")
            return _sync_upsert_company_python_fallback(
                supabase_client, company_name, close_lead_id, domain, website,
                phone, city, state, zip_code, icp_score, icp_tier, source_type
            )
        else:
            logger.error(f"Error upserting company: {e}")
            raise


def _sync_upsert_company_python_fallback(
    supabase_client,
    company_name: str,
    close_lead_id: Optional[str],
    domain: Optional[str],
    website: Optional[str],
    phone: Optional[str],
    city: Optional[str],
    state: Optional[str],
    zip_code: Optional[str],
    icp_score: Optional[int],
    icp_tier: Optional[str],
    source_type: str,
) -> Optional[str]:
    """Synchronous Python fallback."""
    normalized = normalize_company_name(company_name)

    # Check for existing by close_lead_id first
    if close_lead_id:
        result = supabase_client.table('dim_companies').select('company_id').eq(
            'close_lead_id', close_lead_id
        ).limit(1).execute()

        if result.data:
            company_id = result.data[0]['company_id']
            supabase_client.table('dim_companies').update({
                'company_name': company_name,
                'normalized_name': normalized,
                'domain': domain,
                'website': website,
                'phone': phone,
                'city': city,
                'state': state,
                'zip': zip_code,
                'icp_score': icp_score,
                'icp_tier': icp_tier,
            }).eq('company_id', company_id).execute()
            return company_id

    # Check for existing by normalized name
    result = supabase_client.table('dim_companies').select('company_id').eq(
        'normalized_name', normalized
    ).limit(1).execute()

    if result.data:
        company_id = result.data[0]['company_id']
        update_data = {}
        if close_lead_id:
            update_data['close_lead_id'] = close_lead_id
        if domain:
            update_data['domain'] = domain
        if website:
            update_data['website'] = website
        if phone:
            update_data['phone'] = phone
        if city:
            update_data['city'] = city
        if state:
            update_data['state'] = state
        if icp_score:
            update_data['icp_score'] = icp_score
        if icp_tier:
            update_data['icp_tier'] = icp_tier

        if update_data:
            supabase_client.table('dim_companies').update(update_data).eq(
                'company_id', company_id
            ).execute()

        return company_id

    # Insert new
    insert_data = {
        'company_name': company_name,
        'normalized_name': normalized,
        'close_lead_id': close_lead_id,
        'domain': domain,
        'website': website,
        'phone': phone,
        'city': city,
        'state': state,
        'zip': zip_code,
        'icp_score': icp_score,
        'icp_tier': icp_tier,
        'source_type': source_type,
    }
    insert_data = {k: v for k, v in insert_data.items() if v is not None}

    result = supabase_client.table('dim_companies').insert(insert_data).execute()

    if result.data:
        return result.data[0]['company_id']

    return None
