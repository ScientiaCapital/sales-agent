"""Tests for email extraction service."""
import pytest
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
