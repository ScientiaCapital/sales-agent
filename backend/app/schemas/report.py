"""
Pydantic schemas for report generation requests and responses
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class ReportGenerateRequest(BaseModel):
    """Request to generate a report for a lead"""
    lead_id: int = Field(..., description="Lead ID to generate report for", gt=0)
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "lead_id": 42
                }
            ]
        }
    )


class ReportResponse(BaseModel):
    """Complete report response with all data"""
    id: int = Field(..., description="Report ID")
    lead_id: int = Field(..., description="Associated lead ID")
    title: str = Field(..., description="Report title")
    status: str = Field(..., description="Report generation status")
    content_markdown: Optional[str] = Field(None, description="Markdown content")
    content_html: Optional[str] = Field(None, description="HTML content")
    research_data: Optional[Dict[str, Any]] = Field(None, description="Raw research data from SearchAgent")
    insights_data: Optional[Dict[str, Any]] = Field(None, description="Strategic insights from AnalysisAgent")
    confidence_score: Optional[float] = Field(None, description="Overall confidence score (0-100)", ge=0, le=100)
    generation_time_ms: Optional[int] = Field(None, description="Total generation time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if status is 'failed'")
    created_at: datetime = Field(..., description="Report creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "lead_id": 42,
                    "title": "Strategic Report: TechCorp Inc",
                    "status": "completed",
                    "content_markdown": "# Executive Summary\n\nTechCorp Inc is a rapidly growing SaaS company...",
                    "content_html": "<h1>Executive Summary</h1><p>TechCorp Inc is a rapidly growing SaaS company...</p>",
                    "confidence_score": 87.5,
                    "generation_time_ms": 8420,
                    "created_at": "2025-10-04T10:30:00Z"
                }
            ]
        }
    )


class ReportSummary(BaseModel):
    """Lightweight report summary for list views"""
    id: int
    lead_id: int
    title: str
    status: str
    confidence_score: Optional[float] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    """Paginated list of reports"""
    reports: List[ReportSummary] = Field(..., description="List of report summaries")
    total: int = Field(..., description="Total number of reports")
    page: int = Field(1, description="Current page number", ge=1)
    page_size: int = Field(20, description="Items per page", ge=1, le=100)
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reports": [
                        {
                            "id": 1,
                            "lead_id": 42,
                            "title": "Strategic Report: TechCorp Inc",
                            "status": "completed",
                            "confidence_score": 87.5,
                            "created_at": "2025-10-04T10:30:00Z"
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "page_size": 20
                }
            ]
        }
    )


class ReportStatusResponse(BaseModel):
    """Status update for async report generation"""
    report_id: Optional[int] = Field(None, description="Report ID (null if still generating)")
    status: str = Field(..., description="Current status")
    message: str = Field(..., description="Status message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "report_id": None,
                    "status": "generating",
                    "message": "Report generation started. Check back in a few seconds."
                }
            ]
        }
    )
