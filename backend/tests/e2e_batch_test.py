#!/usr/bin/env python3
"""
Manual E2E Test for Batch Processing System

Tests 3 leads through the full pipeline:
1. Fetch sample companies from Supabase
2. Start batch via API
3. Poll status until completion
4. Verify results

Usage:
    cd backend
    source ../venv/bin/activate
    python tests/e2e_batch_test.py

Prerequisites:
    - Docker containers running (docker-compose up -d)
    - Celery worker running (python celery_worker.py)
    - API server running (python start_server.py)
"""
import os
import sys
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def check_prerequisites():
    """Verify all services are running."""
    print("\n🔍 Checking prerequisites...")

    # Check API server
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print("  ✅ API server is running")
        else:
            print(f"  ❌ API server returned {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  ❌ API server not reachable (run: python start_server.py)")
        return False

    # Check Supabase credentials
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  ❌ Supabase credentials not set in .env")
        return False
    print("  ✅ Supabase credentials configured")

    return True


def get_sample_companies(count=3):
    """Fetch sample company IDs from Supabase."""
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get companies with domains (needed for enrichment)
    result = supabase.table("dim_companies").select(
        "company_id, company_name, domain"
    ).not_.is_("domain", "null").limit(count).execute()

    if not result.data:
        # Try without domain filter
        result = supabase.table("dim_companies").select(
            "company_id, company_name, domain"
        ).limit(count).execute()

    print(f"\n📋 Sample Companies ({len(result.data)}):")
    for row in result.data:
        domain = row.get('domain') or 'no domain'
        name = row.get('company_name') or 'Unknown'
        print(f"  - {name} ({domain})")

    return [row["company_id"] for row in result.data]


def start_batch(company_ids):
    """Start a batch job via API."""
    response = requests.post(
        f"{API_BASE}/batch/start",
        json={
            "name": "E2E Test Batch",
            "company_ids": company_ids,
            "priority": "medium",
            "options": {
                "skip_enrichment": True,  # Skip for faster testing
                "skip_marketing": True,
                "skip_bdr": True,
            }
        }
    )

    if response.status_code == 429:
        print(f"\n⚠️ Rate limited: {response.json().get('detail', 'Unknown')}")
        return None

    response.raise_for_status()
    data = response.json()
    print(f"\n🚀 Batch started: {data['batch_id']}")
    print(f"   Status: {data['status']}")
    print(f"   Total leads: {data['total_leads']}")
    return data["batch_id"]


def poll_status(batch_id, timeout=120):
    """Poll batch status until completion."""
    print(f"\n⏳ Polling status (timeout: {timeout}s)...")
    start = time.time()
    last_progress = -1

    while time.time() - start < timeout:
        try:
            response = requests.get(f"{API_BASE}/batch/{batch_id}")
            response.raise_for_status()
            status = response.json()

            progress = status["percent_complete"]
            state = status["status"]
            processed = status["processed_leads"]
            total = status["total_leads"]

            # Only print if progress changed
            if progress != last_progress:
                print(f"  [{state}] {progress:.1f}% - {processed}/{total} leads")
                last_progress = progress

            if state in ("completed", "completed_with_errors", "failed", "cancelled"):
                return status

        except requests.exceptions.RequestException as e:
            print(f"  ⚠️ Request error: {e}")

        time.sleep(3)

    raise TimeoutError(f"Batch did not complete within {timeout}s")


def get_batch_leads(batch_id):
    """Get detailed lead status for the batch."""
    response = requests.get(f"{API_BASE}/batch/{batch_id}/leads")
    response.raise_for_status()
    return response.json()


def verify_results(status, batch_id):
    """Verify batch results."""
    print(f"\n📊 Final Results:")
    print(f"  Status: {status['status']}")
    print(f"  Total: {status['total_leads']}")
    print(f"  Successful: {status['successful_leads']}")
    print(f"  Failed: {status['failed_leads']}")
    print(f"  Skipped: {status['skipped_leads']}")

    if status.get("error_message"):
        print(f"  ⚠️ Error: {status['error_message']}")

    # Get detailed lead status
    try:
        leads = get_batch_leads(batch_id)
        if leads:
            print(f"\n📝 Lead Details:")
            for lead in leads:
                lead_status = lead.get("status", "unknown")
                error = lead.get("error_message", "")
                latency = lead.get("latency_ms", 0)

                emoji = "✅" if lead_status == "completed" else "❌" if lead_status == "failed" else "⏭️"
                print(f"  {emoji} {lead['company_id'][:8]}... - {lead_status}", end="")
                if latency:
                    print(f" ({latency}ms)", end="")
                if error:
                    print(f" - {error}", end="")
                print()
    except Exception as e:
        print(f"  ⚠️ Could not fetch lead details: {e}")

    # Success criteria
    success = (
        status["processed_leads"] == status["total_leads"] and
        status["status"] in ("completed", "completed_with_errors")
    )

    if success:
        print("\n✅ E2E TEST PASSED")
    else:
        print("\n❌ E2E TEST FAILED")

    return success


def main():
    print("=" * 50)
    print("BATCH PROCESSING E2E TEST")
    print("=" * 50)

    # 0. Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix and retry.")
        sys.exit(1)

    # 1. Get sample companies
    try:
        company_ids = get_sample_companies(3)
    except Exception as e:
        print(f"\n❌ Failed to fetch companies: {e}")
        sys.exit(1)

    if len(company_ids) < 3:
        print(f"\n⚠️ Only found {len(company_ids)} companies (need 3)")
        if len(company_ids) == 0:
            print("Run: python sync_gold_standard_to_supabase.py")
            sys.exit(1)

    # 2. Start batch
    try:
        batch_id = start_batch(company_ids)
        if not batch_id:
            sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Failed to start batch: {e}")
        print(f"   Response: {e.response.text if e.response else 'N/A'}")
        sys.exit(1)

    # 3. Poll status
    try:
        final_status = poll_status(batch_id, timeout=120)
    except TimeoutError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # 4. Verify results
    success = verify_results(final_status, batch_id)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
