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
from dotenv import load_dotenv

# Ensure env vars are loaded
load_dotenv()

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

    async def get_activities_since(
        self,
        since: datetime,
        activity_types: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all activities (emails, SMS, calls) since a given timestamp.

        Args:
            since: Fetch activities created after this timestamp
            activity_types: List of activity types to fetch (default: all)
                           Options: "email", "sms", "call"
            limit: Maximum activities per type to return

        Returns:
            List of activity dicts with 'type' field indicating activity type
        """
        if activity_types is None:
            activity_types = ["email", "sms", "call"]

        all_activities = []

        for activity_type in activity_types:
            try:
                endpoint = f"{self.BASE_URL}/activity/{activity_type}/"
                params = {
                    "date_created__gte": since.strftime("%Y-%m-%dT%H:%M:%S"),
                    "_limit": limit,
                    "_order_by": "date_created",
                }

                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        endpoint,
                        headers=self._get_headers(),
                        params=params,
                        timeout=30.0,
                    )

                    response.raise_for_status()
                    data = response.json()

                    activities = data.get("data", [])
                    # Add type field for easy identification
                    for activity in activities:
                        activity["_activity_type"] = activity_type

                    all_activities.extend(activities)
                    logger.debug(
                        f"Fetched {len(activities)} {activity_type} activities since {since}"
                    )

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Close {activity_type} activity fetch error: "
                    f"{e.response.status_code} - {e.response.text}"
                )
            except Exception as e:
                logger.error(f"Failed to fetch {activity_type} activities: {e}")

        logger.info(f"Total activities fetched since {since}: {len(all_activities)}")
        return all_activities

    async def get_incoming_emails_since(
        self,
        since: datetime,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch incoming email replies since a given timestamp.

        Incoming emails are identified by direction='incoming' or lack of sender_user_id.

        Args:
            since: Fetch emails created after this timestamp
            limit: Maximum emails to return

        Returns:
            List of incoming email activity dicts
        """
        try:
            params = {
                "date_created__gte": since.strftime("%Y-%m-%dT%H:%M:%S"),
                "_limit": limit,
                "_order_by": "date_created",
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

                # Filter to incoming emails only
                # Close marks incoming emails with direction='incoming' or status='inbox'
                incoming = [
                    e for e in emails
                    if e.get("direction") == "incoming"
                    or e.get("status") == "inbox"
                    or not e.get("user_id")  # No sending user = received email
                ]

                logger.info(
                    f"Found {len(incoming)} incoming emails since {since} "
                    f"(out of {len(emails)} total)"
                )
                return incoming

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close incoming emails fetch error: {e.response.status_code} - {e.response.text}"
            )
            return []
        except Exception as e:
            logger.error(f"Failed to fetch incoming emails: {e}")
            return []

    # Close CRM Custom Field IDs
    # These map to your actual Close account custom fields
    CUSTOM_FIELDS = {
        # Source tracking
        "original_source": "cf_2hfeT2jPdydIahMQmRGXaoaVRVpPPrWcvqRz07ZUb9n",  # Original Source (choices)
        # Industry
        "primary_industry": "cf_ly6GNkZzcZXaqMS4yjSCf2hCsjco5Mvl5GJ0VB2HtJP",  # Primary Industry (Verified)
        # Lead scoring & qualification
        "tier": "cf_lobJ0ZNFQNmbKG7Wh10LjChXLhbuNLsPvjbYiYY030d",  # tier (hot/warm/cold)
        "tier_verified": "cf_ewefK5iFmVpBemft6uHTknfwFOxXf6jM6MUvp48NKxq",  # Tier (verified) - S/A/B/C
        "qualification_score": "cf_mZ89DBTfARHRjVjZLs5PQvmfLiaZSi2GWq9AFQ6ddwO",  # qualification_score (number)
        "is_atl": "cf_3GYoxBOcie708HxPnMOUExtxjECFpWvN1e61TMqFy0K",  # is_atl (Yes/No)
        # Company details
        "area_of_focus": "cf_LxbZDklwgRTXtBRxwnevlT2kKhBD2tkm0B9vxPRElkA",  # Area of Focus (Residential/Commercial)
        "type_of_work": "cf_QIn6Cb4ongYH794UUUgOdhyn6f1qTjtBVsjHgsXIUmB",  # Type of Work (Construction/Service)
        "num_employees": "cf_JPeSD7tiaqW9OomxwDvLVJzPZ7Z6sULyg7TurFoCgd8",  # Number of employees (text)
        "linkedin_url": "cf_hziAFKlGoqQyLtUYfjNlqwFIbon2AS1lZn2R3NrHiWr",  # Lead LinkedIn URL (verified)
    }

    async def create_lead_with_contact(
        self,
        company_name: str,
        contact_email: str,
        contact_name: Optional[str] = None,
        contact_title: Optional[str] = None,
        company_url: Optional[str] = None,
        company_phone: Optional[str] = None,
        # New ICP fields from Supabase
        icp_tier: Optional[str] = None,
        qualification_score: Optional[float] = None,
        primary_industry: Optional[str] = None,
        area_of_focus: Optional[str] = None,
        is_atl: Optional[bool] = None,
        linkedin_url: Optional[str] = None,
        num_employees: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a lead in Close CRM with one contact and ICP data.

        This is used to auto-import leads from Supabase when staging drafts.
        Creates the lead with full ICP context so we can then create email drafts.

        Args:
            company_name: Company/lead name
            contact_email: Contact email (required for email drafts)
            contact_name: Contact full name (optional)
            contact_title: Contact job title (optional)
            company_url: Company website URL (optional)
            company_phone: Company phone (optional)
            icp_tier: ICP tier from Supabase (PLATINUM/GOLD/SILVER/BRONZE)
            qualification_score: ICP score 0-100
            primary_industry: Industry vertical (HVAC, Solar, etc.)
            area_of_focus: Residential/Commercial/Both
            is_atl: Whether contact is Above The Line decision maker
            linkedin_url: Company LinkedIn URL
            num_employees: Employee count or range

        Returns:
            Dict with lead_id, contact_id, and close_lead_url
        """
        try:
            # Build lead payload
            payload = {
                "name": company_name,
                "contacts": [
                    {
                        "name": contact_name or "Contact",
                        "emails": [{"email": contact_email, "type": "office"}],
                    }
                ],
            }

            # Add optional contact fields
            if contact_title:
                payload["contacts"][0]["title"] = contact_title

            # Add optional company fields
            if company_url:
                payload["url"] = company_url
            if company_phone:
                payload["phones"] = [{"phone": company_phone, "type": "office"}]

            # Set default owner (Tim Kipper)
            default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
            if default_owner:
                payload["user_id"] = default_owner

            # Add source tracking - "AI Outreach" as original source
            # Note: This must be an existing choice in the Original Source field
            # Using "Apollo .io" as fallback since it's a valid choice
            payload[f"custom.{self.CUSTOM_FIELDS['original_source']}"] = "Apollo .io"

            # Map ICP tier to Close tier field
            # Supabase: PLATINUM/GOLD/SILVER/BRONZE → Close: S/A/B/C
            if icp_tier:
                tier_map = {
                    "PLATINUM": "S",
                    "GOLD": "A",
                    "SILVER": "B",
                    "BRONZE": "C",
                }
                close_tier = tier_map.get(icp_tier.upper(), "C")
                payload[f"custom.{self.CUSTOM_FIELDS['tier_verified']}"] = close_tier

                # Also set hot/warm/cold tier based on ICP
                temp_map = {
                    "PLATINUM": "hot",
                    "GOLD": "hot",
                    "SILVER": "warm",
                    "BRONZE": "cold",
                }
                payload[f"custom.{self.CUSTOM_FIELDS['tier']}"] = temp_map.get(icp_tier.upper(), "cold")

            # Add qualification score
            if qualification_score is not None:
                payload[f"custom.{self.CUSTOM_FIELDS['qualification_score']}"] = qualification_score

            # Map primary industry
            # Valid choices: Electrical, GC/Construction, Life Safety, Mechanical/HVAC, Other, Solar
            if primary_industry:
                industry_map = {
                    "HVAC": "Mechanical/HVAC",
                    "Solar": "Solar",
                    "Electrical": "Electrical",
                    "Plumbing": "Other",
                    "Roofing": "GC/Construction",
                }
                close_industry = industry_map.get(primary_industry, "Other")
                payload[f"custom.{self.CUSTOM_FIELDS['primary_industry']}"] = close_industry

            # Map area of focus
            # Valid choices: Both (Residential & Commercial), Commercial, Residential, Utility
            if area_of_focus:
                focus_map = {
                    "Residential": "Residential",
                    "Commercial": "Commercial",
                    "Both": "Both (Residential & Commercial)",
                }
                close_focus = focus_map.get(area_of_focus, area_of_focus)
                payload[f"custom.{self.CUSTOM_FIELDS['area_of_focus']}"] = close_focus

            # Add is_atl flag
            if is_atl is not None:
                payload[f"custom.{self.CUSTOM_FIELDS['is_atl']}"] = "Yes" if is_atl else "No"

            # Add LinkedIn URL
            if linkedin_url:
                payload[f"custom.{self.CUSTOM_FIELDS['linkedin_url']}"] = linkedin_url

            # Add employee count
            if num_employees:
                payload[f"custom.{self.CUSTOM_FIELDS['num_employees']}"] = str(num_employees)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/lead/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                lead_id = result.get("id")
                contacts = result.get("contacts", [])
                contact_id = contacts[0].get("id") if contacts else None

                logger.info(
                    f"Created Close lead: {lead_id} for {company_name} "
                    f"(ICP: {icp_tier}, score: {qualification_score}) "
                    f"with contact {contact_email}"
                )

                return {
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "company_name": company_name,
                    "contact_email": contact_email,
                    "close_lead_url": f"https://app.close.com/lead/{lead_id}/",
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Close create lead error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to create lead in Close: {e}")
            raise
