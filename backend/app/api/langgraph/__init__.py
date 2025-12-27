"""
LangGraph Agent API - Modular Router

This module provides a unified router combining all LangGraph agent endpoints:
- Core: /invoke, /stream, /state (agent invocation and state management)
- Scout: /scout/* (lead discovery and prioritization)
- Report: /report/* (morning report generation)
- Intel: /intel/* (sales intelligence and personal hooks)
- Growth: /growth/* (multi-touch campaigns)
- BDR: /bdr/* (human-in-loop outreach)

Usage in main.py:
    from app.api.langgraph import router as langgraph_router
    app.include_router(langgraph_router, prefix="/api/langgraph")
"""

from fastapi import APIRouter

from app.api.langgraph.core_routes import router as core_router
from app.api.langgraph.scout_routes import router as scout_router
from app.api.langgraph.report_routes import router as report_router
from app.api.langgraph.intel_routes import router as intel_router
from app.api.langgraph.growth_routes import router as growth_router
from app.api.langgraph.bdr_routes import router as bdr_router

# Create unified router
router = APIRouter(prefix="/langgraph", tags=["langgraph"])

# Include all sub-routers
router.include_router(core_router)     # /invoke, /stream, /state
router.include_router(scout_router)    # /scout/*
router.include_router(report_router)   # /report/*
router.include_router(intel_router)    # /intel/*
router.include_router(growth_router)   # /growth/*
router.include_router(bdr_router)      # /bdr/*

# Export schemas and helpers for external use
from app.api.langgraph.schemas import (
    InvokeAgentRequest,
    AgentResponse,
    StateResponse,
    ScoutRunRequest,
    ScoutRunResponse,
    ReportRunRequest,
    ReportRunResponse,
    SalesIntelRunRequest,
    SalesIntelRunResponse,
    GrowthCampaignRequest,
    GrowthCampaignResponse,
    BDRRunRequest,
    BDRRunResponse,
    BDRApprovalRequest,
)
from app.api.langgraph.helpers import get_or_create_thread_id, VALID_AGENTS

__all__ = [
    "router",
    # Schemas
    "InvokeAgentRequest",
    "AgentResponse",
    "StateResponse",
    "ScoutRunRequest",
    "ScoutRunResponse",
    "ReportRunRequest",
    "ReportRunResponse",
    "SalesIntelRunRequest",
    "SalesIntelRunResponse",
    "GrowthCampaignRequest",
    "GrowthCampaignResponse",
    "BDRRunRequest",
    "BDRRunResponse",
    "BDRApprovalRequest",
    # Helpers
    "get_or_create_thread_id",
    "VALID_AGENTS",
]
