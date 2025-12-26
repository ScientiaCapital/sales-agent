"""Response models for VLM services."""
from typing import Any, Optional
from pydantic import BaseModel, Field

from .config import ROIAnalysisResult


class ConfidenceBreakdown(BaseModel):
    """Detailed confidence metrics breakdown."""
    field_completeness: float = Field(ge=0.0, le=1.0)
    value_validity: float = Field(ge=0.0, le=1.0)
    trade_match: float = Field(ge=0.0, le=1.0)
    rag_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)


class SmartVLMResult(BaseModel):
    """Result from SmartVLM analysis with caching and RAG."""
    extraction: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: Optional[ConfidenceBreakdown] = None
    cache_hit: bool
    rag_used: bool
    cost_saved: float  # Estimated $ saved by using cache
    processing_time_ms: int
    roi_analysis: Optional[ROIAnalysisResult] = None
