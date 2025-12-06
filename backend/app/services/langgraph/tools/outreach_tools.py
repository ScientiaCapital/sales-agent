"""
LangChain tools for Close CRM Outreach (Email, SMS, Calling)

Provides LangChain-compatible tools for multi-channel outreach via Close CRM.
Wraps the existing Close CRM clients (CloseEmailClient, CloseSMSClient, CloseCallingClient).

Tools:
- send_email_tool: Send email via Close CRM (tim@coperniq.io)
- create_email_draft_tool: Create draft for review before sending
- send_sms_tool: Send SMS via Close CRM (TCPA-compliant)
- log_call_tool: Log completed phone call in Close
- schedule_call_tool: Schedule call activity for lead
- get_outreach_history_tool: Get all outreach activities for a lead

Integration:
- Uses CloseEmailClient from app.services.crm.close_email
- Uses CloseSMSClient from app.services.crm.close_sms
- Uses CloseCallingClient from app.services.crm.close_calling
- Respects CLOSE_WRITE_DISABLED safety switch
"""

import os
import logging
from typing import Optional
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.crm.close_email import CloseEmailClient
from app.services.crm.close_sms import CloseSMSClient
from app.services.crm.close_calling import CloseCallingClient

logger = logging.getLogger(__name__)


# ========== Safety Check ==========

def _check_write_enabled() -> bool:
    """
    Check if Close CRM writes are enabled.

    Returns:
        True if writes are enabled, False if disabled
    """
    disabled = os.getenv("CLOSE_WRITE_DISABLED", "True").lower() in ("true", "1", "yes")
    return not disabled


# ========== Pydantic Input Schemas ==========

class SendEmailInput(BaseModel):
    """Input schema for sending email via Close CRM."""

    to_email: str = Field(
        ...,
        description="Recipient email address"
    )
    subject: str = Field(
        ...,
        description="Email subject line"
    )
    body_text: str = Field(
        ...,
        description="Plain text email body"
    )
    lead_id: str = Field(
        ...,
        description="Close CRM lead ID (e.g., lead_xxx)"
    )
    body_html: Optional[str] = Field(
        default=None,
        description="HTML email body (optional, recommended for formatting)"
    )
    contact_id: Optional[str] = Field(
        default=None,
        description="Close CRM contact ID (optional)"
    )


class CreateDraftInput(BaseModel):
    """Input schema for creating email draft in Close CRM."""

    to_email: str = Field(
        ...,
        description="Recipient email address"
    )
    subject: str = Field(
        ...,
        description="Email subject line"
    )
    body_text: str = Field(
        ...,
        description="Plain text email body"
    )
    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )
    body_html: Optional[str] = Field(
        default=None,
        description="HTML email body (optional)"
    )


class SendSMSInput(BaseModel):
    """Input schema for sending SMS via Close CRM."""

    phone: str = Field(
        ...,
        description="Recipient phone number (E.164 format preferred)"
    )
    message: str = Field(
        ...,
        description="SMS message text (max 160 chars recommended)"
    )
    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )
    contact_id: Optional[str] = Field(
        default=None,
        description="Close CRM contact ID (optional)"
    )


class LogCallInput(BaseModel):
    """Input schema for logging a completed call in Close CRM."""

    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )
    phone: str = Field(
        ...,
        description="Phone number called"
    )
    duration_seconds: int = Field(
        ...,
        description="Call duration in seconds"
    )
    direction: str = Field(
        default="outbound",
        description="Call direction: 'outbound' or 'inbound'"
    )
    note: Optional[str] = Field(
        default=None,
        description="Call notes/summary"
    )
    disposition: Optional[str] = Field(
        default=None,
        description="Call disposition (e.g., 'connected', 'voicemail', 'no_answer')"
    )
    contact_id: Optional[str] = Field(
        default=None,
        description="Close CRM contact ID (optional)"
    )


class GetOutreachHistoryInput(BaseModel):
    """Input schema for getting outreach history."""

    lead_id: str = Field(
        ...,
        description="Close CRM lead ID"
    )
    limit: int = Field(
        default=20,
        description="Maximum number of activities to return"
    )


# ========== Tools ==========

@tool(args_schema=SendEmailInput)
async def send_email_tool(
    to_email: str,
    subject: str,
    body_text: str,
    lead_id: str,
    body_html: Optional[str] = None,
    contact_id: Optional[str] = None
) -> str:
    """
    Send email via Close CRM using tim@coperniq.io connected account.

    The email is automatically logged as an activity in Close CRM.
    Use this for immediate outreach to qualified leads.
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes are disabled (CLOSE_WRITE_DISABLED=True). "
            "Set CLOSE_WRITE_DISABLED=False in .env to enable email sending."
        )

    try:
        client = CloseEmailClient()
        result = await client.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            lead_id=lead_id,
            body_html=body_html,
            contact_id=contact_id
        )

        logger.info(f"Email sent via Close: {result['id']} to {to_email}")

        return (
            f"Email sent successfully!\n"
            f"- Activity ID: {result['id']}\n"
            f"- To: {to_email}\n"
            f"- Subject: {subject}\n"
            f"- Status: {result['status']}\n"
            f"- Lead ID: {lead_id}"
        )

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise ToolException(f"Failed to send email: {str(e)}")


@tool(args_schema=CreateDraftInput)
async def create_email_draft_tool(
    to_email: str,
    subject: str,
    body_text: str,
    lead_id: str,
    body_html: Optional[str] = None
) -> str:
    """
    Create email draft in Close CRM for review before sending.

    Drafts appear in Close UI and can be reviewed/edited by Tim before sending.
    Use this when you want human approval before sending.
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes are disabled. Set CLOSE_WRITE_DISABLED=False to enable."
        )

    try:
        client = CloseEmailClient()
        result = await client.create_draft(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            lead_id=lead_id,
            body_html=body_html
        )

        logger.info(f"Email draft created: {result['id']}")

        return (
            f"Email draft created for review!\n"
            f"- Draft ID: {result['id']}\n"
            f"- To: {to_email}\n"
            f"- Subject: {subject}\n"
            f"- Status: draft\n"
            f"- Lead ID: {lead_id}\n"
            f"\nReview and send from Close CRM UI, or use send_draft endpoint."
        )

    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        raise ToolException(f"Failed to create email draft: {str(e)}")


