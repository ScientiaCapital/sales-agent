"""
Close CRM Voice Call Integration

Enables voice call activity logging and triggers through Close CRM.
Native Close CRM call tracking for integrated communication.

API Documentation: https://developer.close.com/resources/activities/
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import httpx
import logging
import base64
import os

logger = logging.getLogger(__name__)


class CloseCallingClient:
    """
    Close CRM calling integration for logging and triggering voice calls.

    Features:
    - Log outbound call activities
    - Log call results (answered, voicemail, no-answer, busy)
    - Retrieve call history for leads
    - Automatic activity logging in Close CRM
    - Call disposition tracking

    Close Call API Details:
    - Endpoint: POST /activity/call/
    - Auth: Basic auth with API key
    - Automatic lead/contact association
    - Call recording URL support
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Call statuses from Close API
    CALL_STATUS_ANSWERED = "answered"
    CALL_STATUS_VOICEMAIL = "voicemail"
    CALL_STATUS_NO_ANSWER = "no_answer"
    CALL_STATUS_BUSY = "busy"
    CALL_STATUS_FAILED = "failed"

    def __init__(
        self,
        api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize Close calling client.

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

    async def trigger_call(
        self,
        phone: str,
        lead_id: str,
        script_notes: Optional[str] = None,
        user_id: Optional[str] = None,
        contact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a voice call via Close CRM.

        Creates a call activity in Close CRM that can be used to:
        1. Log that a call is being initiated
        2. Provide script notes to the sales rep
        3. Track the call in CRM timeline

        Note: This logs the call intent. Actual dialing happens via:
        - Close's built-in dialer (if using Close's call features)
        - External dialer integration (e.g., Twilio, RingCentral)
        - Manual dialing by sales rep

        Args:
            phone: Phone number to call (E.164 format recommended: +1234567890)
            lead_id: Close lead ID to associate with (required)
            script_notes: Optional call script or talking points for the rep
            user_id: Close user ID making the call (optional)
            contact_id: Close contact ID to associate with (optional)

        Returns:
            Dict with call activity details:
            {
                "id": "acti_xxx",
                "status": "scheduled",
                "phone": "+1234567890",
                "lead_id": "lead_xxx",
                "notes": "Call script...",
                "created_at": "2024-12-06T12:00:00Z"
            }

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing
        """
        try:
            if not phone or not lead_id:
                raise ValueError("Phone number and lead_id are required")

            # Build call activity payload
            payload = {
                "direction": "outbound",
                "status": "scheduled",  # Indicates call is queued/scheduled
                "phone": phone,
                "lead_id": lead_id,
            }

            # Add script notes if provided
            if script_notes:
                payload["note"] = script_notes

            # Associate with contact if provided
            if contact_id:
                payload["contact_id"] = contact_id

            # Set calling user if provided
            if user_id:
                payload["user_id"] = user_id
            else:
                # Use default owner from environment if configured
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            # Create call activity via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/call/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Call triggered via Close CRM: {result.get('id')} to {phone} "
                    f"(lead: {lead_id})"
                )

                return {
                    "id": result.get("id"),
                    "status": result.get("status", "scheduled"),
                    "phone": phone,
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "notes": script_notes,
                    "created_at": result.get("date_created"),
                    "user_id": result.get("user_id"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Call API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to trigger call via Close: {e}")
            raise

    async def log_call_result(
        self,
        call_id: str,
        result: str,
        notes: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        recording_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log the result of a completed call.

        Updates an existing call activity with the outcome, notes, and duration.
        Used to track call dispositions and follow-up actions.

        Args:
            call_id: Close call activity ID (from trigger_call)
            result: Call outcome (answered, voicemail, no_answer, busy, failed)
            notes: Call notes, summary, or next steps
            duration_seconds: Call duration in seconds (optional)
            recording_url: URL to call recording (optional)

        Returns:
            Dict with updated call activity:
            {
                "id": "acti_xxx",
                "status": "answered",
                "duration": 180,
                "notes": "Discussed pricing...",
                "recording_url": "https://..."
            }

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If result is invalid
        """
        try:
            # Validate call result
            valid_results = [
                self.CALL_STATUS_ANSWERED,
                self.CALL_STATUS_VOICEMAIL,
                self.CALL_STATUS_NO_ANSWER,
                self.CALL_STATUS_BUSY,
                self.CALL_STATUS_FAILED,
            ]
            if result not in valid_results:
                raise ValueError(
                    f"Invalid call result: {result}. Must be one of: {', '.join(valid_results)}"
                )

            # Build update payload
            payload = {
                "status": result,
            }

            # Add notes if provided
            if notes:
                payload["note"] = notes

            # Add duration if provided
            if duration_seconds is not None:
                payload["duration"] = duration_seconds

            # Add recording URL if provided
            if recording_url:
                payload["recording_url"] = recording_url

            # Update call activity via Close API
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/activity/call/{call_id}/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result_data = response.json()

                logger.info(
                    f"Call result logged in Close CRM: {call_id} - {result} "
                    f"({duration_seconds}s)"
                )

                return {
                    "id": result_data.get("id"),
                    "status": result_data.get("status"),
                    "duration": result_data.get("duration"),
                    "notes": result_data.get("note"),
                    "recording_url": result_data.get("recording_url"),
                    "updated_at": result_data.get("date_updated"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Call result API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to log call result in Close: {e}")
            raise

    async def get_call_history(
        self,
        lead_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get call activity history for a lead.

        Retrieves all call activities (inbound and outbound) associated with a lead,
        sorted by date descending (most recent first).

        Args:
            lead_id: Close lead ID
            limit: Max number of call activities to return (default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of call activity dicts:
            [
                {
                    "id": "acti_xxx",
                    "direction": "outbound",
                    "status": "answered",
                    "phone": "+1234567890",
                    "duration": 180,
                    "note": "Discussed pricing...",
                    "date_created": "2024-12-06T12:00:00Z",
                    "user_id": "user_xxx"
                },
                ...
            ]

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        try:
            # Query call activities for the lead
            params = {
                "lead_id": lead_id,
                "_type": "Call",  # Filter to Call activities only
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

                call_activities = data.get("data", [])
                logger.info(
                    f"Retrieved {len(call_activities)} call activities for lead {lead_id}"
                )

                return call_activities

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Call history API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get call history from Close: {e}")
            raise

    async def log_call_directly(
        self,
        phone: str,
        lead_id: str,
        result: str,
        notes: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
        recording_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log a completed call directly (single-step).

        Combines trigger_call and log_call_result into one operation.
        Useful for logging calls made outside of Close (e.g., via external dialer).

        Args:
            phone: Phone number called
            lead_id: Close lead ID
            result: Call outcome (answered, voicemail, no_answer, busy, failed)
            notes: Call notes or summary
            duration_seconds: Call duration in seconds
            contact_id: Close contact ID (optional)
            user_id: Close user ID who made the call (optional)
            recording_url: URL to call recording (optional)

        Returns:
            Dict with call activity details

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing or result invalid
        """
        try:
            if not phone or not lead_id or not result:
                raise ValueError("Phone, lead_id, and result are required")

            # Validate call result
            valid_results = [
                self.CALL_STATUS_ANSWERED,
                self.CALL_STATUS_VOICEMAIL,
                self.CALL_STATUS_NO_ANSWER,
                self.CALL_STATUS_BUSY,
                self.CALL_STATUS_FAILED,
            ]
            if result not in valid_results:
                raise ValueError(
                    f"Invalid call result: {result}. Must be one of: {', '.join(valid_results)}"
                )

            # Build call activity payload with completed status
            payload = {
                "direction": "outbound",
                "status": result,
                "phone": phone,
                "lead_id": lead_id,
            }

            # Add optional fields
            if notes:
                payload["note"] = notes
            if duration_seconds is not None:
                payload["duration"] = duration_seconds
            if contact_id:
                payload["contact_id"] = contact_id
            if recording_url:
                payload["recording_url"] = recording_url
            if user_id:
                payload["user_id"] = user_id
            else:
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            # Create completed call activity via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/call/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result_data = response.json()

                logger.info(
                    f"Call logged directly in Close CRM: {result_data.get('id')} "
                    f"to {phone} - {result} ({duration_seconds}s)"
                )

                return {
                    "id": result_data.get("id"),
                    "status": result_data.get("status"),
                    "phone": phone,
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "duration": result_data.get("duration"),
                    "notes": result_data.get("note"),
                    "recording_url": result_data.get("recording_url"),
                    "created_at": result_data.get("date_created"),
                    "user_id": result_data.get("user_id"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Call logging API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to log call directly in Close: {e}")
            raise

    async def get_call_recording(
        self,
        activity_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get call recording URL and metadata for a call activity.

        Fetches the recording_url and related metadata for a completed call.
        Returns None if no recording is available for the call.

        Args:
            activity_id: Close call activity ID (e.g., "acti_xxx")

        Returns:
            Dict with recording details if available:
            {
                "activity_id": "acti_xxx",
                "recording_url": "https://...",
                "recording_duration": 180,
                "has_recording": True,
                "status": "answered",
                "direction": "outbound"
            }
            or None if no recording available

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/activity/call/{activity_id}/",
                    headers=self._get_headers(),
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                recording_url = data.get("recording_url")
                duration = data.get("duration")

                if recording_url:
                    logger.info(
                        f"Call recording found for activity {activity_id}: "
                        f"{duration}s duration"
                    )
                    return {
                        "activity_id": activity_id,
                        "recording_url": recording_url,
                        "recording_duration": duration,
                        "has_recording": True,
                        "status": data.get("status"),
                        "direction": data.get("direction"),
                        "phone": data.get("phone"),
                        "lead_id": data.get("lead_id"),
                        "contact_id": data.get("contact_id"),
                    }
                else:
                    logger.debug(f"No recording available for call activity {activity_id}")
                    return {
                        "activity_id": activity_id,
                        "recording_url": None,
                        "recording_duration": duration,
                        "has_recording": False,
                        "status": data.get("status"),
                        "direction": data.get("direction"),
                    }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Call recording API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to get call recording from Close: {e}")
            raise

    async def create_meeting(
        self,
        lead_id: str,
        contact_id: str,
        scheduled_at: datetime,
        duration_minutes: int = 30,
        title: Optional[str] = None,
        note: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a meeting activity in Close CRM.

        Creates a scheduled meeting associated with a lead and contact.
        Used for auto-creating meetings from MEETING_REQUEST email replies.

        Args:
            lead_id: Close lead ID (required)
            contact_id: Close contact ID (required)
            scheduled_at: Meeting start time (datetime, UTC)
            duration_minutes: Meeting duration in minutes (default 30)
            title: Meeting title (optional, defaults to "Discovery Call")
            note: Meeting notes or description (optional)
            user_id: Close user ID hosting the meeting (optional)

        Returns:
            Dict with meeting activity details:
            {
                "id": "acti_xxx",
                "lead_id": "lead_xxx",
                "contact_id": "cont_xxx",
                "starts_at": "2024-12-06T14:00:00Z",
                "ends_at": "2024-12-06T14:30:00Z",
                "duration": 1800,
                "title": "Discovery Call",
                "note": "...",
                "created_at": "2024-12-06T12:00:00Z"
            }

        Raises:
            RuntimeError: If CLOSE_WRITE_DISABLED is True
            httpx.HTTPStatusError: If API request fails
            ValueError: If required parameters missing
        """
        try:
            # Check if writes are disabled
            if os.getenv("CLOSE_WRITE_DISABLED", "False").lower() in ("true", "1", "yes"):
                logger.warning("CLOSE_WRITE_DISABLED: Skipping create_meeting()")
                return {"status": "disabled", "message": "Close CRM writes are disabled"}

            if not lead_id or not contact_id:
                raise ValueError("lead_id and contact_id are required")

            # Build meeting activity payload
            # Close API expects duration in seconds
            duration_seconds = duration_minutes * 60

            payload = {
                "lead_id": lead_id,
                "contact_id": contact_id,
                "starts_at": scheduled_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration": duration_seconds,
                "title": title or "Discovery Call",
            }

            # Add note if provided
            if note:
                payload["note"] = note

            # Set meeting host
            if user_id:
                payload["user_id"] = user_id
            else:
                default_owner = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
                if default_owner:
                    payload["user_id"] = default_owner

            # Create meeting activity via Close API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/activity/meeting/",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"Meeting created in Close CRM: {result.get('id')} "
                    f"for lead {lead_id} at {scheduled_at}"
                )

                return {
                    "id": result.get("id"),
                    "lead_id": lead_id,
                    "contact_id": contact_id,
                    "starts_at": result.get("starts_at"),
                    "ends_at": result.get("ends_at"),
                    "duration": result.get("duration"),
                    "title": result.get("title"),
                    "note": result.get("note"),
                    "user_id": result.get("user_id"),
                    "created_at": result.get("date_created"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Close Meeting API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to create meeting in Close: {e}")
            raise
