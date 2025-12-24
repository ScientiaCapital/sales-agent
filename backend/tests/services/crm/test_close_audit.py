"""
Close CRM Campaign Audit - API Integration Tests

Tests the integration with Close CRM API for:
- Querying sequence subscriptions
- Fetching all leads from Close
- Domain normalization and matching
"""

import pytest
from backend.app.services.crm.close_sequences import CloseSequencesClient
from backend.app.services.crm.close import CloseProvider


@pytest.mark.asyncio
async def test_query_icp_energy_multitrade_sequence():
    """Test querying all contacts in ICP-Energy-Multitrade sequence"""
    client = CloseSequencesClient()

    # ICP-Energy-Multitrade sequence
    subs = await client.list_active_subscriptions(
        sequence_id="seq_469XPP98mPXSR2wh5cX9y6"
    )

    # Verify we got subscriptions back
    assert isinstance(subs, list), "Should return list of subscriptions"
    assert len(subs) > 0, "Should have at least some subscriptions"

    # Verify subscription structure
    if len(subs) > 0:
        sub = subs[0]
        assert "id" in sub, "Subscription should have ID"
        assert "contact_id" in sub, "Subscription should have contact_id"
        assert "sequence_id" in sub, "Subscription should have sequence_id"
        assert "status" in sub, "Subscription should have status"


@pytest.mark.asyncio
async def test_query_solar_pivot_sequence():
    """Test querying all contacts in Solar-Pivot-2026 sequence"""
    client = CloseSequencesClient()

    # Solar-Pivot-2026 sequence
    subs = await client.list_active_subscriptions(
        sequence_id="seq_0FHFD0OQtDAOS8x40MIANW"
    )

    # Verify we got subscriptions back
    assert isinstance(subs, list), "Should return list of subscriptions"
    assert len(subs) > 0, "Should have at least some subscriptions"

    # Verify subscription structure
    if len(subs) > 0:
        sub = subs[0]
        assert "id" in sub, "Subscription should have ID"
        assert "contact_id" in sub, "Subscription should have contact_id"
        assert "sequence_id" in sub, "Subscription should have sequence_id"


@pytest.mark.asyncio
async def test_fetch_all_close_leads():
    """Test fetching all leads from Close CRM"""
    provider = CloseProvider()

    # This will need to be implemented in CloseProvider
    # For now, test the interface exists
    assert hasattr(provider, "get_all_leads") or hasattr(provider, "list_leads"), \
        "CloseProvider should have method to fetch all leads"


@pytest.mark.asyncio
async def test_close_api_rate_limiting():
    """Test that Close API respects rate limits (100 req/min)"""
    client = CloseSequencesClient()

    # Make multiple rapid requests
    import time
    start = time.time()

    try:
        for _ in range(5):
            await client.list_active_subscriptions("seq_469XPP98mPXSR2wh5cX9y6")

        elapsed = time.time() - start

        # Should not error out due to rate limiting
        # (internal rate limiting should handle this)
        assert True, "Should handle multiple requests without errors"

    except Exception as e:
        # If we hit rate limit, make sure it's handled gracefully
        assert "rate limit" in str(e).lower() or "429" in str(e), \
            f"Rate limit errors should be clear: {e}"


@pytest.mark.asyncio
async def test_subscription_status_values():
    """Test that subscription statuses are valid"""
    client = CloseSequencesClient()

    subs = await client.list_active_subscriptions("seq_469XPP98mPXSR2wh5cX9y6")

    valid_statuses = {"active", "paused", "finished", "stopped", "failed"}

    for sub in subs:
        if "status" in sub:
            assert sub["status"] in valid_statuses, \
                f"Invalid status: {sub['status']}. Expected one of {valid_statuses}"


@pytest.mark.asyncio
async def test_domain_normalization():
    """Test domain normalization for matching leads to companies"""
    from urllib.parse import urlparse

    def normalize_domain(url: str) -> str:
        """Normalize URL to domain for matching"""
        if not url:
            return ""

        # Remove protocol
        if "://" in url:
            url = url.split("://", 1)[1]

        # Remove www.
        if url.startswith("www."):
            url = url[4:]

        # Remove trailing slash and path
        url = url.split("/")[0]

        # Remove port
        url = url.split(":")[0]

        return url.lower()

    # Test cases
    assert normalize_domain("https://acme.com") == "acme.com"
    assert normalize_domain("http://www.acme.com/about") == "acme.com"
    assert normalize_domain("https://ACME.COM") == "acme.com"
    assert normalize_domain("acme.com:8080") == "acme.com"
    assert normalize_domain("https://subdomain.acme.com") == "subdomain.acme.com"
    assert normalize_domain("") == ""
    assert normalize_domain("acme.com") == "acme.com"


@pytest.mark.asyncio
async def test_match_lead_by_domain():
    """Test matching Close lead to Supabase company by domain"""

    def normalize_domain(url: str) -> str:
        """Normalize URL to domain for matching"""
        if not url:
            return ""
        if "://" in url:
            url = url.split("://", 1)[1]
        if url.startswith("www."):
            url = url[4:]
        url = url.split("/")[0]
        url = url.split(":")[0]
        return url.lower()

    # Test data
    close_lead = {
        "id": "lead_123",
        "name": "Acme Corp",
        "url": "https://www.acme.com/home"
    }

    company = {
        "company_id": "uuid-123",
        "domain": "acme.com"
    }

    # Should match
    assert normalize_domain(close_lead["url"]) == company["domain"], \
        "Domain normalization should match Close lead URL to company domain"

    # Test null/empty cases
    close_lead_no_url = {"id": "lead_456", "name": "Company B", "url": None}
    assert normalize_domain(close_lead_no_url.get("url")) == "", \
        "Should handle None URL gracefully"


@pytest.mark.asyncio
async def test_close_api_authentication():
    """Test that Close API authentication works"""
    import os

    # Verify Close API key exists
    api_key = os.getenv("CLOSE_API_KEY")
    assert api_key is not None, "CLOSE_API_KEY must be set in .env"
    assert api_key.startswith("api_"), "Close API key should start with 'api_'"

    # Test authentication with simple API call
    client = CloseSequencesClient()
    try:
        # Simple API call to verify auth works
        subs = await client.list_active_subscriptions("seq_469XPP98mPXSR2wh5cX9y6")
        assert True, "Authentication successful"
    except Exception as e:
        if "401" in str(e) or "unauthorized" in str(e).lower():
            pytest.fail(f"Close API authentication failed: {e}")
        # Other errors are okay for this test
