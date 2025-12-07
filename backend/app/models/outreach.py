"""
Outreach Models - Staging and channel management for multi-channel outreach

Provides Pydantic models for orchestrating staged outreach across
email, SMS, LinkedIn, calls, and future voice AI channels.

Key Features:
- StagingMode: Control over draft creation vs auto-send
- OutreachRequest: Multi-channel outreach specification
- OutreachResult: Detailed results per channel
- Integration with dim_ai_drafts table for approval workflow

Usage:
    from app.models.outreach import OutreachRequest, StagingMode, OutreachChannel

    request = OutreachRequest(
        lead_id="lead_abc123",
        channels=[OutreachChannel.EMAIL, OutreachChannel.SMS],
        mode=StagingMode.DRAFT,
        priority="morning"
    )
"""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class StagingMode(str, Enum):
    """
    Staging mode for outreach execution.

    Controls whether outreach is sent immediately or requires human approval.
    """
    DRAFT = "draft"           # Create draft, wait for approval (default, safest)
    AUTO_APPROVE = "auto"     # Send immediately (use with caution)
    REVIEW_FIRST = "review"   # Stage + open in dashboard for review


class OutreachChannel(str, Enum):
    """
    Available outreach channels.

    Each channel has different requirements and best practices.
    """
    EMAIL = "email"           # Email via Close CRM (tim@coperniq.io)
    SMS = "sms"               # SMS via Close CRM (TCPA-compliant)
    LINKEDIN = "linkedin"     # LinkedIn connection/message (future: via Browserbase)
    CALL = "call"             # Phone call (creates task for human)
    VOICE = "voice"           # AI voice call (future: via RunPod)


class OutreachPriority(str, Enum):
    """
    When to execute outreach.

    Controls timing of outreach execution.
    """
    NOW = "now"               # Send immediately (if auto mode)
    MORNING = "morning"       # Queue for next morning (7-9 AM local time)
    SCHEDULED = "scheduled"   # Custom scheduled time (requires scheduled_for)


class OutreachRequest(BaseModel):
    """
    Request to stage multi-channel outreach for a lead.

    Specifies which channels to use, when to send, and whether to
    auto-approve or require human review.

    Examples:
        # Email draft for review
        OutreachRequest(
            lead_id="lead_abc",
            channels=[OutreachChannel.EMAIL],
            mode=StagingMode.DRAFT
        )

        # Auto-send email + SMS immediately
        OutreachRequest(
            lead_id="lead_abc",
            channels=[OutreachChannel.EMAIL, OutreachChannel.SMS],
            mode=StagingMode.AUTO_APPROVE,
            priority=OutreachPriority.NOW
        )

        # LinkedIn connection for morning
        OutreachRequest(
            lead_id="lead_abc",
            channels=[OutreachChannel.LINKEDIN],
            mode=StagingMode.REVIEW_FIRST,
            priority=OutreachPriority.MORNING
        )
    """

    # Required fields
    lead_id: str = Field(
        ...,
        description="Close CRM lead ID (e.g., lead_abc123)"
    )

    channels: List[OutreachChannel] = Field(
        ...,
        description="List of channels to use (email, sms, linkedin, call, voice)"
    )

    # Staging configuration
    mode: StagingMode = Field(
        default=StagingMode.DRAFT,
        description="Staging mode: draft (default), auto, or review"
    )

    priority: OutreachPriority = Field(
        default=OutreachPriority.MORNING,
        description="When to execute: now, morning, or scheduled"
    )

    scheduled_for: Optional[datetime] = Field(
        default=None,
        description="Custom scheduled time (required if priority=scheduled)"
    )

    # Content overrides (optional - otherwise AI-generated)
    email_subject: Optional[str] = Field(
        default=None,
        description="Override AI-generated email subject"
    )

    email_body: Optional[str] = Field(
        default=None,
        description="Override AI-generated email body"
    )

    sms_text: Optional[str] = Field(
        default=None,
        description="Override AI-generated SMS text (max 160 chars)"
    )

    linkedin_note: Optional[str] = Field(
        default=None,
        description="Override AI-generated LinkedIn connection note"
    )

    call_script: Optional[str] = Field(
        default=None,
        description="Override AI-generated call script/talking points"
    )

    # Metadata
    created_by: str = Field(
        default="system",
        description="User or system creating this request"
    )

    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context for AI personalization"
    )


