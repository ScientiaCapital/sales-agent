#!/usr/bin/env python3
"""
Sync Lost Deals from Close CRM to Supabase

Syncs to fact_lost_opportunities table to track:
- All lost opportunities with their context
- Last contact date from Close activities
- Revival candidate flag (6+ months since last contact)
- Notes and loss reasons for AI analysis

Usage:
    python sync_lost_deals_to_supabase.py              # Full sync
    python sync_lost_deals_to_supabase.py --dry-run    # Preview without writing
    python sync_lost_deals_to_supabase.py --limit 50   # Sync only 50 deals
"""

import os
import re
import json
import argparse
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import requests

load_dotenv()

CLOSE_API_KEY = os.getenv("CLOSE_API_KEY")
CLOSE_API_BASE = "https://api.close.com/api/v1"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# 6 months threshold for revival candidates
REVIVAL_THRESHOLD_DAYS = 180

# Rate limiting - Close API allows ~100 requests per minute
RATE_LIMIT_DELAY = 0.7  # seconds between activity API calls
CHECKPOINT_FILE = "data/lost_deals_checkpoint.json"

# Common competitor patterns to extract from notes
COMPETITOR_PATTERNS = [
    r"went with (\w+[\w\s]*)",
    r"chose (\w+[\w\s]*)",
    r"selected (\w+[\w\s]*)",
    r"competitor[:\s]+(\w+[\w\s]*)",
    r"lost to (\w+[\w\s]*)",
]


def get_supabase():
    """Get Supabase client."""
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def extract_competitor(note: str) -> Optional[str]:
    """Extract competitor name from opportunity notes."""
    if not note:
        return None

    note_lower = note.lower()
    for pattern in COMPETITOR_PATTERNS:
        match = re.search(pattern, note_lower, re.IGNORECASE)
        if match:
            competitor = match.group(1).strip()
            # Clean up - remove trailing punctuation and limit length
            competitor = re.sub(r'[.,;:!?]+$', '', competitor)
            if len(competitor) > 3 and len(competitor) < 100:
                return competitor.title()
    return None


def fetch_all_lost_opportunities(limit: Optional[int] = None) -> List[Dict]:
    """Fetch all lost opportunities from Close CRM."""
    print("\n" + "=" * 60)
    print("FETCHING LOST OPPORTUNITIES FROM CLOSE CRM")
    print("=" * 60)

    all_opps = []
    skip = 0
    batch_size = 100

    while True:
        resp = requests.get(
            f"{CLOSE_API_BASE}/opportunity/",
            params={
                "status_type": "lost",
                "_skip": skip,
                "_limit": batch_size,
                "_fields": "id,lead_id,lead_name,note,date_lost,date_created,value,value_period,status_label,user_name,created_by_name,custom"
            },
            auth=(CLOSE_API_KEY, ""),
            timeout=30
        )

        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
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

    print(f"\nTotal fetched: {len(all_opps)}")
    return all_opps


def load_checkpoint() -> Dict[str, Any]:
    """Load checkpoint from JSON file."""
    try:
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"  Warning: Could not load checkpoint: {e}")
    return {"processed_leads": {}, "last_updated": None}


def save_checkpoint(data: Dict[str, Any]):
    """Save checkpoint to JSON file."""
    try:
        os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
        data["last_updated"] = datetime.now().isoformat()
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"  Warning: Could not save checkpoint: {e}")


