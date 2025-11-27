"""
Activity Endpoint for Sales-Agent Dashboard

GET /api/activity - Returns recent audit trail events
"""

from datetime import datetime, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import random

app = FastAPI()


class AuditEvent(BaseModel):
    id: int
    company_name: str
    event_type: str
    event_details: Dict[str, Any]
    created_at: str
    session_id: Optional[str] = None


# Event types from lead_audit.py model
EVENT_TYPES = [
    "lead_imported",
    "lead_qualified",
    "crm_match_found",
    "lead_enriched",
    "atl_contact_found",
    "dedup_create_new",
    "dedup_skip_duplicate",
    "lead_exported",
]

# Sample company names for mock data
COMPANIES = [
    "ABC HVAC Services",
    "Brower Mechanical Inc",
    "Elite Plumbing & Heating",
    "GreenTech Solar Solutions",
    "Metro Mechanical Contractors",
    "Pacific Coast HVAC",
    "Premier Energy Systems",
    "Quality Air & Heat",
    "SunPower Installations",
    "TechServ Mechanical",
]


def generate_mock_event(event_id: int, minutes_ago: int) -> AuditEvent:
    """Generate a realistic mock audit event."""
    event_type = random.choice(EVENT_TYPES)
    company = random.choice(COMPANIES)
    now = datetime.utcnow()

    # Event-specific details
    details: Dict[str, Any] = {}

    if event_type == "lead_imported":
        details = {
            "source": random.choice(["csv_import", "dealer_scraper", "manual"]),
            "batch_size": random.randint(1, 50),
        }
    elif event_type == "lead_qualified":
        score = random.randint(45, 95)
        details = {
            "score": score,
            "tier": "hot_atl" if score >= 70 else "validated_atl" if score >= 50 else "btl",
            "latency_ms": random.randint(500, 900),
            "model": "cerebras-llama3.1-8b",
        }
    elif event_type == "crm_match_found":
        details = {
            "close_lead_id": f"lead_{random.randint(10000, 99999)}",
            "match_confidence": round(random.uniform(0.85, 0.99), 2),
        }
    elif event_type == "lead_enriched":
        details = {
            "contacts_found": random.randint(1, 8),
            "source": random.choice(["hunter.io", "apollo", "website_scrape"]),
            "cost_usd": round(random.uniform(0.01, 0.03), 3),
        }
    elif event_type == "atl_contact_found":
        details = {
            "contact_name": f"{random.choice(['John', 'Sarah', 'Mike', 'Lisa'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown'])}",
            "title": random.choice(["CEO", "President", "VP Operations", "Owner", "Director"]),
            "email_found": random.choice([True, True, True, False]),
        }
    elif event_type == "dedup_create_new":
        details = {
            "recommendation": "create_new",
            "highest_match": round(random.uniform(0.45, 0.84), 2),
        }
    elif event_type == "dedup_skip_duplicate":
        details = {
            "recommendation": "skip_duplicate",
            "match_confidence": round(random.uniform(0.85, 0.98), 2),
            "existing_lead_id": f"lead_{random.randint(10000, 99999)}",
        }
    elif event_type == "lead_exported":
        details = {
            "output_file": f"enriched_leads_{now.strftime('%Y%m%d_%H%M')}.csv",
            "leads_count": random.randint(10, 150),
        }

    return AuditEvent(
        id=event_id,
        company_name=company,
        event_type=event_type,
        event_details=details,
        created_at=(now - timedelta(minutes=minutes_ago)).isoformat(),
        session_id=f"session_{random.randint(1000, 9999)}" if random.random() > 0.3 else None
    )


@app.get("/api/activity")
async def get_activity(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=100)
) -> JSONResponse:
    """
    Get recent audit trail activity.

    Args:
        hours: Number of hours to look back (default: 24, max: 168)
        limit: Maximum events to return (default: 10, max: 100)

    For MVP: Returns realistic mock data based on sales-agent audit trail.
    Production: Will query lead_audit_log table.
    """
    events = []

    # Generate events distributed over the time period
    max_minutes = hours * 60
    for i in range(limit):
        minutes_ago = random.randint(1, max_minutes)
        event = generate_mock_event(event_id=i + 1, minutes_ago=minutes_ago)
        events.append(event)

    # Sort by created_at descending (most recent first)
    events.sort(key=lambda e: e.created_at, reverse=True)

    return JSONResponse(
        content=[e.model_dump() for e in events],
        headers={
            "Cache-Control": "public, max-age=60",  # 1 min cache
            "Access-Control-Allow-Origin": "*",
        }
    )
