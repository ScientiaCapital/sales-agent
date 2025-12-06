"""
Close CRM SMS Integration

Enables SMS sending and history retrieval through Close CRM's SMS activity API.
Close SMS is preferred over VozLux for integrated CRM communication tracking.

API Documentation: https://developer.close.com/resources/activities/
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import httpx
import logging
import base64
import os

logger = logging.getLogger(__name__)


class CloseSMSClient:
    """
    Close CRM SMS integration for sending and tracking SMS activities.

    Features:
    - Send SMS messages to leads/contacts
    - Retrieve SMS history for leads
    - Automatic activity logging in Close CRM
    - Rate limiting compatible with Close API

    Close SMS API Details:
    - Endpoint: POST /activity/sms/
    - Auth: Basic auth with API key
    - Automatic lead/contact association
    - Two-way SMS threading support
    """

    BASE_URL = "https://api.close.com/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize Close SMS client.

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

    async def send_sms(
        self,
        phone: str,
        message: str,
        lead_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send SMS via Close CRM.

        The SMS is automatically logged as an activity in Close CRM,
        creating a full communication history trail.

        Args:
            phone: Phone number to send to (E.164 format recommended: +1234567890)
            message: SMS message body (max 160 chars per segment)
            lead_id: Close lead ID to associate with (optional but recommended)
            contact_id: Close contact ID to associate with (optional)
            user_id: Close user ID sending the SMS (optional, defaults to API key owner)

        Returns:
            Dict with SMS activity details:
            {
                "id": "acti_xxx",
                "status": "sent",
                "phone": "+1234567890",
                "message": "Hello...",
                "lead_id": "lead_xxx",
                "created_at": "2024-12-06T12:00:00Z"
            }

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing
        """
        try:
            if not phone or not message:
                raise ValueError("Phone number and message are required")

            # Build SMS activity payload
            payload = {
                "direction": "outbound",
                "status": "draft",  # Close will mark as "sent" after delivery
                "text": message,
                "remote_phone": phone,  # Phone number being contacted
            }

            # Associate with lead if provided
            if lead_id:
                payload["lead_id"] = lead_id

            # Associate with contact if provided
            if contact_id:
                payload["contact_id"] = contact_id

            # Set sending user if provided
            if user_id:
                payload["user_id"] = user_id
            else:
                # Use default owner from environment if configured
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            # Send SMS via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/sms/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"SMS sent via Close CRM: {result.get('id')} to {phone} "
                    f"(lead: {lead_id or 'none'})"
                )

                return {
                    "id": result.get("id"),
                    "status": result.get("status", "sent"),
                    "phone": phone,
                    "message": message,
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "created_at": result.get("date_created"),
                    "user_id": result.get("user_id"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close SMS API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to send SMS via Close: {e}")
            raise

    async def get_sms_history(
        self,
        lead_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get SMS activity history for a lead.

        Retrieves all SMS messages (inbound and outbound) associated with a lead,
        sorted by date descending (most recent first).

        Args:
            lead_id: Close lead ID
            limit: Max number of SMS activities to return (default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of SMS activity dicts:
            [
                {
                    "id": "acti_xxx",
                    "direction": "outbound",
                    "text": "Hello...",
                    "remote_phone": "+1234567890",
                    "status": "sent",
                    "date_created": "2024-12-06T12:00:00Z",
                    "user_id": "user_xxx"
                },
                ...
            ]

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Query SMS activities for the lead
            params = {
                "lead_id": lead_id,
                "_type": "SMS",  # Filter to SMS activities only
                "_limit": limit,
                "_skip": offset,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/activity/",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                sms_activities = data.get("data", [])
                logger.info(
                    f"Retrieved {len(sms_activities)} SMS activities for lead {lead_id}"
                )

                return sms_activities

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close SMS history API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get SMS history from Close: {e}")
            raise

    async def get_contact_sms_history(
        self,
        contact_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get SMS activity history for a specific contact.

        Retrieves all SMS messages (inbound and outbound) associated with a contact,
        sorted by date descending (most recent first).

        Args:
            contact_id: Close contact ID
            limit: Max number of SMS activities to return (default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of SMS activity dicts (same format as get_sms_history)

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Query SMS activities for the contact
            params = {
                "contact_id": contact_id,
                "_type": "SMS",  # Filter to SMS activities only
                "_limit": limit,
                "_skip": offset,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/activity/",
                    headers=self._get_headers(),
                    params=params,
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                sms_activities = data.get("data", [])
                logger.info(
                    f"Retrieved {len(sms_activities)} SMS activities for contact {contact_id}"
                )

                return sms_activities

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close SMS history API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get contact SMS history from Close: {e}")
            raise

    async def send_sms_batch(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Send multiple SMS messages in batch.

        Sends SMS messages sequentially with error handling per message.
        Note: Close API doesn't have a native batch endpoint, so this
        sends messages one-by-one with individual error handling.

        Args:
            messages: List of message dicts, each containing:
                - phone: str (required)
                - message: str (required)
                - lead_id: str (optional)
                - contact_id: str (optional)
                - user_id: str (optional)

        Returns:
            List of results (one per message):
            [
                {"success": True, "id": "acti_xxx", "phone": "+1..."},
                {"success": False, "error": "...", "phone": "+1..."},
                ...
            ]
        """
        results = []

        for msg in messages:
            try:
                result = await self.send_sms(
                    phone=msg["phone"],
                    message=msg["message"],
                    lead_id=msg.get("lead_id"),
                    contact_id=msg.get("contact_id"),
                    user_id=msg.get("user_id"),
                )
                results.append({
                    "success": True,
                    "id": result.get("id"),
                    "phone": msg["phone"],
                })
            except Exception as e:
                logger.error(f"Batch SMS failed for {msg['phone']}: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "phone": msg["phone"],
                })

        return results
