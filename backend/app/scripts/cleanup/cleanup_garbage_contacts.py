#!/usr/bin/env python3
"""
Clean up garbage Apollo contacts (placeholder data from FREE tier).
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from collections import Counter

load_dotenv(Path(__file__).parent.parent.parent.parent.parent / '.env', override=True)

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Clean up garbage Apollo contacts')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--execute', action='store_true', help='Actually delete')
    parser.add_argument('--threshold', type=int, default=3, help='Min duplicates to consider garbage')
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get all Apollo contacts
    print("Fetching Apollo contacts...")
    result = sb.table('dim_contacts').select('contact_id, full_name, company_id').eq('source', 'apollo_search').execute()

    print(f"Total Apollo contacts: {len(result.data)}")

    # Count name occurrences
    name_counts = Counter(c['full_name'] for c in result.data)

    # Names appearing multiple times are garbage (placeholder data)
    garbage_names = {name for name, count in name_counts.items() if count >= args.threshold}

    print(f"\n=== GARBAGE NAMES (appearing {args.threshold}+ times) ===")
    for name, count in name_counts.most_common(30):
        if count >= args.threshold:
            print(f"  {name}: {count} times")

    # Get contacts to delete
    garbage_contacts = [c for c in result.data if c['full_name'] in garbage_names]

    print(f"\nGarbage names: {len(garbage_names)}")
    print(f"Contacts to delete: {len(garbage_contacts)}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made")
        return

    # Delete garbage contacts
    print(f"\nDeleting {len(garbage_contacts)} garbage contacts...")
    deleted = 0
    errors = 0

    for i, contact in enumerate(garbage_contacts, 1):
        try:
            sb.table('dim_contacts').delete().eq('contact_id', contact['contact_id']).execute()
            deleted += 1
            if deleted % 50 == 0:
                print(f"  Deleted {deleted}/{len(garbage_contacts)}...")
        except Exception as e:
            errors += 1
            print(f"  Error deleting {contact['full_name']}: {e}")

    print(f"\n=== CLEANUP COMPLETE ===")
    print(f"Deleted: {deleted}")
    print(f"Errors: {errors}")

    # Verify remaining
    remaining = sb.table('dim_contacts').select('contact_id', count='exact').eq('source', 'apollo_search').execute()
    print(f"Remaining Apollo contacts: {remaining.count}")


if __name__ == '__main__':
    main()
