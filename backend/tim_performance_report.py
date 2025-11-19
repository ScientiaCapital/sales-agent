"""
Tim Kipper Performance Report - Close CRM Activity Analysis

Tracks: Calls, outcomes, emails, meetings, opportunities
Period: July 2025 to present (Q3-Q4 2025)
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

load_dotenv()

# Constants
API_KEY = os.getenv("CLOSE_API_KEY")
BASE_URL = "https://api.close.com/api/v1"
AUTH = (API_KEY, "")
TIM_USER_ID = "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1"
START_DATE = "2025-07-01"


def get_outcomes():
    """Get outcome ID to name mapping."""
    resp = requests.get(f"{BASE_URL}/outcome/", auth=AUTH)
    if resp.ok:
        return {o["id"]: o.get("name", "Unknown") for o in resp.json().get("data", [])}
    return {}


def get_tim_calls(start_date: str):
    """Get all calls by Tim since start_date."""
    all_calls = []
    has_more = True
    skip = 0

    while has_more and skip < 20000:
        resp = requests.get(
            f"{BASE_URL}/activity/call/",
            auth=AUTH,
            params={"_skip": skip, "_limit": 100}
        )
        if not resp.ok:
            break

        data = resp.json()
        batch = data.get("data", [])
        has_more = data.get("has_more", False)

        if not batch:
            break

        # Filter for Tim's calls
        for call in batch:
            if call.get("user_id") == TIM_USER_ID:
                # Filter by date (client-side)
                date = call.get("date_created", "")[:10]
                if date >= start_date:
                    all_calls.append(call)

        skip += 100

    return all_calls


def get_tim_emails(start_date: str):
    """Get all emails by Tim since start_date."""
    all_emails = []
    has_more = True
    skip = 0

    while has_more and skip < 10000:
        resp = requests.get(
            f"{BASE_URL}/activity/email/",
            auth=AUTH,
            params={"_skip": skip, "_limit": 100}
        )
        if not resp.ok:
            break

        data = resp.json()
        batch = data.get("data", [])
        has_more = data.get("has_more", False)

        if not batch:
            break

        # Filter for Tim's emails
        for email in batch:
            if email.get("user_id") == TIM_USER_ID:
                date = email.get("date_created", "")[:10]
                if date >= start_date:
                    all_emails.append(email)

        skip += 100

    return all_emails


def get_tim_opportunities(start_date: str):
    """Get opportunities created/updated by Tim since start_date."""
    opps = []
    skip = 0

    while True:
        resp = requests.get(
            f"{BASE_URL}/opportunity/",
            auth=AUTH,
            params={
                "user_id": TIM_USER_ID,
                "date_created__gt": start_date,
                "_skip": skip,
                "_limit": 200
            }
        )
        if not resp.ok:
            break

        batch = resp.json().get("data", [])
        if not batch:
            break

        opps.extend(batch)
        skip += 200

        if len(batch) < 200:
            break

    return opps


def get_tim_leads_created(start_date: str):
    """Get leads created by Tim since start_date."""
    leads = []
    skip = 0

    while True:
        resp = requests.get(
            f"{BASE_URL}/lead/",
            auth=AUTH,
            params={
                "query": f'created_by:"{TIM_USER_ID}" date_created >= "{start_date}"',
                "_skip": skip,
                "_limit": 200
            }
        )
        if not resp.ok:
            break

        batch = resp.json().get("data", [])
        if not batch:
            break

        leads.extend(batch)
        skip += 200

        if len(batch) < 200:
            break

    return leads


def analyze_calls_by_month(calls):
    """Break down calls by month."""
    by_month = defaultdict(int)
    for call in calls:
        date = call.get("date_created", "")[:7]  # YYYY-MM
        by_month[date] += 1
    return dict(sorted(by_month.items()))


def analyze_calls_by_outcome(calls, outcome_map):
    """Break down calls by outcome."""
    by_outcome = defaultdict(int)
    for call in calls:
        outcome_id = call.get("outcome_id")
        if outcome_id:
            outcome_name = outcome_map.get(outcome_id, "Unknown")
        else:
            outcome_name = f"[{call.get('disposition', 'no-disposition')}]"
        by_outcome[outcome_name] += 1
    return dict(sorted(by_outcome.items(), key=lambda x: -x[1]))


def calculate_call_duration(calls):
    """Calculate total and average call duration."""
    total_seconds = sum(call.get("duration", 0) for call in calls)
    answered_calls = [c for c in calls if c.get("duration", 0) > 0]
    avg_seconds = total_seconds / len(answered_calls) if answered_calls else 0
    return total_seconds, avg_seconds, len(answered_calls)


def print_report():
    """Generate and print the performance report."""
    print("=" * 70)
    print("📊 TIM KIPPER - PERFORMANCE REPORT")
    print(f"   Period: {START_DATE} to {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 70)

    # Get outcome mapping
    print("\n🔄 Loading data from Close CRM...", end="", flush=True)
    outcome_map = get_outcomes()

    # Get all activity
    calls = get_tim_calls(START_DATE)
    emails = get_tim_emails(START_DATE)
    opps = get_tim_opportunities(START_DATE)

    print(" Done!")

    # ========== SUMMARY ==========
    print("\n" + "=" * 70)
    print("📈 ACTIVITY SUMMARY")
    print("=" * 70)

    total_duration, avg_duration, answered = calculate_call_duration(calls)

    print(f"\n  Total Calls:           {len(calls)}")
    print(f"  Answered Calls:        {answered}")
    print(f"  Total Talk Time:       {total_duration // 3600}h {(total_duration % 3600) // 60}m")
    print(f"  Avg Call Duration:     {int(avg_duration // 60)}m {int(avg_duration % 60)}s")
    print(f"\n  Total Emails Sent:     {len(emails)}")
    print(f"  Opportunities Created: {len(opps)}")

    # ========== CALLS BY MONTH ==========
    print("\n" + "-" * 70)
    print("📅 CALLS BY MONTH")
    print("-" * 70)

    by_month = analyze_calls_by_month(calls)
    for month, count in by_month.items():
        bar = "█" * min(count // 5, 40)
        print(f"  {month}:  {count:>4}  {bar}")

    # ========== CALL OUTCOMES ==========
    print("\n" + "-" * 70)
    print("📞 CALL OUTCOMES (Your Results)")
    print("-" * 70)

    by_outcome = analyze_calls_by_outcome(calls, outcome_map)
    for outcome, count in by_outcome.items():
        pct = count / len(calls) * 100 if calls else 0
        bar = "█" * min(count // 2, 30)
        print(f"  {outcome:<25} {count:>4} ({pct:>5.1f}%)  {bar}")

    # ========== KEY METRICS ==========
    print("\n" + "-" * 70)
    print("🎯 KEY PERFORMANCE METRICS")
    print("-" * 70)

    # Count meetings booked
    meetings_booked = sum(1 for c in calls if outcome_map.get(c.get("outcome_id", ""), "").lower() in ["booked meeting", "demo completed"])

    # Count qualified
    qualified = sum(1 for c in calls if outcome_map.get(c.get("outcome_id", ""), "").lower() == "qualified")

    # Conversion rates
    connect_rate = answered / len(calls) * 100 if calls else 0
    meeting_rate = meetings_booked / answered * 100 if answered else 0

    print(f"\n  Connect Rate:          {connect_rate:.1f}% ({answered}/{len(calls)} calls answered)")
    print(f"  Meeting Book Rate:     {meeting_rate:.1f}% ({meetings_booked}/{answered} resulted in meeting)")
    print(f"  Qualified:             {qualified}")
    print(f"  Meetings Booked:       {meetings_booked}")

    # ========== OPPORTUNITIES ==========
    if opps:
        print("\n" + "-" * 70)
        print("💰 OPPORTUNITIES")
        print("-" * 70)

        won = [o for o in opps if o.get("status_type") == "won"]
        lost = [o for o in opps if o.get("status_type") == "lost"]
        active = [o for o in opps if o.get("status_type") == "active"]

        won_value = sum((o.get("value") or 0) / 100 for o in won)
        active_value = sum((o.get("value") or 0) / 100 for o in active)

        print(f"\n  Active:    {len(active):>3}  (${active_value:,.0f} pipeline)")
        print(f"  Won:       {len(won):>3}  (${won_value:,.0f} revenue)")
        print(f"  Lost:      {len(lost):>3}")

        if won:
            avg_deal = won_value / len(won)
            print(f"\n  Avg Deal Size:  ${avg_deal:,.0f}")
            print(f"  Win Rate:       {len(won) / (len(won) + len(lost)) * 100:.1f}%")

    # ========== EFFORT vs RESULTS ==========
    print("\n" + "=" * 70)
    print("⚡ EFFORT vs RESULTS (Q3-Q4 2025)")
    print("=" * 70)

    total_activities = len(calls) + len(emails)

    print(f"\n  EFFORT:")
    print(f"    Total Activities:     {total_activities}")
    print(f"    Calls Made:           {len(calls)}")
    print(f"    Emails Sent:          {len(emails)}")
    print(f"    Hours on Calls:       {total_duration / 3600:.1f}h")

    print(f"\n  RESULTS:")
    print(f"    Meetings Booked:      {meetings_booked}")
    print(f"    Opportunities:        {len(opps)}")
    if opps:
        won_opps = [o for o in opps if o.get("status_type") == "won"]
        won_value = sum((o.get("value") or 0) / 100 for o in won_opps)
        print(f"    Deals Won:            {len(won_opps)}")
        print(f"    Revenue Generated:    ${won_value:,.0f}")

    print(f"\n  EFFICIENCY:")
    if meetings_booked > 0:
        calls_per_meeting = len(calls) / meetings_booked
        print(f"    Calls per Meeting:    {calls_per_meeting:.1f}")
    if opps:
        won_opps = [o for o in opps if o.get("status_type") == "won"]
        if won_opps:
            calls_per_deal = len(calls) / len(won_opps)
            print(f"    Calls per Deal:       {calls_per_deal:.1f}")

    print("\n" + "=" * 70)
    print("Report generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)


if __name__ == "__main__":
    print_report()
