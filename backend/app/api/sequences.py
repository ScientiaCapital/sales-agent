"""
Sequences API - FastAPI router for sequence management.

Endpoints:
- POST /api/sequences/ - Create sequence
- GET /api/sequences/ - List sequences
- GET /api/sequences/{id} - Get sequence
- GET /api/sequences/{id}/stats - Get stats
- PATCH /api/sequences/{id}/activate - Activate
- PATCH /api/sequences/{id}/deactivate - Deactivate
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.sequence import Sequence
from app.services.sequences.engine import SequenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sequences", tags=["sequences"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class StepSchema(BaseModel):
    """Email sequence step schema."""
    step_number: int
    delay_days: int = Field(ge=0, description="Days to wait before sending")
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)


class CreateSequenceRequest(BaseModel):
    """Request to create a new sequence."""
    sequence_id: str = Field(min_length=1, max_length=50, description="Unique sequence identifier")
    name: str = Field(min_length=1, max_length=255, description="Human-readable name")
    steps: List[StepSchema] = Field(min_items=1, description="Sequence steps")
    stop_on_reply: bool = Field(default=True, description="Stop when reply received")
    stop_on_bounce: bool = Field(default=True, description="Stop on bounce")
    daily_limit_per_mailbox: int = Field(default=50, ge=1, le=500)


class SequenceResponse(BaseModel):
    """Sequence response schema."""
    id: int
    sequence_id: str
    name: str
    total_steps: int
    is_active: bool
    stop_on_reply: bool
    stop_on_bounce: bool
    daily_limit_per_mailbox: int
    created_at: str

    class Config:
        from_attributes = True


class SequenceStatsResponse(BaseModel):
    """Sequence statistics response."""
    sequence_id: str
    name: str
    total_enrolled: int
    status_breakdown: dict
    total_emails_sent: int
    total_opens: int
    total_clicks: int
    total_replies: int
    open_rate: float
    reply_rate: float


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/", response_model=SequenceResponse, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    request: CreateSequenceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new email sequence.

    Args:
        request: Sequence configuration
        db: Database session

    Returns:
        Created sequence
    """
    try:
        engine = SequenceEngine(db)

        # Convert steps to dict format
        steps_data = [step.model_dump() for step in request.steps]

        sequence = await engine.create_sequence(
            sequence_id=request.sequence_id,
            name=request.name,
            steps=steps_data,
            stop_on_reply=request.stop_on_reply,
            stop_on_bounce=request.stop_on_bounce,
            daily_limit_per_mailbox=request.daily_limit_per_mailbox,
        )

        return SequenceResponse(
            id=sequence.id,
            sequence_id=sequence.sequence_id,
            name=sequence.name,
            total_steps=sequence.total_steps,
            is_active=sequence.is_active,
            stop_on_reply=sequence.stop_on_reply,
            stop_on_bounce=sequence.stop_on_bounce,
            daily_limit_per_mailbox=sequence.daily_limit_per_mailbox,
            created_at=sequence.created_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to create sequence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sequence: {str(e)}"
        )


@router.get("/", response_model=List[SequenceResponse])
async def list_sequences(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    List all sequences.

    Args:
        active_only: Only return active sequences
        db: Database session

    Returns:
        List of sequences
    """
    try:
        query = select(Sequence)
        if active_only:
            query = query.where(Sequence.is_active == True)
        query = query.order_by(Sequence.created_at.desc())

        result = await db.execute(query)
        sequences = result.scalars().all()

        return [
            SequenceResponse(
                id=seq.id,
                sequence_id=seq.sequence_id,
                name=seq.name,
                total_steps=seq.total_steps,
                is_active=seq.is_active,
                stop_on_reply=seq.stop_on_reply,
                stop_on_bounce=seq.stop_on_bounce,
                daily_limit_per_mailbox=seq.daily_limit_per_mailbox,
                created_at=seq.created_at.isoformat(),
            )
            for seq in sequences
        ]

    except Exception as e:
        logger.error(f"Failed to list sequences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sequences: {str(e)}"
        )


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific sequence by ID.

    Args:
        sequence_id: Unique sequence identifier
        db: Database session

    Returns:
        Sequence details
    """
    try:
        query = select(Sequence).where(Sequence.sequence_id == sequence_id)
        result = await db.execute(query)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sequence '{sequence_id}' not found"
            )

        return SequenceResponse(
            id=sequence.id,
            sequence_id=sequence.sequence_id,
            name=sequence.name,
            total_steps=sequence.total_steps,
            is_active=sequence.is_active,
            stop_on_reply=sequence.stop_on_reply,
            stop_on_bounce=sequence.stop_on_bounce,
            daily_limit_per_mailbox=sequence.daily_limit_per_mailbox,
            created_at=sequence.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sequence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sequence: {str(e)}"
        )


@router.get("/{sequence_id}/stats", response_model=SequenceStatsResponse)
async def get_sequence_stats(
    sequence_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics for a sequence.

    Args:
        sequence_id: Unique sequence identifier
        db: Database session

    Returns:
        Sequence statistics
    """
    try:
        engine = SequenceEngine(db)
        stats = await engine.get_sequence_stats(sequence_id)

        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=stats["error"]
            )

        return SequenceStatsResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.patch("/{sequence_id}/activate", response_model=SequenceResponse)
async def activate_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a sequence.

    Args:
        sequence_id: Unique sequence identifier
        db: Database session

    Returns:
        Updated sequence
    """
    try:
        query = select(Sequence).where(Sequence.sequence_id == sequence_id)
        result = await db.execute(query)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sequence '{sequence_id}' not found"
            )

        sequence.is_active = True
        await db.commit()
        await db.refresh(sequence)

        return SequenceResponse(
            id=sequence.id,
            sequence_id=sequence.sequence_id,
            name=sequence.name,
            total_steps=sequence.total_steps,
            is_active=sequence.is_active,
            stop_on_reply=sequence.stop_on_reply,
            stop_on_bounce=sequence.stop_on_bounce,
            daily_limit_per_mailbox=sequence.daily_limit_per_mailbox,
            created_at=sequence.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate sequence: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate sequence: {str(e)}"
        )


@router.patch("/{sequence_id}/deactivate", response_model=SequenceResponse)
async def deactivate_sequence(
    sequence_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a sequence.

    Args:
        sequence_id: Unique sequence identifier
        db: Database session

    Returns:
        Updated sequence
    """
    try:
        query = select(Sequence).where(Sequence.sequence_id == sequence_id)
        result = await db.execute(query)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sequence '{sequence_id}' not found"
            )

        sequence.is_active = False
        await db.commit()
        await db.refresh(sequence)

        return SequenceResponse(
            id=sequence.id,
            sequence_id=sequence.sequence_id,
            name=sequence.name,
            total_steps=sequence.total_steps,
            is_active=sequence.is_active,
            stop_on_reply=sequence.stop_on_reply,
            stop_on_bounce=sequence.stop_on_bounce,
            daily_limit_per_mailbox=sequence.daily_limit_per_mailbox,
            created_at=sequence.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate sequence: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate sequence: {str(e)}"
        )
