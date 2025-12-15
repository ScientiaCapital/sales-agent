"""Tests for Calendly integration."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.calling.integrations.calendly import (
    CalendlyClient,
    CalendlyBooking,
    TimeSlot,
    get_calendly_link,
)


class TestCalendlyBooking:
    """Tests for CalendlyBooking dataclass."""

    def test_successful_booking(self):
        """Should create successful booking result."""
        booking = CalendlyBooking(
            success=True,
            event_uri="https://api.calendly.com/events/123",
            scheduled_time="2024-12-17T14:00:00Z",
            join_url="https://calendly.com/events/123",
        )
        assert booking.success is True
        assert booking.error is None

    def test_failed_booking(self):
        """Should create failed booking result."""
        booking = CalendlyBooking(
            success=False,
            error="No available times",
        )
        assert booking.success is False
        assert booking.error == "No available times"


class TestTimeSlot:
    """Tests for TimeSlot dataclass."""

    def test_time_slot_creation(self):
        """Should create time slot with times."""
        slot = TimeSlot(
            start_time="2024-12-17T14:00:00Z",
            end_time="2024-12-17T14:30:00Z",
        )
        assert slot.start_time == "2024-12-17T14:00:00Z"
        assert slot.status == "available"


class TestCalendlyClient:
    """Tests for CalendlyClient class."""

    def test_client_initializes_with_default_url(self):
        """Should use default Coperniq Calendly URL."""
        client = CalendlyClient()
        assert "coperniq-sales" in client.scheduling_url
        assert "disco" in client.scheduling_url

    def test_client_initializes_with_custom_url(self):
        """Should accept custom scheduling URL."""
        client = CalendlyClient(scheduling_url="https://calendly.com/custom/event")
        assert client.scheduling_url == "https://calendly.com/custom/event"

    @patch.dict("os.environ", {"CALENDLY_API_KEY": "test_key"})
    def test_client_reads_api_key_from_env(self):
        """Should read API key from environment."""
        client = CalendlyClient()
        assert client.api_key == "test_key"

    def test_get_booking_link_basic(self):
        """Should return scheduling URL."""
        client = CalendlyClient()
        link = client.get_booking_link()
        assert link == client.scheduling_url

    def test_get_booking_link_with_prefill_name(self):
        """Should add name prefill param."""
        client = CalendlyClient()
        link = client.get_booking_link(prefill_name="John Smith")
        assert "name=John%20Smith" in link

    def test_get_booking_link_with_prefill_email(self):
        """Should add email prefill param."""
        client = CalendlyClient()
        link = client.get_booking_link(prefill_email="john@example.com")
        assert "email=john@example.com" in link

    def test_get_booking_link_with_both_prefills(self):
        """Should add both name and email prefills."""
        client = CalendlyClient()
        link = client.get_booking_link(
            prefill_name="John Smith",
            prefill_email="john@example.com",
        )
        assert "name=John%20Smith" in link
        assert "email=john@example.com" in link
        assert "?" in link
        assert "&" in link

    @pytest.mark.asyncio
    async def test_get_current_user_requires_api_key(self):
        """Should raise error without API key."""
        client = CalendlyClient()
        client.api_key = None

        with pytest.raises(RuntimeError, match="API key not configured"):
            await client.get_current_user()

    @pytest.mark.asyncio
    async def test_get_availability_returns_empty_without_event_type(self):
        """Should return empty list when no event type configured."""
        client = CalendlyClient(api_key="test_key")

        with patch.object(client, "get_event_types", new_callable=AsyncMock) as mock_types:
            mock_types.return_value = []

            slots = await client.get_availability()

            assert slots == []

    @pytest.mark.asyncio
    async def test_create_booking_returns_link_without_event_type(self):
        """Should return error when no event type configured."""
        client = CalendlyClient(api_key="test_key")

        with patch.object(client, "get_event_types", new_callable=AsyncMock) as mock_types:
            mock_types.return_value = []

            result = await client.create_booking(
                invitee_email="john@example.com",
                invitee_name="John Smith",
                start_time="2024-12-17T14:00:00Z",
            )

            assert result.success is False
            assert "No event type" in result.error

    @pytest.mark.asyncio
    async def test_create_booking_returns_link_on_success(self):
        """Should return booking link on success."""
        client = CalendlyClient(api_key="test_key")
        client.event_type_uri = "https://api.calendly.com/event_types/123"

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "resource": {
                    "booking_url": "https://calendly.com/booking/abc123",
                }
            }

            result = await client.create_booking(
                invitee_email="john@example.com",
                invitee_name="John Smith",
                start_time="2024-12-17T14:00:00Z",
            )

            assert result.success is True
            assert result.join_url == "https://calendly.com/booking/abc123"


class TestGetCalendlyLinkHelper:
    """Tests for get_calendly_link helper function."""

    def test_returns_prefilled_link(self):
        """Should return Calendly link with prefills."""
        link = get_calendly_link(
            lead_name="John Smith",
            lead_email="john@example.com",
        )
        assert "coperniq-sales" in link
        assert "John%20Smith" in link
        assert "john@example.com" in link

    def test_works_without_email(self):
        """Should work with just name."""
        link = get_calendly_link(lead_name="John Smith")
        assert "John%20Smith" in link

    def test_uses_custom_url(self):
        """Should accept custom scheduling URL."""
        link = get_calendly_link(
            lead_name="John",
            scheduling_url="https://calendly.com/custom/event",
        )
        assert "custom/event" in link
