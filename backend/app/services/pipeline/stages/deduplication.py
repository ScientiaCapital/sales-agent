"""Deduplication stage - Check for existing leads before creation."""
import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable

from app.schemas.pipeline import PipelineStageResult
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage

logger = logging.getLogger(__name__)

# Map recommendation to event type
DEDUP_EVENT_MAP = {
    "create_new": LeadAuditEventType.DEDUP_CREATE_NEW,
    "add_contact_to_existing": LeadAuditEventType.DEDUP_ADD_CONTACT,
    "skip_duplicate": LeadAuditEventType.DEDUP_SKIP_DUPLICATE,
    "update_existing_contact": LeadAuditEventType.DEDUP_UPDATE_EXISTING
}


async def run_deduplication(
    lead: Dict[str, Any],
    close_dedup_service: Optional[Any],
    deduplication_service: Optional[Any],
    db: Optional[Any],
    log_audit: Callable[..., Awaitable[None]]
) -> PipelineStageResult:
    """Run deduplication check against Close CRM API and track metrics."""
    start = time.time()

    # Use Close CRM API deduplication (preferred)
    if close_dedup_service:
        try:
            new_contact_data = {
                "phone": lead.get("phone"),
                "linkedin_url": lead.get("linkedin_url"),
                "department": lead.get("department"),
                "confidence": lead.get("confidence_score", 0)
            }

            result = await close_dedup_service.check_duplicate(
                company_name=lead.get("name") or lead.get("company_name"),
                email=lead.get("email"),
                phone=lead.get("phone"),
                new_contact_data=new_contact_data
            )
            latency_ms = int((time.time() - start) * 1000)

            output = {
                "is_duplicate": result.is_duplicate,
                "company_match_found": result.company_match_found,
                "company_confidence": result.company_confidence,
                "contact_match_found": result.contact_match_found,
                "contact_confidence": result.contact_confidence,
                "matched_lead_id": result.matched_lead_id,
                "matched_contact_id": result.matched_contact_id,
                "matched_company_name": result.matched_company_name,
                "recommendation": result.recommendation,
                "source": "close_crm_api"
            }

            status = "duplicate" if result.is_duplicate else "success"

            logger.info(
                f"Close CRM deduplication: {status}, "
                f"company_match={result.company_match_found} ({result.company_confidence:.1f}%), "
                f"contact_match={result.contact_match_found}"
            )

            # Log audit event
            company_name = lead.get("name") or lead.get("company_name", "")
            dedup_event = DEDUP_EVENT_MAP.get(
                result.recommendation,
                LeadAuditEventType.DEDUP_CREATE_NEW
            )
            await log_audit(
                company_name=company_name,
                event_type=dedup_event,
                stage=LeadAuditStage.DEDUPLICATION.value,
                decision_data={
                    "recommendation": result.recommendation,
                    "company_confidence": result.company_confidence,
                    "contact_confidence": result.contact_confidence,
                    "matched_lead_id": result.matched_lead_id,
                    "matched_company_name": result.matched_company_name,
                    "is_duplicate": result.is_duplicate,
                },
                latency_ms=latency_ms
            )

            return PipelineStageResult(
                status=status,
                latency_ms=latency_ms,
                cost_usd=0.0,
                output=output,
                confidence=result.company_confidence if result.company_match_found else 0.0
            )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Close CRM deduplication failed: {e}")
            # Fall through to local deduplication

    # Fallback: Local database deduplication (legacy)
    if not deduplication_service:
        return PipelineStageResult(
            status="skipped",
            latency_ms=0,
            cost_usd=0.0,
            output={"is_duplicate": False, "reason": "No deduplication service available"}
        )

    try:
        result = await deduplication_service.find_duplicates(
            email=lead.get("email"),
            company=lead.get("name") or lead.get("company_name"),
            linkedin_url=lead.get("linkedin_url"),
            phone=lead.get("phone"),
            company_website=lead.get("website")
        )
        latency_ms = int((time.time() - start) * 1000)

        output = {
            "is_duplicate": result.is_duplicate,
            "confidence": result.confidence,
            "threshold": result.threshold,
            "checked_fields": result.checked_fields,
            "match_count": len(result.matches),
            "source": "local_database"
        }

        return PipelineStageResult(
            status="duplicate" if result.is_duplicate else "no_duplicate",
            latency_ms=latency_ms,
            cost_usd=0.0,
            confidence=result.confidence,
            output=output
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)

        if "does not exist" in str(e).lower() or "relation" in str(e).lower():
            logger.warning(f"Deduplication skipped - CRM tables not available: {e}")
            if db:
                db.rollback()
            return PipelineStageResult(
                status="skipped",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output={"is_duplicate": False, "reason": "CRM tables not available"}
            )

        logger.error(f"Deduplication failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
