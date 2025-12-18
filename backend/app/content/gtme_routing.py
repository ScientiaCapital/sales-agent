"""
GTME Routing: Route Prospects to Sequences Based on Pain Patterns

This module:
1. Pulls discovery questions from dim_gtme_prospects to power enrichment
2. Routes prospects to custom sequences based on pain indicators
3. Recommends optimal GTME content based on company attributes

Usage:
    from app.content.gtme_routing import GTMERouter

    router = GTMERouter()

    # Get discovery questions for a prospect (for enrichment)
    questions = await router.get_discovery_questions("norrell-construction")

    # Route a company to the best sequence based on pain signals
    recommendation = await router.recommend_sequence(company_id="...")

    # Get personalized cold opener based on pain patterns
    opener = await router.get_personalized_opener(company_id="...", channel="call")
"""
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# Pain pattern -> Sequence mapping
PAIN_SEQUENCE_MAP = {
    # Solar++ Campaign - targets solar contractors expanding into storage/MEP
    "expanding_services": "solar-plus-plus-sequence",
    "adding_storage": "solar-plus-plus-sequence",
    "multi_trade": "solar-plus-plus-sequence",
    "permit_complexity": "solar-plus-plus-sequence",
    "rebate_complexity": "solar-plus-plus-sequence",

    # Frankenstack Campaign - targets contractors drowning in disconnected tools
    "multiple_systems": "frankenstack-sequence",
    "servicetitan_user": "frankenstack-sequence",
    "spreadsheet_overload": "frankenstack-sequence",
    "data_silos": "frankenstack-sequence",
    "manual_handoffs": "frankenstack-sequence",
    "quoting_delays": "frankenstack-sequence",

    # General follow-up for warm leads
    "prior_engagement": "solar-plus-plus-followup-sequence",
    "website_visitor": "solar-plus-plus-followup-sequence",
}


