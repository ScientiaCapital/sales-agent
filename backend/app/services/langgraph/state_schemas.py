"""
LangGraph Agent State Schemas

Defines TypedDict state schemas for all LangGraph agents in the sales-agent platform.
Each agent has a dedicated state schema with agent-specific fields and common patterns.

State Design Patterns:
- messages: Annotated[list[BaseMessage], add_messages] for conversation history
- agent_type: Identifies which agent is running
- lead_id: Optional reference to the lead being processed
- metadata: Flexible storage for agent-specific data
- Reducers: Use operator.add or add_messages for concurrent updates
"""

from typing import Optional, Any, List, Dict, Annotated
from typing_extensions import TypedDict
from operator import add

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ========== Base State Schema ==========

class BaseAgentState(TypedDict, total=False):
    """
    Base state schema with common fields across all agents.

    Note: total=False allows optional fields while maintaining type safety.
    """
    # Message history with automatic append reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str

    # Lead reference
    lead_id: Optional[int]

    # Flexible metadata storage
    metadata: Dict[str, Any]


# ========== Qualification Agent (Simple LCEL Chain) ==========

class QualificationAgentState(TypedDict):
    """
    State for QualificationAgent (simple LCEL chain).

    Flow: Input → Cerebras LLM → Structured Output
    Uses: Lead qualification with AI scoring
    """
    # Message history for LLM conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str

    # Input: Lead data
    lead_id: Optional[int]
    company_name: str
    company_website: Optional[str]
    company_size: Optional[str]
    industry: Optional[str]
    contact_name: Optional[str]
    contact_title: Optional[str]
    notes: Optional[str]

    # Output: Qualification results
    qualification_score: Optional[float]  # 0-100 score
    qualification_reasoning: Optional[str]  # AI reasoning
    tier: Optional[str]  # hot, warm, cold, unqualified
    recommendations: Optional[List[str]]  # Action items

    # Metadata
    metadata: Dict[str, Any]  # {model, latency_ms, cost_usd, etc.}


# ========== Enrichment Agent (LCEL Chain with Tools) ==========

class EnrichmentAgentState(TypedDict):
    """
    State for EnrichmentAgent (LCEL chain with tool calling).

    Flow: Input → LLM decides tools → Tools execute → LLM synthesizes
    Uses: Apollo enrichment, LinkedIn scraping, document analysis
    """
    # Message history with tool calls
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str
    lead_id: Optional[int]

    # Input: Contact to enrich
    email: Optional[str]
    linkedin_url: Optional[str]
    company_name: Optional[str]

    # Output: Enriched data from multiple sources
    enriched_data: Dict[str, Any]  # Combined data from all sources
    data_sources: Annotated[List[str], add]  # Sources used: apollo, linkedin, etc.
    confidence_score: Optional[float]  # 0-1 confidence in enrichment quality

    # Tool execution tracking
    tools_called: Annotated[List[str], add]  # Tool names executed
    tool_results: Dict[str, Any]  # Raw results from each tool

    # Metadata
    metadata: Dict[str, Any]


# ========== Growth Agent (Cyclic StateGraph) ==========

class GrowthAgentState(TypedDict):
    """
    State for GrowthAgent (cyclic graph with feedback loops).

    Flow: Analyze → Strategize → Execute → Measure → Loop (until goal met)
    Uses: Multi-touch outreach campaigns with iterative refinement
    """
    # Message history
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str
    lead_id: Optional[int]

    # Cycle tracking
    cycle_count: int  # Number of strategy iterations
    max_cycles: int  # Maximum iterations before termination
    goal_met: bool  # Termination condition

    # Strategy data
    current_strategy: Optional[str]  # Current outreach strategy
    outreach_plan: Dict[str, Any]  # Multi-touch sequence plan
    executed_touches: Annotated[List[Dict[str, Any]], add]  # Completed outreach actions

    # Performance metrics
    response_rate: Optional[float]  # Email response rate
    engagement_score: Optional[float]  # Overall engagement metric
    next_action: Optional[str]  # Recommended next step

    # Feedback for next cycle
    learnings: Annotated[List[str], add]  # Insights from previous cycles

    # Metadata
    metadata: Dict[str, Any]


# ========== Marketing Agent (Parallel Execution StateGraph) ==========

class MarketingAgentState(TypedDict):
    """
    State for MarketingAgent (parallel execution graph).

    Flow: brief → [email | linkedin | social | blog] in parallel → aggregate
    Uses: Multi-channel content generation with cost-optimized LLM selection
    """
    # Input: Campaign parameters
    campaign_brief: str
    target_audience: str
    campaign_goals: List[str]

    # Parallel execution results
    email_content: Optional[str]
    linkedin_content: Optional[str]
    social_content: Optional[str]
    blog_content: Optional[str]

    # Aggregated metadata (use add reducer for concurrent updates)
    generation_metadata: Annotated[Dict[str, Any], add]

    # Aggregation results
    total_cost_usd: Optional[float]
    recommended_schedule: Optional[Dict[str, str]]
    content_quality_score: Optional[float]


