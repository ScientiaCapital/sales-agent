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

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import os

from app.services.langgraph.agents import extract_sales_intel
from app.services.crm.close_email import CloseEmailClient
from app.services.outreach.signal_detector import detect_outreach_signal, SIGNAL_STRATEGIES
from app.core.logging import setup_logging
from app.auth.dependencies import get_current_user, require_admin

logger = setup_logging(__name__)

# Initialize Close Email Client (lazy)
_close_email_client: Optional[CloseEmailClient] = None

def get_close_email_client() -> CloseEmailClient:
    """Get or create Close email client."""
    global _close_email_client
    if _close_email_client is None:
        _close_email_client = CloseEmailClient()
    return _close_email_client

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

    # Close CRM link (for "Open in Close" button)
    close_lead_url: Optional[str] = None

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


class StageDraftResponse(BaseModel):
    """Response after staging draft to Close CRM"""
    draft_id: str
    status: str
    message: str
    close_email_id: Optional[str] = None  # Close CRM email activity ID
    close_lead_url: Optional[str] = None  # URL to open the lead in Close


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
    contact_title: Optional[str] = None,
    signal_data: Optional[Dict[str, Any]] = None
) -> int:
    """
    Save AI-generated drafts to Supabase dim_ai_drafts table.

    Now includes signal context - the "why now" for each draft.
    """
    _check_supabase()

    drafts = []
    now = datetime.utcnow().isoformat()

    # Extract signal fields (if provided)
    signal_type = signal_data.get('signal_type') if signal_data else None
    signal_source = signal_data.get('signal_source') if signal_data else None
    signal_reason = signal_data.get('signal_reason') if signal_data else None
    close_lead_status = signal_data.get('close_lead_status') if signal_data else None
    correspondence_summary = signal_data.get('correspondence_summary') if signal_data else None

    # Base draft data (shared across all draft types)
    base_draft = {
        'company_id': company_id,
        'company_name': company_name,
        'status': DraftStatus.PENDING.value,
        'contact_name': contact_name,
        'contact_title': contact_title,
        'personal_hooks': intel_result.get('personal_hooks', []),
        'confidence': intel_result.get('confidence', 0.5),
        'generated_at': now,
        'updated_at': now,
        # Signal fields - the "why now" context
        'signal_type': signal_type,
        'signal_source': signal_source,
        'signal_reason': signal_reason,
        'close_lead_status': close_lead_status,
        'correspondence_summary': correspondence_summary,
    }

    # Email draft
    if intel_result.get('email_subject') and intel_result.get('email_body'):
        drafts.append({
            **base_draft,
            'draft_type': DraftType.EMAIL.value,
            'subject': intel_result['email_subject'],
            'body': intel_result['email_body'],
        })

    # SMS draft
    if intel_result.get('sms_draft'):
        drafts.append({
            **base_draft,
            'draft_type': DraftType.SMS.value,
            'subject': None,
            'body': intel_result['sms_draft'],
        })

    # Voice opener draft
    if intel_result.get('voice_opener'):
        drafts.append({
            **base_draft,
            'draft_type': DraftType.VOICE.value,
            'subject': None,
            'body': intel_result['voice_opener'],
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
    request: EnrichmentRequest,
    current_user: dict = Depends(get_current_user),
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
                message="Drafts already exist. Use regenerate=true to recreate."
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

    # SIGNAL DETECTION: Determine "why now" before generating draft
    # This is the core of signal-based outreach - never draft without context
    close_lead_id = company.get('close_lead_id')
    signal_data = await detect_outreach_signal(
        company_id=company_id,
        close_lead_id=close_lead_id,
        company_data=company,
    )

    logger.info(f"Signal detected for {company_name}: {signal_data.get('signal_type')} ({signal_data.get('signal_source')})")

    # Use signal strategy to customize the draft generation
    strategy = signal_data.get('strategy', {})
    email_tone = strategy.get('email_tone', 'first_touch')
    cta_type = strategy.get('cta', 'Introduction')

    # Run SalesIntelAgent with signal context
    try:
        intel_result = await extract_sales_intel(
            company_name=company_name,
            contact_name=contact_name,
            contact_title=contact_title,
            scraped_content=scraped_content,
            services=services,
            brands=brands,
            location=location,
            # Pass signal context to inform draft generation
            signal_type=signal_data.get('signal_type'),
            signal_reason=signal_data.get('signal_reason'),
            correspondence_summary=signal_data.get('correspondence_summary'),
            email_tone=email_tone,
            cta_type=cta_type,
        )
    except Exception as e:
        logger.error(f"SalesIntelAgent error: {e}")
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")

    # Save drafts to Supabase WITH signal context
    drafts_count = await _save_drafts_to_supabase(
        company_id=company_id,
        company_name=company_name,
        intel_result=intel_result,
        contact_name=contact_name,
        contact_title=contact_title,
        signal_data=signal_data,  # NOW INCLUDES SIGNAL CONTEXT!
    )

    return EnrichmentResponse(
        company_id=company_id,
        company_name=company_name,
        drafts_generated=drafts_count,
        processing_time_ms=intel_result.get('processing_time_ms', 0),
        confidence=intel_result.get('confidence', 0.5),
        message=f"Generated {drafts_count} drafts for {company_name} (Signal: {signal_data.get('signal_type')})"
    )


@router.get("/drafts", response_model=DraftListResponse)
async def list_drafts(
    status: Optional[DraftStatus] = Query(None, description="Filter by status"),
    draft_type: Optional[DraftType] = Query(None, description="Filter by type"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    # Public endpoint for internal dashboard - no auth required
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
    query = query.order('created_at', desc=True)

    # Pagination
    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    try:
        result = query.execute()

        # Fetch close_lead_url for all company_ids in results
        company_ids = list(set(str(row['company_id']) for row in result.data if row.get('company_id')))
        close_urls = {}
        if company_ids:
            try:
                companies_result = supabase.table('dim_companies').select('company_id, close_lead_url').in_('company_id', company_ids).execute()
                close_urls = {str(c['company_id']): c.get('close_lead_url') for c in companies_result.data}
            except Exception as e:
                logger.warning(f"Failed to fetch close_lead_urls: {e}")

        drafts = []
        for row in result.data:
            company_id = str(row['company_id'])
            # Map from SQL schema (id, created_at) to API schema (draft_id, generated_at)
            drafts.append(OutreachDraft(
                draft_id=str(row['id']),  # SQL uses 'id', API uses 'draft_id'
                company_id=company_id,
                company_name=row.get('company_name', 'Unknown'),  # May need JOIN for actual name
                draft_type=DraftType(row['draft_type']),
                status=DraftStatus(row['status']),
                subject=row.get('subject'),
                body=row['body'],
                contact_name=row.get('contact_name'),
                contact_title=row.get('contact_title'),
                personal_hooks=row.get('personal_hooks', []),
                close_lead_url=close_urls.get(company_id),  # "Open in Close" URL
                confidence=row.get('confidence', 0.5),
                generated_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),  # SQL uses created_at
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
async def get_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
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
async def update_draft(
    draft_id: str,
    request: DraftUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
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
async def send_draft(
    draft_id: str,
    request: SendDraftRequest,
    current_user: dict = Depends(get_current_user),
):
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
            message="CLOSE_WRITE_DISABLED - draft marked as sent but not actually sent",
            close_activity_id=None
        )

    # TODO: Implement actual Close CRM integration
    # For now, just mark as sent (Close activity logging is handled by CloseSyncAgent)
    try:
        supabase.table('dim_ai_drafts').update({
            'status': DraftStatus.SENT.value,
            'sent_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }).eq('draft_id', draft_id).execute()

        logger.info(f"Sent draft {draft_id} - Close CRM write pending via CloseSyncAgent")

        return SendDraftResponse(
            draft_id=draft_id,
            status="sent",
            message="Draft sent successfully - Close CRM sync handled by background agent",
            close_activity_id=None  # Will be populated by CloseSyncAgent
        )

    except Exception as e:
        logger.error(f"Error sending draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send draft: {str(e)}")


@router.post("/drafts/{draft_id}/stage", response_model=StageDraftResponse)
async def stage_draft_to_close(
    draft_id: str,
    # Public endpoint for internal dashboard - no auth required
):
    """
    Stage a draft as a REAL email draft in Close CRM.

    This creates an email with status='draft' in Close CRM, which appears
    in the lead's activity timeline ready for Tim to review and send.

    Workflow:
    1. Get draft from Supabase
    2. Get company data to find Close lead ID and contact email
    3. Create email draft in Close CRM via API
    4. Update Supabase draft with close_email_id
    5. Mark draft as 'approved' (staged to Close)

    Args:
        draft_id: UUID of the draft to stage

    Returns:
        StageDraftResponse with Close activity ID and lead URL
    """
    _check_supabase()

    # Get draft from Supabase (using 'id' column, not 'draft_id')
    try:
        result = supabase.table('dim_ai_drafts').select('*').eq('id', draft_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

        draft_data = result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching draft {draft_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch draft: {str(e)}")

    # Only stage email drafts (SMS would need different handling)
    if draft_data.get('draft_type') != DraftType.EMAIL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Only email drafts can be staged to Close CRM. This is a {draft_data.get('draft_type')} draft."
        )

    # Check draft status
    if draft_data.get('status') in [DraftStatus.SENT.value, DraftStatus.DISCARDED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot stage draft with status {draft_data.get('status')}"
        )

    # Get company data to find Close lead ID
    company_id = draft_data.get('company_id')
    company = await _get_company_data(company_id)

    if not company:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

    close_lead_id = company.get('close_lead_id')
    lead_was_created = False

    # Get contact info first - we'll need it either way
    contact_email = None
    contact_name = None
    contact_title = None
    try:
        contacts_result = supabase.table('dim_contacts').select(
            'email, full_name, title'
        ).eq('company_id', company_id).limit(1).execute()

        if contacts_result.data and len(contacts_result.data) > 0:
            contact = contacts_result.data[0]
            contact_email = contact.get('email')
            contact_name = contact.get('full_name')
            contact_title = contact.get('title')
    except Exception as e:
        logger.warning(f"Error fetching contact for company {company_id}: {e}")

    if not contact_email:
        raise HTTPException(
            status_code=400,
            detail=f"No contact email found for {company.get('company_name')}. Enrich the company first."
        )

    # If no Close lead ID, auto-create the lead in Close with ICP data
    if not close_lead_id:
        logger.info(f"No Close lead ID for {company.get('company_name')} - auto-creating lead with ICP data")
        try:
            close_client = get_close_email_client()

            # Extract ICP data from Supabase company record
            icp_tier = company.get('icp_tier')
            qualification_score = company.get('icp_score') or company.get('qualification_score')
            primary_industry = company.get('primary_vertical') or company.get('vertical')
            linkedin_url = company.get('linkedin_url')
            num_employees = company.get('employee_count') or company.get('linkedin_employees')

            # Determine area of focus based on service flags
            area_of_focus = None
            has_resi = company.get('has_residential', False)
            has_comm = company.get('has_commercial', False)
            if has_resi and has_comm:
                area_of_focus = "Both"
            elif has_resi:
                area_of_focus = "Residential"
            elif has_comm:
                area_of_focus = "Commercial"

            # Check if contact is ATL
            is_atl = contact_title and any(
                title in (contact_title or '').lower()
                for title in ['owner', 'ceo', 'president', 'vp', 'director', 'founder', 'partner', 'principal']
            )

            create_result = await close_client.create_lead_with_contact(
                company_name=company.get('company_name'),
                contact_email=contact_email,
                contact_name=contact_name,
                contact_title=contact_title,
                company_url=company.get('domain'),
                company_phone=company.get('phone'),
                # ICP data
                icp_tier=icp_tier,
                qualification_score=qualification_score,
                primary_industry=primary_industry,
                area_of_focus=area_of_focus,
                is_atl=is_atl,
                linkedin_url=linkedin_url,
                num_employees=str(num_employees) if num_employees else None,
            )
            close_lead_id = create_result.get('lead_id')
            lead_was_created = True

            # Update Supabase with the new Close lead ID
            try:
                supabase.table('dim_companies').update({
                    'close_lead_id': close_lead_id,
                    'close_lead_url': create_result.get('close_lead_url'),
                    'updated_at': datetime.utcnow().isoformat()
                }).eq('id', company_id).execute()
                logger.info(f"Updated dim_companies with close_lead_id={close_lead_id}")
            except Exception as e:
                logger.warning(f"Failed to update Supabase with close_lead_id: {e}")

        except Exception as e:
            logger.error(f"Failed to auto-create Close lead: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create lead in Close CRM: {str(e)}"
            )

    # Create draft in Close CRM
    try:
        close_client = get_close_email_client()

        close_result = await close_client.create_draft(
            to_email=contact_email,
            subject=draft_data.get('subject', 'Follow-up'),
            body_text=draft_data.get('body', ''),
            lead_id=close_lead_id,
        )

        close_email_id = close_result.get('id')
        logger.info(f"Created Close CRM draft {close_email_id} for lead {close_lead_id}")

    except Exception as e:
        logger.error(f"Error creating Close CRM draft: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create draft in Close CRM: {str(e)}"
        )

    # Update Supabase draft with Close email ID and mark as approved
    try:
        supabase.table('dim_ai_drafts').update({
            'status': DraftStatus.APPROVED.value,
            'close_email_id': close_email_id,
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', draft_id).execute()

        logger.info(f"Updated draft {draft_id} with close_email_id={close_email_id}")

    except Exception as e:
        logger.warning(f"Failed to update Supabase draft with close_email_id: {e}")
        # Don't fail the request - the Close draft was created successfully

    # Build Close lead URL
    close_lead_url = f"https://app.close.com/lead/{close_lead_id}/" if close_lead_id else None

    # Build message based on whether lead was auto-created
    if lead_was_created:
        message = f"Lead AUTO-CREATED in Close CRM for {company.get('company_name')}. Email draft staged. Open Close to review and send."
    else:
        message = f"Email draft created in Close CRM for {company.get('company_name')}. Open Close to review and send."

    return StageDraftResponse(
        draft_id=draft_id,
        status="staged",
        message=message,
        close_email_id=close_email_id,
        close_lead_url=close_lead_url
    )


@router.post("/drafts/{draft_id}/regenerate", response_model=EnrichmentResponse)
async def regenerate_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
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
async def discard_draft(
    draft_id: str,
    current_user: dict = Depends(require_admin),
):
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
