"""Pydantic schemas for VLM Analysis API requests and responses.

PRIVATE - Scientia Capital Proprietary IP
"""
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AnalysisType(str, Enum):
    """VLM analysis types."""

    EQUIPMENT = "equipment"
    BLUEPRINT = "blueprint"
    FIELD_PHOTO = "field_photo"
    GENERIC = "generic"


class VLMModel(str, Enum):
    """Supported VLM models via OpenRouter."""

    QWEN_72B = "qwen/qwen2.5-vl-72b-instruct"
    QWEN_30B = "qwen/qwen2.5-vl-30b-instruct"
    QWEN_8B = "qwen/qwen2.5-vl-8b-instruct"
    DEEPSEEK_CHAT = "deepseek/deepseek-chat-v3.1"


class ROIRegion(BaseModel):
    """Region of Interest for targeted re-analysis.

    Attributes:
        quadrant: Quadrant identifier (e.g., "top-left", "bottom-right")
        x: Left edge (0-1 normalized)
        y: Top edge (0-1 normalized)
        width: Width (0-1 normalized)
        height: Height (0-1 normalized)
        confidence: Initial confidence in this region
        priority: Analysis priority (higher = more important)
    """

    quadrant: str = Field(..., description="Quadrant identifier")
    x: float = Field(..., ge=0.0, le=1.0, description="Left edge (normalized)")
    y: float = Field(..., ge=0.0, le=1.0, description="Top edge (normalized)")
    width: float = Field(..., ge=0.0, le=1.0, description="Width (normalized)")
    height: float = Field(..., ge=0.0, le=1.0, description="Height (normalized)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Initial confidence")
    priority: int = Field(..., ge=1, description="Analysis priority")


class AnalyzeRequest(BaseModel):
    """Request schema for POST /api/v1/analyze endpoint.

    Attributes:
        image: Base64-encoded image data (required)
        prompt: Custom analysis prompt (required)
        analysis_type: Type of analysis to perform
        model: VLM model to use (default: qwen-72b)
        trade: Trade/domain context (e.g., "hvac", "roofing", "solar")
        use_cache: Whether to use cached results (default: True)
        use_rag: Whether to use RAG for similar examples (default: True)
        enable_roi: Enable confidence-guided ROI re-analysis (default: False)
        roi_threshold: Confidence threshold to trigger ROI (default: 0.75)
        max_roi_regions: Maximum ROI regions to analyze (default: 2)
        workflow: Workflow identifier for analytics
    """

    image: str = Field(..., min_length=1, description="Base64-encoded image data")
    prompt: str = Field(..., min_length=1, max_length=5000, description="Analysis prompt")
    analysis_type: AnalysisType = Field(
        AnalysisType.GENERIC, description="Type of analysis"
    )
    model: VLMModel = Field(VLMModel.QWEN_72B, description="VLM model to use")
    trade: str | None = Field(None, description="Trade/domain context")
    use_cache: bool = Field(True, description="Use cached results")
    use_rag: bool = Field(True, description="Use RAG for similar examples")
    enable_roi: bool = Field(False, description="Enable ROI re-analysis")
    roi_threshold: float = Field(
        0.75, ge=0.0, le=1.0, description="ROI trigger threshold"
    )
    max_roi_regions: int = Field(
        2, ge=1, le=5, description="Maximum ROI regions to analyze"
    )
    workflow: Literal["field", "homeowner", "takeoff", "cli"] | None = Field(
        None, description="Workflow identifier"
    )

    @field_validator("image")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        """Validate base64 image data."""
        # Remove data URL prefix if present
        if "," in v:
            v = v.split(",", 1)[1]
        return v


class BatchAnalyzeRequest(BaseModel):
    """Request schema for POST /api/v1/analyze/batch endpoint.

    Attributes:
        images: List of base64-encoded images (max 10)
        prompt: Analysis prompt (required)
        analysis_type: Type of analysis to perform
        model: VLM model to use
        trade: Trade/domain context
        use_cache: Whether to use cached results
        use_rag: Whether to use RAG for similar examples
        workflow: Workflow identifier for analytics
    """

    images: list[str] = Field(
        ..., min_length=1, max_length=10, description="Base64-encoded images"
    )
    prompt: str = Field(..., min_length=1, max_length=5000, description="Analysis prompt")
    analysis_type: AnalysisType = Field(
        AnalysisType.GENERIC, description="Type of analysis"
    )
    model: VLMModel = Field(VLMModel.QWEN_72B, description="VLM model to use")
    trade: str | None = Field(None, description="Trade/domain context")
    use_cache: bool = Field(True, description="Use cached results")
    use_rag: bool = Field(True, description="Use RAG for similar examples")
    workflow: Literal["field", "homeowner", "takeoff", "cli"] | None = Field(
        None, description="Workflow identifier"
    )

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str]) -> list[str]:
        """Validate and clean base64 image data."""
        cleaned = []
        for img in v:
            # Remove data URL prefix if present
            if "," in img:
                img = img.split(",", 1)[1]
            cleaned.append(img)
        return cleaned


