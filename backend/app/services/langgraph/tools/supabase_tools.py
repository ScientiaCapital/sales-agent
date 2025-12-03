"""
LangGraph tools for Supabase dim_companies integration

Provides LangChain-compatible tools for querying and updating leads
in the Supabase star schema (dim_companies, dim_contacts).

Tools:
- query_unenriched_leads: Get leads that need enrichment/scouting
- update_lead_recommendation: Update AI recommendation on a lead
- get_lead_details: Get full lead details by company_id
- query_leads_by_tier: Get leads by ICP tier (PLATINUM, GOLD, etc.)

Integration:
- Uses Supabase Python client (sync - wrapped for async)
- Connection via SUPABASE_URL and SUPABASE_SERVICE_KEY from env
- Tables: dim_companies, dim_contacts
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

logger = logging.getLogger(__name__)

# ========== Supabase Client Singleton ==========

_supabase_client = None


def get_supabase():
    """
    Get or create global Supabase client.

    Returns:
        Supabase client instance

    Raises:
        ToolException: If Supabase credentials not configured
    """
    global _supabase_client

    if _supabase_client is None:
        try:
            from supabase import create_client
        except ImportError:
            raise ToolException("supabase package not installed. Run: pip install supabase")

        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')

        if not url or not key:
            raise ToolException("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment")

        _supabase_client = create_client(url, key)
        logger.info("Initialized Supabase client")

    return _supabase_client


# ========== Pydantic Input Schemas ==========

class QueryLeadsInput(BaseModel):
    """Input schema for querying leads."""

    limit: int = Field(
        default=10,
        description="Maximum number of leads to return (1-50)"
    )
    require_domain: bool = Field(
        default=True,
        description="Only return leads with a website domain"
    )
    unenriched_only: bool = Field(
        default=True,
        description="Only return leads not yet enriched (last_enriched_at is null)"
    )
    icp_tier: Optional[str] = Field(
        default=None,
        description="Filter by ICP tier: PLATINUM, GOLD, SILVER, BRONZE"
    )


class UpdateRecommendationInput(BaseModel):
    """Input schema for updating AI recommendation."""

    company_id: str = Field(
        ...,
        description="UUID of the company in dim_companies"
    )
    recommendation: str = Field(
        ...,
        description="AI-generated recommendation explaining WHY to call this lead"
    )
    recommended_opener: Optional[str] = Field(
        default=None,
        description="Suggested opening line for the call"
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority level: HOT, WARM, COLD"
    )
    icp_score: Optional[float] = Field(
        default=None,
        description="ICP score (0-100)"
    )


class GetLeadInput(BaseModel):
    """Input schema for getting lead details."""

    company_id: str = Field(
        ...,
        description="UUID of the company in dim_companies"
    )
    include_contacts: bool = Field(
        default=True,
        description="Include related contacts from dim_contacts"
    )


# ========== LangChain Tools ==========

@tool("query_unenriched_leads", args_schema=QueryLeadsInput)
def query_unenriched_leads(
    limit: int = 10,
    require_domain: bool = True,
    unenriched_only: bool = True,
    icp_tier: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query dim_companies for leads that need enrichment or scouting.

    Returns leads with basic info: company_id, company_name, domain, icp_tier,
    atl_count, btl_count. Prioritizes leads with domains that haven't been enriched.

    Use this tool at the START of a scouting run to get leads to research.

    Args:
        limit: Maximum number of leads to return (1-50)
        require_domain: Only return leads with a website domain
        unenriched_only: Only return leads not yet enriched
        icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)

    Returns:
        List of lead dictionaries with company info

    Example:
        leads = query_unenriched_leads(limit=5, require_domain=True)
        # Returns: [{"company_id": "...", "company_name": "...", "domain": "..."}, ...]
    """
    try:
        supabase = get_supabase()

        # Clamp limit
        limit = max(1, min(limit, 50))

        # Build query - select key fields for scouting
        # Note: Using actual Supabase column names (phone not company_phone, etc.)
        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, normalized_name, '
            'icp_tier, icp_score, oem_count, trade_count, '
            'phone, state, city, industry, '
            'google_rating, google_review_count, events_attended, '
            'oem_brands, service_areas, certifications, '
            'last_enriched_at, ai_company_story, ai_personal_hooks'
        )

        # Apply filters
        if require_domain:
            query = query.not_.is_('domain', 'null')

        if unenriched_only:
            query = query.is_('last_enriched_at', 'null')

        if icp_tier:
            query = query.eq('icp_tier', icp_tier.upper())

        # Order by ICP score (highest first) and limit
        query = query.order('icp_score', desc=True).limit(limit)

        result = query.execute()

        logger.info(f"Queried {len(result.data)} leads (limit={limit}, unenriched={unenriched_only})")

        return result.data or []

    except Exception as e:
        logger.error(f"Error querying leads: {e}")
        raise ToolException(f"Failed to query leads: {str(e)}")


