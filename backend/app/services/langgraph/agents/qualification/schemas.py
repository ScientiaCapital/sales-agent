"""Qualification schemas: Pydantic models and provider configuration."""
from typing import Optional, List
from pydantic import BaseModel, Field


class LeadQualificationResult(BaseModel):
    """
    Structured output schema for lead qualification.

    Enforced by with_structured_output() - guarantees this structure
    without manual JSON parsing or error handling.
    """
    qualification_score: float = Field(
        description="Qualification score from 0-100 based on company fit, contact quality, and sales potential"
    )

    qualification_reasoning: str = Field(
        description="2-3 sentence explanation covering fit, quality, and potential"
    )

    tier: str = Field(
        description="Qualification tier: 'hot' (80-100), 'warm' (60-79), 'cold' (40-59), or 'unqualified' (0-39)"
    )

    fit_assessment: str = Field(
        description="Company fit evaluation: size, industry alignment, market presence"
    )

    contact_quality: str = Field(
        description="Contact level and relevance: decision-maker assessment"
    )

    sales_potential: str = Field(
        description="Buying signals and readiness indicators"
    )

    recommendations: Optional[List[str]] = Field(
        default=None,
        description="2-4 actionable next steps for this lead (provide at least 2)"
    )


# Provider pricing (per million tokens, combined input+output for simplicity)
PROVIDER_PRICING = {
    "cerebras": {
        "llama-3.3-70b": 0.10,
        "llama3.1-70b": 0.60,
    },
    "claude": {
        "claude-3-haiku-20240307": 1.25,  # $0.25 in + $1.00 out
        "claude-3-5-sonnet-20241022": 4.50,  # $3.00 in + $15.00 out
    },
    "deepseek": {
        "deepseek-chat": 0.27,  # $0.14 in + $0.28 out (cache-enabled)
    },
    "ollama": {
        "*": 0.0  # Local inference, no cost
    }
}

__all__ = ["LeadQualificationResult", "PROVIDER_PRICING"]
