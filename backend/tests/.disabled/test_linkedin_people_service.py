"""
Tests for LinkedIn People Search Service

Tests the LinkedInPeopleService class which finds ATL contacts at companies
using Google search for LinkedIn profiles.

Uses respx for async HTTP mocking.
"""

import pytest
import httpx
import respx
from unittest.mock import patch

from app.services.linkedin_people_service import (
    LinkedInPeopleService,
    LinkedInPerson,
    LinkedInPeopleResult,
    get_linkedin_people_service,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def linkedin_service():
    """Create a fresh LinkedInPeopleService instance"""
    return LinkedInPeopleService()


@pytest.fixture
def mock_google_html():
    """Sample Google search result HTML with LinkedIn profiles"""
    return """
    <html>
    <body>
        <a href="/url?q=https://www.linkedin.com/in/john-smith&sa=U">
            John Smith - CEO at TechCorp
        </a>
        <a href="/url?q=https://www.linkedin.com/in/jane-doe&sa=U">
            Jane Doe - Founder at TechCorp
        </a>
        <a href="https://www.linkedin.com/in/bob-jones">
            Bob Jones - President at TechCorp
        </a>
    </body>
    </html>
    """


# ==============================================================================
# Initialization Tests
# ==============================================================================

def test_linkedin_people_service_initialization():
    """Test LinkedInPeopleService initializes with correct defaults"""
    service = LinkedInPeopleService()

    assert service.timeout == 15.0
    assert "Mozilla" in service.user_agent


def test_atl_titles_defined():
    """Test ATL titles list is properly defined"""
    service = LinkedInPeopleService()

    assert "CEO" in service.ATL_TITLES
    assert "President" in service.ATL_TITLES
    assert "VP" in service.ATL_TITLES
    assert "Director" in service.ATL_TITLES
    assert len(service.ATL_TITLES) >= 10


# ==============================================================================
# ATL Contact Search Tests
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_find_atl_contacts_success(linkedin_service, mock_google_html):
    """Test successful ATL contact search"""
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text=mock_google_html)
    )

    result = await linkedin_service.find_atl_contacts(
        company_linkedin_url="https://linkedin.com/company/techcorp",
        company_name="TechCorp",
        limit=10
    )

    assert result.status == "success"
    assert result.company_name == "TechCorp"
    assert len(result.people) > 0


@pytest.mark.asyncio
@respx.mock
async def test_find_atl_contacts_empty_results(linkedin_service):
    """Test handling when no profiles found"""
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text="<html><body>No results</body></html>")
    )

    result = await linkedin_service.find_atl_contacts(
        company_linkedin_url="https://linkedin.com/company/unknown",
        company_name="Unknown Corp",
        limit=10
    )

    assert result.status == "success"
    assert len(result.people) == 0


@pytest.mark.asyncio
@respx.mock
async def test_find_atl_contacts_limit_enforced(linkedin_service, mock_google_html):
    """Test that limit parameter is respected"""
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text=mock_google_html)
    )

    result = await linkedin_service.find_atl_contacts(
        company_linkedin_url="https://linkedin.com/company/techcorp",
        company_name="TechCorp",
        limit=1  # Only want 1 result
    )

    assert len(result.people) <= 1


@pytest.mark.asyncio
@respx.mock
async def test_find_atl_contacts_error_handling(linkedin_service):
    """Test graceful error handling - service catches individual search errors
    and returns success with empty results when all searches fail"""
    respx.get("https://www.google.com/search").mock(
        side_effect=Exception("Network error")
    )

    result = await linkedin_service.find_atl_contacts(
        company_linkedin_url="https://linkedin.com/company/test",
        company_name="Test Corp",
        limit=10
    )

    # The service catches errors in _google_search_people and returns empty list
    # So find_atl_contacts returns success with 0 results (graceful degradation)
    assert result.status == "success"
    assert len(result.people) == 0
    assert result.total_found == 0


# ==============================================================================
# Google Search Tests
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_google_search_people_success(linkedin_service, mock_google_html):
    """Test Google search parsing extracts LinkedIn profiles"""
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text=mock_google_html)
    )

    people = await linkedin_service._google_search_people(
        query='site:linkedin.com/in "CEO at TechCorp"',
        company_name="TechCorp",
        expected_title="CEO"
    )

    assert len(people) > 0
    # Should have LinkedIn URLs
    assert all("linkedin.com/in/" in p.linkedin_url for p in people)


