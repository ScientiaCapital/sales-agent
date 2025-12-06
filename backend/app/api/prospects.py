"""
Prospects API - FastAPI router for prospect enrollment and execution.

Endpoints:
- POST /api/prospects/enroll - Enroll prospect in sequence
- POST /api/prospects/enroll/batch - Batch enrollment
- POST /api/prospects/execute-step - Execute step
- POST /api/prospects/process-due - Process due emails (cron)
- GET /api/prospects/status/{email} - Get prospect status
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.lead import Lead
from app.models.sequence_entry import SequenceEntry
from app.services.sequences.engine import SequenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prospects", tags=["prospects"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class EnrollProspectRequest(BaseModel):
    """Request to enroll a prospect in a sequence."""
    email: EmailStr
    sequence_id: str = Field(min_length=1, description="Sequence identifier")
    mailbox_id: int = Field(ge=1, description="Mailbox ID to send from")
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tier: Optional[str] = Field(None, description="Qualification tier (A/B/C/D)")
    icp_score: Optional[float] = Field(None, ge=0, le=100)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EnrollmentResponse(BaseModel):
    """Response from enrollment attempt."""
    success: bool
    entry_id: Optional[int] = None
    prospect_id: Optional[int] = None
    sequence_id: Optional[str] = None
    status: Optional[str] = None
    first_step_due: Optional[str] = None
    error: Optional[str] = None


class BatchEnrollRequest(BaseModel):
    """Batch enrollment request."""
    prospects: List[EnrollProspectRequest] = Field(min_items=1, max_items=100)


class BatchEnrollmentResponse(BaseModel):
    """Batch enrollment response."""
    success: bool
    total: int
    enrolled: int
    errors: int
    results: List[EnrollmentResponse]


class ExecuteStepRequest(BaseModel):
    """Request to execute a sequence step."""
    entry_id: int = Field(ge=1, description="Sequence entry ID")


class ExecuteStepResponse(BaseModel):
    """Response from step execution."""
    success: bool
    action: Optional[str] = None
    message_id: Optional[str] = None
    test_mode: Optional[bool] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    next_step_due: Optional[str] = None
    error: Optional[str] = None


class ProcessDueResponse(BaseModel):
    """Response from processing due emails."""
    processed: int
    sent: int
    errors: int
    timestamp: str


class ProspectStatusResponse(BaseModel):
    """Prospect status response."""
    email: str
    prospect_id: int
    enrollments: List[Dict[str, Any]]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_prospect(
    request: EnrollProspectRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Enroll a prospect in an email sequence.

    Args:
        request: Enrollment details
        db: Database session

    Returns:
        Enrollment result
    """
    try:
        engine = SequenceEngine(db)

        result = await engine.enroll_prospect(
            prospect_email=request.email,
            sequence_id=request.sequence_id,
            mailbox_id=request.mailbox_id,
            custom_fields=request.custom_fields,
            company_name=request.company_name,
            first_name=request.first_name,
            last_name=request.last_name,
            tier=request.tier,
            icp_score=request.icp_score,
        )

        return EnrollmentResponse(**result)

    except Exception as e:
        logger.error(f"Failed to enroll prospect: {e}")
        return EnrollmentResponse(
            success=False,
            error=str(e)
        )


@router.post("/enroll/batch", response_model=BatchEnrollmentResponse)
async def enroll_prospects_batch(
    request: BatchEnrollRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Enroll multiple prospects in sequences.

    Args:
        request: Batch enrollment details
        db: Database session

    Returns:
        Batch enrollment results
    """
    try:
        engine = SequenceEngine(db)
        results = []
        enrolled = 0
        errors = 0

        for prospect_req in request.prospects:
            try:
                result = await engine.enroll_prospect(
                    prospect_email=prospect_req.email,
                    sequence_id=prospect_req.sequence_id,
                    mailbox_id=prospect_req.mailbox_id,
                    custom_fields=prospect_req.custom_fields,
                    company_name=prospect_req.company_name,
                    first_name=prospect_req.first_name,
                    last_name=prospect_req.last_name,
                    tier=prospect_req.tier,
                    icp_score=prospect_req.icp_score,
                )

                results.append(EnrollmentResponse(**result))

                if result["success"]:
                    enrolled += 1
                else:
                    errors += 1

            except Exception as e:
                logger.error(f"Failed to enroll {prospect_req.email}: {e}")
                results.append(EnrollmentResponse(
                    success=False,
                    error=str(e)
                ))
                errors += 1

        return BatchEnrollmentResponse(
            success=True,
            total=len(request.prospects),
            enrolled=enrolled,
            errors=errors,
            results=results,
        )

    except Exception as e:
        logger.error(f"Batch enrollment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch enrollment failed: {str(e)}"
        )


@router.post("/execute-step", response_model=ExecuteStepResponse)
async def execute_step(
    request: ExecuteStepRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a sequence step for an entry.

    Args:
        request: Execution request
        db: Database session

    Returns:
        Execution result
    """
    try:
        engine = SequenceEngine(db)
        result = await engine.execute_step(request.entry_id)

        return ExecuteStepResponse(**result)

    except Exception as e:
        logger.error(f"Failed to execute step: {e}")
        return ExecuteStepResponse(
            success=False,
            error=str(e)
        )


@router.post("/process-due", response_model=ProcessDueResponse)
async def process_due_emails(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Process all due emails (cron job endpoint).

    Args:
        limit: Maximum number of emails to process
        db: Database session

    Returns:
        Processing statistics
    """
    try:
        engine = SequenceEngine(db)
        result = await engine.process_due_emails(limit=limit)

        return ProcessDueResponse(**result)

    except Exception as e:
        logger.error(f"Failed to process due emails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process due emails: {str(e)}"
        )


@router.get("/status/{email}", response_model=ProspectStatusResponse)
async def get_prospect_status(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get status of a prospect across all sequences.

    Args:
        email: Prospect email address
        db: Database session

    Returns:
        Prospect status and enrollments
    """
    try:
        # Find prospect
        query = select(Lead).where(Lead.contact_email == email)
        result = await db.execute(query)
        prospect = result.scalar_one_or_none()

        if not prospect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prospect with email '{email}' not found"
            )

        # Get all sequence entries
        entry_query = select(SequenceEntry).where(SequenceEntry.lead_id == prospect.id)
        entry_result = await db.execute(entry_query)
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

        return ProspectStatusResponse(
            email=email,
            prospect_id=prospect.id,
            enrollments=enrollments,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prospect status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prospect status: {str(e)}"
        )
