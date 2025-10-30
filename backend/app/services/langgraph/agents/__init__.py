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

# Phase 2.7: LicenseAuditorAgent (Compliance StateGraph) ✅ COMPLETE
from .license_auditor_agent import (
    LicenseAuditorAgent,
    LicenseAuditResult,
)

# Phase 2.8: LinkedInPostWriterAgent (Content Generation StateGraph) ✅ COMPLETE
from .linkedin_post_writer import (
    LinkedInPostWriter,
    LinkedInPostResult,
)

# Phase 2.9: SocialResearchAgent (Social Media StateGraph) ✅ COMPLETE
from .social_research_agent import (
    SocialResearchAgent,
    SocialResearchResult,
)

# Phase 3.0: Advanced Agentic Agents (DeepSeek-based) ✅ COMPLETE
from .reasoner_agent import (
    ReasonerAgent,
    ReasoningResult,
)

from .orchestrator_agent import (
    OrchestratorAgent,
    OrchestrationResult,
)

# Phase 3.1: Master Agent System (LangGraph-based) ✅ COMPLETE
from .master_agent_system import (
    MasterAgentSystem,
    MasterAgentState,
)

# Phase 3.2: Agent Subgraphs (Modular Composition) ✅ COMPLETE
from .agent_subgraphs import (
    create_reasoner_subgraph,
    create_orchestrator_subgraph,
    create_social_research_subgraph,
    create_linkedin_content_subgraph,
    create_contractor_reviews_subgraph,
    create_license_auditor_subgraph,
)

# Phase 3.3: Agent Communication Hub (Inter-Agent Communication) ✅ COMPLETE
from .agent_communication_hub import (
    AgentCommunicationHub,
    InterAgentMessage,
    MessageType,
    AgentStatus,
)


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

    # Phase 2.7 - LicenseAuditorAgent (Compliance)
    "LicenseAuditorAgent",
    "LicenseAuditResult",

    # Phase 2.8 - LinkedInPostWriterAgent (Content Generation)
    "LinkedInPostWriter",
    "LinkedInPostResult",

    # Phase 2.9 - SocialResearchAgent (Social Media)
    "SocialResearchAgent",
    "SocialResearchResult",

    # Phase 3.0 - Advanced Agentic Agents (DeepSeek-based)
    "ReasonerAgent",
    "ReasoningResult",
    "OrchestratorAgent",
    "OrchestrationResult",

    # Phase 3.1 - Master Agent System (LangGraph-based)
    "MasterAgentSystem",
    "MasterAgentState",

    # Phase 3.2 - Agent Subgraphs (Modular Composition)
    "create_reasoner_subgraph",
    "create_orchestrator_subgraph",
    "create_social_research_subgraph",
    "create_linkedin_content_subgraph",
    "create_contractor_reviews_subgraph",
    "create_license_auditor_subgraph",

    # Phase 3.3 - Agent Communication Hub (Inter-Agent Communication)
    "AgentCommunicationHub",
    "InterAgentMessage",
    "MessageType",
    "AgentStatus",
]
