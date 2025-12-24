"""
Close CRM Campaign Audit - Audit Service Logic Tests

Tests the CloseAuditService business logic for:
- Identifying NEW leads (not in Close CRM)
- Identifying LOADED leads (already in Close CRM)
- Cross-referencing Supabase with Close API
- Marking companies as loaded
"""

import pytest
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.close_audit_service import CloseAuditService


@pytest.fixture
def audit_service():
    """Create CloseAuditService instance"""
    return CloseAuditService()


@pytest.mark.asyncio
async def test_identify_new_leads_platinum(audit_service):
    """Test identifying PLATINUM companies NOT in Close CRM"""
    new_leads = await audit_service.get_new_leads(icp_tier="PLATINUM")

    assert isinstance(new_leads, list), "Should return list of leads"

    # Verify all have close_lead_id = NULL
    for lead in new_leads:
        assert lead["close_lead_id"] is None, \
            f"NEW lead should have close_lead_id=NULL, got {lead.get('close_lead_id')}"

        # All should have domain
        assert lead["domain"] is not None and lead["domain"] != "", \
            f"NEW lead should have valid domain, got {lead.get('domain')}"

        # All should be enriched
        assert lead["last_enriched_at"] is not None, \
            f"NEW lead should be enriched, got last_enriched_at={lead.get('last_enriched_at')}"

        # All should be PLATINUM tier
        assert lead["icp_tier"] == "PLATINUM", \
            f"Filtered for PLATINUM but got {lead.get('icp_tier')}"


@pytest.mark.asyncio
async def test_identify_new_leads_all_tiers(audit_service):
    """Test identifying NEW leads across all tiers"""
    new_leads = await audit_service.get_new_leads()  # No tier filter

    assert isinstance(new_leads, list), "Should return list of leads"

    # Verify all have close_lead_id = NULL
    for lead in new_leads:
        assert lead["close_lead_id"] is None, \
            "NEW lead should have close_lead_id=NULL"

        # All should have domain
        assert lead["domain"] is not None and lead["domain"] != "", \
            "NEW lead should have valid domain"


@pytest.mark.asyncio
async def test_identify_loaded_leads(audit_service):
    """Test identifying companies ALREADY in Close CRM"""
    loaded_leads = await audit_service.get_loaded_leads()

    assert isinstance(loaded_leads, list), "Should return list of leads"

    # All should have close_lead_id populated
    for lead in loaded_leads:
        assert lead["close_lead_id"] is not None, \
            "LOADED lead should have close_lead_id populated"
        assert isinstance(lead["close_lead_id"], str), \
            "close_lead_id should be string"
        assert lead["close_lead_id"].startswith("lead_"), \
            "Close lead IDs should start with 'lead_'"


@pytest.mark.asyncio
async def test_cross_reference_with_close(audit_service):
    """Test cross-referencing Supabase with Close CRM"""
    report = await audit_service.cross_reference()

    # Verify report structure
    assert isinstance(report, dict), "Should return dict report"
    assert "new_leads" in report, "Report should include new_leads"
    assert "loaded_leads" in report, "Report should include loaded_leads"
    assert "total_in_close" in report, "Report should include total_in_close"
    assert "total_in_supabase" in report, "Report should include total_in_supabase"

    # Verify counts
    assert isinstance(report["new_leads"], int), "new_leads should be int count"
    assert isinstance(report["loaded_leads"], int), "loaded_leads should be int count"
    assert isinstance(report["total_in_close"], int), "total_in_close should be int"
    assert isinstance(report["total_in_supabase"], int), "total_in_supabase should be int"

    # Logical constraints
    assert report["total_in_supabase"] >= report["loaded_leads"], \
        "Supabase total should be >= loaded leads count"

    assert report["new_leads"] + report["loaded_leads"] <= report["total_in_supabase"], \
        "NEW + LOADED should be <= total in Supabase"


@pytest.mark.asyncio
async def test_mark_loaded_companies(audit_service):
    """Test updating close_lead_id for loaded companies"""
    # This test requires database access
    # Will need to mock or use test database

    company_id = "test-uuid-123"
    close_lead_id = "lead_ABC123"

    result = await audit_service.mark_as_loaded(
        company_id=company_id,
        close_lead_id=close_lead_id
    )

    assert isinstance(result, bool), "Should return boolean success"
    # In real implementation, verify database was updated


