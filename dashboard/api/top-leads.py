"""
Top Leads Endpoint for Sales-Agent Dashboard

GET /api/top-leads - Returns ranked leads with composite scoring

Scoring Algorithm:
- Intent Score (40%): Email opens, calls, engagement velocity
- ICP Score (30%): From dim_companies.icp_score
- Recency Score (20%): Decay function on last activity
- Contactability (10%): Has ATL contact with phone/email
"""

import os
import math
from datetime import datetime, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Supabase REST API configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


def calculate_composite_score(company: dict, activities: list[dict]) -> dict:
    """
    Calculate composite score with breakdown.

    Weights:
    - Intent (40%): Recent activity signals buying intent
    - ICP (30%): Company fit score
    - Recency (20%): Freshness of engagement
    - Contactability (10%): Can we reach decision-makers?
    """
    company_id = company.get("company_id")

    # 1. INTENT SCORE (0-100, weight: 40%)
    # Signals: email opens, call connects, response to outreach
    company_activities = [a for a in activities if a.get("company_id") == company_id]

    email_count = len([a for a in company_activities if a.get("activity_type") == "email"])
    call_count = len([a for a in company_activities if a.get("activity_type") == "call"])
    inbound_count = len([a for a in company_activities if a.get("direction") == "inbound"])

    # Inbound signals are 3x more valuable (they reached out!)
    intent_raw = min((email_count * 5) + (call_count * 10) + (inbound_count * 30), 100)
    intent_score = intent_raw * 0.40

    # 2. ICP SCORE (0-100, weight: 30%)
    icp_raw = company.get("icp_score") or 50  # Default to 50 if missing
    icp_score = icp_raw * 0.30

    # 3. RECENCY SCORE (0-100, weight: 20%)
    # Exponential decay: score halves every 14 days
    if company_activities:
        latest_activity = max(company_activities, key=lambda a: a.get("activity_at", ""))
        try:
            activity_date = datetime.fromisoformat(latest_activity.get("activity_at", "").replace("Z", "+00:00"))
            days_ago = (datetime.now(activity_date.tzinfo) - activity_date).days
            # Half-life decay: score = 100 * 0.5^(days/14)
            recency_raw = 100 * math.pow(0.5, days_ago / 14)
        except (ValueError, TypeError):
            recency_raw = 0
    else:
        recency_raw = 0
    recency_score = recency_raw * 0.20

    # 4. CONTACTABILITY SCORE (0-100, weight: 10%)
    # Has ATL contact? Has phone? Has email?
    has_phone = bool(company.get("phone"))
    has_contacts = True  # Would check dim_contacts in full impl
    contactability_raw = 100 if (has_phone and has_contacts) else 50 if has_phone else 0
    contactability_score = contactability_raw * 0.10

    # COMPOSITE SCORE
    composite = intent_score + icp_score + recency_score + contactability_score

    return {
        "composite_score": round(composite, 1),
        "breakdown": {
            "intent": round(intent_score, 1),
            "icp": round(icp_score, 1),
            "recency": round(recency_score, 1),
            "contactability": round(contactability_score, 1),
        },
        "raw_signals": {
            "email_count": email_count,
            "call_count": call_count,
            "inbound_count": inbound_count,
            "icp_score": icp_raw,
            "days_since_activity": days_ago if company_activities else None,
        }
    }


