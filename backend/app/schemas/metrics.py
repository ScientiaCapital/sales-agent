"""
Pydantic schemas for metrics API endpoints.

Provides request/response models for querying and returning metrics data.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class MetricPoint(BaseModel):
    """Single time-series metric point."""

    timestamp: datetime = Field(description="Metric timestamp")
    value: float = Field(description="Metric value")
    count: int = Field(ge=0, description="Count of items")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-10-30T12:00:00Z",
                "value": 1250.5,
                "count": 42
            }
        }
    )


class AgentMetricResponse(BaseModel):
    """Agent execution metrics response."""

    agent_type: str = Field(description="Type of agent (qualification, enrichment, etc.)")
    date: datetime = Field(description="Date of metrics")
    total_executions: int = Field(ge=0, description="Total number of executions")
    successful_executions: int = Field(ge=0, description="Number of successful executions")
    failed_executions: int = Field(ge=0, description="Number of failed executions")
    avg_latency_ms: float = Field(description="Average execution latency in milliseconds")
    min_latency_ms: Optional[float] = Field(None, description="Minimum execution latency")
    max_latency_ms: Optional[float] = Field(None, description="Maximum execution latency")
    total_cost_usd: float = Field(description="Total cost in USD")
    avg_cost_usd: float = Field(description="Average cost per execution in USD")
    success_rate: float = Field(ge=0, le=1, description="Success rate (0-1)")

    model_config = ConfigDict(from_attributes=True)


class ProviderCostMetrics(BaseModel):
    """Cost metrics by AI provider."""

    provider: str = Field(description="AI provider (cerebras, claude, deepseek, ollama)")
    date: datetime = Field(description="Date of metrics")
    total_calls: int = Field(ge=0, description="Total API calls")
    total_tokens: int = Field(ge=0, description="Total tokens used")
    total_cost_usd: float = Field(description="Total cost in USD")
    avg_latency_ms: Optional[float] = Field(None, description="Average latency in milliseconds")

    model_config = ConfigDict(from_attributes=True)


class SystemMetricResponse(BaseModel):
    """System-level metric response."""

    metric_name: str = Field(description="Name of the metric")
    metric_value: float = Field(description="Metric value")
    metric_unit: str = Field(description="Unit of measurement (ms, %, count, etc.)")
    category: str = Field(description="Metric category (performance, error, resource, business)")
    recorded_at: datetime = Field(description="When metric was recorded")
    tags: Optional[Dict[str, Any]] = Field(None, description="Additional context tags")

    model_config = ConfigDict(from_attributes=True)


class MetricsSummaryResponse(BaseModel):
    """Comprehensive metrics summary for dashboard."""

    period_start: datetime = Field(description="Start of metrics period")
    period_end: datetime = Field(description="End of metrics period")

    # API Performance
    total_api_requests: int = Field(ge=0, description="Total API requests in period")
    avg_response_time_ms: float = Field(description="Average API response time")
    error_rate: float = Field(ge=0, le=1, description="API error rate (0-1)")

    # Agent Performance
    total_agent_executions: int = Field(ge=0, description="Total agent executions")
    agent_success_rate: float = Field(ge=0, le=1, description="Agent success rate (0-1)")
    avg_agent_latency_ms: float = Field(description="Average agent execution latency")

    # Cost Tracking
    total_cost_usd: float = Field(description="Total AI costs in period")
    cost_by_provider: Dict[str, float] = Field(description="Cost breakdown by provider")

    # Business Metrics
    leads_processed: int = Field(ge=0, description="Total leads processed")
    leads_qualified: int = Field(ge=0, description="Total leads qualified")
    qualification_rate: float = Field(ge=0, le=1, description="Qualification success rate")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period_start": "2025-10-23T00:00:00Z",
                "period_end": "2025-10-30T23:59:59Z",
                "total_api_requests": 15420,
                "avg_response_time_ms": 245.5,
                "error_rate": 0.02,
                "total_agent_executions": 8750,
                "agent_success_rate": 0.97,
                "avg_agent_latency_ms": 945.3,
                "total_cost_usd": 12.45,
                "cost_by_provider": {
                    "cerebras": 8.50,
                    "claude": 3.25,
                    "deepseek": 0.70
                },
                "leads_processed": 1250,
                "leads_qualified": 875,
                "qualification_rate": 0.70
            }
        }
    )


class EndpointMetricResponse(BaseModel):
    """API endpoint performance metrics."""

    endpoint_path: str = Field(description="API endpoint path")
    method: str = Field(description="HTTP method")
    date: datetime = Field(description="Date of metrics")
    total_requests: int = Field(ge=0, description="Total requests")
    avg_response_time_ms: float = Field(description="Average response time")
    p50_response_time_ms: Optional[float] = Field(None, description="50th percentile response time")
    p95_response_time_ms: Optional[float] = Field(None, description="95th percentile response time")
    p99_response_time_ms: Optional[float] = Field(None, description="99th percentile response time")
    error_count: int = Field(ge=0, description="Number of errors")
    error_rate: float = Field(ge=0, le=1, description="Error rate (0-1)")

    model_config = ConfigDict(from_attributes=True)
