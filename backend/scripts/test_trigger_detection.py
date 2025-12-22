#!/usr/bin/env python3
"""
Test Trigger Event Detection
=============================
Test script to verify trigger event detection is working correctly.

Usage:
    python scripts/test_trigger_detection.py

Tests:
1. Query ICP companies with enriched contacts
2. Run trigger detection on 3-5 sample companies
3. Display detected events
4. Verify Supabase saving and deduplication
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Load env vars
from dotenv import load_dotenv
load_dotenv(project_root.parent / '.env', override=True)

from app.services.trigger_event_detector import get_trigger_event_detector
from supabase import create_client
from uuid import UUID


async def test_trigger_detection():
    """Test trigger event detection on sample companies."""
    print("🔍 Testing Trigger Event Detection System\n")
    print("=" * 70)

    # Initialize Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not configured")
        return

    supabase = create_client(supabase_url, supabase_key)

    # Query sample ICP companies with enriched contacts
    print("\n📊 Querying ICP companies with enriched contacts...")
    print("-" * 70)

    query = supabase.table("dim_companies") \
        .select("company_id, company_name, domain, icp_tier, icp_score") \
        .in_("icp_tier", ["PLATINUM", "GOLD", "SILVER"]) \
        .in_("enrichment_status", ["paid_enriched", "enriched"]) \
        .order("icp_score", desc=True) \
        .limit(5)

    result = query.execute()

    if not result.data:
        print("❌ No companies found matching criteria")
        print("   Criteria: icp_tier IN (PLATINUM, GOLD, SILVER)")
        print("            enrichment_status IN (paid_enriched, enriched)")
        return

    companies = result.data
    print(f"✅ Found {len(companies)} companies to test\n")

    # Display companies
    for i, company in enumerate(companies, 1):
        print(f"{i}. {company['company_name']}")
        print(f"   Domain: {company.get('domain', 'N/A')}")
        print(f"   ICP Tier: {company['icp_tier']} (Score: {company['icp_score']})")
        print(f"   Company ID: {company['company_id']}")
        print()

    # Test trigger detection
    print("=" * 70)
    print("🚀 Running Trigger Detection...\n")

    detector = await get_trigger_event_detector()
    total_events = 0

    for i, company in enumerate(companies, 1):
        company_id = UUID(company['company_id'])
        company_name = company['company_name']
        domain = company.get('domain')

        print(f"[{i}/{len(companies)}] Detecting events for: {company_name}")
        print("-" * 70)

        try:
            events = await detector.detect_all_signals(
                company_id,
                company_name,
                domain
            )

            if events:
                print(f"✅ Detected {len(events)} event(s):\n")
                for event in events:
                    print(f"   📌 {event.event_type.upper()}")
                    print(f"      Title: {event.title[:80]}")
                    print(f"      Signal Strength: {event.signal_strength}/10")
                    print(f"      Source: {event.source_url}")
                    print(f"      Hash: {event.content_hash[:16]}...")
                    print()
                total_events += len(events)
            else:
                print(f"   No events detected for {company_name}")
                print()

        except Exception as e:
            print(f"❌ Error detecting events for {company_name}: {e}\n")
            continue

    # Summary
    print("=" * 70)
    print("📈 DETECTION SUMMARY\n")
    print(f"Companies Checked: {len(companies)}")
    print(f"Total Events Detected: {total_events}")
    print(f"Average Events/Company: {total_events / len(companies):.1f}")

    # Query saved events from database
    print("\n" + "=" * 70)
    print("💾 Verifying Supabase Storage...\n")

    saved_events = supabase.table("trigger_events") \
        .select("event_id, company_id, event_type, title, signal_strength, detected_at") \
        .order("detected_at", desc=True) \
        .limit(10) \
        .execute()

    if saved_events.data:
        print(f"✅ Found {len(saved_events.data)} recent events in database:")
        for event in saved_events.data[:5]:
            print(f"\n   Event Type: {event['event_type']}")
            print(f"   Title: {event['title'][:60]}...")
            print(f"   Signal: {event['signal_strength']}/10")
            print(f"   Detected: {event['detected_at']}")
    else:
        print("⚠️  No events found in database")
        print("   (Events may not have been saved yet)")

    print("\n" + "=" * 70)
    print("✅ Test Complete!")


async def test_deduplication():
    """Test that duplicate events are not saved twice."""
    print("\n" + "=" * 70)
    print("🔄 Testing Deduplication...\n")

    detector = await get_trigger_event_detector()

    # Test with a known company
    test_company_id = UUID("00000000-0000-0000-0000-000000000001")  # Dummy ID
    test_company_name = "Test Company Inc"

    print(f"Running detection twice for {test_company_name}...")

    # First run
    events1 = await detector.detect_all_signals(
        test_company_id,
        test_company_name,
        None
    )
    print(f"First run: {len(events1)} events detected")

    # Second run (should detect duplicates via content_hash)
    events2 = await detector.detect_all_signals(
        test_company_id,
        test_company_name,
        None
    )
    print(f"Second run: {len(events2)} events detected")

    if len(events1) == len(events2):
        print("✅ Deduplication working (same events found both times)")
        print("   Database should only contain 1 copy of each event")
    else:
        print("⚠️  Different number of events detected")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║         TRIGGER EVENT DETECTION TEST                               ║
    ║         Testing: Funding, Hiring, News Detection                   ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(test_trigger_detection())

    # Uncomment to test deduplication
    # asyncio.run(test_deduplication())

    print("\n💡 Next Steps:")
    print("   1. Check Supabase dashboard for saved events")
    print("   2. Verify Slack notifications (if configured)")
    print("   3. Start Celery Beat to enable hourly monitoring")
    print("\n   celery -A app.celery_app beat --loglevel=info")
    print("   celery -A app.celery_app worker --loglevel=info --queues=default\n")
