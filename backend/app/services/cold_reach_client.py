"""
Cold Reach Client - Integration service for email sequence enrollment.

Connects Qualifier (sales-agent) to Sender (cold-reach) for:
- Enrolling qualified leads (Tier A/B) in email sequences
- Checking enrollment status
- Processing sequence webhooks

Flow: Qualifier → cold_reach_client → cold-reach API
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx
from pydantic import BaseModel, Field, EmailStr

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

COLD_REACH_API_URL = os.getenv("COLD_REACH_API_URL", "http://localhost:8002")
COLD_REACH_API_KEY = os.getenv("COLD_REACH_API_KEY", "")

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
    HTTP client for cold-reach API.

    Usage:
        client = ColdReachClient()

        # Single enrollment
        result = await client.enroll_lead(lead_data)

        # Batch enrollment
        result = await client.enroll_leads_batch(leads)
    """

    def __init__(
        self,
        base_url: str = COLD_REACH_API_URL,
        api_key: str = COLD_REACH_API_KEY,
        default_mailbox_id: int = DEFAULT_MAILBOX_ID,
        timeout: float = 30.0,
    ):
        """
        Initialize client.

        Args:
            base_url: cold-reach API base URL
            api_key: API key for authentication
            default_mailbox_id: Default mailbox for sending
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_mailbox_id = default_mailbox_id
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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

            # Build request payload
            payload = {
                "email": request.email,
                "sequence_id": sequence_id,
                "mailbox_id": request.mailbox_id or self.default_mailbox_id,
                "company": request.company,
                "first_name": request.first_name,
                "last_name": request.last_name,
                "tier": request.tier,
                "icp_score": request.icp_score,
                "custom_fields": custom_fields,
            }

            # Call cold-reach API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/prospects/enroll",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    return EnrollmentResult(
                        success=data.get("success", False),
                        entry_id=data.get("entry_id"),
                        prospect_id=data.get("prospect_id"),
                        sequence_id=sequence_id,
                        status=data.get("status"),
                        first_step_due=data.get("first_step_due"),
                        error=data.get("error"),
                    )
                else:
                    error_detail = response.text[:200]
                    logger.error(
                        f"Cold-reach enrollment failed: {response.status_code} - {error_detail}"
                    )
                    return EnrollmentResult(
                        success=False,
                        error=f"API error: {response.status_code}",
                    )

        except httpx.ConnectError:
            logger.error(f"Cannot connect to cold-reach at {self.base_url}")
            return EnrollmentResult(
                success=False,
                error="Connection failed - cold-reach service unavailable",
            )
        except httpx.TimeoutException:
            logger.error(f"Timeout connecting to cold-reach")
            return EnrollmentResult(
                success=False,
                error="Request timeout",
            )
        except Exception as e:
            logger.error(f"Enrollment error: {e}")
            return EnrollmentResult(
                success=False,
                error=str(e),
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

            # Build batch payload
            batch_sequence_id = sequence_id or eligible_leads[0].sequence_id
            batch_mailbox_id = mailbox_id or eligible_leads[0].mailbox_id

            payload = {
                "prospects": [
                    {
                        "email": l.email,
                        "company": l.company,
                        "first_name": l.first_name,
                        "last_name": l.last_name,
                        "tier": l.tier,
                        "icp_score": l.icp_score,
                        "custom_fields": {
                            "coperniq_score": l.coperniq_score,
                            "oem_certifications": l.oem_certifications,
                            "state": l.state,
                        },
                    }
                    for l in eligible_leads
                ],
                "sequence_id": batch_sequence_id,
                "mailbox_id": batch_mailbox_id,
            }

            # Call batch endpoint
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/prospects/enroll/batch",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout * 2,  # Longer timeout for batch
                )

                if response.status_code == 200:
                    data = response.json()
                    api_results = [
                        EnrollmentResult(**r) for r in data.get("results", [])
                    ]
                    return BatchEnrollmentResult(
                        success=data.get("success", False),
                        total=len(leads),
                        enrolled=data.get("enrolled", 0),
                        skipped=len(skipped_results) + data.get("skipped", 0),
                        errors=data.get("errors", 0),
                        results=skipped_results + api_results,
                    )
                else:
                    error_detail = response.text[:200]
                    logger.error(
                        f"Cold-reach batch enrollment failed: {response.status_code}"
                    )
                    return BatchEnrollmentResult(
                        success=False,
                        total=len(leads),
                        enrolled=0,
                        skipped=len(skipped_results),
                        errors=len(eligible_leads),
                        results=skipped_results,
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
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/prospects/status/{email}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return {"error": "Prospect not found"}
                else:
                    return {"error": f"API error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Get status error: {e}")
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Check if cold-reach service is available."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=5.0,
                )
                return {
                    "available": response.status_code == 200,
                    "status_code": response.status_code,
                    "base_url": self.base_url,
                }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "base_url": self.base_url,
            }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def enroll_qualified_lead(
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
            email="john@solar.com",
            company="Solar Electric",
            tier="A",
            coperniq_score=92,
        )
    """
    client = ColdReachClient()
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
        )

    client = ColdReachClient()
    return await client.enroll_leads_batch(requests)