def fetch_activities_summary(lead_id: str, checkpoint: Dict = None) -> Dict[str, Any]:
    """Get activity summary for a lead (last activity date, counts)."""
    # Check if we already have this in checkpoint
    if checkpoint and lead_id in checkpoint.get("processed_leads", {}):
        return checkpoint["processed_leads"][lead_id]

    # Rate limit - sleep before making request
    time.sleep(RATE_LIMIT_DELAY)

    resp = requests.get(
        f"{CLOSE_API_BASE}/activity/",
        params={
            "lead_id": lead_id,
            "_limit": 100,
            "_order_by": "-date_created"  # Most recent first
        },
        auth=(CLOSE_API_KEY, ""),
        timeout=30
    )

    if resp.status_code == 429:
        # Rate limited - wait and retry
        reset_time = int(resp.headers.get("X-RateLimit-Reset", 60))
        print(f"  ⚠️ Rate limited. Waiting {reset_time}s...")
        time.sleep(reset_time)
        return fetch_activities_summary(lead_id, checkpoint)

    if resp.status_code != 200:
        print(f"  ⚠️ Activity fetch failed for {lead_id}: {resp.status_code}")
        return {}

    data = resp.json()
    activities = data.get("data", [])
    total = data.get("total_results", 0)

    # Summarize
    summary = {
        "total_activities": total,
        "emails_sent": 0,
        "emails_received": 0,
        "calls_made": 0,
        "meetings": 0,
        "last_activity_date": None,
        "last_outbound_date": None,  # Last time WE reached out
    }

    for act in activities:
        act_type = act.get("_type", "")
        date_created = act.get("date_created")

        # Track last activity
        if date_created and not summary["last_activity_date"]:
            summary["last_activity_date"] = date_created

        if act_type == "Email":
            direction = act.get("direction", "")
            if direction == "outgoing":
                summary["emails_sent"] += 1
                if not summary["last_outbound_date"]:
                    summary["last_outbound_date"] = date_created
            else:
                summary["emails_received"] += 1

        elif act_type == "Call":
            summary["calls_made"] += 1
            if not summary["last_outbound_date"]:
                summary["last_outbound_date"] = date_created

        elif act_type == "Meeting":
            summary["meetings"] += 1

    return summary


def verify_table_exists(supabase) -> bool:
    """Verify fact_lost_opportunities table exists."""
    try:
        result = supabase.table("fact_lost_opportunities").select("id").limit(1).execute()
        print("  ✅ Table fact_lost_opportunities exists")
        return True
    except Exception as e:
        print(f"  ❌ Table fact_lost_opportunities not found: {e}")
        print("\n  Please create the table in Supabase SQL Editor first.")
        return False


def analyze_lost_deal(opp: Dict, activities: Dict) -> Dict:
    """Analyze a lost deal and calculate metrics for user's schema."""
    now = datetime.now(timezone.utc)

    # Calculate days since lost (from date_lost)
    days_since_lost = None
    date_lost = opp.get("date_lost")
    if date_lost:
        try:
            lost_dt = datetime.fromisoformat(date_lost.replace("Z", "+00:00"))
            days_since_lost = (now - lost_dt).days
        except:
            pass

    # Get last contact date (last outbound from us)
    last_contact_date = activities.get("last_outbound_date")

    # Determine if revival candidate (6+ months since we last contacted them)
    is_revival = False
    revival_priority = None
    if last_contact_date:
        try:
            last_dt = datetime.fromisoformat(last_contact_date.replace("Z", "+00:00"))
            days_since_contact = (now - last_dt).days
            if days_since_contact >= REVIVAL_THRESHOLD_DAYS:
                is_revival = True
        except:
            pass
    elif days_since_lost and days_since_lost >= REVIVAL_THRESHOLD_DAYS:
        # No recorded contact, use date_lost as proxy
        is_revival = True

    # Assign priority based on deal value
    if is_revival:
        deal_value = (opp.get("value") or 0) / 100
        if deal_value >= 30000:
            revival_priority = "high"
        elif deal_value >= 15000:
            revival_priority = "medium"
        else:
            revival_priority = "low"

    # Calculate revival score (0-100) - combines engagement + deal value signals
    revival_score = 0
    if activities.get("emails_received", 0) > 0:
        revival_score += 25  # They responded at some point
    if activities.get("calls_made", 0) > 0:
        revival_score += 15
    if activities.get("meetings", 0) > 0:
        revival_score += 30  # Had actual meeting = higher quality
    response_rate = activities.get("emails_received", 0) / max(activities.get("emails_sent", 1), 1)
    if response_rate > 0.3:
        revival_score += 15
    # Bonus for higher deal values
    deal_value = (opp.get("value") or 0) / 100
    if deal_value >= 50000:
        revival_score += 15
    elif deal_value >= 25000:
        revival_score += 10
    elif deal_value >= 10000:
        revival_score += 5
    revival_score = min(revival_score, 100)

    # Extract competitor from notes
    competitor = extract_competitor(opp.get("note"))

    # Build close_reason summary from note
    note = opp.get("note") or ""
    close_reason = None
    note_lower = note.lower()
    if "competitor" in note_lower or "went with" in note_lower:
        close_reason = "Lost to competitor"
    elif "price" in note_lower or "cost" in note_lower or "budget" in note_lower:
        close_reason = "Pricing/Budget"
    elif "timing" in note_lower or "not now" in note_lower or "later" in note_lower:
        close_reason = "Bad timing"
    elif "no response" in note_lower or "ghosted" in note_lower:
        close_reason = "No response"
    elif note:
        # Use first 100 chars of note as reason
        close_reason = note[:100].strip()

    return {
        "days_since_lost": days_since_lost,
        "is_revival_candidate": is_revival,
        "revival_priority": revival_priority,
        "revival_score": revival_score,
        "last_contact_date": last_contact_date,
        "competitor_lost_to": competitor,
        "close_reason": close_reason,
    }


