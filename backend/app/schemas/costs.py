"""
Cost Reporting Pydantic Schemas

Response models for the cost reporting API endpoints.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# PROVIDER BREAKDOWN MODELS
# ============================================================================

class ProviderCostBreakdown(BaseModel):
    """Cost breakdown for a single provider"""

    provider: str = Field(..., description="Provider name (cerebras, openrouter, anthropic, etc.)")
    total_cost_usd: float = Field(..., description="Total cost for this provider in USD")
    total_requests: int = Field(..., description="Total number of API requests")
    percentage: float = Field(..., description="Percentage of total cost")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "provider": "cerebras",
                "total_cost_usd": 0.0024,
                "total_requests": 400,
                "percentage": 45.5
            }]
        }
    }


class CostTrendPoint(BaseModel):
    """Single point in cost trend time series"""

    date: str = Field(..., description="ISO 8601 date string")
    cost_usd: float = Field(..., description="Total cost for this date")
    requests: int = Field(..., description="Total requests for this date")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "date": "2025-01-08",
                "cost_usd": 0.0012,
                "requests": 200
            }]
        }
    }


# ============================================================================
# COST SUMMARY RESPONSE
# ============================================================================

class CostSummaryResponse(BaseModel):
    """Cost summary for specified time period"""

    total_cost_usd: float = Field(..., description="Total cost across all providers")
    total_requests: int = Field(..., description="Total API requests")
    avg_cost_per_request: float = Field(..., description="Average cost per request")
    provider_breakdown: List[ProviderCostBreakdown] = Field(..., description="Cost breakdown by provider")
    cost_trend: List[CostTrendPoint] = Field(..., description="Daily cost trend data")
    period_days: int = Field(..., description="Number of days in the reporting period")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "total_cost_usd": 0.0053,
                "total_requests": 880,
                "avg_cost_per_request": 0.000006,
                "provider_breakdown": [
                    {
                        "provider": "cerebras",
                        "total_cost_usd": 0.0024,
                        "total_requests": 400,
                        "percentage": 45.3
                    },
                    {
                        "provider": "anthropic",
                        "total_cost_usd": 0.0020,
                        "total_requests": 200,
                        "percentage": 37.7
                    }
                ],
                "cost_trend": [
                    {"date": "2025-01-08", "cost_usd": 0.0012, "requests": 200},
                    {"date": "2025-01-09", "cost_usd": 0.0018, "requests": 300}
                ],
                "period_days": 7
            }]
        }
    }


# ============================================================================
# COST BREAKDOWN RESPONSE
# ============================================================================

class CostBreakdownItem(BaseModel):
    """Single item in cost breakdown"""

    group_name: str = Field(..., description="Name of the group (provider, model, user, or operation)")
    total_cost_usd: float = Field(..., description="Total cost for this group")
    total_requests: int = Field(..., description="Total requests for this group")
    percentage_of_total: float = Field(..., description="Percentage of total cost")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "group_name": "llama3.1-8b",
                "total_cost_usd": 0.0024,
                "total_requests": 400,
                "percentage_of_total": 45.3
            }]
        }
    }


class CostBreakdownResponse(BaseModel):
    """Cost breakdown grouped by specified dimension"""

    group_by: str = Field(..., description="Grouping dimension (provider, model, user, operation)")
    breakdown: List[CostBreakdownItem] = Field(..., description="Cost breakdown items")
    total_cost_usd: float = Field(..., description="Total cost across all groups")
    total_requests: int = Field(..., description="Total requests across all groups")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "group_by": "model",
                "breakdown": [
                    {
                        "group_name": "llama3.1-8b",
                        "total_cost_usd": 0.0024,
                        "total_requests": 400,
                        "percentage_of_total": 45.3
                    },
                    {
                        "group_name": "claude-3-5-sonnet",
                        "total_cost_usd": 0.0020,
                        "total_requests": 200,
                        "percentage_of_total": 37.7
                    }
                ],
                "total_cost_usd": 0.0053,
                "total_requests": 880
            }]
        }
    }


# ============================================================================
# USAGE TIME SERIES RESPONSE
# ============================================================================

class UsageTimeSeriesPoint(BaseModel):
    """Single point in usage time series"""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    total_cost_usd: float = Field(..., description="Total cost for this time period")
    total_requests: int = Field(..., description="Total requests for this time period")
    avg_latency_ms: int = Field(..., description="Average latency in milliseconds")
    provider_costs: Dict[str, float] = Field(..., description="Cost breakdown by provider")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "timestamp": "2025-01-08T00:00:00Z",
                "total_cost_usd": 0.0012,
                "total_requests": 200,
                "avg_latency_ms": 650,
                "provider_costs": {
                    "cerebras": 0.0006,
                    "anthropic": 0.0006,
                    "openrouter": 0.0000
                }
            }]
        }
    }


class UsageTimeseriesResponse(BaseModel):
    """Time-series usage data for charting"""

    interval: str = Field(..., description="Time interval (hourly, daily, monthly)")
    data_points: List[UsageTimeSeriesPoint] = Field(..., description="Time series data points")
    start_date: str = Field(..., description="Start date of time series")
    end_date: str = Field(..., description="End date of time series")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "interval": "daily",
                "data_points": [
                    {
                        "timestamp": "2025-01-08T00:00:00Z",
                        "total_cost_usd": 0.0012,
                        "total_requests": 200,
                        "avg_latency_ms": 650,
                        "provider_costs": {
                            "cerebras": 0.0006,
                            "anthropic": 0.0006
                        }
                    }
                ],
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-08T00:00:00Z"
            }]
        }
    }


# ============================================================================
# BUDGET STATUS RESPONSE
# ============================================================================

class BudgetStatusResponse(BaseModel):
    """Current budget utilization status"""

    daily_budget_usd: float = Field(..., description="Daily budget limit in USD")
    daily_spend_usd: float = Field(..., description="Today's spend in USD")
    daily_utilization_percent: float = Field(..., description="Daily budget utilization percentage")

    monthly_budget_usd: float = Field(..., description="Monthly budget limit in USD")
    monthly_spend_usd: float = Field(..., description="Month-to-date spend in USD")
    monthly_utilization_percent: float = Field(..., description="Monthly budget utilization percentage")

    threshold_status: str = Field(..., description="Threshold status (OK, WARNING, CRITICAL, BLOCKED)")
    current_strategy: str = Field(default="standard", description="Current routing strategy")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "daily_budget_usd": 10.0,
                "daily_spend_usd": 0.0053,
                "daily_utilization_percent": 0.053,
                "monthly_budget_usd": 300.0,
                "monthly_spend_usd": 45.67,
                "monthly_utilization_percent": 15.22,
                "threshold_status": "OK",
                "current_strategy": "standard"
            }]
        }
    }


# ============================================================================
# EXPORT MODELS
# ============================================================================

class CostExportRecord(BaseModel):
    """Single record in cost export"""

    timestamp: str
    provider: str
    model: str
    operation_type: str
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    success: bool

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "timestamp": "2025-01-08T12:00:00Z",
                "provider": "cerebras",
                "model": "llama3.1-8b",
                "operation_type": "qualification",
                "cost_usd": 0.000006,
                "prompt_tokens": 150,
                "completion_tokens": 300,
                "latency_ms": 633,
                "success": True
            }]
        }
    }
