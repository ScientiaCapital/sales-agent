"""CRM Check stage - Check Close CRM for existing ATL contacts."""
import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable

from app.schemas.pipeline import PipelineStageResult
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage

logger = logging.getLogger(__name__)

# ATL titles to look for
ATL_KEYWORDS = [
    "ceo", "cto", "vp", "vice president", "director",
    "founder", "co-founder", "owner", "president",
    "head of", "manager", "partner", "principal"
]


async def check_close_crm_for_atl(
    lead: Dict[str, Any],
    close_dedup_service: Optional[Any],
    log_audit: Callable[..., Awaitable[None]]
) -> PipelineStageResult:
    """
    Check Close CRM for existing company and ATL contacts.

    Returns status: "found_atl" | "found_no_atl" | "not_found" | "failed"
    """
    start = time.time()
    try:
        if not close_dedup_service:
            logger.warning("Close CRM check skipped - Close API key not configured")
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"recommendation": "run_enrichment"}
            )

        company_name = lead.get("name") or lead.get("company")
        if not company_name:
            return PipelineStageResult(
                status="failed",
                latency_ms=0,
                cost_usd=0.0,
                error="Company name required for Close CRM check"
            )

        recommendation = await close_dedup_service.check_duplicate(
            company_name=company_name,
            email=lead.get("email")
        )

        latency_ms = int((time.time() - start) * 1000)

        # Check for ATL contacts in existing company
        atl_contacts = []
        company_exists = recommendation.recommendation != "create_new"
        lead_id = recommendation.matched_lead_id if company_exists else None

        if company_exists and recommendation.existing_contacts:
            for contact in recommendation.existing_contacts:
                title = (contact.get("title") or "").lower()
                if any(keyword in title for keyword in ATL_KEYWORDS):
                    atl_contacts.append(contact)

            logger.info(
                f"Close CRM check for {company_name}: "
                f"company_exists=True, atl_contacts={len(atl_contacts)}"
            )

            if atl_contacts:
                await log_audit(
                    company_name=company_name,
                    event_type=LeadAuditEventType.CRM_MATCH_FOUND,
                    stage=LeadAuditStage.CRM_CHECK.value,
                    decision_data={
                        "company_exists": True,
                        "lead_id": lead_id,
                        "atl_contacts_count": len(atl_contacts),
                        "recommendation": "skip_enrichment",
                        "atl_titles": [c.get("title") for c in atl_contacts],
                    },
                    latency_ms=latency_ms
                )

                return PipelineStageResult(
                    status="found_atl",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        "company_exists": True,
                        "lead_id": lead_id,
                        "atl_contacts": atl_contacts,
                        "recommendation": "skip_enrichment",
                        "message": f"Found {len(atl_contacts)} ATL contacts in Close CRM"
                    }
                )
            else:
                return PipelineStageResult(
                    status="found_no_atl",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        "company_exists": True,
                        "lead_id": lead_id,
                        "atl_contacts": [],
                        "recommendation": "run_enrichment",
                        "message": "Company exists but no ATL contacts found"
                    }
                )
        else:
            logger.info(f"Close CRM check for {company_name}: company_exists=False")
            await log_audit(
                company_name=company_name,
                event_type=LeadAuditEventType.CRM_NO_MATCH,
                stage=LeadAuditStage.CRM_CHECK.value,
                decision_data={
                    "company_exists": False,
                    "recommendation": "run_enrichment",
                },
                latency_ms=latency_ms
            )

            return PipelineStageResult(
                status="not_found",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output={
                    "company_exists": False,
                    "lead_id": None,
                    "atl_contacts": [],
                    "recommendation": "run_enrichment",
                    "message": "Company not in Close CRM - enrichment needed"
                }
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Close CRM check failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e),
            output={"recommendation": "run_enrichment"}
        )
