"""
BDR Work Queue Service - Tim's prioritized daily calling list with talking points.

Queries mv_bdr_work_queue materialized view from Supabase and generates
personalized talking points for each lead based on:
- ICP tier and score
- OEM certifications (good openers)
- Reputation score (if available from review scraping)
- Services offered (has_hvac, has_solar, etc.)
- Contact context (ATL title, recent activity)

Usage:
    service = BDRWorkQueueService()
    queue = await service.get_work_queue(limit=25, filter_tier="PLATINUM")

    # Each item includes:
    # - recommended_action: "📞 First Call - ATL Decision Maker"
    # - talking_points: ["They're a Carrier dealer - ask about service volume", ...]
    # - contact info, ICP data, Close CRM URL
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

import httpx
from dotenv import load_dotenv

# Suppress httpx debug logging (prevents API key exposure in logs)
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

logger = logging.getLogger(__name__)


class WorkQueueAction(Enum):
    """Recommended actions from mv_bdr_work_queue."""
    HOT_INTENT = "hot_intent"          # 🔥 CALL NOW - Hot Intent
    FIRST_CALL = "first_call"          # 📞 First Call - ATL Decision Maker
    EMAIL_OPENED = "email_opened"      # 📧 They Read Your Email
    FOLLOW_UP = "follow_up"            # 📧 Follow-up Email
    LINKEDIN = "linkedin"              # 💼 LinkedIn Connection
    WARM_HANDOFF = "warm_handoff"      # 🤝 Warm Handoff to AE
    RE_ENRICH = "re_enrich"            # 🔄 Re-enrich - Check for New Contacts
    RESEARCH = "research"              # 🔍 Research - Find Decision Maker
    REVIEW = "review"                  # 📋 Update Status - Review & Categorize


@dataclass
class WorkQueueItem:
    """A single item in Tim's work queue with talking points."""

    # Identity
    company_id: str
    company_name: str
    rank: int

    # Action
    recommended_action: str
    action_reason: str
    action_type: WorkQueueAction

    # ICP Data
    icp_tier: str
    icp_score: float

    # Contact Info
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_linkedin: Optional[str] = None

    # Activity
    total_touches: int = 0
    days_since_activity: Optional[int] = None
    days_in_pipeline: Optional[int] = None
    opportunity_value: Optional[float] = None
    enrichment_age_days: Optional[float] = None

    # CRM Link
    close_lead_url: Optional[str] = None

    # GENERATED: Talking points for the call
    talking_points: list[str] = field(default_factory=list)

    # UI styling hints
    icon: str = "clipboard"
    color: str = "#94A3B8"


@dataclass
class WorkQueueSummary:
    """Summary statistics for the work queue."""
    total: int
    hot_intent: int
    first_calls: int
    follow_ups: int
    research: int
    by_tier: dict[str, int]


