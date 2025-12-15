"""
Scientia Capital Audit Schema
Investor-Grade Logging for VLM Provider Validation

Business Context:
- Proves Chinese VLM cost arbitrage vs Western models
- Validates accuracy parity for 3-year pro forma
- Tracks margin story: Qwen @ 1/10th cost of Claude/Gemini
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Provider(str, Enum):
    """VLM Provider types."""
    OPENROUTER = "openrouter"      # Chinese VLMs (Qwen) - cost leader
    ANTHROPIC = "anthropic"        # Claude 4.5 family - premium baseline
    GEMINI = "gemini"              # Google - alternative baseline
    LOCAL = "local"                # Self-hosted (future)


class ModelTier(str, Enum):
    """Model pricing tiers for margin analysis."""
    BUDGET = "budget"              # < $0.001/call (Qwen 8B)
    COST_LEADER = "cost_leader"    # $0.001-0.005/call (Qwen 30B/72B)
    STANDARD = "standard"          # $0.005-0.02/call (Gemini Flash)
    PREMIUM = "premium"            # $0.02-0.10/call (Claude Sonnet)
    ULTRA = "ultra"                # > $0.10/call (Claude Opus)


# =============================================================================
# MODEL REGISTRY - Exact strings verified 2025-12-13
# =============================================================================

# Pricing is per 1M tokens (divide by 1,000,000 to get per-token cost)
OPENROUTER_MODELS = {
    # QWEN FAMILY - Primary Chinese VLM stack
    "qwen/qwen3-vl-30b-a3b-instruct": {
        "tier": ModelTier.COST_LEADER,
        "cost_per_1m_input": 0.22,  # $0.22 per 1M input tokens
        "cost_per_1m_output": 0.22,  # $0.22 per 1M output tokens
        "vision": True,
        "context_length": 32768,
        "avg_score": 5.9,  # 216-test audit winner
        "is_chinese_vlm": True,
    },
    "qwen/qwen2.5-vl-72b-instruct": {
        "tier": ModelTier.BUDGET,
        "cost_per_1m_input": 0.40,
        "cost_per_1m_output": 0.40,
        "vision": True,
        "context_length": 32768,
        "avg_score": 4.8,
        "is_chinese_vlm": True,
    },
    "qwen/qwen3-vl-8b-a3b-instruct": {
        "tier": ModelTier.BUDGET,
        "cost_per_1m_input": 0.12,
        "cost_per_1m_output": 0.12,
        "vision": True,
        "context_length": 32768,
        "is_chinese_vlm": True,
    },
    "qwen/qwen-vl-max": {
        "tier": ModelTier.COST_LEADER,
        "cost_per_1m_input": 0.73,
        "cost_per_1m_output": 0.73,
        "vision": True,
        "context_length": 32768,
        "avg_score": 5.5,  # High accuracy fallback
        "is_chinese_vlm": True,
    },
    # GLM FAMILY - Zhipu AI (Chart/Reference Specialist)
    "z-ai/glm-4.6v": {
        "tier": ModelTier.COST_LEADER,
        "cost_per_1m_input": 1.10,
        "cost_per_1m_output": 1.10,
        "vision": True,
        "context_length": 128000,
        "avg_score": 4.7,
        "specialty": "charts_and_pitch_tables",
        "is_chinese_vlm": True,
    },
}

# Anthropic pricing per 1M tokens (official pricing 2025-01)
ANTHROPIC_MODELS = {
    # Claude 4 Family - Premium Western Baseline
    "claude-sonnet-4-20250514": {
        "tier": ModelTier.PREMIUM,
        "cost_per_1m_input": 3.00,   # $3/1M input
        "cost_per_1m_output": 15.00,  # $15/1M output
        "vision": True,
        "context_length": 200000,
        "is_chinese_vlm": False,
    },
    "claude-opus-4-20250514": {
        "tier": ModelTier.ULTRA,
        "cost_per_1m_input": 15.00,  # $15/1M input
        "cost_per_1m_output": 75.00,  # $75/1M output
        "vision": True,
        "context_length": 200000,
        "is_chinese_vlm": False,
    },
    # Claude 3.5 Haiku - fastest/cheapest
    "claude-3-5-haiku-20241022": {
        "tier": ModelTier.STANDARD,
        "cost_per_1m_input": 1.00,   # $1/1M input
        "cost_per_1m_output": 5.00,   # $5/1M output
        "vision": True,
        "context_length": 200000,
        "is_chinese_vlm": False,
    },
}

GEMINI_MODELS = {
    # Gemini 2.0 Family
    "gemini-2.0-flash": {
        "tier": ModelTier.STANDARD,
        "cost_per_1m_input": 0.10,
        "cost_per_1m_output": 0.40,
        "vision": True,
        "context_length": 1000000,
        "is_chinese_vlm": False,
    },
    "gemini-2.0-flash-lite": {
        "tier": ModelTier.BUDGET,
        "cost_per_1m_input": 0.075,
        "cost_per_1m_output": 0.30,
        "vision": True,
        "context_length": 1000000,
        "is_chinese_vlm": False,
    },
    # Gemini 2.5 Family
    "gemini-2.5-flash": {
        "tier": ModelTier.STANDARD,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60,
        "vision": True,
        "context_length": 1000000,
        "is_chinese_vlm": False,
    },
    "gemini-2.5-pro": {
        "tier": ModelTier.PREMIUM,
        "cost_per_1m_input": 2.00,
        "cost_per_1m_output": 12.00,
        "vision": True,
        "context_length": 1000000,
        "is_chinese_vlm": False,
    },
    # Gemini 3.0 Family
    "gemini-3.0-flash": {
        "tier": ModelTier.STANDARD,
        "cost_per_1m_input": 0.15,
        "cost_per_1m_output": 0.60,
        "vision": True,
        "context_length": 1000000,
        "is_chinese_vlm": False,
    },
}

ALL_MODELS = {**OPENROUTER_MODELS, **ANTHROPIC_MODELS, **GEMINI_MODELS}


# =============================================================================
# AUDIT SCHEMA - Pydantic V2 Models
# =============================================================================

class AuditMetadata(BaseModel):
    """Metadata for each audit record."""
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0.0"
    repo_name: Literal["vlm-ai-core", "lang-core", "voice-ai-core"] = "vlm-ai-core"
    session_id: Optional[str] = None
    test_run_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    environment: Literal["development", "staging", "production", "test"] = "test"
    trade: Optional[str] = None  # hvac, electrical, plumbing, roofing, solar


class ModelInfo(BaseModel):
    """Model identification and capabilities."""
    provider: Provider
    model_name: str
    model_tier: ModelTier = ModelTier.STANDARD
    is_vision_model: bool = True
    is_chinese_vlm: bool = False  # Key for margin analysis
    context_length: int = 0


class TokenMetrics(BaseModel):
    """Token usage for cost calculation."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    image_tokens: int = 0  # Estimated tokens for image


