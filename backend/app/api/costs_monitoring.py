"""
Cost Monitoring API - Real-time AI Cost Tracking

Provides endpoints for monitoring AI costs across multiple providers
with the Unified Claude SDK integration.

Endpoints:
- GET /api/costs/ai - Current AI costs and usage statistics
- GET /api/costs/ai/breakdown - Cost breakdown by provider
- GET /api/costs/ai/savings - Savings analysis vs Claude-only
- GET /api/costs/ai/recommendations - Cost optimization recommendations
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/costs", tags=["costs"])


# ========== Models ==========

class AICostStats(BaseModel):
    """AI cost statistics."""
    total_requests: int
    total_cost_usd: float
    average_cost_per_request: float
    provider_breakdown: Dict[str, Dict[str, Any]]
    time_range: str
    last_updated: datetime


class ProviderStats(BaseModel):
    """Statistics for a single provider."""
    provider_name: str
    requests: int
    total_cost: float
    total_tokens: int
    average_cost_per_request: float
    percentage_of_total_requests: float


class SavingsAnalysis(BaseModel):
    """Cost savings analysis."""
    current_cost: float
    claude_only_cost: float
    savings_amount: float
    savings_percentage: float
    deepseek_usage_percentage: float
    recommendations: List[str]


class CostRecommendation(BaseModel):
    """Cost optimization recommendation."""
    recommendation: str
    potential_savings_usd: float
    potential_savings_percentage: float
    priority: str  # high, medium, low
    action: str


# ========== API Endpoints ==========

@router.get("/ai", response_model=AICostStats)
async def get_ai_costs(
    time_range: str = Query("24h", description="Time range: 1h, 24h, 7d, 30d")
) -> AICostStats:
    """
    Get current AI costs and usage statistics.

    Returns real-time statistics from the Unified Claude SDK including:
    - Total requests and costs
    - Provider breakdown (Anthropic vs DeepSeek)
    - Average costs
    - Token usage
    """
    try:
        # Import here to avoid startup errors if dependencies missing
        from app.services.unified_claude_sdk import get_unified_claude_client

        # Get unified client stats
        client = await get_unified_claude_client()
        stats = client.get_stats()

        # Format response
        return AICostStats(
            total_requests=stats["total"]["requests"],
            total_cost_usd=stats["total"]["cost_usd"],
            average_cost_per_request=stats["total"]["average_cost_per_request"],
            provider_breakdown=stats["providers"],
            time_range=time_range,
            last_updated=datetime.now()
        )

    except Exception as e:
        logger.error(f"Failed to get AI costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/breakdown", response_model=List[ProviderStats])
async def get_cost_breakdown() -> List[ProviderStats]:
    """
    Get detailed cost breakdown by provider.

    Returns granular statistics for each AI provider:
    - Anthropic Claude (premium quality)
    - DeepSeek (cost-optimized)
    """
    try:
        from app.services.unified_claude_sdk import get_unified_claude_client

        client = await get_unified_claude_client()
        stats = client.get_stats()

        total_requests = stats["total"]["requests"]
        breakdown = []

        for provider_name, provider_stats in stats["providers"].items():
            requests = provider_stats["requests"]
            percentage = (requests / total_requests * 100) if total_requests > 0 else 0

            breakdown.append(ProviderStats(
                provider_name=provider_name.value if hasattr(provider_name, 'value') else str(provider_name),
                requests=requests,
                total_cost=provider_stats["total_cost"],
                total_tokens=provider_stats["total_tokens"],
                average_cost_per_request=provider_stats["total_cost"] / max(requests, 1),
                percentage_of_total_requests=round(percentage, 2)
            ))

        return breakdown

    except Exception as e:
        logger.error(f"Failed to get cost breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/savings", response_model=SavingsAnalysis)
async def get_savings_analysis() -> SavingsAnalysis:
    """
    Analyze cost savings vs Claude-only approach.

    Calculates how much money was saved by using intelligent routing
    between DeepSeek (cheap) and Claude (quality) instead of using
    Claude for everything.
    """
    try:
        from app.services.unified_claude_sdk import get_unified_claude_client, Provider

        client = await get_unified_claude_client()
        stats = client.get_stats()

        # Current cost
        current_cost = stats["total"]["cost_usd"]
        total_requests = stats["total"]["requests"]

        # Calculate what it would have cost with Claude only
        anthropic_config = client.providers[Provider.ANTHROPIC]
        deepseek_stats = stats["providers"].get(Provider.DEEPSEEK, {"total_tokens": 0})
        deepseek_tokens = deepseek_stats.get("total_tokens", 0)

        # Estimate Claude cost for DeepSeek requests (assuming similar token distribution)
        # Average token split: 60% input, 40% output
        estimated_input_tokens = deepseek_tokens * 0.6
        estimated_output_tokens = deepseek_tokens * 0.4

        claude_only_cost_for_deepseek = (
            (estimated_input_tokens / 1_000_000) * anthropic_config.cost_per_1m_input +
            (estimated_output_tokens / 1_000_000) * anthropic_config.cost_per_1m_output
        )

        claude_only_total_cost = current_cost + claude_only_cost_for_deepseek

        # Calculate savings
        savings_amount = claude_only_total_cost - current_cost
        savings_percentage = (savings_amount / claude_only_total_cost * 100) if claude_only_total_cost > 0 else 0

        # DeepSeek usage percentage
        deepseek_requests = stats["providers"].get(Provider.DEEPSEEK, {}).get("requests", 0)
        deepseek_usage_pct = (deepseek_requests / total_requests * 100) if total_requests > 0 else 0

        # Generate recommendations
        recommendations = []
        if deepseek_usage_pct < 50:
            recommendations.append("Increase DeepSeek usage for simple tasks to save more")
        if deepseek_usage_pct > 80:
            recommendations.append("Consider using Claude for more complex tasks to improve quality")
        if total_requests > 100:
            recommendations.append("Enable prompt caching for 90% additional savings on repeated prompts")

        return SavingsAnalysis(
            current_cost=round(current_cost, 6),
            claude_only_cost=round(claude_only_total_cost, 6),
            savings_amount=round(savings_amount, 6),
            savings_percentage=round(savings_percentage, 2),
            deepseek_usage_percentage=round(deepseek_usage_pct, 2),
            recommendations=recommendations
        )

    except Exception as e:
        logger.error(f"Failed to analyze savings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/recommendations", response_model=List[CostRecommendation])
async def get_cost_recommendations() -> List[CostRecommendation]:
    """
    Get AI cost optimization recommendations.

    Analyzes current usage patterns and provides actionable recommendations
    to reduce costs while maintaining quality.
    """
    try:
        from app.services.unified_claude_sdk import get_unified_claude_client, Provider

        client = await get_unified_claude_client()
        stats = client.get_stats()

        recommendations = []
        total_requests = stats["total"]["requests"]
        current_cost = stats["total"]["cost_usd"]

        # Recommendation 1: Increase DeepSeek usage
        deepseek_requests = stats["providers"].get(Provider.DEEPSEEK, {}).get("requests", 0)
        deepseek_pct = (deepseek_requests / total_requests * 100) if total_requests > 0 else 0

        if deepseek_pct < 60 and total_requests > 50:
            potential_savings = current_cost * 0.3  # 30% potential savings
            recommendations.append(CostRecommendation(
                recommendation="Route more simple tasks to DeepSeek",
                potential_savings_usd=round(potential_savings, 6),
                potential_savings_percentage=30.0,
                priority="high",
                action="Review task complexity detection and lower thresholds for DeepSeek routing"
            ))

        # Recommendation 2: Enable prompt caching
        if total_requests > 100:
            potential_savings = current_cost * 0.5  # 50% potential savings with caching
            recommendations.append(CostRecommendation(
                recommendation="Enable prompt caching for repeated system prompts",
                potential_savings_usd=round(potential_savings, 6),
                potential_savings_percentage=50.0,
                priority="high",
                action="Set enable_caching=True for requests with identical system prompts"
            ))

        # Recommendation 3: Batch processing
        if total_requests > 500:
            potential_savings = current_cost * 0.15  # 15% savings from batching
            recommendations.append(CostRecommendation(
                recommendation="Implement batch processing for similar requests",
                potential_savings_usd=round(potential_savings, 6),
                potential_savings_percentage=15.0,
                priority="medium",
                action="Group similar requests and process together to reduce overhead"
            ))

        # Recommendation 4: Use Haiku for faster tasks
        anthropic_requests = stats["providers"].get(Provider.ANTHROPIC, {}).get("requests", 0)
        if anthropic_requests > 50:
            potential_savings = current_cost * 0.2  # 20% savings with Haiku
            recommendations.append(CostRecommendation(
                recommendation="Use Claude Haiku for non-critical tasks",
                potential_savings_usd=round(potential_savings, 6),
                potential_savings_percentage=20.0,
                priority="medium",
                action="Switch to claude-3-5-haiku-20241022 for speed-critical, quality-flexible tasks"
            ))

        # Default recommendation if everything looks good
        if not recommendations:
            recommendations.append(CostRecommendation(
                recommendation="Usage patterns are well-optimized",
                potential_savings_usd=0.0,
                potential_savings_percentage=0.0,
                priority="low",
                action="Continue monitoring for optimization opportunities"
            ))

        return recommendations

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/reset-stats")
async def reset_statistics():
    """
    Reset AI cost statistics.

    WARNING: This will clear all accumulated statistics.
    Use with caution.
    """
    try:
        from app.services.unified_claude_sdk import get_unified_claude_client, Provider

        client = await get_unified_claude_client()

        # Reset stats
        client.stats = {
            Provider.ANTHROPIC: {"requests": 0, "total_cost": 0.0, "total_tokens": 0},
            Provider.DEEPSEEK: {"requests": 0, "total_cost": 0.0, "total_tokens": 0}
        }

        return {
            "status": "success",
            "message": "Statistics reset successfully",
            "timestamp": datetime.now()
        }

    except Exception as e:
        logger.error(f"Failed to reset statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/health")
async def check_provider_health():
    """
    Check health of all AI providers.

    Returns availability status for Anthropic and DeepSeek.
    """
    try:
        from app.services.unified_claude_sdk import get_unified_claude_client

        client = await get_unified_claude_client()
        health = await client.health_check()

        return {
            "status": "healthy" if all(health.values()) else "degraded",
            "providers": health,
            "timestamp": datetime.now()
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now()
        }
