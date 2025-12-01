"""
Pipeline Lead Schema - Shared data contract for GTM stack integration.

This schema represents a lead flowing through the entire pipeline:
Prospector (dealer-scraper) → Qualifier (sales-agent) → Sender (cold-reach) → VozLux

Matches the dealer-scraper CSV output format.
"""
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PipelineStage(str, Enum):
    """Pipeline stages a lead progresses through."""
    SCRAPED = "scraped"          # Imported from Prospector CSV
    QUALIFIED = "qualified"     # Scored by Qualifier
    SEQUENCED = "sequenced"     # Enrolled in Sender email sequence
    CONTACTED = "contacted"     # First email sent
    REPLIED = "replied"         # Reply received
    CALLED = "called"           # Voice call triggered
    CONVERTED = "converted"     # Meeting scheduled
    DISQUALIFIED = "disqualified"  # Removed from pipeline


class QualificationTier(str, Enum):
    """Lead qualification tiers from Qualifier scoring."""
    A = "A"  # Top priority - immediate action
    B = "B"  # High value - next batch
    C = "C"  # Medium value - nurture
    D = "D"  # Low value - archive


class PriorityTier(str, Enum):
    """Priority tiers from Prospector ICP scoring."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PipelineLead(BaseModel):
    """
    Core lead schema for pipeline integration.

    Maps directly to dealer-scraper CSV output fields.
    """
    # Identity
    lead_id: Optional[str] = Field(None, description="Unique lead identifier (generated if not provided)")
    company_name: str = Field(..., alias="name", description="Company/dealer name")

    # Contact info
    phone: Optional[str] = Field(None, description="Primary phone number")
    email: Optional[EmailStr] = Field(None, description="Primary email (may be empty)")
    decision_maker_email: Optional[EmailStr] = Field(None, description="Decision maker email if found")
    decision_maker_name: Optional[str] = Field(None, description="Decision maker name if found")

    # Location
    street: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State abbreviation")
    zip_code: Optional[str] = Field(None, alias="zip", description="ZIP code")
    address_full: Optional[str] = Field(None, description="Full formatted address")

    # Prospector scoring (from dealer-scraper)
    coperniq_score: int = Field(default=0, ge=0, le=100, description="ICP score 0-100 from Prospector")
    icp_tier: Optional[str] = Field(None, alias="ICP_Tier", description="ICP tier from Prospector")
    priority_tier: PriorityTier = Field(default=PriorityTier.MEDIUM, description="Priority tier: HIGH/MEDIUM/LOW")

    # OEM certifications
    oem_certifications: List[str] = Field(default_factory=list, description="List of OEM certifications")
    oem_count: int = Field(default=0, alias="OEM_Count", description="Number of OEM certifications")
    generac_tier: Optional[str] = Field(None, description="Generac certification tier if applicable")

    # Pipeline state
    pipeline_stage: PipelineStage = Field(default=PipelineStage.SCRAPED, description="Current pipeline stage")
    qualification_tier: Optional[QualificationTier] = Field(None, description="Qualifier tier A/B/C/D")
    qualification_score: Optional[float] = Field(None, ge=0, le=100, description="Qualifier AI score")
    qualification_reasoning: Optional[str] = Field(None, description="AI reasoning for qualification")

    # Online presence
    website: Optional[str] = Field(None, description="Company website")
    domain: Optional[str] = Field(None, description="Domain name")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn company page")

    # Business intelligence
    rating: Optional[float] = Field(None, description="Google rating")
    review_count: Optional[int] = Field(None, description="Google review count")
    employee_count: Optional[str] = Field(None, description="Estimated employee count")
    estimated_revenue: Optional[str] = Field(None, description="Estimated revenue")

    # Capability flags
    has_solar: bool = Field(default=False)
    has_hvac: bool = Field(default=False)
    has_battery: bool = Field(default=False)
    has_generator: bool = Field(default=False)
    has_electrical: bool = Field(default=False)
    is_residential: bool = Field(default=False)
    is_commercial: bool = Field(default=False)

    # MEPR scoring (Multi-trade capability)
    mep_score: Optional[int] = Field(None, description="MEP-R capability score")
    is_mep_contractor: bool = Field(default=False)
    is_mep_r_contractor: bool = Field(default=False)

    # Sequence tracking (filled by Sender)
    sequence_id: Optional[int] = Field(None, description="Active sequence ID in cold-reach")
    sequence_entry_id: Optional[int] = Field(None, description="Sequence entry tracking ID")
    last_email_sent: Optional[datetime] = Field(None, description="Last email timestamp")
    emails_sent: int = Field(default=0, description="Total emails sent")
    reply_received: bool = Field(default=False, description="Whether reply was received")
    reply_intent: Optional[str] = Field(None, description="Classified reply intent")

    # Call tracking (filled by VozLux)
    last_call_at: Optional[datetime] = Field(None, description="Last call timestamp")
    calls_made: int = Field(default=0, description="Total calls made")
    call_outcome: Optional[str] = Field(None, description="Latest call outcome")
    meeting_scheduled: bool = Field(default=False, description="Whether meeting was scheduled")

    # Metadata
    source: str = Field(default="dealer-scraper", description="Lead source")
    collection_date: Optional[datetime] = Field(None, description="When lead was scraped")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Flexible custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional custom data")

    model_config = {
        "populate_by_name": True,  # Allow both alias and field name
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "name": "SunPower Electric LLC",
                "phone": "+1-555-123-4567",
                "email": "info@sunpowerelectric.com",
                "state": "CA",
                "city": "Sacramento",
                "coperniq_score": 85,
                "priority_tier": "HIGH",
                "oem_certifications": ["Generac", "Enphase", "SolarEdge"],
                "pipeline_stage": "qualified",
                "qualification_tier": "A",
                "has_solar": True,
                "has_battery": True
            }
        }
    }

    @field_validator('oem_certifications', mode='before')
    @classmethod
    def parse_oem_certifications(cls, v):
        """Parse OEM certifications from string or list."""
        if isinstance(v, str):
            # Handle comma-separated string from CSV
            if not v or v.lower() == 'nan':
                return []
            return [cert.strip() for cert in v.split(',') if cert.strip()]
        return v or []

    @field_validator('priority_tier', mode='before')
    @classmethod
    def normalize_priority_tier(cls, v):
        """Normalize priority tier to enum."""
        if not v:
            return PriorityTier.MEDIUM
        v_upper = str(v).upper()
        if v_upper in ['HIGH', 'H', '1']:
            return PriorityTier.HIGH
        elif v_upper in ['LOW', 'L', '3']:
            return PriorityTier.LOW
        return PriorityTier.MEDIUM


class PipelineLeadBatch(BaseModel):
    """Batch of pipeline leads for import."""
    leads: List[PipelineLead] = Field(..., description="List of leads")
    source: str = Field(default="csv_import", description="Import source")
    imported_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def count(self) -> int:
        return len(self.leads)

    @property
    def high_priority_count(self) -> int:
        return sum(1 for l in self.leads if l.priority_tier == PriorityTier.HIGH)


class PipelineLeadUpdate(BaseModel):
    """Partial update for a pipeline lead."""
    pipeline_stage: Optional[PipelineStage] = None
    qualification_tier: Optional[QualificationTier] = None
    qualification_score: Optional[float] = None
    qualification_reasoning: Optional[str] = None
    sequence_id: Optional[int] = None
    sequence_entry_id: Optional[int] = None
    last_email_sent: Optional[datetime] = None
    emails_sent: Optional[int] = None
    reply_received: Optional[bool] = None
    reply_intent: Optional[str] = None
    last_call_at: Optional[datetime] = None
    calls_made: Optional[int] = None
    call_outcome: Optional[str] = None
    meeting_scheduled: Optional[bool] = None
    custom_fields: Optional[Dict[str, Any]] = None


class PipelineImportResult(BaseModel):
    """Result of a batch import operation."""
    success: bool = Field(..., description="Overall import success")
    total_leads: int = Field(..., description="Total leads in input")
    imported_count: int = Field(..., description="Successfully imported")
    skipped_count: int = Field(default=0, description="Skipped (duplicates, etc)")
    failed_count: int = Field(default=0, description="Failed validation")

    tier_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count by priority tier")
    stage_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count by pipeline stage")

    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    duration_ms: int = Field(..., description="Import duration in milliseconds")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "total_leads": 100,
                "imported_count": 92,
                "skipped_count": 5,
                "failed_count": 3,
                "tier_breakdown": {"HIGH": 35, "MEDIUM": 42, "LOW": 15},
                "stage_breakdown": {"scraped": 92},
                "errors": ["Row 45: Missing company name"],
                "duration_ms": 1250
            }
        }
    }
