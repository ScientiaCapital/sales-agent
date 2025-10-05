"""
Personalized Outreach Campaign API Endpoints

Provides REST API for creating, managing, and analyzing multi-channel outreach campaigns
with A/B testing and variant optimization.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.campaign import Campaign, CampaignMessage, CampaignStatus, CampaignChannel, MessageStatus
from app.services.outreach import CampaignService
from app.core.logging import setup_logging
from app.core.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    ResourceConflictError
)

logger = setup_logging(__name__)

router = APIRouter(prefix="/campaigns", tags=["campaigns", "outreach"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class CampaignCreateRequest(BaseModel):
    """Request schema for campaign creation."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    channel: str = Field(..., description="Channel: email, linkedin, or sms")
    min_qualification_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum lead score (0-100)")
    target_industries: Optional[List[str]] = Field(None, description="Target industries")
    target_company_sizes: Optional[List[str]] = Field(None, description="Target company sizes")
    message_template: Optional[str] = Field(None, description="Message template with {{variable}} placeholders")
    custom_context: Optional[str] = Field(None, description="Additional context for message generation")
    
    @validator('channel')
    def validate_channel(cls, v):
        """Validate channel value."""
        if v.lower() not in ['email', 'linkedin', 'sms']:
            raise ValueError("Channel must be email, linkedin, or sms")
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Enterprise SaaS Q1 Outreach",
                "channel": "email",
                "min_qualification_score": 70,
                "target_industries": ["Technology", "SaaS", "Enterprise Software"],
                "target_company_sizes": ["50-200", "200-500"],
                "custom_context": "Focus on ROI and enterprise security features"
            }
        }


class MessageGenerationRequest(BaseModel):
    """Request schema for message generation."""
    
    custom_context: Optional[str] = Field(None, description="Override campaign context for this generation")
    force_regenerate: bool = Field(False, description="Regenerate messages even if they exist")
    
    class Config:
        json_schema_extra = {
            "example": {
                "custom_context": "Emphasize Q1 pricing promotion",
                "force_regenerate": False
            }
        }


class MessageStatusUpdate(BaseModel):
    """Request schema for message status update."""
    
    status: str = Field(..., description="Status: sent, delivered, opened, clicked, replied, bounced, failed")
    variant_number: Optional[int] = Field(None, ge=0, le=2, description="Variant number (0-2) if tracking specific variant")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate status value."""
        valid_statuses = ['sent', 'delivered', 'opened', 'clicked', 'replied', 'bounced', 'failed']
        if v.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "opened",
                "variant_number": 0
            }
        }


class CampaignResponse(BaseModel):
    """Response schema for campaign data."""
    
    id: int
    name: str
    status: str
    channel: str
    min_qualification_score: Optional[float]
    target_industries: Optional[List[str]]
    target_company_sizes: Optional[List[str]]
    total_messages: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_replied: int
    total_cost: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Response schema for campaign message."""
    
    id: int
    campaign_id: int
    lead_id: int
    variants: List[Dict[str, str]]
    selected_variant: int
    status: str
    generation_cost: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class AnalyticsResponse(BaseModel):
    """Response schema for campaign analytics."""
    
    campaign: CampaignResponse
    metrics: Dict[str, float]
    cost: Dict[str, float]
    ab_testing: Dict[str, Any]
    top_performing_messages: List[Dict[str, Any]]


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_campaign_service(db: Session = Depends(get_db)) -> CampaignService:
    """
    Dependency injection for campaign service.
    
    Returns:
        Initialized CampaignService instance
    
    Raises:
        HTTPException: If service initialization fails
    """
    try:
        return CampaignService(db)
    except Exception as e:
        logger.error(f"Failed to initialize campaign service: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Campaign service initialization failed: {str(e)}"
        )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post(
    "/create",
    response_model=CampaignResponse,
    status_code=201,
    summary="Create new campaign",
    description="Create a new outreach campaign with targeting criteria"
)
async def create_campaign(
    request: CampaignCreateRequest,
    service: CampaignService = Depends(get_campaign_service)
) -> CampaignResponse:
    """
    Create a new outreach campaign.
    
    Args:
        request: Campaign creation parameters
        service: Campaign service instance (injected)
    
    Returns:
        Created campaign data
    
    Raises:
        HTTPException: If campaign creation fails
    """
    try:
        campaign = service.create_campaign(
            name=request.name,
            channel=request.channel,
            min_qualification_score=request.min_qualification_score,
            target_industries=request.target_industries,
            target_company_sizes=request.target_company_sizes,
            message_template=request.message_template,
            custom_context=request.custom_context
        )
        
        logger.info(f"Campaign created successfully: {campaign.name} (ID: {campaign.id})")
        
        return CampaignResponse.model_validate(campaign)
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during campaign creation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Campaign creation failed")


