"""
Integration test for VLM pipeline - Full E2E test of VLM-based contact enrichment.

Tests the complete flow:
1. Take screenshot of company website
2. Analyze screenshot with VLM (extract contacts + ICP signals)
3. Save contacts to database with verification
4. Update company ICP signals
"""

# CRITICAL: Set DATABASE_URL BEFORE any imports (required by conftest.py)
import os
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import sys


# Mock vlm_core imports at module level
@pytest.fixture(autouse=True)
def mock_vlm_core_imports():
    """Mock vlm_core imports for all tests."""
    with patch.dict('sys.modules', {
        'vlm_core': Mock(),
        'vlm_core.providers': Mock(),
        'vlm_core.providers.openrouter': Mock(),
    }):
        yield


@pytest.fixture
def mock_screenshot_path(tmp_path):
    """Create a temporary mock screenshot file."""
    # Create a minimal PNG file (1x1 pixel)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    screenshot_file = tmp_path / "company_homepage.png"
    screenshot_file.write_bytes(png_data)
    return screenshot_file


@pytest.fixture
def mock_supabase_client():
    """Create a comprehensive mock Supabase client for integration testing."""
    client = MagicMock()
    stored_contacts = {}
    stored_companies = {}

    def create_table_mock(table_name):
        table = MagicMock()

        if table_name == "dim_contacts":
            # Select mock for readback and duplicate checking
            select_mock = MagicMock()

            def eq_handler(column, value):
                eq_result = MagicMock()

                if column == "contact_id":
                    # Readback verification
                    if value in stored_contacts:
                        result = MagicMock()
                        result.data = [stored_contacts[value]]
                        eq_result.execute = MagicMock(return_value=result)
                        return eq_result
                    else:
                        eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                        return eq_result

                elif column == "company_id":
                    # Duplicate check - need to handle .ilike() chaining
                    ilike_mock = MagicMock()
                    ilike_mock.execute = MagicMock(
                        return_value=MagicMock(data=[])  # No duplicates
                    )
                    eq_result.ilike = MagicMock(return_value=ilike_mock)
                    return eq_result

                # Default case
                eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                return eq_result

            select_mock.eq = MagicMock(side_effect=eq_handler)
            table.select = MagicMock(return_value=select_mock)

            # Insert mock
            def insert_handler(data):
                insert_result = MagicMock()
                # Store the contact for readback
                contact_id = data.get("contact_id")
                if contact_id:
                    stored_contacts[contact_id] = data.copy()
                insert_result.execute = MagicMock(return_value=MagicMock(data=[data]))
                return insert_result

            table.insert = MagicMock(side_effect=insert_handler)

        elif table_name == "dim_companies":
            # Update mock for ICP signals
            update_mock = MagicMock()

            def update_handler(data):
                company_id = None  # Will be set by .eq()
                eq_mock = MagicMock()

                def eq_handler_company(column, value):
                    nonlocal company_id
                    company_id = value
                    exec_mock = MagicMock()

                    def execute_update():
                        # Store signals
                        if company_id not in stored_companies:
                            stored_companies[company_id] = {}
                        stored_companies[company_id].update(data)
                        return MagicMock(data=[{}])

                    exec_mock.execute = MagicMock(side_effect=execute_update)
                    return exec_mock

                eq_mock.eq = MagicMock(side_effect=eq_handler_company)
                return eq_mock

            table.update = MagicMock(side_effect=update_handler)

            # Select mock for readback
            select_mock = MagicMock()

            def eq_handler_select(column, value):
                eq_result = MagicMock()
                if value in stored_companies:
                    result = MagicMock()
                    result.data = [stored_companies[value]]
                    eq_result.execute = MagicMock(return_value=result)
                    return eq_result
                else:
                    eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                    return eq_result

            select_mock.eq = MagicMock(side_effect=eq_handler_select)
            table.select = MagicMock(return_value=select_mock)

        elif table_name == "fact_enrichment_errors":
            # Error logging table
            insert_mock = MagicMock()
            insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
            table.insert = MagicMock(return_value=insert_mock)

        return table

    client.table = MagicMock(side_effect=create_table_mock)
    client._stored_contacts = stored_contacts
    client._stored_companies = stored_companies
    return client


