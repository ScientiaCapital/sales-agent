"""Staging stage - Stage marketing content to Close CRM as notes."""
import time
import logging
from typing import Dict, Any, Callable, Awaitable

from app.schemas.pipeline import PipelineStageResult
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage

logger = logging.getLogger(__name__)


async def run_staging(
    lead: Dict[str, Any],
    log_audit: Callable[..., Awaitable[None]]
) -> PipelineStageResult:
    """
    Stage marketing content to Close CRM as notes (NO actual email/SMS sends).
    """
    start = time.time()
    company_name = lead.get("name") or lead.get("company_name", "Unknown")

    try:
        from app.services.crm.close_staging import CloseStagingService

        marketing_content = lead.get("_marketing_content", {})
        if not marketing_content:
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"reason": "No marketing content to stage"}
            )

        close_lead_id = (
            lead.get("close_lead_id") or
            lead.get("_close_lead_id") or
            lead.get("lead_id")
        )

        if not close_lead_id:
            logger.warning(f"No Close CRM lead_id for {company_name}")
            return PipelineStageResult(
                status="skipped",
                latency_ms=int((time.time() - start) * 1000),
                cost_usd=0.0,
                output={
                    "reason": "No Close CRM lead_id - cannot stage content",
                    "company_name": company_name
                }
            )

        staging = CloseStagingService()
        result = await staging.stage_marketing_content(
            lead_id=close_lead_id,
            marketing_content=marketing_content
        )

        latency_ms = int((time.time() - start) * 1000)

        note_result = result.get("note", {})
        if note_result.get("success"):
            logger.info(
                f"Staged marketing content for {company_name} "
                f"(activity_id: {note_result.get('activity_id')})"
            )

            await log_audit(
                company_name=company_name,
                event_type=LeadAuditEventType.LEAD_STAGED,
                stage=LeadAuditStage.STAGING.value,
                decision_data={
                    "lead_id": close_lead_id,
                    "activity_id": note_result.get("activity_id"),
                    "content_type": "note",
                    "email_staged": bool(marketing_content.get("email_content")),
                    "sms_staged": bool(marketing_content.get("sms_content")),
                },
                latency_ms=latency_ms,
                cost_usd=0.0
            )

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output={
                    "lead_id": close_lead_id,
                    "activity_id": note_result.get("activity_id"),
                    "type": "note",
                    "message": "Marketing content staged as note in Close CRM"
                }
            )
        else:
            error_msg = note_result.get("error", "Unknown staging error")
            logger.warning(f"Staging failed for {company_name}: {error_msg}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=error_msg,
                output={"lead_id": close_lead_id}
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Staging failed for {company_name}: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
