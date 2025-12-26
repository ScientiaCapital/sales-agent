"""Configuration models for VLM services."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class Trade(str, Enum):
    """Construction trade types for VLM analysis."""
    HVAC = "hvac"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    ROOFING = "roofing"
    SOLAR = "solar"
    GENERAL = "general"


class ModelInfo(BaseModel):
    """Information about a VLM model."""
    id: str
    name: str
    context_length: int
    cost_per_image: float
    supports_pdf: bool = False
    max_image_size: int = 4096  # Max dimension in pixels


class VLMConfig(BaseModel):
    """VLM analysis configuration."""
    model: str = "qwen/qwen2.5-vl-72b-instruct"
    prompt: str
    max_tokens: int = 4096
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Image configuration
    image_quality: float = Field(default=0.85, ge=0.1, le=1.0)
    max_dimension: int = Field(default=2048, ge=256, le=4096)

    # Optional metadata
    trade: Optional[Trade] = None
    workflow: Optional[str] = None  # 'field', 'homeowner', 'takeoff', 'cli'

    # Cache and RAG settings
    use_cache: bool = True
    use_rag: bool = True
    min_cache_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    rag_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    rag_max_examples: int = Field(default=3, ge=1, le=10)

    # ROI re-analysis settings
    enable_roi: bool = False
    roi_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    max_roi_regions: int = Field(default=2, ge=1, le=5)


class VLMResponse(BaseModel):
    """Response from VLM analysis."""
    extraction: dict[str, Any]
    model: str
    tokens_used: int
    latency_ms: int
    confidence: float = Field(ge=0.0, le=1.0)


class BoundingBox(BaseModel):
    """Bounding box for image regions."""
    x: int  # Top-left X coordinate
    y: int  # Top-left Y coordinate
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary format."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height
        }


class ROIRegion(BaseModel):
    """Region of Interest detected in an image."""
    quadrant: str  # 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'
    priority: str  # 'high', 'medium', 'low'
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    description: str
    detected_features: list[str] = Field(default_factory=list)


class ROIAnalysisResult(BaseModel):
    """Result from ROI re-analysis."""
    triggered: bool
    initial_confidence: float
    final_confidence: float
    regions_analyzed: list[ROIRegion]
    region_results: list[dict[str, Any]] = Field(default_factory=list)
    roi_detection_time_ms: int
    roi_analysis_time_ms: int
    confidence_improvement: float


class CacheEntry(BaseModel):
    """VLM cache entry from database."""
    id: str
    image_hash: str
    trade: str
    extraction_result: dict[str, Any]
    confidence: float
    times_served: int
    created_at: str
    last_accessed: str
