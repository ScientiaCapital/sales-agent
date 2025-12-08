"""
Signal Detection Service

Determines the "why now" signal for outreach based on:
1. Close CRM lead status (SQL, SAL, MQL, etc.)
2. Activity history (last contact date, correspondence)
3. ICP tier and scoring data

Signal Types:
- SQL_BOOKING: Lead is Sales Qualified, needs meeting booking
- SAL_FOLLOWUP: Sales Accepted, needs follow-up sequence
- NURTURE_REENGAGE: Nurture Hot/Cold, needs re-engagement
- OPPORTUNITY_PROGRESS: In pipeline, needs deal progression
- COLD_NEW: Never contacted, first touch needed
- STALE_LEAD: 90+ days since last contact
- REPLY: Lead responded, immediate follow-up
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import os
import httpx

logger = logging.getLogger(__name__)

# Close CRM Lead Status IDs (from Tim's Close account)
CLOSE_STATUS_IDS = {
    "SQL": "stat_49hSBBD1DHbwxRPHSiqMDx2CDM6IuTLNRBC1tljKwgK",
    "SAL": "stat_fixvC94WqhKKdYOChaiiLk7mFPiATnHk83jfHXARI1Q",
    "MQL": "stat_gmoph1y5BMjOIAyzMKv5AJ0HPksjINuHLL4rP1WIowv",
    "Opportunity": "stat_s2o7BE20Y7nnQ0UlRh8qzaoqTnqNXHWektjFexHy9PU",
    "Customer": "stat_jmqx3wlvBskEA7jv0n92hMA8PgzokJjpEIpXgn46ouu",
    "Nurture_Hot": "stat_oaw8oi3A4QAbQNPbEHhQ0wNmQkuKzUsRz5s1aqTGVM3",
    "Nurture_Cold": "stat_kNYHn58vnlGWXux0DVaLwqiXXx4dRsrzkfgflEkEUcO",
    "Raw": "stat_4qxeqdfEDGNFmh93pFmXz4l8bw78DuQtTlATratY2Qb",
    "Unqualified": "stat_G0Wh2TC7KCPDlS1dncGTU8myEZeSO5AwnSyzbm6GTHg",
    "Junk": "stat_enAxL5F9Iz1tRyaHQtomVUJDq7RYyvyN4iLibe1KQaD",
}

# Reverse lookup
STATUS_ID_TO_NAME = {v: k for k, v in CLOSE_STATUS_IDS.items()}

# Signal type to draft messaging strategy
SIGNAL_STRATEGIES = {
    "SQL_BOOKING": {
        "priority": 1,
        "email_tone": "booking",
        "reason_template": "Sales Qualified - ready for demo/meeting",
        "cta": "Schedule a call",
    },
    "REPLY": {
        "priority": 2,
        "email_tone": "followup",
        "reason_template": "Responded to outreach - immediate follow-up needed",
        "cta": "Continue the conversation",
    },
    "OPPORTUNITY_PROGRESS": {
        "priority": 3,
        "email_tone": "deal_progression",
        "reason_template": "Active opportunity - move deal forward",
        "cta": "Next steps",
    },
    "SAL_FOLLOWUP": {
        "priority": 4,
        "email_tone": "followup_sequence",
        "reason_template": "Sales Accepted - needs follow-up sequence",
        "cta": "Reconnect",
    },
    "NURTURE_REENGAGE": {
        "priority": 5,
        "email_tone": "reengagement",
        "reason_template": "In nurture - checking in after time has passed",
        "cta": "Touch base",
    },
    "STALE_LEAD": {
        "priority": 6,
        "email_tone": "reengagement",
        "reason_template": "90+ days since last contact - re-engagement needed",
        "cta": "Reconnect",
    },
    "COLD_NEW": {
        "priority": 7,
        "email_tone": "first_touch",
        "reason_template": "Net new lead - first touch outreach",
        "cta": "Introduction",
    },
    "MQL_QUALIFY": {
        "priority": 8,
        "email_tone": "qualification",
        "reason_template": "Marketing Qualified - needs sales qualification",
        "cta": "Quick call",
    },
}


class SignalDetector:
    """
    Detects outreach signals from Close CRM and Supabase data.

    Determines "why now" for each lead to ensure contextual, strategic outreach.
    """

    def __init__(self, close_api_key: Optional[str] = None):
        """Initialize signal detector."""
        self.api_key = close_api_key or os.getenv("CLOSE_API_KEY")

    async def detect_signal(
        self,
        company_id: str,
        close_lead_id: Optional[str] = None,
        company_data: Optional[Dict[str, Any]] = None,
        check_activities: bool = True,
    ) -> Tuple[str, str, str, Optional[str]]:
        """
        Detect the signal type for a lead.

        Args:
            company_id: Supabase company ID
            close_lead_id: Close CRM lead ID (if known)
            company_data: Company data from Supabase (optional, will fetch if not provided)
            check_activities: Whether to check Close CRM activity history

        Returns:
            Tuple of (signal_type, signal_source, signal_reason, close_lead_status)
        """
        signal_type = "COLD_NEW"  # Default if no other signal
        signal_source = "default"
        signal_reason = "Net new lead"
        close_lead_status = None

        # If we have a Close lead ID, check the lead status
        if close_lead_id:
            status_info = await self._get_close_lead_status(close_lead_id)
            if status_info:
                close_lead_status = status_info.get("status_label")
                signal_type, signal_source, signal_reason = self._status_to_signal(
                    status_info.get("status_id"),
                    status_info.get("status_label"),
                )

                # Check for staleness (90+ days since last activity)
                if check_activities:
                    last_activity = await self._get_last_activity_date(close_lead_id)
                    if last_activity:
                        days_since = (datetime.utcnow() - last_activity).days
                        if days_since > 90:
                            signal_type = "STALE_LEAD"
                            signal_source = "activity_date"
                            signal_reason = f"Last contact was {days_since} days ago - re-engagement needed"

        # If no Close lead, use Supabase ICP data as signal
        elif company_data:
            icp_tier = company_data.get("icp_tier")
            icp_score = company_data.get("icp_score", 0) or 0

            if icp_tier == "PLATINUM" or icp_score >= 80:
                signal_reason = f"High-value lead (ICP: {icp_tier}, Score: {icp_score})"
            elif icp_tier == "GOLD" or icp_score >= 65:
                signal_reason = f"Good fit lead (ICP: {icp_tier}, Score: {icp_score})"
            else:
                signal_reason = f"New lead in pipeline (ICP: {icp_tier or 'Unknown'})"

            signal_source = "supabase_icp"

        logger.info(f"Signal detected for {company_id}: {signal_type} ({signal_source})")
        return signal_type, signal_source, signal_reason, close_lead_status

    async def _get_close_lead_status(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get lead status from Close CRM."""
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.close.com/api/v1/lead/{lead_id}/",
                    auth=(self.api_key, ""),
                    params={"_fields": "id,status_id,status_label"}
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "lead_id": data.get("id"),
                        "status_id": data.get("status_id"),
                        "status_label": data.get("status_label"),
                    }
        except Exception as e:
            logger.warning(f"Error fetching Close lead status: {e}")

        return None

    async def _get_last_activity_date(self, lead_id: str) -> Optional[datetime]:
        """Get the most recent activity date for a lead."""
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.close.com/api/v1/activity/",
                    auth=(self.api_key, ""),
                    params={
                        "lead_id": lead_id,
                        "_limit": 1,
                        "_order_by": "-date_created",
                        "_fields": "date_created"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        date_str = data["data"][0].get("date_created")
                        if date_str:
                            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"Error fetching last activity date: {e}")

        return None

    def _status_to_signal(
        self, status_id: str, status_label: str
    ) -> Tuple[str, str, str]:
        """Map Close CRM status to signal type."""
        status_name = STATUS_ID_TO_NAME.get(status_id, status_label)

        if status_name == "SQL":
            return "SQL_BOOKING", "close_status", "Sales Qualified - ready for demo booking"
        elif status_name == "SAL":
            return "SAL_FOLLOWUP", "close_status", "Sales Accepted - follow-up sequence"
        elif status_name == "Opportunity":
            return "OPPORTUNITY_PROGRESS", "close_status", "Active opportunity - deal progression"
        elif status_name == "Nurture_Hot":
            return "NURTURE_REENGAGE", "close_status", "Nurture Hot - warm re-engagement"
        elif status_name == "Nurture_Cold":
            return "NURTURE_REENGAGE", "close_status", "Nurture Cold - checking back in"
        elif status_name == "MQL":
            return "MQL_QUALIFY", "close_status", "Marketing Qualified - needs qualification"
        elif status_name == "Raw":
            return "COLD_NEW", "close_status", "Raw lead - first touch"
        elif status_name == "Customer":
            return "COLD_NEW", "close_status", "Existing customer - upsell/cross-sell"
        else:
            return "COLD_NEW", "close_status", f"Status: {status_label}"

    async def get_correspondence_summary(
        self, lead_id: str, limit: int = 10
    ) -> Optional[str]:
        """
        Get a summary of recent correspondence with the lead.

        Returns a formatted string summarizing:
        - Recent emails (sent/received)
        - Recent calls (outcome)
        - Recent notes
        """
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.close.com/api/v1/activity/",
                    auth=(self.api_key, ""),
                    params={
                        "lead_id": lead_id,
                        "_limit": limit,
                        "_order_by": "-date_created",
                        "_fields": "_type,date_created,direction,subject,disposition,note"
                    }
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                if not data.get("data"):
                    return "No prior correspondence"

                summary_parts = []
                for activity in data["data"]:
                    act_type = activity.get("_type")
                    date_str = activity.get("date_created", "")[:10]

                    if act_type == "Email":
                        direction = activity.get("direction", "unknown")
                        subject = activity.get("subject", "No subject")[:40]
                        summary_parts.append(f"- {date_str}: Email ({direction}) - {subject}")
                    elif act_type == "Call":
                        direction = activity.get("direction", "unknown")
                        disposition = activity.get("disposition", "unknown")
                        summary_parts.append(f"- {date_str}: Call ({direction}) - {disposition}")
                    elif act_type == "Note":
                        note = (activity.get("note") or "")[:50]
                        summary_parts.append(f"- {date_str}: Note - {note}")

                if not summary_parts:
                    return "No relevant activity found"

                return "\n".join(summary_parts[:5])  # Top 5 activities

        except Exception as e:
            logger.warning(f"Error getting correspondence summary: {e}")
            return None


