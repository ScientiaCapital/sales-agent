#!/usr/bin/env python3
"""Debug RunPod serverless endpoint stuck in initializing status."""

import os
import json
import requests
from datetime import datetime

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
if not RUNPOD_API_KEY:
    raise ValueError("RUNPOD_API_KEY environment variable not set")
GRAPHQL_URL = "https://api.runpod.io/graphql"

def query_graphql(query: str) -> dict:
    """Execute GraphQL query against RunPod API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }

    response = requests.post(
        GRAPHQL_URL,
        json={"query": query},
        headers=headers,
        timeout=30
    )

    response.raise_for_status()
    return response.json()

def list_endpoints():
    """List all serverless endpoints."""
    query = """
    query {
      myself {
        serverlessEndpoints {
          id
          name
          templateId
          version
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

    result = query_graphql(query)
    return result.get("data", {}).get("myself", {}).get("serverlessEndpoints", [])

def get_endpoint_workers(endpoint_id: str):
    """Get detailed worker information for an endpoint."""
    query = f"""
    query {{
      endpoint(endpointId: "{endpoint_id}") {{
        id
        name
        workers {{
          id
          status
          location
          gpuTypeId
          startedAt
          readyAt
        }}
      }}
    }}
    """

    result = query_graphql(query)
    return result.get("data", {}).get("endpoint", {})

def main():
    print("=" * 80)
    print("RunPod Endpoint Debug Tool")
    print("=" * 80)
    print()

    # List all endpoints
    print("📋 Querying all serverless endpoints...")
    endpoints = list_endpoints()

    if not endpoints:
        print("❌ No serverless endpoints found!")
        return

    print(f"✅ Found {len(endpoints)} endpoint(s):\n")

    for endpoint in endpoints:
        print(f"Endpoint: {endpoint['name']}")
        print(f"  ID: {endpoint['id']}")
        print(f"  Workers: {endpoint['workersMin']}-{endpoint['workersMax']}")
        print(f"  Scaler: {endpoint['scalerType']} (value: {endpoint['scalerValue']})")
        print(f"  Idle Timeout: {endpoint['idleTimeout']}s")
        print(f"  GPU IDs: {endpoint['gpuIds']}")
        print()

        # Get worker details if this is the visiting_sapphire_kangaroo endpoint
        if endpoint['name'] == 'visiting_sapphire_kangaroo':
            print(f"🔍 Querying worker details for '{endpoint['name']}'...")
            print()

            worker_data = get_endpoint_workers(endpoint['id'])
            workers = worker_data.get('workers', [])

            if not workers:
                print("⚠️  No workers found! This is unusual for an 'Initializing' endpoint.")
                print()
            else:
                print(f"📊 Worker Status ({len(workers)} worker(s)):\n")
                for worker in workers:
                    print(f"Worker ID: {worker['id']}")
                    print(f"  Status: {worker['status']}")
                    print(f"  Location: {worker['location']}")
                    print(f"  GPU Type: {worker['gpuTypeId']}")
                    print(f"  Started At: {worker.get('startedAt', 'N/A')}")
                    print(f"  Ready At: {worker.get('readyAt', 'N/A')}")
                    print()

    print("=" * 80)
    print("Analysis Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()
