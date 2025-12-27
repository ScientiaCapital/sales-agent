"""
Close CRM Opportunities & Pipelines API

FastAPI endpoints for managing opportunities and pipelines in Close CRM.
Provides CRUD operations for deal tracking and pipeline visibility.

API Docs: https://developer.close.com/resources/opportunities/
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.services.crm.close import CloseProvider
from app.services.crm.base import (
    CRMNotFoundError,
    CRMValidationError,
    CRMRateLimitError,
    CRMNetworkError,
)
from app.core.config import settings
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/close", tags=["close-opportunities"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class OpportunityCreateRequest(BaseModel):
    """Request to create an opportunity in Close CRM."""

    lead_id: str = Field(..., description="Close CRM lead ID to associate opportunity with")
    name: str = Field(..., description="Opportunity name/title", max_length=255)
    amount: Optional[float] = Field(None, description="Deal value in cents", ge=0)
    pipeline_id: Optional[str] = Field(None, description="Pipeline ID (uses default if not specified)")
    expected_close_date: Optional[datetime] = Field(None, description="Expected close date")
    confidence: Optional[int] = Field(None, description="Win confidence 0-100", ge=0, le=100)
    status_id: Optional[str] = Field(None, description="Status/stage ID within pipeline")
    note: Optional[str] = Field(None, description="Additional notes about the opportunity")


class OpportunityUpdateRequest(BaseModel):
    """Request to update an opportunity in Close CRM."""

    name: Optional[str] = Field(None, description="Opportunity name/title", max_length=255)
    amount: Optional[float] = Field(None, description="Deal value in cents", ge=0)
    status_id: Optional[str] = Field(None, description="Status/stage ID within pipeline")
    expected_close_date: Optional[datetime] = Field(None, description="Expected close date")
    confidence: Optional[int] = Field(None, description="Win confidence 0-100", ge=0, le=100)
    note: Optional[str] = Field(None, description="Additional notes about the opportunity")


class OpportunityResponse(BaseModel):
    """Response model for opportunity data."""

    id: str = Field(..., description="Close CRM opportunity ID")
    lead_id: str = Field(..., description="Associated lead ID")
    lead_name: Optional[str] = Field(None, description="Lead/company name")
    name: str = Field(..., description="Opportunity name")
    amount: Optional[float] = Field(None, description="Deal value in cents")
    confidence: Optional[int] = Field(None, description="Win confidence 0-100")
    status_id: Optional[str] = Field(None, description="Current status/stage ID")
    status_label: Optional[str] = Field(None, description="Current status label")
    pipeline_id: Optional[str] = Field(None, description="Pipeline ID")
    expected_close_date: Optional[str] = Field(None, description="Expected close date")
    date_won: Optional[str] = Field(None, description="Date opportunity was won")
    date_lost: Optional[str] = Field(None, description="Date opportunity was lost")
    created_by: Optional[str] = Field(None, description="User ID who created")
    updated_by: Optional[str] = Field(None, description="User ID who last updated")
    date_created: Optional[str] = Field(None, description="Creation timestamp")
    date_updated: Optional[str] = Field(None, description="Last update timestamp")


class OpportunityListResponse(BaseModel):
    """Response model for list of opportunities."""

    count: int
    opportunities: List[Dict[str, Any]]


class PipelineResponse(BaseModel):
    """Response model for pipeline data."""

    id: str = Field(..., description="Close CRM pipeline ID")
    name: str = Field(..., description="Pipeline name")
    statuses: List[Dict[str, Any]] = Field(default_factory=list, description="Pipeline statuses/stages")
    date_created: Optional[str] = Field(None, description="Creation timestamp")
    date_updated: Optional[str] = Field(None, description="Last update timestamp")


class PipelineListResponse(BaseModel):
    """Response model for list of pipelines."""

    count: int
    pipelines: List[Dict[str, Any]]


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================


def get_close_provider() -> CloseProvider:
    """Get Close CRM provider instance."""
    try:
        return CloseProvider(api_key=settings.CLOSE_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize CloseProvider: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Close CRM provider initialization failed: {str(e)}"
        )


# ============================================================================
# OPPORTUNITY ENDPOINTS
# ============================================================================


@router.get("/opportunities", response_model=OpportunityListResponse)
async def list_opportunities(
    lead_id: Optional[str] = Query(None, description="Filter by lead ID"),
    pipeline_id: Optional[str] = Query(None, description="Filter by pipeline ID"),
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    List opportunities from Close CRM.

    Returns all opportunities, optionally filtered by lead_id or pipeline_id.

    **Query Parameters:**
    - `lead_id`: Filter opportunities by associated lead
    - `pipeline_id`: Filter opportunities by pipeline

    **Returns:**
    - List of opportunity objects with deal details
    """
    try:
        opportunities = await close_provider.get_opportunities(
            lead_id=lead_id,
            pipeline_id=pipeline_id,
        )

        return OpportunityListResponse(
            count=len(opportunities),
            opportunities=opportunities,
        )

    except CRMRateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except CRMNetworkError as e:
        logger.error(f"Network error listing opportunities: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: str,
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a single opportunity by ID.

    **Path Parameters:**
    - `opportunity_id`: Close CRM opportunity ID

    **Returns:**
    - Opportunity object with full details
    """
    try:
        # Get all opportunities and filter by ID
        # Close API doesn't have a direct get-by-id endpoint for opportunities
        opportunities = await close_provider.get_opportunities(
            filters={"id": opportunity_id}
        )

        # Find the matching opportunity
        for opp in opportunities:
            if opp.get("id") == opportunity_id:
                return OpportunityResponse(
                    id=opp.get("id"),
                    lead_id=opp.get("lead_id"),
                    lead_name=opp.get("lead_name"),
                    name=opp.get("note") or opp.get("id"),  # Close uses 'note' field as name sometimes
                    amount=opp.get("value"),
                    confidence=opp.get("confidence"),
                    status_id=opp.get("status_id"),
                    status_label=opp.get("status_label"),
                    pipeline_id=opp.get("pipeline_id"),
                    expected_close_date=opp.get("date_expected_close"),
                    date_won=opp.get("date_won"),
                    date_lost=opp.get("date_lost"),
                    created_by=opp.get("created_by"),
                    updated_by=opp.get("updated_by"),
                    date_created=opp.get("date_created"),
                    date_updated=opp.get("date_updated"),
                )

        raise CRMNotFoundError(f"Opportunity {opportunity_id} not found")

    except CRMNotFoundError as e:
        logger.warning(f"Opportunity not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except CRMRateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except CRMNetworkError as e:
        logger.error(f"Network error getting opportunity: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting opportunity {opportunity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities", response_model=OpportunityResponse, status_code=201)
async def create_opportunity(
    request: OpportunityCreateRequest,
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new opportunity in Close CRM.

    Associates the opportunity with a lead and optionally a pipeline.

    **Request Body:**
    - `lead_id`: Required - Close lead ID to associate with
    - `name`: Required - Opportunity name/title
    - `amount`: Optional - Deal value in cents
    - `pipeline_id`: Optional - Pipeline to use (defaults to org default)
    - `expected_close_date`: Optional - Expected close date
    - `confidence`: Optional - Win confidence 0-100

    **Example:**
    ```json
    {
        "lead_id": "lead_xxx123",
        "name": "Enterprise License Deal",
        "amount": 50000,
        "confidence": 75,
        "expected_close_date": "2025-03-15T00:00:00Z"
    }
    ```

    **Returns:**
    - Created opportunity with ID and details
    """
    try:
        # Build opportunity data for Close API
        opportunity_data: Dict[str, Any] = {
            "note": request.name,  # Close uses 'note' as the opportunity name
        }

        if request.amount is not None:
            opportunity_data["value"] = request.amount
        if request.pipeline_id:
            opportunity_data["pipeline_id"] = request.pipeline_id
        if request.expected_close_date:
            opportunity_data["date_expected_close"] = request.expected_close_date.isoformat()
        if request.confidence is not None:
            opportunity_data["confidence"] = request.confidence
        if request.status_id:
            opportunity_data["status_id"] = request.status_id

        result = await close_provider.create_opportunity(
            lead_id=request.lead_id,
            opportunity_data=opportunity_data,
        )

        # Check if write operations are disabled
        if result.get("status") == "disabled":
            raise HTTPException(
                status_code=403,
                detail="Close CRM write operations are disabled (CLOSE_WRITE_DISABLED=True)"
            )

        return OpportunityResponse(
            id=result.get("id"),
            lead_id=result.get("lead_id"),
            lead_name=result.get("lead_name"),
            name=result.get("note") or request.name,
            amount=result.get("value"),
            confidence=result.get("confidence"),
            status_id=result.get("status_id"),
            status_label=result.get("status_label"),
            pipeline_id=result.get("pipeline_id"),
            expected_close_date=result.get("date_expected_close"),
            date_won=result.get("date_won"),
            date_lost=result.get("date_lost"),
            created_by=result.get("created_by"),
            updated_by=result.get("updated_by"),
            date_created=result.get("date_created"),
            date_updated=result.get("date_updated"),
        )

    except CRMValidationError as e:
        logger.warning(f"Validation error creating opportunity: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except CRMRateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except CRMNetworkError as e:
        logger.error(f"Network error creating opportunity: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: str,
    request: OpportunityUpdateRequest,
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    Update an existing opportunity in Close CRM.

    **Path Parameters:**
    - `opportunity_id`: Close CRM opportunity ID to update

    **Request Body (all optional):**
    - `name`: Opportunity name/title
    - `amount`: Deal value in cents
    - `status_id`: Stage/status ID within pipeline
    - `expected_close_date`: Expected close date
    - `confidence`: Win confidence 0-100

    **Example:**
    ```json
    {
        "amount": 75000,
        "confidence": 90,
        "status_id": "stat_negotiation"
    }
    ```

    **Returns:**
    - Updated opportunity with new values
    """
    try:
        # Build update data - only include non-None fields
        update_data: Dict[str, Any] = {}

        if request.name is not None:
            update_data["note"] = request.name
        if request.amount is not None:
            update_data["value"] = request.amount
        if request.status_id is not None:
            update_data["status_id"] = request.status_id
        if request.expected_close_date is not None:
            update_data["date_expected_close"] = request.expected_close_date.isoformat()
        if request.confidence is not None:
            update_data["confidence"] = request.confidence
        if request.note is not None:
            update_data["note"] = request.note

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update provided")

        result = await close_provider.update_opportunity(
            opportunity_id=opportunity_id,
            update_data=update_data,
        )

        # Check if write operations are disabled
        if result.get("status") == "disabled":
            raise HTTPException(
                status_code=403,
                detail="Close CRM write operations are disabled (CLOSE_WRITE_DISABLED=True)"
            )

        return OpportunityResponse(
            id=result.get("id"),
            lead_id=result.get("lead_id"),
            lead_name=result.get("lead_name"),
            name=result.get("note") or "",
            amount=result.get("value"),
            confidence=result.get("confidence"),
            status_id=result.get("status_id"),
            status_label=result.get("status_label"),
            pipeline_id=result.get("pipeline_id"),
            expected_close_date=result.get("date_expected_close"),
            date_won=result.get("date_won"),
            date_lost=result.get("date_lost"),
            created_by=result.get("created_by"),
            updated_by=result.get("updated_by"),
            date_created=result.get("date_created"),
            date_updated=result.get("date_updated"),
        )

    except CRMNotFoundError as e:
        logger.warning(f"Opportunity not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except CRMValidationError as e:
        logger.warning(f"Validation error updating opportunity: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except CRMRateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except CRMNetworkError as e:
        logger.error(f"Network error updating opportunity: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating opportunity {opportunity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PIPELINE ENDPOINTS
# ============================================================================


@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(
    close_provider: CloseProvider = Depends(get_close_provider),
    current_user: dict = Depends(get_current_user),
):
    """
    List all pipelines from Close CRM.

    Returns all configured pipelines with their stages/statuses.

    **Returns:**
    - List of pipeline objects with stages
    """
    try:
        pipelines = await close_provider.get_pipelines()

        return PipelineListResponse(
            count=len(pipelines),
            pipelines=pipelines,
        )

    except CRMRateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except CRMNetworkError as e:
        logger.error(f"Network error listing pipelines: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))
