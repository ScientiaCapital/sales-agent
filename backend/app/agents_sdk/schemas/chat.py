"""Chat-related Pydantic schemas for Agent SDK."""
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import json


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request to chat with an agent."""

    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(None, description="Existing session ID")
    stream: bool = Field(True, description="Stream response via SSE")
    metadata: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    session_id: str
    message: str
    agent_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class SSEChunk(BaseModel):
    """Server-Sent Event chunk for streaming."""

    event: str = Field("message", description="SSE event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    id: Optional[str] = None

    def format_sse(self) -> str:
        """Format as SSE protocol string."""
        lines = []

        if self.id:
            lines.append(f"id: {self.id}")

        lines.append(f"event: {self.event}")
        lines.append(f"data: {json.dumps(self.data)}")
        lines.append("")  # Empty line terminates event

        return "\n".join(lines)


class SessionInfo(BaseModel):
    """Session metadata."""

    session_id: str
    user_id: str
    agent_type: str
    created_at: datetime
    last_activity_at: datetime
    message_count: int = 0
    total_cost_usd: float = 0.0
