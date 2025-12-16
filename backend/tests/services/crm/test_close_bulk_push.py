"""
TDD Tests for Close Bulk Push Service (RED Phase)

Tests for CloseBulkPushService that pushes enriched leads from Supabase to Close CRM.
These tests follow TDD - they should FAIL initially until the service is implemented.

Test Coverage:
- Lead creation with multiple contacts
- Dry-run mode (no actual writes)
- Duplicate detection and skipping
- ATL filtering (Above The Line contacts only)
- Error handling and retry logic
- Batch processing and rate limiting
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# Import will fail initially - that's expected in RED phase
from app.services.crm.close_bulk_push import (
    CloseBulkPushService,
    BulkPushResult,
    LeadPushResult
)


# ========== Fixtures ==========

@pytest.fixture
def mock_close_provider():
    """Mock CloseProvider for testing bulk push service."""
    provider = AsyncMock()

    # Mock create_lead to return success
    provider.create_lead = AsyncMock(return_value={
        "id": "lead_test123",
        "company": "Test Electric Co",
        "status": "created",
        "contacts_created": 1
    })

    # Mock add_contact_to_lead
    provider.add_contact_to_lead = AsyncMock(return_value={
        "id": "cont_test456",
        "name": "Test Contact",
        "email": "test@example.com"
    })

    return provider


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = AsyncMock()

    # Mock query methods
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def sample_leads_data() -> List[Dict[str, Any]]:
    """
    Sample enriched leads data from Supabase.

    Structure matches what we get from lead enrichment pipeline:
    - company_name, domain
    - contacts array with ATL/BTL designation
    - qualification scores, industry, etc.
    """
    return [
        {
            "company_name": "Test Electric Co",
            "domain": "testelectric.com",
            "industry": "Electrical Contractors",
            "qualification_score": 85,
            "contacts": [
                {
                    "name": "John Owner",
                    "first_name": "John",
                    "last_name": "Owner",
                    "title": "Owner",
                    "email": "john@testelectric.com",
                    "phone": "555-1234",
                    "is_atl": True,
                    "position": "Owner"
                },
                {
                    "name": "Jane Manager",
                    "first_name": "Jane",
                    "last_name": "Manager",
                    "title": "Operations Manager",
                    "email": "jane@testelectric.com",
                    "phone": "555-1235",
                    "is_atl": True,
                    "position": "Operations Manager"
                },
                {
                    "name": "Bob Tech",
                    "first_name": "Bob",
                    "last_name": "Tech",
                    "title": "Technician",
                    "email": "bob@testelectric.com",
                    "is_atl": False,  # BTL contact
                    "position": "Technician"
                }
            ]
        },
        {
            "company_name": "HVAC Solutions Inc",
            "domain": "hvacsolutions.com",
            "industry": "HVAC Contractors",
            "qualification_score": 90,
            "contacts": [
                {
                    "name": "Sarah CEO",
                    "first_name": "Sarah",
                    "last_name": "CEO",
                    "title": "CEO",
                    "email": "sarah@hvacsolutions.com",
                    "phone": "555-9999",
                    "is_atl": True,
                    "position": "CEO"
                }
            ]
        }
    ]


@pytest.fixture
def bulk_push_service(mock_close_provider, mock_db_session):
    """Create CloseBulkPushService instance with mocked dependencies."""
    return CloseBulkPushService(
        close_provider=mock_close_provider,
        db_session=mock_db_session
    )


# ========== Test 1: Push leads creates lead with contacts ==========

@pytest.mark.asyncio
async def test_push_leads_creates_lead_with_contacts(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that push_leads creates Close lead with all ATL contacts.

    Expected behavior:
    - Create lead in Close CRM
    - Include only ATL contacts (by default)
    - Return success count and created lead IDs
    """
    # Execute: Call push_leads with test data
    result = await bulk_push_service.push_leads(
        leads_data=sample_leads_data,
        dry_run=False,
        atl_only=True
    )

    # Assert: Verify result structure
    assert isinstance(result, BulkPushResult)
    assert result.success_count == 2  # Both leads created
    assert result.failed_count == 0
    assert result.skipped_duplicates == 0
    assert result.total_leads == 2

    # Assert: create_lead was called twice (once per lead)
    assert mock_close_provider.create_lead.call_count == 2

    # Assert: First call had only ATL contacts (2 out of 3)
    first_call_args = mock_close_provider.create_lead.call_args_list[0]
    lead_data = first_call_args[1]["lead"]  # kwargs

    # Check contacts in lead data
    assert "_discovered_contacts" in lead_data
    discovered_contacts = lead_data["_discovered_contacts"]

    # Should have 2 ATL contacts (John and Jane, not Bob)
    assert len(discovered_contacts) == 2
    assert all(c.get("is_atl") for c in discovered_contacts)

    # Check contact names
    contact_names = {c["name"] for c in discovered_contacts}
    assert "John Owner" in contact_names
    assert "Jane Manager" in contact_names
    assert "Bob Tech" not in contact_names  # BTL excluded


