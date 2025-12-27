"""Sales Intel API routes - Personal hooks extraction endpoints."""

import logging
import time as time_module
from fastapi import APIRouter, Depends, HTTPException

from app.api.langgraph.schemas import SalesIntelRunRequest, SalesIntelRunResponse
from app.auth.dependencies import get_current_user
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/intel", tags=["langgraph-intel"])


@router.post("/run", response_model=SalesIntelRunResponse, status_code=200)
async def run_sales_intel(
    request: SalesIntelRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run SalesIntelAgent to extract personal hooks from scouted leads."""
    try:
        if request.async_mode:
            from app.tasks.agent_tasks import run_sales_intel_batch_task
            task = run_sales_intel_batch_task.delay(limit=request.limit)
            logger.info(f"SalesIntel task queued: {task.id}")
            return SalesIntelRunResponse(status="queued", task_id=task.id)
        else:
            from app.services.langgraph.agents.sales_intel_agent import SalesIntelAgent
            from app.services.langgraph.tools.supabase_tools import query_leads_for_sales_intel, save_sales_intel

            start_time = time_module.time()
            leads = query_leads_for_sales_intel(limit=request.limit)

            if not leads:
                return SalesIntelRunResponse(status="success", leads_processed=0, hooks_extracted=0, duration_ms=0, results=[], errors=[])

            agent = SalesIntelAgent(provider='cerebras')
            results, errors, total_hooks = [], [], 0

            for lead in leads:
                try:
                    intel_result = await agent.analyze(
                        company_name=lead.get('company_name', ''),
                        contact_name=lead.get('contact_name'),
                        contact_title=lead.get('contact_title'),
                        scraped_content=lead.get('ai_company_story', ''),
                        services=lead.get('service_areas'),
                        brands=lead.get('oem_brands'),
                        location=f"{lead.get('city', '')}, {lead.get('state', '')}"
                    )
                    save_sales_intel(
                        company_id=lead['company_id'],
                        personal_hooks=intel_result.personal_hooks,
                        company_story=intel_result.company_story,
                        pain_points=intel_result.pain_points,
                        email_draft=intel_result.email_body,
                        sms_draft=intel_result.sms_draft,
                        voice_opener=intel_result.voice_opener
                    )
                    hook_count = len(intel_result.personal_hooks) if intel_result.personal_hooks else 0
                    total_hooks += hook_count
                    results.append({
                        "company_id": lead['company_id'],
                        "company_name": lead.get('company_name'),
                        "hooks_found": hook_count,
                        "has_email_draft": bool(intel_result.email_body),
                        "has_sms_draft": bool(intel_result.sms_draft)
                    })
                except Exception as e:
                    errors.append({"company_id": lead.get('company_id'), "error": str(e)})
                    logger.error(f"SalesIntel failed for {lead.get('company_id')}: {e}")

            duration_ms = int((time_module.time() - start_time) * 1000)
            logger.info(f"SalesIntel completed: {len(results)} leads, {total_hooks} hooks in {duration_ms}ms")
            return SalesIntelRunResponse(
                status="success", leads_processed=len(results), hooks_extracted=total_hooks,
                duration_ms=duration_ms, results=results, errors=errors if errors else None
            )
    except Exception as e:
        logger.error(f"Error running SalesIntel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SalesIntel failed: {str(e)}")


@router.get("/results", status_code=200)
async def get_sales_intel_results(
    limit: int = 20,
    has_hooks: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Get leads with extracted personal hooks."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, icp_tier, icp_score, current_stage, '
            'ai_personal_hooks, ai_pain_points, ai_company_story, phone, state, city, ai_enriched_at'
        )
        if has_hooks:
            query = query.not_.is_('ai_personal_hooks', 'null')

        result = query.order('ai_enriched_at', desc=True).limit(limit).execute()
        return {"status": "success", "count": len(result.data), "results": result.data}
    except Exception as e:
        logger.error(f"Error getting intel results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get intel results: {str(e)}")
