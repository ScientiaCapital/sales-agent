#!/usr/bin/env python3
"""
Import Top 200 Dealer Prospects from CSV

Script to import top_200_prospects_final_20251029.csv using the existing CSV import endpoint.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import asyncio
from typing import Dict, Any

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
CSV_FILE_PATH = "/Users/tmkipper/Desktop/dealer-scraper-mvp/output/top_200_prospects_final_20251029.csv"


async def import_csv(file_path: str) -> Dict[str, Any]:
    """
    Import CSV file using the /api/v1/leads/import/csv endpoint.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Import result dictionary
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    url = f"{API_BASE_URL}/api/v1/leads/import/csv"
    
    print(f"📤 Importing CSV: {file_path}")
    print(f"🌐 API Endpoint: {url}")
    
    # Read CSV file
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'text/csv')}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                files=files,
                params={'strict_mode': False}  # Skip invalid rows instead of failing
            )
            
            if response.status_code == 200:
                result = response.json()
                print("\n✅ Import successful!")
                print(f"   Total leads: {result['total_leads']}")
                print(f"   Imported: {result['imported_count']}")
                print(f"   Failed: {result['failed_count']}")
                print(f"   Duration: {result['duration_ms']}ms")
                print(f"   Throughput: {result['leads_per_second']:.1f} leads/sec")
                
                if result.get('errors'):
                    print(f"\n⚠️  Errors ({len(result['errors'])}):")
                    for error in result['errors'][:5]:  # Show first 5 errors
                        print(f"   - {error}")
                    if len(result['errors']) > 5:
                        print(f"   ... and {len(result['errors']) - 5} more")
                
                return result
            else:
                error_detail = response.json().get('detail', response.text)
                print(f"\n❌ Import failed: {response.status_code}")
                print(f"   Error: {error_detail}")
                response.raise_for_status()


async def main():
    """Main execution"""
    try:
        result = await import_csv(CSV_FILE_PATH)
        print("\n🎉 Import complete!")
        return 0
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        return 1
    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP Error: {e.response.status_code}")
        print(f"   Detail: {e.response.text}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

