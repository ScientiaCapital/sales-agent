"""
Fixtures for VLM service tests.

Provides mocks for OpenRouter API and Supabase client.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE importing app modules
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime


# ==================== OpenRouter Mocks ====================

@pytest.fixture
def mock_openrouter_response():
    """Create a mock OpenRouter API response."""
    def _create_response(
        content: str = '{"contacts": [], "icp_signals": {}}',
        input_tokens: int = 1000,
        output_tokens: int = 200,
        model: str = "opengvlab/internvl3-78b"
    ):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        response.usage = MagicMock()
        response.usage.prompt_tokens = input_tokens
        response.usage.completion_tokens = output_tokens
        response.model = model
        return response
    return _create_response


@pytest.fixture
def mock_openai_client(mock_openrouter_response):
    """Create a mock AsyncOpenAI client for OpenRouter."""
    client = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=mock_openrouter_response()
    )
    return client


@pytest.fixture
def mock_openai_client_with_fallback(mock_openrouter_response):
    """
    Create a mock client that fails on first call (primary model)
    and succeeds on second call (fallback model).
    """
    client = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()

    # First call fails, second succeeds
    client.chat.completions.create = AsyncMock(
        side_effect=[
            Exception("Primary model rate limited"),
            mock_openrouter_response(
                content='{"contacts": [{"name": "Fallback User", "title": "Manager", "confidence": "HIGH"}], "icp_signals": {}}',
                model="qwen/qwen3-vl-30b-a3b-instruct"
            )
        ]
    )
    return client


# ==================== Supabase Mocks ====================

@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = MagicMock()

    # Mock table method that returns chainable mock
    def create_table_mock(table_name):
        table = MagicMock()
        table.table_name = table_name

        # Mock chainable methods
        select_mock = MagicMock()
        select_mock.eq = MagicMock(return_value=select_mock)
        select_mock.ilike = MagicMock(return_value=select_mock)
        select_mock.execute = MagicMock(return_value=MagicMock(data=[], count=0))

        insert_mock = MagicMock()
        insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))

        update_mock = MagicMock()
        update_mock.eq = MagicMock(return_value=update_mock)
        update_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))

        table.select = MagicMock(return_value=select_mock)
        table.insert = MagicMock(return_value=insert_mock)
        table.update = MagicMock(return_value=update_mock)

        return table

    client.table = MagicMock(side_effect=create_table_mock)
    return client


@pytest.fixture
def mock_supabase_with_readback():
    """
    Create a mock Supabase client that simulates successful insert + readback.
    """
    client = MagicMock()
    saved_contacts = {}

    def create_table_mock(table_name):
        table = MagicMock()
        table.table_name = table_name

        if table_name == "dim_contacts":
            # Select mock for readback
            select_mock = MagicMock()

            def select_eq(column, value):
                eq_result = MagicMock()

                if column == "contact_id" and value in saved_contacts:
                    # Readback check - return the saved contact
                    result = MagicMock()
                    result.data = [saved_contacts[value]]
                    eq_result.execute = MagicMock(return_value=result)
                    return eq_result
                elif column == "company_id":
                    # Duplicate check - need to handle .ilike() chaining
                    ilike_mock = MagicMock()
                    ilike_mock.execute = MagicMock(
                        return_value=MagicMock(data=[])
                    )
                    eq_result.ilike = MagicMock(return_value=ilike_mock)
                    return eq_result

                # Default case
                eq_result.execute = MagicMock(return_value=MagicMock(data=[]))
                return eq_result

            select_mock.eq = MagicMock(side_effect=select_eq)
            select_mock.ilike = MagicMock(return_value=select_mock)
            select_mock.execute = MagicMock(return_value=MagicMock(data=[]))

            # Insert mock
            def insert_handler(data):
                insert_result = MagicMock()
                # Store the contact for readback
                contact_id = data.get("contact_id")
                if contact_id:
                    saved_contacts[contact_id] = data.copy()
                insert_result.execute = MagicMock(return_value=MagicMock(data=[data]))
                return insert_result

            table.select = MagicMock(return_value=select_mock)
            table.insert = MagicMock(side_effect=insert_handler)

        elif table_name == "fact_enrichment_errors":
            # Error logging table
            insert_mock = MagicMock()
            insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
            table.insert = MagicMock(return_value=insert_mock)

        return table

    client.table = MagicMock(side_effect=create_table_mock)
    client._saved_contacts = saved_contacts
    return client


@pytest.fixture
def mock_supabase_with_duplicate():
    """
    Create a mock Supabase client that simulates duplicate detection.
    """
    client = MagicMock()

    def create_table_mock(table_name):
        table = MagicMock()

        if table_name == "dim_contacts":
            select_mock = MagicMock()

            def ilike_handler(column, value):
                result_mock = MagicMock()
                # Simulate finding an existing contact with same name (case-insensitive)
                result_mock.execute = MagicMock(
                    return_value=MagicMock(data=[{
                        "contact_id": "existing-uuid-123",
                        "full_name": value.strip()
                    }])
                )
                return result_mock

            def eq_handler(column, value):
                if column == "company_id":
                    ilike_result = MagicMock()
                    ilike_result.ilike = MagicMock(side_effect=ilike_handler)
                    return ilike_result
                return select_mock

            select_mock.eq = MagicMock(side_effect=eq_handler)
            table.select = MagicMock(return_value=select_mock)

        elif table_name == "fact_enrichment_errors":
            insert_mock = MagicMock()
            insert_mock.execute = MagicMock(return_value=MagicMock(data=[{}]))
            table.insert = MagicMock(return_value=insert_mock)

        return table

    client.table = MagicMock(side_effect=create_table_mock)
    return client


# ==================== Sample Data Fixtures ====================

@pytest.fixture
def sample_vlm_response_valid():
    """Sample valid VLM JSON response."""
    return '''{
  "contacts": [
    {
      "name": "John Smith",
      "title": "CEO & Founder",
      "email": "john@example.com",
      "confidence": "HIGH",
      "visual_context": "Large photo at top with title below"
    },
    {
      "name": "Sarah Johnson",
      "title": "VP of Operations",
      "email": null,
      "confidence": "MEDIUM",
      "visual_context": "Team section card"
    }
  ],
  "icp_signals": {
    "has_design_build": true,
    "has_engineering": false,
    "has_medical_specialization": true,
    "has_building_automation": false,
    "has_awards": true,
    "has_oem_partnerships": false
  }
}'''


@pytest.fixture
def sample_vlm_response_markdown():
    """Sample VLM response wrapped in markdown code block."""
    return '''Here is the extracted information:

```json
{
  "contacts": [
    {
      "name": "Michael Brown",
      "title": "Project Manager",
      "email": "michael@company.com",
      "confidence": "HIGH",
      "visual_context": "Staff directory listing"
    }
  ],
  "icp_signals": {
    "has_design_build": false,
    "has_engineering": true,
    "has_awards": false
  }
}
```

I found one contact on this page.'''


@pytest.fixture
def sample_vlm_response_with_garbage():
    """Sample VLM response with garbage contacts that should be filtered."""
    return '''{
  "contacts": [
    {
      "name": "John Doe",
      "title": "CEO",
      "confidence": "HIGH"
    },
    {
      "name": "None",
      "title": "",
      "confidence": "LOW"
    },
    {
      "name": "null",
      "title": "Unknown",
      "confidence": "LOW"
    },
    {
      "name": "Kenneth A.",
      "title": "Happy Customer - 5 years with us",
      "confidence": "MEDIUM"
    },
    {
      "name": "Our Team",
      "title": "",
      "confidence": "LOW"
    },
    {
      "name": "Contact Us",
      "title": "",
      "confidence": "LOW"
    },
    {
      "name": "AB",
      "title": "Short name",
      "confidence": "LOW"
    }
  ],
  "icp_signals": {}
}'''


@pytest.fixture
def sample_contact_data():
    """Sample contact data for SaveVerifier tests."""
    return {
        "full_name": "Jane Doe",
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "Director of Engineering",
        "email": "jane.doe@example.com",
        "phone": "+1-555-123-4567",
        "is_atl": True,
        "confidence": 85,
    }


@pytest.fixture
def sample_company_id():
    """Sample company UUID."""
    return "12345678-abcd-1234-abcd-123456789abc"


# ==================== Screenshot Fixtures ====================

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
    screenshot_file = tmp_path / "test_screenshot.png"
    screenshot_file.write_bytes(png_data)
    return screenshot_file
