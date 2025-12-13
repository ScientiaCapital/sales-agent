#!/usr/bin/env python3
"""
Test CSV Import via Dealer Import API

Imports grandmaster_list_expanded_20251029.csv (8,278 contractor records)
via the dealer import endpoint with MEP+E scoring enabled.
"""

import requests
import json

# API endpoint
url = "http://localhost:8001/api/v1/dealer-import/import"

# Form data
data = {
    "file_path": "/Users/tmkipper/Desktop/dealer-scraper-mvp/output/grandmaster_list_expanded_20251029.csv",
    "batch_size": "50",
    "qualification_enabled": "true",
    "enrichment_enabled": "false"
}

print("=" * 80)
print("CSV Import Test")
print("=" * 80)
print(f"Endpoint: {url}")
print(f"File: {data['file_path']}")
print(f"Batch size: {data['batch_size']}")
print(f"Qualification: {data['qualification_enabled']}")
print(f"Enrichment: {data['enrichment_enabled']}")
print()
print("Sending request...")
print()

try:
    response = requests.post(url, data=data, timeout=3600)  # 1 hour timeout

    print(f"Status Code: {response.status_code}")
    print()

    if response.status_code == 200:
        result = response.json()
        print("✓ Import Successful!")
        print()
        print("Results:")
        print(json.dumps(result, indent=2))
    else:
        print("✗ Import Failed!")
        print()
        print("Response:")
        print(response.text)

except requests.exceptions.Timeout:
    print("✗ Request timed out after 1 hour")
except Exception as e:
    print(f"✗ Error: {e}")
