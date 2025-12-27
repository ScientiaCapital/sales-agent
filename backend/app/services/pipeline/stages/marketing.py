"""Marketing stage - Email/SMS content generation."""
import time
import logging
from typing import Dict, Any

from app.schemas.pipeline import PipelineStageResult

logger = logging.getLogger(__name__)


async def run_marketing(
    lead: Dict[str, Any],
    marketing_agent: Any
) -> PipelineStageResult:
    """Generate marketing content (email, SMS) using MarketingAgent."""
    start = time.time()
    try:
        company_name = lead.get("company_name") or lead.get("name") or "Unknown Company"
        industry = lead.get("industry", "business services")
        qualification_score = lead.get("qualification_score", 50)

        contacts = lead.get("_discovered_contacts", [])
        primary_contact = contacts[0] if contacts else {}
        contact_name = primary_contact.get("name", "Decision Maker")
        contact_title = primary_contact.get("title", "")

        campaign_brief = f"""
        Outreach for {company_name} in the {industry} industry.
        Target contact: {contact_name}{f' ({contact_title})' if contact_title else ''}.
        Lead quality: {'Hot' if qualification_score >= 70 else 'Warm' if qualification_score >= 50 else 'Cold'} prospect.
        Goal: Schedule a discovery call to discuss solar/energy efficiency solutions.
        """

        target_audience = f"{contact_title or 'Decision makers'} at {industry} companies"

        result = await marketing_agent.generate_campaign(
            campaign_brief=campaign_brief.strip(),
            target_audience=target_audience,
            campaign_goals=["awareness", "meeting_request"]
        )

        latency_ms = int((time.time() - start) * 1000)

        output = {
            "email_content": result.email_content,
            "email_subject": f"Quick question for {contact_name} at {company_name}",
            "sms_content": result.social_content[:160] if result.social_content else None,
            "linkedin_content": result.linkedin_content,
            "content_quality_score": result.content_quality_score,
            "total_cost_usd": result.total_cost_usd
        }

        lead["_marketing_content"] = output

        logger.info(
            f"Generated marketing content for {company_name}: "
            f"email={bool(result.email_content)}, sms={bool(output['sms_content'])}"
        )

        return PipelineStageResult(
            status="completed",
            latency_ms=latency_ms,
            cost_usd=result.total_cost_usd,
            output=output
        )

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Marketing content generation failed: {e}")
        return PipelineStageResult(
            status="failed",
            latency_ms=latency_ms,
            cost_usd=0.0,
            error=str(e)
        )
