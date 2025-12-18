"""
Cold Reach Client - Integration service for email sequence enrollment.

Connects Qualifier (sales-agent) to Sender (cold-reach) for:
- Enrolling qualified leads (Tier A/B) in email sequences
- Checking enrollment status
- Processing sequence webhooks
- Triggering voice calls via Close CRM for interested replies

Flow: Qualifier → cold_reach_client → SequenceEngine (direct)
      Interested Reply → Close CRM Call Trigger

UPDATED: Now uses direct imports instead of HTTP calls for better performance.
"""
import os
import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sequences.engine import SequenceEngine

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Default sequences for different lead tiers
DEFAULT_SEQUENCES = {
    "A": "high_priority_solar",
    "B": "standard_solar_intro",
    "C": "nurture_sequence",
    "D": None,  # Don't enroll D tier
}

# Default mailbox IDs (configure in .env)
DEFAULT_MAILBOX_ID = int(os.getenv("COLD_REACH_DEFAULT_MAILBOX_ID", "1"))


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EnrollmentRequest(BaseModel):
    """Request to enroll a lead in cold-reach."""
    email: EmailStr
    company: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tier: str = "B"  # A/B/C/D
    icp_score: Optional[float] = None
    coperniq_score: Optional[int] = None
    oem_certifications: List[str] = Field(default_factory=list)
    state: Optional[str] = None
    phone: Optional[str] = None
    decision_maker_email: Optional[EmailStr] = None
    decision_maker_name: Optional[str] = None
    sequence_id: Optional[str] = None  # Override default
    mailbox_id: Optional[int] = None  # Override default


class EnrollmentResult(BaseModel):
    """Result from enrollment attempt."""
    success: bool
    entry_id: Optional[int] = None
    prospect_id: Optional[int] = None
    sequence_id: Optional[str] = None
    status: Optional[str] = None
    first_step_due: Optional[str] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


class BatchEnrollmentResult(BaseModel):
    """Result from batch enrollment."""
    success: bool
    total: int
    enrolled: int
    skipped: int
    errors: int
    results: List[EnrollmentResult] = Field(default_factory=list)


# ============================================================================
# CLIENT CLASS
# ============================================================================

