"""
Close CRM Email Integration

Enables email sending and history retrieval through Close CRM's Email activity API.
Uses tim@coperniq.io as the default connected account for automated workflows.

API Documentation: https://developer.close.com/resources/activities/email
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import httpx
import logging
import base64
import os

logger = logging.getLogger(__name__)


class CloseEmailClient:
    """
    Close CRM email integration for sending and tracking email activities.

    Features:
    - Send emails via connected Close accounts (tim@coperniq.io)
    - Create drafts for review before sending
    - Schedule emails for future delivery
    - Retrieve email history for leads/contacts
    - Support for email templates
    - Automatic activity logging in Close CRM

    Close Email API Details:
    - Endpoint: POST /activity/email/
    - Auth: Basic auth with API key
    - Statuses: inbox, draft, scheduled, outbox, sent
    - Supports HTML and plain text bodies
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Email statuses from Close API
    STATUS_INBOX = "inbox"      # Received email (logging inbound)
    STATUS_DRAFT = "draft"      # Draft email (not sent yet)
    STATUS_SCHEDULED = "scheduled"  # Scheduled for future sending
    STATUS_OUTBOX = "outbox"    # Queued for immediate sending
    STATUS_SENT = "sent"        # Already sent (logging historical)

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize Close email client.

        Args:
            api_key: Close API key (falls back to CLOSE_API_KEY env var)
            redis_client: Redis client for rate limiting (optional)
        """
        self.api_key = api_key or os.getenv("CLOSE_API_KEY")
        if not self.api_key:
            raise ValueError("Close API key is required. Set CLOSE_API_KEY env var or pass api_key.")

        self.redis = redis_client

        # Close uses Basic auth with format "api_key:" (note the colon)
        auth_string = f"{self.api_key}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        self.auth_header = f"Basic {auth_b64}"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        lead_id: str,
        body_html: Optional[str] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
        sender: Optional[str] = None,
        template_id: Optional[str] = None,
        schedule_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send email via Close CRM.

        The email is sent using the connected email account (tim@coperniq.io)
        and automatically logged as an activity in Close CRM.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_text: Plain text email body
            lead_id: Close lead ID to associate with (required)
            body_html: HTML email body (optional, recommended for formatting)
            contact_id: Close contact ID to associate with (optional)
            user_id: Close user ID sending the email (optional, defaults to API key owner)
            sender: Custom sender in format '"Name" <email>' (optional)
            template_id: Close email template ID to use instead of body (optional)
            schedule_seconds: Delay sending by N seconds (max 59) (optional)

        Returns:
            Dict with email activity details:
            {
                "id": "acti_xxx",
                "status": "outbox" or "sent",
                "to": "recipient@example.com",
                "subject": "Subject...",
                "lead_id": "lead_xxx",
                "created_at": "2024-12-06T12:00:00Z"
            }

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing
        """
        try:
            if not to_email or not lead_id:
                raise ValueError("Recipient email and lead_id are required")

            if not template_id and not body_text:
                raise ValueError("Either body_text or template_id is required")

            # Build email activity payload
            # Use "outbox" status to send immediately
            payload = {
                "status": self.STATUS_OUTBOX,
                "lead_id": lead_id,
                "to": [to_email],
                "subject": subject,
            }

            # Add body content
            if template_id:
                payload["template_id"] = template_id
            else:
                payload["body_text"] = body_text
                if body_html:
                    payload["body_html"] = body_html

            # Associate with contact if provided
            if contact_id:
                payload["contact_id"] = contact_id

            # Set sending user
            if user_id:
                payload["user_id"] = user_id
            else:
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            # Custom sender (uses connected account by default)
            if sender:
                payload["sender"] = sender

            # Delay sending if specified
            if schedule_seconds and schedule_seconds < 60:
                payload["send_in"] = schedule_seconds

            # Send email via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/email/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Email sent via Close CRM: {result.get('id')} to {to_email} "
                    f"(lead: {lead_id}, subject: {subject[:50]}...)"
                )

                return {
                    "id": result.get("id"),
                    "status": result.get("status", "outbox"),
                    "to": to_email,
                    "subject": subject,
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "created_at": result.get("date_created"),
                    "user_id": result.get("user_id"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Email API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to send email via Close: {e}")
            raise

    async def create_draft(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        lead_id: str,
        body_html: Optional[str] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create email draft in Close CRM for review before sending.

        Drafts appear in Close UI for manual review and sending.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_text: Plain text email body
            lead_id: Close lead ID to associate with
            body_html: HTML email body (optional)
            contact_id: Close contact ID (optional)
            user_id: Close user ID (optional)

        Returns:
            Dict with draft details including ID for later sending
        """
        try:
            payload = {
                "status": self.STATUS_DRAFT,
                "lead_id": lead_id,
                "to": [to_email],
                "subject": subject,
                "body_text": body_text,
            }

            if body_html:
                payload["body_html"] = body_html
            if contact_id:
                payload["contact_id"] = contact_id
            if user_id:
                payload["user_id"] = user_id
            else:
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/email/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Email draft created: {result.get('id')} to {to_email} "
                    f"(lead: {lead_id})"
                )

                return {
                    "id": result.get("id"),
                    "status": "draft",
                    "to": to_email,
                    "subject": subject,
                    "lead_id": lead_id,
                    "created_at": result.get("date_created"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Close Draft API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to create draft in Close: {e}")
            raise

    async def send_draft(self, email_id: str) -> Dict[str, Any]:
        """
        Send a previously created draft email.

        Args:
            email_id: Close email activity ID (from create_draft)

        Returns:
            Dict with updated email status
        """
        try:
            payload = {
                "status": self.STATUS_OUTBOX,  # Move to outbox for sending
            }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/activity/email/{email_id}/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Draft sent: {email_id} -> status: {result.get('status')}")

                return {
                    "id": result.get("id"),
                    "status": result.get("status"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Close send draft error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to send draft: {e}")
            raise

    async def schedule_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        lead_id: str,
        scheduled_time: datetime,
        body_html: Optional[str] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule email for future delivery.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_text: Plain text email body
            lead_id: Close lead ID
            scheduled_time: When to send (datetime object, UTC)
            body_html: HTML email body (optional)
            contact_id: Close contact ID (optional)
            user_id: Close user ID (optional)

        Returns:
            Dict with scheduled email details
        """
        try:
            payload = {
                "status": self.STATUS_SCHEDULED,
                "lead_id": lead_id,
                "to": [to_email],
                "subject": subject,
                "body_text": body_text,
                "date_scheduled": scheduled_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            if body_html:
                payload["body_html"] = body_html
            if contact_id:
                payload["contact_id"] = contact_id
            if user_id:
                payload["user_id"] = user_id
            else:
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/email/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Email scheduled: {result.get('id')} to {to_email} "
                    f"for {scheduled_time}"
                )

                return {
                    "id": result.get("id"),
                    "status": "scheduled",
                    "to": to_email,
                    "subject": subject,
                    "scheduled_for": scheduled_time.isoformat(),
                    "lead_id": lead_id,
                    "created_at": result.get("date_created"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Close schedule email error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to schedule email: {e}")
            raise

    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """
        Get a specific email activity by ID.

        Args:
            email_id: Close email activity ID

        Returns:
            Dict with full email details
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/activity/email/{email_id}/",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"Close get email error: {e.response.status_code} - {e.response.text}")
            raise

    async def get_email_history(
        self,
        lead_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get email activity history for a lead.

        Retrieves all email activities (inbound and outbound) associated with a lead,
        sorted by date descending (most recent first).

        Args:
            lead_id: Close lead ID
            limit: Max number of emails to return (default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of email activity dicts
        """
        try:
            params = {
                "lead_id": lead_id,
                "_limit": limit,
                "_skip": offset,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/activity/email/",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                emails = data.get("data", [])
                logger.info(f"Retrieved {len(emails)} emails for lead {lead_id}")

                return emails

        except httpx.HTTPStatusError as e:
            logger.error(f"Close email history error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to get email history: {e}")
            raise

    async def cancel_scheduled(self, email_id: str) -> Dict[str, Any]:
        """
        Cancel a scheduled email by reverting to draft status.

        Args:
            email_id: Close email activity ID

        Returns:
            Dict with updated status
        """
        try:
            payload = {
                "status": self.STATUS_DRAFT,  # Revert to draft
            }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/activity/email/{email_id}/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"Scheduled email cancelled: {email_id} -> draft")

                return {
                    "id": result.get("id"),
                    "status": "draft",
                    "message": "Scheduled email cancelled and reverted to draft",
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Close cancel email error: {e.response.status_code} - {e.response.text}")
            raise

    async def delete_email(self, email_id: str) -> bool:
        """
        Delete an email activity.

        Args:
            email_id: Close email activity ID

        Returns:
            True if deleted successfully
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.BASE_URL}/activity/email/{email_id}/",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                response.raise_for_status()
                logger.info(f"Email deleted: {email_id}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Close delete email error: {e.response.status_code} - {e.response.text}")
            raise