@pytest.mark.asyncio
async def test_mark_loaded_validation():
    """Test that mark_as_loaded validates inputs"""
    service = CloseAuditService()

    # Test invalid UUID
    with pytest.raises(ValueError):
        await service.mark_as_loaded(
            company_id="not-a-uuid",
            close_lead_id="lead_123"
        )

    # Test invalid Close lead ID format
    with pytest.raises(ValueError):
        await service.mark_as_loaded(
            company_id="12345678-1234-1234-1234-123456789012",
            close_lead_id="invalid_format"
        )

    # Test null values
    with pytest.raises(ValueError):
        await service.mark_as_loaded(
            company_id=None,
            close_lead_id="lead_123"
        )


@pytest.mark.asyncio
async def test_get_new_leads_excludes_zero_contacts():
    """Test that get_new_leads can optionally exclude companies with 0 contacts"""
    service = CloseAuditService()

    # Get all new leads
    all_leads = await service.get_new_leads()

    # Get only leads with contacts
    leads_with_contacts = await service.get_new_leads(min_contacts=1)

    assert len(leads_with_contacts) <= len(all_leads), \
        "Filtered list should be <= unfiltered list"

    # Verify all have at least 1 contact
    for lead in leads_with_contacts:
        assert lead.get("contact_count", 0) >= 1, \
            f"Lead should have at least 1 contact, got {lead.get('contact_count')}"


@pytest.mark.asyncio
async def test_get_new_leads_filters_by_industry():
    """Test filtering NEW leads by industry"""
    service = CloseAuditService()

    # Get Energy companies
    energy_leads = await service.get_new_leads(industry="Energy")

    for lead in energy_leads:
        assert lead.get("industry") == "Energy", \
            f"Should only return Energy companies, got {lead.get('industry')}"

    # Get MEP companies
    mep_leads = await service.get_new_leads(industry="MEP")

    for lead in mep_leads:
        assert lead.get("industry") in ["MEP", "Mechanical", "Electrical", "Plumbing"], \
            f"Should only return MEP companies, got {lead.get('industry')}"


@pytest.mark.asyncio
async def test_cross_reference_respects_rate_limits():
    """Test that cross_reference doesn't hit Close API rate limits"""
    service = CloseAuditService()

    # Mock the Close API to track call count
    call_count = 0

    async def mock_api_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return []

    with patch.object(service, "_fetch_close_leads", side_effect=mock_api_call):
        await service.cross_reference()

        # Should batch/paginate intelligently
        # Close API allows 100 req/min
        assert call_count < 50, \
            f"Should not make excessive API calls: {call_count}"


@pytest.mark.asyncio
async def test_get_sequence_enrolled_companies():
    """Test getting companies enrolled in specific sequences"""
    service = CloseAuditService()

    sequence_ids = [
        "seq_469XPP98mPXSR2wh5cX9y6",  # ICP-Energy-Multitrade
        "seq_0FHFD0OQtDAOS8x40MIANW"   # Solar-Pivot-2026
    ]

    enrolled = await service.get_sequence_enrolled_companies(sequence_ids)

    assert isinstance(enrolled, list), "Should return list of companies"

    # Verify all have close_lead_id (they're in Close to be in a sequence)
    for company in enrolled:
        assert company["close_lead_id"] is not None, \
            "Companies in sequences must have close_lead_id"


@pytest.mark.asyncio
async def test_error_handling_supabase_connection():
    """Test graceful handling of Supabase connection errors"""
    service = CloseAuditService()

    # Mock Supabase failure
    with patch.object(service, "_query_supabase", side_effect=Exception("Connection failed")):
        with pytest.raises(Exception) as exc_info:
            await service.get_new_leads()

        assert "Connection failed" in str(exc_info.value) or "Supabase" in str(exc_info.value), \
            "Should propagate Supabase errors clearly"


@pytest.mark.asyncio
async def test_error_handling_close_api():
    """Test graceful handling of Close API errors"""
    service = CloseAuditService()

    # Mock Close API failure
    with patch.object(service, "_fetch_close_leads", side_effect=Exception("API Error 503")):
        with pytest.raises(Exception) as exc_info:
            await service.cross_reference()

        assert "API" in str(exc_info.value) or "Close" in str(exc_info.value), \
            "Should propagate Close API errors clearly"
