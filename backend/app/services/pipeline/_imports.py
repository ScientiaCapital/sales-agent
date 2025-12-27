"""Lazy imports for pipeline agents to avoid loading during test collection."""

QualificationAgent = None
EnrichmentAgent = None
MarketingAgent = None
DeduplicationService = None
CloseService = None
CloseDeduplicationService = None
ColdReachClient = None


def lazy_import_agents():
    """Lazy import agents to avoid loading all dependencies during test collection."""
    global QualificationAgent, EnrichmentAgent, MarketingAgent
    global DeduplicationService, CloseService, CloseDeduplicationService, ColdReachClient

    if QualificationAgent is None:
        from app.services.langgraph.agents.qualification_agent import QualificationAgent as QA
        from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent as EA
        from app.services.langgraph.agents.marketing_agent import MarketingAgent as MA
        from app.services.crm.deduplication import DeduplicationEngine as DS
        from app.services.crm.close import CloseProvider as CS
        from app.services.crm.close_deduplication import CloseDeduplicationService as CDS
        from app.services.cold_reach_client import ColdReachClient as CRC

        QualificationAgent = QA
        EnrichmentAgent = EA
        MarketingAgent = MA
        DeduplicationService = DS
        CloseService = CS
        CloseDeduplicationService = CDS
        ColdReachClient = CRC


def get_agents():
    """Get imported agent classes."""
    lazy_import_agents()
    return {
        "QualificationAgent": QualificationAgent,
        "EnrichmentAgent": EnrichmentAgent,
        "MarketingAgent": MarketingAgent,
        "DeduplicationService": DeduplicationService,
        "CloseService": CloseService,
        "CloseDeduplicationService": CloseDeduplicationService,
        "ColdReachClient": ColdReachClient,
    }
