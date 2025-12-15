"""
Scientia Capital Agent Schema
Strict-Typed Agentic AI Infrastructure

Architecture:
- Orchestrator (Opus/Sonnet): Planning, reasoning, synthesis
- Extractors (Qwen VL): Vision extraction, cheap parallel workers
- Reasoners (DeepSeek): JSON validation, structured reasoning

DeepSeek Note: Only TEXT models on OpenRouter (no VL).
Vision: Qwen VL | JSON Reasoning: DeepSeek | Complex Reasoning: Sonnet
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# AGENT ROLES & STATE
# =============================================================================

class AgentRole(str, Enum):
    """Agent roles in the MEP orchestration pipeline."""

    # Orchestrator - Plans, coordinates, synthesizes (Opus/Sonnet)
    ORCHESTRATOR = "orchestrator"

    # Extractors - Cheap parallel workers for vision (Qwen VL)
    VLM_EXTRACTOR = "vlm_extractor"

    # Reasoners - JSON validation, structured output (DeepSeek)
    JSON_REASONER = "json_reasoner"

    # Validators - Quality checks, schema validation
    VALIDATOR = "validator"

    # Synthesizers - Combine results, generate reports
    SYNTHESIZER = "synthesizer"


class AgentState(str, Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_FOR_TOOL = "waiting_for_tool"
    PROCESSING_RESULT = "processing_result"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    ERROR = "error"


class ModelConfig(BaseModel):
    """Model configuration for an agent."""
    provider: Literal["openrouter", "anthropic", "deepseek"] = "openrouter"
    model_name: str
    temperature: float = 0.0
    max_tokens: int = 4096

    # Cost tracking
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0

    # Capabilities
    supports_vision: bool = False
    supports_json_mode: bool = True
    context_length: int = 32768


# Preconfigured model configs
MODELS = {
    # Orchestrators (smart, expensive)
    "claude-sonnet-4": ModelConfig(
        provider="anthropic",
        model_name="claude-sonnet-4-20250514",
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        supports_vision=True,
        context_length=200000,
    ),
    "claude-opus-4": ModelConfig(
        provider="anthropic",
        model_name="claude-opus-4-20250514",
        cost_per_1m_input=15.0,
        cost_per_1m_output=75.0,
        supports_vision=True,
        context_length=200000,
    ),

    # VLM Extractors (cheap vision)
    "qwen-vl-72b": ModelConfig(
        provider="openrouter",
        model_name="qwen/qwen2.5-vl-72b-instruct",
        cost_per_1m_input=0.40,
        cost_per_1m_output=0.40,
        supports_vision=True,
        context_length=32768,
    ),
    "qwen-vl-30b": ModelConfig(
        provider="openrouter",
        model_name="qwen/qwen3-vl-30b-a3b-instruct",
        cost_per_1m_input=0.22,
        cost_per_1m_output=0.22,
        supports_vision=True,
        context_length=32768,
    ),

    # JSON Reasoners (DeepSeek - text only, cheapest)
    "deepseek-chat": ModelConfig(
        provider="openrouter",
        model_name="deepseek/deepseek-chat",
        cost_per_1m_input=0.21,
        cost_per_1m_output=0.79,
        supports_vision=False,
        supports_json_mode=True,
        context_length=64000,
    ),
    "deepseek-chat-v3": ModelConfig(
        provider="openrouter",
        model_name="deepseek/deepseek-chat-v3-0324",
        cost_per_1m_input=0.21,
        cost_per_1m_output=0.79,
        supports_vision=False,
        supports_json_mode=True,
        context_length=64000,
    ),
}


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

T = TypeVar("T")


class ToolParameter(BaseModel):
    """Single parameter definition for a tool."""
    name: str
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[str]] = None


class Tool(BaseModel):
    """Tool definition for agent use."""
    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)

    # Execution metadata
    requires_vision: bool = False
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: int = 0

    # Model routing
    preferred_model: Optional[str] = None  # Key from MODELS dict

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolCall(BaseModel):
    """Tool invocation request from an agent."""
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    # Execution context
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    agent_id: Optional[str] = None

    # Cost estimation
    estimated_cost_usd: float = 0.0


class ToolResult(BaseModel, Generic[T]):
    """Result from tool execution."""
    tool_call_id: str
    tool_name: str

    # Result data
    success: bool
    result: Optional[T] = None
    error: Optional[str] = None

    # Execution metrics
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: int = 0
    cost_usd: float = 0.0

    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0


# =============================================================================
# MESSAGE TYPES
# =============================================================================

class MessageRole(str, Enum):
    """Message role in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """Message in agent conversation."""
    role: MessageRole
    content: str

    # Tool-related fields
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None  # For tool response messages

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model: Optional[str] = None

    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

