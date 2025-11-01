"""
Quick Test: Hunter.io Email Service Integration

Tests the hunter_email_service.py with a real contractor domain.
Verifies API key works and ATL contact discovery functions correctly.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables from parent .env file
env_path = '/Users/tmkipper/Desktop/tk_projects/sales-agent/.env'
load_dotenv(env_path)

# Verify API key loaded
api_key = os.getenv('HUNTER_API_KEY')
if api_key:
    print(f"✅ Loaded HUNTER_API_KEY: {api_key[:10]}...")
else:
    print("❌ HUNTER_API_KEY not found in .env file!")

# Add backend to path
sys.path.insert(0, '/Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/pipeline-testing/backend')

from app.services.hunter_email_service import get_hunter_service


async def test_hunter_service():
    """Test Hunter.io service with a contractor domain"""

    print("=" * 80)
    print("TESTING HUNTER.IO EMAIL SERVICE")
    print("=" * 80)

    # Test domain: ACS Commercial Services (first contractor from CSV)
    test_domain = "acsfixit.com"
    company_name = "ACS Commercial Services LLC"

    print(f"\nTest Domain: {test_domain}")
    print(f"Company: {company_name}")
    print(f"\nSearching for ATL contacts...")
    print("-" * 80)

    try:
        # Get service
        hunter = await get_hunter_service()

        # Find emails
        result = await hunter.find_emails(test_domain, atl_only=True)

        # Print results
        print(f"\n✅ Status: {result.status}")
        print(f"Total ATL Contacts Found: {result.total_emails}")

        if result.status == "success" and result.contacts:
            print(f"\n📧 ATL Contacts at {company_name}:")
            print("-" * 80)

            for i, contact in enumerate(result.contacts, 1):
                print(f"\n{i}. {contact.first_name} {contact.last_name}")
                print(f"   Email: {contact.email}")
                print(f"   Title: {contact.position}")
                print(f"   Confidence: {contact.confidence}%")
                if contact.department:
                    print(f"   Department: {contact.department}")

        elif result.status == "rate_limited":
            print("\n⚠️  Rate limit hit - You've used your free tier searches for today")
            print("   Hunter.io free tier: 25 searches/month")

        elif result.status == "error":
            print(f"\n❌ Error: {result.error_message}")

        else:
            print(f"\n⚠️  No ATL contacts found at {test_domain}")
            print("   This might mean:")
            print("   - Company doesn't have public emails on Hunter.io")
            print("   - Domain is too new/small to be indexed")
            print("   - LinkedIn/Website scraping will be primary sources")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

        return result

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    result = asyncio.run(test_hunter_service())

    if result and result.status == "success":
        print("\n✅ Hunter.io integration is working correctly!")
    elif result and result.status == "rate_limited":
        print("\n⚠️  Hunter.io rate limit reached (expected on free tier)")
    else:
        print("\n⚠️  Hunter.io returned no contacts (LinkedIn/website will be primary sources)")