# ========== BDR Agent (Human-in-Loop StateGraph) ==========

class BDRAgentState(TypedDict):
    """
    State for BDRAgent (human-in-loop graph with approval gates).

    Flow: Research → Draft → [Approval Gate] → Send → Follow-up
    Uses: High-value outreach with human review before sending
    """
    # Message history
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str
    lead_id: int  # Required for BDR workflows

    # Workflow state
    current_stage: str  # research, draft, approval_pending, approved, sent
    needs_approval: bool  # Approval gate flag
    approved_by: Optional[str]  # User who approved
    approval_timestamp: Optional[str]

    # Research phase
    research_summary: Optional[str]  # Company/contact research
    talking_points: Annotated[List[str], add]  # Key points for outreach

    # Draft phase
    draft_subject: Optional[str]  # Email subject line
    draft_body: Optional[str]  # Email body content
    draft_version: int  # Iteration count

    # Approval phase
    approval_notes: Optional[str]  # Feedback from human reviewer
    revision_requests: Annotated[List[str], add]  # Change requests

    # Execution phase
    sent_at: Optional[str]  # Timestamp when sent
    delivery_status: Optional[str]  # delivered, bounced, opened

    # Follow-up tracking
    follow_up_scheduled: bool
    follow_up_date: Optional[str]

    # Metadata
    metadata: Dict[str, Any]


# ========== Conversation Agent (Voice-Enabled StateGraph) ==========

class ConversationAgentState(TypedDict):
    """
    State for ConversationAgent (voice-enabled graph with Cartesia TTS).

    Flow: STT → LLM → TTS → Audio Playback (cyclic conversation)
    Uses: Real-time voice conversations with leads
    """
    # Message history (voice transcripts)
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent identification
    agent_type: str
    lead_id: Optional[int]
    call_id: str  # Unique call session ID

    # Voice context
    caller_name: Optional[str]
    caller_phone: Optional[str]
    call_purpose: str  # qualification, demo, support

    # Conversation state
    conversation_stage: str  # greeting, discovery, presentation, closing
    is_active: bool  # Call in progress
    call_duration_seconds: int

    # Audio processing
    audio_files: Annotated[List[str], add]  # File paths to generated TTS audio
    transcripts: Annotated[List[Dict[str, str]], add]  # {speaker, text, timestamp}

    # Voice configuration
    voice_id: Optional[str]  # Cartesia voice ID
    voice_emotion: str  # neutral, professional, empathetic
    voice_speed: str  # normal, fast, slow

    # Conversation analysis
    sentiment: Optional[str]  # positive, neutral, negative
    intent: Optional[str]  # buy, learn, object, end
    objections: Annotated[List[str], add]  # Detected objections

    # Call outcome
    call_result: Optional[str]  # scheduled_meeting, not_interested, callback
    next_steps: Optional[List[str]]  # Action items

    # Metadata
    metadata: Dict[str, Any]  # {tts_latency_ms, llm_latency_ms, total_cost_usd}


# ========== Common State Utilities ==========

def create_initial_state(
    agent_type: str,
    **kwargs
) -> BaseAgentState:
    """
    Create initial state for any agent with common defaults.

    Args:
        agent_type: Type of agent (qualification, enrichment, etc.)
        **kwargs: Agent-specific initial values

    Returns:
        Initial state dict with defaults

    Example:
        >>> initial = create_initial_state(
        ...     agent_type="qualification",
        ...     company_name="Acme Corp",
        ...     industry="SaaS"
        ... )
    """
    return {
        "messages": [],
        "agent_type": agent_type,
        "metadata": {},
        **kwargs
    }


def get_latest_message(state: BaseAgentState) -> Optional[BaseMessage]:
    """
    Get the most recent message from state.

    Args:
        state: Agent state with messages

    Returns:
        Latest message or None if no messages
    """
    messages = state.get("messages", [])
    return messages[-1] if messages else None


def get_messages_by_role(
    state: BaseAgentState,
    role: str
) -> List[BaseMessage]:
    """
    Filter messages by role (user, assistant, system, tool).

    Args:
        state: Agent state with messages
        role: Message role to filter

    Returns:
        List of messages with matching role
    """
    messages = state.get("messages", [])
    return [msg for msg in messages if getattr(msg, "role", None) == role]


# ========== Type Exports ==========

__all__ = [
    # Base
    "BaseAgentState",

    # Agent States
    "QualificationAgentState",
    "EnrichmentAgentState",
    "GrowthAgentState",
    "MarketingAgentState",
    "BDRAgentState",
    "ConversationAgentState",

    # Utilities
    "create_initial_state",
    "get_latest_message",
    "get_messages_by_role",
]
