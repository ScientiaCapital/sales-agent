"""
Lead qualification API endpoints
"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.models import Lead, CerebrasAPICall, get_db
from app.schemas import LeadQualificationRequest, LeadQualificationResponse, LeadListResponse
from app.services import CerebrasService, LeadScorer, SignalData
from app.services.csv_importer import CSVImportService
from app.services.cache_manager import CacheManager
from app.core.cache import get_cache
from app.core.logging import setup_logging
from app.core.exceptions import (
    LeadNotFoundError,
    InvalidFileFormatError,
    FileSizeExceededError,
    ValidationError,
    DatabaseError
)

logger = setup_logging(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])

# Initialize services
cerebras_service = CerebrasService()
csv_importer = CSVImportService()
lead_scorer = LeadScorer()  # Default weights


@router.post("/qualify", response_model=LeadQualificationResponse, status_code=201)
async def qualify_lead(
    request: LeadQualificationRequest,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(get_cache)
):
    """
    Qualify a new lead using hybrid AI + rule-based scoring

    This endpoint implements:
    1. Check Redis cache for existing qualification (< 10ms)
    2. On cache miss: Call Cerebras API (~945ms) for AI insights
    3. Apply multi-factor rule-based scoring (company size, industry, signals)
    4. Combine AI and rule-based scores with weighted average
    5. Cache the result with 24h TTL
    6. Store in database and track API usage

    Returns the qualified lead with hybrid score, reasoning, and recommendations.
    """

    # Check cache first (cache-aside pattern)
    logger.info(f"Qualifying lead: company={request.company_name}, industry={request.industry}")
    cached_result = await cache.get_cached_qualification(
        company_name=request.company_name,
        industry=request.industry
    )
    
    cache_hit = False
    ai_score = 50.0  # Default if AI fails
    ai_reasoning = ""

    if cached_result:
        # Cache hit - use cached AI qualification
        ai_score = cached_result["score"]
        ai_reasoning = cached_result["reasoning"]
        latency_ms = cached_result.get("latency_ms", 0)
        cache_hit = True
        logger.info(f"Cache HIT for {request.company_name} - returning cached qualification")
    else:
        # Cache miss - call Cerebras API
        logger.info(f"Cache MISS for {request.company_name} - calling Cerebras API")
        ai_score, ai_reasoning, latency_ms = cerebras_service.qualify_lead(
            company_name=request.company_name,
            company_website=request.company_website,
            company_size=request.company_size,
            industry=request.industry,
            contact_name=request.contact_name,
            contact_title=request.contact_title,
            notes=request.notes
        )
        logger.info(f"AI qualification: company={request.company_name}, score={ai_score}, latency={latency_ms}ms")

        # Cache the AI result for future requests
        await cache.cache_qualification(
            company_name=request.company_name,
            industry=request.industry,
            qualification_data={
                "score": ai_score,
                "reasoning": ai_reasoning,
                "latency_ms": latency_ms,
                "model": cerebras_service.default_model
            }
        )

    # Apply rule-based scoring for multi-factor analysis
    lead_data = {
        "company_name": request.company_name,
        "company_size": request.company_size,
        "industry": request.industry,
        "company_website": request.company_website
    }

    # Create signals if available (extend this based on your data sources)
    signals = None
    if hasattr(request, 'signals') and request.signals:
        signals = SignalData(**request.signals)

    # Calculate rule-based score
    scoring_result = lead_scorer.calculate_score(lead_data, signals)

    # Combine AI and rule-based scores (weighted average)
    # 60% AI score, 40% rule-based score for balanced approach
    final_score = (ai_score * 0.6) + (scoring_result.score * 0.4)

    # Combine reasoning from both approaches
    combined_reasoning = f"AI Analysis: {ai_reasoning} | Rule-Based Analysis: {scoring_result.reasoning}"

    # Use tier and recommendations from rule-based scorer
    tier = scoring_result.tier
    recommendations = scoring_result.recommendations

    # Create Lead record with hybrid scoring
    lead = Lead(
        company_name=request.company_name,
        company_website=request.company_website,
        company_size=request.company_size,
        industry=request.industry,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        contact_title=request.contact_title,
        qualification_score=round(final_score, 1),
        qualification_reasoning=combined_reasoning,
        qualification_model=f"{cerebras_service.default_model}+LeadScorer",
        qualification_latency_ms=latency_ms,
        qualified_at=datetime.now(),
        notes=request.notes,
        additional_data={
            "ai_score": round(ai_score, 1),
            "rule_based_score": round(scoring_result.score, 1),
            "confidence": round(scoring_result.confidence, 2),
            "tier": tier,
            "recommendations": recommendations,
            "scoring_factors": scoring_result.factors
        }
    )

    db.add(lead)
    db.flush()  # Flush to get the lead ID

    # Track API call for cost management (only if not cached)
    if not cache_hit:
        # Note: OpenAI SDK doesn't provide token counts directly in Cerebras mode
        # Estimate based on content length (rough approximation)
        prompt_est = len(str(request.dict())) // 4  # Rough token estimate
        completion_est = len(ai_reasoning) // 4

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
            operation_type="lead_qualification_hybrid",
            success=True,
            metadata={
                "final_score": round(final_score, 1),
                "ai_score": round(ai_score, 1),
                "rule_score": round(scoring_result.score, 1),
                "tier": tier
            }
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
        raise LeadNotFoundError(lead_id=lead_id)
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
        raise InvalidFileFormatError(
            message="File must be a CSV file (.csv extension)",
            details={"filename": file.filename}
        )

    # Read file content
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise InvalidFileFormatError(
            message="File must be UTF-8 encoded",
            details={"filename": file.filename}
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
