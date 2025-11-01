"""Tests for email extraction service."""
import pytest
import httpx
import pytest_httpx
from app.services.email_extractor import EmailExtractor


@pytest.fixture
def extractor():
    """Create EmailExtractor instance."""
    return EmailExtractor()


@pytest.mark.asyncio
async def test_extractor_initializes(extractor):
    """Test EmailExtractor can be instantiated."""
    assert extractor is not None
    assert extractor.timeout == 10


@pytest.mark.asyncio
async def test_extract_from_simple_html(extractor):
    """Test basic email extraction from HTML."""
    html = '<a href="mailto:test@example.com">Contact</a>'
    emails = await extractor._extract_from_html(html, "https://example.com")

    assert "test@example.com" in emails


@pytest.mark.asyncio
async def test_extract_standard_email(extractor):
    """Test standard email format extraction."""
    html = '<p>Email: john.smith@example.com</p>'
    emails = await extractor._extract_from_html(html, "https://example.com")

    assert "john.smith@example.com" in emails


@pytest.mark.asyncio
async def test_extract_mailto_link(extractor):
    """Test mailto: link extraction."""
    html = '<a href="mailto:contact@example.com">Email Us</a>'
    emails = await extractor._extract_from_html(html, "https://example.com")

    assert "contact@example.com" in emails


@pytest.mark.asyncio
async def test_extract_obfuscated_at(extractor):
    """Test obfuscated (at) format."""
    html = '<p>john.smith (at) example.com</p>'
    emails = await extractor._extract_from_html(html, "https://example.com")

    assert "john.smith@example.com" in emails


@pytest.mark.asyncio
async def test_extract_multiple_emails(extractor):
    """Test extracting multiple emails from same page."""
    html = '''
    <div>
        <a href="mailto:sales@example.com">Sales</a>
        <p>Support: support@example.com</p>
        <span>CEO: john.doe@example.com</span>
    </div>
    '''
    emails = await extractor._extract_from_html(html, "https://example.com")

    assert len(emails) >= 3
    assert "sales@example.com" in emails
    assert "support@example.com" in emails
    assert "john.doe@example.com" in emails


@pytest.mark.asyncio
async def test_filter_generic_emails(extractor):
    """Test generic email filtering."""
    emails = [
        'john.smith@example.com',
        'info@example.com',
        'sales@example.com',
        'noreply@example.com',
        'admin@example.com'
    ]
    filtered = extractor._filter_generic(emails)

    assert 'john.smith@example.com' in filtered
    assert 'sales@example.com' in filtered
    assert 'info@example.com' not in filtered
    assert 'noreply@example.com' not in filtered
    assert 'admin@example.com' not in filtered


@pytest.mark.asyncio
async def test_prioritize_personal_emails_first(extractor):
    """Test personal emails prioritized first."""
    emails = [
        'contact@example.com',
        'john.doe@example.com',
        'sales@example.com',
        'jane.smith@example.com'
    ]
    prioritized = extractor._prioritize_emails(emails, 'https://example.com')

    # Personal names should be first
    assert prioritized[0] in ['john.doe@example.com', 'jane.smith@example.com']
    assert prioritized[1] in ['john.doe@example.com', 'jane.smith@example.com']
    # Business-related third
    assert prioritized[2] == 'sales@example.com'
    # Other last
    assert prioritized[3] == 'contact@example.com'


@pytest.mark.asyncio
async def test_prioritize_business_emails_second(extractor):
    """Test business emails prioritized after personal."""
    emails = ['other@example.com', 'sales@example.com', 'ceo@example.com']
    prioritized = extractor._prioritize_emails(emails, 'https://example.com')

    # Business-related first (no personal names)
    assert prioritized[0] in ['sales@example.com', 'ceo@example.com']
    # Other last
    assert prioritized[-1] == 'other@example.com'


@pytest.mark.asyncio
async def test_extract_from_main_page(extractor, httpx_mock):
    """Test extraction from main website page."""
    httpx_mock.add_response(
        url="https://example.com",
        html='''
        <html>
            <body>
                <a href="mailto:contact@example.com">Contact Us</a>
                <p>Sales: sales@example.com</p>
            </body>
        </html>
        '''
    )

    emails = await extractor.extract_emails("https://example.com", max_pages=0)

    assert len(emails) >= 1
    assert "contact@example.com" in emails or "sales@example.com" in emails


@pytest.mark.asyncio
async def test_extract_from_contact_page(extractor, httpx_mock):
    """Test extraction from contact page."""
    # Mock main page (no emails)
    httpx_mock.add_response(
        url="https://example.com",
        html='<html><body>Welcome</body></html>'
    )

    # Mock contact page (has emails)
    httpx_mock.add_response(
        url="https://example.com/contact",
        html='<html><body><a href="mailto:john.doe@example.com">Contact</a></body></html>'
    )

    emails = await extractor.extract_emails("https://example.com", max_pages=1)

    assert "john.doe@example.com" in emails


@pytest.mark.asyncio
async def test_handle_404_gracefully(extractor, httpx_mock):
    """Test graceful handling of 404 errors."""
    httpx_mock.add_response(url="https://example.com", status_code=404)

    emails = await extractor.extract_emails("https://example.com", max_pages=0)

    assert emails == []  # Should return empty list, not crash


@pytest.mark.asyncio
async def test_handle_timeout_gracefully(extractor, httpx_mock):
    """Test graceful handling of timeouts."""
    httpx_mock.add_exception(httpx.TimeoutException("Request timeout"))

    emails = await extractor.extract_emails("https://example.com", max_pages=0)

    assert emails == []  # Should return empty list, not crash
