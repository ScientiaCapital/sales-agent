"""
GTME Telemetry: Track and Analyze Outreach Performance

Records every touch using GTME content and provides analytics
to close the attribution loop.

Usage:
    from app.content.gtme_telemetry import GTMETelemetry

    telemetry = GTMETelemetry()

    # Record a touch
    touch_id = await telemetry.record_touch(
        company_id="...",
        contact_id="...",
        channel="email",
        touch_type="sequence_email",
        sequence_key="solar-plus-plus-sequence",
        sequence_step_number=1,
        subject_variant="A"
    )

    # Update outcome when reply comes in
    await telemetry.update_outcome(touch_id, outcome="replied")

    # Get sequence performance
    perf = await telemetry.get_sequence_performance("solar-plus-plus-sequence")
"""
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class GTMETelemetry:
    """
    Track GTME content usage and outcomes for attribution.

    This closes the loop: we know which messaging converts and by how much.
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
    # RECORD TOUCHES
    # =========================================================================

    async def record_touch(
        self,
        channel: str,
        touch_type: str,
        company_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        user_id: Optional[str] = None,
        sequence_key: Optional[str] = None,
        campaign_key: Optional[str] = None,
        script_key: Optional[str] = None,
        resource_key: Optional[str] = None,
        prospect_key: Optional[str] = None,
        sequence_step_number: Optional[int] = None,
        script_variant: Optional[str] = None,
        subject_variant: Optional[str] = None,
        outcome: str = "pending",
        close_activity_id: Optional[str] = None,
        close_lead_id: Optional[str] = None,
        notes: Optional[str] = None,
        touched_at: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Record a GTME touch event.

        Args:
            channel: 'email', 'call', 'sms', 'linkedin', 'voicemail'
            touch_type: Type of touch (sequence_email, cold_call, etc.)
            company_id: dim_companies reference
            contact_id: dim_contacts reference
            user_id: dim_users reference (BDR)
            sequence_key: Which GTME sequence was used
            campaign_key: Which GTME campaign
            script_key: Which phone script
            resource_key: Which resource was shared
            prospect_key: If this is a flagship prospect
            sequence_step_number: Step number in sequence
            script_variant: A/B test variant for script
            subject_variant: A/B test variant for subject line
            outcome: Initial outcome (usually 'pending' or 'sent')
            close_activity_id: Close CRM activity ID
            close_lead_id: Close CRM lead ID
            notes: BDR notes
            touched_at: When touch occurred (defaults to now)

        Returns:
            touch_id or None if failed
        """
        try:
            # Check if first touch for this contact
            is_first_touch = False
            touch_sequence_position = 1

            if contact_id:
                existing = self.client.table("fact_gtme_touches").select(
                    "touch_id"
                ).eq("contact_id", contact_id).execute()

                if not existing.data:
                    is_first_touch = True
                else:
                    touch_sequence_position = len(existing.data) + 1

            data = {
                "channel": channel,
                "touch_type": touch_type,
                "outcome": outcome,
                "is_first_touch": is_first_touch,
                "touch_sequence_position": touch_sequence_position,
                "touched_at": (touched_at or datetime.utcnow()).isoformat(),
            }

            # Add optional fields
            if company_id:
                data["company_id"] = company_id
            if contact_id:
                data["contact_id"] = contact_id
            if user_id:
                data["user_id"] = user_id
            if sequence_key:
                data["sequence_key"] = sequence_key
            if campaign_key:
                data["campaign_key"] = campaign_key
            if script_key:
                data["script_key"] = script_key
            if resource_key:
                data["resource_key"] = resource_key
            if prospect_key:
                data["prospect_key"] = prospect_key
            if sequence_step_number:
                data["sequence_step_number"] = sequence_step_number
            if script_variant:
                data["script_variant"] = script_variant
            if subject_variant:
                data["subject_variant"] = subject_variant
            if close_activity_id:
                data["close_activity_id"] = close_activity_id
            if close_lead_id:
                data["close_lead_id"] = close_lead_id
            if notes:
                data["notes"] = notes

            result = self.client.table("fact_gtme_touches").insert(data).execute()

            if result.data:
                touch_id = result.data[0]["touch_id"]
                logger.info(f"Recorded GTME touch: {touch_type} via {channel} -> {touch_id}")
                return touch_id
            return None

        except Exception as e:
            logger.error(f"Failed to record touch: {e}")
            return None

    async def update_outcome(
        self,
        touch_id: str,
        outcome: str,
        call_duration_seconds: Optional[int] = None,
        open_count: Optional[int] = None,
        click_count: Optional[int] = None,
        meeting_booked_at: Optional[datetime] = None,
        attributed_revenue_usd: Optional[float] = None,
        pain_indicators_mentioned: Optional[List[str]] = None,
        discovery_answers: Optional[Dict[str, str]] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Update the outcome of a touch.

        Args:
            touch_id: The touch to update
            outcome: New outcome status
            call_duration_seconds: Call duration if applicable
            open_count: Number of email opens
            click_count: Number of link clicks
            meeting_booked_at: When meeting was booked
            attributed_revenue_usd: Revenue to attribute if won
            pain_indicators_mentioned: Which pains came up
            discovery_answers: Answers to discovery questions
            notes: Additional notes

        Returns:
            True if successful
        """
        try:
            data = {
                "outcome": outcome,
                "outcome_updated_at": datetime.utcnow().isoformat(),
            }

            if call_duration_seconds is not None:
                data["call_duration_seconds"] = call_duration_seconds
            if open_count is not None:
                data["open_count"] = open_count
            if click_count is not None:
                data["click_count"] = click_count
            if meeting_booked_at:
                data["meeting_booked_at"] = meeting_booked_at.isoformat()
            if attributed_revenue_usd is not None:
                data["attributed_revenue_usd"] = attributed_revenue_usd
            if pain_indicators_mentioned:
                data["pain_indicators_mentioned"] = pain_indicators_mentioned
            if discovery_answers:
                data["discovery_answers"] = discovery_answers
            if notes:
                data["notes"] = notes

            self.client.table("fact_gtme_touches").update(data).eq(
                "touch_id", touch_id
            ).execute()

            logger.info(f"Updated touch {touch_id} outcome: {outcome}")
            return True

        except Exception as e:
            logger.error(f"Failed to update touch outcome: {e}")
            return False

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def get_sequence_performance(
        self,
        sequence_key: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics for sequences.

        Args:
            sequence_key: Specific sequence (None = all)
            days: Look back period

        Returns:
            List of performance records
        """
        try:
            # Use the pre-built view
            result = self.client.table("v_gtme_sequence_performance").select("*")

            if sequence_key:
                result = result.eq("sequence_key", sequence_key)

            return result.execute().data or []

        except Exception as e:
            logger.error(f"Failed to get sequence performance: {e}")
            return []

    async def get_script_ab_analysis(
        self,
        script_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get A/B test analysis for phone scripts.

        Args:
            script_key: Specific script (None = all)

        Returns:
            List of A/B performance records
        """
        try:
            result = self.client.table("v_gtme_script_ab_analysis").select("*")

            if script_key:
                result = result.eq("script_key", script_key)

            return result.execute().data or []

        except Exception as e:
            logger.error(f"Failed to get script A/B analysis: {e}")
            return []

    async def get_daily_activity(
        self,
        user_id: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get daily GTME activity summary.

        Args:
            user_id: Specific BDR (None = all)
            days: Look back period

        Returns:
            Daily activity records
        """
        try:
            result = self.client.table("v_gtme_daily_activity").select("*")

            if user_id:
                result = result.eq("user_id", user_id)

            return result.order("activity_date", desc=True).limit(days * 3).execute().data or []

        except Exception as e:
            logger.error(f"Failed to get daily activity: {e}")
            return []

    async def get_touch_history(
        self,
        contact_id: Optional[str] = None,
        company_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get touch history for a contact or company.

        Args:
            contact_id: Contact to look up
            company_id: Company to look up
            limit: Max records

        Returns:
            Touch history records
        """
        try:
            query = self.client.table("fact_gtme_touches").select("*")

            if contact_id:
                query = query.eq("contact_id", contact_id)
            elif company_id:
                query = query.eq("company_id", company_id)

            return query.order("touched_at", desc=True).limit(limit).execute().data or []

        except Exception as e:
            logger.error(f"Failed to get touch history: {e}")
            return []

    async def get_meeting_attribution(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get touches that led to meetings (attribution analysis).

        Args:
            days: Look back period

        Returns:
            Meeting-attributed touches
        """
        try:
            result = self.client.table("fact_gtme_touches").select(
                "*, dim_gtme_sequences(name), dim_gtme_scripts(name), dim_gtme_campaigns(name)"
            ).in_(
                "outcome", ["meeting_booked", "demo_scheduled", "callback_scheduled"]
            ).order("meeting_booked_at", desc=True).limit(100).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get meeting attribution: {e}")
            return []


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

_telemetry = None


def _get_telemetry() -> GTMETelemetry:
    """Get singleton telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = GTMETelemetry()
    return _telemetry


async def record_touch(**kwargs) -> Optional[str]:
    """Record a GTME touch event."""
    return await _get_telemetry().record_touch(**kwargs)


async def update_outcome(touch_id: str, **kwargs) -> bool:
    """Update touch outcome."""
    return await _get_telemetry().update_outcome(touch_id, **kwargs)


async def get_sequence_performance(**kwargs) -> List[Dict[str, Any]]:
    """Get sequence performance metrics."""
    return await _get_telemetry().get_sequence_performance(**kwargs)


async def get_meeting_attribution(**kwargs) -> List[Dict[str, Any]]:
    """Get meeting attribution data."""
    return await _get_telemetry().get_meeting_attribution(**kwargs)