class CostMetrics(BaseModel):
    """Cost tracking - critical for margin analysis."""
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    # Margin analysis fields
    cost_ceiling_usd: float = 0.05  # Max acceptable cost per call
    cost_alert_threshold_usd: float = 0.03
    cost_alert_triggered: bool = False

    # Comparison to Western baseline
    western_baseline_cost_usd: Optional[float] = None  # What Claude would cost
    cost_savings_usd: Optional[float] = None  # Savings vs Western
    cost_savings_percent: Optional[float] = None  # % savings

    # Projections for pro forma
    projected_cost_10k_calls: Optional[float] = None
    projected_cost_100k_calls: Optional[float] = None
    projected_cost_1m_calls: Optional[float] = None


class LatencyMetrics(BaseModel):
    """Latency tracking - secondary KPI."""
    total_latency_ms: int = 0
    ttft_ms: Optional[int] = None  # Time to first token

    # SLA targets (relaxed - speed is secondary)
    latency_p50_target_ms: int = 2000
    latency_p95_target_ms: int = 5000
    latency_p99_target_ms: int = 10000
    latency_sla_met: bool = True


class AccuracyMetrics(BaseModel):
    """Accuracy tracking - PRIMARY KPI for investor story."""
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Extraction quality
    fields_extracted: int = 0
    fields_expected: int = 0
    field_completion_rate: float = 0.0

    # Confidence scoring
    confidence_score: Optional[float] = None
    confidence_breakdown: Optional[dict[str, float]] = None

    # Human validation (post-hoc)
    accuracy_label: Literal[
        "correct", "partial", "hallucination", "failed", "pending_review"
    ] = "pending_review"
    human_verified: bool = False
    human_accuracy_score: Optional[float] = None  # 0-1 from human review

    # Comparison to Western baseline
    western_baseline_accuracy: Optional[float] = None
    accuracy_delta: Optional[float] = None  # Chinese VLM - Western


class OperationalMetrics(BaseModel):
    """Operational data for debugging."""
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_ts: Optional[datetime] = None
    retry_count: int = 0
    fallback_triggered: bool = False
    fallback_provider: Optional[str] = None
    fallback_reason: Optional[str] = None
    request_id: Optional[str] = None


class HashInfo(BaseModel):
    """Content hashes for deduplication."""
    input_hash: Optional[str] = None   # SHA-256 of input image
    output_hash: Optional[str] = None  # SHA-256 of output
    prompt_hash: Optional[str] = None  # SHA-256 of prompt


