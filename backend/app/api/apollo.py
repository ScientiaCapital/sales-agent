"""
Apollo.io Contact Enrichment API Endpoints

Provides REST API for Apollo.io contact and company enrichment.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.services.apollo import ApolloService
from app.services.crm.base import Contact
from app.core.logging import setup_logging
from app.core.exceptions import (
    ValidationError,
    APIAuthenticationError,
    APIRateLimitError,
    APIConnectionError,
    APITimeoutError
)

logger = setup_logging(__name__)

router = APIRouter(prefix="/apollo", tags=["apollo", "enrichment"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class ContactEnrichRequest(BaseModel):
    """Request schema for contact enrichment."""
    
    email: Optional[EmailStr] = Field(None, description="Business email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    domain: Optional[str] = Field(None, description="Company domain (e.g., 'apollo.io')")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    reveal_personal_email: bool = Field(False, description="Get personal email (consumes extra credits)")
    reveal_phone: bool = Field(False, description="Get phone number (consumes extra credits)")
    
    @validator('domain')
    def clean_domain(cls, v):
        """Clean domain by removing www. and @ symbols."""
        if v:
            return v.replace("www.", "").replace("@", "").strip()
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@acme.com",
                "reveal_personal_email": False,
                "reveal_phone": False
            }
        }


class CompanyEnrichRequest(BaseModel):
    """Request schema for company enrichment."""
    
    domain: str = Field(..., description="Company domain without www. or @ (e.g., 'apollo.io')")
    
    @validator('domain')
    def clean_domain(cls, v):
        """Clean and validate domain."""
        cleaned = v.replace("www.", "").replace("@", "").strip()
        if not cleaned:
            raise ValueError("Domain cannot be empty")
        return cleaned
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "apollo.io"
            }
        }


class BulkContactEnrichRequest(BaseModel):
    """Request schema for bulk contact enrichment."""
    
    contacts: List[Dict[str, str]] = Field(
        ...,
        description="List of contacts to enrich (max 10)",
        max_items=10
    )
    reveal_personal_emails: bool = Field(False, description="Get personal emails (consumes extra credits)")
    
    @validator('contacts')
    def validate_contacts(cls, v):
        """Validate contact data."""
        if len(v) > 10:
            raise ValueError("Maximum 10 contacts per bulk request")
        if len(v) == 0:
            raise ValueError("At least one contact required")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "contacts": [
                    {"email": "john@acme.com"},
                    {"first_name": "Jane", "last_name": "Doe", "domain": "acme.com"}
                ],
                "reveal_personal_emails": False
            }
        }


class ContactEnrichResponse(BaseModel):
    """Response schema for contact enrichment."""
    
    success: bool
    contact: Contact
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "apollo"
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "contact": {
                    "email": "john@acme.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "title": "VP of Sales",
                    "company": "Acme Corp",
                    "linkedin_url": "https://linkedin.com/in/johndoe"
                },
                "enriched_at": "2024-01-01T12:00:00Z",
                "source": "apollo"
            }
        }


class CompanyEnrichResponse(BaseModel):
    """Response schema for company enrichment."""
    
    success: bool
    company: Dict[str, Any]
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "apollo"


class BulkContactEnrichResponse(BaseModel):
    """Response schema for bulk contact enrichment."""
    
    success: bool
    contacts: List[Contact]
    total_enriched: int
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "apollo"


class CreditBalanceResponse(BaseModel):
    """Response schema for credit balance check."""
    
    credits_remaining: str
    credits_used: str
    rate_limit_remaining: str


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_apollo_service() -> ApolloService:
    """
    Dependency injection for Apollo service.
    
    Returns:
        Initialized ApolloService instance
    
    Raises:
        HTTPException: If API key is missing or invalid
    """
    try:
        service = ApolloService()
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Apollo service: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Apollo service initialization failed: {str(e)}"
        )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post(
    "/enrich/contact",
    response_model=ContactEnrichResponse,
    summary="Enrich contact data",
    description="Enrich contact information using Apollo.io person match API"
)
async def enrich_contact(
    request: ContactEnrichRequest,
    apollo: ApolloService = Depends(get_apollo_service)
) -> ContactEnrichResponse:
    """
    Enrich contact data with Apollo.io.
    
    Provide at least one of: email, first_name+last_name, or linkedin_url.
    
    Args:
        request: Contact enrichment request with identifying information
        apollo: Apollo service instance (injected)
    
    Returns:
        Enriched contact data
    
    Raises:
        HTTPException: If enrichment fails or validation errors occur
    """
    try:
        enriched_contact = await apollo.enrich_contact(
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            domain=request.domain,
            linkedin_url=request.linkedin_url,
            reveal_personal_email=request.reveal_personal_email,
            reveal_phone=request.reveal_phone
        )
        
        logger.info(f"Contact enriched successfully: {request.email or request.linkedin_url}")
        
        return ContactEnrichResponse(
            success=True,
            contact=enriched_contact
        )
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except APIAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    except APIRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    
    except APITimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during contact enrichment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Contact enrichment failed")
    
    finally:
        await apollo.close()


@router.post(
    "/enrich/company",
    response_model=CompanyEnrichResponse,
    summary="Enrich company data",
    description="Enrich company information using Apollo.io organization API"
)
async def enrich_company(
    request: CompanyEnrichRequest,
    apollo: ApolloService = Depends(get_apollo_service)
) -> CompanyEnrichResponse:
    """
    Enrich company data with Apollo.io.
    
    Args:
        request: Company enrichment request with domain
        apollo: Apollo service instance (injected)
    
    Returns:
        Enriched company data
    
    Raises:
        HTTPException: If enrichment fails or validation errors occur
    """
    try:
        enriched_company = await apollo.enrich_company(domain=request.domain)
        
        logger.info(f"Company enriched successfully: {request.domain}")
        
        return CompanyEnrichResponse(
            success=True,
            company=enriched_company
        )
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except APIAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    except APIRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    
    except APITimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during company enrichment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Company enrichment failed")
    
    finally:
        await apollo.close()


@router.post(
    "/enrich/bulk",
    response_model=BulkContactEnrichResponse,
    summary="Bulk enrich contacts",
    description="Enrich multiple contacts in a single request (max 10)"
)
async def bulk_enrich_contacts(
    request: BulkContactEnrichRequest,
    apollo: ApolloService = Depends(get_apollo_service)
) -> BulkContactEnrichResponse:
    """
    Bulk enrich up to 10 contacts with Apollo.io.
    
    Args:
        request: Bulk enrichment request with contact list
        apollo: Apollo service instance (injected)
    
    Returns:
        List of enriched contacts
    
    Raises:
        HTTPException: If enrichment fails or validation errors occur
    """
    try:
        enriched_contacts = await apollo.bulk_enrich_contacts(
            contacts=request.contacts,
            reveal_personal_emails=request.reveal_personal_emails
        )
        
        logger.info(f"Bulk enrichment complete: {len(enriched_contacts)} contacts enriched")
        
        return BulkContactEnrichResponse(
            success=True,
            contacts=enriched_contacts,
            total_enriched=len(enriched_contacts)
        )
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except APIAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    except APIRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    
    except APITimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during bulk enrichment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Bulk enrichment failed")
    
    finally:
        await apollo.close()


@router.get(
    "/credits",
    response_model=CreditBalanceResponse,
    summary="Check credit balance",
    description="Get remaining API credits and usage information"
)
async def get_credits(
    apollo: ApolloService = Depends(get_apollo_service)
) -> CreditBalanceResponse:
    """
    Get Apollo.io credit balance and usage stats.
    
    Args:
        apollo: Apollo service instance (injected)
    
    Returns:
        Credit balance and usage information
    
    Note:
        This endpoint returns placeholder data until credit tracking is implemented.
    """
    try:
        balance = await apollo.get_credit_balance()
        
        return CreditBalanceResponse(
            credits_remaining=balance["credits_remaining"],
            credits_used=balance["credits_used"],
            rate_limit_remaining=balance["rate_limit_remaining"]
        )
    
    finally:
        await apollo.close()
