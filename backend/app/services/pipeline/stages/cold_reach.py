"""Cold Reach stage - Enroll leads in email sequences."""
import time
import logging
from typing import Dict, Any, Optional

from app.schemas.pipeline import PipelineStageResult

logger = logging.getLogger(__name__)


async def run_cold_reach_enrollment(
    lead: Dict[str, Any],
    tier: str,
    cold_reach_client: Optional[Any]
) -> PipelineStageResult:
    """
    Enroll qualified lead in cold-reach email sequences.

    Integration Point: Qualifier (sales-agent) → Sender (cold-reach)
    """
    start = time.time()

    if not cold_reach_client:
        return PipelineStageResult(
            status="skipped",
            latency_ms=0,
            cost_usd=0.0,
            output={"reason": "Cold Reach client not available"}
        )

    try:
        email = lead.get("email") or lead.get("contact_email")
        if not email:
            discovered_contacts = lead.get("_discovered_contacts", [])
            for contact in discovered_contacts:
                if contact.get("email") and contact.get("is_atl"):
                    email = contact["email"]
                    lead["first_name"] = contact.get("first_name")
                    lead["last_name"] = contact.get("last_name")
                    break

        if not email:
            return PipelineStageResult(
                status="skipped",
                latency_ms=int((time.time() - start) * 1000),
                cost_usd=0.0,
                output={"reason": "No email available for enrollment"}
            )

        from app.services.cold_reach_client import EnrollmentRequest

        company_name = lead.get("name") or lead.get("company_name", "")

        request = EnrollmentRequest(
            email=email,
            company=company_name,
            first_name=lead.get("first_name"),
            last_name=lead.get("last_name"),
            tier=tier,
            icp_score=lead.get("qualification_score") or lead.get("icp_score"),
            coperniq_score=lead.get("coperniq_score"),
            oem_certifications=lead.get("oem_certifications", []),
            state=lead.get("state"),
            phone=lead.get("phone"),
        )

        result = await cold_reach_client.enroll_lead(request)
        latency_ms = int((time.time() - start) * 1000)

        if result.success:
            if result.skipped:
                logger.info(f"Cold Reach enrollment skipped for {email}: {result.skip_reason}")
                return PipelineStageResult(
                    status="skipped",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        "reason": result.skip_reason,
                        "email": email,
                        "tier": tier,
                    }
                )
            else:
                logger.info(
                    f"Cold Reach enrollment successful: {email} → "
                    f"sequence={result.sequence_id}, entry_id={result.entry_id}"
                )
                return PipelineStageResult(
                    status="enrolled",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        "email": email,
                        "company": company_name,
                        "tier": tier,
                        "sequence_id": result.sequence_id,
                        "entry_id": result.entry_id,
                        "prospect_id": result.prospect_id,
                        "status": result.status,
                        "first_step_due": result.first_step_due,
                    }
                )
        else:
            logger.warning(f"Cold Reach enrollment failed for {email}: {result.error}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=result.error,
                output={"email": email, "tier": tier}
            )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Cold Reach enrollment failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