@router.post(
    "/{campaign_id}/generate-messages",
    summary="Generate campaign messages",
    description="Generate personalized messages with 3 variants for all qualified leads"
)
async def generate_messages(
    campaign_id: int,
    request: MessageGenerationRequest = MessageGenerationRequest(),
    service: CampaignService = Depends(get_campaign_service)
) -> Dict[str, Any]:
    """
    Generate personalized messages for campaign leads.
    
    Args:
        campaign_id: Campaign ID
        request: Message generation parameters
        service: Campaign service instance (injected)
    
    Returns:
        Generation statistics
    
    Raises:
        HTTPException: If generation fails
    """
    try:
        stats = service.generate_messages(
            campaign_id=campaign_id,
            custom_context=request.custom_context,
            force_regenerate=request.force_regenerate
        )
        
        logger.info(f"Messages generated for campaign {campaign_id}: {stats['messages_generated']} messages")
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "statistics": stats
        }
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except ResourceConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during message generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Message generation failed")


@router.get(
    "/{campaign_id}/messages",
    response_model=List[MessageResponse],
    summary="List campaign messages",
    description="Get all messages for a campaign with optional status filter"
)
async def list_messages(
    campaign_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    service: CampaignService = Depends(get_campaign_service)
) -> List[MessageResponse]:
    """
    List messages for a campaign.
    
    Args:
        campaign_id: Campaign ID
        status: Optional status filter
        skip: Pagination offset
        limit: Pagination limit
        service: Campaign service instance (injected)
    
    Returns:
        List of campaign messages
    
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        messages = service.get_campaign_messages(
            campaign_id=campaign_id,
            status=status,
            skip=skip,
            limit=limit
        )
        
        return [MessageResponse.model_validate(msg) for msg in messages]
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error listing messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.get(
    "/{campaign_id}/analytics",
    response_model=AnalyticsResponse,
    summary="Get campaign analytics",
    description="Comprehensive analytics with A/B testing results and performance metrics"
)
async def get_analytics(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service)
) -> AnalyticsResponse:
    """
    Get comprehensive campaign analytics.
    
    Args:
        campaign_id: Campaign ID
        service: Campaign service instance (injected)
    
    Returns:
        Campaign analytics with A/B testing results
    
    Raises:
        HTTPException: If analytics retrieval fails
    """
    try:
        analytics = service.get_campaign_analytics(campaign_id)
        
        return AnalyticsResponse(**analytics)
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analytics retrieval failed")


@router.post(
    "/{campaign_id}/send",
    summary="Activate campaign",
    description="Mark campaign as active and ready to send messages"
)
async def activate_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service)
) -> Dict[str, Any]:
    """
    Activate a campaign for sending.
    
    Args:
        campaign_id: Campaign ID
        service: Campaign service instance (injected)
    
    Returns:
        Updated campaign data
    
    Raises:
        HTTPException: If activation fails
    """
    try:
        campaign = service.activate_campaign(campaign_id)
        
        logger.info(f"Campaign {campaign_id} activated: {campaign.name}")
        
        return {
            "success": True,
            "campaign": CampaignResponse.model_validate(campaign)
        }
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error activating campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Campaign activation failed")


@router.get(
    "/messages/{message_id}/variants",
    summary="View message variants",
    description="Get all 3 variants for A/B testing comparison"
)
async def get_message_variants(
    message_id: int,
    service: CampaignService = Depends(get_campaign_service)
) -> Dict[str, Any]:
    """
    Get all variants for a message.
    
    Args:
        message_id: Message ID
        service: Campaign service instance (injected)
    
    Returns:
        All 3 message variants with analytics
    
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        variants = service.get_message_variants(message_id)
        
        return {
            "message_id": message_id,
            "variants": variants
        }
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving variants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Variant retrieval failed")


@router.put(
    "/messages/{message_id}/status",
    summary="Update message status",
    description="Update message delivery status and track variant performance"
)
async def update_message_status(
    message_id: int,
    request: MessageStatusUpdate,
    service: CampaignService = Depends(get_campaign_service)
) -> Dict[str, Any]:
    """
    Update message status and variant analytics.
    
    Args:
        message_id: Message ID
        request: Status update data
        service: Campaign service instance (injected)
    
    Returns:
        Updated message data
    
    Raises:
        HTTPException: If update fails
    """
    try:
        message = service.update_message_status(
            message_id=message_id,
            status=request.status,
            variant_number=request.variant_number
        )
        
        logger.info(f"Message {message_id} status updated to {request.status}")
        
        return {
            "success": True,
            "message": MessageResponse.model_validate(message)
        }
    
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error updating message status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Status update failed")


@router.get(
    "",
    response_model=List[CampaignResponse],
    summary="List all campaigns",
    description="Get all campaigns with optional status filter"
)
async def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    service: CampaignService = Depends(get_campaign_service)
) -> List[CampaignResponse]:
    """
    List all campaigns.
    
    Args:
        status: Optional status filter
        skip: Pagination offset
        limit: Pagination limit
        service: Campaign service instance (injected)
    
    Returns:
        List of campaigns
    
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        campaigns = service.list_campaigns(
            status=status,
            skip=skip,
            limit=limit
        )
        
        return [CampaignResponse.model_validate(c) for c in campaigns]
    
    except Exception as e:
        logger.error(f"Unexpected error listing campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve campaigns")
