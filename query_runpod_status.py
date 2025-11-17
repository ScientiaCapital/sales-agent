#!/usr/bin/env python3
"""Query RunPod endpoint status using GraphQL API."""

import json
import os
import requests
from dotenv import load_dotenv

# Load environment variables from backend/.env (works from any CWD)
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

RUNPOD_API_KEY = os.getenv('RUNPOD_API_KEY')
RUNPOD_API_URL = "https://api.runpod.io/graphql"

if not RUNPOD_API_KEY:
    print("❌ RUNPOD_API_KEY not found in environment variables")
    print("Please set it in .env file")
    exit(1)

print(f"🔑 Using API Key: {RUNPOD_API_KEY[:10]}...{RUNPOD_API_KEY[-4:]}")
print()

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {RUNPOD_API_KEY}"
}

# Query all serverless endpoints
query = """
query {
  myself {
    serverlessEndpoints {
      id
      name
      workersMin
      workersMax
      idleTimeout
      scalerType
      scalerValue
      gpuIds
    }
  }
}
"""

print("=" * 80)
print("Querying RunPod Serverless Endpoints")
print("=" * 80)
print()

response = requests.post(
    RUNPOD_API_URL,
    headers=headers,
    json={"query": query},
    timeout=30
)

print(f"HTTP Status: {response.status_code}")
print()

if response.status_code != 200:
    print(f"❌ API Request Failed:")
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.text}")
    exit(1)

data = response.json()

if "errors" in data:
    print("❌ GraphQL Errors:")
    for error in data["errors"]:
        print(f"   - {error.get('message', 'Unknown error')}")
    exit(1)

endpoints = data.get("data", {}).get("myself", {}).get("serverlessEndpoints", [])

if not endpoints:
    print("⚠️  No serverless endpoints found!")
    exit(0)

print(f"✅ Found {len(endpoints)} endpoint(s):\n")

for endpoint in endpoints:
    print(f"📍 Endpoint: {endpoint['name']}")
    print(f"   ID: {endpoint['id']}")
    print(f"   GPU: {endpoint['gpuIds']}")
    print(f"   Workers: {endpoint['workersMin']}-{endpoint['workersMax']}")
    print(f"   Scaler: {endpoint['scalerType']} (value: {endpoint['scalerValue']})")
    print(f"   Idle Timeout: {endpoint['idleTimeout']}s")
    print()

# If we found visiting_sapphire_kangaroo, show we need to check web console for workers
visiting_sapphire = [e for e in endpoints if e['name'] == 'visiting_sapphire_kangaroo']
if visiting_sapphire:
    print("=" * 80)
    print("ℹ️  NOTE: Worker status not available via GraphQL API")
    print("   Please check RunPod web console for worker initialization status")
    print(f"   URL: https://www.runpod.io/console/serverless/{visiting_sapphire[0]['id']}")
    print("=" * 80)

print("\n✅ Query Complete")
