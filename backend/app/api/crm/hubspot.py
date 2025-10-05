"""
HubSpot CRM API Endpoints

OAuth 2.0 authorization flow, webhook handling, and contact management endpoints.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import logging

from app.models.database import get_db
from app.services.crm.hubspot import HubSpotProvider
from app.services.crm.base import (
    CRMCredentials,
    Contact,
    SyncResult,
    WebhookEvent,
    CRMAuthenticationError,
    CRMWebhookError,
)
from app.core.exceptions import (
    AuthenticationError,
    ValidationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm/hubspot", tags=["HubSpot CRM"])

# Environment configuration
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8001/api/crm/hubspot/callback")

# Default OAuth scopes
DEFAULT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.schemas.contacts.read",
    "oauth"
]


def get_hubspot_provider(
    user_id: Optional[int] = None,
    credentials: Optional[CRMCredentials] = None,
    db: Session = Depends(get_db)
) -> HubSpotProvider:
    """
    Get HubSpot provider instance.
    
    Args:
        user_id: User ID for credentials lookup
        credentials: Existing credentials
        db: Database session
    
    Returns:
        Configured HubSpotProvider
    """
    if not HUBSPOT_CLIENT_ID or not HUBSPOT_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="HubSpot credentials not configured. Set HUBSPOT_CLIENT_ID and HUBSPOT_CLIENT_SECRET."
        )
    
    if not credentials:
        # TODO: Fetch credentials from database using user_id
        credentials = CRMCredentials(
            platform="hubspot",
            user_id=user_id
        )
    
    # TODO: Get Redis client for rate limiting
    redis_client = None
    
    return HubSpotProvider(
        credentials=credentials,
        client_id=HUBSPOT_CLIENT_ID,
        client_secret=HUBSPOT_CLIENT_SECRET,
        redirect_uri=HUBSPOT_REDIRECT_URI,
        redis_client=redis_client
    )


# ============================================================================
# OAUTH 2.0 ENDPOINTS
# ============================================================================

@router.get("/authorize")
async def authorize(
    user_id: Optional[int] = Query(None, description="User ID for credential association"),
    scopes: Optional[str] = Query(None, description="Comma-separated OAuth scopes")
):
    """
    Initiate HubSpot OAuth 2.0 authorization flow.
    
    Redirects user to HubSpot authorization page with PKCE.
    
    Args:
        user_id: Optional user ID to associate credentials
        scopes: Optional custom scopes (defaults to contact management)
    
    Returns:
        Redirect to HubSpot authorization URL
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    # Parse scopes or use defaults
    scope_list = scopes.split(',') if scopes else DEFAULT_SCOPES
    
    # Generate authorization URL with PKCE
    auth_url, code_verifier = provider.generate_authorization_url(scope_list)
    
    # TODO: Store code_verifier in session/cache with state parameter
    # For now, log it (insecure - fix in production)
    logger.info(f"OAuth code_verifier: {code_verifier}")
    
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from HubSpot"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    db: Session = Depends(get_db)
):
    """
    OAuth 2.0 callback endpoint.
    
    Exchanges authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from HubSpot
        state: State parameter for verification
        db: Database session
    
    Returns:
        Success message with token info
    """
    # TODO: Retrieve code_verifier from session/cache using state
    # For now, this is a placeholder - MUST be implemented for production
    code_verifier = "PLACEHOLDER_CODE_VERIFIER"
    
    provider = get_hubspot_provider()
    
    try:
        token_data = await provider.exchange_code_for_token(code, code_verifier)
        
        # TODO: Save encrypted credentials to database
        logger.info(f"HubSpot OAuth successful. Token expires in {token_data['expires_in']}s")
        
        return {
            "status": "success",
            "message": "HubSpot authorization successful",
            "expires_in": token_data['expires_in']
        }
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail="OAuth callback failed")


@router.post("/refresh-token")
async def refresh_token(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Refresh HubSpot access token.
    
    Args:
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        New access token info
    """
    # TODO: Fetch credentials from database
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        new_token = await provider.refresh_access_token()
        
        # TODO: Update credentials in database
        
        return {
            "status": "success",
            "message": "Access token refreshed successfully"
        }
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ============================================================================
# CONTACT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get HubSpot contact by ID.
    
    Args:
        contact_id: HubSpot contact ID
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        Contact details
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        contact = await provider.get_contact(contact_id)
        return contact.dict()
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Get contact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts")
async def create_contact(
    contact: Contact,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Create new contact in HubSpot.
    
    Args:
        contact: Contact data
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        Created contact with HubSpot ID
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        created_contact = await provider.create_contact(contact)
        return created_contact.dict()
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Create contact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: str,
    contact: Contact,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Update HubSpot contact.
    
    Args:
        contact_id: HubSpot contact ID
        contact: Updated contact data
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        Updated contact
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        updated_contact = await provider.update_contact(contact_id, contact)
        return updated_contact.dict()
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Update contact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SYNC ENDPOINTS
# ============================================================================

@router.post("/sync")
async def sync_contacts(
    direction: str = Query("import", description="Sync direction: import, export, bidirectional"),
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Sync contacts between HubSpot and local database.
    
    Args:
        direction: Sync direction (import/export/bidirectional)
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        Sync operation result
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        result = await provider.sync_contacts(direction=direction)
        return result.dict()
        
    except CRMAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@router.post("/webhook")
async def webhook_handler(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle HubSpot webhook events.
    
    Verifies signature and processes contact events.
    
    Args:
        request: FastAPI request object
        db: Database session
    
    Returns:
        Success confirmation
    """
    # Get signature from header
    signature = request.headers.get('X-HubSpot-Signature-v3')
    if not signature:
        raise HTTPException(
            status_code=400,
            detail="Missing X-HubSpot-Signature-v3 header"
        )
    
    # Get raw payload
    payload = await request.body()
    
    # Verify signature
    provider = get_hubspot_provider()
    
    try:
        await provider.verify_webhook_signature(payload, signature)
    except CRMWebhookError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    # Parse webhook event
    webhook_data = await request.json()
    
    # Process each event
    for event_data in webhook_data:
        event = WebhookEvent(
            platform='hubspot',
            event_type=event_data.get('subscriptionType', 'unknown'),
            event_id=event_data.get('eventId', ''),
            contact_id=event_data.get('objectId'),
            payload=event_data,
            signature=signature,
            timestamp=event_data.get('occurredAt', '')
        )
        
        try:
            await provider.handle_webhook(event)
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            # Continue processing other events
    
    return {"status": "success", "message": "Webhook processed"}


# ============================================================================
# RATE LIMIT STATUS
# ============================================================================

@router.get("/rate-limit")
async def get_rate_limit_status(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get current HubSpot rate limit status.
    
    Args:
        user_id: User ID for credential lookup
        db: Database session
    
    Returns:
        Rate limit information
    """
    provider = get_hubspot_provider(user_id=user_id)
    
    try:
        rate_limit_info = await provider.check_rate_limit()
        return rate_limit_info
        
    except Exception as e:
        logger.error(f"Rate limit check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
