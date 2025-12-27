"""Enrichment stage - Company data enhancement via Hunter.io."""
import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable

from app.schemas.pipeline import PipelineStageResult
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage

logger = logging.getLogger(__name__)


async def run_enrichment(
    lead: Dict[str, Any],
    enrichment_agent: Any,
    hunter_service: Optional[Any],
    log_audit: Callable[..., Awaitable[None]]
) -> PipelineStageResult:
    """Run enrichment agent and track metrics."""
    start = time.time()
    try:
        has_email = bool(lead.get("email"))
        has_linkedin = bool(lead.get("linkedin_url"))
        has_lead_id = bool(lead.get("id"))

        if not (has_email or has_linkedin or has_lead_id):
            logger.info(
                f"Skipping enrichment for {lead.get('name')} - no contact identifiers."
            )
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"reason": "company_only_lead"}
            )

        result = await enrichment_agent.enrich(
            email=lead.get("email"),
            linkedin_url=lead.get("linkedin_url"),
            lead_id=lead.get("id")
        )

        # Hunter.io fallback for additional contacts
        if not lead.get("_discovered_contacts") and hunter_service:
            company_website = lead.get("website") or lead.get("url")
            if company_website:
                try:
                    logger.info(f"Attempting Hunter.io domain search for {lead.get('name')}")
                    hunter_contacts = await hunter_service.domain_search(
                        company_website,
                        atl_only=False
                    )
                    if hunter_contacts:
                        lead["_discovered_contacts"] = hunter_contacts
                        logger.info(f"Discovered {len(hunter_contacts)} contacts via Hunter.io")
                except Exception as e:
                    logger.warning(f"Hunter.io domain search failed: {e}")

        latency_ms = int((time.time() - start) * 1000)

        if hasattr(result, 'model_dump'):
            output = result.model_dump()
        elif isinstance(result, dict):
            output = result
        else:
            output = {"result": str(result)}

        # Log audit event
        company_name = lead.get("name") or lead.get("company_name", "")
        discovered_contacts = lead.get("_discovered_contacts", [])
        await log_audit(
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_ENRICHED,
            stage=LeadAuditStage.ENRICHMENT.value,
            decision_data={
                "sources_tried": ["apollo", "linkedin", "hunter"],
                "contacts_found": len(discovered_contacts),
                "atl_contacts": len([c for c in discovered_contacts if c.get("is_atl")]),
                "emails_found": len([c for c in discovered_contacts if c.get("email")]),
            },
            latency_ms=latency_ms,
            cost_usd=0.0001
        )

        return PipelineStageResult(
            status="success",
            latency_ms=latency_ms,
            cost_usd=0.0001,
            output=output
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Enrichment failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