@pytest.mark.asyncio
async def test_push_leads_includes_all_contacts_when_atl_only_false(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that push_leads includes ALL contacts when atl_only=False.
    """
    # Execute: Call push_leads with atl_only=False
    result = await bulk_push_service.push_leads(
        leads_data=sample_leads_data,
        dry_run=False,
        atl_only=False
    )

    # Assert: First lead should have all 3 contacts (ATL + BTL)
    first_call_args = mock_close_provider.create_lead.call_args_list[0]
    lead_data = first_call_args[1]["lead"]
    discovered_contacts = lead_data["_discovered_contacts"]

    assert len(discovered_contacts) == 3  # All contacts included

    contact_names = {c["name"] for c in discovered_contacts}
    assert "John Owner" in contact_names
    assert "Jane Manager" in contact_names
    assert "Bob Tech" in contact_names  # BTL included


# ========== Test 2: Dry-run mode doesn't create actual leads ==========

@pytest.mark.asyncio
async def test_push_leads_respects_dry_run(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that dry_run=True does not create actual leads.

    Expected behavior:
    - Validate data and check duplicates
    - Do NOT call create_lead
    - Return what WOULD be created
    """
    # Execute: Call push_leads with dry_run=True
    result = await bulk_push_service.push_leads(
        leads_data=sample_leads_data,
        dry_run=True,
        atl_only=True
    )

    # Assert: Result indicates dry-run mode
    assert result.dry_run is True
    assert result.total_leads == 2

    # Assert: create_lead was NOT called
    mock_close_provider.create_lead.assert_not_called()

    # Assert: Would-create counts are correct
    assert result.would_create_count == 2
    assert result.success_count == 0  # No actual writes in dry-run

    # Assert: Dry-run results show what would be created
    assert len(result.results) == 2
    for lead_result in result.results:
        assert lead_result.status == "would_create"
        assert lead_result.dry_run is True


@pytest.mark.asyncio
async def test_dry_run_validates_data_format(
    bulk_push_service,
    sample_leads_data
):
    """
    Test that dry-run validates data format and catches errors.
    """
    # Setup: Add invalid lead (missing required fields)
    invalid_leads = sample_leads_data + [
        {
            "company_name": "Invalid Co",
            # Missing domain
            "contacts": []  # No contacts
        }
    ]

    # Execute: Call push_leads in dry-run mode
    result = await bulk_push_service.push_leads(
        leads_data=invalid_leads,
        dry_run=True,
        atl_only=True
    )

    # Assert: Validation errors detected
    assert result.failed_count == 1  # Invalid lead
    assert result.would_create_count == 2  # Valid leads

    # Assert: Invalid lead has error details
    failed_results = [r for r in result.results if r.status == "failed"]
    assert len(failed_results) == 1
    assert "contacts" in failed_results[0].error_message.lower()


# ========== Test 3: Duplicate detection skips existing leads ==========

@pytest.mark.asyncio
async def test_push_leads_handles_duplicates(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data,
    mock_db_session
):
    """
    Test that existing leads are skipped via deduplication.

    Expected behavior:
    - Check for existing leads by domain/email
    - Skip duplicates
    - Only create new leads
    """
    # Setup: Mock _check_existing_lead to return existing lead for first company
    with patch.object(
        bulk_push_service,
        '_check_existing_lead',
        new_callable=AsyncMock
    ) as mock_check:
        # First lead is duplicate, second is new
        mock_check.side_effect = [
            {"id": "lead_existing123", "company": "Test Electric Co"},  # Existing
            None  # New lead
        ]

        # Execute: Call push_leads
        result = await bulk_push_service.push_leads(
            leads_data=sample_leads_data,
            dry_run=False,
            atl_only=True
        )

        # Assert: One duplicate skipped, one created
        assert result.skipped_duplicates == 1
        assert result.success_count == 1
        assert result.total_leads == 2

        # Assert: create_lead only called once (for new lead)
        assert mock_close_provider.create_lead.call_count == 1

        # Assert: Duplicate result has correct status
        duplicate_results = [r for r in result.results if r.status == "duplicate"]
        assert len(duplicate_results) == 1
        assert duplicate_results[0].company_name == "Test Electric Co"
        assert duplicate_results[0].existing_lead_id == "lead_existing123"


@pytest.mark.asyncio
async def test_push_leads_adds_contacts_to_existing_when_update_mode(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that update_existing=True adds new contacts to existing leads.
    """
    # Setup: Mock existing lead
    with patch.object(
        bulk_push_service,
        '_check_existing_lead',
        new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = {
            "id": "lead_existing123",
            "company": "Test Electric Co"
        }

        # Execute: Call push_leads with update_existing=True
        result = await bulk_push_service.push_leads(
            leads_data=sample_leads_data[:1],  # Just first lead
            dry_run=False,
            atl_only=True,
            update_existing=True
        )

        # Assert: create_lead called with matched_lead_id
        assert mock_close_provider.create_lead.call_count == 1
        call_kwargs = mock_close_provider.create_lead.call_args[1]
        assert call_kwargs["matched_lead_id"] == "lead_existing123"

        # Assert: Result shows contacts added
        assert result.success_count == 1
        assert result.results[0].status == "updated"


# ========== Test 4: ATL filtering works correctly ==========

@pytest.mark.asyncio
async def test_push_leads_filters_atl_contacts_only(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that only ATL contacts are included when atl_only=True.

    Expected behavior:
    - Filter contacts where is_atl=True
    - Exclude BTL contacts
    - Skip leads with no ATL contacts
    """
    # Setup: Create leads with mixed ATL/BTL and BTL-only
    mixed_leads = [
        {
            "company_name": "Mixed Contacts Co",
            "domain": "mixedco.com",
            "contacts": [
                {"name": "ATL Person", "email": "atl@mixed.com", "is_atl": True},
                {"name": "BTL Person", "email": "btl@mixed.com", "is_atl": False}
            ]
        },
        {
            "company_name": "BTL Only Co",
            "domain": "btlonly.com",
            "contacts": [
                {"name": "BTL Only", "email": "btl@btl.com", "is_atl": False}
            ]
        },
        {
            "company_name": "ATL Only Co",
            "domain": "atlonly.com",
            "contacts": [
                {"name": "ATL Only", "email": "atl@atl.com", "is_atl": True}
            ]
        }
    ]

    # Execute: Call push_leads with atl_only=True
    result = await bulk_push_service.push_leads(
        leads_data=mixed_leads,
        dry_run=False,
        atl_only=True
    )

    # Assert: Only 2 leads created (BTL-only skipped)
    assert result.success_count == 2
    assert result.skipped_no_contacts == 1  # BTL-only lead skipped
    assert result.total_leads == 3

    # Assert: create_lead called twice
    assert mock_close_provider.create_lead.call_count == 2

    # Assert: Each created lead has only ATL contacts
    for call in mock_close_provider.create_lead.call_args_list:
        lead_data = call[1]["lead"]
        contacts = lead_data["_discovered_contacts"]

        # All contacts should be ATL
        assert all(c.get("is_atl") for c in contacts)


@pytest.mark.asyncio
async def test_atl_filtering_handles_missing_is_atl_flag(
    bulk_push_service,
    mock_close_provider
):
    """
    Test that contacts without is_atl flag are treated as BTL (excluded by default).
    """
    # Setup: Leads with contacts missing is_atl flag
    leads_missing_flag = [
        {
            "company_name": "Missing Flag Co",
            "domain": "missing.com",
            "contacts": [
                {"name": "No Flag", "email": "noflag@missing.com"}
                # Missing is_atl flag
            ]
        }
    ]

    # Execute: Call push_leads with atl_only=True
    result = await bulk_push_service.push_leads(
        leads_data=leads_missing_flag,
        dry_run=False,
        atl_only=True
    )

    # Assert: Lead skipped (no ATL contacts)
    assert result.success_count == 0
    assert result.skipped_no_contacts == 1

    # Assert: create_lead NOT called
    mock_close_provider.create_lead.assert_not_called()


# ========== Test 5: Error handling and retry logic ==========

@pytest.mark.asyncio
async def test_push_leads_handles_api_errors_gracefully(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that API errors are caught and recorded without stopping batch.
    """
    # Setup: Mock create_lead to fail for first lead, succeed for second
    mock_close_provider.create_lead.side_effect = [
        Exception("API error: Rate limit exceeded"),
        {"id": "lead_success", "status": "created"}
    ]

    # Execute: Call push_leads
    result = await bulk_push_service.push_leads(
        leads_data=sample_leads_data,
        dry_run=False,
        atl_only=True
    )

    # Assert: One failed, one succeeded
    assert result.failed_count == 1
    assert result.success_count == 1
    assert result.total_leads == 2

    # Assert: Error details captured
    failed_results = [r for r in result.results if r.status == "failed"]
    assert len(failed_results) == 1
    assert "rate limit" in failed_results[0].error_message.lower()


@pytest.mark.asyncio
async def test_push_leads_retries_on_transient_failures(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that transient failures are retried with exponential backoff.
    """
    # Setup: Mock create_lead to fail twice, then succeed
    mock_close_provider.create_lead.side_effect = [
        Exception("Network error"),
        Exception("Timeout"),
        {"id": "lead_success", "status": "created"}
    ]

    # Execute: Call push_leads with retry enabled
    result = await bulk_push_service.push_leads(
        leads_data=sample_leads_data[:1],  # Just first lead
        dry_run=False,
        atl_only=True,
        max_retries=2
    )

    # Assert: Eventually succeeded after retries
    assert result.success_count == 1
    assert result.failed_count == 0

    # Assert: create_lead called 3 times (2 failures + 1 success)
    assert mock_close_provider.create_lead.call_count == 3


# ========== Test 6: Batch processing and rate limiting ==========

@pytest.mark.asyncio
async def test_push_leads_processes_in_batches(
    bulk_push_service,
    mock_close_provider
):
    """
    Test that large datasets are processed in configurable batches.
    """
    # Setup: Create 25 leads
    large_dataset = [
        {
            "company_name": f"Company {i}",
            "domain": f"company{i}.com",
            "contacts": [
                {"name": f"Contact {i}", "email": f"contact{i}@company{i}.com", "is_atl": True}
            ]
        }
        for i in range(25)
    ]

    # Execute: Call push_leads with batch_size=10
    result = await bulk_push_service.push_leads(
        leads_data=large_dataset,
        dry_run=False,
        atl_only=True,
        batch_size=10
    )

    # Assert: All leads processed
    assert result.total_leads == 25
    assert result.success_count == 25

    # Assert: Processed in 3 batches (10 + 10 + 5)
    assert result.batches_processed == 3


@pytest.mark.asyncio
async def test_push_leads_respects_rate_limits(
    bulk_push_service,
    mock_close_provider
):
    """
    Test that rate limiting is respected between API calls.
    """
    # Setup: Track timing of calls
    call_times = []

    async def mock_create_with_timing(*args, **kwargs):
        call_times.append(datetime.utcnow())
        return {"id": "lead_test", "status": "created"}

    mock_close_provider.create_lead.side_effect = mock_create_with_timing

    # Execute: Call push_leads with rate_limit_delay
    result = await bulk_push_service.push_leads(
        leads_data=[
            {"company_name": "Co1", "domain": "co1.com", "contacts": [{"name": "C1", "email": "c1@co1.com", "is_atl": True}]},
            {"company_name": "Co2", "domain": "co2.com", "contacts": [{"name": "C2", "email": "c2@co2.com", "is_atl": True}]},
            {"company_name": "Co3", "domain": "co3.com", "contacts": [{"name": "C3", "email": "c3@co3.com", "is_atl": True}]}
        ],
        dry_run=False,
        atl_only=True,
        rate_limit_delay=0.5  # 500ms between calls
    )

    # Assert: Delays were applied
    if len(call_times) > 1:
        for i in range(1, len(call_times)):
            time_diff = (call_times[i] - call_times[i-1]).total_seconds()
            assert time_diff >= 0.4  # Allow some margin for test execution


# ========== Test 7: Result aggregation and reporting ==========

@pytest.mark.asyncio
async def test_bulk_push_result_provides_comprehensive_summary(
    bulk_push_service,
    mock_close_provider,
    sample_leads_data
):
    """
    Test that BulkPushResult provides comprehensive summary of operation.
    """
    # Setup: Mock mixed outcomes
    with patch.object(
        bulk_push_service,
        '_check_existing_lead',
        new_callable=AsyncMock
    ) as mock_check:
        # First lead is duplicate, second is new
        mock_check.side_effect = [
            {"id": "lead_dup", "company": "Duplicate"},
            None
        ]

        # Execute: Call push_leads
        result = await bulk_push_service.push_leads(
            leads_data=sample_leads_data,
            dry_run=False,
            atl_only=True
        )

        # Assert: Summary stats are correct
        assert result.total_leads == 2
        assert result.success_count == 1  # One new lead created
        assert result.failed_count == 0
        assert result.skipped_duplicates == 1
        assert result.skipped_no_contacts == 0

        # Assert: Individual results available
        assert len(result.results) == 2

        # Assert: Can get results by status
        successful = [r for r in result.results if r.status == "created"]
        duplicates = [r for r in result.results if r.status == "duplicate"]

        assert len(successful) == 1
        assert len(duplicates) == 1

        # Assert: Created lead has Close ID
        assert successful[0].close_lead_id is not None

        # Assert: Duplicate has existing lead ID
        assert duplicates[0].existing_lead_id == "lead_dup"


def test_lead_push_result_serialization():
    """
    Test that LeadPushResult can be serialized to JSON for logging.
    """
    result = LeadPushResult(
        company_name="Test Co",
        domain="test.com",
        status="created",
        close_lead_id="lead_123",
        contacts_created=2,
        dry_run=False
    )

    # Should be serializable
    result_dict = result.to_dict()

    assert result_dict["company_name"] == "Test Co"
    assert result_dict["status"] == "created"
    assert result_dict["close_lead_id"] == "lead_123"
    assert result_dict["contacts_created"] == 2


def test_bulk_push_result_calculates_percentages():
    """
    Test that BulkPushResult calculates success/failure percentages.
    """
    result = BulkPushResult(
        total_leads=100,
        success_count=80,
        failed_count=10,
        skipped_duplicates=10,
        skipped_no_contacts=0,
        dry_run=False
    )

    assert result.success_rate == 0.8  # 80%
    assert result.failure_rate == 0.1  # 10%
    assert result.duplicate_rate == 0.1  # 10%


# ========== Edge Cases ==========

@pytest.mark.asyncio
async def test_push_leads_handles_empty_input(bulk_push_service):
    """Test that empty leads list returns empty result."""
    result = await bulk_push_service.push_leads(
        leads_data=[],
        dry_run=False,
        atl_only=True
    )

    assert result.total_leads == 0
    assert result.success_count == 0
    assert len(result.results) == 0


@pytest.mark.asyncio
async def test_push_leads_handles_none_input(bulk_push_service):
    """Test that None input raises validation error."""
    with pytest.raises(ValueError, match="leads_data cannot be None"):
        await bulk_push_service.push_leads(
            leads_data=None,
            dry_run=False,
            atl_only=True
        )


@pytest.mark.asyncio
async def test_push_leads_handles_malformed_lead_data(
    bulk_push_service,
    mock_close_provider
):
    """Test that malformed lead data is caught and skipped."""
    malformed_leads = [
        {"company_name": "Valid Co", "domain": "valid.com", "contacts": [{"name": "Test", "email": "test@valid.com", "is_atl": True}]},
        {"company_name": None, "domain": "invalid.com"},  # Missing company name
        {"domain": "nocompany.com", "contacts": []},  # Missing company_name AND contacts
        {},  # Completely empty
    ]

    result = await bulk_push_service.push_leads(
        leads_data=malformed_leads,
        dry_run=False,
        atl_only=True
    )

    # Only first lead should succeed
    assert result.success_count == 1
    assert result.failed_count >= 1  # Malformed leads fail validation
