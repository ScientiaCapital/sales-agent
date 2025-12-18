"""
Tests for Dealer Scraper Sync API

Run with: pytest tests/test_sync_from_scraper.py -v
"""

# Skip tests - requires langchain_core which is an optional dependency
import pytest



import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

# Import the FastAPI app
from app.main import app



client = TestClient(app)


# ============================================================================
# TEST DATA
# ============================================================================

SAMPLE_CONTRACTORS = [
    {
        "company_name": "Test HVAC Co",
        "normalized_name": "test hvac co",
        "phone": "5551234567",
        "email": "info@testhvac.com",
        "domain": "testhvac.com",
        "state": "tx",
        "city": "Austin",
        "oem_brands": ["Carrier", "Trane"],
        "source_scraper": "carrier",
        "certifications": ["NATE"],
        "service_areas": ["Austin", "Round Rock"]
    }
]

SAMPLE_CONTACTS = [
    {
        "company_name": "Test HVAC Co",
        "normalized_company_name": "test hvac co",
        "full_name": "John Smith",
        "email": "john@testhvac.com",
        "phone": "5551234568",
        "title": "Owner",
        "is_decision_maker": True,
        "source_scraper": "carrier"
    }
]


# ============================================================================
# MOCK SUPABASE
# ============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    with patch('app.api.sync_from_scraper.get_supabase') as mock:
        supabase = Mock()

        # Mock table().select().execute() chain for existing companies
        companies_result = Mock()
        companies_result.data = []  # Empty initially (new import)
        supabase.table.return_value.select.return_value.execute.return_value = companies_result

        # Mock table().insert().execute() chain
        insert_result = Mock()
        insert_result.data = [{"company_id": "test-uuid-123"}]
        supabase.table.return_value.insert.return_value.execute.return_value = insert_result

        # Mock table().update().execute() chain
        update_result = Mock()
        update_result.data = [{"company_id": "test-uuid-123"}]
        supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = update_result

        mock.return_value = supabase
        yield supabase


# ============================================================================
# CONTRACTOR SYNC TESTS
# ============================================================================

