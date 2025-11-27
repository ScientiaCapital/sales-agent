"""
Metrics Endpoint for Sales-Agent Dashboard

GET /api/metrics - Returns pipeline and performance metrics
"""

from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict

app = FastAPI()


class MetricsSummary(BaseModel):
    # Lead Pipeline
    total_leads: int
    qualified_leads: int
    meetings_booked: int
    opportunities: int
    won_deals: int
    lost_deals: int

    # Conversion Rates
    qualification_rate: float
    meeting_conversion_rate: float
    opportunity_conversion_rate: float
    win_rate: float

    # Performance
    avg_qualification_time_ms: float
    total_cost_usd: float
    cost_per_lead: float

    # Revenue
    total_revenue: float
    avg_deal_size: float

    # Meta
    period_start: str
    period_end: str


@app.get("/api/metrics")
async def get_metrics() -> JSONResponse:
    """
    Get pipeline metrics summary.

    For MVP: Returns realistic mock data based on sales-agent pipeline.
    Production: Will query PostgreSQL/Supabase for real metrics.
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # Mock data based on typical sales-agent pipeline performance
    response = MetricsSummary(
        # Lead Pipeline (realistic for MEP contractor pipeline)
        total_leads=1247,
        qualified_leads=902,
        meetings_booked=229,
        opportunities=112,
        won_deals=35,
        lost_deals=77,

        # Conversion Rates
        qualification_rate=0.723,  # 72.3% MQL -> SQL
        meeting_conversion_rate=0.254,  # 25.4% SQL -> Meeting
        opportunity_conversion_rate=0.489,  # 48.9% Meeting -> Opp
        win_rate=0.312,  # 31.2% Opp -> Won

        # Performance (Cerebras-powered qualification)
        avg_qualification_time_ms=633,  # Target: <1000ms
        total_cost_usd=14.87,  # 4-tier model stack
        cost_per_lead=0.012,  # $0.012/lead vs $3+ for premium AI

        # Revenue
        total_revenue=875000,  # $875K pipeline
        avg_deal_size=25000,  # $25K avg for Coperniq solar installs

        # Meta
        period_start=week_ago.isoformat(),
        period_end=now.isoformat()
    )

    return JSONResponse(
        content=response.model_dump(),
        headers={
            "Cache-Control": "public, max-age=300",  # 5 min cache
            "Access-Control-Allow-Origin": "*",
        }
    )
