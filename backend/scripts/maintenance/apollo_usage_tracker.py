#!/usr/bin/env python3
"""
Apollo API Usage Tracker
========================

Tracks Apollo API calls, rate limits, and when to retry.
Stores data in a JSON file for persistence across runs.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "data" / "apollo_usage.json"


def _ensure_data_dir():
    """Ensure data directory exists."""
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_tracker() -> dict:
    """Load tracker data from file."""
    _ensure_data_dir()
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE, 'r') as f:
            return json.load(f)
    return {
        "daily_calls": {},
        "hourly_calls": {},
        "rate_limit_hits": [],
        "last_successful_call": None,
        "credits_used": {
            "export": 0,
            "mobile": 0,
            "email": 0
        }
    }


def _save_tracker(data: dict):
    """Save tracker data to file."""
    _ensure_data_dir()
    with open(TRACKER_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def log_api_call(endpoint: str, success: bool, response_code: int = 200):
    """Log an Apollo API call."""
    data = _load_tracker()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hour = now.strftime("%Y-%m-%d %H:00")

    # Track daily calls
    if today not in data["daily_calls"]:
        data["daily_calls"][today] = {"total": 0, "success": 0, "failed": 0}
    data["daily_calls"][today]["total"] += 1
    if success:
        data["daily_calls"][today]["success"] += 1
        data["last_successful_call"] = now.isoformat()
    else:
        data["daily_calls"][today]["failed"] += 1

    # Track hourly calls
    if hour not in data["hourly_calls"]:
        data["hourly_calls"][hour] = {"total": 0, "success": 0, "failed": 0}
    data["hourly_calls"][hour]["total"] += 1
    if success:
        data["hourly_calls"][hour]["success"] += 1
    else:
        data["hourly_calls"][hour]["failed"] += 1

    _save_tracker(data)


def log_rate_limit_hit(endpoint: str, response_headers: dict = None):
    """Log when we hit a rate limit."""
    data = _load_tracker()
    now = datetime.now()

    # Parse retry-after header if available
    retry_after = None
    reset_time = None
    if response_headers:
        retry_after = response_headers.get("Retry-After") or response_headers.get("retry-after")
        if retry_after:
            try:
                retry_seconds = int(retry_after)
                reset_time = (now + timedelta(seconds=retry_seconds)).isoformat()
            except ValueError:
                pass

    # Default to 1 hour if no header
    if not reset_time:
        reset_time = (now + timedelta(hours=1)).isoformat()

    hit_record = {
        "timestamp": now.isoformat(),
        "endpoint": endpoint,
        "reset_time": reset_time,
        "retry_after_seconds": retry_after
    }

    data["rate_limit_hits"].append(hit_record)

    # Keep only last 50 rate limit records
    data["rate_limit_hits"] = data["rate_limit_hits"][-50:]

    _save_tracker(data)

    return reset_time


def can_call_apollo() -> tuple[bool, str]:
    """
    Check if we can call Apollo API.
    Returns (can_call, reason/wait_time)
    """
    data = _load_tracker()
    now = datetime.now()

    if not data["rate_limit_hits"]:
        return True, "No rate limits recorded"

    # Check last rate limit hit
    last_hit = data["rate_limit_hits"][-1]
    reset_time = datetime.fromisoformat(last_hit["reset_time"])

    if now >= reset_time:
        return True, f"Rate limit reset at {reset_time.strftime('%H:%M:%S')}"

    wait_minutes = int((reset_time - now).total_seconds() / 60)
    return False, f"Rate limited. Wait {wait_minutes} minutes (until {reset_time.strftime('%H:%M:%S')})"


def get_usage_stats() -> dict:
    """Get current usage statistics."""
    data = _load_tracker()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    hour = now.strftime("%Y-%m-%d %H:00")

    stats = {
        "today": data["daily_calls"].get(today, {"total": 0, "success": 0, "failed": 0}),
        "this_hour": data["hourly_calls"].get(hour, {"total": 0, "success": 0, "failed": 0}),
        "last_successful_call": data.get("last_successful_call"),
        "total_rate_limit_hits": len(data["rate_limit_hits"]),
        "can_call": can_call_apollo()
    }

    # Last rate limit info
    if data["rate_limit_hits"]:
        last_hit = data["rate_limit_hits"][-1]
        stats["last_rate_limit"] = {
            "timestamp": last_hit["timestamp"],
            "reset_time": last_hit["reset_time"],
            "endpoint": last_hit["endpoint"]
        }

    return stats


def print_status():
    """Print current Apollo API status."""
    stats = get_usage_stats()
    can_call, reason = stats["can_call"]

    print("\n" + "="*50)
    print("📊 APOLLO API STATUS")
    print("="*50)
    print(f"Today's calls: {stats['today']['total']} ({stats['today']['success']} success, {stats['today']['failed']} failed)")
    print(f"This hour: {stats['this_hour']['total']} calls")
    print(f"Last successful: {stats['last_successful_call'] or 'Never'}")
    print(f"Total rate limit hits: {stats['total_rate_limit_hits']}")

    if "last_rate_limit" in stats:
        print(f"\nLast rate limit:")
        print(f"  Hit at: {stats['last_rate_limit']['timestamp']}")
        print(f"  Resets: {stats['last_rate_limit']['reset_time']}")

    print(f"\n{'✅' if can_call else '⏳'} {reason}")
    print("="*50)


def reset_tracker():
    """Reset the tracker (for testing)."""
    _ensure_data_dir()
    if TRACKER_FILE.exists():
        TRACKER_FILE.unlink()
    print("✅ Tracker reset")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print_status()
        elif sys.argv[1] == "reset":
            reset_tracker()
        elif sys.argv[1] == "can-call":
            can_call, reason = can_call_apollo()
            print(f"{'YES' if can_call else 'NO'}: {reason}")
    else:
        print_status()
