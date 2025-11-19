"""
KPI Dashboard - Track leads, costs, and conversions.

Tracks:
- Lead pipeline metrics (count, sources, stages)
- Enrichment costs (Hunter.io, Apollo API calls)
- Conversion funnel (lead → qualified → opportunity → signed)
- ROI calculations
"""

import pandas as pd
import json
import os
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
DATA_DIR = Path("data")
KPI_FILE = DATA_DIR / "kpi_metrics.json"
COST_LOG = DATA_DIR / "enrichment_costs.json"

# API Cost Constants (per request)
COSTS = {
    "hunter_domain_search": 0.01,  # ~$0.01 per domain
    "hunter_email_finder": 0.005,  # ~$0.005 per lookup
    "apollo_people_match": 0.002,  # ~$0.002 per match
    "apollo_enrich": 0.003,        # ~$0.003 per enrichment
    "cerebras_qualification": 0.000006,  # Extremely cheap
}


def load_kpi_data() -> dict:
    """Load existing KPI data or create new."""
    if KPI_FILE.exists():
        with open(KPI_FILE) as f:
            return json.load(f)
    return {
        "total_leads_processed": 0,
        "total_contacts_found": 0,
        "total_atl_contacts": 0,
        "total_enrichment_cost": 0.0,
        "batches": [],
        "funnel": {
            "mql": 0,              # Marketing Qualified Lead (entered Close CRM)
            "sql": 0,              # Sales Qualified Lead (contacted/engaged)
            "meeting_booked": 0,   # Meeting scheduled
            "opportunity": 0,      # Active opportunity
            "opportunity_won": 0,  # Closed won
            "opportunity_lost": 0  # Closed lost
        },
        "revenue": {
            "total_contract_value": 0.0,
            "avg_deal_size": 0.0
        }
    }


