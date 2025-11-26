"""
Tests for LeadAuditService - Lead lifecycle audit trail.

Tests cover:
1. Event logging methods (log_event, log_qualification, etc.)
2. Query methods (get_lead_history, get_session_summary, etc.)
3. Deduplication decision logging
4. Error handling and edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from app.services.lead_audit_service import LeadAuditService
from app.models.lead_audit import LeadAuditEventType, LeadAuditStage, LeadAuditLog


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def audit_service(mock_db):
    """Create LeadAuditService with mock db."""
    return LeadAuditService(mock_db)


@pytest.fixture
def sample_lead_audit_log():
    """Create a sample LeadAuditLog for testing."""
    return LeadAuditLog(
        id=uuid4(),
        lead_id=uuid4(),
        company_name="Test Company",
        session_id="session_123",
        event_type=LeadAuditEventType.LEAD_QUALIFIED.value,
        stage=LeadAuditStage.QUALIFICATION.value,
        decision_data={"score": 85, "tier": "gold"},
        source_file="test.csv",
        source_row=5,
        created_at=datetime.utcnow(),
        created_by="system",
        latency_ms=150,
        cost_usd=Decimal("0.000006")
    )


# =========================================================================
# Test Event Logging
# =========================================================================

class TestLogEvent:
    """Tests for the generic log_event method."""

    @pytest.mark.asyncio
    async def test_log_event_success(self, audit_service, mock_db):
        """Test successful event logging."""
        result = await audit_service.log_event(
            session_id="session_123",
            company_name="Acme Corp",
            event_type=LeadAuditEventType.LEAD_QUALIFIED,
            stage=LeadAuditStage.QUALIFICATION.value,
            decision_data={"score": 85, "tier": "gold"},
            latency_ms=150,
            cost_usd=0.000006
        )

        # Verify db methods were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_event_with_source_tracking(self, audit_service, mock_db):
        """Test event logging with source file tracking."""
        await audit_service.log_event(
            session_id="session_123",
            company_name="Acme Corp",
            event_type=LeadAuditEventType.LEAD_IMPORTED,
            stage=LeadAuditStage.IMPORT.value,
            decision_data={"source_columns": ["name", "phone"]},
            source_file="leads_batch_001.csv",
            source_row=42
        )

        # Verify the model was created with source tracking
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.source_file == "leads_batch_001.csv"
        assert added_obj.source_row == 42

    @pytest.mark.asyncio
    async def test_log_event_rollback_on_error(self, audit_service, mock_db):
        """Test that errors trigger rollback."""
        mock_db.commit.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            await audit_service.log_event(
                session_id="session_123",
                company_name="Acme Corp",
                event_type=LeadAuditEventType.LEAD_QUALIFIED,
                stage=LeadAuditStage.QUALIFICATION.value,
                decision_data={}
            )

        mock_db.rollback.assert_awaited_once()


class TestConvenienceMethods:
    """Tests for convenience logging methods."""

    @pytest.mark.asyncio
    async def test_log_import(self, audit_service, mock_db):
        """Test log_import convenience method."""
        await audit_service.log_import(
            session_id="session_123",
            company_name="Test Co",
            source_file="batch.csv",
            source_row=10,
            decision_data={"oem_count": 3}
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.LEAD_IMPORTED.value
        assert added_obj.stage == LeadAuditStage.IMPORT.value

    @pytest.mark.asyncio
    async def test_log_qualification(self, audit_service, mock_db):
        """Test log_qualification convenience method."""
        await audit_service.log_qualification(
            session_id="session_123",
            company_name="Test Co",
            score=85.5,
            tier="gold",
            is_atl=True,
            decision_data={"website_found": True},
            latency_ms=500,
            cost_usd=0.000006
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.LEAD_QUALIFIED.value
        assert added_obj.decision_data["score"] == 85.5
        assert added_obj.decision_data["tier"] == "gold"
        assert added_obj.decision_data["is_atl"] is True

    @pytest.mark.asyncio
    async def test_log_enrichment(self, audit_service, mock_db):
        """Test log_enrichment convenience method."""
        await audit_service.log_enrichment(
            session_id="session_123",
            company_name="Test Co",
            sources_tried=["hunter", "apollo"],
            sources_succeeded=["hunter"],
            contacts_found=3,
            decision_data={"emails_found": 2},
            latency_ms=2000,
            cost_usd=0.01
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.LEAD_ENRICHED.value
        assert added_obj.decision_data["sources_tried"] == ["hunter", "apollo"]
        assert added_obj.decision_data["contacts_found"] == 3

    @pytest.mark.asyncio
    async def test_log_export(self, audit_service, mock_db):
        """Test log_export convenience method."""
        await audit_service.log_export(
            session_id="session_123",
            company_name="Test Co",
            output_file="output.csv",
            row_number=15,
            decision_data={"dedup_status": "create_new"}
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.LEAD_EXPORTED.value
        assert added_obj.decision_data["output_file"] == "output.csv"


class TestLogDedupDecision:
    """Tests for deduplication decision logging."""

    @pytest.mark.asyncio
    async def test_log_dedup_create_new(self, audit_service, mock_db):
        """Test logging create_new dedup decision."""
        await audit_service.log_dedup_decision(
            session_id="session_123",
            company_name="New Company",
            recommendation="create_new",
            company_confidence=0.0,
            contact_confidence=None,
            decision_data={"reason": "No match found"}
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.DEDUP_CREATE_NEW.value

    @pytest.mark.asyncio
    async def test_log_dedup_skip_duplicate(self, audit_service, mock_db):
        """Test logging skip_duplicate dedup decision."""
        await audit_service.log_dedup_decision(
            session_id="session_123",
            company_name="Existing Company",
            recommendation="skip_duplicate",
            company_confidence=92.5,
            contact_confidence=100.0,
            decision_data={
                "matched_lead_id": "lead_abc",
                "match_reasons": ["exact_email_match"]
            }
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.DEDUP_SKIP_DUPLICATE.value
        assert added_obj.decision_data["company_confidence"] == 92.5

    @pytest.mark.asyncio
    async def test_log_dedup_add_contact(self, audit_service, mock_db):
        """Test logging add_contact dedup decision."""
        await audit_service.log_dedup_decision(
            session_id="session_123",
            company_name="Existing Company",
            recommendation="add_contact_to_existing",
            company_confidence=95.0,
            contact_confidence=0.0,
            decision_data={"matched_lead_id": "lead_xyz"}
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.event_type == LeadAuditEventType.DEDUP_ADD_CONTACT.value


# =========================================================================
# Test Query Methods
# =========================================================================

class TestGetLeadHistory:
    """Tests for get_lead_history query method."""

    @pytest.mark.asyncio
    async def test_get_lead_history_by_company_name(self, audit_service, mock_db, sample_lead_audit_log):
        """Test querying lead history by company name."""
        # Setup mock to return sample data
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_lead_audit_log]
        mock_db.execute.return_value = mock_result

        history = await audit_service.get_lead_history(company_name="Test Company")

        assert len(history) == 1
        assert history[0].company_name == "Test Company"

    @pytest.mark.asyncio
    async def test_get_lead_history_requires_identifier(self, audit_service):
        """Test that get_lead_history requires company_name or lead_id."""
        with pytest.raises(ValueError, match="Must provide company_name or lead_id"):
            await audit_service.get_lead_history()


class TestGetSessionSummary:
    """Tests for get_session_summary query method."""

    @pytest.mark.asyncio
    async def test_get_session_summary_with_events(self, audit_service, mock_db):
        """Test session summary with events."""
        # Create sample events
        events = [
            LeadAuditLog(
                id=uuid4(),
                company_name="Company A",
                session_id="session_123",
                event_type=LeadAuditEventType.LEAD_QUALIFIED.value,
                stage=LeadAuditStage.QUALIFICATION.value,
                decision_data={},
                created_at=datetime.utcnow() - timedelta(minutes=5),
                latency_ms=100,
                cost_usd=Decimal("0.000006")
            ),
            LeadAuditLog(
                id=uuid4(),
                company_name="Company B",
                session_id="session_123",
                event_type=LeadAuditEventType.LEAD_ENRICHED.value,
                stage=LeadAuditStage.ENRICHMENT.value,
                decision_data={},
                created_at=datetime.utcnow(),
                latency_ms=200,
                cost_usd=Decimal("0.01")
            )
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_db.execute.return_value = mock_result

        summary = await audit_service.get_session_summary(session_id="session_123")

        assert summary["session_id"] == "session_123"
        assert summary["total_events"] == 2
        assert summary["companies_processed"] == 2
        assert summary["by_event_type"][LeadAuditEventType.LEAD_QUALIFIED.value] == 1
        assert summary["by_stage"][LeadAuditStage.ENRICHMENT.value] == 1

    @pytest.mark.asyncio
    async def test_get_session_summary_empty(self, audit_service, mock_db):
        """Test session summary with no events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        summary = await audit_service.get_session_summary(session_id="nonexistent")

        assert summary["total_events"] == 0
        assert summary["companies_processed"] == 0


