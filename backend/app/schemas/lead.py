"""
Pydantic schemas for lead qualification requests and responses
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class LeadQualificationRequest(BaseModel):
    """Request body for lead qualification endpoint"""
    company_name: str = Field(..., description="Company name", min_length=1, max_length=255)
    company_website: Optional[str] = Field(None, description="Company website URL", max_length=500)
    company_size: Optional[str] = Field(None, description="Company size", max_length=100)
    industry: Optional[str] = Field(None, description="Industry sector", max_length=200)
    contact_name: Optional[str] = Field(None, description="Contact person's name", max_length=255)
    contact_email: Optional[EmailStr] = Field(None, description="Contact email address")
    contact_phone: Optional[str] = Field(None, description="Contact phone number", max_length=50)
    contact_title: Optional[str] = Field(None, description="Contact person's job title", max_length=200)
    notes: Optional[str] = Field(None, description="Additional notes about the lead")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "company_name": "TechCorp Inc",
                    "company_website": "https://techcorp.example.com",
                    "company_size": "50-200",
                    "industry": "SaaS",
                    "contact_name": "John Smith",
                    "contact_email": "john.smith@techcorp.example.com",
                    "contact_title": "VP of Sales",
                    "notes": "Expressed interest in automation tools"
                }
            ]
        }
    }


class LeadQualificationResponse(BaseModel):
    """Response from lead qualification endpoint"""
    id: int = Field(..., description="Lead ID in database")
    company_name: str
    qualification_score: float = Field(..., description="AI-generated qualification score (0-100)", ge=0, le=100)
    qualification_reasoning: str = Field(..., description="AI explanation for the score")
    qualification_latency_ms: int = Field(..., description="API response time in milliseconds")
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "company_name": "TechCorp Inc",
                    "qualification_score": 85.5,
                    "qualification_reasoning": "High-value lead: SaaS company in growth phase (50-200 employees) with VP-level contact. Industry alignment is strong. Website indicates established product offering.",
                    "qualification_latency_ms": 78,
                    "created_at": "2025-10-04T13:45:00Z"
                }
            ]
        }
    }


class LeadListResponse(BaseModel):
    """Response for listing leads"""
    id: int
    company_name: str
    qualification_score: Optional[float]
    contact_email: Optional[str]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