class GTMERouter:
    """
    Route prospects to optimal GTME content based on pain patterns.

    The router:
    1. Analyzes company data for pain indicators
    2. Matches pain patterns to the best campaign/sequence
    3. Provides discovery questions to power enrichment
    4. Recommends personalized openers for calls
    """

    def __init__(self, supabase_client=None):
        """Initialize with optional Supabase client."""
        self._client = supabase_client

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            self._client = create_client(url, key)
        return self._client

    # =========================================================================
    # DISCOVERY QUESTIONS (Power Enrichment Workflows)
    # =========================================================================

    async def get_discovery_questions(
        self,
        prospect_key: Optional[str] = None,
        campaign_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get discovery questions to power enrichment workflows.

        If a prospect_key is provided, returns prospect-specific questions.
        Otherwise, returns campaign-level discovery questions.

        Args:
            prospect_key: Specific prospect (for flagship accounts)
            campaign_type: 'solar_plus_plus' or 'frankenstack'

        Returns:
            List of {question, why_it_matters} dicts
        """
        try:
            # First check for prospect-specific questions
            if prospect_key:
                prospect = self.client.table("dim_gtme_prospects").select(
                    "discovery_questions"
                ).eq("prospect_key", prospect_key).single().execute()

                if prospect.data and prospect.data.get("discovery_questions"):
                    return prospect.data["discovery_questions"]

            # Fall back to campaign-level discovery questions
            campaign_key = campaign_type.replace("_", "-") if campaign_type else "solar-plus-plus"

            campaign = self.client.table("dim_gtme_campaigns").select(
                "target_signals, messaging_framework"
            ).eq("campaign_key", campaign_key).single().execute()

            if campaign.data:
                # Generate discovery questions from target signals
                signals = campaign.data.get("target_signals", [])
                questions = []

                for signal in signals:
                    questions.append({
                        "question": f"Does the company show signs of: {signal.get('signal', '')}?",
                        "why_it_matters": signal.get("description", "Key ICP indicator"),
                    })

                # Add standard discovery questions
                questions.extend([
                    {
                        "question": "What project management or field service tools do they use?",
                        "why_it_matters": "Identifies Frankenstack pain - multiple disconnected tools",
                    },
                    {
                        "question": "Are they expanding into new service lines (storage, HVAC, etc.)?",
                        "why_it_matters": "Identifies Solar++ opportunity - need unified platform",
                    },
                    {
                        "question": "What's their quoting process like? Manual or automated?",
                        "why_it_matters": "Speed-to-quote is key differentiator for Coperniq",
                    },
                    {
                        "question": "How many office staff vs field technicians?",
                        "why_it_matters": "Field-to-office ratio indicates admin overhead pain",
                    },
                ])

                return questions

            return []

        except Exception as e:
            logger.error(f"Failed to get discovery questions: {e}")
            return []

    # =========================================================================
    # PAIN PATTERN ANALYSIS
    # =========================================================================

    async def analyze_pain_patterns(
        self,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Analyze a company's data for pain indicators.

        Checks enrichment data, AI analysis, and manual notes for
        signals that match our campaign pain points.

        Args:
            company_id: Company to analyze

        Returns:
            {pain_patterns: [...], confidence: float, recommended_campaign: str}
        """
        try:
            company = self.client.table("dim_companies").select(
                """
                company_name, domain, industry, services,
                ai_company_description, ai_icp_score, ai_icp_reasoning,
                tool_stack, enrichment_notes,
                original_source
                """
            ).eq("company_id", company_id).single().execute()

            if not company.data:
                return {"pain_patterns": [], "confidence": 0.0, "recommended_campaign": None}

            data = company.data
            pain_patterns = []
            confidence_score = 0.0

            # Check for Solar++ indicators
            services = (data.get("services") or "").lower()
            description = (data.get("ai_company_description") or "").lower()
            source = (data.get("original_source") or "").lower()

            # Solar company expanding
            if any(s in services for s in ["solar", "pv", "photovoltaic"]):
                if any(s in services for s in ["storage", "battery", "hvac", "electrical"]):
                    pain_patterns.append("multi_trade")
                    confidence_score += 0.3
                elif "spw" in source or "amicus_solar" in source:
                    pain_patterns.append("expanding_services")
                    confidence_score += 0.2

            # Check for Frankenstack indicators
            tool_stack = (data.get("tool_stack") or "").lower()
            if "servicetitan" in tool_stack:
                pain_patterns.append("servicetitan_user")
                confidence_score += 0.2
            if any(t in tool_stack for t in ["quickbooks", "excel", "spreadsheet"]):
                pain_patterns.append("spreadsheet_overload")
                confidence_score += 0.15
            if len(tool_stack.split(",")) >= 3:
                pain_patterns.append("multiple_systems")
                confidence_score += 0.2

            # Check AI reasoning for pain signals
            icp_reasoning = (data.get("ai_icp_reasoning") or "").lower()
            if "quoting" in icp_reasoning or "estimate" in icp_reasoning:
                pain_patterns.append("quoting_delays")
                confidence_score += 0.15
            if "handoff" in icp_reasoning or "manual" in icp_reasoning:
                pain_patterns.append("manual_handoffs")
                confidence_score += 0.1

            # Determine recommended campaign
            solar_patterns = {"expanding_services", "adding_storage", "multi_trade",
                           "permit_complexity", "rebate_complexity"}
            frankenstack_patterns = {"multiple_systems", "servicetitan_user",
                                    "spreadsheet_overload", "data_silos",
                                    "manual_handoffs", "quoting_delays"}

            solar_count = len(set(pain_patterns) & solar_patterns)
            frankenstack_count = len(set(pain_patterns) & frankenstack_patterns)

            if solar_count > frankenstack_count:
                recommended = "solar-plus-plus"
            elif frankenstack_count > solar_count:
                recommended = "frankenstack"
            elif "spw" in source or "amicus_solar" in source:
                recommended = "solar-plus-plus"  # Default for solar lists
            else:
                recommended = "solar-plus-plus"  # Default fallback

            return {
                "pain_patterns": pain_patterns,
                "confidence": min(confidence_score, 1.0),
                "recommended_campaign": recommended,
                "solar_indicator_count": solar_count,
                "frankenstack_indicator_count": frankenstack_count,
            }

        except Exception as e:
            logger.error(f"Failed to analyze pain patterns: {e}")
            return {"pain_patterns": [], "confidence": 0.0, "recommended_campaign": None}

    # =========================================================================
    # SEQUENCE ROUTING
    # =========================================================================

    async def recommend_sequence(
        self,
        company_id: str,
        sequence_type: str = "cold"
    ) -> Dict[str, Any]:
        """
        Recommend the best sequence for a company based on pain patterns.

        Args:
            company_id: Company to route
            sequence_type: 'cold', 'warm', 'followup', 'breakup'

        Returns:
            {sequence_key, campaign_key, confidence, reasoning}
        """
        try:
            # Analyze pain patterns
            analysis = await self.analyze_pain_patterns(company_id)

            campaign = analysis.get("recommended_campaign", "solar-plus-plus")

            # Build sequence key based on campaign and type
            sequence_key = f"{campaign}-{sequence_type}-sequence"

            # Check if sequence exists
            seq = self.client.table("dim_gtme_sequences").select(
                "sequence_key, name"
            ).eq("sequence_key", sequence_key).eq("is_active", True).single().execute()

            if not seq.data:
                # Fall back to main sequence
                sequence_key = f"{campaign}-sequence"
                seq = self.client.table("dim_gtme_sequences").select(
                    "sequence_key, name"
                ).eq("sequence_key", sequence_key).eq("is_active", True).single().execute()

            reasoning = []
            if analysis.get("pain_patterns"):
                reasoning.append(f"Pain patterns detected: {', '.join(analysis['pain_patterns'])}")
            reasoning.append(f"Recommended campaign: {campaign}")

            return {
                "sequence_key": seq.data["sequence_key"] if seq.data else sequence_key,
                "sequence_name": seq.data["name"] if seq.data else sequence_key,
                "campaign_key": campaign,
                "confidence": analysis.get("confidence", 0.5),
                "pain_patterns": analysis.get("pain_patterns", []),
                "reasoning": "; ".join(reasoning),
            }

        except Exception as e:
            logger.error(f"Failed to recommend sequence: {e}")
            return {
                "sequence_key": "solar-plus-plus-sequence",
                "campaign_key": "solar-plus-plus",
                "confidence": 0.0,
                "reasoning": f"Error: {e}",
            }

    async def get_personalized_opener(
        self,
        company_id: str,
        channel: str = "call"
    ) -> Dict[str, Any]:
        """
        Get personalized cold opener based on pain patterns.

        Args:
            company_id: Company to call
            channel: 'call' or 'email'

        Returns:
            {opener, variant, campaign_key, personalization_notes}
        """
        try:
            # Analyze pain
            analysis = await self.analyze_pain_patterns(company_id)
            campaign = analysis.get("recommended_campaign", "solar-plus-plus")

            # Get company info for personalization
            company = self.client.table("dim_companies").select(
                "company_name, original_source"
            ).eq("company_id", company_id).single().execute()

            company_name = company.data.get("company_name", "") if company.data else ""
            source = (company.data.get("original_source") or "").lower() if company.data else ""

            # Get script
            script = self.client.table("dim_gtme_scripts").select(
                "cold_openers, warm_opener"
            ).eq("campaign_key", campaign).eq("is_active", True).single().execute()

            if not script.data:
                return {"opener": None, "campaign_key": campaign}

            cold_openers = script.data.get("cold_openers", [])

            # Select opener variant based on pain patterns
            variant = "A"  # Default
            personalization_notes = []

            # If we detected specific pains, use variant B (more targeted)
            if analysis.get("pain_patterns"):
                variant = "B" if len(analysis["pain_patterns"]) >= 2 else "A"
                personalization_notes.append(f"Detected: {', '.join(analysis['pain_patterns'][:2])}")

            # If from SPW list, note for personalization
            if "spw" in source:
                personalization_notes.append("From Solar Power World list - mention it!")

            # Get the opener
            opener = None
            for o in cold_openers:
                if o.get("option") == variant:
                    opener = o.get("script")
                    break

            return {
                "opener": opener,
                "variant": variant,
                "campaign_key": campaign,
                "personalization_notes": personalization_notes,
                "pain_patterns": analysis.get("pain_patterns", []),
                "company_name": company_name,
            }

        except Exception as e:
            logger.error(f"Failed to get personalized opener: {e}")
            return {"opener": None, "campaign_key": "solar-plus-plus", "error": str(e)}

    # =========================================================================
    # BULK ROUTING (For enrichment pipelines)
    # =========================================================================

    async def route_batch(
        self,
        company_ids: List[str],
        sequence_type: str = "cold"
    ) -> List[Dict[str, Any]]:
        """
        Route a batch of companies to sequences.

        Use this for enrichment pipelines to pre-route leads
        before outreach begins.

        Args:
            company_ids: List of company IDs to route
            sequence_type: Type of sequence to recommend

        Returns:
            List of routing recommendations
        """
        results = []
        for company_id in company_ids:
            rec = await self.recommend_sequence(company_id, sequence_type)
            rec["company_id"] = company_id
            results.append(rec)

        return results


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

_router = None


def _get_router() -> GTMERouter:
    """Get singleton router instance."""
    global _router
    if _router is None:
        _router = GTMERouter()
    return _router


async def get_discovery_questions(**kwargs) -> List[Dict[str, str]]:
    """Get discovery questions for enrichment."""
    return await _get_router().get_discovery_questions(**kwargs)


async def recommend_sequence(company_id: str, **kwargs) -> Dict[str, Any]:
    """Recommend a sequence for a company."""
    return await _get_router().recommend_sequence(company_id, **kwargs)


async def get_personalized_opener(company_id: str, **kwargs) -> Dict[str, Any]:
    """Get personalized opener for a company."""
    return await _get_router().get_personalized_opener(company_id, **kwargs)


async def route_batch(company_ids: List[str], **kwargs) -> List[Dict[str, Any]]:
    """Route a batch of companies."""
    return await _get_router().route_batch(company_ids, **kwargs)
