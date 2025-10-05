"""
Reports API endpoints

Provides endpoints for:
- Generating reports asynchronously
- Retrieving report by ID
- Listing reports by lead
- Getting report status
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import get_db
from app.models.lead import Lead
from app.models.report import Report
from app.schemas.report import (
    ReportGenerateRequest,
    ReportResponse,
    ReportSummary,
    ReportListResponse,
    ReportStatusResponse
)
from app.services.report_generator import ReportGenerator
from app.tasks.agent_tasks import generate_report_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

# Initialize report generator
report_generator = ReportGenerator()


@router.post("/generate", response_model=ReportStatusResponse, status_code=202)
async def generate_report(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered report for a lead (async with Celery)
    
    This endpoint enqueues report generation as a Celery task and returns immediately.
    
    The multi-agent pipeline will:
    1. SearchAgent: Research company information
    2. AnalysisAgent: Generate strategic insights
    3. SynthesisAgent: Create professional report
    
    Use GET /reports/lead/{lead_id} to check status and retrieve completed reports.
    
    Args:
        request: ReportGenerateRequest with lead_id and optional force_refresh
        db: Database session
        
    Returns:
        ReportStatusResponse with status 'generating' and task_id
    """
    # Verify lead exists
    lead = db.query(Lead).filter(Lead.id == request.lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=404,
            detail=f"Lead with ID {request.lead_id} not found"
        )
    
    logger.info(f"Enqueuing Celery report generation for lead {lead.id}: {lead.company_name}")
    
    # Enqueue Celery task for report generation
    task = generate_report_async.delay(
        lead_id=lead.id,
        force_refresh=request.force_refresh if hasattr(request, 'force_refresh') else False
    )
    
    return ReportStatusResponse(
        report_id=None,
        status="generating",
        message=f"Report generation task enqueued for {lead.company_name}. Task ID: {task.id}",
        task_id=task.id
    )


async def _generate_report_background(lead: Lead, db: Session):
    """Background task for report generation"""
    try:
        await report_generator.generate_report(lead, db)
        logger.info(f"Background report generation complete for lead {lead.id}")
    except Exception as e:
        logger.error(f"Background report generation failed for lead {lead.id}: {e}")


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get report by ID
    
    Returns complete report with all content and metadata.
    
    Args:
        report_id: Report ID
        db: Database session
        
    Returns:
        ReportResponse with complete report data
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Report with ID {report_id} not found"
        )
    
    return report


@router.get("/lead/{lead_id}", response_model=ReportListResponse)
def get_reports_by_lead(
    lead_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get all reports for a specific lead
    
    Returns paginated list of reports ordered by creation date (newest first).
    
    Args:
        lead_id: Lead ID to get reports for
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        
    Returns:
        ReportListResponse with paginated reports
    """
    # Verify lead exists
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=404,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    # Get total count
    total = db.query(Report).filter(Report.lead_id == lead_id).count()
    
    # Get paginated reports
    offset = (page - 1) * page_size
    reports = (
        db.query(Report)
        .filter(Report.lead_id == lead_id)
        .order_by(desc(Report.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    
    # Convert to summary objects
    report_summaries = [
        ReportSummary(
            id=r.id,
            lead_id=r.lead_id,
            title=r.title,
            status=r.status,
            confidence_score=r.confidence_score,
            created_at=r.created_at
        )
        for r in reports
    ]
    
    return ReportListResponse(
        reports=report_summaries,
        total=total,
        page=page,
        page_size=page_size
    )



@router.get("/", response_model=ReportListResponse)
def list_all_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (generating, completed, failed)"),
    db: Session = Depends(get_db)
):
    """
    List all reports with optional filtering
    
    Returns paginated list of all reports, optionally filtered by status.
    
    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        status: Optional status filter
        db: Database session
        
    Returns:
        ReportListResponse with paginated reports
    """
    # Build query
    query = db.query(Report)
    
    if status:
        query = query.filter(Report.status == status)
    
    # Get total count
    total = query.count()
    
    # Get paginated reports
    offset = (page - 1) * page_size
    reports = (
        query
        .order_by(desc(Report.created_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    
    # Convert to summary objects
    report_summaries = [
        ReportSummary(
            id=r.id,
            lead_id=r.lead_id,
            title=r.title,
            status=r.status,
            confidence_score=r.confidence_score,
            created_at=r.created_at
        )
        for r in reports
    ]
    
    return ReportListResponse(
        reports=report_summaries,
        total=total,
        page=page,
        page_size=page_size
    )
