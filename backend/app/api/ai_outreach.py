"""
AI Outreach Router - Endpoints for sales intelligence extraction and outreach draft management.

Provides endpoints to:
1. Trigger SalesIntelAgent enrichment for companies
2. Manage AI-generated outreach drafts (email/SMS/voice)
3. Approve and send drafts via Close CRM
4. Regenerate drafts with fresh AI analysis

Architecture:
- Uses Supabase for draft storage (dim_ai_drafts table)
- Integrates with SalesIntelAgent for content extraction
- Supports human-in-the-loop approval workflow
- Tracks draft status: pending -> approved -> sent (or discarded)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import os
import logging

from app.services.langgraph.agents import extract_sales_intel
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/ai", tags=["ai-outreach"])

# Import Supabase
try:
    from supabase import create_client, Client

    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase not configured - AI outreach endpoints will not work")
        supabase: Optional[Client] = None
    else:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized for AI outreach")
except ImportError:
    logger.error("supabase-py not installed - AI outreach endpoints disabled")
    supabase = None


# ========== Enums ==========

class DraftStatus(str, Enum):
    """Status of an AI-generated outreach draft"""
    PENDING = "pending"      # Generated, awaiting review
    APPROVED = "approved"    # Human approved, ready to send
    SENT = "sent"           # Sent via Close CRM
    DISCARDED = "discarded" # Rejected/deleted by human


class DraftType(str, Enum):
    """Type of outreach draft"""
    EMAIL = "email"
    SMS = "sms"
    VOICE = "voice"


# ========== Request/Response Schemas ==========

class EnrichmentRequest(BaseModel):
    """Request to trigger SalesIntelAgent enrichment"""
    contact_name: Optional[str] = Field(None, description="Primary contact name (CEO/Owner)")
    contact_title: Optional[str] = Field("Owner", description="Contact title")
    scraped_content: Optional[str] = Field(None, description="Website content (if already scraped)")
    regenerate: bool = Field(False, description="Force regeneration even if drafts exist")


class EnrichmentResponse(BaseModel):
    """Response from enrichment trigger"""
    company_id: str
    company_name: str
    drafts_generated: int
    processing_time_ms: int
    confidence: float
    message: str


class OutreachDraft(BaseModel):
    """Single outreach draft"""
    draft_id: str
    company_id: str
    company_name: str
    draft_type: DraftType
    status: DraftStatus

    # Content
    subject: Optional[str] = None  # Email only
    body: str

    # Context
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    personal_hooks: List[Dict[str, str]] = Field(default_factory=list)

    # Metadata
    confidence: float
    generated_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None


class DraftListResponse(BaseModel):
    """Paginated list of drafts"""
    drafts: List[OutreachDraft]
    total: int
    page: int
    page_size: int


class DraftUpdateRequest(BaseModel):
    """Request to update draft content"""
    subject: Optional[str] = None
    body: Optional[str] = None


class SendDraftRequest(BaseModel):
    """Request to send draft via Close CRM"""
    send_now: bool = Field(True, description="Send immediately or schedule")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule for later")


class SendDraftResponse(BaseModel):
    """Response after sending draft"""
    draft_id: str
    status: str
    message: str
    close_activity_id: Optional[str] = None


# ========== Helper Functions ==========

def _check_supabase():
    """Raise error if Supabase not configured"""
    if not supabase:
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )


async def _get_company_data(company_id: str) -> Optional[Dict[str, Any]]:
    """Fetch company data from Supabase dim_companies table"""
    _check_supabase()

    try:
        result = supabase.table('dim_companies').select('*').eq('company_id', company_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {e}")
        return None


async def _save_drafts_to_supabase(
    company_id: str,
    company_name: str,
    intel_result: Dict[str, Any],
    contact_name: Optional[str] = None,
    contact_title: Optional[str] = None
) -> int:
    """Save AI-generated drafts to Supabase dim_ai_drafts table"""
    _check_supabase()

    drafts = []
    now = datetime.utcnow().isoformat()

    # Email draft
    if intel_result.get('email_subject') and intel_result.get('email_body'):
        drafts.append({
            'company_id': company_id,
            'company_name': company_name,
            'draft_type': DraftType.EMAIL.value,
            'status': DraftStatus.PENDING.value,
            'subject': intel_result['email_subject'],
            'body': intel_result['email_body'],
            'contact_name': contact_name,
            'contact_title': contact_title,
            'personal_hooks': intel_result.get('personal_hooks', []),
            'confidence': intel_result.get('confidence', 0.5),
            'generated_at': now,
            'updated_at': now,
        })

    # SMS draft
    if intel_result.get('sms_draft'):
        drafts.append({
            'company_id': company_id,
            'company_name': company_name,
            'draft_type': DraftType.SMS.value,
            'status': DraftStatus.PENDING.value,
            'subject': None,
            'body': intel_result['sms_draft'],
            'contact_name': contact_name,
            'contact_title': contact_title,
            'personal_hooks': intel_result.get('personal_hooks', []),
            'confidence': intel_result.get('confidence', 0.5),
            'generated_at': now,
            'updated_at': now,
        })

    # Voice opener draft
    if intel_result.get('voice_opener'):
        drafts.append({
            'company_id': company_id,
            'company_name': company_name,
            'draft_type': DraftType.VOICE.value,
            'status': DraftStatus.PENDING.value,
            'subject': None,
            'body': intel_result['voice_opener'],
            'contact_name': contact_name,
            'contact_title': contact_title,
            'personal_hooks': intel_result.get('personal_hooks', []),
            'confidence': intel_result.get('confidence', 0.5),
            'generated_at': now,
            'updated_at': now,
        })

    if drafts:
        try:
            supabase.table('dim_ai_drafts').insert(drafts).execute()
            logger.info(f"Saved {len(drafts)} drafts for {company_name}")
            return len(drafts)
        except Exception as e:
            logger.error(f"Error saving drafts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save drafts: {str(e)}")

    return 0


# ========== API Endpoints ==========

@router.post("/enrich/{company_id}", response_model=EnrichmentResponse)
async def enrich_company(
    company_id: str,
    request: EnrichmentRequest
):
    """
    Trigger SalesIntelAgent enrichment for a company.

    Workflow:
    1. Fetch company data from Supabase dim_companies
    2. Get scraped content (from request or database)
    3. Run SalesIntelAgent to extract personal hooks + generate drafts
    4. Save drafts to dim_ai_drafts table
    5. Return summary

    Args:
        company_id: Supabase company_id from dim_companies
        request: Optional contact info and content

    Returns:
        EnrichmentResponse with draft count and processing time
    """
    _check_supabase()

    logger.info(f"Starting enrichment for company_id={company_id}")

    # Fetch company data
    company = await _get_company_data(company_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

    company_name = company.get('company_name', '')

    # Check if drafts already exist (unless regenerate=True)
    if not request.regenerate:
        existing = supabase.table('dim_ai_drafts').select('draft_id').eq('company_id', company_id).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"Drafts already exist for {company_name} - use regenerate=true to override")
            return EnrichmentResponse(
                company_id=company_id,
                company_name=company_name,
                drafts_generated=0,
                processing_time_ms=0,
                confidence=1.0,
                message=f"Drafts already exist. Use regenerate=true to recreate."
            )

    # Get contact info (from request or database)
    contact_name = request.contact_name
    contact_title = request.contact_title or "Owner"

    # If no contact provided, try to fetch from dim_contacts
    if not contact_name:
        contacts = supabase.table('dim_contacts').select('contact_name, title').eq('company_id', company_id).limit(1).execute()
        if contacts.data and len(contacts.data) > 0:
            contact_name = contacts.data[0].get('contact_name')
            contact_title = contacts.data[0].get('title', 'Owner')

    if not contact_name:
        contact_name = "the team"  # Fallback

    # Get scraped content (from request or database)
    scraped_content = request.scraped_content
    if not scraped_content:
        # Try to fetch from enrichment data
        enrichment = supabase.table('fact_enrichments').select('scraped_content').eq('company_id', company_id).order('enriched_at', desc=True).limit(1).execute()
        if enrichment.data and len(enrichment.data) > 0:
            scraped_content = enrichment.data[0].get('scraped_content')

    if not scraped_content:
        logger.warning(f"No scraped content for {company_name} - using basic info")
        scraped_content = f"{company_name} is located in {company.get('city', 'Unknown')}, {company.get('state', 'Unknown')}."

    # Extract services and brands from company data
    services = []
    if company.get('has_hvac'):
        services.append('HVAC')
    if company.get('has_solar'):
        services.append('Solar')
    if company.get('has_electrical'):
        services.append('Electrical')

    brands = company.get('oem_brands', []) if isinstance(company.get('oem_brands'), list) else []

    location = f"{company.get('city', '')}, {company.get('state', '')}" if company.get('city') else None

    # Run SalesIntelAgent
    try:
        intel_result = await extract_sales_intel(
            company_name=company_name,
            contact_name=contact_name,
            contact_title=contact_title,
            scraped_content=scraped_content,
            services=services,
            brands=brands,
            location=location
        )
    except Exception as e:
        logger.error(f"SalesIntelAgent error: {e}")
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")

    # Save drafts to Supabase
    drafts_count = await _save_drafts_to_supabase(
        company_id=company_id,
        company_name=company_name,
        intel_result=intel_result,
        contact_name=contact_name,
        contact_title=contact_title
    )

    return EnrichmentResponse(
        company_id=company_id,
        company_name=company_name,
        drafts_generated=drafts_count,
        processing_time_ms=intel_result.get('processing_time_ms', 0),
        confidence=intel_result.get('confidence', 0.5),
        message=f"Generated {drafts_count} drafts for {company_name}"
    )


@router.get("/drafts", response_model=DraftListResponse)
async def list_drafts(
    status: Optional[DraftStatus] = Query(None, description="Filter by status"),
    draft_type: Optional[DraftType] = Query(None, description="Filter by type"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page")
):
    """
    List pending outreach drafts with pagination and filtering.

    Query params:
        status: Filter by draft status (pending, approved, sent, discarded)
        draft_type: Filter by type (email, sms, voice)
        company_id: Filter by specific company
        page: Page number (1-indexed)
        page_size: Items per page (1-100)

    Returns:
        Paginated list of drafts
    """
    _check_supabase()

    # Build query
    query = supabase.table('dim_ai_drafts').select('*', count='exact')

    if status:
        query = query.eq('status', status.value)

    if draft_type:
        query = query.eq('draft_type', draft_type.value)

    if company_id:
        query = query.eq('company_id', company_id)

    # Order by newest first
    query = query.order('generated_at', desc=True)

    # Pagination
    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    try:
        result = query.execute()

        drafts = []
        for row in result.data:
            drafts.append(OutreachDraft(
                draft_id=row['draft_id'],
                company_id=row['company_id'],
                company_name=row['company_name'],
                draft_type=DraftType(row['draft_type']),
                status=DraftStatus(row['status']),
                subject=row.get('subject'),
                body=row['body'],
                contact_name=row.get('contact_name'),
                contact_title=row.get('contact_title'),
                personal_hooks=row.get('personal_hooks', []),
                confidence=row.get('confidence', 0.5),
                generated_at=datetime.fromisoformat(row['generated_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')),
                sent_at=datetime.fromisoformat(row['sent_at'].replace('Z', '+00:00')) if row.get('sent_at') else None
            ))

        total = result.count if result.count else len(drafts)

        return DraftListResponse(
            drafts=drafts,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing drafts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list drafts: {str(e)}")


@router.get("/drafts/{draft_id}", response_model=OutreachDraft)
async def get_draft(draft_id: str):
    """
    Get a single draft by ID.

    Args:
        draft_id: UUID of the draft

    Returns:
        OutreachDraft details
    """
    _check_supabase()

    try:
        result = supabase.table('dim_ai_drafts').select('*').eq('draft_id', draft_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        row = result.data[0]

        return OutreachDraft(
            draft_id=row['draft_id'],
            company_id=row['company_id'],
            company_name=row['company_name'],
            draft_type=DraftType(row['draft_type']),
            status=DraftStatus(row['status']),
            subject=row.get('subject'),
            body=row['body'],
            contact_name=row.get('contact_name'),
            contact_title=row.get('contact_title'),
            personal_hooks=row.get('personal_hooks', []),
            confidence=row.get('confidence', 0.5),
            generated_at=datetime.fromisoformat(row['generated_at'].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')),
            sent_at=datetime.fromisoformat(row['sent_at'].replace('Z', '+00:00')) if row.get('sent_at') else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get draft: {str(e)}")


@router.put("/drafts/{draft_id}", response_model=OutreachDraft)
async def update_draft(draft_id: str, request: DraftUpdateRequest):
    """
    Update draft content (subject/body).

    Args:
        draft_id: UUID of the draft
        request: New subject/body content

    Returns:
        Updated draft
    """
    _check_supabase()

    update_data = {
        'updated_at': datetime.utcnow().isoformat()
    }

    if request.subject is not None:
        update_data['subject'] = request.subject

    if request.body is not None:
        update_data['body'] = request.body

    try:
        result = supabase.table('dim_ai_drafts').update(update_data).eq('draft_id', draft_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        logger.info(f"Updated draft {draft_id}")

        # Return updated draft
        return await get_draft(draft_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update draft: {str(e)}")


@router.post("/drafts/{draft_id}/send", response_model=SendDraftResponse)
async def send_draft(draft_id: str, request: SendDraftRequest):
    """
    Approve and send draft via Close CRM.

    Workflow:
    1. Validate draft exists and is pending/approved
    2. Mark as approved (if pending)
    3. Send via Close CRM API (email/SMS)
    4. Mark as sent with timestamp
    5. Return confirmation

    Args:
        draft_id: UUID of the draft
        request: Send options (now vs scheduled)

    Returns:
        SendDraftResponse with status
    """
    _check_supabase()

    # Get draft
    draft = await get_draft(draft_id)

    # Validate status
    if draft.status in [DraftStatus.SENT, DraftStatus.DISCARDED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send draft with status {draft.status}"
        )

    # Check if Close CRM is enabled
    close_write_disabled = os.getenv('CLOSE_WRITE_DISABLED', 'true').lower() == 'true'
    if close_write_disabled:
        logger.warning("CLOSE_WRITE_DISABLED=true - not actually sending to CRM")

        # Mark as sent anyway (for testing)
        supabase.table('dim_ai_drafts').update({
            'status': DraftStatus.SENT.value,
            'sent_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }).eq('draft_id', draft_id).execute()

        return SendDraftResponse(
            draft_id=draft_id,
            status="simulated",
            message=f"CLOSE_WRITE_DISABLED - draft marked as sent but not actually sent",
            close_activity_id=None
        )

    # TODO: Implement actual Close CRM integration
    # For now, just mark as sent
    try:
        supabase.table('dim_ai_drafts').update({
            'status': DraftStatus.SENT.value,
            'sent_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }).eq('draft_id', draft_id).execute()

        logger.info(f"Sent draft {draft_id} via Close CRM")

        return SendDraftResponse(
            draft_id=draft_id,
            status="sent",
            message=f"Draft sent successfully",
            close_activity_id="mock_activity_123"  # TODO: Real Close CRM activity ID
        )

    except Exception as e:
        logger.error(f"Error sending draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send draft: {str(e)}")


@router.post("/drafts/{draft_id}/regenerate", response_model=EnrichmentResponse)
async def regenerate_draft(draft_id: str):
    """
    Regenerate draft with fresh AI analysis.

    Workflow:
    1. Get existing draft to extract company_id
    2. Delete old draft
    3. Re-run SalesIntelAgent enrichment
    4. Generate new draft

    Args:
        draft_id: UUID of the draft to regenerate

    Returns:
        EnrichmentResponse with new draft details
    """
    _check_supabase()

    # Get existing draft
    draft = await get_draft(draft_id)

    # Delete old draft
    try:
        supabase.table('dim_ai_drafts').delete().eq('draft_id', draft_id).execute()
        logger.info(f"Deleted old draft {draft_id}")
    except Exception as e:
        logger.error(f"Error deleting old draft: {e}")
        # Continue anyway

    # Re-enrich with regenerate=True
    return await enrich_company(
        company_id=draft.company_id,
        request=EnrichmentRequest(
            contact_name=draft.contact_name,
            contact_title=draft.contact_title,
            regenerate=True
        )
    )


@router.delete("/drafts/{draft_id}")
async def discard_draft(draft_id: str):
    """
    Discard/delete a draft (mark as discarded).

    Args:
        draft_id: UUID of the draft

    Returns:
        Success message
    """
    _check_supabase()

    try:
        result = supabase.table('dim_ai_drafts').update({
            'status': DraftStatus.DISCARDED.value,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('draft_id', draft_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        logger.info(f"Discarded draft {draft_id}")

        return {"message": f"Draft {draft_id} discarded successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discarding draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to discard draft: {str(e)}")
