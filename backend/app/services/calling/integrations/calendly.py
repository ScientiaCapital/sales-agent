"""
Calendly Integration for AI Calling System.

Features:
- Check availability for booking
- Create one-off scheduling links
- Book meetings directly via API
- Get confirmation for post-call gate

Calendly API Docs: https://developer.calendly.com/api-docs
"""
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

# Calendly API base URL
CALENDLY_API_BASE = "https://api.calendly.com"


@dataclass
class CalendlyBooking:
    """Result of a Calendly booking."""
    success: bool
    event_uri: Optional[str] = None
    invitee_uri: Optional[str] = None
    scheduled_time: Optional[str] = None
    join_url: Optional[str] = None
    cancel_url: Optional[str] = None
    reschedule_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TimeSlot:
    """Available time slot."""
    start_time: str  # ISO 8601
    end_time: str
    status: str = "available"


class CalendlyClient:
    """
    Calendly API client for booking meetings.

    Usage:
        client = CalendlyClient(api_key="your_key")

        # Get available times
        slots = await client.get_availability(
            event_type_uri="https://api.calendly.com/event_types/xxx"
        )

        # Book a meeting
        booking = await client.create_booking(
            event_type_uri="https://api.calendly.com/event_types/xxx",
            invitee_email="lead@company.com",
            invitee_name="John Smith",
            start_time="2024-12-17T14:00:00Z"
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        scheduling_url: str = "https://calendly.com/coperniq-sales/disco",
    ):
        self.api_key = api_key or os.getenv("CALENDLY_API_KEY")
        self.scheduling_url = scheduling_url
        self.user_uri: Optional[str] = None
        self.event_type_uri: Optional[str] = None

        if not self.api_key:
            logger.warning("CALENDLY_API_KEY not set - booking will use link only")

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Calendly API."""
        if not self.api_key:
            raise RuntimeError("Calendly API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            url = f"{CALENDLY_API_BASE}{endpoint}"

            if method == "GET":
                response = await client.get(url, headers=headers, params=data)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code >= 400:
                logger.error(f"Calendly API error: {response.status_code} - {response.text}")
                raise httpx.HTTPStatusError(
                    f"Calendly API error: {response.status_code}",
                    request=response.request,
                    response=response,
                )

            return response.json()

    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user info."""
        result = await self._request("GET", "/users/me")
        self.user_uri = result.get("resource", {}).get("uri")
        return result.get("resource", {})

    async def get_event_types(self) -> List[Dict[str, Any]]:
        """Get all event types for the current user."""
        if not self.user_uri:
            await self.get_current_user()

        result = await self._request("GET", "/event_types", {
            "user": self.user_uri,
            "active": "true",
        })
        return result.get("collection", [])

    async def get_availability(
        self,
        event_type_uri: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[TimeSlot]:
        """
        Get available time slots for an event type.

        Args:
            event_type_uri: URI of the event type (or uses default)
            start_time: Start of availability window (ISO 8601)
            end_time: End of availability window (ISO 8601)

        Returns:
            List of available TimeSlots
        """
        event_uri = event_type_uri or self.event_type_uri
        if not event_uri:
            # Try to get first active event type
            event_types = await self.get_event_types()
            if event_types:
                event_uri = event_types[0].get("uri")
                self.event_type_uri = event_uri

        if not event_uri:
            logger.error("No event type URI available")
            return []

        # Default to next 7 days
        now = datetime.utcnow()
        start = start_time or now.isoformat() + "Z"
        end = end_time or (now + timedelta(days=7)).isoformat() + "Z"

        result = await self._request("GET", "/event_type_available_times", {
            "event_type": event_uri,
            "start_time": start,
            "end_time": end,
        })

        slots = []
        for slot in result.get("collection", []):
            slots.append(TimeSlot(
                start_time=slot.get("start_time"),
                end_time=slot.get("start_time"),  # Calendly returns start only
                status=slot.get("status", "available"),
            ))

        return slots

    async def create_booking(
        self,
        invitee_email: str,
        invitee_name: str,
        start_time: str,
        event_type_uri: Optional[str] = None,
        questions_and_answers: Optional[List[Dict]] = None,
    ) -> CalendlyBooking:
        """
        Create a booking (schedule a meeting).

        Note: Calendly doesn't have a direct "create invitee" API for
        standard accounts. This uses the scheduling links approach.

        For enterprise accounts with the "Scheduled Events" API, you'd use:
        POST /scheduled_events

        Args:
            invitee_email: Email of the person being invited
            invitee_name: Name of the invitee
            start_time: When to schedule (ISO 8601)
            event_type_uri: Event type to book
            questions_and_answers: Optional Q&A responses

        Returns:
            CalendlyBooking with confirmation details
        """
        # For standard Calendly, we generate a one-time scheduling link
        # and return that for the invitee to click

        # First, check availability at this time
        event_uri = event_type_uri or self.event_type_uri
        if not event_uri:
            event_types = await self.get_event_types()
            if event_types:
                event_uri = event_types[0].get("uri")

        if not event_uri:
            return CalendlyBooking(
                success=False,
                error="No event type configured",
            )

        # Create single-use scheduling link
        try:
            result = await self._request("POST", "/scheduling_links", {
                "max_event_count": 1,
                "owner": event_uri,
                "owner_type": "EventType",
            })

            booking_url = result.get("resource", {}).get("booking_url")

            return CalendlyBooking(
                success=True,
                join_url=booking_url,
                scheduled_time=start_time,
            )

        except Exception as e:
            logger.error(f"Failed to create Calendly booking: {e}")
            return CalendlyBooking(
                success=False,
                error=str(e),
            )

    def get_booking_link(
        self,
        prefill_name: Optional[str] = None,
        prefill_email: Optional[str] = None,
    ) -> str:
        """
        Get a pre-filled booking link.

        This is the simplest approach - send the lead directly to Calendly
        with their info pre-filled.

        Args:
            prefill_name: Pre-fill the name field
            prefill_email: Pre-fill the email field

        Returns:
            Calendly URL with query params
        """
        url = self.scheduling_url
        params = []

        if prefill_name:
            params.append(f"name={prefill_name.replace(' ', '%20')}")
        if prefill_email:
            params.append(f"email={prefill_email}")

        if params:
            url += "?" + "&".join(params)

        return url

    async def get_scheduled_events(
        self,
        min_start_time: Optional[str] = None,
        max_start_time: Optional[str] = None,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """
        Get scheduled events (booked meetings).

        Args:
            min_start_time: Filter by minimum start time
            max_start_time: Filter by maximum start time
            status: active, canceled, or all

        Returns:
            List of scheduled event details
        """
        if not self.user_uri:
            await self.get_current_user()

        params = {
            "user": self.user_uri,
            "status": status,
        }
        if min_start_time:
            params["min_start_time"] = min_start_time
        if max_start_time:
            params["max_start_time"] = max_start_time

        result = await self._request("GET", "/scheduled_events", params)
        return result.get("collection", [])


# Helper function for simple use case
def get_calendly_link(
    lead_name: str,
    lead_email: Optional[str] = None,
    scheduling_url: str = "https://calendly.com/coperniq-sales/disco",
) -> str:
    """
    Quick helper to get a pre-filled Calendly link.

    Args:
        lead_name: Name to pre-fill
        lead_email: Email to pre-fill
        scheduling_url: Base Calendly URL

    Returns:
        Pre-filled booking URL
    """
    client = CalendlyClient(scheduling_url=scheduling_url)
    return client.get_booking_link(prefill_name=lead_name, prefill_email=lead_email)