class BDRWorkQueueService:
    """
    Service for fetching and enriching BDR work queue from Supabase.

    Connects to mv_bdr_work_queue materialized view and generates
    talking points for each lead based on available data.
    """

    # OEM brands to highlight as talking points
    NOTABLE_OEMS = {
        "Carrier": "Carrier certified dealers typically have high service volume",
        "Trane": "Trane dealers often focus on commercial projects",
        "Lennox": "Lennox dealers usually have strong residential presence",
        "Daikin": "Daikin specializes in ductless/mini-split systems",
        "Schneider Electric": "Schneider dealers work on energy management systems",
        "Generac": "Generac dealers focus on backup power solutions",
        "Briggs & Stratton": "B&S dealers handle generator installations",
        "Tesla": "Tesla partners do solar + Powerwall installations",
        "SunPower": "SunPower dealers are premium solar installers",
        "Enphase": "Enphase partners specialize in microinverter systems",
    }

    # Title-based talking points
    TITLE_TALKING_POINTS = {
        "ceo": "As CEO, they're focused on growth and profitability",
        "owner": "Owner-operators care deeply about reputation and efficiency",
        "president": "Presidents often handle strategic partnerships",
        "founder": "Founders appreciate innovation and new technology",
        "vp": "VPs are typically evaluating solutions for their teams",
        "director": "Directors manage day-to-day operations and budgets",
        "manager": "Managers need tools that help their team perform",
        "operations": "Operations leaders care about efficiency and scheduling",
        "sales": "Sales leaders want tools that help close deals faster",
    }

    def __init__(self):
        """Initialize with Supabase credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase credentials not configured - will return empty queue")

    async def get_work_queue(
        self,
        limit: int = 25,
        filter_tier: Optional[str] = None,
        filter_action: Optional[str] = None,
        include_talking_points: bool = True
    ) -> tuple[list[WorkQueueItem], WorkQueueSummary]:
        """
        Fetch prioritized work queue with talking points.

        Args:
            limit: Max items to return (default 25)
            filter_tier: Optional ICP tier filter (PLATINUM, GOLD, SILVER, BRONZE)
            filter_action: Optional action type filter (hot_intent, first_call, etc.)
            include_talking_points: Generate talking points (default True)

        Returns:
            Tuple of (list of WorkQueueItems, WorkQueueSummary)
        """
        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase not configured - returning empty queue")
            return [], WorkQueueSummary(
                total=0, hot_intent=0, first_calls=0,
                follow_ups=0, research=0, by_tier={}
            )

        try:
            # Fetch from materialized view
            rows = await self._fetch_from_supabase(limit, filter_tier)

            if not rows:
                logger.info("No work queue items found")
                return [], WorkQueueSummary(
                    total=0, hot_intent=0, first_calls=0,
                    follow_ups=0, research=0, by_tier={}
                )

            # Transform to WorkQueueItems with talking points
            items = []
            for row in rows:
                item = self._transform_row(row)

                # Apply action filter EARLY to skip expensive operations
                if filter_action and item.action_type.value != filter_action:
                    continue

                if include_talking_points:
                    item.talking_points = self._generate_talking_points(row)

                items.append(item)

            # Calculate summary
            summary = self._calculate_summary(items)

            logger.info(
                f"Work queue fetched: {len(items)} items "
                f"(hot: {summary.hot_intent}, first_call: {summary.first_calls})"
            )

            return items, summary

        except Exception as e:
            logger.error(f"Error fetching work queue: {e}")
            return [], WorkQueueSummary(
                total=0, hot_intent=0, first_calls=0,
                follow_ups=0, research=0, by_tier={}
            )

    async def _fetch_from_supabase(
        self,
        limit: int,
        filter_tier: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch work queue from Supabase REST API."""
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

        params = {
            "select": "*",
            "order": "rank.asc",
            "limit": str(limit)
        }

        # Add tier filter if specified
        if filter_tier:
            params["icp_tier"] = f"eq.{filter_tier}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.supabase_url}/rest/v1/mv_bdr_work_queue",
                headers=headers,
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Supabase error: {response.status_code} - {response.text}")
                return []

            return response.json()

    def _transform_row(self, row: dict[str, Any]) -> WorkQueueItem:
        """Transform Supabase row to WorkQueueItem."""
        action_text = row.get("recommended_action", "")
        action_type = self._parse_action_type(action_text)
        icon, color = self._get_action_styling(action_type)

        return WorkQueueItem(
            company_id=str(row.get("company_id", "")),
            company_name=row.get("company_name", ""),
            rank=row.get("rank", 0),
            recommended_action=action_text,
            action_reason=row.get("action_reason", ""),
            action_type=action_type,
            icp_tier=row.get("icp_tier", ""),
            icp_score=float(row.get("icp_score", 0)),
            contact_name=row.get("best_contact_name"),
            contact_title=row.get("best_contact_title"),
            contact_phone=row.get("best_contact_phone"),
            contact_email=row.get("best_contact_email"),
            contact_linkedin=row.get("best_contact_linkedin"),
            total_touches=row.get("total_touches", 0),
            days_since_activity=row.get("days_since_activity"),
            days_in_pipeline=row.get("days_in_pipeline"),
            opportunity_value=float(row.get("opportunity_value")) if row.get("opportunity_value") else None,
            enrichment_age_days=float(row.get("enrichment_age_days")) if row.get("enrichment_age_days") else None,
            close_lead_url=row.get("close_lead_url"),
            icon=icon,
            color=color
        )

    def _parse_action_type(self, action_text: str) -> WorkQueueAction:
        """Parse action type from recommended_action text."""
        action_lower = action_text.lower()

        if "call now" in action_lower or "hot intent" in action_lower:
            return WorkQueueAction.HOT_INTENT
        elif "first call" in action_lower:
            return WorkQueueAction.FIRST_CALL
        elif "read" in action_lower and "email" in action_lower:
            return WorkQueueAction.EMAIL_OPENED
        elif "follow-up" in action_lower or "follow up" in action_lower:
            return WorkQueueAction.FOLLOW_UP
        elif "linkedin" in action_lower:
            return WorkQueueAction.LINKEDIN
        elif "handoff" in action_lower or "hand off" in action_lower:
            return WorkQueueAction.WARM_HANDOFF
        elif "re-enrich" in action_lower or "reenrich" in action_lower:
            return WorkQueueAction.RE_ENRICH
        elif "research" in action_lower:
            return WorkQueueAction.RESEARCH
        else:
            return WorkQueueAction.REVIEW

    def _get_action_styling(self, action_type: WorkQueueAction) -> tuple[str, str]:
        """Get icon and color for action type."""
        styling = {
            WorkQueueAction.HOT_INTENT: ("flame", "#EF4444"),
            WorkQueueAction.FIRST_CALL: ("phone", "#3B82F6"),
            WorkQueueAction.EMAIL_OPENED: ("mail-open", "#10B981"),
            WorkQueueAction.FOLLOW_UP: ("mail", "#8B5CF6"),
            WorkQueueAction.LINKEDIN: ("linkedin", "#0077B5"),
            WorkQueueAction.WARM_HANDOFF: ("user-check", "#F59E0B"),
            WorkQueueAction.RE_ENRICH: ("refresh-cw", "#6366F1"),
            WorkQueueAction.RESEARCH: ("search", "#64748B"),
            WorkQueueAction.REVIEW: ("clipboard", "#94A3B8"),
        }
        return styling.get(action_type, ("clipboard", "#94A3B8"))

    def _generate_talking_points(self, row: dict[str, Any]) -> list[str]:
        """
        Generate talking points for a lead based on available data.

        This is where the magic happens - we create personalized openers
        and conversation starters based on:
        - ICP tier and score
        - Contact title
        - Activity history
        - Enrichment age

        Note: This is a synchronous function (no async I/O needed).
        """
        points = []

        # 1. ICP Tier talking point
        tier = row.get("icp_tier", "")
        score = row.get("icp_score", 0)
        if tier == "PLATINUM":
            points.append(f"🏆 PLATINUM lead (Score: {score}) - our ideal customer profile")
        elif tier == "GOLD":
            points.append(f"⭐ GOLD lead (Score: {score}) - strong ICP fit")

        # 2. Contact title talking point
        title = row.get("best_contact_title", "") or ""
        title_lower = title.lower()
        for keyword, point in self.TITLE_TALKING_POINTS.items():
            if keyword in title_lower:
                points.append(f"👤 {title}: {point}")
                break

        # 3. Phone availability (generic - phone_type not in view schema)
        if row.get("best_contact_phone"):
            points.append("📞 Phone number available for outreach")

        # 4. Activity-based talking points
        days_since = row.get("days_since_activity")
        total_touches = row.get("total_touches", 0)

        if days_since is not None and days_since > 14:
            points.append(f"⏰ No contact in {days_since} days - good time to reconnect")
        elif total_touches == 0:
            points.append("🆕 First outreach - introduce Coperniq value proposition")
        elif total_touches >= 3:
            points.append(f"🔄 {total_touches} previous touches - they know who we are")

        # 5. Opportunity value
        opp_value = row.get("opportunity_value")
        if opp_value and opp_value > 50000:
            points.append(f"💰 Opportunity value: ${opp_value:,.0f} - high-value prospect")

        # 6. Enrichment age (stale data indicator)
        enrich_age = row.get("enrichment_age_days")
        if enrich_age and enrich_age > 30:
            points.append(f"🔄 Data is {int(enrich_age)} days old - may need re-enrichment")

        # 7. LinkedIn availability for research
        if row.get("best_contact_linkedin"):
            points.append("💼 LinkedIn profile available - research before calling")

        # Ensure we have at least one talking point
        if not points:
            points.append("📋 Review company profile before call")

        return points[:5]  # Cap at 5 talking points

    def _calculate_summary(self, items: list[WorkQueueItem]) -> WorkQueueSummary:
        """Calculate summary statistics for the work queue."""
        by_tier: dict[str, int] = {}

        hot_intent = 0
        first_calls = 0
        follow_ups = 0
        research = 0

        for item in items:
            # Count by tier
            by_tier[item.icp_tier] = by_tier.get(item.icp_tier, 0) + 1

            # Count by action type
            if item.action_type == WorkQueueAction.HOT_INTENT:
                hot_intent += 1
            elif item.action_type == WorkQueueAction.FIRST_CALL:
                first_calls += 1
            elif item.action_type in (WorkQueueAction.FOLLOW_UP, WorkQueueAction.EMAIL_OPENED):
                follow_ups += 1
            elif item.action_type in (WorkQueueAction.RESEARCH, WorkQueueAction.RE_ENRICH):
                research += 1

        return WorkQueueSummary(
            total=len(items),
            hot_intent=hot_intent,
            first_calls=first_calls,
            follow_ups=follow_ups,
            research=research,
            by_tier=by_tier
        )

    async def get_talking_points_for_company(
        self,
        company_id: str
    ) -> list[str]:
        """
        Get talking points for a specific company.

        Useful when viewing a single lead and wanting updated talking points.

        Args:
            company_id: The company_id from dim_companies

        Returns:
            List of talking point strings
        """
        if not self.supabase_url or not self.supabase_key:
            return ["Supabase not configured"]

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/mv_bdr_work_queue",
                    headers=headers,
                    params={
                        "select": "*",
                        "company_id": f"eq.{company_id}",
                        "limit": "1"
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Supabase error: {response.status_code}")
                    return ["Error fetching company data"]

                rows = response.json()
                if not rows:
                    return ["Company not found in work queue"]

                return self._generate_talking_points(rows[0])

        except Exception as e:
            logger.error(f"Error getting talking points: {e}")
            return [f"Error: {str(e)}"]


# Factory function for dependency injection
async def get_bdr_work_queue_service() -> BDRWorkQueueService:
    """
    Get BDRWorkQueueService instance.

    For FastAPI dependency injection:
        service: BDRWorkQueueService = Depends(get_bdr_work_queue_service)
    """
    return BDRWorkQueueService()
