"""
Agent Health Endpoint for Sales-Agent Dashboard

GET /api/agents - Returns health status for all 6 LangGraph agents
"""

from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Literal
import random

app = FastAPI()


class AgentMetric(BaseModel):
    agent_type: str
    display_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_latency_ms: float
    target_latency_ms: int
    avg_cost_usd: float
    success_rate: float
    status: Literal["healthy", "degraded", "failing", "idle"]
    last_execution_at: str


def get_agent_status(success_rate: float, avg_latency: float, target_latency: int) -> str:
    """Determine agent health status based on metrics."""
    if success_rate >= 0.95 and avg_latency <= target_latency:
        return "healthy"
    elif success_rate >= 0.85 or avg_latency <= target_latency * 1.5:
        return "degraded"
    else:
        return "failing"


@app.get("/api/agents")
async def get_agents() -> JSONResponse:
    """
    Get health status for all 6 LangGraph agents.

    For MVP: Returns realistic mock data based on actual agent performance.
    Production: Will query agent_executions table.
    """
    now = datetime.utcnow()

    # Agent configurations with realistic performance data
    agents_config = [
        {
            "agent_type": "qualification",
            "display_name": "Qualification Agent",
            "target_latency_ms": 1000,
            "avg_latency_ms": 633,
            "executions": 847,
            "success_rate": 0.998,
            "cost": 0.000006,
        },
        {
            "agent_type": "enrichment",
            "display_name": "Enrichment Agent",
            "target_latency_ms": 3000,
            "avg_latency_ms": 2400,
            "executions": 724,
            "success_rate": 0.982,
            "cost": 0.015,
        },
        {
            "agent_type": "growth",
            "display_name": "Growth Agent",
            "target_latency_ms": 5000,
            "avg_latency_ms": 5200,  # Slightly over target
            "executions": 156,
            "success_rate": 0.957,
            "cost": 0.00009,
        },
        {
            "agent_type": "marketing",
            "display_name": "Marketing Agent",
            "target_latency_ms": 4000,
            "avg_latency_ms": 3800,
            "executions": 89,
            "success_rate": 0.991,
            "cost": 0.0002,
        },
        {
            "agent_type": "bdr",
            "display_name": "BDR Agent",
            "target_latency_ms": 2000,
            "avg_latency_ms": 1900,
            "executions": 234,
            "success_rate": 0.995,
            "cost": 0.0001,
        },
        {
            "agent_type": "conversation",
            "display_name": "Conversation Agent",
            "target_latency_ms": 1000,
            "avg_latency_ms": 872,
            "executions": 67,
            "success_rate": 0.999,
            "cost": 0.001,
        },
    ]

    agents = []
    for config in agents_config:
        successful = int(config["executions"] * config["success_rate"])
        failed = config["executions"] - successful

        agent = AgentMetric(
            agent_type=config["agent_type"],
            display_name=config["display_name"],
            total_executions=config["executions"],
            successful_executions=successful,
            failed_executions=failed,
            avg_latency_ms=config["avg_latency_ms"],
            target_latency_ms=config["target_latency_ms"],
            avg_cost_usd=config["cost"],
            success_rate=config["success_rate"],
            status=get_agent_status(
                config["success_rate"],
                config["avg_latency_ms"],
                config["target_latency_ms"]
            ),
            last_execution_at=(now - timedelta(minutes=random.randint(1, 30))).isoformat()
        )
        agents.append(agent)

    return JSONResponse(
        content=[a.model_dump() for a in agents],
        headers={
            "Cache-Control": "public, max-age=30",  # 30s cache
            "Access-Control-Allow-Origin": "*",
        }
    )