class ConfidenceBreakdown(BaseModel):
    """Detailed confidence metrics.

    Attributes:
        overall: Overall confidence score (0-1)
        vlm_confidence: VLM model confidence
        cache_hit: Whether cache was used
        rag_similarity: RAG similarity score (if used)
        field_completeness: Field completeness score
        validation_pass: Validation pass rate
        roi_boost: Confidence boost from ROI analysis
    """

    overall: float = Field(..., ge=0.0, le=1.0)
    vlm_confidence: float = Field(..., ge=0.0, le=1.0)
    cache_hit: bool = Field(False)
    rag_similarity: float | None = Field(None, ge=0.0, le=1.0)
    field_completeness: float | None = Field(None, ge=0.0, le=1.0)
    validation_pass: float | None = Field(None, ge=0.0, le=1.0)
    roi_boost: float = Field(0.0, ge=0.0, le=0.2)


class ROIAnalysisResult(BaseModel):
    """ROI re-analysis result.

    Attributes:
        triggered: Whether ROI was triggered
        initial_confidence: Confidence before ROI
        final_confidence: Confidence after ROI
        regions_analyzed: Regions that were re-analyzed
        confidence_improvement: Total confidence improvement
        roi_detection_time_ms: ROI detection time
        roi_analysis_time_ms: ROI analysis time
    """

    triggered: bool
    initial_confidence: float = Field(..., ge=0.0, le=1.0)
    final_confidence: float = Field(..., ge=0.0, le=1.0)
    regions_analyzed: list[ROIRegion]
    confidence_improvement: float = Field(..., ge=0.0)
    roi_detection_time_ms: float = Field(..., ge=0.0)
    roi_analysis_time_ms: float = Field(..., ge=0.0)


class AnalyzeResponse(BaseModel):
    """Response schema for POST /api/v1/analyze endpoint.

    Attributes:
        extraction: Extracted data as JSON object
        confidence: Overall confidence score (0-1)
        confidence_breakdown: Detailed confidence metrics
        cache_hit: Whether cache was used
        rag_used: Whether RAG was used
        cost_saved: Estimated $ saved by using cache
        processing_time_ms: Total processing time
        roi_analysis: ROI re-analysis results (if triggered)
        model_used: VLM model that was used
    """

    extraction: dict[str, Any] = Field(..., description="Extracted data")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    confidence_breakdown: ConfidenceBreakdown | None = Field(
        None, description="Detailed confidence metrics"
    )
    cache_hit: bool = Field(False, description="Cache was used")
    rag_used: bool = Field(False, description="RAG was used")
    cost_saved: float = Field(0.0, ge=0.0, description="Cost saved ($)")
    processing_time_ms: float = Field(..., ge=0.0, description="Processing time (ms)")
    roi_analysis: ROIAnalysisResult | None = Field(None, description="ROI analysis")
    model_used: str = Field(..., description="VLM model used")


class BatchAnalyzeResponse(BaseModel):
    """Response schema for POST /api/v1/analyze/batch endpoint.

    Attributes:
        results: List of analysis results
        total_processing_time_ms: Total processing time for all images
        total_cost_saved: Total cost saved across all images
        cache_hit_rate: Percentage of cache hits
    """

    results: list[AnalyzeResponse] = Field(..., description="Analysis results")
    total_processing_time_ms: float = Field(
        ..., ge=0.0, description="Total processing time"
    )
    total_cost_saved: float = Field(0.0, ge=0.0, description="Total cost saved")
    cache_hit_rate: float = Field(
        0.0, ge=0.0, le=1.0, description="Cache hit rate (0-1)"
    )


class ModelInfo(BaseModel):
    """VLM model information.

    Attributes:
        id: Model identifier
        name: Human-readable model name
        provider: Provider name (OpenRouter)
        context_length: Maximum context length in tokens
        cost_per_million_tokens: Cost per 1M tokens
        recommended_for: Recommended use cases
    """

    id: str
    name: str
    provider: str = "OpenRouter"
    context_length: int
    cost_per_million_tokens: float
    recommended_for: list[str]


class ErrorResponse(BaseModel):
    """Standard error response schema.

    Attributes:
        detail: Error message description
        error_type: Type of error
        status_code: HTTP status code
    """

    detail: str
    error_type: str | None = None
    status_code: int = 500
