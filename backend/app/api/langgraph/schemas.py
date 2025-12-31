"""LangGraph API schemas - Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


# ========== Core Agent Schemas ==========

class InvokeAgentRequest(BaseModel):
    """Request schema for invoking a LangGraph agent."""

    agent_type: str = Field(
        ...,
        description="Agent type: qualification, enrichment, growth, marketing, bdr, conversation"
    )
    input: Dict[str, Any] = Field(
        ...,
        description="Input data matching the agent's state schema"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for conversation continuity (auto-generated if not provided)"
    )
    lead_id: Optional[int] = Field(
        default=None,
        description="Lead ID to associate with this agent execution"
    )
    stream_mode: str = Field(
        default="values",
        description="Streaming mode: messages, updates, values, custom"
    )
    provider: Optional[str] = Field(
        default="cerebras",
        description="LLM provider: cerebras, claude, deepseek, ollama"
    )
    model: Optional[str] = Field(
        default=None,
        description="Model ID (auto-selects if None)"
    )


class AgentResponse(BaseModel):
    """Response schema for agent invocation."""

    status: str = Field(description="Status: success, error, pending")
    agent_type: str = Field(description="Type of agent that was invoked")
    thread_id: str = Field(description="Thread ID for conversation continuity")
    output: Dict[str, Any] = Field(description="Agent output state")
    metadata: Dict[str, Any] = Field(description="Execution metadata")
    timestamp: str = Field(description="ISO 8601 timestamp of completion")


class StateResponse(BaseModel):
    """Response schema for checkpoint state retrieval."""

    thread_id: str = Field(description="Thread ID")
    checkpoint_exists: bool = Field(description="Whether a checkpoint was found")
    state: Optional[Dict[str, Any]] = Field(description="Checkpoint state data")
    metadata: Optional[Dict[str, Any]] = Field(description="Checkpoint metadata")


# ========== Scout Schemas ==========

class ScoutRunRequest(BaseModel):
    """Request schema for triggering a scout run."""
    limit: int = Field(default=10, description="Number of leads to scout (1-50)")
    require_domain: bool = Field(default=True, description="Only scout leads with website domains")
    icp_tier: Optional[str] = Field(default=None, description="Filter by ICP tier")
    async_mode: bool = Field(default=False, description="Run via Celery task")


class ScoutResultItem(BaseModel):
    """Single scout result item."""
    company_id: str
    company_name: str
    domain: Optional[str]
    icp_score: float
    priority: str
    why_call: str
    scouted_at: str


class ScoutRunResponse(BaseModel):
    """Response for scout run."""
    status: str
    task_id: Optional[str] = None
    total_scouted: Optional[int] = None
    hot_leads: Optional[int] = None
    warm_leads: Optional[int] = None
    cold_leads: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


# ========== Report Schemas ==========

class ReportRunRequest(BaseModel):
    """Request schema for generating a morning report."""
    hours_back: int = Field(default=24, description="Hours to look back")
    top_n: int = Field(default=10, description="Number of top leads")
    save_to_file: bool = Field(default=True, description="Save report to file")
    async_mode: bool = Field(default=False, description="Run via Celery task")


class ReportRunResponse(BaseModel):
    """Response for morning report generation."""
    status: str
    task_id: Optional[str] = None
    generated_at: Optional[str] = None
    report_date: Optional[str] = None
    total_scouted: Optional[int] = None
    hot_leads: Optional[int] = None
    warm_leads: Optional[int] = None
    cold_leads: Optional[int] = None
    top_leads_count: Optional[int] = None
    signals_summary: Optional[dict] = None
    summary: Optional[str] = None
    file_path: Optional[str] = None


# ========== Sales Intel Schemas ==========

class SalesIntelRunRequest(BaseModel):
    """Request schema for running SalesIntel analysis."""
    limit: int = Field(default=10, description="Number of leads to analyze (1-50)")
    async_mode: bool = Field(default=False, description="Run via Celery task")


class SalesIntelRunResponse(BaseModel):
    """Response for SalesIntel run."""
    status: str
    task_id: Optional[str] = None
    leads_processed: Optional[int] = None
    hooks_extracted: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


# ========== Growth Campaign Schemas ==========

class GrowthCampaignRequest(BaseModel):
    """Request schema for running growth campaigns."""
    goal: str = Field(default="book_meeting", description="Campaign goal")
    max_leads: int = Field(default=5, description="Maximum leads (1-20)")
    max_cycles: int = Field(default=5, description="Maximum optimization cycles (1-10)")
    async_mode: bool = Field(default=False, description="Run via Celery task")


class GrowthCampaignResponse(BaseModel):
    """Response for growth campaign run."""
    status: str
    task_id: Optional[str] = None
    campaigns_run: Optional[int] = None
    goals_met: Optional[int] = None
    total_cycles: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


# ========== BDR Outreach Schemas ==========

class BDRRunRequest(BaseModel):
    """Request schema for running BDR outreach."""
    company_id: Optional[str] = Field(default=None, description="UUID of target company")
    limit: int = Field(default=3, description="Number of leads in batch (1-10)")
    async_mode: bool = Field(default=True, description="Run via Celery task")


class BDRRunResponse(BaseModel):
    """Response for BDR outreach."""
    status: str
    task_id: Optional[str] = None
    draft_id: Optional[str] = None
    company_name: Optional[str] = None
    leads_queued: Optional[int] = None
    message: Optional[str] = None


class BDRApprovalRequest(BaseModel):
    """Request schema for approving/rejecting a BDR draft."""
    draft_id: str = Field(..., description="UUID of the draft")
    action: str = Field(..., description="Action: approve, reject, revise")
    feedback: Optional[str] = Field(default=None, description="Feedback for revision")
    approved_by: Optional[str] = Field(default="API", description="Name of approver")
