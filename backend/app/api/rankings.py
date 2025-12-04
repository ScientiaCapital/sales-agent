"""
Lead Rankings API Endpoints
===========================
FastAPI endpoints for accessing lead prediction rankings.

Endpoints:
- GET /rankings - Get current lead rankings
- GET /rankings/stats - Get prediction market statistics
- POST /rankings/refresh - Trigger rankings refresh

Author: Claude + Tim
Date: Dec 3, 2025
"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class LeadRankingItem(BaseModel):
    """Single lead ranking item."""
    rank: int
    company_id: str
    company_name: str
    domain: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    icp_score: Optional[float] = None
    icp_tier: Optional[str] = None
    prediction_score: Optional[float] = None
    stage: Optional[str] = None
    why_now: Optional[str] = None
    company_story: Optional[str] = None


class RankingsResponse(BaseModel):
    """Response for rankings endpoint."""
    success: bool
    count: int
    rankings: List[LeadRankingItem]


class RankingsStatsResponse(BaseModel):
    """Response for rankings stats endpoint."""
    success: bool
    total_ranked: int
    avg_score: float
    top_score: float
    last_update: Optional[str] = None


class RefreshResponse(BaseModel):
    """Response for rankings refresh endpoint."""
    success: bool
    updated: int
    message: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/rankings", response_model=RankingsResponse)
async def get_lead_rankings(
    limit: int = Query(default=10, le=100, description="Number of leads to return"),
    include_why_now: bool = Query(default=True, description="Include AI-generated reasoning")
):
    """
    Get current lead rankings.

    Returns top leads ranked by prediction score, with optional
    "why call now" reasoning from the Lead Prediction Agent.

    Example:
        GET /api/v1/rankings?limit=10&include_why_now=true

    Returns:
        {
            "success": true,
            "count": 10,
            "rankings": [
                {
                    "rank": 1,
                    "company_id": "uuid",
                    "company_name": "ACME Corp",
                    "prediction_score": 87.5,
                    "icp_tier": "GOLD",
                    "why_now": "Call because..."
                },
                ...
            ]
        }
    """
    try:
        from app.services.prediction_market import get_top_leads
        import asyncio

        leads = await get_top_leads(limit=limit, include_why_now=include_why_now)

        rankings = [
            LeadRankingItem(**lead)
            for lead in leads
        ]

        return RankingsResponse(
            success=True,
            count=len(rankings),
            rankings=rankings
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching rankings: {str(e)}"
        )


@router.get("/rankings/stats", response_model=RankingsStatsResponse)
async def get_rankings_stats():
    """
    Get prediction market statistics.

    Returns aggregate statistics about the prediction rankings.

    Example:
        GET /api/v1/rankings/stats

    Returns:
        {
            "success": true,
            "total_ranked": 1000,
            "avg_score": 45.3,
            "top_score": 92.5,
            "last_update": "2025-12-03T12:00:00Z"
        }
    """
    try:
        from app.services.prediction_market import get_prediction_stats

        stats = await get_prediction_stats()

        return RankingsStatsResponse(
            success=True,
            total_ranked=stats['total_ranked'],
            avg_score=stats['avg_score'],
            top_score=stats['top_score'],
            last_update=stats['last_update']
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching stats: {str(e)}"
        )


@router.post("/rankings/refresh", response_model=RefreshResponse)
async def refresh_rankings(
    limit: int = Query(default=1000, le=5000, description="Max companies to rank")
):
    """
    Trigger a rankings refresh.

    Manually triggers the prediction market to recalculate rankings.
    This is automatically done every 5 minutes by Celery Beat.

    Example:
        POST /api/v1/rankings/refresh?limit=1000

    Returns:
        {
            "success": true,
            "updated": 1000,
            "message": "Rankings refreshed successfully"
        }
    """
    try:
        from app.services.prediction_market import update_rankings

        result = await update_rankings(limit=limit)

        return RefreshResponse(
            success=True,
            updated=result['updated'],
            message=f"Rankings refreshed: {result['updated']} companies ranked"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing rankings: {str(e)}"
        )


@router.get("/rankings/{company_id}")
async def get_company_ranking(company_id: str):
    """
    Get ranking info for a specific company.

    Example:
        GET /api/v1/rankings/abc-123-def

    Returns:
        Company's current ranking and prediction details
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()

        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        supabase = create_client(url, key)

        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, phone, city, state, '
            'icp_score, icp_tier, prediction_score, prediction_rank, '
            'prediction_why_now, current_stage'
        ).eq('company_id', company_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Company not found: {company_id}")

        company = result.data[0]

        return {
            "success": True,
            "company": {
                "company_id": company.get('company_id'),
                "company_name": company.get('company_name'),
                "domain": company.get('domain'),
                "phone": company.get('phone'),
                "location": f"{company.get('city', '')}, {company.get('state', '')}".strip(', '),
                "icp_score": company.get('icp_score'),
                "icp_tier": company.get('icp_tier'),
                "prediction_score": company.get('prediction_score'),
                "prediction_rank": company.get('prediction_rank'),
                "why_now": company.get('prediction_why_now'),
                "stage": company.get('current_stage')
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching company ranking: {str(e)}"
        )