@tool(args_schema=SendSMSInput)
async def send_sms_tool(
    phone: str,
    message: str,
    lead_id: str,
    contact_id: Optional[str] = None
) -> str:
    """
    Send SMS via Close CRM (TCPA-compliant).

    Uses Tim's Close phone number. Messages are logged as SMS activities.
    Keep messages under 160 characters for single SMS.
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes are disabled. Set CLOSE_WRITE_DISABLED=False to enable SMS."
        )

    try:
        client = CloseSMSClient()
        result = await client.send_sms(
            phone=phone,
            message=message,
            lead_id=lead_id,
            contact_id=contact_id
        )

        logger.info(f"SMS sent via Close: {result['id']} to {phone}")

        return (
            f"SMS sent successfully!\n"
            f"- Activity ID: {result['id']}\n"
            f"- To: {phone}\n"
            f"- Message: {message[:50]}{'...' if len(message) > 50 else ''}\n"
            f"- Status: {result['status']}\n"
            f"- Lead ID: {lead_id}"
        )

    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        raise ToolException(f"Failed to send SMS: {str(e)}")


@tool(args_schema=LogCallInput)
async def log_call_tool(
    lead_id: str,
    phone: str,
    duration_seconds: int,
    direction: str = "outbound",
    note: Optional[str] = None,
    disposition: Optional[str] = None,
    contact_id: Optional[str] = None
) -> str:
    """
    Log a completed phone call in Close CRM.

    Use this after completing a call to record the activity.
    Includes call duration, notes, and disposition.

    Valid dispositions: answered, voicemail, no_answer, busy, failed
    """
    if not _check_write_enabled():
        raise ToolException(
            "Close CRM writes are disabled. Set CLOSE_WRITE_DISABLED=False to enable."
        )

    try:
        client = CloseCallingClient()

        # Map disposition to Close CRM status (default to 'answered')
        result_status = disposition or "answered"

        result = await client.log_call_directly(
            phone=phone,
            lead_id=lead_id,
            result=result_status,
            notes=note,
            duration_seconds=duration_seconds,
            contact_id=contact_id
        )

        logger.info(f"Call logged in Close: {result['id']}")

        return (
            f"Call logged successfully!\n"
            f"- Activity ID: {result['id']}\n"
            f"- Phone: {phone}\n"
            f"- Duration: {duration_seconds} seconds\n"
            f"- Status: {result_status}\n"
            f"- Lead ID: {lead_id}"
        )

    except Exception as e:
        logger.error(f"Failed to log call: {e}")
        raise ToolException(f"Failed to log call: {str(e)}")


@tool(args_schema=GetOutreachHistoryInput)
async def get_outreach_history_tool(
    lead_id: str,
    limit: int = 20
) -> str:
    """
    Get all outreach activity history for a lead.

    Retrieves emails, SMS, and calls associated with the lead.
    Useful for understanding engagement history before reaching out.
    """
    try:
        email_client = CloseEmailClient()
        sms_client = CloseSMSClient()
        call_client = CloseCallingClient()

        # Fetch all activity types in parallel
        emails = await email_client.get_email_history(lead_id, limit=limit)
        sms_messages = await sms_client.get_sms_history(lead_id, limit=limit)
        calls = await call_client.get_call_history(lead_id, limit=limit)

        # Format output
        output_lines = [f"Outreach History for Lead {lead_id}:", ""]

        if emails:
            output_lines.append(f"EMAILS ({len(emails)}):")
            for email in emails[:5]:  # Show top 5
                status = email.get('status', 'unknown')
                subject = email.get('subject', 'No subject')[:40]
                date = email.get('date_created', 'Unknown date')[:10]
                output_lines.append(f"  - [{status}] {date}: {subject}")
            if len(emails) > 5:
                output_lines.append(f"  ... and {len(emails) - 5} more")
        else:
            output_lines.append("EMAILS: None")

        output_lines.append("")

        if sms_messages:
            output_lines.append(f"SMS ({len(sms_messages)}):")
            for sms in sms_messages[:5]:
                text = sms.get('text', '')[:30]
                date = sms.get('date_created', 'Unknown')[:10]
                output_lines.append(f"  - {date}: {text}...")
            if len(sms_messages) > 5:
                output_lines.append(f"  ... and {len(sms_messages) - 5} more")
        else:
            output_lines.append("SMS: None")

        output_lines.append("")

        if calls:
            output_lines.append(f"CALLS ({len(calls)}):")
            for call in calls[:5]:
                duration = call.get('duration', 0)
                direction = call.get('direction', 'outbound')
                date = call.get('date_created', 'Unknown')[:10]
                output_lines.append(f"  - {date}: {direction} ({duration}s)")
            if len(calls) > 5:
                output_lines.append(f"  ... and {len(calls) - 5} more")
        else:
            output_lines.append("CALLS: None")

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"Failed to get outreach history: {e}")
        raise ToolException(f"Failed to get outreach history: {str(e)}")


# ========== Tool List for Agent Integration ==========

OUTREACH_TOOLS = [
    send_email_tool,
    create_email_draft_tool,
    send_sms_tool,
    log_call_tool,
    get_outreach_history_tool
]
