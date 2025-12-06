"""
Close CRM Outreach API

FastAPI endpoints for Email, SMS, and voice call outreach via Close CRM.
Full GTM automation using Close's connected accounts (tim@coperniq.io).

API Docs: https://developer.close.com/resources/activities/
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr
import logging

from app.services.crm.close_sms import CloseSMSClient
from app.services.crm.close_calling import CloseCallingClient
from app.services.crm.close_email import CloseEmailClient
from app.services.crm.close import CloseProvider
from app.core.config import settings
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/close", tags=["close-outreach"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SMSRequest(BaseModel):
    """Request to send SMS via Close CRM."""
    phone: str = Field(..., description="Phone number (E.164 format recommended: +1234567890)")
    message: str = Field(..., description="SMS message body", max_length=1600)
    lead_id: Optional[str] = Field(None, description="Close lead ID")
    contact_id: Optional[str] = Field(None, description="Close contact ID")
    user_id: Optional[str] = Field(None, description="Close user ID (defaults to API key owner)")


class SMSResponse(BaseModel):
    """Response from SMS send operation."""
    success: bool
    activity_id: Optional[str] = None
    status: Optional[str] = None
    phone: str
    message: str
    lead_id: Optional[str] = None
    created_at: Optional[str] = None
    error: Optional[str] = None


class CallTriggerRequest(BaseModel):
    """Request to trigger voice call via Close CRM."""
    phone: str = Field(..., description="Phone number to call (E.164 format)")
    lead_id: str = Field(..., description="Close lead ID (required)")
    script_notes: Optional[str] = Field(None, description="Call script or talking points")
    contact_id: Optional[str] = Field(None, description="Close contact ID")
    user_id: Optional[str] = Field(None, description="Close user ID making the call")


class CallResultRequest(BaseModel):
    """Request to log call result."""
    call_id: str = Field(..., description="Close call activity ID")
    result: str = Field(..., description="Call outcome: answered, voicemail, no_answer, busy, failed")
    notes: Optional[str] = Field(None, description="Call notes or summary")
    duration_seconds: Optional[int] = Field(None, description="Call duration in seconds")
    recording_url: Optional[str] = Field(None, description="URL to call recording")


class CallResponse(BaseModel):
    """Response from call operation."""
    success: bool
    activity_id: Optional[str] = None
    status: Optional[str] = None
    phone: str
    lead_id: str
    created_at: Optional[str] = None
    error: Optional[str] = None


class LeadSyncRequest(BaseModel):
    """Request to sync prospect to Close as lead."""
    email: EmailStr = Field(..., description="Prospect email address")
    company: str = Field(..., description="Company name")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    qualification_score: Optional[int] = Field(None, ge=0, le=100)
    is_atl: bool = Field(False, description="Is above-the-line decision maker")
    tier: Optional[str] = Field(None, description="Qualification tier: hot/warm/cold/unqualified")


class LeadSyncResponse(BaseModel):
    """Response from lead sync operation."""
    success: bool
    lead_id: Optional[str] = None
    company: str
    status: str
    contacts_created: int = 0
    error: Optional[str] = None


class ActivityHistoryResponse(BaseModel):
    """Response containing activity history."""
    lead_id: str
    activity_type: str  # "sms" or "call" or "email"
    count: int
    activities: List[Dict[str, Any]]


# Email Models
class EmailRequest(BaseModel):
    """Request to send email via Close CRM."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line", max_length=500)
    body_text: str = Field(..., description="Plain text email body")
    lead_id: str = Field(..., description="Close lead ID (required)")
    body_html: Optional[str] = Field(None, description="HTML email body")
    contact_id: Optional[str] = Field(None, description="Close contact ID")
    user_id: Optional[str] = Field(None, description="Close user ID")
    template_id: Optional[str] = Field(None, description="Close email template ID")


class EmailDraftRequest(BaseModel):
    """Request to create email draft for review."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body_text: str = Field(..., description="Plain text email body")
    lead_id: str = Field(..., description="Close lead ID")
    body_html: Optional[str] = Field(None, description="HTML email body")
    contact_id: Optional[str] = Field(None, description="Close contact ID")


class EmailScheduleRequest(BaseModel):
    """Request to schedule email for future delivery."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body_text: str = Field(..., description="Plain text email body")
    lead_id: str = Field(..., description="Close lead ID")
    scheduled_time: str = Field(..., description="ISO format datetime (UTC)")
    body_html: Optional[str] = Field(None, description="HTML email body")
    contact_id: Optional[str] = Field(None, description="Close contact ID")


