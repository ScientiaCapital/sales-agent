#!/usr/bin/env python3
"""
Live Enrichment Monitor - Real-time stats during enrichment
Shows: Companies enriched, ATL contacts found, hourly rate
"""
import os
import time
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('../.env')

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def get_enrichment_stats(since_minutes=60):
    """Get enrichment stats for last N minutes"""
    cutoff = (datetime.utcnow() - timedelta(minutes=since_minutes)).isoformat()

    # Companies enriched recently (apollo_organization_id indicates enrichment)
    enriched = supabase.table('dim_companies').select('company_id,company_name,updated_at').gte(
        'updated_at', cutoff
    ).not_.is_('apollo_organization_id', 'null').execute()

    # ATL contacts added recently
    atl_contacts = supabase.table('dim_contacts').select('contact_id,full_name,title,company_id,created_at').gte(
        'created_at', cutoff
    ).execute()

    # Total stats
    total_companies = supabase.table('dim_companies').select('company_id', count='exact').execute()
    total_enriched = supabase.table('dim_companies').select('company_id', count='exact').not_.is_('apollo_organization_id', 'null').execute()
    total_atl = supabase.table('dim_contacts').select('contact_id', count='exact').execute()

    return {
        'recent_enriched': len(enriched.data),
        'recent_atl': len(atl_contacts.data),
        'total_companies': total_companies.count,
        'total_enriched': total_enriched.count,
        'total_atl': total_atl.count,
        'enriched_companies': enriched.data[:10],  # Show top 10
        'new_atl': atl_contacts.data[:10],
    }

def display_dashboard(stats, elapsed_seconds):
    clear_screen()

    elapsed_min = elapsed_seconds / 60
    hourly_rate_companies = (stats['recent_enriched'] / elapsed_min * 60) if elapsed_min > 0 else 0
    hourly_rate_atl = (stats['recent_atl'] / elapsed_min * 60) if elapsed_min > 0 else 0

    print("=" * 80)
    print("🚀 LIVE ENRICHMENT MONITOR".center(80))
    print("=" * 80)
    print()

    print(f"⏱️  RUNTIME: {int(elapsed_min)} minutes")
    print()

    print("📊 REAL-TIME STATS (Last 60 minutes)")
    print("-" * 80)
    print(f"  Companies Enriched:  {stats['recent_enriched']:>6} ({hourly_rate_companies:.1f}/hour)")
    print(f"  ATL Contacts Found:  {stats['recent_atl']:>6} ({hourly_rate_atl:.1f}/hour)")
    print()

    print("📈 TOTAL DATABASE")
    print("-" * 80)
    print(f"  Total Companies:     {stats['total_companies']:>6}")
    print(f"  Enriched Companies:  {stats['total_enriched']:>6} ({stats['total_enriched']/stats['total_companies']*100:.1f}%)")
    print(f"  Total ATL Contacts:  {stats['total_atl']:>6}")
    print()

    if stats['enriched_companies']:
        print("✨ RECENTLY ENRICHED COMPANIES")
        print("-" * 80)
        for company in stats['enriched_companies'][:5]:
            print(f"  • {company['company_name']}")
        print()

    if stats['new_atl']:
        print("👤 NEW ATL CONTACTS")
        print("-" * 80)
        for contact in stats['new_atl'][:5]:
            print(f"  • {contact['full_name']} - {contact.get('title', 'N/A')}")
        print()

    print("=" * 80)
    print(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    print("Press Ctrl+C to stop monitoring")

def main():
    print("🔍 Starting live enrichment monitor...")
    print("This will refresh every 5 seconds\n")
    time.sleep(2)

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            stats = get_enrichment_stats(since_minutes=60)
            display_dashboard(stats, elapsed)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")

if __name__ == "__main__":
    main()