class ColdReachClient:
    """
    Direct client for sequence enrollment using SequenceEngine.

    UPDATED: Now uses direct imports instead of HTTP calls.

    Usage:
        client = ColdReachClient(db_session)

        # Single enrollment
        result = await client.enroll_lead(lead_data)

        # Batch enrollment
        result = await client.enroll_leads_batch(leads)
    """

    def __init__(
        self,
        session: AsyncSession,
        default_mailbox_id: int = DEFAULT_MAILBOX_ID,
    ):
        """
        Initialize client.

        Args:
            session: Database session for SequenceEngine
            default_mailbox_id: Default mailbox for sending
        """
        self.session = session
        self.default_mailbox_id = default_mailbox_id
        self.engine = SequenceEngine(session)

    def _get_sequence_for_tier(self, tier: str) -> Optional[str]:
        """Get default sequence ID for a qualification tier."""
        return DEFAULT_SEQUENCES.get(tier.upper())

    async def enroll_lead(
        self,
        request: EnrollmentRequest,
    ) -> EnrollmentResult:
        """
        Enroll a single lead in a cold-reach sequence.

        Args:
            request: Enrollment request with lead data

        Returns:
            EnrollmentResult with status
        """
        try:
            # Check if tier should be enrolled
            sequence_id = request.sequence_id or self._get_sequence_for_tier(request.tier)
            if not sequence_id:
                logger.info(
                    f"Skipping enrollment for {request.email} - "
                    f"tier {request.tier} not eligible for sequences"
                )
                return EnrollmentResult(
                    success=True,
                    skipped=True,
                    skip_reason=f"Tier {request.tier} not eligible for email sequences",
                )

            # Build custom fields
            custom_fields = {
                "coperniq_score": request.coperniq_score,
                "oem_certifications": request.oem_certifications,
                "state": request.state,
                "phone": request.phone,
                "decision_maker_email": request.decision_maker_email,
                "decision_maker_name": request.decision_maker_name,
            }
            # Remove None values
            custom_fields = {k: v for k, v in custom_fields.items() if v is not None}

            # Call SequenceEngine directly
            result = await self.engine.enroll_prospect(
                prospect_email=request.email,
                sequence_id=sequence_id,
                mailbox_id=request.mailbox_id or self.default_mailbox_id,
                custom_fields=custom_fields,
                company_name=request.company,
                first_name=request.first_name,
                last_name=request.last_name,
                tier=request.tier,
                icp_score=request.icp_score,
            )

            return EnrollmentResult(
                success=result.get("success", False),
                entry_id=result.get("entry_id"),
                prospect_id=result.get("prospect_id"),
                sequence_id=sequence_id,
                status=result.get("status"),
                first_step_due=result.get("first_step_due"),
                error=result.get("error"),
            )

        except Exception as e:
            logger.error(f"Enrollment failed: {e}")
            return EnrollmentResult(
                success=False,
                error=f"Enrollment failed: {str(e)}",
            )

    async def enroll_leads_batch(
        self,
        leads: List[EnrollmentRequest],
        sequence_id: Optional[str] = None,
        mailbox_id: Optional[int] = None,
    ) -> BatchEnrollmentResult:
        """
        Enroll multiple leads in batch.

        More efficient than individual calls for bulk imports.

        Args:
            leads: List of enrollment requests
            sequence_id: Override sequence for all leads
            mailbox_id: Override mailbox for all leads

        Returns:
            BatchEnrollmentResult with statistics
        """
        try:
            # Filter eligible leads
            eligible_leads = []
            skipped_results = []

            for lead in leads:
                seq_id = sequence_id or lead.sequence_id or self._get_sequence_for_tier(lead.tier)
                if not seq_id:
                    skipped_results.append(EnrollmentResult(
                        success=True,
                        skipped=True,
                        skip_reason=f"Tier {lead.tier} not eligible",
                    ))
                else:
                    lead.sequence_id = seq_id
                    lead.mailbox_id = mailbox_id or lead.mailbox_id or self.default_mailbox_id
                    eligible_leads.append(lead)

            if not eligible_leads:
                return BatchEnrollmentResult(
                    success=True,
                    total=len(leads),
                    enrolled=0,
                    skipped=len(skipped_results),
                    errors=0,
                    results=skipped_results,
                )

            # Enroll each lead directly using SequenceEngine
            enrollment_results = []
            enrolled = 0
            errors = 0

            for lead in eligible_leads:
                try:
                    custom_fields = {
                        "coperniq_score": lead.coperniq_score,
                        "oem_certifications": lead.oem_certifications,
                        "state": lead.state,
                        "phone": lead.phone,
                        "decision_maker_email": lead.decision_maker_email,
                        "decision_maker_name": lead.decision_maker_name,
                    }
                    custom_fields = {k: v for k, v in custom_fields.items() if v is not None}

                    result = await self.engine.enroll_prospect(
                        prospect_email=lead.email,
                        sequence_id=lead.sequence_id,
                        mailbox_id=lead.mailbox_id,
                        custom_fields=custom_fields,
                        company_name=lead.company,
                        first_name=lead.first_name,
                        last_name=lead.last_name,
                        tier=lead.tier,
                        icp_score=lead.icp_score,
                    )

                    enrollment_result = EnrollmentResult(
                        success=result.get("success", False),
                        entry_id=result.get("entry_id"),
                        prospect_id=result.get("prospect_id"),
                        sequence_id=lead.sequence_id,
                        status=result.get("status"),
                        first_step_due=result.get("first_step_due"),
                        error=result.get("error"),
                    )

                    enrollment_results.append(enrollment_result)

                    if enrollment_result.success:
                        enrolled += 1
                    else:
                        errors += 1

                except Exception as e:
                    logger.error(f"Failed to enroll {lead.email}: {e}")
                    enrollment_results.append(EnrollmentResult(
                        success=False,
                        error=str(e)
                    ))
                    errors += 1

            return BatchEnrollmentResult(
                success=True,
                total=len(leads),
                enrolled=enrolled,
                skipped=len(skipped_results),
                errors=errors,
                results=skipped_results + enrollment_results,
            )

        except Exception as e:
            logger.error(f"Batch enrollment error: {e}")
            return BatchEnrollmentResult(
                success=False,
                total=len(leads),
                enrolled=0,
                skipped=0,
                errors=len(leads),
            )

    async def get_prospect_status(self, email: str) -> Dict[str, Any]:
        """
        Get prospect's status in cold-reach sequences.

        Args:
            email: Prospect email address

        Returns:
            Status dict with sequence enrollments
        """
        try:
            from sqlalchemy import select
            from app.models.lead import Lead
            from app.models.sequence_entry import SequenceEntry

            # Find prospect
            query = select(Lead).where(Lead.contact_email == email)
            result = await self.session.execute(query)
            prospect = result.scalar_one_or_none()

            if not prospect:
                return {"error": "Prospect not found"}

            # Get all sequence entries
            entry_query = select(SequenceEntry).where(SequenceEntry.lead_id == prospect.id)
            entry_result = await self.session.execute(entry_query)
            entries = entry_result.scalars().all()

            enrollments = [
                {
                    "entry_id": entry.id,
                    "sequence_id": entry.sequence_id,
                    "status": entry.status,
                    "current_step": entry.current_step,
                    "emails_sent": entry.emails_sent,
                    "reply_received": entry.reply_received.isoformat() if entry.reply_received else None,
                    "reply_intent": entry.reply_intent,
                }
                for entry in entries
            ]

            return {
                "email": email,
                "prospect_id": prospect.id,
                "enrollments": enrollments,
            }

        except Exception as e:
            logger.error(f"Get status error: {e}")
            return {"error": str(e)}


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def enroll_qualified_lead(
    session: AsyncSession,
    email: str,
    company: str,
    tier: str,
    icp_score: Optional[float] = None,
    coperniq_score: Optional[int] = None,
    oem_certifications: Optional[List[str]] = None,
    **kwargs,
) -> EnrollmentResult:
    """
    Convenience function to enroll a qualified lead.

    Usage:
        result = await enroll_qualified_lead(
            session=db,
            email="john@solar.com",
            company="Solar Electric",
            tier="A",
            coperniq_score=92,
        )
    """
    client = ColdReachClient(session)
    request = EnrollmentRequest(
        email=email,
        company=company,
        tier=tier,
        icp_score=icp_score,
        coperniq_score=coperniq_score,
        oem_certifications=oem_certifications or [],
        **kwargs,
    )
    return await client.enroll_lead(request)