def save_kpi_data(data: dict):
    """Save KPI data to file."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(KPI_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def sync_close_crm_funnel() -> dict:
    """Read Close CRM to get actual funnel counts (READ ONLY).

    Returns dict with counts for each funnel stage based on lead statuses
    and opportunity statuses.
    """
    api_key = os.getenv("CLOSE_API_KEY")
    if not api_key:
        return {"error": "CLOSE_API_KEY not set"}

    base_url = "https://api.close.com/api/v1"
    auth = (api_key, "")

    funnel = {
        "mql": 0,
        "sql": 0,
        "meeting_booked": 0,
        "opportunity": 0,
        "opportunity_won": 0,
        "opportunity_lost": 0,
        "total_leads": 0,
        "total_revenue": 0.0
    }

    try:
        # Get lead statuses first
        status_resp = requests.get(f"{base_url}/status/lead/", auth=auth)
        status_map = {}
        status_id_map = {}  # id -> label
        if status_resp.ok:
            for status in status_resp.json().get("data", []):
                status_map[status["label"].lower()] = status["id"]
                status_id_map[status["id"]] = status["label"]

        # Count leads by status using search queries
        # Close CRM funnel stages mapping:
        funnel_mapping = {
            "mql": ["mql"],                           # Marketing Qualified Lead
            "sql": ["sal", "sql"],                    # Sales Accepted/Qualified Lead
            "opportunity": ["opportunity"],           # Opportunity stage
            "opportunity_won": ["customer"],          # Closed won
            "opportunity_lost": ["churned", "unqualified", "out of business", "do not sell", "junk"]
        }

        # Query each funnel stage
        for stage, status_labels in funnel_mapping.items():
            for label in status_labels:
                if label in status_map:
                    status_id = status_map[label]
                    # Use search query format for accurate counts
                    search_resp = requests.get(
                        f"{base_url}/lead/",
                        auth=auth,
                        params={"query": f'lead_status:"{status_id_map.get(status_id, label)}"', "_limit": 0}
                    )
                    if search_resp.ok:
                        count = search_resp.json().get("total_results", 0)
                        funnel[stage] += count

        # Get total leads
        leads_resp = requests.get(f"{base_url}/lead/", auth=auth, params={"_limit": 0})
        if leads_resp.ok:
            funnel["total_leads"] = leads_resp.json().get("total_results", 0)

        # Get call outcomes to find "Booked Meeting"
        outcomes_resp = requests.get(f"{base_url}/outcome/", auth=auth)
        meeting_outcome_ids = []
        if outcomes_resp.ok:
            outcomes = outcomes_resp.json().get("data", [])
            for outcome in outcomes:
                name = outcome.get("name", "").lower()
                if "meeting" in name or "booked" in name or "demo" in name:
                    meeting_outcome_ids.append(outcome["id"])

        # Count calls with meeting outcomes (limit to recent 2000 for speed)
        if meeting_outcome_ids:
            skip = 0
            max_calls = 2000  # Limit for faster sync
            batch_size = 500  # Larger batch for fewer API calls
            while skip < max_calls:
                calls_resp = requests.get(
                    f"{base_url}/activity/call/",
                    auth=auth,
                    params={"_skip": skip, "_limit": batch_size}
                )
                if calls_resp.ok:
                    calls = calls_resp.json().get("data", [])
                    if not calls:
                        break
                    for call in calls:
                        if call.get("outcome_id") in meeting_outcome_ids:
                            funnel["meeting_booked"] += 1
                    skip += batch_size
                else:
                    break

        # Get opportunities
        opps_resp = requests.get(f"{base_url}/opportunity/", auth=auth, params={"_limit": 200})
        if opps_resp.ok:
            opps = opps_resp.json().get("data", [])
            for opp in opps:
                status = opp.get("status_type", "").lower()
                value = opp.get("value", 0) or 0

                if status == "active":
                    funnel["opportunity"] += 1
                elif status == "won":
                    funnel["opportunity_won"] += 1
                    funnel["total_revenue"] += value / 100  # Close stores in cents
                elif status == "lost":
                    funnel["opportunity_lost"] += 1

        # Get activities to count meetings
        # Look for activities with type "Meeting" or "Call"
        activities_resp = requests.get(
            f"{base_url}/activity/",
            auth=auth,
            params={"_type": "Meeting", "_limit": 0}
        )
        if activities_resp.ok:
            funnel["meeting_booked"] = activities_resp.json().get("total_results", 0)

        return funnel

    except Exception as e:
        return {"error": str(e)}


def log_batch_results(
    batch_name: str,
    leads_processed: int,
    contacts_found: int,
    atl_contacts: int,
    hunter_calls: int = 0,
    apollo_calls: int = 0,
    cerebras_calls: int = 0
):
    """Log results from a batch import."""
    kpi = load_kpi_data()

    # Calculate costs
    hunter_cost = hunter_calls * COSTS["hunter_domain_search"]
    apollo_cost = apollo_calls * COSTS["apollo_people_match"]
    cerebras_cost = cerebras_calls * COSTS["cerebras_qualification"]
    total_cost = hunter_cost + apollo_cost + cerebras_cost

    # Update totals
    kpi["total_leads_processed"] += leads_processed
    kpi["total_contacts_found"] += contacts_found
    kpi["total_atl_contacts"] += atl_contacts
    kpi["total_enrichment_cost"] += total_cost

    # Log batch details
    batch = {
        "name": batch_name,
        "date": datetime.now().isoformat(),
        "leads_processed": leads_processed,
        "contacts_found": contacts_found,
        "atl_contacts": atl_contacts,
        "atl_rate": round(atl_contacts / contacts_found * 100, 1) if contacts_found > 0 else 0,
        "costs": {
            "hunter": round(hunter_cost, 2),
            "apollo": round(apollo_cost, 2),
            "cerebras": round(cerebras_cost, 4),
            "total": round(total_cost, 2)
        },
        "cost_per_lead": round(total_cost / leads_processed, 3) if leads_processed > 0 else 0,
        "cost_per_atl": round(total_cost / atl_contacts, 3) if atl_contacts > 0 else 0
    }
    kpi["batches"].append(batch)

    save_kpi_data(kpi)
    return batch


def log_conversion(stage: str, lead_id: str, deal_value: float = 0.0):
    """Log a conversion event.

    Stages: mql, sql, meeting_booked, opportunity, opportunity_won, opportunity_lost
    """
    kpi = load_kpi_data()

    # Handle legacy data structure
    if "conversions" in kpi and "funnel" not in kpi:
        kpi["funnel"] = {
            "mql": 0, "sql": 0, "meeting_booked": 0,
            "opportunity": 0, "opportunity_won": 0, "opportunity_lost": 0
        }

    if stage in kpi["funnel"]:
        kpi["funnel"][stage] += 1

    if stage == "opportunity_won" and deal_value > 0:
        kpi["revenue"]["total_contract_value"] += deal_value
        won_count = kpi["funnel"]["opportunity_won"]
        if won_count > 0:
            kpi["revenue"]["avg_deal_size"] = kpi["revenue"]["total_contract_value"] / won_count

    save_kpi_data(kpi)


def print_dashboard(sync_close: bool = False):
    """Print the KPI dashboard.

    Args:
        sync_close: If True, pull live data from Close CRM (read-only)
    """
    kpi = load_kpi_data()
    close_data = None

    if sync_close:
        print("🔄 Syncing with Close CRM (read-only)...", end="", flush=True)
        close_data = sync_close_crm_funnel()
        if "error" in close_data:
            print(f"\n  ⚠️  {close_data['error']}")
            close_data = None
        else:
            print(" ✅ Done\n")

    print("=" * 70)
    print("📊 SALES AGENT KPI DASHBOARD")
    print("=" * 70)

    # Lead Metrics
    print("\n📈 LEAD PIPELINE METRICS")
    print("-" * 70)
    print(f"  Total leads processed:    {kpi['total_leads_processed']:,}")
    print(f"  Total contacts found:     {kpi['total_contacts_found']:,}")
    print(f"  Total ATL contacts:       {kpi['total_atl_contacts']:,}")
    if kpi['total_contacts_found'] > 0:
        atl_rate = kpi['total_atl_contacts'] / kpi['total_contacts_found'] * 100
        print(f"  Overall ATL rate:         {atl_rate:.1f}%")

    # Cost Metrics
    print("\n💰 ENRICHMENT COSTS")
    print("-" * 70)
    print(f"  Total spent:              ${kpi['total_enrichment_cost']:.2f}")
    if kpi['total_leads_processed'] > 0:
        cpl = kpi['total_enrichment_cost'] / kpi['total_leads_processed']
        print(f"  Cost per lead:            ${cpl:.3f}")
    if kpi['total_atl_contacts'] > 0:
        cpa = kpi['total_enrichment_cost'] / kpi['total_atl_contacts']
        print(f"  Cost per ATL:             ${cpa:.3f}")

    # Sales Funnel
    if close_data:
        print("\n🎯 SALES FUNNEL (Live from Close CRM)")
        funnel = close_data
        print(f"  Total Leads in CRM: {funnel.get('total_leads', 0)}")
    else:
        print("\n🎯 SALES FUNNEL (Manual Tracking)")
        # Handle both old and new data structures
        if "funnel" in kpi:
            funnel = kpi['funnel']
        elif "conversions" in kpi:
            funnel = {"mql": 0, "sql": 0, "meeting_booked": 0, "opportunity": 0, "opportunity_won": 0, "opportunity_lost": 0}
        else:
            funnel = {"mql": 0, "sql": 0, "meeting_booked": 0, "opportunity": 0, "opportunity_won": 0, "opportunity_lost": 0}

    print("-" * 70)

    stages = [
        ("MQL (Entered CRM)", funnel.get('mql', 0)),
        ("SQL (Contacted)", funnel.get('sql', 0)),
        ("Meeting Booked", funnel.get('meeting_booked', 0)),
        ("Opportunity", funnel.get('opportunity', 0)),
        ("Opp Won ✅", funnel.get('opportunity_won', 0)),
        ("Opp Lost ❌", funnel.get('opportunity_lost', 0))
    ]
    for name, count in stages:
        bar = "█" * min(int(count), 50)
        print(f"  {name:<18} {count:>5}  {bar}")

    # Show conversion rates
    mql = funnel.get('mql', 0)
    sql = funnel.get('sql', 0)
    meetings = funnel.get('meeting_booked', 0)
    opps = funnel.get('opportunity', 0)
    won = funnel.get('opportunity_won', 0)

    if mql > 0:
        print(f"\n  Conversion Rates:")
        if sql > 0:
            print(f"    MQL → SQL:        {sql/mql*100:.1f}%")
        if meetings > 0:
            print(f"    SQL → Meeting:    {meetings/sql*100:.1f}%" if sql > 0 else f"    MQL → Meeting:    {meetings/mql*100:.1f}%")
        if won > 0:
            print(f"    Opp → Won:        {won/opps*100:.1f}%" if opps > 0 else f"    MQL → Won:        {won/mql*100:.1f}%")

    # Revenue & ROI
    print("\n💵 REVENUE & ROI")
    print("-" * 70)

    # Use Close CRM revenue if synced, otherwise use local tracking
    if close_data and close_data.get('total_revenue', 0) > 0:
        total_revenue = close_data['total_revenue']
        won_deals = close_data.get('opportunity_won', 0)
        avg_deal = total_revenue / won_deals if won_deals > 0 else 0
        print(f"  Total contract value:     ${total_revenue:,.2f}  (from Close CRM)")
        print(f"  Average deal size:        ${avg_deal:,.2f}")
    else:
        rev = kpi['revenue']
        print(f"  Total contract value:     ${rev['total_contract_value']:,.2f}")
        print(f"  Average deal size:        ${rev['avg_deal_size']:,.2f}")
        total_revenue = rev['total_contract_value']

    if kpi['total_enrichment_cost'] > 0 and total_revenue > 0:
        roi = (total_revenue - kpi['total_enrichment_cost']) / kpi['total_enrichment_cost'] * 100
        print(f"  ROI:                      {roi:,.1f}%")

    # Batch History
    if kpi['batches']:
        print("\n📋 BATCH HISTORY (Last 5)")
        print("-" * 70)
        for batch in kpi['batches'][-5:]:
            date = batch['date'][:10]
            print(f"  {date} | {batch['name'][:25]:<25} | "
                  f"{batch['leads_processed']:>4} leads | "
                  f"{batch['atl_contacts']:>3} ATL | "
                  f"${batch['costs']['total']:.2f}")

    print("\n" + "=" * 70)


def analyze_enrichment_output(csv_path: str, batch_name: str):
    """Analyze an enrichment output CSV and log KPIs."""
    df = pd.read_csv(csv_path)

    leads = int(df['company_name'].nunique()) if 'company_name' in df.columns else len(df)
    contacts = int(len(df))
    atl = int(df['is_atl'].sum()) if 'is_atl' in df.columns else 0

    # Estimate API calls (rough heuristic)
    hunter_calls = leads  # One domain search per company
    apollo_calls = contacts  # One match per contact
    cerebras_calls = leads  # One qualification per company

    batch = log_batch_results(
        batch_name=batch_name,
        leads_processed=leads,
        contacts_found=contacts,
        atl_contacts=atl,
        hunter_calls=hunter_calls,
        apollo_calls=apollo_calls,
        cerebras_calls=cerebras_calls
    )

    print(f"\n✅ Logged batch: {batch_name}")
    print(f"   Leads: {leads} | Contacts: {contacts} | ATL: {atl}")
    print(f"   Cost: ${batch['costs']['total']:.2f} (${batch['cost_per_atl']:.3f}/ATL)")


if __name__ == "__main__":
    import sys

    sync_close = False

    if len(sys.argv) > 1:
        if sys.argv[1] == "analyze" and len(sys.argv) > 3:
            # Analyze a CSV: python kpi_dashboard.py analyze <csv_path> <batch_name>
            analyze_enrichment_output(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == "conversion" and len(sys.argv) > 3:
            # Log conversion: python kpi_dashboard.py conversion <stage> <lead_id> [value]
            # Stages: mql, sql, meeting_booked, opportunity, opportunity_won, opportunity_lost
            value = float(sys.argv[4]) if len(sys.argv) > 4 else 0
            log_conversion(sys.argv[2], sys.argv[3], value)
            print(f"✅ Logged {sys.argv[2]} conversion for {sys.argv[3]}")
        elif sys.argv[1] == "--sync" or sys.argv[1] == "sync":
            # Sync with Close CRM: python kpi_dashboard.py --sync
            sync_close = True
        elif sys.argv[1] == "--help" or sys.argv[1] == "help":
            print("""
📊 KPI Dashboard - Usage

  python kpi_dashboard.py                  Show dashboard (local data)
  python kpi_dashboard.py --sync           Show dashboard with Close CRM data (read-only)
  python kpi_dashboard.py analyze <csv> <name>   Log batch from CSV
  python kpi_dashboard.py conversion <stage> <lead_id> [value]   Log funnel conversion

Funnel Stages:
  mql              - Marketing Qualified Lead (entered Close CRM)
  sql              - Sales Qualified Lead (contacted/engaged)
  meeting_booked   - Meeting scheduled
  opportunity      - Active opportunity
  opportunity_won  - Closed won (include deal value!)
  opportunity_lost - Closed lost

Examples:
  python kpi_dashboard.py --sync
  python kpi_dashboard.py conversion mql lead_abc123
  python kpi_dashboard.py conversion opportunity_won lead_abc123 15000
""")
            sys.exit(0)

    # Show dashboard
    print_dashboard(sync_close=sync_close)
