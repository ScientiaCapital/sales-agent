"""
Lead qualification API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.models import Lead, CerebrasAPICall, get_db
from app.schemas import LeadQualificationRequest, LeadQualificationResponse, LeadListResponse
from app.services import CerebrasService

router = APIRouter(prefix="/api/leads", tags=["leads"])

# Initialize Cerebras service
cerebras_service = CerebrasService()


@router.post("/qualify", response_model=LeadQualificationResponse, status_code=201)
async def qualify_lead(
    request: LeadQualificationRequest,
    db: Session = Depends(get_db)
):
    """
    Qualify a new lead using Cerebras AI inference

    This endpoint:
    1. Receives lead information
    2. Calls Cerebras API for real-time qualification (<100ms target)
    3. Stores the qualified lead in the database
    4. Tracks API usage and costs

    Returns the qualified lead with score and reasoning.
    """

    # Call Cerebras service for qualification
    score, reasoning, latency_ms = cerebras_service.qualify_lead(
        company_name=request.company_name,
        company_website=request.company_website,
        company_size=request.company_size,
        industry=request.industry,
        contact_name=request.contact_name,
        contact_title=request.contact_title,
        notes=request.notes
    )

    # Create Lead record
    lead = Lead(
        company_name=request.company_name,
        company_website=request.company_website,
        company_size=request.company_size,
        industry=request.industry,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        contact_title=request.contact_title,
        qualification_score=score,
        qualification_reasoning=reasoning,
        qualification_model=cerebras_service.default_model,
        qualification_latency_ms=latency_ms,
        qualified_at=datetime.now(),
        notes=request.notes
    )

    db.add(lead)
    db.flush()  # Flush to get the lead ID

    # Track API call for cost management
    # Note: OpenAI SDK doesn't provide token counts directly in Cerebras mode
    # Estimate based on content length (rough approximation)
    prompt_est = len(str(request.dict())) // 4  # Rough token estimate
    completion_est = len(reasoning) // 4

    cost_info = cerebras_service.calculate_cost(prompt_est, completion_est)

    api_call = CerebrasAPICall(
        endpoint="/chat/completions",
        model=cerebras_service.default_model,
        prompt_tokens=prompt_est,
        completion_tokens=completion_est,
        total_tokens=prompt_est + completion_est,
        latency_ms=latency_ms,
        cache_hit=False,
        cost_usd=cost_info["total_cost_usd"],
        input_cost_usd=cost_info["input_cost_usd"],
        output_cost_usd=cost_info["output_cost_usd"],
        operation_type="lead_qualification",
        success=True
    )

    db.add(api_call)
    db.commit()
    db.refresh(lead)

    return lead


@router.get("/", response_model=List[LeadListResponse])
async def list_leads(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all leads with pagination

    Returns a list of leads ordered by creation date (newest first).
    """
    leads = db.query(Lead).order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()
    return leads


@router.get("/{lead_id}", response_model=LeadQualificationResponse)
async def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """
    Get a specific lead by ID

    Returns full lead details including qualification score and reasoning.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
    return lead
