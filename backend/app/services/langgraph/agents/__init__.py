"""
LangGraph Agents Module

Provides 6 production-ready agents for sales automation using LangChain/LangGraph:

1. **QualificationAgent** (LCEL Chain) - Ultra-fast lead scoring with Cerebras
2. **EnrichmentAgent** (ReAct with Tools) - Multi-source data enrichment
3. **GrowthAgent** (Cyclic StateGraph) - Iterative outreach campaigns
4. **MarketingAgent** (Parallel StateGraph) - Multi-channel content generation
5. **BDRAgent** (Human-in-Loop StateGraph) - High-value outreach with approval gates
6. **ConversationAgent** (Voice StateGraph) - Real-time voice conversations

Agent Architecture Patterns:
- LCEL Chains: Linear workflows with structured output
- ReAct: Reasoning + Acting with tool use
- StateGraph: Complex branching, cycles, parallel execution
- Human-in-Loop: Approval gates for critical decisions

Usage:
    ```python
    from app.services.langgraph.agents import (
        QualificationAgent,
        EnrichmentAgent,
        GrowthAgent,
        MarketingAgent,
        BDRAgent,
        ConversationAgent
    )

    # Simple LCEL agent
    qual_agent = QualificationAgent()
    result, latency, metadata = await qual_agent.qualify(
        company_name="Acme Corp",
        industry="SaaS"
    )

    # Complex StateGraph agent (coming in Phase 2.2+)
    # enrichment_agent = EnrichmentAgent()
    # enriched_data = await enrichment_agent.enrich(email="john@acme.com")
    ```
"""

# Phase 2.1: QualificationAgent (LCEL) ✅ COMPLETE
from .qualification_agent import (
    QualificationAgent,
    LeadQualificationResult,
)

# Phase 2.2: EnrichmentAgent (ReAct) ✅ COMPLETE
from .enrichment_agent import (
    EnrichmentAgent,
    EnrichmentResult,
)

# Phase 2.3: GrowthAgent (Cyclic StateGraph) ✅ COMPLETE
from .growth_agent import (
    GrowthAgent,
    GrowthCampaignResult,
)

# Phase 2.4: MarketingAgent (Parallel StateGraph) ✅ COMPLETE
from .marketing_agent import (
    MarketingAgent,
    MarketingCampaignResult,
)

# Phase 2.5: BDRAgent (Human-in-Loop) ✅ COMPLETE
from .bdr_agent import (
    BDRAgent,
    BDROutreachResult,
)

# Phase 2.6: ConversationAgent (Voice) ✅ COMPLETE
from .conversation_agent import (
    ConversationAgent,
    ConversationTurnResult,
)

# ARCHIVED 2025-12-02: Moved to backend/archive/cleanup_2025_12_02/
# - license_auditor_agent.py (unused compliance agent)
# - linkedin_post_writer.py (unused content generation)
# - social_research_agent.py (unused social media agent)
# - reasoner_agent.py (experimental DeepSeek agent)

from .orchestrator_agent import (
    OrchestratorAgent,
    OrchestrationResult,
)

# Phase 3.1: Master Agent System (LangGraph-based) - REMOVED (not used in production)

# Phase 3.2: Agent Subgraphs (Modular Composition) ✅ COMPLETE
from .agent_subgraphs import (
    create_orchestrator_subgraph,
    # ARCHIVED 2025-12-02: Subgraphs for archived agents
    # create_reasoner_subgraph,
    # create_social_research_subgraph,
    # create_linkedin_content_subgraph,
    # create_license_auditor_subgraph,
)

# Phase 3.3: Agent Communication Hub (Inter-Agent Communication) ✅ COMPLETE
from .agent_communication_hub import (
    AgentCommunicationHub,
    InterAgentMessage,
    MessageType,
    AgentStatus,
)

# Phase 3.4: SalesIntelAgent (Sales Intelligence Extraction) ✅ COMPLETE
from .sales_intel_agent import (
    SalesIntelAgent,
    SalesIntelResult,
    extract_sales_intel,
)

# Phase 3.5: OutreachAgent (Multi-Channel GTM via Close CRM) ✅ COMPLETE
from .outreach_agent import OutreachAgent

# Phase 3.6: CloseCRMAgent (Lead Management with Deduplication) ✅ COMPLETE
from .close_crm_agent import CloseCRMAgent


__all__ = [
    # Phase 2.1 - QualificationAgent (LCEL)
    "QualificationAgent",
    "LeadQualificationResult",

    # Phase 2.2 - EnrichmentAgent (ReAct)
    "EnrichmentAgent",
    "EnrichmentResult",

    # Phase 2.3 - GrowthAgent (Cyclic StateGraph)
    "GrowthAgent",
    "GrowthCampaignResult",

    # Phase 2.4 - MarketingAgent (Parallel StateGraph)
    "MarketingAgent",
    "MarketingCampaignResult",

    # Phase 2.5 - BDRAgent (Human-in-Loop)
    "BDRAgent",
    "BDROutreachResult",

    # Phase 2.6 - ConversationAgent (Voice)
    "ConversationAgent",
    "ConversationTurnResult",

    # Phase 3.0 - OrchestratorAgent (still active)
    "OrchestratorAgent",
    "OrchestrationResult",

    # Phase 3.2 - Agent Subgraphs (Modular Composition)
    "create_orchestrator_subgraph",

    # Phase 3.3 - Agent Communication Hub (Inter-Agent Communication)
    "AgentCommunicationHub",
    "InterAgentMessage",
    "MessageType",
    "AgentStatus",

    # Phase 3.4 - SalesIntelAgent (Sales Intelligence Extraction)
    "SalesIntelAgent",
    "SalesIntelResult",
    "extract_sales_intel",

    # Phase 3.5 - OutreachAgent (Multi-Channel GTM via Close CRM)
    "OutreachAgent",

    # Phase 3.6 - CloseCRMAgent (Lead Management with Deduplication)
    "CloseCRMAgent",
]
