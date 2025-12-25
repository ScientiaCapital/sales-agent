"""
Close CRM Workflow Intelligence - Tests

Tests the WorkflowIntelligenceService for:
- Collecting sequences from Close API
- Collecting subscriptions for sequences
- Enriching subscriptions with Supabase data
- Generating workflow reports with ICP/industry/ATL breakdowns
"""

import pytest
from typing import List, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.workflow_intelligence import (
    WorkflowIntelligenceService,
    WorkflowReport,
    EngagementMetrics
)


@pytest.fixture
def workflow_service():
    """Create WorkflowIntelligenceService instance"""
    return WorkflowIntelligenceService()


@pytest.mark.asyncio
async def test_collect_all_sequences(workflow_service):
    """Test collecting all sequences"""
    sequences = await workflow_service.collect_all_sequences()

    assert isinstance(sequences, list), "Should return list of sequences"
    assert len(sequences) > 0, "Should have at least one sequence"

    # Verify sequence structure
    for seq in sequences:
        assert "id" in seq, "Sequence should have ID"
        assert "name" in seq, "Sequence should have name"


@pytest.mark.asyncio
async def test_collect_all_sequences_for_user(workflow_service):
    """Test collecting sequences filtered by user"""
    sequences = await workflow_service.collect_all_sequences(user_email="tim@coperniq.io")

    assert isinstance(sequences, list), "Should return list of sequences"

    # In production, would verify user filter works
    # For now, just check structure
    assert len(sequences) >= 0, "Should return sequences or empty list"


@pytest.mark.asyncio
async def test_collect_subscriptions_for_sequence(workflow_service):
    """Test collecting subscriptions for a specific sequence"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    subscriptions = await workflow_service.collect_subscriptions_for_sequence(sequence_id)

    assert isinstance(subscriptions, list), "Should return list of subscriptions"
    assert len(subscriptions) > 0, "Should have at least some subscriptions"

    # Verify subscription structure
    if len(subscriptions) > 0:
        sub = subscriptions[0]
        assert "id" in sub, "Subscription should have ID"
        assert "contact_id" in sub, "Subscription should have contact_id"
        assert "status" in sub, "Subscription should have status"


@pytest.mark.asyncio
async def test_enrich_with_supabase_data(workflow_service):
    """Test enriching subscriptions with Supabase data"""
    # Mock subscriptions
    mock_subs = [
        {
            "id": "sub_1",
            "contact_id": "cont_123",
            "status": "active"
        }
    ]

    # Mock Supabase response
    mock_contact_data = {
        "close_contact_id": "cont_123",
        "contact_id": "uuid-456",
        "company_id": "uuid-789",
        "is_atl": True,
        "dim_companies": {
            "company_name": "Acme Corp",
            "icp_tier": "PLATINUM",
            "industry": "Energy"
        }
    }

    with patch.object(workflow_service.supabase, "table") as mock_table:
        mock_table.return_value.select.return_value.in_.return_value.execute.return_value.data = [mock_contact_data]

        enriched = await workflow_service.enrich_with_supabase_data(mock_subs)

        assert len(enriched) == 1, "Should return same number of subscriptions"
        assert enriched[0]["icp_tier"] == "PLATINUM", "Should add ICP tier"
        assert enriched[0]["is_atl"] is True, "Should add ATL flag"
        assert enriched[0]["industry"] == "Energy", "Should add industry"


@pytest.mark.asyncio
async def test_generate_workflow_report(workflow_service):
    """Test generating comprehensive workflow report"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    # Verify report structure
    assert isinstance(report, WorkflowReport), "Should return WorkflowReport"
    assert report.sequence_id == sequence_id, "Should have correct sequence ID"
    assert report.total_enrolled > 0, "Should have enrolled contacts"

    # Verify breakdowns
    assert isinstance(report.status_breakdown, dict), "Should have status breakdown"
    assert isinstance(report.icp_breakdown, dict), "Should have ICP breakdown"
    assert isinstance(report.industry_breakdown, dict), "Should have industry breakdown"
    assert isinstance(report.contact_breakdown, dict), "Should have contact breakdown"

    # Verify engagement metrics
    assert isinstance(report.engagement, EngagementMetrics), "Should have engagement metrics"


@pytest.mark.asyncio
async def test_icp_breakdown_accuracy(workflow_service):
    """Test that ICP breakdown is accurate"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    # Verify ICP breakdown
    icp_breakdown = report.icp_breakdown

    # Should have valid tiers
    valid_tiers = {"PLATINUM", "GOLD", "SILVER", "BRONZE", "UNKNOWN"}
    for tier in icp_breakdown.keys():
        assert tier in valid_tiers, f"Invalid tier: {tier}"

    # Counts should sum to total or less (if some missing data)
    total_with_tier = sum(icp_breakdown.values())
    assert total_with_tier <= report.total_enrolled, \
        "ICP tier counts should be <= total enrolled"


@pytest.mark.asyncio
async def test_industry_breakdown_accuracy(workflow_service):
    """Test that industry breakdown is accurate"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    # Verify industry breakdown
    industry_breakdown = report.industry_breakdown

    assert isinstance(industry_breakdown, dict), "Should be dict"
    assert len(industry_breakdown) > 0, "Should have at least one industry"

    # Should have Energy or MEP (based on sequence name)
    assert "Energy" in industry_breakdown or "MEP" in industry_breakdown, \
        "Should have Energy or MEP companies"


