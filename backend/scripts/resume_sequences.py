#!/usr/bin/env python3
"""
Resume Close CRM sequences after email limits are configured.

Usage:
    python scripts/resume_sequences.py
    python scripts/resume_sequences.py --dry-run  # Check status only

IMPORTANT: Only run after admin has configured Email Sending Limits:
    - Daily Limit: 50
    - Hourly Limit: 10
"""

import os
import sys
import httpx
import base64
import argparse


SEQUENCES = [
    ("seq_469XPP98mPXSR2wh5cX9y6", "ICP-Energy-Multitrade"),
    ("seq_0FHFD0OQtDAOS8x40MIANW", "Solar-Pivot-2026"),
]


def get_headers():
    api_key = os.getenv("CLOSE_API_KEY")
    if not api_key:
        print("ERROR: CLOSE_API_KEY not set")
        sys.exit(1)
    auth_b64 = base64.b64encode(f"{api_key}:".encode()).decode()
    return {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/json"}


def check_status():
    """Check current sequence status."""
    headers = get_headers()
    print("=== Current Sequence Status ===\n")

    for seq_id, name in SEQUENCES:
        response = httpx.get(
            f"https://api.close.com/api/v1/sequence/{seq_id}/",
            headers=headers,
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown").upper()
            counts = data.get("subscription_counts_by_status", {})
            active = counts.get("active", 0)
            print(f"{name}")
            print(f"  Status: {status}")
            print(f"  Active Subscriptions: {active}")
            print(f"  Schedule: {data.get('schedule', {}).get('ranges', [{}])[0]}")
            print(f"  Timezone: {data.get('timezone')}")
            print()
        else:
            print(f"{name}: ERROR {response.status_code}")


def resume_sequences():
    """Resume both sequences."""
    headers = get_headers()

    print("⚠️  CONFIRM: Has the admin configured Email Sending Limits?")
    print("   - Daily Limit: 50")
    print("   - Hourly Limit: 10")
    print()
    confirm = input("Type 'YES' to resume sequences: ")

    if confirm != "YES":
        print("Aborted.")
        return

    print("\n=== Resuming Sequences ===\n")

    for seq_id, name in SEQUENCES:
        print(f"Resuming {name}...")
        response = httpx.put(
            f"https://api.close.com/api/v1/sequence/{seq_id}/",
            headers=headers,
            json={"status": "active"},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ SUCCESS - Status: {data.get('status')}")
        else:
            print(f"  ❌ FAILED: {response.status_code} - {response.text[:200]}")

    print("\n=== Verification ===")
    check_status()


def main():
    parser = argparse.ArgumentParser(description="Resume Close CRM sequences")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check status only, don't resume"
    )
    args = parser.parse_args()

    if args.dry_run:
        check_status()
    else:
        resume_sequences()


if __name__ == "__main__":
    main()