# Singleton instance
_signal_detector: Optional[SignalDetector] = None


def get_signal_detector() -> SignalDetector:
    """Get or create signal detector instance."""
    global _signal_detector
    if _signal_detector is None:
        _signal_detector = SignalDetector()
    return _signal_detector


async def detect_outreach_signal(
    company_id: str,
    close_lead_id: Optional[str] = None,
    company_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to detect outreach signal.

    Returns dict with:
    - signal_type: Type of signal (SQL_BOOKING, NURTURE_REENGAGE, etc.)
    - signal_source: Where the signal came from (close_status, supabase_icp, etc.)
    - signal_reason: Human-readable reason for outreach
    - close_lead_status: Current Close CRM status (if applicable)
    - correspondence_summary: Recent activity summary (if available)
    - strategy: Draft generation strategy for this signal type
    """
    detector = get_signal_detector()

    signal_type, signal_source, signal_reason, close_lead_status = await detector.detect_signal(
        company_id=company_id,
        close_lead_id=close_lead_id,
        company_data=company_data,
    )

    # Get correspondence summary if we have a Close lead
    correspondence_summary = None
    if close_lead_id:
        correspondence_summary = await detector.get_correspondence_summary(close_lead_id)

    # Get strategy for this signal type
    strategy = SIGNAL_STRATEGIES.get(signal_type, SIGNAL_STRATEGIES["COLD_NEW"])

    return {
        "signal_type": signal_type,
        "signal_source": signal_source,
        "signal_reason": signal_reason,
        "close_lead_status": close_lead_status,
        "correspondence_summary": correspondence_summary,
        "strategy": strategy,
    }