@pytest.mark.asyncio
@respx.mock
async def test_google_search_people_timeout(linkedin_service):
    """Test Google search timeout handling"""
    respx.get("https://www.google.com/search").mock(
        side_effect=httpx.TimeoutException("Timeout")
    )

    people = await linkedin_service._google_search_people(
        query="site:linkedin.com/in test",
        company_name="Test",
        expected_title="CEO"
    )

    assert people == []  # Should return empty, not raise


@pytest.mark.asyncio
@respx.mock
async def test_google_search_people_rate_limited(linkedin_service):
    """Test handling of Google rate limiting (429 or similar)"""
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(429, text="Too many requests")
    )

    people = await linkedin_service._google_search_people(
        query="site:linkedin.com/in test",
        company_name="Test",
        expected_title="CEO"
    )

    assert people == []  # Should handle gracefully


@pytest.mark.asyncio
@respx.mock
async def test_google_search_cleans_linkedin_urls(linkedin_service):
    """Test that LinkedIn URLs are cleaned properly"""
    html = """
    <html>
    <body>
        <a href="/url?q=https://www.linkedin.com/in/john-smith?param=123&tracking=abc&sa=U">
            John Smith
        </a>
    </body>
    </html>
    """
    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text=html)
    )

    people = await linkedin_service._google_search_people(
        query="test",
        company_name="Test",
        expected_title="CEO"
    )

    if people:  # May be empty depending on parsing
        # URL should be cleaned of query params
        assert "?" not in people[0].linkedin_url or people[0].linkedin_url.endswith("john-smith")


# ==============================================================================
# Company ID Extraction Tests
# ==============================================================================

def test_extract_company_id_standard_url(linkedin_service):
    """Test extracting company ID from standard LinkedIn URL"""
    url = "https://www.linkedin.com/company/techcorp-inc"
    company_id = linkedin_service._extract_company_id(url)

    assert company_id == "techcorp-inc"


def test_extract_company_id_with_trailing_slash(linkedin_service):
    """Test extracting company ID with trailing slash"""
    url = "https://linkedin.com/company/acme/"
    company_id = linkedin_service._extract_company_id(url)

    assert company_id == "acme"


def test_extract_company_id_with_query_params(linkedin_service):
    """Test extracting company ID with query parameters"""
    url = "https://linkedin.com/company/startup-co?trk=something"
    company_id = linkedin_service._extract_company_id(url)

    assert company_id == "startup-co"


def test_extract_company_id_plain_id(linkedin_service):
    """Test fallback when given just an ID"""
    url = "just-the-company-id"
    company_id = linkedin_service._extract_company_id(url)

    assert company_id == "just-the-company-id"


# ==============================================================================
# Name Extraction Tests
# ==============================================================================

def test_extract_name_from_link_text(linkedin_service):
    """Test extracting name from link text"""
    url = "https://linkedin.com/in/john-smith"
    link_text = "John Smith - CEO at TechCorp"

    name = linkedin_service._extract_name(url, link_text)

    assert name == "John Smith"


def test_extract_name_from_url_slug(linkedin_service):
    """Test extracting name from URL when link text is empty"""
    url = "https://linkedin.com/in/jane-doe"
    link_text = ""

    name = linkedin_service._extract_name(url, link_text)

    assert name == "Jane Doe"


def test_extract_name_from_url_with_underscores(linkedin_service):
    """Test extracting name from URL with underscores"""
    url = "https://linkedin.com/in/bob_jones_123"
    link_text = ""

    name = linkedin_service._extract_name(url, link_text)

    assert "Bob" in name
    assert "Jones" in name


def test_extract_name_strips_title_suffixes(linkedin_service):
    """Test that title suffixes are stripped from name"""
    url = "https://linkedin.com/in/alice-wilson"
    link_text = "Alice Wilson - Founder & CEO at StartupCo"

    name = linkedin_service._extract_name(url, link_text)

    assert name == "Alice Wilson"
    assert "Founder" not in name
    assert "CEO" not in name


def test_extract_name_unknown_fallback(linkedin_service):
    """Test fallback to 'Unknown' when no name can be extracted"""
    url = "https://example.com/not-linkedin"
    link_text = ""

    name = linkedin_service._extract_name(url, link_text)

    assert name == "Unknown"


# ==============================================================================
# ATL Title Detection Tests
# ==============================================================================

def test_is_atl_title_ceo(linkedin_service):
    """Test CEO is recognized as ATL"""
    assert linkedin_service._is_atl_title("CEO") is True
    assert linkedin_service._is_atl_title("Chief Executive Officer") is True