class ChannelResult(BaseModel):
    """
    Result of staging/sending outreach on a single channel.

    Tracks success/failure per channel with detailed metadata.
    """

    channel: OutreachChannel = Field(
        ...,
        description="Channel that was attempted"
    )

    success: bool = Field(
        ...,
        description="Whether staging/sending succeeded"
    )

    status: str = Field(
        ...,
        description="Status: staged, sent, failed, skipped"
    )

    # For staged drafts
    draft_id: Optional[str] = Field(
        default=None,
        description="Draft ID in dim_ai_drafts (if staged)"
    )

    # For sent messages
    activity_id: Optional[str] = Field(
        default=None,
        description="Close CRM activity ID (if sent)"
    )

    # Error handling
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )

    # Metadata
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this channel was processed"
    )

    processing_time_ms: int = Field(
        default=0,
        description="Time taken to process this channel"
    )


class OutreachResult(BaseModel):
    """
    Result of a multi-channel outreach request.

    Aggregates results across all requested channels with overall stats.

    Example:
        {
            "request_id": "req_abc123",
            "lead_id": "lead_xyz",
            "channels_requested": ["email", "sms"],
            "channels_staged": ["email", "sms"],
            "channels_sent": [],
            "channels_failed": [],
            "drafts_created": 2,
            "slack_notified": true,
            "results": [
                {"channel": "email", "success": true, "status": "staged", "draft_id": "draft_1"},
                {"channel": "sms", "success": true, "status": "staged", "draft_id": "draft_2"}
            ]
        }
    """

    # Request metadata
    request_id: str = Field(
        ...,
        description="Unique identifier for this outreach request"
    )

    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )

    # Aggregate stats
    channels_requested: List[OutreachChannel] = Field(
        ...,
        description="Channels that were requested"
    )

    channels_staged: List[OutreachChannel] = Field(
        default_factory=list,
        description="Channels successfully staged as drafts"
    )

    channels_sent: List[OutreachChannel] = Field(
        default_factory=list,
        description="Channels successfully sent (auto mode)"
    )

    channels_failed: List[OutreachChannel] = Field(
        default_factory=list,
        description="Channels that failed to stage/send"
    )

    drafts_created: int = Field(
        default=0,
        description="Number of drafts created in dim_ai_drafts"
    )

    slack_notified: bool = Field(
        default=False,
        description="Whether Slack notification was sent for approval"
    )

    # Detailed results per channel
    results: List[ChannelResult] = Field(
        default_factory=list,
        description="Detailed results for each channel"
    )

    # Overall metadata
    total_processing_time_ms: int = Field(
        default=0,
        description="Total time to process all channels"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this request was created"
    )

    completed_at: Optional[datetime] = Field(
        default=None,
        description="When this request completed"
    )


class DraftApprovalRequest(BaseModel):
    """
    Request to approve a draft and send via Close CRM.

    Used by Slack buttons or dashboard UI to approve staged drafts.
    """

    draft_id: str = Field(
        ...,
        description="Draft ID from dim_ai_drafts"
    )

    approved_by: str = Field(
        ...,
        description="User who approved (e.g., 'tim@coperniq.io' or Slack user ID)"
    )

    # Optional edits before sending
    subject: Optional[str] = Field(
        default=None,
        description="Override subject (email only)"
    )

    body: Optional[str] = Field(
        default=None,
        description="Override body text"
    )


class DraftRejectionRequest(BaseModel):
    """
    Request to reject/discard a draft.

    Marks draft as discarded and optionally provides feedback.
    """

    draft_id: str = Field(
        ...,
        description="Draft ID from dim_ai_drafts"
    )

    rejected_by: str = Field(
        ...,
        description="User who rejected"
    )

    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for rejection (for learning)"
    )


class SlackApprovalPayload(BaseModel):
    """
    Slack Block Kit action payload for draft approval/rejection.

    Sent when user clicks "Approve" or "Reject" button in Slack.
    """

    action: Literal["approve", "reject"] = Field(
        ...,
        description="Action taken: approve or reject"
    )

    draft_id: str = Field(
        ...,
        description="Draft ID from button value"
    )

    user_id: str = Field(
        ...,
        description="Slack user ID who clicked button"
    )

    user_email: Optional[str] = Field(
        default=None,
        description="Slack user email (if available)"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When action was taken"
    )