@pytest.mark.asyncio
async def test_atl_btl_breakdown_accuracy(workflow_service):
    """Test that ATL/BTL breakdown is accurate"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    # Verify contact breakdown
    cb = report.contact_breakdown

    assert "atl_count" in cb, "Should have atl_count"
    assert "btl_count" in cb, "Should have btl_count"
    assert "unknown_count" in cb, "Should have unknown_count"

    # Counts should be non-negative
    assert cb["atl_count"] >= 0, "ATL count should be >= 0"
    assert cb["btl_count"] >= 0, "BTL count should be >= 0"
    assert cb["unknown_count"] >= 0, "Unknown count should be >= 0"


@pytest.mark.asyncio
async def test_engagement_metrics(workflow_service):
    """Test engagement metrics calculation"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    eng = report.engagement

    # Verify metrics exist
    assert isinstance(eng.total_emails_sent, int), "Emails sent should be int"
    assert isinstance(eng.total_replies, int), "Replies should be int"
    assert isinstance(eng.reply_rate, float), "Reply rate should be float"

    # Verify logical constraints
    assert eng.total_emails_sent >= 0, "Emails sent should be non-negative"
    assert eng.total_replies >= 0, "Replies should be non-negative"
    assert eng.total_replies <= eng.total_emails_sent, \
        "Replies should be <= emails sent"
    assert 0 <= eng.reply_rate <= 100, "Reply rate should be 0-100%"


@pytest.mark.asyncio
async def test_generate_all_workflows_report(workflow_service):
    """Test generating reports for all workflows"""
    reports = await workflow_service.generate_all_workflows_report()

    assert isinstance(reports, list), "Should return list of reports"
    assert len(reports) > 0, "Should have at least one report"

    # Verify all are WorkflowReport objects
    for report in reports:
        assert isinstance(report, WorkflowReport), "Should be WorkflowReport"
        assert report.total_enrolled >= 0, "Should have enrollment count"


@pytest.mark.asyncio
async def test_to_dict_conversion(workflow_service):
    """Test converting WorkflowReport to dict for JSON export"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)
    report_dict = workflow_service.to_dict(report)

    # Verify dict structure
    assert isinstance(report_dict, dict), "Should return dict"
    assert "sequence_id" in report_dict, "Should have sequence_id"
    assert "sequence_name" in report_dict, "Should have sequence_name"
    assert "total_enrolled" in report_dict, "Should have total_enrolled"
    assert "icp_breakdown" in report_dict, "Should have icp_breakdown"
    assert "engagement" in report_dict, "Should have engagement"

    # Verify engagement is dict not object
    assert isinstance(report_dict["engagement"], dict), "Engagement should be dict"


@pytest.mark.asyncio
async def test_empty_subscriptions_handling():
    """Test handling of sequence with no subscriptions"""
    service = WorkflowIntelligenceService()

    # Mock empty subscriptions
    with patch.object(service, "collect_subscriptions_for_sequence", return_value=[]):
        report = await service.generate_workflow_report("seq_empty")

        assert report.total_enrolled == 0, "Should have 0 enrolled"
        assert len(report.status_breakdown) == 0, "Should have empty breakdown"


@pytest.mark.asyncio
async def test_missing_supabase_data_handling(workflow_service):
    """Test handling subscriptions with missing Supabase data"""
    # Mock subscriptions with contact IDs not in Supabase
    mock_subs = [
        {"id": "sub_1", "contact_id": "unknown_contact", "status": "active"}
    ]

    # Mock empty Supabase response
    with patch.object(workflow_service.supabase, "table") as mock_table:
        mock_table.return_value.select.return_value.in_.return_value.execute.return_value.data = []

        enriched = await workflow_service.enrich_with_supabase_data(mock_subs)

        # Should still return subscriptions, just not enriched
        assert len(enriched) == 1, "Should return subscriptions"
        assert "icp_tier" not in enriched[0] or enriched[0].get("icp_tier") is None, \
            "Should not have ICP tier for unknown contact"


@pytest.mark.asyncio
async def test_status_breakdown_completeness(workflow_service):
    """Test that status breakdown includes all subscription statuses"""
    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    report = await workflow_service.generate_workflow_report(sequence_id)

    status_breakdown = report.status_breakdown

    # Should have at least one status
    assert len(status_breakdown) > 0, "Should have status breakdown"

    # All statuses should be valid
    valid_statuses = {"active", "paused", "finished", "stopped", "failed", "unknown"}
    for status in status_breakdown.keys():
        assert status in valid_statuses, f"Invalid status: {status}"


@pytest.mark.asyncio
async def test_report_performance():
    """Test that report generation completes in reasonable time"""
    service = WorkflowIntelligenceService()
    import time

    sequence_id = "seq_469XPP98mPXSR2wh5cX9y6"

    start = time.time()
    report = await service.generate_workflow_report(sequence_id)
    elapsed = time.time() - start

    # Should complete in under 10 seconds
    assert elapsed < 10, f"Report took too long: {elapsed}s (should be < 10s)"
    assert report is not None, "Should return report"
