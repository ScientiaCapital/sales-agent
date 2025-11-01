"""
Pydantic schemas for pipeline testing API
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime


class PipelineTestOptions(BaseModel):
    """Options for pipeline test execution"""
    stop_on_duplicate: bool = Field(default=True, description="Halt if duplicate detected")
    skip_enrichment: bool = Field(default=False, description="Skip enrichment stage")
    create_in_crm: bool = Field(default=True, description="Actually create lead in CRM")
    dry_run: bool = Field(default=False, description="Test without CRM writes")


class PipelineTestRequest(BaseModel):
    """Request to test a lead through the pipeline"""
    lead: Dict[str, Any] = Field(..., description="Lead data from CSV or manual input")
    options: PipelineTestOptions = Field(default_factory=PipelineTestOptions)

    @field_validator('lead')
    def validate_lead_has_name(cls, v):
        """Ensure lead has at minimum a name"""
        if not v.get('name') and not v.get('company'):
            raise ValueError("Lead must have 'name' or 'company' field")
        return v


class PipelineStageResult(BaseModel):
    """Result from a single pipeline stage"""
    status: str = Field(..., description="Stage status: success, failed, skipped, duplicate")
    latency_ms: Optional[int] = Field(None, description="Stage execution time in milliseconds")
    cost_usd: Optional[float] = Field(None, description="Stage cost in USD")
    confidence: Optional[float] = Field(None, description="Confidence score (for deduplication)")
    output: Optional[Dict[str, Any]] = Field(None, description="Stage output data")
    error: Optional[str] = Field(None, description="Error message if failed")


class PipelineTestResponse(BaseModel):
    """Complete pipeline test result"""
    success: bool = Field(..., description="Overall pipeline success")
    total_latency_ms: int = Field(..., description="Total execution time")
    total_cost_usd: float = Field(..., description="Total cost across all stages")
    lead_name: str = Field(..., description="Lead name for tracking")

    stages: Dict[str, PipelineStageResult] = Field(..., description="Per-stage results")

    error_stage: Optional[str] = Field(None, description="Stage that caused failure")
    error_message: Optional[str] = Field(None, description="Failure error message")

    timeline: Optional[List[Dict[str, Any]]] = Field(None, description="Stage timing timeline")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_latency_ms": 4250,
                "total_cost_usd": 0.002014,
                "lead_name": "A & A GENPRO INC.",
                "stages": {
                    "qualification": {
                        "status": "success",
                        "latency_ms": 633,
                        "cost_usd": 0.000006,
                        "output": {"score": 72, "tier": "high_value"}
                    }
                }
            }
        }


class CSVLeadImportRequest(BaseModel):
    """Request to import lead from CSV by index"""
    csv_path: str = Field(..., description="Absolute path to CSV file")
    lead_index: int = Field(..., ge=0, le=199, description="Lead index (0-199)")
    options: PipelineTestOptions = Field(default_factory=PipelineTestOptions)