@tool("update_lead_recommendation", args_schema=UpdateRecommendationInput)
def update_lead_recommendation(
    company_id: str,
    recommendation: str,
    recommended_opener: Optional[str] = None,
    priority: Optional[str] = None,
    icp_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Update AI recommendation on a lead in dim_companies.

    Use this tool AFTER researching a lead to save the "WHY call this company"
    reasoning for Tim's calling list.

    Args:
        company_id: UUID of the company
        recommendation: AI-generated recommendation explaining WHY to call
        recommended_opener: Suggested opening line for the call
        priority: Priority level (HOT, WARM, COLD)
        icp_score: Updated ICP score (0-100)

    Returns:
        Updated company record

    Example:
        result = update_lead_recommendation(
            company_id="abc-123",
            recommendation="70-year HVAC company with ATL contact. NATE certified.",
            recommended_opener="Noticed you've been in business since 1950...",
            priority="HOT",
            icp_score=92.0
        )
    """
    try:
        supabase = get_supabase()

        # Build update data using actual Supabase column names
        update_data = {
            'ai_company_story': recommendation,
            'ai_enriched_at': datetime.now().isoformat()
        }

        if recommended_opener:
            update_data['ai_personal_hooks'] = recommended_opener

        if priority:
            update_data['current_stage'] = priority.upper()

        if icp_score is not None:
            update_data['icp_score'] = int(icp_score)  # Supabase expects integer
            # Auto-calculate tier from score
            if icp_score >= 80:
                update_data['icp_tier'] = 'PLATINUM'
            elif icp_score >= 65:
                update_data['icp_tier'] = 'GOLD'
            elif icp_score >= 50:
                update_data['icp_tier'] = 'SILVER'
            else:
                update_data['icp_tier'] = 'BRONZE'

        result = supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()

        if result.data:
            logger.info(f"Updated recommendation for company {company_id}")
            return result.data[0]
        else:
            raise ToolException(f"Company not found: {company_id}")

    except Exception as e:
        logger.error(f"Error updating recommendation: {e}")
        raise ToolException(f"Failed to update recommendation: {str(e)}")


@tool("get_lead_details", args_schema=GetLeadInput)
def get_lead_details(
    company_id: str,
    include_contacts: bool = True
) -> Dict[str, Any]:
    """
    Get full details for a lead from dim_companies and optionally dim_contacts.

    Use this tool to get complete information about a specific lead before
    generating recommendations or outreach.

    Args:
        company_id: UUID of the company
        include_contacts: Whether to include related contacts

    Returns:
        Complete lead record with optional contacts list

    Example:
        lead = get_lead_details(company_id="abc-123", include_contacts=True)
        # Returns: {"company_name": "...", "contacts": [...], ...}
    """
    try:
        supabase = get_supabase()

        # Get company
        result = supabase.table('dim_companies').select('*').eq('company_id', company_id).execute()

        if not result.data:
            raise ToolException(f"Company not found: {company_id}")

        company = result.data[0]

        # Get contacts if requested
        if include_contacts:
            contacts_result = supabase.table('dim_contacts').select('*').eq('company_id', company_id).execute()
            company['contacts'] = contacts_result.data or []
            logger.info(f"Retrieved lead {company_id} with {len(company['contacts'])} contacts")

        return company

    except Exception as e:
        logger.error(f"Error getting lead details: {e}")
        raise ToolException(f"Failed to get lead details: {str(e)}")


@tool("query_leads_by_priority")
def query_leads_by_priority(
    priority: str = "HOT",
    limit: int = 10,
    has_recommendation: bool = True
) -> List[Dict[str, Any]]:
    """
    Query leads by priority tier for Tim's calling list.

    Use this tool to get the TOP leads that have been scouted and are ready to call.

    Args:
        priority: Priority level (HOT, WARM, COLD)
        limit: Maximum number of leads (1-50)
        has_recommendation: Only return leads with AI recommendations

    Returns:
        List of high-priority leads sorted by ICP score
    """
    try:
        supabase = get_supabase()

        limit = max(1, min(limit, 50))

        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, '
            'icp_tier, icp_score, current_stage, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, '
            'oem_count, trade_count, phone'
        )

        # Use current_stage instead of priority_tier
        query = query.eq('current_stage', priority.upper())

        if has_recommendation:
            query = query.not_.is_('ai_company_story', 'null')

        query = query.order('icp_score', desc=True).limit(limit)

        result = query.execute()

        logger.info(f"Queried {len(result.data)} {priority} leads")

        return result.data or []

    except Exception as e:
        logger.error(f"Error querying priority leads: {e}")
        raise ToolException(f"Failed to query priority leads: {str(e)}")


# ========== Exports ==========

__all__ = [
    "get_supabase",
    "query_unenriched_leads",
    "update_lead_recommendation",
    "get_lead_details",
    "query_leads_by_priority",
]
