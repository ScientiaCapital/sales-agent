"""
LangChain tools for Close CRM Sequences

Provides LangChain-compatible tools for managing multi-step email sequences.
Wraps CloseSequencesClient for use in LangGraph agents.

Tools:
- list_sequences_tool: List available sequences
- subscribe_to_sequence_tool: Enroll contact in sequence
- pause_sequence_tool: Pause subscription (e.g., OOO detected)
- resume_sequence_tool: Resume paused subscription
- stop_sequence_tool: Stop subscription (e.g., reply received)
- stop_all_sequences_tool: Stop all sequences for contact (unsubscribe)
- get_sequence_status_tool: Check subscription progress

Integration:
- OutreachAgent: Enroll leads in drip campaigns
- ReplyRouter: Auto-pause/stop on replies
- BDRAgent: Manual sequence management
"""

import os
import logging
from typing import Optional
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.crm.close_sequences import CloseSequencesClient

logger = logging.getLogger(__name__)


# ========== Safety Check ==========

def _check_write_enabled() -> bool:
    """Check if Close CRM writes are enabled."""
    disabled = os.getenv(
        "CLOSE_WRITE_DISABLED", "True"
    ).lower() in ("true", "1", "yes")
    return not disabled


# ========== Pydantic Input Schemas ==========

class ListSequencesInput(BaseModel):
    """Input schema for listing sequences."""
    active_only: bool = Field(
        default=True,
        description="Only return active sequences"
    )


class SubscribeInput(BaseModel):
    """Input schema for subscribing to a sequence."""
    sequence_id: str = Field(
        ...,
        description="Close sequence ID (seq_xxx)"
    )
    contact_id: str = Field(
        ...,
        description="Close contact ID (cont_xxx)"
    )
    sender_email: Optional[str] = Field(
        default=None,
        description="Override sender email (optional)"
    )


class SubscriptionActionInput(BaseModel):
    """Input schema for subscription actions (pause/resume/stop)."""
    subscription_id: str = Field(
        ...,
        description="Close subscription ID (sub_xxx)"
    )


class ContactSequenceInput(BaseModel):
    """Input schema for contact-level operations."""
    contact_id: str = Field(
        ...,
        description="Close contact ID (cont_xxx)"
    )


class SequenceByNameInput(BaseModel):
    """Input schema for finding sequence by name."""
    sequence_name: str = Field(
        ...,
        description="Sequence name to search for"
    )
    contact_id: str = Field(
        ...,
        description="Contact ID to enroll"
    )


# ========== Tools ==========

@tool(args_schema=ListSequencesInput)
async def list_sequences_tool(active_only: bool = True) -> str:
    """
    List all available sequences in Close CRM.

    Returns sequence names and IDs for enrollment.
    """
    try:
        client = CloseSequencesClient()
        sequences = await client.list_sequences(active_only=active_only)

        if not sequences:
            return "No sequences found in Close CRM."

        lines = ["Available Sequences:", ""]
        for seq in sequences:
            name = seq.get("name", "Unnamed")
            seq_id = seq.get("id", "unknown")
            status = seq.get("status", "unknown")
            lines.append(f"- {name} ({seq_id}) - {status}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to list sequences: {e}")
        raise ToolException(f"Failed to list sequences: {str(e)}")


@tool(args_schema=SubscribeInput)
async def subscribe_to_sequence_tool(
    sequence_id: str,
    contact_id: str,
    sender_email: Optional[str] = None
) -> str:
    """
    Subscribe a contact to a sequence (drip campaign).

    Use this to enroll leads in automated email sequences.
    The sequence will send emails according to its defined steps and delays.
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes are disabled (CLOSE_WRITE_DISABLED=True). "
            "Set CLOSE_WRITE_DISABLED=False to enable sequence enrollment."
        )

    try:
        client = CloseSequencesClient()
        result = await client.subscribe_contact(
            sequence_id=sequence_id,
            contact_id=contact_id,
            sender_email=sender_email
        )

        if result:
            sub_id = result.get("id", "unknown")
            status = result.get("status", "active")
            return (
                f"Contact enrolled in sequence successfully!\n"
                f"- Subscription ID: {sub_id}\n"
                f"- Status: {status}\n"
                f"- Sequence: {sequence_id}\n"
                f"- Contact: {contact_id}"
            )
        else:
            raise ToolException("Failed to subscribe contact to sequence")

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        raise ToolException(f"Failed to subscribe: {str(e)}")


@tool(args_schema=SequenceByNameInput)
async def enroll_in_sequence_by_name_tool(
    sequence_name: str,
    contact_id: str
) -> str:
    """
    Find a sequence by name and enroll a contact.

    Searches for a sequence matching the name, then subscribes the contact.
    Use this when you know the sequence name but not the ID.
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes disabled. Cannot enroll in sequence."
        )

    try:
        client = CloseSequencesClient()

        # Find sequence by name
        sequence = await client.get_sequence_by_name(sequence_name)
        if not sequence:
            return f"Sequence '{sequence_name}' not found in Close CRM."

        seq_id = sequence.get("id")
        if not seq_id:
            return f"Sequence '{sequence_name}' has no ID."

        # Subscribe contact
        result = await client.subscribe_contact(
            sequence_id=seq_id,
            contact_id=contact_id
        )

        if result:
            return (
                f"Enrolled contact in '{sequence_name}'!\n"
                f"- Subscription ID: {result.get('id')}\n"
                f"- Status: {result.get('status', 'active')}"
            )
        else:
            raise ToolException("Failed to enroll contact")

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Failed to enroll by name: {e}")
        raise ToolException(f"Failed to enroll: {str(e)}")