class AuditRecord(BaseModel):
    """
    Complete audit record for one provider call.

    This is the core data structure for:
    - Investor demos (cost comparison)
    - 3-year pro forma validation (margin story)
    - Quality assurance (accuracy parity)
    """
    metadata: AuditMetadata
    model: ModelInfo
    tokens: TokenMetrics = Field(default_factory=TokenMetrics)
    cost: CostMetrics = Field(default_factory=CostMetrics)
    latency: LatencyMetrics = Field(default_factory=LatencyMetrics)
    accuracy: AccuracyMetrics
    operational: OperationalMetrics = Field(default_factory=OperationalMetrics)
    hashes: HashInfo = Field(default_factory=HashInfo)

    # Raw response for debugging
    raw_response: Optional[dict[str, Any]] = None
    extracted_data: Optional[dict[str, Any]] = None

    # Custom fields per repo
    custom: dict[str, Any] = Field(default_factory=dict)

    def calculate_cost_savings(self, western_baseline_model: str = "claude-sonnet-4-20250514") -> None:
        """Calculate cost savings vs Western baseline."""
        if western_baseline_model in ANTHROPIC_MODELS:
            baseline = ANTHROPIC_MODELS[western_baseline_model]
            # Type-safe extraction using explicit dict key access
            # Model registry dicts are guaranteed to have these numeric keys
            input_price: float = 3.0  # Default Claude Sonnet input price
            output_price: float = 15.0  # Default Claude Sonnet output price
            if "cost_per_1m_input" in baseline:
                input_price = baseline["cost_per_1m_input"]  # type: ignore[assignment]
            if "cost_per_1m_output" in baseline:
                output_price = baseline["cost_per_1m_output"]  # type: ignore[assignment]
            baseline_cost: float = (
                (self.tokens.input_tokens / 1_000_000) * input_price +
                (self.tokens.output_tokens / 1_000_000) * output_price
            )
            self.cost.western_baseline_cost_usd = baseline_cost
            self.cost.cost_savings_usd = baseline_cost - self.cost.total_cost_usd
            if baseline_cost > 0:
                self.cost.cost_savings_percent = (
                    (baseline_cost - self.cost.total_cost_usd) / baseline_cost
                ) * 100

        # Calculate projections
        if self.cost.total_cost_usd > 0:
            self.cost.projected_cost_10k_calls = self.cost.total_cost_usd * 10_000
            self.cost.projected_cost_100k_calls = self.cost.total_cost_usd * 100_000
            self.cost.projected_cost_1m_calls = self.cost.total_cost_usd * 1_000_000

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten for CSV export."""
        flat = {}
        for section_name, section in self.model_dump().items():
            if isinstance(section, dict):
                for key, val in section.items():
                    if isinstance(val, dict):
                        # Skip nested dicts in flat export
                        flat[f"{section_name}_{key}"] = str(val)
                    else:
                        flat[f"{section_name}_{key}"] = val
            else:
                flat[section_name] = section
        return flat

    def summary(self) -> str:
        """Human-readable summary for gate reviews."""
        status = "✅" if self.accuracy.success else "❌"
        return f"""
{status} {self.model.provider.value}/{self.model.model_name}
├── Cost: ${self.cost.total_cost_usd:.6f} (Savings: {self.cost.cost_savings_percent or 0:.1f}%)
├── Tokens: {self.tokens.total_tokens} (in: {self.tokens.input_tokens}, out: {self.tokens.output_tokens})
├── Latency: {self.latency.total_latency_ms}ms
├── Accuracy: {self.accuracy.confidence_score or 0:.2f} confidence
├── Fields: {self.accuracy.fields_extracted}/{self.accuracy.fields_expected}
└── Trade: {self.metadata.trade or 'general'}
"""


# =============================================================================
# MARGIN ANALYSIS HELPERS
# =============================================================================

def calculate_margin_comparison(
    chinese_vlm_cost: float,
    western_cost: float,
    our_price_to_customer: float = 0.05
) -> dict[str, float]:
    """
    Calculate margin comparison for investor deck.

    Args:
        chinese_vlm_cost: Our cost using Qwen
        western_cost: What it would cost using Claude/Gemini
        our_price_to_customer: What we charge customers

    Returns:
        Margin analysis dict
    """
    chinese_margin = our_price_to_customer - chinese_vlm_cost
    western_margin = our_price_to_customer - western_cost

    return {
        "chinese_vlm_cost": chinese_vlm_cost,
        "western_cost": western_cost,
        "our_price": our_price_to_customer,
        "chinese_margin": chinese_margin,
        "western_margin": western_margin,
        "chinese_margin_percent": (chinese_margin / our_price_to_customer) * 100 if our_price_to_customer > 0 else 0,
        "western_margin_percent": (western_margin / our_price_to_customer) * 100 if our_price_to_customer > 0 else 0,
        "margin_improvement": chinese_margin - western_margin,
        "margin_improvement_percent": ((chinese_margin - western_margin) / western_margin) * 100 if western_margin != 0 else 0,
    }


def project_annual_costs(
    cost_per_call: float,
    monthly_volume: int = 100_000
) -> dict[str, float]:
    """
    Project annual costs for 3-year pro forma.

    Args:
        cost_per_call: Cost per VLM call
        monthly_volume: Expected monthly call volume

    Returns:
        Annual projections
    """
    annual_calls = monthly_volume * 12

    return {
        "monthly_volume": monthly_volume,
        "annual_calls": annual_calls,
        "year_1_cost": cost_per_call * annual_calls,
        "year_2_cost": cost_per_call * annual_calls * 1.5,  # 50% growth
        "year_3_cost": cost_per_call * annual_calls * 2.25,  # 50% YoY
        "total_3_year_cost": cost_per_call * annual_calls * (1 + 1.5 + 2.25),
    }
