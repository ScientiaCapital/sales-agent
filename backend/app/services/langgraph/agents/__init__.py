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

# Phase 2.5: BDRAgent (Human-in-Loop) - Coming soon
# from .bdr_agent import BDRAgent

# Phase 2.6: ConversationAgent (Voice) - Coming soon
# from .conversation_agent import ConversationAgent


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

    # Phase 2.5-2.6 - Coming Soon
    # "BDRAgent",
    # "ConversationAgent",
]