@tool(args_schema=SubscriptionActionInput)
async def pause_sequence_tool(subscription_id: str) -> str:
    """
    Pause a sequence subscription.

    Use this when an out-of-office reply is detected or when you
    want to temporarily halt a sequence.
    """
    if not _check_write_enabled():
        raise ToolException("Close CRM writes disabled.")

    try:
        client = CloseSequencesClient()
        result = await client.pause_subscription(subscription_id)

        if result:
            return (
                f"Sequence paused successfully!\n"
                f"- Subscription: {subscription_id}\n"
                f"- Status: paused"
            )
        else:
            raise ToolException("Failed to pause sequence")

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause: {e}")
        raise ToolException(f"Failed to pause: {str(e)}")


@tool(args_schema=SubscriptionActionInput)
async def resume_sequence_tool(subscription_id: str) -> str:
    """
    Resume a paused sequence subscription.

    Use this to continue a previously paused sequence.
    """
    if not _check_write_enabled():
        raise ToolException("Close CRM writes disabled.")

    try:
        client = CloseSequencesClient()
        result = await client.resume_subscription(subscription_id)

        if result:
            return (
                f"Sequence resumed successfully!\n"
                f"- Subscription: {subscription_id}\n"
                f"- Status: active"
            )
        else:
            raise ToolException("Failed to resume sequence")

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume: {e}")
        raise ToolException(f"Failed to resume: {str(e)}")


@tool(args_schema=SubscriptionActionInput)
async def stop_sequence_tool(subscription_id: str) -> str:
    """
    Stop (unsubscribe) a sequence subscription.

    Use this when a reply is received or lead is no longer in sequence.
    """
    if not _check_write_enabled():
        raise ToolException("Close CRM writes disabled.")

    try:
        client = CloseSequencesClient()
        success = await client.unsubscribe_contact(subscription_id)

        if success:
            return (
                f"Sequence stopped successfully!\n"
                f"- Subscription: {subscription_id}\n"
                f"- Status: stopped"
            )
        else:
            raise ToolException("Failed to stop sequence")

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop: {e}")
        raise ToolException(f"Failed to stop: {str(e)}")


@tool(args_schema=ContactSequenceInput)
async def stop_all_sequences_tool(contact_id: str) -> str:
    """
    Stop ALL active sequences for a contact.

    Use this when a contact unsubscribes or requests no further contact.
    Critical for compliance with unsubscribe requests.
    """
    if not _check_write_enabled():
        raise ToolException("Close CRM writes disabled.")

    try:
        client = CloseSequencesClient()
        stopped = await client.stop_all_sequences_for_contact(contact_id)

        return (
            f"Stopped {stopped} sequences for contact!\n"
            f"- Contact: {contact_id}\n"
            f"- Sequences stopped: {stopped}"
        )

    except Exception as e:
        logger.error(f"Failed to stop all: {e}")
        raise ToolException(f"Failed to stop sequences: {str(e)}")


@tool(args_schema=ContactSequenceInput)
async def get_contact_sequence_status_tool(contact_id: str) -> str:
    """
    Get sequence subscription status for a contact.

    Shows which sequences the contact is enrolled in and their progress.
    """
    try:
        client = CloseSequencesClient()
        subs = await client.get_contact_subscriptions(
            contact_id, active_only=False
        )

        if not subs:
            return f"Contact {contact_id} is not enrolled in any sequences."

        lines = [f"Sequence subscriptions for {contact_id}:", ""]
        for sub in subs:
            sub_id = sub.get("id", "unknown")
            seq_id = sub.get("sequence_id", "unknown")
            status = sub.get("status", "unknown")
            step = sub.get("current_step", 0)
            lines.append(f"- {sub_id}: {status} (step {step}) - seq: {seq_id}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise ToolException(f"Failed to get status: {str(e)}")


# ========== Tool List for Agent Integration ==========

SEQUENCE_TOOLS = [
    list_sequences_tool,
    subscribe_to_sequence_tool,
    enroll_in_sequence_by_name_tool,
    pause_sequence_tool,
    resume_sequence_tool,
    stop_sequence_tool,
    stop_all_sequences_tool,
    get_contact_sequence_status_tool,
]


def get_sequence_tools():
    """Get all sequence tools for agent integration."""
    return SEQUENCE_TOOLS


__all__ = [
    "list_sequences_tool",
    "subscribe_to_sequence_tool",
    "enroll_in_sequence_by_name_tool",
    "pause_sequence_tool",
    "resume_sequence_tool",
    "stop_sequence_tool",
    "stop_all_sequences_tool",
    "get_contact_sequence_status_tool",
    "get_sequence_tools",
    "SEQUENCE_TOOLS",
]
