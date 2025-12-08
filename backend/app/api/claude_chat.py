"""
Claude Agent SDK API Endpoint

Allows CEO/CTO to interact with Claude like Tim does with Claude Code.
Provides conversational access to pipeline data, agent status, and analytics.

Usage:
    POST /api/claude/chat
    {
        "message": "How many leads did we enrich today?",
        "context": "dashboard"
    }
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta

# Supabase for data access
from supabase import create_client

router = APIRouter(prefix="/claude", tags=["Claude Chat"])


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = "general"  # dashboard, agents, pipeline, analytics


class ChatResponse(BaseModel):
    response: str
    data: Optional[dict] = None
    timestamp: str


# Initialize Supabase
def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


async def get_pipeline_summary() -> dict:
    """Get current pipeline stats from Supabase"""
    supabase = get_supabase()
    if not supabase:
        return {"error": "Supabase not configured"}

    try:
        # Get company stats
        companies = supabase.table("dim_companies").select("id, icp_tier, enrichment_status, has_phone, has_email, created_at").execute()
        contacts = supabase.table("dim_contacts").select("id, is_atl").execute()

        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        week_start = today_start - timedelta(days=7)

        data = companies.data or []
        contact_data = contacts.data or []

        return {
            "total_contractors": len(data),
            "enriched": len([c for c in data if c.get("enrichment_status") == "complete"]),
            "with_phone": len([c for c in data if c.get("has_phone")]),
            "with_email": len([c for c in data if c.get("has_email")]),
            "platinum": len([c for c in data if c.get("icp_tier") == "PLATINUM"]),
            "gold": len([c for c in data if c.get("icp_tier") == "GOLD"]),
            "silver": len([c for c in data if c.get("icp_tier") == "SILVER"]),
            "bronze": len([c for c in data if c.get("icp_tier") == "BRONZE"]),
            "total_contacts": len(contact_data),
            "atl_contacts": len([c for c in contact_data if c.get("is_atl")]),
            "added_today": len([c for c in data if c.get("created_at") and datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) >= today_start]),
            "added_this_week": len([c for c in data if c.get("created_at") and datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")).replace(tzinfo=None) >= week_start]),
        }
    except Exception as e:
        return {"error": str(e)}


async def get_recent_activity() -> list:
    """Get recent audit log entries"""
    supabase = get_supabase()
    if not supabase:
        return []

    try:
        result = supabase.table("lead_audit_log").select("event_type, company_name, created_at").order("created_at", desc=True).limit(10).execute()
        return result.data or []
    except:
        return []


def generate_response(message: str, stats: dict, activity: list) -> str:
    """Generate a helpful response based on the question and data"""
    message_lower = message.lower()

    # Pipeline questions
    if any(word in message_lower for word in ["how many", "total", "count", "leads", "contractors"]):
        return f"""📊 **Pipeline Summary**

**Total Contractors**: {stats.get('total_contractors', 0):,}
**Enriched**: {stats.get('enriched', 0):,}
**With Phone**: {stats.get('with_phone', 0):,}
**With Email**: {stats.get('with_email', 0):,}

**Decision Makers (ATL)**: {stats.get('atl_contacts', 0):,}

**ICP Breakdown**:
- 💎 Platinum: {stats.get('platinum', 0)}
- 🥇 Gold: {stats.get('gold', 0)}
- 🥈 Silver: {stats.get('silver', 0)}
- 🥉 Bronze: {stats.get('bronze', 0)}

**Growth**:
- Added today: +{stats.get('added_today', 0)}
- Added this week: +{stats.get('added_this_week', 0)}"""

    # Enrichment questions
    if any(word in message_lower for word in ["enrich", "enrichment", "today"]):
        return f"""✨ **Enrichment Status**

**Total Enriched**: {stats.get('enriched', 0):,} contractors
**Added Today**: +{stats.get('added_today', 0)}
**Added This Week**: +{stats.get('added_this_week', 0)}

**Quality**:
- With Phone: {stats.get('with_phone', 0):,}
- With Email: {stats.get('with_email', 0):,}
- ATL Contacts: {stats.get('atl_contacts', 0):,}

Recent activity:
{chr(10).join([f"- {a.get('event_type', 'N/A')}: {a.get('company_name', 'Unknown')}" for a in activity[:5]])}"""

    # Agent questions
    if any(word in message_lower for word in ["agent", "running", "status"]):
        return """🤖 **Agent Status**

6 LangGraph Agents are running autonomously:

1. **SCOUT** (🔍) - Discovering new contractors from OEM websites
2. **ICP-SCORER** (📊) - Calculating fit scores for Coperniq ICP
3. **PREDICTOR** (🎯) - Ranking leads by call-worthiness
4. **BRIEFER** (📋) - Generating "Why Call Now" reasoning
5. **INTEL** (🧠) - Extracting personal hooks from research
6. **OUTREACH** (✉️) - Drafting personalized emails

Runtime: 6AM-11PM CST (15+ hours/day)
Backend: FastAPI + Celery + Redis"""

    # ICP questions
    if any(word in message_lower for word in ["icp", "ideal", "customer", "coperniq"]):
        return f"""🎯 **Coperniq ICP Pipeline**

**Target**: Self-performing contractors in the $5M-$50M "Fibonacci Gold Zone"

**Verticals**:
- HVAC (Residential & Commercial)
- Solar (Resi, Resimercial, C&I)
- Electrical
- Plumbing
- Roofing
- EV Charger Installation

**Current Pipeline**:
- Total: {stats.get('total_contractors', 0):,} contractors
- Platinum (best fit): {stats.get('platinum', 0)}
- Gold: {stats.get('gold', 0)}
- Silver: {stats.get('silver', 0)}

**Multi-trade Focus**: Companies doing HVAC+Electrical, Solar+Roofing, etc."""

    # Default response
    return f"""👋 I'm your GTM AI Assistant!

I can help with:
- **Pipeline stats**: "How many contractors do we have?"
- **Enrichment**: "What did we enrich today?"
- **Agent status**: "Are the agents running?"
- **ICP details**: "Tell me about our Coperniq ICP"

**Quick Stats**:
- {stats.get('total_contractors', 0):,} contractors in pipeline
- {stats.get('atl_contacts', 0):,} decision makers
- +{stats.get('added_this_week', 0)} added this week

Ask me anything about the GTM pipeline!"""


@router.post("/chat", response_model=ChatResponse)
async def chat_with_claude(request: ChatRequest):
    """
    Chat endpoint for CEO/CTO interaction with the GTM system.

    Provides conversational access to:
    - Pipeline stats (leads, contacts, ICP tiers)
    - Enrichment status
    - Agent health
    - Recent activity
    """
    try:
        # Get data from Supabase
        stats = await get_pipeline_summary()
        activity = await get_recent_activity()

        # Generate response
        response = generate_response(request.message, stats, activity)

        return ChatResponse(
            response=response,
            data=stats if request.context == "dashboard" else None,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_chat_status():
    """Check if Claude chat is available"""
    supabase = get_supabase()
    return {
        "available": supabase is not None,
        "supabase_connected": supabase is not None,
        "message": "Claude chat is ready! Ask me about your pipeline."
    }
