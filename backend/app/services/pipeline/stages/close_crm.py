"""Close CRM stage - Create/update lead in CRM."""
import time
import logging
from typing import Dict, Any, Optional

from app.schemas.pipeline import PipelineStageResult

logger = logging.getLogger(__name__)


async def run_close_crm(
    lead: Dict[str, Any],
    close_service: Optional[Any],
    dedup_result: Optional[PipelineStageResult] = None
) -> PipelineStageResult:
    """Create/update lead in Close CRM based on deduplication recommendation."""
    start = time.time()

    if not close_service:
        return PipelineStageResult(
            status="skipped",
            latency_ms=0,
            cost_usd=0.0,
            output={"message": "CRM service not available"}
        )

    try:
        # Get deduplication recommendation
        recommendation = "create_new"
        matched_lead_id = None
        matched_contact_id = None

        if dedup_result and dedup_result.output:
            recommendation = dedup_result.output.get("recommendation", "create_new")
            matched_lead_id = dedup_result.output.get("matched_lead_id")
            matched_contact_id = dedup_result.output.get("matched_contact_id")

        logger.info(f"CRM stage recommendation: {recommendation}")

        if recommendation == "skip_duplicate":
            logger.info(
                f"Skipping CRM creation - contact already exists "
                f"(lead_id: {matched_lead_id}, contact_id: {matched_contact_id})"
            )
            return PipelineStageResult(
                status="skipped",
                latency_ms=int((time.time() - start) * 1000),
                cost_usd=0.0,
                output={
                    "message": "Contact already exists in CRM",
                    "lead_id": matched_lead_id,
                    "contact_id": matched_contact_id,
                    "action": "skipped"
                }
            )

        elif recommendation == "update_existing_contact":
            logger.info(
                f"Updating existing contact in CRM "
                f"(lead_id: {matched_lead_id}, contact_id: {matched_contact_id})"
            )
            return PipelineStageResult(
                status="updated",
                latency_ms=int((time.time() - start) * 1000),
                cost_usd=0.0,
                output={
                    "message": "Contact updated with new data",
                    "lead_id": matched_lead_id,
                    "contact_id": matched_contact_id,
                    "action": "updated"
                }
            )

        elif recommendation == "add_contact_to_existing":
            logger.info(f"Adding discovered contacts to existing lead {matched_lead_id}")
            result = await close_service.create_lead(lead, matched_lead_id=matched_lead_id)
            latency_ms = int((time.time() - start) * 1000)
            return PipelineStageResult(
                status="contact_added",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output={
                    **result,
                    "action": "contact_added",
                    "existing_lead_id": matched_lead_id
                }
            )

        else:  # "create_new"
            result = await close_service.create_lead(lead)
            latency_ms = int((time.time() - start) * 1000)

            return PipelineStageResult(
                status="created",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output={
                    **result,
                    "action": "created"
                }
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Close CRM operation failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
