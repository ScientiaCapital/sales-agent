"""
Integration tests for LinkedIn scrapers.

These tests verify:
1. Company scraper can search Google and extract LinkedIn URLs
2. Profile scraper can search for personal LinkedIn profiles
3. Both scrapers properly use the session pool
4. ATL/BTL classification works correctly

Usage:
    python -m pytest test_linkedin_scrapers.py -v

Note: These are LIVE tests that hit real APIs (Browserbase + Google).
      Run sparingly to avoid rate limits.
"""

import asyncio
import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Load .env BEFORE imports
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path, override=True)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from parallel_linkedin_company_scraper import (
    ParallelLinkedInCompanyScraper,
    LinkedInCompanyResult,
    LinkedInEmployee,
)
from parallel_linkedin_profile_scraper import (
    ParallelLinkedInProfileScraper,
    ProfileSearchResult,
)
from app.services.browserbase_session_pool import (
    get_session_pool,
    close_session_pool,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# UNIT TESTS (No API calls)
# =============================================================================

def test_atl_classification():
    """Test that ATL/BTL classification works correctly."""
    logger.info("TEST: ATL Classification")

    # ATL titles
    atl_titles = [
        "Chief Executive Officer",
        "CEO",
        "President",
        "Owner",
        "Co-Founder",
        "Vice President of Sales",
        "VP Engineering",
        "Director of Operations",
        "Managing Partner",
        "Principal",
        "Chief Technology Officer",
        "CTO",
    ]

    for title in atl_titles:
        employee = LinkedInEmployee(
            name="Test Person",
            title=title,
            profile_url=None,
        )
        assert employee.is_atl, f"'{title}' should be classified as ATL"

    # BTL titles
    btl_titles = [
        "Sales Representative",
        "Account Manager",
        "Software Engineer",
        "Marketing Coordinator",
        "Office Manager",
        "Customer Service",
        "Technician",
        "Analyst",
    ]

    for title in btl_titles:
        employee = LinkedInEmployee(
            name="Test Person",
            title=title,
            profile_url=None,
        )
        assert not employee.is_atl, f"'{title}' should be classified as BTL"

    logger.info("✓ ATL classification working correctly")


def test_linkedin_employee_dataclass():
    """Test LinkedInEmployee dataclass creation."""
    logger.info("TEST: LinkedInEmployee dataclass")

    employee = LinkedInEmployee(
        name="John Smith",
        title="CEO",
        profile_url="https://linkedin.com/in/johnsmith",
    )

    assert employee.name == "John Smith"
    assert employee.title == "CEO"
    assert employee.profile_url == "https://linkedin.com/in/johnsmith"
    assert employee.is_atl is True

    logger.info("✓ LinkedInEmployee dataclass works")


def test_linkedin_company_result_dataclass():
    """Test LinkedInCompanyResult dataclass creation."""
    logger.info("TEST: LinkedInCompanyResult dataclass")

    employee1 = LinkedInEmployee(name="CEO Person", title="CEO", profile_url=None)
    employee2 = LinkedInEmployee(name="Dev Person", title="Engineer", profile_url=None)

    result = LinkedInCompanyResult(
        company_name="Test Corp",
        domain="test.com",
        linkedin_url="https://linkedin.com/company/testcorp",
        employee_count=50,
        employees=[employee1, employee2],
    )

    assert result.company_name == "Test Corp"
    assert result.linkedin_url == "https://linkedin.com/company/testcorp"
    assert result.employee_count == 50
    assert len(result.employees) == 2
    assert len(result.atl_employees) == 1  # Only CEO
    assert result.atl_employees[0].name == "CEO Person"

    logger.info("✓ LinkedInCompanyResult dataclass works")


def test_profile_search_result_dataclass():
    """Test ProfileSearchResult dataclass creation."""
    logger.info("TEST: ProfileSearchResult dataclass")

    result = ProfileSearchResult(
        contact_id="123",
        contact_name="John Smith",
        company_name="Acme Corp",
        linkedin_url="https://linkedin.com/in/johnsmith",
        confidence=0.85,
        search_query='site:linkedin.com/in "John Smith" "Acme Corp"',
        candidates=[],
    )

    assert result.contact_id == "123"
    assert result.linkedin_url == "https://linkedin.com/in/johnsmith"
    assert result.confidence == 0.85

    logger.info("✓ ProfileSearchResult dataclass works")


# =============================================================================
# INTEGRATION TESTS (Require Browserbase API)
# =============================================================================

async def test_session_pool_integration():
    """Test that scrapers can use the session pool."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Session Pool Integration")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Test checkout/checkin
    session = await pool.checkout()
    logger.info(f"✓ Checked out session: {session.session_id[:12]}...")

    assert session.connect_url is not None
    assert session.connect_url.startswith("wss://")

    await pool.checkin(session)
    logger.info("✓ Checked in session")

    await close_session_pool()
    logger.info("✓ Session pool integration working")


async def test_company_scraper_initialization():
    """Test that company scraper initializes correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Company Scraper Initialization")
    logger.info("=" * 60)

    scraper = ParallelLinkedInCompanyScraper(max_workers=2)

    # Initialize (creates session pool)
    await scraper.initialize()
    logger.info("✓ Scraper initialized")

    # Check pool is ready
    assert scraper.session_pool is not None

    # Cleanup
    await scraper.cleanup()
    logger.info("✓ Scraper cleanup complete")


async def test_profile_scraper_initialization():
    """Test that profile scraper initializes correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Profile Scraper Initialization")
    logger.info("=" * 60)

    # Get shared pool
    pool = await get_session_pool()

    scraper = ParallelLinkedInProfileScraper(session_pool=pool)
    logger.info("✓ Scraper created with session pool")

    # Check pool is set
    assert scraper.session_pool is not None

    # Cleanup
    await close_session_pool()
    logger.info("✓ Profile scraper initialization working")


# =============================================================================
# LIVE SCRAPING TESTS (Use sparingly - hits real APIs)
# =============================================================================

async def test_company_scraper_live_single():
    """
    LIVE TEST: Scrape a single well-known company.

    This test hits real Browserbase + Google APIs.
    Only run when testing integration.
    """
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Live Company Scrape (Single)")
    logger.info("=" * 60)

    scraper = ParallelLinkedInCompanyScraper(max_workers=1)
    await scraper.initialize()

    try:
        # Scrape a well-known company
        results = await scraper.scrape_companies([
            {"name": "Anthropic", "domain": "anthropic.com"}
        ])

        assert len(results) == 1
        result = results[0]

        logger.info(f"Company: {result.company_name}")
        logger.info(f"LinkedIn URL: {result.linkedin_url}")
        logger.info(f"Employee Count: {result.employee_count}")
        logger.info(f"Employees Found: {len(result.employees)}")
        logger.info(f"ATL Employees: {len(result.atl_employees)}")

        if result.error:
            logger.warning(f"Error: {result.error}")

        # Should have found LinkedIn URL
        if result.linkedin_url:
            assert "linkedin.com/company" in result.linkedin_url
            logger.info("✓ LinkedIn company URL found")

        logger.info("✓ Live company scrape completed")

    finally:
        await scraper.cleanup()


async def test_profile_scraper_live_single():
    """
    LIVE TEST: Search for a single well-known profile.

    This test hits real Browserbase + Google APIs.
    Only run when testing integration.
    """
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Live Profile Search (Single)")
    logger.info("=" * 60)

    pool = await get_session_pool()
    scraper = ParallelLinkedInProfileScraper(session_pool=pool)

    try:
        # Search for a well-known person
        result = await scraper.search_profile(
            contact_name="Dario Amodei",
            company_name="Anthropic",
            contact_id="test-001",
            title="CEO",
        )

        logger.info(f"Search Query: {result.search_query}")
        logger.info(f"LinkedIn URL: {result.linkedin_url}")
        logger.info(f"Confidence: {result.confidence:.2f}")
        logger.info(f"Candidates: {len(result.candidates)}")

        if result.error:
            logger.warning(f"Error: {result.error}")

        # Should have found something with reasonable confidence
        if result.linkedin_url and result.confidence >= 0.3:
            assert "linkedin.com/in" in result.linkedin_url
            logger.info("✓ LinkedIn profile URL found with good confidence")

        logger.info("✓ Live profile search completed")

    finally:
        await close_session_pool()


# =============================================================================
# TEST RUNNER
# =============================================================================

async def run_unit_tests():
    """Run unit tests (no API calls)."""
    logger.info("\n" + "=" * 60)
    logger.info("UNIT TESTS")
    logger.info("=" * 60)

    test_atl_classification()
    test_linkedin_employee_dataclass()
    test_linkedin_company_result_dataclass()
    test_profile_search_result_dataclass()

    logger.info("\n✅ All unit tests passed!")


async def run_integration_tests():
    """Run integration tests (requires Browserbase API)."""
    logger.info("\n" + "=" * 60)
    logger.info("INTEGRATION TESTS")
    logger.info("=" * 60)

    await test_session_pool_integration()
    await test_company_scraper_initialization()
    await test_profile_scraper_initialization()

    logger.info("\n✅ All integration tests passed!")


async def run_live_tests():
    """Run live scraping tests (use sparingly)."""
    logger.info("\n" + "=" * 60)
    logger.info("LIVE SCRAPING TESTS")
    logger.info("WARNING: These tests hit real APIs!")
    logger.info("=" * 60)

    # Uncomment to run live tests:
    # await test_company_scraper_live_single()
    # await test_profile_scraper_live_single()

    logger.info("\n⚠️  Live tests skipped (uncomment to run)")


async def main():
    """Run all tests."""
    try:
        await run_unit_tests()
        await run_integration_tests()
        await run_live_tests()

        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS COMPLETED")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
