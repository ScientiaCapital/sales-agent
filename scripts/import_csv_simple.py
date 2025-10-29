#!/usr/bin/env python3
"""
Simple CSV Import (Non-Interactive)

Just imports the CSV without asking questions.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from scripts.import_csv import import_csv

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "companies_ready_to_import.csv"
    
    print(f"📤 Importing {csv_file}...")
    success = import_csv(csv_file)
    
    if success:
        print("\n✅ Import complete!")
        print("\nNext steps:")
        print("  1. Discover ATL contacts: python3 scripts/full_pipeline.py --skip-import")
        print("  2. Test agents: python3 agent_cli.py")
        print("  3. Enrich contacts: python3 scripts/batch_enrich_companies.py --mode email_only")
    else:
        sys.exit(1)

