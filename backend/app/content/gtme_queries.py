"""
GTME Content Queries

Query functions for agents to retrieve GTME content from Supabase.
These functions are used by LangGraph agents to get sequences, scripts, and resources.

Usage:
    from app.content.gtme_queries import GTMEQueries

    queries = GTMEQueries()

    # Get a sequence for the sequence engine
    seq = await queries.get_sequence("solar-plus-plus-cold")

    # Get phone script for calling
    script = await queries.get_phone_script("solar-plus-plus-phone-script")

    # Get campaign strategy
    campaign = await queries.get_campaign("solar-plus-plus")
"""
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GTMEQueries:
    """
    Query GTME content from Supabase.

    Used by agents to retrieve sequences, scripts, campaigns, and resources
    without needing file system access.
    """

    def __init__(self, supabase_client=None):
        """
        Initialize with optional Supabase client.

        Args:
            supabase_client: Supabase client (auto-creates if None)
        """
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
    # SEQUENCE QUERIES
    # =========================================================================

    async def get_sequence(self, sequence_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a sequence by key.

        Args:
            sequence_key: e.g., 'solar-plus-plus-cold-sequence'

        Returns:
            Sequence data or None
        """
        try:
            result = self.client.table("dim_gtme_sequences").select("*").eq(
                "sequence_key", sequence_key
            ).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"Sequence not found: {sequence_key} - {e}")
            return None

    async def get_sequences_by_campaign(self, campaign_type: str) -> List[Dict[str, Any]]:
        """
        Get all sequences for a campaign type.

        Args:
            campaign_type: 'solar_plus_plus', 'frankenstack', or 'general'

        Returns:
            List of sequences
        """
        result = self.client.table("dim_gtme_sequences").select("*").eq(
            "campaign_type", campaign_type
        ).eq("is_active", True).execute()
        return result.data or []

    async def get_sequence_for_engine(self, sequence_key: str) -> Optional[Dict[str, Any]]:
        """
        Get sequence in SequenceEngine.create_sequence() format.

        Args:
            sequence_key: Sequence identifier

        Returns:
            Dict ready for create_sequence()
        """
        seq = await self.get_sequence(sequence_key)
        if not seq:
            return None

        # Convert to engine format
        steps = seq.get("steps", [])
        email_steps = [
            {
                "step_number": step["step_number"],
                "subject": step.get("subject", ""),
                "body": step.get("body", ""),
                "delay_days": step.get("delay_days", 0),
            }
            for step in steps
            if step.get("channel") == "email"
        ]

        return {
            "sequence_id": seq["sequence_key"].replace("-", "_"),
            "name": seq["name"],
            "steps": email_steps,
            "stop_on_reply": True,
            "stop_on_bounce": True,
        }

    async def list_sequences(self) -> List[Dict[str, Any]]:
        """List all active sequences (summary only)."""
        result = self.client.table("dim_gtme_sequences").select(
            "sequence_key, name, campaign_type, sequence_type, total_steps, channels_used"
        ).eq("is_active", True).execute()
        return result.data or []

    # =========================================================================
    # CAMPAIGN QUERIES
    # =========================================================================

    async def get_campaign(self, campaign_key: str) -> Optional[Dict[str, Any]]:
        """
        Get campaign strategy by key.

        Args:
            campaign_key: e.g., 'solar-plus-plus'

        Returns:
            Campaign data or None
        """
        try:
            result = self.client.table("dim_gtme_campaigns").select("*").eq(
                "campaign_key", campaign_key
            ).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"Campaign not found: {campaign_key} - {e}")
            return None

    async def get_objection_handling(self, campaign_key: str) -> List[Dict[str, str]]:
        """
        Get objection handling for a campaign.

        Args:
            campaign_key: Campaign identifier

        Returns:
            List of {objection, response} dicts
        """
        campaign = await self.get_campaign(campaign_key)
        if campaign:
            return campaign.get("objection_handling", [])
        return []

    async def get_messaging_framework(self, campaign_key: str) -> Dict[str, str]:
        """
        Get messaging framework for a campaign.

        Args:
            campaign_key: Campaign identifier

        Returns:
            {primary_pain, core_narrative, value_prop}
        """
        campaign = await self.get_campaign(campaign_key)
        if campaign:
            return campaign.get("messaging_framework", {})
        return {}

    # =========================================================================
    # SCRIPT QUERIES
    # =========================================================================

    async def get_phone_script(self, script_key: str) -> Optional[Dict[str, Any]]:
        """
        Get phone script by key.

        Args:
            script_key: e.g., 'solar-plus-plus-phone-script'

        Returns:
            Script data or None
        """
        try:
            result = self.client.table("dim_gtme_scripts").select("*").eq(
                "script_key", script_key
            ).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"Script not found: {script_key} - {e}")
            return None

    async def get_script_for_campaign(self, campaign_key: str) -> Optional[Dict[str, Any]]:
        """
        Get phone script for a campaign.

        Args:
            campaign_key: e.g., 'solar-plus-plus'

        Returns:
            Script data or None
        """
        try:
            result = self.client.table("dim_gtme_scripts").select("*").eq(
                "campaign_key", campaign_key
            ).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"No script found for campaign: {campaign_key} - {e}")
            return None

    async def get_cold_opener(self, campaign_key: str, option: str = "A") -> Optional[str]:
        """
        Get a specific cold opener for a campaign.

        Args:
            campaign_key: Campaign identifier
            option: "A" or "B"

        Returns:
            Cold opener script text or None
        """
        script = await self.get_script_for_campaign(campaign_key)
        if script and script.get("cold_openers"):
            for opener in script["cold_openers"]:
                if opener.get("option") == option:
                    return opener.get("script")
        return None

    async def get_voicemail(self, campaign_key: str) -> Optional[str]:
        """
        Get voicemail script for a campaign.

        Args:
            campaign_key: Campaign identifier

        Returns:
            Voicemail text or None
        """
        script = await self.get_script_for_campaign(campaign_key)
        if script:
            return script.get("voicemail")
        return None

    # =========================================================================
    # RESOURCE QUERIES
    # =========================================================================

    async def get_resource(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a value-add resource.

        Args:
            resource_key: e.g., 'field-to-office-gap'

        Returns:
            Resource data or None
        """
        try:
            result = self.client.table("dim_gtme_resources").select("*").eq(
                "resource_key", resource_key
            ).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"Resource not found: {resource_key} - {e}")
            return None

    async def get_resource_content(self, resource_key: str) -> Optional[str]:
        """
        Get just the markdown content for a resource.

        Args:
            resource_key: Resource identifier

        Returns:
            Markdown content or None
        """
        resource = await self.get_resource(resource_key)
        if resource:
            return resource.get("content_markdown")
        return None

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all active resources (summary only)."""
        result = self.client.table("dim_gtme_resources").select(
            "resource_key, title, summary, use_case"
        ).eq("is_active", True).execute()
        return result.data or []

    # =========================================================================
    # PROSPECT QUERIES
    # =========================================================================

    async def get_prospect(self, prospect_key: str) -> Optional[Dict[str, Any]]:
        """
        Get prospect research by key.

        Args:
            prospect_key: e.g., 'norrell-construction'

        Returns:
            Prospect data or None
        """
        try:
            result = self.client.table("dim_gtme_prospects").select("*").eq(
                "prospect_key", prospect_key
            ).single().execute()
            return result.data
        except Exception as e:
            logger.warning(f"Prospect not found: {prospect_key} - {e}")
            return None

    async def list_prospects_by_status(self, status: str = "researched") -> List[Dict[str, Any]]:
        """
        List prospects by status.

        Args:
            status: 'researched', 'contacted', 'engaged', 'meeting', 'won', 'lost'

        Returns:
            List of prospects
        """
        result = self.client.table("dim_gtme_prospects").select("*").eq(
            "status", status
        ).execute()
        return result.data or []

    # =========================================================================
    # CONVENIENCE METHODS FOR AGENTS
    # =========================================================================

    async def get_full_context_for_call(self, campaign_key: str) -> Dict[str, Any]:
        """
        Get everything an agent needs for a cold call.

        Returns:
            {script, campaign, objections, resources}
        """
        campaign = await self.get_campaign(campaign_key)
        script = await self.get_script_for_campaign(campaign_key)

        return {
            "campaign": campaign,
            "script": script,
            "cold_openers": script.get("cold_openers", []) if script else [],
            "warm_opener": script.get("warm_opener", "") if script else "",
            "voicemail": script.get("voicemail", "") if script else "",
            "response_paths": script.get("response_paths", []) if script else [],
            "objections": campaign.get("objection_handling", []) if campaign else [],
            "messaging": campaign.get("messaging_framework", {}) if campaign else {},
        }

    async def get_full_context_for_sequence(self, sequence_key: str) -> Dict[str, Any]:
        """
        Get everything needed to run a sequence.

        Returns:
            {sequence, campaign, resources}
        """
        sequence = await self.get_sequence(sequence_key)
        if not sequence:
            return {}

        campaign_type = sequence.get("campaign_type", "general")
        campaign_key = campaign_type.replace("_", "-")
        campaign = await self.get_campaign(campaign_key)

        return {
            "sequence": sequence,
            "engine_format": await self.get_sequence_for_engine(sequence_key),
            "campaign": campaign,
            "messaging": campaign.get("messaging_framework", {}) if campaign else {},
        }


# =========================================================================
# CONVENIENCE FUNCTIONS (for direct import)
# =========================================================================

_queries = None


def _get_queries() -> GTMEQueries:
    """Get singleton queries instance."""
    global _queries
    if _queries is None:
        _queries = GTMEQueries()
    return _queries


async def get_sequence(sequence_key: str) -> Optional[Dict[str, Any]]:
    """Get a sequence from Supabase."""
    return await _get_queries().get_sequence(sequence_key)


async def get_sequence_for_engine(sequence_key: str) -> Optional[Dict[str, Any]]:
    """Get sequence in engine format."""
    return await _get_queries().get_sequence_for_engine(sequence_key)


async def get_phone_script(script_key: str) -> Optional[Dict[str, Any]]:
    """Get a phone script from Supabase."""
    return await _get_queries().get_phone_script(script_key)


async def get_cold_opener(campaign_key: str, option: str = "A") -> Optional[str]:
    """Get a cold opener for a campaign."""
    return await _get_queries().get_cold_opener(campaign_key, option)


async def get_campaign(campaign_key: str) -> Optional[Dict[str, Any]]:
    """Get campaign strategy from Supabase."""
    return await _get_queries().get_campaign(campaign_key)


async def get_objection_handling(campaign_key: str) -> List[Dict[str, str]]:
    """Get objection handling for a campaign."""
    return await _get_queries().get_objection_handling(campaign_key)


async def get_resource_content(resource_key: str) -> Optional[str]:
    """Get resource markdown content."""
    return await _get_queries().get_resource_content(resource_key)


async def get_call_context(campaign_key: str) -> Dict[str, Any]:
    """Get full context for a cold call."""
    return await _get_queries().get_full_context_for_call(campaign_key)