def sync_lost_deals(limit: Optional[int] = None, dry_run: bool = False):
    """Main sync function - matches user's fact_lost_opportunities schema."""
    supabase = get_supabase()

    # Verify table exists (user should have created it)
    if not verify_table_exists(supabase):
        if not dry_run:
            print("\n⚠️  Please create the table first, then re-run")
            return

    # Fetch lost opportunities
    opps = fetch_all_lost_opportunities(limit)

    if not opps:
        print("No lost opportunities found")
        return

    # Get existing Close lead IDs in dim_companies
    print("\n" + "=" * 60)
    print("MATCHING TO EXISTING COMPANIES")
    print("=" * 60)

    companies = supabase.table("dim_companies").select(
        "company_id, close_lead_id, company_name"
    ).not_.is_("close_lead_id", "null").execute()

    lead_to_company = {}
    for c in (companies.data or []):
        if c.get("close_lead_id"):
            lead_to_company[c["close_lead_id"]] = c["company_id"]

    print(f"  Found {len(lead_to_company)} companies with Close lead IDs")

    # Process each opportunity
    print("\n" + "=" * 60)
    print("SYNCING LOST OPPORTUNITIES")
    print("=" * 60)

    # Load checkpoint for resumable sync
    checkpoint = load_checkpoint()
    cached_count = len(checkpoint.get("processed_leads", {}))
    if cached_count > 0:
        print(f"  📁 Loaded checkpoint with {cached_count} cached activity summaries")

    synced = 0
    revival_candidates = 0
    high_priority = 0
    total_value = 0

    records = []
    start_time = time.time()

    for i, opp in enumerate(opps):
        lead_id = opp.get("lead_id")
        lead_name = opp.get("lead_name", "Unknown")

        # Progress logging every 10 items (more frequent)
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(opps) - i) / rate if rate > 0 else 0
            cached = lead_id in checkpoint.get("processed_leads", {})
            print(f"  [{i+1}/{len(opps)}] {lead_name[:30]:<30} {'(cached)' if cached else '(fetching)'} | ETA: {eta/60:.1f}min")

        # Get activity summary (only if not dry run, to save API calls)
        if not dry_run:
            activities = fetch_activities_summary(lead_id, checkpoint)
            # Save to checkpoint
            if lead_id not in checkpoint.get("processed_leads", {}):
                checkpoint.setdefault("processed_leads", {})[lead_id] = activities
                # Save checkpoint every 25 records
                if i % 25 == 0:
                    save_checkpoint(checkpoint)
                    print(f"  💾 Checkpoint saved ({len(checkpoint['processed_leads'])} leads)")
        else:
            activities = {"total_activities": 0}

        # Analyze
        analysis = analyze_lost_deal(opp, activities)

        # Build record matching user's schema:
        # close_opportunity_id, company_id, close_lead_id, lead_name, deal_value,
        # close_reason, date_lost, days_since_lost, is_revival_candidate,
        # revival_priority, revival_score, last_contact_date, original_stage,
        # competitor_lost_to, notes
        deal_value = (opp.get("value") or 0) / 100
        total_value += deal_value

        record = {
            "close_opportunity_id": opp.get("id"),
            "company_id": lead_to_company.get(lead_id),  # May be None if not in dim_companies
            "close_lead_id": lead_id,
            "lead_name": lead_name,
            "deal_value": deal_value,
            "close_reason": analysis["close_reason"],
            "date_lost": opp.get("date_lost"),
            "days_since_lost": analysis["days_since_lost"],
            "is_revival_candidate": analysis["is_revival_candidate"],
            "revival_priority": analysis["revival_priority"],
            "revival_score": analysis["revival_score"],
            "last_contact_date": analysis["last_contact_date"],
            "original_stage": opp.get("status_label"),  # e.g., "Lost - Competitor"
            "competitor_lost_to": analysis["competitor_lost_to"],
            "notes": opp.get("note"),  # Full note text
        }

        records.append(record)

        if analysis["is_revival_candidate"]:
            revival_candidates += 1
            if analysis["revival_priority"] == "high":
                high_priority += 1

    # Summary before sync
    print("\n" + "=" * 60)
    print("SYNC SUMMARY")
    print("=" * 60)
    print(f"  Total lost opportunities: {len(records)}")
    print(f"  Total value lost: ${total_value:,.0f}")
    print(f"  Revival candidates (6+ months): {revival_candidates}")
    print(f"  High priority revivals (>$30K): {high_priority}")
    print(f"  Linked to existing companies: {sum(1 for r in records if r.get('company_id'))}")

    # Count by close reason
    reasons = {}
    for r in records:
        reason = r.get("close_reason") or "Unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    print("\n  Close Reasons:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1])[:5]:
        print(f"    - {reason}: {count}")

    # Save final checkpoint
    if not dry_run:
        save_checkpoint(checkpoint)
        print(f"  💾 Final checkpoint saved ({len(checkpoint.get('processed_leads', {}))} leads)")

    if dry_run:
        print("\n  [DRY RUN] No data written to Supabase")
        print("\n  Sample records:")
        for r in records[:5]:
            print(f"    - {r['lead_name'][:35]} (${r['deal_value']:,.0f}) | Revival: {r['is_revival_candidate']} | {r['close_reason'] or 'N/A'}")
        return

    # Upsert to Supabase
    print("\n  Writing to Supabase...")
    try:
        # Upsert in batches
        batch_size = 50
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table("fact_lost_opportunities").upsert(
                batch,
                on_conflict="close_opportunity_id"
            ).execute()
            synced += len(batch)
            print(f"    Synced {synced}/{len(records)}...")

        print(f"\n  ✅ Successfully synced {synced} lost opportunities!")

    except Exception as e:
        print(f"\n  ❌ Error syncing to Supabase: {e}")
        print("  Make sure the fact_lost_opportunities table exists")
        raise

    # Show revival candidates
    print("\n" + "=" * 60)
    print("TOP REVIVAL CANDIDATES (HIGH PRIORITY)")
    print("=" * 60)

    high_revivals = [r for r in records if r["revival_priority"] == "high"]
    high_revivals.sort(key=lambda x: x["deal_value"], reverse=True)

    for r in high_revivals[:15]:
        days = r.get("days_since_lost") or "?"
        competitor = r.get("competitor_lost_to") or "-"
        print(f"  ${r['deal_value']:>8,.0f} | {r['lead_name'][:35]:<35} | {days:>4} days | {competitor[:15]}")


def main():
    parser = argparse.ArgumentParser(description="Sync lost deals from Close to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, help="Limit number of deals to sync")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("LOST DEAL SYNC: CLOSE CRM → SUPABASE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    sync_lost_deals(limit=args.limit, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
