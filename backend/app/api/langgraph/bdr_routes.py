"""BDR Outreach API routes - Human-in-loop outreach endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.api.langgraph.schemas import BDRRunRequest, BDRRunResponse, BDRApprovalRequest
from app.auth.dependencies import get_current_user
from app.core.logging import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/bdr", tags=["langgraph-bdr"])


@router.post("/run", response_model=BDRRunResponse, status_code=200)
async def run_bdr_outreach(
    request: BDRRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run BDR outreach for a specific company or batch of HOT leads."""
    try:
        if request.company_id:
            from app.tasks.agent_tasks import run_bdr_outreach_task
            if request.async_mode:
                task = run_bdr_outreach_task.delay(request.company_id)
                logger.info(f"BDR outreach task queued: {task.id}")
                return BDRRunResponse(
                    status="queued", task_id=task.id,
                    message=f"BDR outreach queued for company_id={request.company_id}"
                )
            else:
                return BDRRunResponse(
                    status="error", message="BDR requires async_mode=true for Slack notification workflow"
                )
        else:
            from app.tasks.agent_tasks import run_bdr_batch_task
            task = run_bdr_batch_task.delay(limit=request.limit)
            logger.info(f"BDR batch task queued: {task.id}")
            return BDRRunResponse(
                status="queued", task_id=task.id, leads_queued=request.limit,
                message=f"BDR batch queued for up to {request.limit} leads"
            )
    except Exception as e:
        logger.error(f"Error running BDR outreach: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"BDR outreach failed: {str(e)}")


@router.post("/approve", status_code=200)
async def approve_bdr_draft(
    request: BDRApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Approve, reject, or request revision for a BDR draft."""
    try:
        from app.tasks.agent_tasks import resume_bdr_outreach_task

        if request.action not in ["approve", "reject", "revise"]:
            raise HTTPException(status_code=400, detail="Invalid action. Must be: approve, reject, or revise")
        if request.action == "revise" and not request.feedback:
            raise HTTPException(status_code=400, detail="Feedback is required for revision action")

        task = resume_bdr_outreach_task.delay(
            draft_id=request.draft_id, action=request.action,
            feedback=request.feedback, approved_by=request.approved_by
        )
        logger.info(f"BDR resume task queued: {task.id} for {request.action}")
        return {
            "status": "processing", "task_id": task.id, "draft_id": request.draft_id,
            "action": request.action, "message": f"Draft {request.action} processing"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving BDR draft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.get("/drafts", status_code=200)
async def get_bdr_drafts(
    status: str = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Get BDR drafts from dim_ai_drafts."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        query = supabase.table('dim_ai_drafts').select(
            'draft_id, company_id, contact_email, draft_type, subject, body, status, approved_by, created_at, sent_at'
        )
        if status:
            query = query.eq('status', status)
        result = query.order('created_at', desc=True).limit(limit).execute()

        drafts = result.data or []
        if drafts:
            company_ids = list(set(d['company_id'] for d in drafts if d.get('company_id')))
            if company_ids:
                companies = supabase.table('dim_companies').select('company_id, company_name').in_('company_id', company_ids).execute()
                company_map = {c['company_id']: c['company_name'] for c in (companies.data or [])}
                for draft in drafts:
                    draft['company_name'] = company_map.get(draft.get('company_id'), 'Unknown')

        return {"status": "success", "count": len(drafts), "drafts": drafts}
    except Exception as e:
        logger.error(f"Error getting BDR drafts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get drafts: {str(e)}")


@router.get("/status", status_code=200)
async def get_bdr_status(current_user: dict = Depends(get_current_user)):
    """Get BDR status and statistics."""
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase
        supabase = get_supabase()

        pending = supabase.table('dim_ai_drafts').select('draft_id', count='exact').eq('status', 'pending_approval').execute()
        sent = supabase.table('dim_ai_drafts').select('draft_id', count='exact').eq('status', 'sent').execute()
        rejected = supabase.table('dim_ai_drafts').select('draft_id', count='exact').eq('status', 'rejected').execute()
        available = supabase.table('dim_companies').select('company_id', count='exact').eq('current_stage', 'HOT').gte('icp_score', 70).not_.is_('ai_company_story', 'null').execute()

        return {
            "status": "success",
            "drafts": {"pending_approval": pending.count or 0, "sent": sent.count or 0, "rejected": rejected.count or 0},
            "leads_available": available.count or 0,
            "next_scheduled": "Every hour at :00 (3 leads per batch)"
        }
    except Exception as e:
        logger.error(f"Error getting BDR status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get BDR status: {str(e)}")
