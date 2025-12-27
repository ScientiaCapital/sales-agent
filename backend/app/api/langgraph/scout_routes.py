"""Lead Scout API routes - Discovery and prioritization endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.api.langgraph.schemas import ScoutRunRequest, ScoutRunResponse
from app.auth.dependencies import get_current_user
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/scout", tags=["langgraph-scout"])


@router.post("/run", response_model=ScoutRunResponse, status_code=200)
async def run_lead_scout(
    request: ScoutRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """Trigger Lead Scout run to discover and prioritize leads."""
    try:
        if request.async_mode:
            from app.tasks.agent_tasks import run_lead_scout_task
            task = run_lead_scout_task.delay(
                limit=request.limit,
                require_domain=request.require_domain,
                icp_tier=request.icp_tier
            )
            logger.info(f"Lead Scout task queued: {task.id}")
            return ScoutRunResponse(status="queued", task_id=task.id)
        else:
            from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent
            scout = LeadScoutAgent(provider='cerebras')
            result = await scout.scout(
                limit=request.limit,
                require_domain=request.require_domain,
                icp_tier=request.icp_tier
            )
            logger.info(f"Lead Scout completed: {result.total_scouted} scouted")
            return ScoutRunResponse(
                status="success",
                total_scouted=result.total_scouted,
                hot_leads=result.hot_leads,
                warm_leads=result.warm_leads,
                cold_leads=result.cold_leads,
                duration_ms=result.duration_ms,
                results=[{
                    "company_id": r.company_id,
                    "company_name": r.company_name,
                    "domain": r.domain,
                    "icp_score": r.icp_score,
                    "priority": r.priority,
                    "why_call": r.why_call[:200],
                    "scouted_at": r.scouted_at
                } for r in result.results],
                errors=result.errors
            )
    except Exception as e:
        logger.error(f"Error running Lead Scout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lead Scout failed: {str(e)}")


@router.get("/results", status_code=200)
async def get_scout_results(
    limit: int = 20,
    priority: str = None,
    current_user: dict = Depends(get_current_user),
):
    """Get recent scout results with AI recommendations."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, icp_tier, icp_score, current_stage, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, phone, state, city, ai_enriched_at'
        ).not_.is_('ai_company_story', 'null')

        if priority:
            query = query.eq('current_stage', priority.upper())

        result = query.order('ai_enriched_at', desc=True).limit(limit).execute()
        return {"status": "success", "count": len(result.data), "results": result.data}
    except Exception as e:
        logger.error(f"Error getting scout results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get scout results: {str(e)}")


@router.get("/status", status_code=200)
async def get_scout_status(current_user: dict = Depends(get_current_user)):
    """Get Lead Scout status and statistics."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()

        total = supabase.table('dim_companies').select('company_id', count='exact').not_.is_('ai_company_story', 'null').execute()
        hot = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'HOT').not_.is_('ai_company_story', 'null').execute()
        warm = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'WARM').not_.is_('ai_company_story', 'null').execute()
        cold = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'COLD').not_.is_('ai_company_story', 'null').execute()
        unenriched = supabase.table('dim_companies').select('company_id', count='exact').not_.is_('domain', 'null').is_('ai_company_story', 'null').execute()

        return {
            "status": "success",
            "scouted": {"total": total.count or 0, "hot": hot.count or 0, "warm": warm.count or 0, "cold": cold.count or 0},
            "remaining": unenriched.count or 0,
            "next_scheduled": "Every 30 minutes (Celery Beat)"
        }
    except Exception as e:
        logger.error(f"Error getting scout status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get scout status: {str(e)}")
