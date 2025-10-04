"""
Lead qualification API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.models import Lead, CerebrasAPICall, get_db
from app.schemas import LeadQualificationRequest, LeadQualificationResponse, LeadListResponse
from app.services import CerebrasService
from app.services.csv_importer import CSVImportService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/leads", tags=["leads"])

# Initialize services
cerebras_service = CerebrasService()
csv_importer = CSVImportService()


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
    logger.info(f"Qualifying lead: company={request.company_name}, industry={request.industry}")
    score, reasoning, latency_ms = cerebras_service.qualify_lead(
        company_name=request.company_name,
        company_website=request.company_website,
        company_size=request.company_size,
        industry=request.industry,
        contact_name=request.contact_name,
        contact_title=request.contact_title,
        notes=request.notes
    )
    logger.info(f"Lead qualified: company={request.company_name}, score={score}, latency={latency_ms}ms")

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


@router.post("/import/csv")
async def import_leads_from_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Bulk import leads from CSV file

    **Performance Target**: 1,000 leads in < 5 seconds

    **Required CSV Columns**:
    - company_name (max 255 chars)
    - industry
    - company_website

    **Optional CSV Columns**:
    - company_size
    - contact_name
    - contact_email (must be valid email format)
    - contact_phone
    - contact_title
    - notes

    **CSV Format**:
    ```csv
    company_name,industry,company_website,company_size,contact_name,contact_email
    TechCorp,SaaS,https://techcorp.com,50-200,John Doe,john@techcorp.com
    DataInc,Analytics,https://datainc.com,200-500,Jane Smith,jane@datainc.com
    ```

    Returns import statistics including:
    - Total leads processed
    - Successfully imported count
    - Import duration in milliseconds
    - Import rate (leads per second)
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file (.csv extension)"
        )

    # Read file content
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be UTF-8 encoded"
        )

    # Parse CSV and validate
    leads = csv_importer.parse_csv_file(csv_content)

    # Bulk import leads
    result = csv_importer.bulk_import_leads(db, leads)

    logger.info(f"CSV import completed: {file.filename} - {result}")
    
    return {
        "message": "Leads imported successfully",
        "filename": file.filename,
        **result
    }