class EmailResponse(BaseModel):
    """Response from email operation."""
    success: bool
    activity_id: Optional[str] = None
    status: Optional[str] = None
    to: Optional[str] = None
    subject: Optional[str] = None
    lead_id: Optional[str] = None
    created_at: Optional[str] = None
    scheduled_for: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_sms_client() -> CloseSMSClient:
    """Get Close SMS client instance."""
    try:
        return CloseSMSClient(api_key=settings.CLOSE_API_KEY)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Close SMS client initialization failed: {str(e)}"
        )


def get_calling_client() -> CloseCallingClient:
    """Get Close calling client instance."""
    try:
        return CloseCallingClient(api_key=settings.CLOSE_API_KEY)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Close calling client initialization failed: {str(e)}"
        )


def get_close_provider() -> CloseProvider:
    """Get Close CRM provider instance."""
    try:
        return CloseProvider(api_key=settings.CLOSE_API_KEY)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Close CRM provider initialization failed: {str(e)}"
        )


def get_email_client() -> CloseEmailClient:
    """Get Close email client instance."""
    try:
        return CloseEmailClient(api_key=settings.CLOSE_API_KEY)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Close email client initialization failed: {str(e)}"
        )


# ============================================================================
# EMAIL ENDPOINTS
# ============================================================================

