"""
Pydantic schemas for CSV import endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CSVUploadResponse(BaseModel):
    """Response after CSV file upload"""
    import_id: int = Field(..., description="Unique ID for this import")
    filename: str = Field(..., description="Sanitized filename")
    status: str = Field(..., description="Import status (uploaded, processing, completed, failed)")
    total_rows: int = Field(..., description="Total rows in CSV")
    message: str = Field(..., description="Human-readable status message")

    class Config:
        json_schema_extra = {
            "example": {
                "import_id": 123,
                "filename": "leads_20240116.csv",
                "status": "processing",
                "total_rows": 20,
                "message": "CSV uploaded successfully. Processing 20 leads in background."
            }
        }


class CSVImportStatus(BaseModel):
    """Status of CSV import processing"""
    import_id: int
    filename: str
    status: str = Field(..., description="uploaded | processing | completed | failed | archived")

    # Row counts
    total_rows: int
    processed_rows: int
    failed_rows: int

    # Progress percentage
    progress_percent: float = Field(..., description="Processing progress (0-100)")

    # Cost tracking
    total_cost_usd: float

    # Timestamps
    uploaded_at: datetime
    started_processing_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Error handling
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "import_id": 123,
                "filename": "leads_20240116.csv",
                "status": "processing",
                "total_rows": 20,
                "processed_rows": 15,
                "failed_rows": 0,
                "progress_percent": 75.0,
                "total_cost_usd": 0.0375,
                "uploaded_at": "2024-01-16T10:30:00Z",
                "started_processing_at": "2024-01-16T10:30:05Z",
                "completed_at": None,
                "error_message": None
            }
        }


class CSVProcessingOptions(BaseModel):
    """Options for CSV processing through pipeline"""
    stop_on_duplicate: bool = Field(True, description="Stop processing if duplicate detected")
    skip_enrichment: bool = Field(False, description="Skip enrichment stage")
    create_in_crm: bool = Field(True, description="Create leads in Close CRM")
    dry_run: bool = Field(False, description="Test mode - no CRM writes")
    max_concurrent: int = Field(1, description="Maximum concurrent lead processing (1-10)")

    class Config:
        json_schema_extra = {
            "example": {
                "stop_on_duplicate": False,
                "skip_enrichment": False,
                "create_in_crm": True,
                "dry_run": False,
                "max_concurrent": 1
            }
        }
