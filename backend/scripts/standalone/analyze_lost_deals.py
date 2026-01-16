#!/usr/bin/env python3
"""
Lost Deal Analysis - Extract insights from 535 lost opportunities

Extracts:
1. Opportunity notes and context
2. All associated activities (emails, calls, SMS, notes)
3. Engagement patterns (response rates, call frequency)
4. AI-powered loss reason analysis

Usage:
    python analyze_lost_deals.py                    # Full extraction
    python analyze_lost_deals.py --limit 50         # Test with 50 deals
    python analyze_lost_deals.py --analyze          # Run AI analysis
    python analyze_lost_deals.py --export           # Export to CSV
"""

import os
import json
import csv
import time
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional
from dotenv import load_dotenv
import requests

load_dotenv()

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
OUTPUT_DIR = Path(__file__).parent / "data" / "lost_deal_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
REQUESTS_PER_SECOND = 2
last_request_time = 0


def rate_limit():
    """Simple rate limiter for Close API."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < 1 / REQUESTS_PER_SECOND:
        time.sleep(1 / REQUESTS_PER_SECOND - elapsed)
    last_request_time = time.time()


def fetch_lost_opportunities(limit: Optional[int] = None) -> list:
    """Fetch all lost opportunities from Close CRM."""
    print(f"\n{'='*60}")
    print("FETCHING LOST OPPORTUNITIES FROM CLOSE CRM")
    print(f"{'='*60}")

    all_opps = []
    skip = 0
    batch_size = 100

    while True:
        rate_limit()
        resp = requests.get(
            "https://api.close.com/api/v1/opportunity/",
            params={
                "status_type": "lost",
                "_skip": skip,
                "_limit": batch_size,
                "_fields": "id,lead_id,lead_name,note,date_lost,date_created,value,value_period,confidence,status_label,user_name,created_by_name"
            },
            auth=(CLOSE_API_KEY, "")
        )

        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            break

        data = resp.json()
        opps = data.get("data", [])
        total = data.get("total_results", 0)

        all_opps.extend(opps)
        print(f"  Fetched {len(all_opps)}/{total} opportunities...")

        if len(opps) < batch_size:
            break

        skip += batch_size

        if limit and len(all_opps) >= limit:
            all_opps = all_opps[:limit]
            break

    print(f"\nTotal opportunities fetched: {len(all_opps)}")
    return all_opps


def fetch_activities_for_lead(lead_id: str) -> dict:
    """Fetch all activities for a lead and summarize them."""
    rate_limit()
    resp = requests.get(
        "https://api.close.com/api/v1/activity/",
        params={
            "lead_id": lead_id,
            "_limit": 100  # Get up to 100 activities per lead
        },
        auth=(CLOSE_API_KEY, "")
    )

    if resp.status_code != 200:
        return {"error": resp.text}

    data = resp.json()
    activities = data.get("data", [])
    total = data.get("total_results", 0)

    # Summarize activities
    summary = {
        "total_activities": total,
        "emails_sent": 0,
        "emails_received": 0,
        "calls_made": 0,
        "call_duration_seconds": 0,
        "sms_sent": 0,
        "sms_received": 0,
        "meetings": 0,
        "notes_count": 0,
        "notes_text": [],
        "email_subjects": [],
        "first_activity_date": None,
        "last_activity_date": None,
        "activity_types": Counter()
    }

    for act in activities:
        act_type = act.get("_type", "unknown")
        summary["activity_types"][act_type] += 1

        date_created = act.get("date_created")
        if date_created:
            if not summary["first_activity_date"] or date_created < summary["first_activity_date"]:
                summary["first_activity_date"] = date_created
            if not summary["last_activity_date"] or date_created > summary["last_activity_date"]:
                summary["last_activity_date"] = date_created

        if act_type == "Email":
            direction = act.get("direction", "")
            if direction == "outgoing":
                summary["emails_sent"] += 1
                subject = act.get("subject", "")
                if subject:
                    summary["email_subjects"].append(subject)
            elif direction == "incoming":
                summary["emails_received"] += 1

        elif act_type == "Call":
            summary["calls_made"] += 1
            duration = act.get("duration", 0)
            if duration:
                summary["call_duration_seconds"] += duration

        elif act_type == "SMS":
            direction = act.get("direction", "")
            if direction == "outgoing":
                summary["sms_sent"] += 1
            else:
                summary["sms_received"] += 1

        elif act_type == "Meeting":
            summary["meetings"] += 1

        elif act_type == "Note":
            summary["notes_count"] += 1
            note_text = act.get("note", "")
            if note_text:
                summary["notes_text"].append(note_text[:500])  # Truncate long notes

    # Convert Counter to dict for JSON serialization
    summary["activity_types"] = dict(summary["activity_types"])

    return summary


def analyze_deal(opp: dict, activities: dict) -> dict:
    """Analyze a single lost deal for patterns."""
    analysis = {
        "lead_name": opp.get("lead_name"),
        "lead_id": opp.get("lead_id"),
        "opportunity_id": opp.get("id"),
        "deal_value": opp.get("value", 0) / 100 if opp.get("value") else 0,
        "date_lost": opp.get("date_lost", "")[:10] if opp.get("date_lost") else None,
        "date_created": opp.get("date_created", "")[:10] if opp.get("date_created") else None,
        "opportunity_note": opp.get("note", ""),
        "owner": opp.get("user_name"),
        "created_by": opp.get("created_by_name"),

        # Activity metrics
        "total_activities": activities.get("total_activities", 0),
        "emails_sent": activities.get("emails_sent", 0),
        "emails_received": activities.get("emails_received", 0),
        "calls_made": activities.get("calls_made", 0),
        "call_duration_minutes": activities.get("call_duration_seconds", 0) / 60,
        "sms_sent": activities.get("sms_sent", 0),
        "meetings": activities.get("meetings", 0),
        "notes_count": activities.get("notes_count", 0),

        # Derived metrics
        "response_rate": 0,
        "engagement_score": 0,
        "deal_cycle_days": None,

        # Loss indicators
        "loss_indicators": [],
    }

    # Calculate response rate
    total_outbound = analysis["emails_sent"] + analysis["sms_sent"]
    total_inbound = activities.get("emails_received", 0) + activities.get("sms_received", 0)
    if total_outbound > 0:
        analysis["response_rate"] = total_inbound / total_outbound

    # Calculate engagement score (0-100)
    score = 0
    if activities.get("emails_received", 0) > 0:
        score += 20
    if activities.get("calls_made", 0) > 0:
        score += 15
    if activities.get("call_duration_seconds", 0) > 300:  # 5+ minutes of calls
        score += 20
    if activities.get("meetings", 0) > 0:
        score += 25
    if analysis["response_rate"] > 0.3:
        score += 20
    analysis["engagement_score"] = min(score, 100)

    # Calculate deal cycle
    if analysis["date_created"] and analysis["date_lost"]:
        try:
            created = datetime.fromisoformat(analysis["date_created"])
            lost = datetime.fromisoformat(analysis["date_lost"])
            analysis["deal_cycle_days"] = (lost - created).days
        except:
            pass

    # Identify loss indicators
    indicators = []

    if analysis["emails_received"] == 0 and analysis["emails_sent"] > 3:
        indicators.append("NO_RESPONSE")

    if analysis["meetings"] == 0 and analysis["total_activities"] > 10:
        indicators.append("NO_MEETING_BOOKED")

    if analysis["calls_made"] == 0:
        indicators.append("NO_CALLS_MADE")

    if analysis["deal_cycle_days"] and analysis["deal_cycle_days"] > 90:
        indicators.append("LONG_CYCLE")

    if analysis["response_rate"] < 0.1 and total_outbound > 5:
        indicators.append("LOW_ENGAGEMENT")

    note = analysis.get("opportunity_note", "").lower()
    if "competitor" in note or "went with" in note or "chose" in note:
        indicators.append("COMPETITOR_WIN")
    if "price" in note or "cost" in note or "budget" in note:
        indicators.append("PRICING_ISSUE")
    if "timing" in note or "not now" in note or "later" in note:
        indicators.append("BAD_TIMING")
    if "champion" in note or "atl" in note or "decision maker" in note:
        indicators.append("CHAMPION_ISSUE")

    analysis["loss_indicators"] = indicators

    # Add activity notes
    analysis["notes_text"] = activities.get("notes_text", [])

    return analysis


def extract_all_deals(limit: Optional[int] = None) -> list:
    """Extract and analyze all lost deals."""
    opps = fetch_lost_opportunities(limit)

    print(f"\n{'='*60}")
    print("EXTRACTING ACTIVITIES FOR EACH DEAL")
    print(f"{'='*60}")

    analyzed_deals = []

    for i, opp in enumerate(opps):
        lead_id = opp.get("lead_id")
        lead_name = opp.get("lead_name")

        if i % 10 == 0:
            print(f"  Processing {i+1}/{len(opps)}: {lead_name}...")

        activities = fetch_activities_for_lead(lead_id)
        analysis = analyze_deal(opp, activities)
        analyzed_deals.append(analysis)

    return analyzed_deals


def generate_summary(deals: list) -> dict:
    """Generate summary statistics from analyzed deals."""
    print(f"\n{'='*60}")
    print("GENERATING SUMMARY STATISTICS")
    print(f"{'='*60}")

    summary = {
        "total_deals": len(deals),
        "total_value_lost": sum(d.get("deal_value", 0) for d in deals),
        "avg_deal_value": 0,
        "avg_emails_sent": 0,
        "avg_response_rate": 0,
        "avg_engagement_score": 0,
        "avg_deal_cycle_days": 0,

        # Loss indicator counts
        "loss_indicators": Counter(),

        # Deals by engagement level
        "high_engagement_deals": 0,
        "medium_engagement_deals": 0,
        "low_engagement_deals": 0,

        # Response analysis
        "no_response_deals": 0,
        "some_response_deals": 0,

        # Meeting analysis
        "no_meeting_deals": 0,
        "had_meeting_deals": 0,

        # Owner breakdown
        "by_owner": Counter(),

        # Value segments
        "deals_under_10k": 0,
        "deals_10k_50k": 0,
        "deals_over_50k": 0,
    }

    valid_cycles = []

    for deal in deals:
        # Aggregate loss indicators
        for indicator in deal.get("loss_indicators", []):
            summary["loss_indicators"][indicator] += 1

        # Engagement levels
        score = deal.get("engagement_score", 0)
        if score >= 60:
            summary["high_engagement_deals"] += 1
        elif score >= 30:
            summary["medium_engagement_deals"] += 1
        else:
            summary["low_engagement_deals"] += 1

        # Response analysis
        if deal.get("emails_received", 0) == 0 and deal.get("emails_sent", 0) > 0:
            summary["no_response_deals"] += 1
        elif deal.get("emails_received", 0) > 0:
            summary["some_response_deals"] += 1

        # Meeting analysis
        if deal.get("meetings", 0) == 0:
            summary["no_meeting_deals"] += 1
        else:
            summary["had_meeting_deals"] += 1

        # Owner
        owner = deal.get("owner", "Unknown")
        summary["by_owner"][owner] += 1

        # Value segments
        value = deal.get("deal_value", 0)
        if value < 10000:
            summary["deals_under_10k"] += 1
        elif value < 50000:
            summary["deals_10k_50k"] += 1
        else:
            summary["deals_over_50k"] += 1

        # Collect valid cycle days
        cycle = deal.get("deal_cycle_days")
        if cycle is not None and cycle > 0:
            valid_cycles.append(cycle)

    # Calculate averages
    if len(deals) > 0:
        summary["avg_deal_value"] = summary["total_value_lost"] / len(deals)
        summary["avg_emails_sent"] = sum(d.get("emails_sent", 0) for d in deals) / len(deals)
        summary["avg_response_rate"] = sum(d.get("response_rate", 0) for d in deals) / len(deals)
        summary["avg_engagement_score"] = sum(d.get("engagement_score", 0) for d in deals) / len(deals)

    if valid_cycles:
        summary["avg_deal_cycle_days"] = sum(valid_cycles) / len(valid_cycles)

    # Convert Counters to dicts for JSON
    summary["loss_indicators"] = dict(summary["loss_indicators"])
    summary["by_owner"] = dict(summary["by_owner"])

    return summary


def print_summary(summary: dict, deals: list):
    """Print human-readable summary."""
    print(f"\n{'='*60}")
    print("LOST DEAL ANALYSIS SUMMARY")
    print(f"{'='*60}")

    print(f"\n--- Overview ---")
    print(f"Total Lost Deals: {summary['total_deals']}")
    print(f"Total Value Lost: ${summary['total_value_lost']:,.0f}")
    print(f"Avg Deal Value: ${summary['avg_deal_value']:,.0f}")
    print(f"Avg Deal Cycle: {summary['avg_deal_cycle_days']:.0f} days")

    print(f"\n--- Engagement Analysis ---")
    print(f"High Engagement (60+): {summary['high_engagement_deals']} deals")
    print(f"Medium Engagement (30-60): {summary['medium_engagement_deals']} deals")
    print(f"Low Engagement (<30): {summary['low_engagement_deals']} deals")
    print(f"Avg Engagement Score: {summary['avg_engagement_score']:.1f}/100")

    print(f"\n--- Response Analysis ---")
    print(f"No Response (ghosted): {summary['no_response_deals']} deals")
    print(f"Some Response: {summary['some_response_deals']} deals")
    print(f"Avg Response Rate: {summary['avg_response_rate']*100:.1f}%")

    print(f"\n--- Meeting Analysis ---")
    print(f"No Meeting Booked: {summary['no_meeting_deals']} deals")
    print(f"Had Meeting(s): {summary['had_meeting_deals']} deals")

    print(f"\n--- Loss Indicators (Top 10) ---")
    for indicator, count in sorted(summary["loss_indicators"].items(), key=lambda x: -x[1])[:10]:
        pct = count / summary["total_deals"] * 100
        print(f"  {indicator}: {count} ({pct:.1f}%)")

    print(f"\n--- By Owner ---")
    for owner, count in sorted(summary["by_owner"].items(), key=lambda x: -x[1]):
        print(f"  {owner}: {count} deals")

    print(f"\n--- Value Segments ---")
    print(f"Under $10K: {summary['deals_under_10k']} deals")
    print(f"$10K-$50K: {summary['deals_10k_50k']} deals")
    print(f"Over $50K: {summary['deals_over_50k']} deals")

    # Top 10 highest value lost deals
    print(f"\n--- Top 10 Highest Value Lost Deals ---")
    sorted_deals = sorted(deals, key=lambda x: x.get("deal_value", 0), reverse=True)
    for deal in sorted_deals[:10]:
        indicators = ", ".join(deal.get("loss_indicators", [])) or "No indicators"
        print(f"  ${deal['deal_value']:,.0f} - {deal['lead_name']}")
        print(f"    Indicators: {indicators}")
        if deal.get("opportunity_note"):
            print(f"    Note: {deal['opportunity_note'][:100]}...")

    # Deals that should be revisited (high engagement but lost)
    print(f"\n--- Potential Revival Candidates (High Engagement, Lost) ---")
    revival_candidates = [d for d in deals if d.get("engagement_score", 0) >= 50 and d.get("meetings", 0) > 0]
    revival_candidates = sorted(revival_candidates, key=lambda x: x.get("deal_value", 0), reverse=True)
    for deal in revival_candidates[:10]:
        print(f"  ${deal['deal_value']:,.0f} - {deal['lead_name']} (Engagement: {deal['engagement_score']}, Meetings: {deal['meetings']})")


def export_to_csv(deals: list, filename: str = "lost_deals_analysis.csv"):
    """Export analyzed deals to CSV."""
    output_path = OUTPUT_DIR / filename

    fieldnames = [
        "lead_name", "lead_id", "opportunity_id", "deal_value",
        "date_created", "date_lost", "deal_cycle_days",
        "owner", "created_by",
        "total_activities", "emails_sent", "emails_received",
        "calls_made", "call_duration_minutes", "sms_sent", "meetings",
        "response_rate", "engagement_score",
        "loss_indicators", "opportunity_note"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for deal in deals:
            row = deal.copy()
            row["loss_indicators"] = "|".join(deal.get("loss_indicators", []))
            writer.writerow(row)

    print(f"\nExported to: {output_path}")
    return output_path


def export_to_json(deals: list, summary: dict, filename: str = "lost_deals_full.json"):
    """Export full analysis to JSON."""
    output_path = OUTPUT_DIR / filename

    export_data = {
        "export_date": datetime.now().isoformat(),
        "summary": summary,
        "deals": deals
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"Exported to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Analyze lost deals from Close CRM")
    parser.add_argument("--limit", type=int, help="Limit number of deals to analyze")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    parser.add_argument("--json", action="store_true", help="Export to JSON")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("LOST DEAL ANALYSIS - CLOSE CRM")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Extract and analyze deals
    deals = extract_all_deals(limit=args.limit)

    # Generate summary
    summary = generate_summary(deals)

    # Print results
    print_summary(summary, deals)

    # Export if requested
    if args.export or args.json:
        if args.export:
            export_to_csv(deals)
        if args.json:
            export_to_json(deals, summary)
    else:
        # Always export JSON for later use
        export_to_json(deals, summary)

    print(f"\n{'='*60}")
    print(f"Analysis complete! {len(deals)} deals analyzed.")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
