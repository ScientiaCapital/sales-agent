"""Tests for sales-agent plugin tools.

TDD: Write tests first, then implement.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOutreachTool:
    """Test OutreachTool for sending sales outreach."""

    def test_tool_definition(self):
        """Tool has correct definition."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()
        defn = tool.definition

        assert defn.name == "outreach_send"
        assert "outreach" in defn.description.lower()
        assert defn.parameters["required"] == ["lead_id", "channel"]
        assert "lead_id" in defn.parameters["properties"]
        assert "channel" in defn.parameters["properties"]
        assert "email" in defn.parameters["properties"]
        assert "sequence" in defn.parameters["properties"]["channel"]["enum"]

    @pytest.mark.asyncio
    async def test_send_email_outreach(self):
        """Can send email outreach via SendGrid."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()

        with patch.object(tool, "_send_email") as mock_send:
            mock_send.return_value = {
                "message_id": "msg-123",
                "channel": "email",
                "status": "sent",
                "cost_usd": 0.00025,
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "channel": "email",
                "email": "test@example.com",
                "subject": "Quick question",
                "custom_message": "Hello!",
            })

        assert result.success is True
        assert result.result["message_id"] == "msg-123"
        assert result.result["status"] == "sent"
        assert result.result["cost_usd"] == 0.00025

    @pytest.mark.asyncio
    async def test_send_sms_outreach(self):
        """Can send SMS outreach via Twilio."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()

        with patch.object(tool, "_send_sms") as mock_send:
            mock_send.return_value = {
                "message_id": "sms-456",
                "channel": "sms",
                "status": "sent",
                "segments": 1,
                "cost_usd": 0.0079,
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "channel": "sms",
                "phone": "+15551234567",
                "custom_message": "Hi there!",
            })

        assert result.success is True
        assert result.result["channel"] == "sms"
        assert result.result["segments"] == 1

    @pytest.mark.asyncio
    async def test_enroll_sequence(self):
        """Can enroll lead in cold-reach email sequence."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()

        with patch.object(tool, "_enroll_sequence") as mock_enroll:
            mock_enroll.return_value = {
                "enrollment_id": "seq-abc123",
                "channel": "sequence",
                "sequence_name": "high_priority_solar",
                "status": "enrolled",
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "channel": "sequence",
                "email": "test@example.com",
                "company_name": "ABC Solar",
                "tier": "A",
            })

        assert result.success is True
        assert result.result["status"] == "enrolled"
        assert result.result["sequence_name"] == "high_priority_solar"

    @pytest.mark.asyncio
    async def test_queue_linkedin(self):
        """LinkedIn queues for manual action."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()

        result = await tool.run({
            "lead_id": "lead-abc",
            "channel": "linkedin",
            "company_name": "ABC Solar",
        })

        assert result.success is True
        assert result.result["status"] == "queued"
        assert result.result["action_required"] == "manual"

    @pytest.mark.asyncio
    async def test_email_requires_email_field(self):
        """Email channel requires email field."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()
        result = await tool.run({
            "lead_id": "lead-abc",
            "channel": "email",
            # Missing email field
        })

        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_sms_requires_phone(self):
        """SMS channel requires phone field."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()
        result = await tool.run({
            "lead_id": "lead-abc",
            "channel": "sms",
            # Missing phone field
        })

        assert result.success is False
        assert "phone" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_channel_fails(self):
        """Invalid channel returns error."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()
        result = await tool.run({
            "lead_id": "lead-abc",
            "channel": "carrier_pigeon",
        })

        assert result.success is False
        assert "channel" in result.error.lower()

    @pytest.mark.asyncio
    async def test_service_unavailable_graceful(self):
        """Handles service unavailable gracefully."""
        from plugins.sales_tools.outreach import OutreachTool

        tool = OutreachTool()

        with patch.object(tool, "_send_email") as mock_send:
            mock_send.return_value = {
                "status": "service_unavailable",
                "error": "DeliveryService not available",
                "fallback": True,
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "channel": "email",
                "email": "test@example.com",
            })

        # Should still return result, just with unavailable status
        assert result.result["status"] == "service_unavailable"
        assert result.result["fallback"] is True


class TestQualifyTool:
    """Test QualifyTool for lead qualification."""

    def test_tool_definition(self):
        """Tool has correct definition."""
        from plugins.sales_tools.qualify import QualifyTool

        tool = QualifyTool()
        defn = tool.definition

        assert defn.name == "lead_qualify"
        assert "qualify" in defn.description.lower() or "score" in defn.description.lower()
        assert defn.parameters["required"] == ["lead_id"]
        assert "lead_id" in defn.parameters["properties"]

    @pytest.mark.asyncio
    async def test_qualify_lead_success(self):
        """Can qualify a lead and get score."""
        from plugins.sales_tools.qualify import QualifyTool

        tool = QualifyTool()

        with patch.object(tool, "_score_lead") as mock_score:
            mock_score.return_value = {
                "lead_id": "lead-abc",
                "score": 85,
                "qualified": True,
                "reasons": ["Employee count > 50", "Revenue > $1M"],
            }

            result = await tool.run({"lead_id": "lead-abc"})

        assert result.success is True
        assert result.result["score"] == 85
        assert result.result["qualified"] is True
        assert len(result.result["reasons"]) > 0

    @pytest.mark.asyncio
    async def test_qualify_with_enrichment_data(self):
        """Can qualify with additional enrichment data."""
        from plugins.sales_tools.qualify import QualifyTool

        tool = QualifyTool()

        with patch.object(tool, "_score_lead") as mock_score:
            mock_score.return_value = {
                "lead_id": "lead-xyz",
                "score": 92,
                "qualified": True,
                "reasons": ["Has valid license", "Multiple locations"],
            }

            result = await tool.run({
                "lead_id": "lead-xyz",
                "enrichment_data": {
                    "employee_count": 75,
                    "revenue_range": "$5M-$10M",
                },
            })

        assert result.success is True
        assert result.result["score"] == 92

    @pytest.mark.asyncio
    async def test_lead_not_found(self):
        """Missing lead returns error."""
        from plugins.sales_tools.qualify import QualifyTool

        tool = QualifyTool()

        with patch.object(tool, "_score_lead") as mock_score:
            mock_score.return_value = None

            result = await tool.run({"lead_id": "nonexistent"})

        assert result.success is False
        assert "not found" in result.error.lower()


class TestCRMSyncTool:
    """Test CRMSyncTool for CRM synchronization."""

    def test_tool_definition(self):
        """Tool has correct definition."""
        from plugins.sales_tools.crm_sync import CRMSyncTool

        tool = CRMSyncTool()
        defn = tool.definition

        assert defn.name == "crm_sync"
        assert "crm" in defn.description.lower()
        assert defn.parameters["required"] == ["lead_id", "crm"]
        assert "lead_id" in defn.parameters["properties"]
        assert "crm" in defn.parameters["properties"]
        assert "close" in defn.parameters["properties"]["crm"]["enum"]

    @pytest.mark.asyncio
    async def test_sync_to_close_crm(self):
        """Can sync lead to Close CRM."""
        from plugins.sales_tools.crm_sync import CRMSyncTool

        tool = CRMSyncTool()

        with patch.object(tool, "_sync_to_crm") as mock_sync:
            mock_sync.return_value = {
                "crm": "close",
                "crm_id": "lead_abc123",
                "status": "created",
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "crm": "close",
            })

        assert result.success is True
        assert result.result["crm"] == "close"
        assert result.result["status"] == "created"

    @pytest.mark.asyncio
    async def test_sync_to_hubspot(self):
        """Can sync lead to HubSpot."""
        from plugins.sales_tools.crm_sync import CRMSyncTool

        tool = CRMSyncTool()

        with patch.object(tool, "_sync_to_crm") as mock_sync:
            mock_sync.return_value = {
                "crm": "hubspot",
                "crm_id": "hs-contact-789",
                "status": "updated",
            }

            result = await tool.run({
                "lead_id": "lead-abc",
                "crm": "hubspot",
            })

        assert result.success is True
        assert result.result["crm"] == "hubspot"

    @pytest.mark.asyncio
    async def test_invalid_crm_fails(self):
        """Invalid CRM returns error."""
        from plugins.sales_tools.crm_sync import CRMSyncTool

        tool = CRMSyncTool()
        result = await tool.run({
            "lead_id": "lead-abc",
            "crm": "salesforce",  # Not supported
        })

        assert result.success is False
        assert "crm" in result.error.lower()


class TestPluginRegistration:
    """Test plugin registration with conductor-ai."""

    def test_register_function_exists(self):
        """Plugin has register function."""
        from plugins.sales_tools import register

        assert callable(register)

    def test_register_adds_tools(self):
        """Register adds all tools to registry."""
        from plugins.sales_tools import register

        mock_registry = MagicMock()
        register(mock_registry)

        assert mock_registry.register.call_count == 3

    def test_all_exports(self):
        """Module exports all tools."""
        from plugins.sales_tools import (
            OutreachTool,
            QualifyTool,
            CRMSyncTool,
            register,
        )

        assert OutreachTool is not None
        assert QualifyTool is not None
        assert CRMSyncTool is not None
        assert register is not None