@pytest.mark.asyncio
async def test_full_pipeline_single_company(
    mock_screenshot_path,
    mock_supabase_client
):
    """
    Test the full VLM pipeline for a single company.

    This E2E test validates the entire workflow:
    1. VLMContactExtractor analyzes screenshot
    2. Contacts are extracted with ICP signals
    3. SaveVerifier saves each contact with readback verification
    4. SaveVerifier updates company ICP signals
    5. All data is persisted and verified in mock database

    This ensures all components work together correctly.
    """
    from app.services.vlm_contact_extractor import VLMContactExtractor
    from app.services.save_verifier import SaveVerifier

    # SETUP: Company data
    company_id = "test-company-123"
    page_url = "https://example-hvac.com/team"

    # STEP 1: Mock VLM extraction
    # Create a mock VLM response with contacts and ICP signals
    mock_vlm_response = {
        "contacts": [
            {
                "name": "John Smith",
                "title": "CEO & Founder",
                "email": "john@example-hvac.com",
                "confidence": "HIGH",
                "visual_context": "Large photo with title below"
            },
            {
                "name": "Sarah Johnson",
                "title": "VP of Operations",
                "email": None,
                "confidence": "MEDIUM",
                "visual_context": "Team section card"
            }
        ],
        "icp_signals": {
            "has_design_build": True,
            "has_engineering": True,
            "has_medical_specialization": False,
            "has_building_automation": True,
            "has_awards": False,
            "has_oem_partnerships": True
        }
    }

    # Mock the OpenRouter API call
    with patch('app.services.vlm_contact_extractor.AsyncOpenAI') as mock_openai_class:
        # Create mock client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response with valid JSON
        import json
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps(mock_vlm_response)
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 1200
        mock_completion.usage.completion_tokens = 300

        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        # STEP 2: Extract contacts using VLM
        extractor = VLMContactExtractor(api_key="test-openrouter-key")
        extraction_result = await extractor.extract_contacts(
            screenshot_path=mock_screenshot_path,
            page_url=page_url
        )

        # Verify extraction succeeded
        assert len(extraction_result["contacts"]) == 2
        assert extraction_result["icp_signals"]["has_design_build"] is True
        assert extraction_result["icp_signals"]["has_engineering"] is True
        assert extraction_result["cost"] > 0  # Cost was calculated

    # STEP 3: Save contacts with verification
    verifier = SaveVerifier(supabase=mock_supabase_client, max_retries=1)

    saved_contact_ids = []
    for contact in extraction_result["contacts"]:
        # Prepare contact data
        contact_data = {
            "full_name": contact["name"],
            "first_name": contact["name"].split()[0] if " " in contact["name"] else contact["name"],
            "last_name": contact["name"].split()[-1] if " " in contact["name"] else "",
            "title": contact.get("title", ""),
            "email": contact.get("email"),
            "confidence": 85 if contact["confidence"] == "HIGH" else 70,
            "is_atl": "CEO" in contact.get("title", "") or "VP" in contact.get("title", "")
        }

        # Save contact
        success, contact_id, error = verifier.save_contact(
            company_id=company_id,
            contact_data=contact_data,
            source="vlm_screenshot"
        )

        # Verify save succeeded
        assert success is True, f"Failed to save contact: {error}"
        assert contact_id is not None
        assert error is None

        saved_contact_ids.append(contact_id)

    # Verify 2 contacts were saved
    assert len(saved_contact_ids) == 2

    # Verify contacts are in mock database
    for contact_id in saved_contact_ids:
        assert contact_id in mock_supabase_client._stored_contacts
        stored = mock_supabase_client._stored_contacts[contact_id]
        assert stored["company_id"] == company_id
        assert stored["source"] == "vlm_screenshot"

    # STEP 4: Update company ICP signals
    success, error = verifier.update_company_signals(
        company_id=company_id,
        signals=extraction_result["icp_signals"],
        source="vlm_extractor"
    )

    # Verify signals update succeeded
    assert success is True, f"Failed to update signals: {error}"
    assert error is None

    # Verify signals are in mock database
    assert company_id in mock_supabase_client._stored_companies
    stored_signals = mock_supabase_client._stored_companies[company_id]
    assert stored_signals["has_design_build"] is True
    assert stored_signals["has_engineering"] is True
    assert stored_signals["has_building_automation"] is True
    assert stored_signals["has_oem_partnerships"] is True
    assert stored_signals["has_medical_specialization"] is False
    assert stored_signals["has_awards"] is False

    # STEP 5: Final verification
    # Verify we can read contacts back
    all_contacts = [mock_supabase_client._stored_contacts[cid] for cid in saved_contact_ids]

    # Find John and Sarah by title (more reliable than name matching)
    ceo_contact = next((c for c in all_contacts if "CEO" in c.get("title", "")), None)
    vp_contact = next((c for c in all_contacts if "VP" in c.get("title", "")), None)

    # Verify John (CEO)
    assert ceo_contact is not None, "CEO contact not found"
    assert "John Smith" in ceo_contact["full_name"]
    assert ceo_contact["title"] == "CEO & Founder"
    assert ceo_contact["email"] == "john@example-hvac.com"
    assert ceo_contact["is_atl"] is True  # CEO is ATL

    # Verify Sarah (VP)
    assert vp_contact is not None, "VP contact not found"
    assert "Sarah Johnson" in vp_contact["full_name"]
    assert vp_contact["title"] == "VP of Operations"
    assert vp_contact["is_atl"] is True  # VP is ATL

    # SUCCESS: Full pipeline completed successfully!
    print(f"VLM Pipeline E2E Test PASSED:")
    print(f"  - Extracted {len(extraction_result['contacts'])} contacts")
    print(f"  - Saved {len(saved_contact_ids)} contacts to database")
    print(f"  - Updated {len(stored_signals)} ICP signals")
    print(f"  - Total cost: ${extraction_result['cost']:.4f}")
