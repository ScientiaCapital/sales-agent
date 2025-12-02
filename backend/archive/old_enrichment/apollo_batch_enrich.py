#!/usr/bin/env python3
"""
Apollo Batch Enrichment - Process the Apollo enrichment queue

Run this script when Apollo credits are purchased to enrich all queued leads.

Usage:
    # View queue stats
    python apollo_batch_enrich.py --stats

    # Process queue (dry run - no API calls)
    python apollo_batch_enrich.py --dry-run

    # Process queue (real enrichment)
    python apollo_batch_enrich.py --process

    # Process specific number of leads
    python apollo_batch_enrich.py --process --limit 50

    # Export queue to CSV for manual review
    python apollo_batch_enrich.py --export

    # Check Apollo API status
    python apollo_batch_enrich.py --check-apollo

IMPORTANT:
    - Apollo costs ~$0.03-0.05 per contact enriched
    - Rate limit: 10 requests/second, 2400 credits/month ($99 plan)
    - Always run --dry-run first to estimate costs
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime
from typing import Optional

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.apollo_enrichment_queue import (
    get_apollo_queue,
    QueueStatus,
    QueuePriority
)


async def check_apollo_status() -> bool:
    """Check if Apollo API is configured and working."""
    api_key = os.getenv("APOLLO_API_KEY")

    if not api_key:
        print("❌ APOLLO_API_KEY not found in environment")
        print("   Add APOLLO_API_KEY to your .env file")
        print("   Get API key: https://app.apollo.io/#/settings/integrations/api")
        return False

    print(f"✅ Apollo API key found: {api_key[:10]}...")

    # Test API connection
    try:
        from app.services.apollo import ApolloService
        apollo = ApolloService()
        # Apollo doesn't have a simple health check, so we'll just verify initialization
        print("✅ Apollo service initialized successfully")
        print("\n⚠️  NOTE: Apollo credits are currently DISABLED in qualification_agent.py")
        print("   To re-enable, uncomment the Apollo section (~lines 630-710)")
        return True
    except Exception as e:
        print(f"❌ Apollo service failed to initialize: {e}")
        return False


async def show_queue_stats():
    """Display queue statistics."""
    queue = get_apollo_queue()
    stats = queue.get_queue_stats()

    print("\n" + "=" * 60)
    print("APOLLO ENRICHMENT QUEUE STATS")
    print("=" * 60)
    print(f"Total entries:        {stats['total']}")
    print(f"Pending:              {stats['pending']}")
    print(f"Completed:            {stats['completed']}")
    print(f"Failed:               {stats['failed']}")
    print()
    print("By Priority:")
    print(f"  🔥 High (1):        {stats['by_priority'].get(1, 0)}")
    print(f"  ⭐ Medium (2):      {stats['by_priority'].get(2, 0)}")
    print(f"  📋 Low (3):         {stats['by_priority'].get(3, 0)}")
    print()
    print(f"Contacts needing email: {stats['contacts_needing_email']}")
    print()

    # Cost estimate
    estimated_contacts = stats['pending'] * 3  # Assume ~3 contacts per company
    estimated_cost = estimated_contacts * 0.04  # ~$0.04 per contact average
    print("Estimated Enrichment Cost:")
    print(f"  Companies to enrich:  {stats['pending']}")
    print(f"  Est. contacts:        ~{estimated_contacts}")
    print(f"  Est. cost:            ~${estimated_cost:.2f}")
    print("=" * 60)


async def export_queue():
    """Export queue to CSV."""
    queue = get_apollo_queue()
    output_file = queue.export_for_enrichment()
    print(f"\n✅ Queue exported to: {output_file}")
    print("   Open in Excel/Sheets to review before enrichment")


async def process_queue(dry_run: bool = True, limit: Optional[int] = None):
    """Process the Apollo enrichment queue."""
    queue = get_apollo_queue()
    pending = queue.get_pending_entries(limit=limit)

    if not pending:
        print("\n✅ No pending entries in queue!")
        return

    print(f"\n{'DRY RUN - ' if dry_run else ''}Processing {len(pending)} entries...")
    print("=" * 60)

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No actual API calls will be made")
        print("   Run with --process to actually enrich leads\n")

    # Check Apollo availability
    if not dry_run:
        api_key = os.getenv("APOLLO_API_KEY")
        if not api_key:
            print("❌ APOLLO_API_KEY not found - cannot process queue")
            return

        try:
            from app.services.apollo import ApolloService
            apollo = ApolloService()
        except Exception as e:
            print(f"❌ Apollo service failed: {e}")
            return

    total_contacts = 0
    total_cost = 0.0

    for i, entry in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {entry.company_name}")
        print(f"   Website: {entry.company_website or 'N/A'}")
        print(f"   Priority: {entry.priority}")
        print(f"   Existing contacts needing email: {len(entry.existing_contacts)}")

        if dry_run:
            # Estimate what would happen
            est_contacts = 3 + len(entry.existing_contacts)
            est_cost = est_contacts * 0.04
            print(f"   [DRY RUN] Would enrich ~{est_contacts} contacts (~${est_cost:.2f})")
            total_contacts += est_contacts
            total_cost += est_cost
        else:
            # Actual enrichment
            queue.mark_processing(entry.company_name)

            try:
                enriched_contacts = []

                # Method 1: Domain search (if website available)
                if entry.company_website:
                    from app.services.hunter_service import extract_domain
                    domain = extract_domain(entry.company_website)

                    domain_contacts = await apollo.search_and_enrich_contacts(
                        domain=domain,
                        max_results=10,
                        reveal_emails=True,
                        reveal_phones=False
                    )

                    if domain_contacts:
                        enriched_contacts.extend(domain_contacts)
                        print(f"   ✅ Domain search found {len(domain_contacts)} contacts")

                # Method 2: Enrich existing contacts (if names available)
                for contact in entry.existing_contacts:
                    if contact.get('first_name') and contact.get('last_name'):
                        email_result = await apollo.find_email(
                            first_name=contact['first_name'],
                            last_name=contact['last_name'],
                            domain=domain if entry.company_website else None,
                            company_name=entry.company_name
                        )
                        if email_result and email_result.get('email'):
                            contact['email'] = email_result['email']
                            contact['email_confidence'] = email_result.get('confidence', 'unknown')
                            enriched_contacts.append(contact)
                            print(f"   ✅ Found email for {contact['first_name']} {contact['last_name']}")

                # Mark completed
                queue.mark_completed(entry.company_name, enriched_contacts)
                total_contacts += len(enriched_contacts)
                total_cost += len(enriched_contacts) * 0.04

                print(f"   ✅ Enriched {len(enriched_contacts)} contacts")

            except Exception as e:
                queue.mark_failed(entry.company_name, str(e))
                print(f"   ❌ Failed: {e}")

            # Rate limit: 10 req/sec = 100ms delay
            await asyncio.sleep(0.1)

    print("\n" + "=" * 60)
    print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
    print("=" * 60)
    print(f"Entries processed:    {len(pending)}")
    print(f"Contacts enriched:    {total_contacts}")
    print(f"Estimated cost:       ${total_cost:.2f}")

    if dry_run:
        print("\n💡 To actually enrich, run:")
        print("   python apollo_batch_enrich.py --process")


async def main():
    parser = argparse.ArgumentParser(description="Apollo Batch Enrichment Queue Processor")
    parser.add_argument("--stats", action="store_true", help="Show queue statistics")
    parser.add_argument("--export", action="store_true", help="Export queue to CSV")
    parser.add_argument("--dry-run", action="store_true", help="Process queue without API calls")
    parser.add_argument("--process", action="store_true", help="Process queue with real API calls")
    parser.add_argument("--limit", type=int, help="Limit number of entries to process")
    parser.add_argument("--check-apollo", action="store_true", help="Check Apollo API status")

    args = parser.parse_args()

    print("=" * 60)
    print("APOLLO BATCH ENRICHMENT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    if args.check_apollo:
        await check_apollo_status()
    elif args.stats:
        await show_queue_stats()
    elif args.export:
        await export_queue()
    elif args.dry_run:
        await process_queue(dry_run=True, limit=args.limit)
    elif args.process:
        print("\n⚠️  WARNING: This will make real Apollo API calls!")
        print("   Each contact enrichment costs ~$0.03-0.05")
        response = input("   Continue? (yes/no): ")
        if response.lower() == "yes":
            await process_queue(dry_run=False, limit=args.limit)
        else:
            print("   Cancelled.")
    else:
        # Default: show stats
        await show_queue_stats()
        print("\n💡 Commands:")
        print("   --stats       Show queue statistics")
        print("   --export      Export queue to CSV")
        print("   --dry-run     Simulate processing (no API calls)")
        print("   --process     Process queue (real API calls)")
        print("   --check-apollo  Check Apollo API status")


if __name__ == "__main__":
    asyncio.run(main())