class TestCheckRecentlyProcessed:
    """Tests for check_recently_processed method."""

    @pytest.mark.asyncio
    async def test_recently_processed_true(self, audit_service, mock_db):
        """Test when company was recently processed."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5  # 5 events found
        mock_db.execute.return_value = mock_result

        was_processed = await audit_service.check_recently_processed(
            company_name="Test Company",
            hours=24
        )

        assert was_processed is True

    @pytest.mark.asyncio
    async def test_recently_processed_false(self, audit_service, mock_db):
        """Test when company was NOT recently processed."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0  # No events found
        mock_db.execute.return_value = mock_result

        was_processed = await audit_service.check_recently_processed(
            company_name="New Company",
            hours=24
        )

        assert was_processed is False


class TestGetRecentActivity:
    """Tests for get_recent_activity method."""

    @pytest.mark.asyncio
    async def test_get_recent_activity_all(self, audit_service, mock_db, sample_lead_audit_log):
        """Test getting all recent activity."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_lead_audit_log]
        mock_db.execute.return_value = mock_result

        activity = await audit_service.get_recent_activity(hours=24)

        assert len(activity) == 1

    @pytest.mark.asyncio
    async def test_get_recent_activity_filtered(self, audit_service, mock_db):
        """Test getting recent activity with event type filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        activity = await audit_service.get_recent_activity(
            hours=24,
            event_types=["lead_qualified", "lead_enriched"]
        )

        # Should still call execute
        mock_db.execute.assert_awaited_once()