async def enroll_pipeline_leads_batch(
    session: AsyncSession,
    leads: List[Dict[str, Any]],
    min_tier: str = "B",
) -> BatchEnrollmentResult:
    """
    Enroll pipeline leads from dealer-scraper import.

    Filters leads by tier before enrollment.

    Args:
        leads: List of lead dicts (from PipelineLead schema)
        min_tier: Minimum tier to enroll (A, B, C, D)

    Returns:
        BatchEnrollmentResult
    """
    # Tier hierarchy
    tier_order = {"A": 1, "B": 2, "C": 3, "D": 4}
    min_tier_value = tier_order.get(min_tier.upper(), 2)

    # Filter and convert to requests
    requests = []
    for lead in leads:
        tier = lead.get("qualification_tier") or lead.get("tier") or "C"
        if tier_order.get(tier.upper(), 4) <= min_tier_value:
            requests.append(EnrollmentRequest(
                email=lead.get("email") or lead.get("decision_maker_email"),
                company=lead.get("company_name") or lead.get("name"),
                first_name=lead.get("decision_maker_name", "").split()[0] if lead.get("decision_maker_name") else None,
                last_name=lead.get("decision_maker_name", "").split()[-1] if lead.get("decision_maker_name") and len(lead.get("decision_maker_name", "").split()) > 1 else None,
                tier=tier,
                icp_score=lead.get("qualification_score"),
                coperniq_score=lead.get("coperniq_score"),
                oem_certifications=lead.get("oem_certifications", []),
                state=lead.get("state"),
                phone=lead.get("phone"),
            ))

    if not requests:
        return BatchEnrollmentResult(
            success=True,
            total=len(leads),
            enrolled=0,
            skipped=len(leads),
            errors=0,
            results=[],
        )

    client = ColdReachClient(session)
    return await client.enroll_leads_batch(requests)


# ============================================================================
# CLOSE CRM INTEGRATION (Voice Call Triggers)
# ============================================================================

async def trigger_interested_reply_call(
    email: str,
    lead_id: str,
    phone: str,
    reply_text: Optional[str] = None,
    qualification_score: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Trigger a voice call via Close CRM for an interested email reply.

    This function is called when cold-reach detects an interested reply
    (e.g., "Yes, I'm interested" or "Tell me more") and wants to escalate
    to a phone call.

    Replaces external voice integration with native Close CRM call tracking.

    Args:
        email: Prospect email address
        lead_id: Close CRM lead ID
        phone: Phone number to call
        reply_text: The prospect's reply text (optional)
        qualification_score: Lead qualification score (optional)

    Returns:
        Dict with call trigger result:
        {
            "success": True,
            "activity_id": "acti_xxx",
            "status": "scheduled",
            "phone": "+1234567890"
        }

    Example:
        # Prospect replied "Yes, let's schedule a call"
        result = await trigger_interested_reply_call(
            email="john@solarpros.com",
            lead_id="lead_xxx123",
            phone="+12125551234",
            reply_text="Yes, let's schedule a call to discuss pricing",
            qualification_score=85
        )
    """
    try:
        # Import here to avoid circular dependency
        from app.services.crm.close_calling import CloseCallingClient

        # Build call script notes
        script_notes_parts = [
            "INTERESTED REPLY - High Priority Call",
            f"Prospect Email: {email}",
        ]

        if reply_text:
            script_notes_parts.append(f"\nProspect Reply:\n{reply_text[:500]}")

        if qualification_score:
            script_notes_parts.append(f"\nQualification Score: {qualification_score}/100")

        script_notes_parts.extend([
            "\nSuggested Discussion Points:",
            "- Thank them for their interest",
            "- Understand their timeline and requirements",
            "- Discuss pricing and ROI",
            "- Schedule next steps (demo, site visit, proposal)",
        ])

        script_notes = "\n".join(script_notes_parts)

        # Initialize Close calling client
        calling_client = CloseCallingClient()

        # Trigger call via Close CRM
        result = await calling_client.trigger_call(
            phone=phone,
            lead_id=lead_id,
            script_notes=script_notes,
        )

        logger.info(
            f"Voice call triggered for interested reply: {email} -> {phone} "
            f"(activity_id: {result.get('id')})"
        )

        return {
            "success": True,
            "activity_id": result.get("id"),
            "status": result.get("status"),
            "phone": phone,
            "lead_id": lead_id,
            "method": "close_crm",
        }

    except Exception as e:
        logger.error(f"Failed to trigger call via Close CRM for {email}: {e}")
        return {
            "success": False,
            "error": str(e),
            "phone": phone,
            "lead_id": lead_id,
            "method": "close_crm",
        }
