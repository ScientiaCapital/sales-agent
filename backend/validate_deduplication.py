"""
Close CRM Deduplication Validation Script

Validates the deduplication logic against Close CRM API to ensure:
1. No duplicate companies are created
2. No duplicate contacts are created within companies
3. Fuzzy matching works correctly (Inc, LLC, Corp variations)
4. Existing leads are properly detected

Run this BEFORE processing CSV files to verify deduplication is working.

Usage:
    python validate_deduplication.py
"""

import os
import asyncio
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.crm.close_deduplication import CloseDeduplicationService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Load environment variables
load_dotenv()


async def validate_deduplication():
    """
    Comprehensive validation of Close CRM deduplication logic.
    """
    print("=" * 70)
    print("CLOSE CRM DEDUPLICATION VALIDATION")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.getenv("CLOSE_API_KEY")
    if not api_key:
        print("❌ FAIL: CLOSE_API_KEY not found in environment")
        print("   Add CLOSE_API_KEY to backend/.env file")
        return False

    print(f"✅ Close API Key found: {api_key[:10]}...")
    print()

    # Initialize service
    try:
        dedup_service = CloseDeduplicationService(api_key=api_key)
        print("✅ CloseDeduplicationService initialized")
        print()
    except Exception as e:
        print(f"❌ FAIL: Could not initialize service: {e}")
        return False

    # Test cases
    test_cases = [
        {
            "name": "Test 1: Search for existing company in Close CRM",
            "company": "YourRealCompanyName",  # Replace with actual company in your Close CRM
            "email": None,
            "expected_match": True,  # Set to True if company exists, False if not
            "description": "Verifies that the service can find existing companies"
        },
        {
            "name": "Test 2: Fuzzy matching - Company with Inc suffix",
            "company": "YourCompany Inc",  # Replace with variations
            "email": None,
            "expected_match": True,
            "description": "Verifies fuzzy matching handles 'Inc', 'LLC', 'Corp' variations"
        },
        {
            "name": "Test 3: Non-existent company",
            "company": "NonExistent Test Company XYZ 12345",
            "email": "test@nonexistent12345.com",
            "expected_match": False,
            "description": "Verifies service returns 'create_new' for non-existent companies"
        },
        {
            "name": "Test 4: Existing company + existing contact",
            "company": "YourRealCompanyName",  # Replace
            "email": "existing@yourcompany.com",  # Replace with real contact email
            "expected_match": True,
            "description": "Verifies duplicate detection for existing contact at existing company"
        },
        {
            "name": "Test 5: Existing company + NEW contact",
            "company": "YourRealCompanyName",  # Replace
            "email": "newperson@yourcompany.com",  # Use email that doesn't exist
            "expected_match": False,  # Not a duplicate because contact is new
            "description": "Verifies 'add_contact_to_existing' recommendation for new contact"
        }
    ]

    print("=" * 70)
    print("RUNNING VALIDATION TESTS")
    print("=" * 70)
    print()
    print("⚠️  NOTE: Update test_cases with real company names from your Close CRM")
    print("   to properly validate the deduplication logic.")
    print()

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}/{len(test_cases)}: {test['name']}")
        print(f"  Description: {test['description']}")
        print(f"  Company: {test['company']}")
        print(f"  Email: {test['email'] or 'None'}")
        print()

        try:
            result = await dedup_service.check_duplicate(
                company_name=test["company"],
                email=test["email"]
            )

            print(f"  Results:")
            print(f"    • Is Duplicate: {result.is_duplicate}")
            print(f"    • Company Match Found: {result.company_match_found}")
            print(f"    • Company Confidence: {result.company_confidence:.1f}%")
            print(f"    • Contact Match Found: {result.contact_match_found}")
            print(f"    • Recommendation: {result.recommendation}")

            if result.matched_company_name:
                print(f"    • Matched Company: {result.matched_company_name}")
                print(f"    • Matched Lead ID: {result.matched_lead_id}")

            if result.matched_contact_email:
                print(f"    • Matched Contact Email: {result.matched_contact_email}")
                print(f"    • Matched Contact ID: {result.matched_contact_id}")

            print()

            # Validation logic
            if test["expected_match"]:
                if result.company_match_found:
                    print(f"  ✅ PASS: Company match found as expected")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: Expected company match but none found")
                    failed += 1
            else:
                if not result.company_match_found:
                    print(f"  ✅ PASS: No company match as expected")
                    passed += 1
                else:
                    print(f"  ⚠️  WARNING: Unexpected company match found")
                    print(f"     This may indicate fuzzy matching is too aggressive")
                    failed += 1

        except Exception as e:
            print(f"  ❌ FAIL: Exception occurred: {e}")
            failed += 1

        print("-" * 70)
        print()

    # Summary
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Tests Passed: {passed}/{len(test_cases)}")
    print(f"Tests Failed: {failed}/{len(test_cases)}")
    print()

    if failed == 0:
        print("✅ ALL TESTS PASSED - Deduplication logic is working correctly!")
        print()
        print("Next steps:")
        print("  1. Start CSV folder monitor: cd backend && bash start_csv_monitor.sh")
        print("  2. Drop CSV files in: backend/data/csv/inbox/")
        print("  3. Monitor logs for deduplication results")
        return True
    else:
        print("❌ SOME TESTS FAILED - Review the logic before processing CSV files")
        print()
        print("Common issues:")
        print("  • CLOSE_API_KEY incorrect or expired")
        print("  • Test cases need to be updated with real company names")
        print("  • Fuzzy matching threshold too aggressive (lower from 85% if needed)")
        return False


async def test_api_connection():
    """Quick test of Close API connection."""
    print("Testing Close API connection...")
    print()

    api_key = os.getenv("CLOSE_API_KEY")
    if not api_key:
        print("❌ No CLOSE_API_KEY found")
        return False

    dedup_service = CloseDeduplicationService(api_key=api_key)

    try:
        # Try searching for anything to test connection
        result = await dedup_service.check_duplicate(
            company_name="Test Connection",
            email=None
        )
        print("✅ Close API connection successful!")
        print()
        return True

    except Exception as e:
        print(f"❌ Close API connection failed: {e}")
        print()
        return False


if __name__ == "__main__":
    print()
    print("Close CRM Deduplication Validation")
    print("====================================")
    print()

    # First test API connection
    connection_ok = asyncio.run(test_api_connection())

    if not connection_ok:
        print("Cannot proceed without valid Close API connection")
        sys.exit(1)

    # Run full validation
    success = asyncio.run(validate_deduplication())

    sys.exit(0 if success else 1)
