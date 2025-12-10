"""Tests for TransferHandler."""

import pytest
from app.services.voice.handlers.transfer_handler import (
    TransferHandler,
    TRANSFER_DESTINATIONS
)
from app.services.voice.handlers.base import HandlerResponse


class TestTransferHandler:
    """Tests for transfer handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return TransferHandler()

    def test_init(self, handler):
        """Test handler initialization."""
        assert handler is not None
        assert handler.cerebras_service is None

    def test_init_with_cerebras_service(self):
        """Test handler with CerebrasService."""
        mock_service = object()
        handler = TransferHandler(cerebras_service=mock_service)
        assert handler.cerebras_service is mock_service

    def test_handle_transfer_request(self, handler):
        """Test handling basic transfer request."""
        response = handler.handle(
            transcript="Can I speak to someone?",
            conversation_history=[],
            lead_context=None
        )

        assert isinstance(response, HandlerResponse)
        assert response.response_text is not None
        assert response.should_transfer is True
        assert response.next_intent is None  # Transfer ends AI handling

    def test_transfer_to_sales(self, handler):
        """Test transfer routing to sales."""
        response = handler.handle(
            transcript="I want to discuss pricing with someone",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True
        assert response.transfer_destination is not None
        assert response.transfer_destination.get("name") == "Sales Team"

    def test_transfer_to_support(self, handler):
        """Test transfer routing to support."""
        response = handler.handle(
            transcript="I'm having a problem and need help",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True
        assert response.transfer_destination is not None
        assert response.transfer_destination.get("name") == "Customer Support"

    def test_transfer_to_billing(self, handler):
        """Test transfer routing to billing."""
        response = handler.handle(
            transcript="I have a question about my invoice",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True
        assert response.transfer_destination is not None
        assert response.transfer_destination.get("name") == "Billing Department"

    def test_default_transfer_to_sales(self, handler):
        """Test default transfer goes to sales."""
        response = handler.handle(
            transcript="Can I speak with a person please?",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True
        assert response.transfer_destination.get("name") == "Sales Team"

    def test_handoff_summary_generated(self, handler):
        """Test handoff summary is generated."""
        response = handler.handle(
            transcript="Transfer me please",
            conversation_history=[],
            lead_context=None
        )

        assert response.handoff_summary is not None
        assert len(response.handoff_summary) > 0

    def test_handoff_summary_includes_lead_context(self, handler):
        """Test handoff summary includes lead info."""
        lead_context = {
            "contact_name": "John Smith",
            "company": "Acme Corp",
            "email": "john@acme.com"
        }

        response = handler.handle(
            transcript="Can I speak to sales?",
            conversation_history=[],
            lead_context=lead_context
        )

        assert "John Smith" in response.handoff_summary
        assert "Acme Corp" in response.handoff_summary
        assert "john@acme.com" in response.handoff_summary

    def test_handoff_summary_includes_conversation_context(self, handler):
        """Test handoff summary includes conversation history."""
        history = [
            {"role": "user", "content": "I'm interested in your pricing plans"},
            {"role": "assistant", "content": "We have several options"},
            {"role": "user", "content": "I need something for enterprise use"}
        ]

        response = handler.handle(
            transcript="Let me talk to sales",
            conversation_history=history,
            lead_context=None
        )

        # Should include topics or recent context
        assert len(response.handoff_summary) > 0

    def test_transfer_announcement_is_natural(self, handler):
        """Test transfer announcement sounds natural."""
        response = handler.handle(
            transcript="Transfer me to sales",
            conversation_history=[],
            lead_context=None
        )

        # Should be conversational
        assert "connect" in response.response_text.lower() or "transfer" in response.response_text.lower()
        # Should mention the team
        assert "sales" in response.response_text.lower() or "team" in response.response_text.lower()

    def test_response_is_tts_friendly(self, handler):
        """Test that responses are suitable for TTS."""
        response = handler.handle(
            transcript="Can I speak to someone?",
            conversation_history=[],
            lead_context=None
        )

        # No markdown or formatting
        assert "**" not in response.response_text
        assert "##" not in response.response_text
        assert "```" not in response.response_text
        assert "* " not in response.response_text

    def test_metadata_includes_transfer_info(self, handler):
        """Test metadata contains transfer details."""
        response = handler.handle(
            transcript="Transfer me to support",
            conversation_history=[],
            lead_context=None
        )

        assert response.metadata is not None
        assert response.metadata.get("transfer_initiated") is True
        assert response.metadata.get("destination_name") is not None
        assert response.metadata.get("destination_extension") is not None

    def test_data_includes_transfer_type(self, handler):
        """Test data includes transfer type."""
        response = handler.handle(
            transcript="I need to speak with someone",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("transfer_type") == "warm"

    def test_get_transfer_destinations(self, handler):
        """Test getting available destinations."""
        destinations = handler.get_transfer_destinations()

        assert "sales" in destinations
        assert "support" in destinations
        assert "billing" in destinations
        assert "general" in destinations

    def test_conversation_history_influences_routing(self, handler):
        """Test routing based on conversation history."""
        history = [
            {"role": "user", "content": "My account is being charged incorrectly"},
            {"role": "assistant", "content": "I'm sorry to hear that"},
            {"role": "user", "content": "I need a refund"}
        ]

        response = handler.handle(
            transcript="Let me talk to someone",
            conversation_history=history,
            lead_context=None
        )

        # Should route to billing based on history
        assert response.transfer_destination.get("name") == "Billing Department"

    def test_topic_extraction_pricing(self, handler):
        """Test topic extraction for pricing."""
        history = [
            {"role": "user", "content": "What's the price of your enterprise plan?"}
        ]

        response = handler.handle(
            transcript="Transfer me",
            conversation_history=history,
            lead_context=None
        )

        # Topics should be extracted
        assert "pricing" in response.handoff_summary.lower() or len(response.handoff_summary) > 10

    def test_topic_extraction_demo(self, handler):
        """Test topic extraction for demo."""
        history = [
            {"role": "user", "content": "I'd like to see a demo of your product"}
        ]

        response = handler.handle(
            transcript="Can I speak to someone?",
            conversation_history=history,
            lead_context=None
        )

        assert len(response.handoff_summary) > 0


class TestTransferDestinations:
    """Tests for transfer destination configuration."""

    def test_all_destinations_have_required_fields(self):
        """Test all destinations have name, extension, description."""
        for key, dest in TRANSFER_DESTINATIONS.items():
            assert "name" in dest, f"Missing name for {key}"
            assert "extension" in dest, f"Missing extension for {key}"
            assert "description" in dest, f"Missing description for {key}"

    def test_extensions_are_valid(self):
        """Test extensions are valid strings."""
        for key, dest in TRANSFER_DESTINATIONS.items():
            ext = dest["extension"]
            assert isinstance(ext, str)
            assert len(ext) > 0

    def test_sales_destination_exists(self):
        """Test sales destination is configured."""
        assert "sales" in TRANSFER_DESTINATIONS
        assert TRANSFER_DESTINATIONS["sales"]["name"] == "Sales Team"

    def test_support_destination_exists(self):
        """Test support destination is configured."""
        assert "support" in TRANSFER_DESTINATIONS
        assert TRANSFER_DESTINATIONS["support"]["name"] == "Customer Support"

    def test_billing_destination_exists(self):
        """Test billing destination is configured."""
        assert "billing" in TRANSFER_DESTINATIONS
        assert TRANSFER_DESTINATIONS["billing"]["name"] == "Billing Department"

    def test_general_destination_exists(self):
        """Test general destination is configured."""
        assert "general" in TRANSFER_DESTINATIONS
        assert "0" in TRANSFER_DESTINATIONS["general"]["extension"]


class TestTransferEdgeCases:
    """Tests for edge cases in transfer handling."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return TransferHandler()

    def test_empty_conversation_history(self, handler):
        """Test handling with empty history."""
        response = handler.handle(
            transcript="Transfer me",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True
        assert response.handoff_summary is not None

    def test_none_lead_context(self, handler):
        """Test handling with None lead context."""
        response = handler.handle(
            transcript="Transfer me",
            conversation_history=[],
            lead_context=None
        )

        assert response.should_transfer is True

    def test_empty_lead_context(self, handler):
        """Test handling with empty lead context."""
        response = handler.handle(
            transcript="Transfer me",
            conversation_history=[],
            lead_context={}
        )

        assert response.should_transfer is True

    def test_partial_lead_context(self, handler):
        """Test handling with partial lead context."""
        lead_context = {
            "contact_name": "Jane"
            # Missing company and email
        }

        response = handler.handle(
            transcript="Transfer me",
            conversation_history=[],
            lead_context=lead_context
        )

        assert response.should_transfer is True
        assert "Jane" in response.handoff_summary

    def test_long_conversation_history(self, handler):
        """Test handling with long conversation history."""
        history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]

        response = handler.handle(
            transcript="Transfer me now",
            conversation_history=history,
            lead_context=None
        )

        assert response.should_transfer is True
        # Should not crash with long history