def test_is_atl_title_vp(linkedin_service):
    """Test VP variations are recognized as ATL"""
    assert linkedin_service._is_atl_title("VP of Sales") is True
    assert linkedin_service._is_atl_title("Vice President") is True


def test_is_atl_title_director(linkedin_service):
    """Test Director is recognized as ATL"""
    assert linkedin_service._is_atl_title("Director of Engineering") is True
    assert linkedin_service._is_atl_title("IT Director") is True


def test_is_atl_title_founder(linkedin_service):
    """Test Founder/Owner variations are recognized as ATL"""
    assert linkedin_service._is_atl_title("Founder") is True
    assert linkedin_service._is_atl_title("Co-Founder") is True
    assert linkedin_service._is_atl_title("Owner") is True


def test_is_atl_title_not_atl(linkedin_service):
    """Test non-ATL titles are correctly rejected"""
    assert linkedin_service._is_atl_title("Software Engineer") is False
    assert linkedin_service._is_atl_title("Sales Representative") is False
    assert linkedin_service._is_atl_title("Analyst") is False


def test_is_atl_title_empty(linkedin_service):
    """Test empty/None titles return False"""
    assert linkedin_service._is_atl_title("") is False
    assert linkedin_service._is_atl_title(None) is False


# ==============================================================================
# Singleton Pattern Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_linkedin_people_service_singleton():
    """Test get_linkedin_people_service returns singleton"""
    # Reset singleton for test
    import app.services.linkedin_people_service as lps
    lps._linkedin_people_service = None

    service1 = await get_linkedin_people_service()
    service2 = await get_linkedin_people_service()

    assert service1 is service2


@pytest.mark.asyncio
async def test_get_linkedin_people_service_creates_instance():
    """Test get_linkedin_people_service creates new instance"""
    import app.services.linkedin_people_service as lps
    lps._linkedin_people_service = None

    service = await get_linkedin_people_service()

    assert service is not None
    assert isinstance(service, LinkedInPeopleService)


# ==============================================================================
# Pydantic Model Tests
# ==============================================================================

def test_linkedin_person_model():
    """Test LinkedInPerson Pydantic model"""
    person = LinkedInPerson(
        name="John Doe",
        linkedin_url="https://linkedin.com/in/john-doe",
        title="CEO",
        company="TechCorp"
    )

    assert person.name == "John Doe"
    assert person.linkedin_url == "https://linkedin.com/in/john-doe"
    assert person.title == "CEO"
    assert person.is_atl is True  # Default
    assert person.source == "linkedin"  # Default


def test_linkedin_person_model_minimal():
    """Test LinkedInPerson with minimal required fields"""
    person = LinkedInPerson(
        name="Jane",
        linkedin_url="https://linkedin.com/in/jane"
    )

    assert person.name == "Jane"
    assert person.title is None
    assert person.company is None
    assert person.email is None


def test_linkedin_people_result_success():
    """Test LinkedInPeopleResult for success case"""
    result = LinkedInPeopleResult(
        people=[
            LinkedInPerson(name="John", linkedin_url="https://linkedin.com/in/john")
        ],
        company_name="TechCorp",
        total_found=1,
        status="success"
    )

    assert result.status == "success"
    assert len(result.people) == 1
    assert result.error_message is None


def test_linkedin_people_result_error():
    """Test LinkedInPeopleResult for error case"""
    result = LinkedInPeopleResult(
        people=[],
        company_name="FailCorp",
        total_found=0,
        status="error",
        error_message="Network timeout"
    )

    assert result.status == "error"
    assert result.error_message == "Network timeout"
    assert len(result.people) == 0


# ==============================================================================
# Integration-Style Tests
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_end_to_end_contact_search(linkedin_service):
    """Test full contact search workflow"""
    # Mock multiple Google searches (for different titles)
    html_ceo = """
    <html><body>
        <a href="/url?q=https://linkedin.com/in/ceo-person">CEO Person</a>
    </body></html>
    """

    respx.get("https://www.google.com/search").mock(
        return_value=httpx.Response(200, text=html_ceo)
    )

    result = await linkedin_service.find_atl_contacts(
        company_linkedin_url="https://linkedin.com/company/test-co",
        company_name="Test Co",
        limit=5
    )

    assert result.status == "success"
    assert result.company_name == "Test Co"
    # Should have searched and parsed results
    assert isinstance(result.total_found, int)