@router.post("/email", response_model=EmailResponse)
async def send_email(
    request: EmailRequest,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Send email via Close CRM using connected account (tim@coperniq.io).

    Creates an email activity in Close CRM and sends immediately.
    Automatically logs the communication in the lead's timeline.

    **Example:**
    ```json
    {
        "to_email": "owner@hvacpros.com",
        "subject": "Quick question about your HVAC business",
        "body_text": "Hi John, I noticed you work with Carrier...",
        "lead_id": "lead_xxx123"
    }
    ```

    **Returns:**
    - `success`: Whether the email was sent
    - `activity_id`: Close CRM activity ID for tracking
    - `status`: Send status (outbox, sent, etc.)
    """
    try:
        result = await email_client.send_email(
            to_email=request.to_email,
            subject=request.subject,
            body_text=request.body_text,
            lead_id=request.lead_id,
            body_html=request.body_html,
            contact_id=request.contact_id,
            user_id=request.user_id,
            template_id=request.template_id,
        )

        return EmailResponse(
            success=True,
            activity_id=result.get("id"),
            status=result.get("status"),
            to=request.to_email,
            subject=request.subject,
            lead_id=request.lead_id,
            created_at=result.get("created_at"),
        )

    except Exception as e:
        logger.error(f"Failed to send email via Close: {e}")
        return EmailResponse(
            success=False,
            to=request.to_email,
            subject=request.subject,
            lead_id=request.lead_id,
            error=str(e),
        )


@router.post("/email/draft", response_model=EmailResponse)
async def create_email_draft(
    request: EmailDraftRequest,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Create email draft in Close CRM for review before sending.

    Drafts appear in Close UI for manual review by Tim.
    Use PUT /email/{id}/send to send the draft.

    **Returns:**
    - `activity_id`: Draft ID for later sending
    - `status`: "draft"
    """
    try:
        result = await email_client.create_draft(
            to_email=request.to_email,
            subject=request.subject,
            body_text=request.body_text,
            lead_id=request.lead_id,
            body_html=request.body_html,
            contact_id=request.contact_id,
        )

        return EmailResponse(
            success=True,
            activity_id=result.get("id"),
            status="draft",
            to=request.to_email,
            subject=request.subject,
            lead_id=request.lead_id,
            created_at=result.get("created_at"),
        )

    except Exception as e:
        logger.error(f"Failed to create email draft: {e}")
        return EmailResponse(
            success=False,
            to=request.to_email,
            subject=request.subject,
            error=str(e),
        )


@router.put("/email/{email_id}/send", response_model=EmailResponse)
async def send_draft_email(
    email_id: str,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Send a previously created draft email.

    **Path Parameters:**
    - `email_id`: Close email activity ID from create_draft

    **Returns:**
    - `status`: Updated status (outbox/sent)
    """
    try:
        result = await email_client.send_draft(email_id)

        return EmailResponse(
            success=True,
            activity_id=result.get("id"),
            status=result.get("status"),
        )

    except Exception as e:
        logger.error(f"Failed to send draft email {email_id}: {e}")
        return EmailResponse(
            success=False,
            activity_id=email_id,
            error=str(e),
        )


@router.post("/email/schedule", response_model=EmailResponse)
async def schedule_email(
    request: EmailScheduleRequest,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Schedule email for future delivery.

    **Example:**
    ```json
    {
        "to_email": "owner@hvacpros.com",
        "subject": "Following up on solar installation",
        "body_text": "Hi John...",
        "lead_id": "lead_xxx123",
        "scheduled_time": "2024-12-09T09:00:00Z"
    }
    ```

    **Returns:**
    - `scheduled_for`: When the email will be sent
    - `status`: "scheduled"
    """
    try:
        from datetime import datetime
        scheduled_dt = datetime.fromisoformat(request.scheduled_time.replace('Z', '+00:00'))

        result = await email_client.schedule_email(
            to_email=request.to_email,
            subject=request.subject,
            body_text=request.body_text,
            lead_id=request.lead_id,
            scheduled_time=scheduled_dt,
            body_html=request.body_html,
            contact_id=request.contact_id,
        )

        return EmailResponse(
            success=True,
            activity_id=result.get("id"),
            status="scheduled",
            to=request.to_email,
            subject=request.subject,
            lead_id=request.lead_id,
            scheduled_for=result.get("scheduled_for"),
            created_at=result.get("created_at"),
        )

    except Exception as e:
        logger.error(f"Failed to schedule email: {e}")
        return EmailResponse(
            success=False,
            to=request.to_email,
            subject=request.subject,
            error=str(e),
        )


@router.get("/email/history/{lead_id}", response_model=ActivityHistoryResponse)
async def get_email_history(
    lead_id: str,
    limit: int = 50,
    offset: int = 0,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Get email activity history for a lead.

    Retrieves all email activities (inbound and outbound) from Close CRM.

    **Query Parameters:**
    - `limit`: Max number of emails to return (default: 50)
    - `offset`: Pagination offset (default: 0)

    **Returns:**
    - List of email activities with subject, body, status, timestamps
    """
    try:
        emails = await email_client.get_email_history(
            lead_id=lead_id,
            limit=limit,
            offset=offset,
        )

        return ActivityHistoryResponse(
            lead_id=lead_id,
            activity_type="email",
            count=len(emails),
            activities=emails,
        )

    except Exception as e:
        logger.error(f"Failed to get email history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email history: {str(e)}"
        )


@router.delete("/email/{email_id}")
async def delete_email(
    email_id: str,
    email_client: CloseEmailClient = Depends(get_email_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete an email activity (draft or scheduled).

    Cannot delete already-sent emails.
    """
    try:
        await email_client.delete_email(email_id)
        return {"success": True, "deleted_id": email_id}

    except Exception as e:
        logger.error(f"Failed to delete email {email_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete email: {str(e)}"
        )


# ============================================================================
# SMS ENDPOINTS
# ============================================================================

@router.post("/sms", response_model=SMSResponse)
async def send_sms(
    request: SMSRequest,
    sms_client: CloseSMSClient = Depends(get_sms_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Send SMS via Close CRM.

    Creates an SMS activity in Close CRM and sends the message.
    Automatically logs the communication in the lead's timeline.

    **Example:**
    ```json
    {
        "phone": "+12125551234",
        "message": "Hi John, following up on our conversation about solar...",
        "lead_id": "lead_xxx123"
    }
    ```

    **Returns:**
    - `success`: Whether the SMS was sent successfully
    - `activity_id`: Close CRM activity ID for tracking
    - `status`: Send status (sent, failed, etc.)
    """
    try:
        result = await sms_client.send_sms(
            phone=request.phone,
            message=request.message,
            lead_id=request.lead_id,
            contact_id=request.contact_id,
            user_id=request.user_id,
        )

        return SMSResponse(
            success=True,
            activity_id=result.get("id"),
            status=result.get("status"),
            phone=request.phone,
            message=request.message,
            lead_id=request.lead_id,
            created_at=result.get("created_at"),
        )

    except Exception as e:
        logger.error(f"Failed to send SMS via Close: {e}")
        return SMSResponse(
            success=False,
            phone=request.phone,
            message=request.message,
            lead_id=request.lead_id,
            error=str(e),
        )


@router.get("/sms/history/{lead_id}", response_model=ActivityHistoryResponse)
async def get_sms_history(
    lead_id: str,
    limit: int = 50,
    offset: int = 0,
    sms_client: CloseSMSClient = Depends(get_sms_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Get SMS activity history for a lead.

    Retrieves all SMS messages (inbound and outbound) from Close CRM
    for a specific lead, sorted by date descending.

    **Query Parameters:**
    - `limit`: Max number of activities to return (default: 50)
    - `offset`: Pagination offset (default: 0)

    **Returns:**
    - List of SMS activities with text, phone, status, and timestamps
    """
    try:
        activities = await sms_client.get_sms_history(
            lead_id=lead_id,
            limit=limit,
            offset=offset,
        )

        return ActivityHistoryResponse(
            lead_id=lead_id,
            activity_type="sms",
            count=len(activities),
            activities=activities,
        )

    except Exception as e:
        logger.error(f"Failed to get SMS history from Close: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve SMS history: {str(e)}"
        )


# ============================================================================
# VOICE CALL ENDPOINTS
# ============================================================================

@router.post("/call", response_model=CallResponse)
async def trigger_call(
    request: CallTriggerRequest,
    calling_client: CloseCallingClient = Depends(get_calling_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger voice call via Close CRM.

    Creates a call activity in Close CRM that can be used to:
    1. Log that a call is being initiated
    2. Provide script notes to the sales rep
    3. Track the call in CRM timeline

    **Example:**
    ```json
    {
        "phone": "+12125551234",
        "lead_id": "lead_xxx123",
        "script_notes": "Discuss pricing for 50kW commercial system. Mention Q4 incentives."
    }
    ```

    **Returns:**
    - `success`: Whether the call was scheduled/triggered
    - `activity_id`: Close CRM activity ID for logging results
    """
    try:
        result = await calling_client.trigger_call(
            phone=request.phone,
            lead_id=request.lead_id,
            script_notes=request.script_notes,
            user_id=request.user_id,
            contact_id=request.contact_id,
        )

        return CallResponse(
            success=True,
            activity_id=result.get("id"),
            status=result.get("status"),
            phone=request.phone,
            lead_id=request.lead_id,
            created_at=result.get("created_at"),
        )

    except Exception as e:
        logger.error(f"Failed to trigger call via Close: {e}")
        return CallResponse(
            success=False,
            phone=request.phone,
            lead_id=request.lead_id,
            error=str(e),
        )


@router.post("/call/result")
async def log_call_result(
    request: CallResultRequest,
    calling_client: CloseCallingClient = Depends(get_calling_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Log call result in Close CRM.

    Updates a call activity with the outcome, notes, and duration.
    Used to track call dispositions and follow-up actions.

    **Valid Results:**
    - `answered`: Call was answered
    - `voicemail`: Left voicemail
    - `no_answer`: No answer
    - `busy`: Busy signal
    - `failed`: Call failed to connect

    **Example:**
    ```json
    {
        "call_id": "acti_xxx123",
        "result": "answered",
        "notes": "Discussed pricing. Interested in 50kW system. Follow up next week.",
        "duration_seconds": 180
    }
    ```
    """
    try:
        result = await calling_client.log_call_result(
            call_id=request.call_id,
            result=request.result,
            notes=request.notes,
            duration_seconds=request.duration_seconds,
            recording_url=request.recording_url,
        )

        return {
            "success": True,
            "activity_id": result.get("id"),
            "status": result.get("status"),
            "duration": result.get("duration"),
            "updated_at": result.get("updated_at"),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to log call result in Close: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log call result: {str(e)}"
        )


@router.get("/call/history/{lead_id}", response_model=ActivityHistoryResponse)
async def get_call_history(
    lead_id: str,
    limit: int = 50,
    offset: int = 0,
    calling_client: CloseCallingClient = Depends(get_calling_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Get call activity history for a lead.

    Retrieves all call activities (inbound and outbound) from Close CRM
    for a specific lead, sorted by date descending.

    **Query Parameters:**
    - `limit`: Max number of activities to return (default: 50)
    - `offset`: Pagination offset (default: 0)

    **Returns:**
    - List of call activities with status, duration, notes, and timestamps
    """
    try:
        activities = await calling_client.get_call_history(
            lead_id=lead_id,
            limit=limit,
            offset=offset,
        )

        return ActivityHistoryResponse(
            lead_id=lead_id,
            activity_type="call",
            count=len(activities),
            activities=activities,
        )

    except Exception as e:
        logger.error(f"Failed to get call history from Close: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve call history: {str(e)}"
        )


# ============================================================================
# LEAD SYNC ENDPOINT
# ============================================================================

@router.post("/sync-lead", response_model=LeadSyncResponse)
async def sync_lead(
    request: LeadSyncRequest,
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    Sync prospect to Close CRM as a lead.

    Creates or updates a lead in Close CRM with enrichment data.
    Automatically sets lead status based on qualification tier and ATL status.

    **Example:**
    ```json
    {
        "email": "john.doe@solarpros.com",
        "company": "Solar Pros LLC",
        "first_name": "John",
        "last_name": "Doe",
        "title": "VP of Operations",
        "qualification_score": 85,
        "is_atl": true,
        "tier": "hot"
    }
    ```

    **Lead Prioritization:**
    - Hot ATL (score >= 70): High priority
    - Validated ATL (score < 70): Medium priority
    - BTL: Standard follow-up

    **Returns:**
    - `success`: Whether the lead was synced
    - `lead_id`: Close CRM lead ID
    - `status`: Creation status
    """
    try:
        # Build lead data dict for CloseProvider
        lead_data = {
            "email": request.email,
            "name": request.company,
            "company": request.company,
            "first_name": request.first_name,
            "last_name": request.last_name,
            "title": request.title,
            "phone": request.phone,
            "linkedin_url": request.linkedin_url,
            "qualification_score": request.qualification_score or 0,
            "is_atl": request.is_atl,
            "tier": request.tier or "unknown",
        }

        # Create lead via CloseProvider
        result = await close_provider.create_lead(lead_data)

        # Check if write operations are disabled
        if result.get("status") == "disabled":
            return LeadSyncResponse(
                success=False,
                company=request.company,
                status="disabled",
                error="Close CRM write operations are disabled (CLOSE_WRITE_DISABLED=True)",
            )

        return LeadSyncResponse(
            success=True,
            lead_id=result.get("id"),
            company=request.company,
            status=result.get("status", "created"),
            contacts_created=result.get("contacts_created", 1),
        )

    except Exception as e:
        logger.error(f"Failed to sync lead to Close: {e}")
        return LeadSyncResponse(
            success=False,
            company=request.company,
            status="error",
            error=str(e),
        )


@router.get("/lead/{lead_id}/activity")
async def get_lead_activity(
    lead_id: str,
    activity_type: Optional[str] = None,
    limit: int = 100,
    calling_client: CloseCallingClient = Depends(get_calling_client),
    sms_client: CloseSMSClient = Depends(get_sms_client),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all activity history for a lead.

    Retrieves SMS and/or call activities for a lead from Close CRM.

    **Query Parameters:**
    - `activity_type`: Filter by type ("sms", "call", or omit for both)
    - `limit`: Max activities per type (default: 100)

    **Returns:**
    - Combined activity history with SMS and call activities
    """
    try:
        result = {
            "lead_id": lead_id,
            "sms_activities": [],
            "call_activities": [],
            "total_count": 0,
        }

        # Get SMS activities if requested
        if activity_type in [None, "sms"]:
            sms_activities = await sms_client.get_sms_history(
                lead_id=lead_id,
                limit=limit,
            )
            result["sms_activities"] = sms_activities
            result["total_count"] += len(sms_activities)

        # Get call activities if requested
        if activity_type in [None, "call"]:
            call_activities = await calling_client.get_call_history(
                lead_id=lead_id,
                limit=limit,
            )
            result["call_activities"] = call_activities
            result["total_count"] += len(call_activities)

        return result

    except Exception as e:
        logger.error(f"Failed to get lead activity from Close: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve lead activity: {str(e)}"
        )
