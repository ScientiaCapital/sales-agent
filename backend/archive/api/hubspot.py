"""
HubSpot API Endpoints

Provides REST endpoints for HubSpot CRM integration:
- Contact sync (Close ↔ HubSpot)
- Webhook handling for form submissions
- Lifecycle stage management
- Marketing analytics

For GTM team marketing automation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
import logging
import hmac
import hashlib

from app.services.crm.hubspot import HubSpotService, get_hubspot_service, HubSpotCompany, HubSpotDeal
from app.services.crm.base import Contact, WebhookEvent, CRMNotFoundError, CRMRateLimitError
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hubspot", tags=["HubSpot"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================


class ContactCreateRequest(BaseModel):
    """Request to create a contact in HubSpot"""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    lifecycle_stage: Optional[str] = Field(None, pattern="^(subscriber|lead|marketingqualifiedlead|salesqualifiedlead|opportunity|customer)$")


class ContactResponse(BaseModel):
    """Contact response"""
    hubspot_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    lifecycle_stage: Optional[str] = None


class SyncRequest(BaseModel):
    """Request for contact sync"""
    direction: str = Field(..., pattern="^(import|export|bidirectional)$")
    filters: Optional[Dict[str, Any]] = None


class SyncResponse(BaseModel):
    """Sync operation response"""
    platform: str
    operation: str
    contacts_processed: int
    contacts_created: int
    contacts_updated: int
    contacts_failed: int
    duration_seconds: float
    errors: List[Dict[str, Any]]


class CloseSyncRequest(BaseModel):
    """Request to sync a Close lead to HubSpot"""
    close_lead_id: str
    close_data: Dict[str, Any]


class HubSpotWebhookPayload(BaseModel):
    """HubSpot webhook payload"""
    objectId: int
    propertyName: Optional[str] = None
    propertyValue: Optional[str] = None
    changeSource: Optional[str] = None
    eventId: int
    subscriptionId: int
    portalId: int
    appId: int
    occurredAt: int
    subscriptionType: str
    attemptNumber: int


class HealthCheckResponse(BaseModel):
    """HubSpot health check response"""
    status: str
    authenticated: bool
    api_version: str = "v3"
    timestamp: datetime


# ============================================================================
# DEPENDENCY
# ============================================================================


async def get_service() -> HubSpotService:
    """Get HubSpot service instance."""
    service = get_hubspot_service()
    return service


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Check HubSpot connection health",
    description="Verify HubSpot API credentials and connectivity"
)
async def health_check(
    service: HubSpotService = Depends(get_service)
) -> HealthCheckResponse:
    """Check if HubSpot API is accessible and authenticated."""
    try:
        authenticated = await service.authenticate()
        return HealthCheckResponse(
            status="healthy" if authenticated else "unhealthy",
            authenticated=authenticated,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"HubSpot health check failed: {e}")
        return HealthCheckResponse(
            status="error",
            authenticated=False,
            timestamp=datetime.utcnow()
        )


@router.post(
    "/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create contact in HubSpot",
    description="Create a new contact in HubSpot for marketing automation"
)
async def create_contact(
    request: ContactCreateRequest,
    service: HubSpotService = Depends(get_service)
) -> ContactResponse:
    """Create a new contact in HubSpot."""
    try:
        contact = Contact(
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            company=request.company,
            title=request.title,
            phone=request.phone
        )

        created = await service.create_contact(contact)

        # Update lifecycle stage if provided
        if request.lifecycle_stage:
            hubspot_id = created.external_ids.get("hubspot")
            if hubspot_id:
                await service.update_lifecycle_stage(hubspot_id, request.lifecycle_stage)

        return ContactResponse(
            hubspot_id=created.external_ids.get("hubspot", ""),
            email=created.email,
            first_name=created.first_name,
            last_name=created.last_name,
            company=created.company,
            title=created.title,
            phone=created.phone,
            lifecycle_stage=request.lifecycle_stage
        )

    except CRMRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after or 10)}
        )
    except Exception as e:
        logger.error(f"Failed to create HubSpot contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/contacts/{email}",
    response_model=ContactResponse,
    summary="Get contact by email",
    description="Retrieve a contact from HubSpot by email address"
)
async def get_contact_by_email(
    email: EmailStr,
    service: HubSpotService = Depends(get_service)
) -> ContactResponse:
    """Get contact by email address."""
    try:
        contact = await service.get_contact_by_email(email)

        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contact not found: {email}"
            )

        return ContactResponse(
            hubspot_id=contact.external_ids.get("hubspot", ""),
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            title=contact.title,
            phone=contact.phone
        )

    except CRMNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact not found: {email}"
        )
    except Exception as e:
        logger.error(f"Failed to get HubSpot contact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/contacts",
    response_model=List[ContactResponse],
    summary="List contacts",
    description="List contacts from HubSpot with pagination"
)
async def list_contacts(
    limit: int = 100,
    after: Optional[str] = None,
    service: HubSpotService = Depends(get_service)
) -> List[ContactResponse]:
    """List contacts from HubSpot."""
    try:
        contacts = await service.list_contacts(limit=limit, after=after)

        return [
            ContactResponse(
                hubspot_id=c.external_ids.get("hubspot", ""),
                email=c.email,
                first_name=c.first_name,
                last_name=c.last_name,
                company=c.company,
                title=c.title,
                phone=c.phone
            )
            for c in contacts
        ]

    except Exception as e:
        logger.error(f"Failed to list HubSpot contacts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch(
    "/contacts/{hubspot_id}/lifecycle-stage",
    status_code=status.HTTP_200_OK,
    summary="Update lifecycle stage",
    description="Update contact's lifecycle stage in HubSpot"
)
async def update_lifecycle_stage(
    hubspot_id: str,
    stage: str,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, str]:
    """Update contact lifecycle stage."""
    valid_stages = ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer"]
    if stage not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    try:
        await service.update_lifecycle_stage(hubspot_id, stage)
        return {"status": "updated", "lifecycle_stage": stage}
    except CRMNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact not found: {hubspot_id}"
        )


@router.patch(
    "/contacts/{hubspot_id}/lead-status",
    status_code=status.HTTP_200_OK,
    summary="Update lead status",
    description="Update contact's lead status in HubSpot"
)
async def update_lead_status(
    hubspot_id: str,
    status_value: str,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, str]:
    """Update contact lead status."""
    valid_statuses = ["new", "open", "in_progress", "open_deal", "unqualified", "attempted_to_contact", "connected", "bad_timing"]
    if status_value not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    try:
        await service.update_lead_status(hubspot_id, status_value)
        return {"status": "updated", "lead_status": status_value}
    except CRMNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact not found: {hubspot_id}"
        )


# ============================================================================
# SYNC ENDPOINTS
# ============================================================================


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync contacts",
    description="Sync contacts between local database and HubSpot"
)
async def sync_contacts(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    service: HubSpotService = Depends(get_service)
) -> SyncResponse:
    """Sync contacts with HubSpot."""
    try:
        result = await service.sync_contacts(
            direction=request.direction,
            filters=request.filters
        )

        return SyncResponse(
            platform=result.platform,
            operation=result.operation,
            contacts_processed=result.contacts_processed,
            contacts_created=result.contacts_created,
            contacts_updated=result.contacts_updated,
            contacts_failed=result.contacts_failed,
            duration_seconds=result.duration_seconds or 0.0,
            errors=result.errors
        )

    except Exception as e:
        logger.error(f"HubSpot sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/sync/from-close",
    status_code=status.HTTP_200_OK,
    summary="Sync Close lead to HubSpot",
    description="Push a Close CRM lead to HubSpot for marketing automation"
)
async def sync_from_close(
    request: CloseSyncRequest,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, Any]:
    """Sync a Close lead to HubSpot."""
    try:
        hubspot_id = await service.sync_from_close(
            close_lead_id=request.close_lead_id,
            close_data=request.close_data
        )

        return {
            "status": "synced",
            "close_lead_id": request.close_lead_id,
            "hubspot_contact_id": hubspot_id
        }

    except Exception as e:
        logger.error(f"Close→HubSpot sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================


def verify_hubspot_signature(request: Request, payload: bytes) -> bool:
    """
    Verify HubSpot webhook signature.

    HubSpot signs webhooks with HMAC SHA-256.
    """
    signature = request.headers.get("X-HubSpot-Signature-v3")
    if not signature:
        return False

    # Get client secret from settings
    client_secret = settings.HUBSPOT_CLIENT_SECRET
    if not client_secret:
        logger.warning("HUBSPOT_CLIENT_SECRET not configured, skipping signature verification")
        return True  # Allow in development

    # Calculate expected signature
    timestamp = request.headers.get("X-HubSpot-Request-Timestamp", "")
    string_to_sign = f"{request.method}{str(request.url)}{payload.decode()}{timestamp}"

    expected = hmac.new(
        client_secret.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


@router.post(
    "/webhooks",
    status_code=status.HTTP_200_OK,
    summary="Handle HubSpot webhooks",
    description="Receive and process webhooks from HubSpot (form submissions, contact updates)"
)
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, str]:
    """
    Handle incoming HubSpot webhooks.

    Webhook types:
    - contact.creation
    - contact.propertyChange
    - contact.deletion
    - form.submit
    """
    try:
        # Read raw payload for signature verification
        payload = await request.body()

        # Verify signature (optional in development)
        if not verify_hubspot_signature(request, payload):
            logger.warning("Invalid HubSpot webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        # Parse payload
        import json
        events = json.loads(payload)

        # Process each event in background
        for event_data in events if isinstance(events, list) else [events]:
            event = WebhookEvent(
                platform="hubspot",
                event_type=event_data.get("subscriptionType", "unknown"),
                event_id=str(event_data.get("eventId", "")),
                contact_id=str(event_data.get("objectId", "")),
                payload=event_data,
                timestamp=datetime.utcnow()
            )

            background_tasks.add_task(service.handle_webhook, event)

        return {"status": "received", "events_queued": len(events) if isinstance(events, list) else 1}

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# COMPANY ENDPOINTS
# ============================================================================


@router.post(
    "/companies",
    status_code=status.HTTP_201_CREATED,
    summary="Create company in HubSpot",
    description="Create a new company record in HubSpot"
)
async def create_company(
    company: HubSpotCompany,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, Any]:
    """Create a company in HubSpot."""
    try:
        created = await service.create_company(company)
        return {
            "hubspot_id": created.id,
            "name": created.name,
            "domain": created.domain
        }
    except Exception as e:
        logger.error(f"Failed to create HubSpot company: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# DEAL ENDPOINTS
# ============================================================================


@router.post(
    "/deals",
    status_code=status.HTTP_201_CREATED,
    summary="Create deal in HubSpot",
    description="Create a new deal in HubSpot pipeline"
)
async def create_deal(
    deal: HubSpotDeal,
    service: HubSpotService = Depends(get_service)
) -> Dict[str, Any]:
    """Create a deal in HubSpot."""
    try:
        created = await service.create_deal(deal)
        return {
            "hubspot_id": created.id,
            "dealname": created.dealname,
            "amount": created.amount,
            "dealstage": created.dealstage
        }
    except Exception as e:
        logger.error(f"Failed to create HubSpot deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