class TestGetDedupDecisions:
    """Tests for get_dedup_decisions method."""

    @pytest.mark.asyncio
    async def test_get_dedup_decisions(self, audit_service, mock_db):
        """Test getting all dedup decisions for a company."""
        dedup_event = LeadAuditLog(
            id=uuid4(),
            company_name="Test Company",
            session_id="session_123",
            event_type=LeadAuditEventType.DEDUP_SKIP_DUPLICATE.value,
            stage=LeadAuditStage.DEDUPLICATION.value,
            decision_data={"recommendation": "skip_duplicate"},
            created_at=datetime.utcnow()
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [dedup_event]
        mock_db.execute.return_value = mock_result

        decisions = await audit_service.get_dedup_decisions(company_name="Test Company")

        assert len(decisions) == 1
        assert "dedup" in decisions[0].event_type


# =========================================================================
# Test Edge Cases
# =========================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_log_event_with_none_cost(self, audit_service, mock_db):
        """Test logging event with None cost."""
        await audit_service.log_event(
            session_id="session_123",
            company_name="Test Co",
            event_type=LeadAuditEventType.LEAD_QUALIFIED,
            stage=LeadAuditStage.QUALIFICATION.value,
            decision_data={},
            cost_usd=None
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.cost_usd is None

    @pytest.mark.asyncio
    async def test_log_event_with_large_decision_data(self, audit_service, mock_db):
        """Test logging event with large decision_data JSON."""
        large_data = {
            "contacts": [{"name": f"Contact {i}", "email": f"contact{i}@test.com"}
                        for i in range(100)],
            "scoring_factors": {f"factor_{i}": i for i in range(50)}
        }

        await audit_service.log_event(
            session_id="session_123",
            company_name="Test Co",
            event_type=LeadAuditEventType.LEAD_ENRICHED,
            stage=LeadAuditStage.ENRICHMENT.value,
            decision_data=large_data
        )

        added_obj = mock_db.add.call_args[0][0]
        assert len(added_obj.decision_data["contacts"]) == 100