class AgentConfig(BaseModel):
    """Configuration for an agent instance."""
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    role: AgentRole

    # Model configuration
    model_config_key: str  # Key from MODELS dict

    # System prompt
    system_prompt: str

    # Available tools
    tools: list[Tool] = Field(default_factory=list)

    # Execution limits
    max_iterations: int = 10
    max_tool_calls_per_turn: int = 5
    timeout_seconds: int = 300

    # Cost limits
    max_cost_per_run_usd: float = 1.0
    cost_alert_threshold_usd: float = 0.50

    # Behavior settings
    verbose: bool = False
    trace_enabled: bool = True  # For LangSmith

    def get_model_config(self) -> ModelConfig:
        """Get the model configuration for this agent."""
        if self.model_config_key not in MODELS:
            raise ValueError(f"Unknown model: {self.model_config_key}")
        return MODELS[self.model_config_key]


# =============================================================================
# AGENT RUN STATE
# =============================================================================

class AgentRun(BaseModel):
    """State for a single agent run."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_config: AgentConfig

    # State machine
    state: AgentState = AgentState.IDLE
    iteration: int = 0

    # Conversation history
    messages: list[Message] = Field(default_factory=list)

    # Pending tool calls
    pending_tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult[Any]] = Field(default_factory=list)

    # Metrics
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Error tracking
    errors: list[str] = Field(default_factory=list)

    def add_message(self, message: Message) -> None:
        """Add message and update metrics."""
        self.messages.append(message)
        self.total_tokens += message.input_tokens + message.output_tokens
        self.total_cost_usd += message.cost_usd

    def add_tool_result(self, result: ToolResult[Any]) -> None:
        """Add tool result and update metrics."""
        self.tool_results.append(result)
        self.total_tokens += result.input_tokens + result.output_tokens
        self.total_cost_usd += result.cost_usd

    def check_limits(self) -> tuple[bool, Optional[str]]:
        """Check if run has exceeded any limits."""
        config = self.agent_config

        if self.iteration >= config.max_iterations:
            return False, f"Exceeded max iterations: {config.max_iterations}"

        if self.total_cost_usd >= config.max_cost_per_run_usd:
            return False, f"Exceeded cost limit: ${config.max_cost_per_run_usd}"

        return True, None


# =============================================================================
# ORCHESTRATION TYPES
# =============================================================================

class TaskType(str, Enum):
    """Types of tasks in MEP workflow."""
    EXTRACT_IMAGE = "extract_image"
    VALIDATE_JSON = "validate_json"
    COMPARE_EXTRACTIONS = "compare_extractions"
    GENERATE_REPORT = "generate_report"
    SYNTHESIZE = "synthesize"


class Task(BaseModel):
    """Task in the orchestration pipeline."""
    task_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    task_type: TaskType

    # Input data
    input_data: dict[str, Any] = Field(default_factory=dict)

    # Assignment
    assigned_agent: Optional[str] = None
    assigned_model: Optional[str] = None

    # Execution status
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    # Metrics
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cost_usd: float = 0.0


class Pipeline(BaseModel):
    """Orchestration pipeline for MEP extraction."""
    pipeline_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str

    # Tasks
    tasks: list[Task] = Field(default_factory=list)

    # Execution state
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    current_task_index: int = 0

    # Agent pool
    orchestrator_config: Optional[AgentConfig] = None
    extractor_configs: list[AgentConfig] = Field(default_factory=list)
    reasoner_configs: list[AgentConfig] = Field(default_factory=list)

    # Metrics
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_cost_usd: float = 0.0

    def add_task(self, task: Task) -> None:
        """Add task to pipeline."""
        self.tasks.append(task)

    def get_next_task(self) -> Optional[Task]:
        """Get next pending task."""
        for task in self.tasks:
            if task.status == "pending":
                return task
        return None


# =============================================================================
# EXTRACTION RESULTS
# =============================================================================

class MEPExtraction(BaseModel):
    """Extracted data from MEP image."""
    image_type: Literal["blueprint", "field_photo", "diagram", "unknown"]
    trade: Literal["solar", "electrical", "hvac", "plumbing", "roofing", "unknown"]

    # Extracted fields - Any type for VLM flexibility
    equipment_visible: list[str] = Field(default_factory=list)
    specifications: dict[str, Any] = Field(default_factory=dict)
    measurements: dict[str, Any] = Field(default_factory=dict)

    # Condition (for field photos)
    condition: Optional[Literal["good", "fair", "poor", "critical"]] = None
    issues_found: list[str] = Field(default_factory=list)

    # Confidence
    confidence_score: float = 0.0
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)

    # Metadata
    model_used: Optional[str] = None
    extraction_time_ms: int = 0
    cost_usd: float = 0.0


class ExtractionComparison(BaseModel):
    """Comparison between multiple extractions."""
    extractions: list[MEPExtraction] = Field(default_factory=list)

    # Consensus
    consensus_reached: bool = False
    consensus_extraction: Optional[MEPExtraction] = None

    # Disagreements
    disagreement_fields: list[str] = Field(default_factory=list)
    needs_orchestrator_decision: bool = False

    # Best extraction (highest confidence)
    best_extraction_index: int = 0
    best_confidence: float = 0.0
