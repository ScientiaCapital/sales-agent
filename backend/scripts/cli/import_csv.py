#!/usr/bin/env python3
"""
Import CSV file to Sales Agent API

Usage:
    python3 scripts/import_csv.py [file_path] [--strict]

Examples:
    python3 scripts/import_csv.py companies_ready_to_import.csv
    python3 scripts/import_csv.py companies_ready_to_import.csv --strict
"""
import requests
import sys
from pathlib import Path

def import_csv(file_path, strict_mode=False, base_url="http://localhost:8001"):
    """Import CSV file via API"""
    url = f"{base_url}/api/leads/import/csv"
    params = {"strict_mode": strict_mode} if strict_mode else {}
    
    # Check file exists
    if not Path(file_path).exists():
        print(f"❌ Error: File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f, 'text/csv')}
            print(f"📤 Uploading {file_path}...")
            response = requests.post(url, files=files, params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success!")
            print(f"   Filename: {result['filename']}")
            print(f"   Total rows: {result['total_leads']}")
            print(f"   ✅ Imported: {result['imported_count']}")
            print(f"   ❌ Failed: {result['failed_count']}")
            print(f"   ⏱️  Duration: {result['duration_ms']}ms ({result['duration_ms']/1000:.2f}s)")
            print(f"   ⚡ Rate: {result['leads_per_second']:.2f} leads/sec")
            
            if result.get('errors'):
                print(f"\n⚠️  Validation Errors ({len(result['errors'])}):")
                for i, error in enumerate(result['errors'][:10], 1):  # Show first 10
                    print(f"   {i}. {error}")
                if len(result['errors']) > 10:
                    print(f"   ... and {len(result['errors']) - 10} more errors")
            
            return True
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Detail: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to server at {base_url}")
        print(f"   Make sure the server is running: python3 start_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "companies_ready_to_import.csv"
    strict = "--strict" in sys.argv
    
    success = import_csv(file_path, strict_mode=strict)
    sys.exit(0 if success else 1)

