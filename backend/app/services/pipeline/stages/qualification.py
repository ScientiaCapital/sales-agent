"""Qualification stage - Lead scoring and tier classification."""
import time
import logging
from typing import Dict, Any, Callable, Awaitable

from app.schemas.pipeline import PipelineStageResult
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage

logger = logging.getLogger(__name__)


async def run_qualification(
    lead: Dict[str, Any],
    qualification_agent: Any,
    log_audit: Callable[..., Awaitable[None]]
) -> PipelineStageResult:
    """Run qualification agent and track metrics."""
    start = time.time()
    try:
        result = await qualification_agent.qualify(
            company_name=lead.get("name") or lead.get("company_name"),
            company_website=lead.get("website"),
            company_size=lead.get("company_size"),
            industry=lead.get("industry"),
            contact_name=lead.get("contact_name"),
            contact_email=lead.get("email") or lead.get("contact_email"),
            contact_title=lead.get("contact_title"),
            company_phone=lead.get("phone"),
            notes=lead.get("notes")
        )

        # Handle different return formats
        if isinstance(result, tuple) and len(result) == 3:
            qualification_result, agent_latency_ms, metadata = result

            if hasattr(qualification_result, 'qualification_score'):
                output = {
                    "qualification_score": qualification_result.qualification_score,
                    "tier": getattr(qualification_result, 'tier', None),
                    "qualification_reasoning": getattr(qualification_result, 'qualification_reasoning', None),
                    "fit_assessment": getattr(qualification_result, 'fit_assessment', None),
                    "contact_quality": getattr(qualification_result, 'contact_quality', None),
                    "sales_potential": getattr(qualification_result, 'sales_potential', None),
                    "metadata": metadata
                }
            else:
                output = {"qualification_score": float(qualification_result), "metadata": metadata}

            cost = metadata.get("estimated_cost_usd", 0.000006) if isinstance(metadata, dict) else 0.000006
        else:
            agent_latency_ms = int((time.time() - start) * 1000)
            output = {"result": str(result)}
            cost = 0.000006

        # Log audit event
        company_name = lead.get("name") or lead.get("company_name", "")
        await log_audit(
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_QUALIFIED,
            stage=LeadAuditStage.QUALIFICATION.value,
            decision_data={
                "score": output.get("qualification_score"),
                "tier": output.get("tier"),
                "website_found": bool(lead.get("website")),
                "email_found": bool(lead.get("email") or lead.get("contact_email")),
            },
            latency_ms=agent_latency_ms,
            cost_usd=cost
        )

        return PipelineStageResult(
            status="success",
            latency_ms=agent_latency_ms,
            cost_usd=cost,
            output=output
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Qualification failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