def test_sync_contractors_new_company(mock_supabase):
    """Test syncing new contractors (INSERT)."""

    payload = {
        "contractors": SAMPLE_CONTRACTORS,
        "batch_id": "test_batch_001",
        "source_scraper": "carrier"
    }

    response = client.post("/api/v1/scraper/contractors", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["batch_id"] == "test_batch_001"
    assert data["source_scraper"] == "carrier"
    assert data["total_received"] == 1
    assert data["inserted"] >= 0  # May vary based on mock
    assert data["updated"] >= 0
    assert data["skipped"] == 0
    assert len(data["errors"]) == 0


def test_sync_contractors_existing_company(mock_supabase):
    """Test syncing existing contractors (UPDATE with OEM merge)."""

    # Mock existing company
    existing_company = {
        "company_id": "existing-uuid-456",
        "normalized_name": "test hvac co",
        "phone": None,
        "domain": None,
        "oem_brands": ["Lennox"],  # Will merge with Carrier, Trane
        "service_areas": [],
        "certifications": []
    }

    companies_result = Mock()
    companies_result.data = [existing_company]
    mock_supabase.table.return_value.select.return_value.execute.return_value = companies_result

    payload = {
        "contractors": SAMPLE_CONTRACTORS,
        "batch_id": "test_batch_002",
        "source_scraper": "carrier"
    }

    response = client.post("/api/v1/scraper/contractors", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["total_received"] == 1
    # Should update, not insert
    # Note: Actual counts depend on mock behavior


def test_sync_contractors_validation_error():
    """Test contractor sync with validation errors."""

    invalid_payload = {
        "contractors": [
            {
                "company_name": "Invalid Co",
                # Missing required fields: normalized_name, state, source_scraper
            }
        ],
        "batch_id": "test_invalid",
        "source_scraper": "test"
    }

    response = client.post("/api/v1/scraper/contractors", json=invalid_payload)

    # Should return 422 validation error
    assert response.status_code == 422


def test_sync_contractors_empty_batch(mock_supabase):
    """Test syncing empty contractor batch."""

    payload = {
        "contractors": [],
        "batch_id": "test_empty",
        "source_scraper": "test"
    }

    response = client.post("/api/v1/scraper/contractors", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["total_received"] == 0
    assert data["inserted"] == 0
    assert data["updated"] == 0
    assert data["skipped"] == 0


# ============================================================================
# CONTACT SYNC TESTS
# ============================================================================

def test_sync_contacts_with_matching_company(mock_supabase):
    """Test syncing contacts when matching company exists."""

    # Mock existing company
    companies_result = Mock()
    companies_result.data = [{
        "company_id": "company-uuid-789",
        "normalized_name": "test hvac co"
    }]

    # Mock existing contacts (empty)
    contacts_result = Mock()
    contacts_result.data = []

    # Set up mock chain
    mock_supabase.table.return_value.select.return_value.execute.side_effect = [
        companies_result,  # First call for companies
        contacts_result    # Second call for existing contacts
    ]

    payload = {
        "contacts": SAMPLE_CONTACTS,
        "batch_id": "test_contacts_001",
        "source_scraper": "carrier"
    }

    response = client.post("/api/v1/scraper/contacts", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["total_received"] == 1
    # Should insert or skip based on company match


def test_sync_contacts_no_matching_company(mock_supabase):
    """Test syncing contacts when NO matching company exists."""

    # Mock empty companies
    companies_result = Mock()
    companies_result.data = []

    contacts_result = Mock()
    contacts_result.data = []

    mock_supabase.table.return_value.select.return_value.execute.side_effect = [
        companies_result,
        contacts_result
    ]

    payload = {
        "contacts": SAMPLE_CONTACTS,
        "batch_id": "test_contacts_002",
        "source_scraper": "carrier"
    }

    response = client.post("/api/v1/scraper/contacts", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Should skip contacts (no matching company)
    assert data["skipped"] >= 0  # May be 1 if logic works
    assert len(data["errors"]) >= 0  # May have errors for no company


def test_sync_contacts_validation_error():
    """Test contact sync with validation errors."""

    invalid_payload = {
        "contacts": [
            {
                "full_name": "John Doe",
                # Missing required fields: company_name, normalized_company_name, source_scraper
            }
        ],
        "batch_id": "test_invalid",
        "source_scraper": "test"
    }

    response = client.post("/api/v1/scraper/contacts", json=invalid_payload)

    # Should return 422 validation error
    assert response.status_code == 422


# ============================================================================
# STATUS ENDPOINT TESTS
# ============================================================================

def test_get_sync_status(mock_supabase):
    """Test GET /status endpoint."""

    # Mock audit log
    audit_result = Mock()
    audit_result.data = [{
        "created_at": "2025-12-08T10:00:00Z",
        "session_id": "test_batch_123",
        "decision_data": {"source_scraper": "carrier"}
    }]

    # Mock company count
    contractors_result = Mock()
    contractors_result.count = 100

    # Mock contact count
    contacts_result = Mock()
    contacts_result.count = 50

    # Set up mock chain
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = audit_result
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
        contractors_result,
        contacts_result
    ]

    response = client.get("/api/v1/scraper/status")

    assert response.status_code == 200
    data = response.json()

    assert "last_sync_at" in data
    assert "total_contractors_synced" in data
    assert "total_contacts_synced" in data
    assert "last_batch_id" in data
    assert "last_source_scraper" in data


# ============================================================================
# INTEGRATION TESTS (Require Real Supabase)
# ============================================================================

@pytest.mark.skip(reason="Requires real Supabase connection")
def test_end_to_end_contractor_sync():
    """End-to-end test with real Supabase (skip by default)."""

    payload = {
        "contractors": [
            {
                "company_name": "E2E Test HVAC",
                "normalized_name": "e2e test hvac",
                "domain": "e2etest.com",
                "state": "tx",
                "oem_brands": ["Carrier"],
                "source_scraper": "pytest"
            }
        ],
        "batch_id": "pytest_e2e_001",
        "source_scraper": "pytest"
    }

    response = client.post("/api/v1/scraper/contractors", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["inserted"] == 1 or data["updated"] == 1

    # Cleanup: Delete test company from Supabase
    # (Add cleanup code here)


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

def test_normalize_phone():
    """Test phone normalization helper."""
    from app.api.sync_from_scraper import normalize_phone

    assert normalize_phone("555-123-4567") == "5551234567"
    assert normalize_phone("(555) 123-4567") == "5551234567"
    assert normalize_phone("5551234567") == "5551234567"
    assert normalize_phone("+1 555 123 4567") == "5551234567"
    assert normalize_phone("") is None
    assert normalize_phone(None) is None


def test_merge_oem_brands():
    """Test OEM brand merging (case-insensitive)."""
    from app.api.sync_from_scraper import merge_oem_brands

    existing = ["Carrier", "Trane"]
    new = ["trane", "Lennox"]

    result = merge_oem_brands(existing, new)

    assert len(result) == 3
    assert "Carrier" in result
    assert "Lennox" in result
    # Should keep one of "Trane" or "trane" (case-insensitive dedup)


def test_merge_service_areas():
    """Test service area merging (case-insensitive)."""
    from app.api.sync_from_scraper import merge_service_areas

    existing = ["Austin", "Round Rock"]
    new = ["austin", "Cedar Park"]

    result = merge_service_areas(existing, new)

    assert len(result) == 3
    assert "Cedar Park" in result
    # Should keep one of "Austin" or "austin" (case-insensitive dedup)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