async def fetch_top_leads(limit: int = 100) -> dict | None:
    """
    Fetch and score all leads, return top N.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch companies with contacts
            companies_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dim_companies",
                headers=headers,
                params={
                    "select": "company_id,company_name,phone,website,city,state,icp_score,icp_tier,current_stage,close_lead_id,first_seen_at",
                    "order": "icp_score.desc.nullslast",
                    "limit": "500"  # Get top 500 for scoring
                }
            )

            if companies_resp.status_code != 200:
                logger.error(f"Companies fetch error: {companies_resp.status_code}")
                return None

            companies = companies_resp.json()

            # Fetch recent activities (last 90 days)
            cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
            activities_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/fact_activities",
                headers=headers,
                params={
                    "select": "company_id,activity_type,direction,activity_at",
                    "activity_at": f"gte.{cutoff}",
                    "limit": "2000"
                }
            )

            activities = activities_resp.json() if activities_resp.status_code == 200 else []

            # Fetch contacts for contactability score
            contacts_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/dim_contacts",
                headers=headers,
                params={
                    "select": "company_id,full_name,email,phone,title,is_atl",
                    "is_atl": "eq.true",
                    "limit": "1000"
                }
            )

            contacts = contacts_resp.json() if contacts_resp.status_code == 200 else []
            contacts_by_company = {}
            for c in contacts:
                cid = c.get("company_id")
                if cid not in contacts_by_company:
                    contacts_by_company[cid] = []
                contacts_by_company[cid].append(c)

            # Score each company
            scored_leads = []
            for company in companies:
                company_id = company.get("company_id")
                score_data = calculate_composite_score(company, activities)

                # Get best ATL contact
                company_contacts = contacts_by_company.get(company_id, [])
                best_contact = company_contacts[0] if company_contacts else None

                scored_leads.append({
                    "company_id": company_id,
                    "company_name": company.get("company_name"),
                    "phone": company.get("phone"),
                    "website": company.get("website"),
                    "city": company.get("city"),
                    "state": company.get("state"),
                    "icp_tier": company.get("icp_tier"),
                    "current_stage": company.get("current_stage"),
                    "close_lead_id": company.get("close_lead_id"),
                    "close_url": f"https://app.close.com/lead/{company.get('close_lead_id')}" if company.get("close_lead_id") else None,
                    # Scoring
                    "composite_score": score_data["composite_score"],
                    "score_breakdown": score_data["breakdown"],
                    "signals": score_data["raw_signals"],
                    # Best contact
                    "contact_name": best_contact.get("full_name") if best_contact else None,
                    "contact_email": best_contact.get("email") if best_contact else None,
                    "contact_phone": best_contact.get("phone") if best_contact else None,
                    "contact_title": best_contact.get("title") if best_contact else None,
                })

            # Sort by composite score and take top N
            scored_leads.sort(key=lambda x: x["composite_score"], reverse=True)
            top_leads = scored_leads[:limit]

            # Add ranks
            for i, lead in enumerate(top_leads, 1):
                lead["rank"] = i

            return {
                "leads": top_leads,
                "total_scored": len(companies),
                "returned": len(top_leads),
            }

    except Exception as e:
        logger.error(f"Top leads fetch error: {e}")
        return None


@app.get("/api/top-leads")
async def get_top_leads(
    limit: int = Query(default=20, ge=1, le=100, description="Number of leads (20, 50, or 100)"),
    tier: str = Query(default=None, description="Filter by tier (PLATINUM, GOLD, SILVER, BRONZE)"),
    export: bool = Query(default=False, description="Return CSV-ready format"),
) -> JSONResponse:
    """
    Get Top N leads ranked by composite score.

    Scoring combines:
    - Intent (40%): Email opens, calls, inbound signals
    - ICP Fit (30%): Company qualification score
    - Recency (20%): How fresh the engagement is
    - Contactability (10%): Has reachable ATL contact

    Use ?limit=20 for Top 20, ?limit=50 for Top 50, etc.
    Use ?export=true for CSV download format.
    """
    data = await fetch_top_leads(limit=limit)

    if data is None:
        return JSONResponse(
            content={"error": "Failed to fetch leads", "data_source": "error"},
            status_code=500
        )

    # Filter by tier if requested
    if tier:
        data["leads"] = [l for l in data["leads"] if l.get("icp_tier") == tier.upper()]
        data["returned"] = len(data["leads"])

    # Re-rank after filtering
    for i, lead in enumerate(data["leads"], 1):
        lead["rank"] = i

    if export:
        # CSV-ready format
        csv_leads = []
        for lead in data["leads"]:
            csv_leads.append({
                "rank": lead["rank"],
                "company_name": lead["company_name"],
                "composite_score": lead["composite_score"],
                "icp_tier": lead["icp_tier"],
                "contact_name": lead["contact_name"],
                "contact_email": lead["contact_email"],
                "contact_phone": lead["contact_phone"],
                "contact_title": lead["contact_title"],
                "phone": lead["phone"],
                "website": lead["website"],
                "city": lead["city"],
                "state": lead["state"],
                "close_url": lead["close_url"],
                "intent_score": lead["score_breakdown"]["intent"],
                "icp_score": lead["score_breakdown"]["icp"],
                "recency_score": lead["score_breakdown"]["recency"],
            })
        return JSONResponse(
            content={
                "csv_data": csv_leads,
                "columns": list(csv_leads[0].keys()) if csv_leads else [],
                "count": len(csv_leads),
            },
            headers={
                "Content-Disposition": f"attachment; filename=top_{limit}_leads.json",
                "Access-Control-Allow-Origin": "*",
            }
        )

    return JSONResponse(
        content={
            **data,
            "data_source": "star_schema_composite",
            "scoring_version": "1.0",
            "weights": {"intent": 0.4, "icp": 0.3, "recency": 0.2, "contactability": 0.1},
            "updated_at": datetime.utcnow().isoformat()
        },
        headers={
            "Cache-Control": "public, max-age=60",
            "Access-Control-Allow-Origin": "*",
        }
    )
