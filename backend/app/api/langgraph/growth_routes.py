"""Growth Campaign API routes - Multi-touch campaign endpoints."""

import logging
import time as time_module
from fastapi import APIRouter, Depends, HTTPException

from app.api.langgraph.schemas import GrowthCampaignRequest, GrowthCampaignResponse
from app.auth.dependencies import get_current_user
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/growth", tags=["langgraph-growth"])


@router.post("/run", response_model=GrowthCampaignResponse, status_code=200)
async def run_growth_campaigns(
    request: GrowthCampaignRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run GrowthAgent multi-touch campaigns for HOT leads."""
    try:
        if request.async_mode:
            from app.tasks.agent_tasks import run_growth_campaigns_task
            task = run_growth_campaigns_task.delay(goal=request.goal, max_leads=request.max_leads)
            logger.info(f"Growth campaign task queued: {task.id}")
            return GrowthCampaignResponse(status="queued", task_id=task.id)
        else:
            from app.services.langgraph.agents.growth_agent import GrowthAgent
            from app.services.langgraph.tools.supabase_tools import query_hot_leads

            start_time = time_module.time()
            leads = query_hot_leads(limit=request.max_leads)

            if not leads:
                return GrowthCampaignResponse(
                    status="success", campaigns_run=0, goals_met=0, total_cycles=0, duration_ms=0, results=[], errors=[]
                )

            agent = GrowthAgent(provider='cerebras')
            results, errors, goals_met, total_cycles = [], [], 0, 0

            for lead in leads:
                try:
                    campaign_result = await agent.run_campaign(
                        lead_id=lead['company_id'],
                        goal=request.goal,
                        max_cycles=request.max_cycles
                    )
                    if campaign_result.goal_met:
                        goals_met += 1
                    total_cycles += campaign_result.cycle_count
                    results.append({
                        "company_id": lead['company_id'],
                        "company_name": lead.get('company_name'),
                        "goal": campaign_result.goal,
                        "goal_met": campaign_result.goal_met,
                        "cycles": campaign_result.cycle_count,
                        "response_rate": campaign_result.response_rate,
                        "engagement_score": campaign_result.engagement_score,
                        "learnings": campaign_result.learnings[:3] if campaign_result.learnings else []
                    })
                except Exception as e:
                    errors.append({"company_id": lead.get('company_id'), "error": str(e)})
                    logger.error(f"Growth campaign failed for {lead.get('company_id')}: {e}")

            duration_ms = int((time_module.time() - start_time) * 1000)
            logger.info(f"Growth campaigns completed: {len(results)} campaigns, {goals_met} goals met")
            return GrowthCampaignResponse(
                status="success", campaigns_run=len(results), goals_met=goals_met, total_cycles=total_cycles,
                duration_ms=duration_ms, results=results, errors=errors if errors else None
            )
    except Exception as e:
        logger.error(f"Error running Growth campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Growth campaigns failed: {str(e)}")


@router.get("/status", status_code=200)
async def get_growth_status(current_user: dict = Depends(get_current_user)):
    """Get Growth campaign status and statistics."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()

        hot_total = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'HOT').execute()
        hot_high_icp = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'HOT').gte('icp_score', 75).execute()
        with_drafts = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'HOT').not_.is_('ai_personal_hooks', 'null').execute()

        return {
            "status": "success",
            "hot_leads": {"total": hot_total.count or 0, "high_icp": hot_high_icp.count or 0, "with_campaigns": with_drafts.count or 0},
            "next_scheduled": "Daily at 10 AM EST (15:00 UTC)"
        }
    except Exception as e:
        logger.error(f"Error getting growth status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get growth status: {str(e)}")
