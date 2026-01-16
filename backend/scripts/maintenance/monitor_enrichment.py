#!/usr/bin/env python3
"""
Real-time Enrichment Monitor
Tracks enrichment progress for the current batch run
"""
import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client

load_dotenv(Path(__file__).parent.parent / '.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def monitor_progress(target_count=250, interval_seconds=30):
    """Monitor enrichment progress in real-time"""
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    start_time = datetime.now(timezone.utc)

    print(f"🔍 Monitoring enrichment progress (target: {target_count} companies)")
    print(f"   Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   Refresh interval: {interval_seconds}s\n")

    try:
        while True:
            # Check pending
            pending = sb.table('dim_companies').select('company_id', count='exact')\
                .is_('last_enriched_at', 'null').not_.is_('website', 'null').execute()

            # Check recently enriched (since start)
            recently = sb.table('dim_companies').select('company_name,last_enriched_at', count='exact')\
                .gte('last_enriched_at', start_time.isoformat())\
                .order('last_enriched_at', desc=True).limit(10).execute()

            completed = recently.count
            remaining = target_count - completed
            progress_pct = (completed / target_count * 100) if target_count > 0 else 0

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            rate = completed / (elapsed / 60) if elapsed > 0 else 0
            eta_mins = remaining / rate if rate > 0 else 0

            # Clear screen and show stats
            print("\033[2J\033[H", end="")  # Clear screen
            print(f"{'='*60}")
            print(f"🚀 ENRICHMENT PROGRESS")
            print(f"{'='*60}")
            print(f"Target:     {target_count} companies")
            print(f"Completed:  {completed} ({progress_pct:.1f}%)")
            print(f"Remaining:  {remaining}")
            print(f"Pending:    {pending.count} total in queue")
            print(f"\nRate:       {rate:.1f} companies/min")
            print(f"Elapsed:    {int(elapsed/60)}m {int(elapsed%60)}s")
            print(f"ETA:        {int(eta_mins)}m")

            if recently.data:
                print(f"\n📊 Last 10 enriched:")
                for i, c in enumerate(recently.data[:10], 1):
                    enriched_at = datetime.fromisoformat(c['last_enriched_at'].replace('Z', '+00:00'))
                    ago_secs = (datetime.now(timezone.utc) - enriched_at).total_seconds()
                    print(f"  {i:2d}. {c['company_name'][:45]:45s} ({int(ago_secs)}s ago)")

            if completed >= target_count:
                print(f"\n✅ TARGET REACHED! Processed {completed}/{target_count} companies")
                break

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print(f"\n\n⏸ Monitoring stopped. Progress: {completed}/{target_count}")

if __name__ == '__main__':
    monitor_progress()
