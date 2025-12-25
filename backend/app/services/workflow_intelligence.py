"""
Close CRM Workflow Intelligence Service

Aggregates analytics for Close CRM sequences since Close doesn't provide
built-in analytics endpoints. Provides comprehensive reporting on:
- Enrollment counts by sequence
- Status breakdown (active, paused, finished, stopped, failed)
- ICP tier breakdown (PLATINUM, GOLD, SILVER, BRONZE)
- Industry breakdown (Energy, MEP, Other)
- ATL vs BTL contact breakdown
- Reply rates and engagement metrics

Usage:
    service = WorkflowIntelligenceService()

    # Get all sequences for a user
    sequences = await service.collect_all_sequences(user_email="tim@coperniq.io")

    # Get subscriptions for a specific sequence
    subs = await service.collect_subscriptions_for_sequence(sequence_id)

    # Generate comprehensive workflow report
    report = await service.generate_workflow_report(sequence_id)

    # Generate report for all user sequences
    all_reports = await service.generate_all_workflows_report(user_email)
"""

import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from supabase import create_client, Client
from app.services.crm.close_sequences import CloseSequencesClient

logger = logging.getLogger(__name__)


@dataclass
class EngagementMetrics:
    """Engagement metrics for a workflow"""
    total_emails_sent: int = 0
    total_replies: int = 0
    reply_rate: float = 0.0
    avg_steps_completed: float = 0.0


@dataclass
class DateCount:
    """Date-based count for timeline data"""
    date: str
    count: int


@dataclass
class WorkflowReport:
    """Comprehensive workflow analytics report"""
    sequence_id: str
    sequence_name: str
    total_enrolled: int
    status_breakdown: Dict[str, int] = field(default_factory=dict)
    icp_breakdown: Dict[str, int] = field(default_factory=dict)
    industry_breakdown: Dict[str, int] = field(default_factory=dict)
    contact_breakdown: Dict[str, int] = field(default_factory=dict)
    engagement: EngagementMetrics = field(default_factory=EngagementMetrics)
    enrolled_over_time: List[DateCount] = field(default_factory=list)
    replies_over_time: List[DateCount] = field(default_factory=list)


class WorkflowIntelligenceService:
    """Service for aggregating Close CRM sequence analytics"""

    def __init__(self):
        """Initialize Workflow Intelligence Service"""
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Initialize Close CRM client
        self.close_sequences = CloseSequencesClient()

        logger.info("WorkflowIntelligenceService initialized")

    async def collect_all_sequences(self, user_email: Optional[str] = None) -> List[Dict]:
        """
        Query Close API for all sequences (optionally filtered by user)

        Args:
            user_email: Filter sequences by user email (None = all sequences)

        Returns:
            List of sequences with metadata
        """
        logger.info(f"Collecting all sequences (user={user_email or 'ALL'})")

        # This would need to be implemented in CloseSequencesClient
        # For now, return placeholder
        # In production, would call: GET /api/v1/sequence/

        # Placeholder: Return known sequences from Dec 29 campaign
        sequences = [
            {
                "id": "seq_469XPP98mPXSR2wh5cX9y6",
                "name": "ICP-Energy-Multitrade",
                "created_at": "2024-11-15",
                "status": "active"
            },
            {
                "id": "seq_0FHFD0OQtDAOS8x40MIANW",
                "name": "Solar-Pivot-2026",
                "created_at": "2024-11-20",
                "status": "active"
            }
        ]

        logger.info(f"Found {len(sequences)} sequences")
        return sequences

    async def collect_subscriptions_for_sequence(self, sequence_id: str) -> List[Dict]:
        """
        Query Close API for all subscriptions in a sequence

        Args:
            sequence_id: Close sequence ID (e.g., seq_469XPP98mPXSR2wh5cX9y6)

        Returns:
            List of subscriptions with contact and status info
        """
        logger.info(f"Collecting subscriptions for sequence {sequence_id}")

        # Use CloseSequencesClient to get subscriptions
        subscriptions = await self.close_sequences.list_active_subscriptions(sequence_id)

        logger.info(f"Found {len(subscriptions)} subscriptions in {sequence_id}")
        return subscriptions

    async def enrich_with_supabase_data(
        self,
        subscriptions: List[Dict]
    ) -> List[Dict]:
        """
        Add ICP tier, ATL/BTL, industry from Supabase

        Args:
            subscriptions: List of Close sequence subscriptions

        Returns:
            List of enriched subscriptions with Supabase data
        """
        logger.info(f"Enriching {len(subscriptions)} subscriptions with Supabase data")

        enriched = []

        # Extract contact IDs
        contact_ids = [sub.get("contact_id") for sub in subscriptions if sub.get("contact_id")]

        if not contact_ids:
            logger.warning("No contact IDs found in subscriptions")
            return subscriptions

        # Query Supabase for contacts (batch query)
        # Join on close_contact_id → contact_id → company_id
        response = self.supabase.table("dim_contacts").select(
            "contact_id, close_contact_id, company_id, is_atl, "
            "dim_companies(company_id, company_name, icp_tier, industry, domain)"
        ).in_("close_contact_id", contact_ids).execute()

        contacts_map = {c["close_contact_id"]: c for c in response.data}

        # Enrich subscriptions
        for sub in subscriptions:
            contact_id = sub.get("contact_id")
            contact_data = contacts_map.get(contact_id, {})

            enriched_sub = {
                **sub,
                "supabase_contact_id": contact_data.get("contact_id"),
                "company_id": contact_data.get("company_id"),
                "is_atl": contact_data.get("is_atl"),
            }

            # Add company data if available
            company_data = contact_data.get("dim_companies", {})
            if isinstance(company_data, dict):
                enriched_sub.update({
                    "company_name": company_data.get("company_name"),
                    "icp_tier": company_data.get("icp_tier"),
                    "industry": company_data.get("industry"),
                    "domain": company_data.get("domain")
                })

            enriched.append(enriched_sub)

        logger.info(f"Enriched {len(enriched)} subscriptions")
        return enriched

    async def generate_workflow_report(
        self,
        sequence_id: str,
        sequence_name: Optional[str] = None
    ) -> WorkflowReport:
        """
        Generate comprehensive analytics for a workflow

        Args:
            sequence_id: Close sequence ID
            sequence_name: Optional sequence name (will be looked up if not provided)

        Returns:
            WorkflowReport with all analytics
        """
        logger.info(f"Generating workflow report for {sequence_id}")

        # Collect subscriptions
        subscriptions = await self.collect_subscriptions_for_sequence(sequence_id)

        # Enrich with Supabase data
        enriched_subs = await self.enrich_with_supabase_data(subscriptions)

        # Calculate status breakdown
        status_breakdown = {}
        for sub in subscriptions:
            status = sub.get("status", "unknown")
            status_breakdown[status] = status_breakdown.get(status, 0) + 1

        # Calculate ICP breakdown
        icp_breakdown = {}
        for sub in enriched_subs:
            tier = sub.get("icp_tier", "UNKNOWN")
            icp_breakdown[tier] = icp_breakdown.get(tier, 0) + 1

        # Calculate industry breakdown
        industry_breakdown = {}
        for sub in enriched_subs:
            industry = sub.get("industry", "Other")
            industry_breakdown[industry] = industry_breakdown.get(industry, 0) + 1

        # Calculate ATL vs BTL breakdown
        contact_breakdown = {
            "atl_count": sum(1 for s in enriched_subs if s.get("is_atl") is True),
            "btl_count": sum(1 for s in enriched_subs if s.get("is_atl") is False),
            "unknown_count": sum(1 for s in enriched_subs if s.get("is_atl") is None)
        }

        # Calculate engagement metrics
        engagement = await self._calculate_engagement_metrics(sequence_id, enriched_subs)

        # Build report
        report = WorkflowReport(
            sequence_id=sequence_id,
            sequence_name=sequence_name or sequence_id,
            total_enrolled=len(subscriptions),
            status_breakdown=status_breakdown,
            icp_breakdown=icp_breakdown,
            industry_breakdown=industry_breakdown,
            contact_breakdown=contact_breakdown,
            engagement=engagement
        )

        logger.info(f"Generated report for {sequence_id}: {len(subscriptions)} enrolled")
        return report

    async def generate_all_workflows_report(
        self,
        user_email: Optional[str] = None
    ) -> List[WorkflowReport]:
        """
        Generate reports for all workflows (optionally filtered by user)

        Args:
            user_email: Filter by user email (None = all workflows)

        Returns:
            List of WorkflowReport objects
        """
        logger.info(f"Generating reports for all workflows (user={user_email or 'ALL'})")

        # Get all sequences
        sequences = await self.collect_all_sequences(user_email)

        # Generate report for each sequence
        reports = []
        for seq in sequences:
            report = await self.generate_workflow_report(
                sequence_id=seq["id"],
                sequence_name=seq.get("name")
            )
            reports.append(report)

        logger.info(f"Generated {len(reports)} workflow reports")
        return reports

    async def _calculate_engagement_metrics(
        self,
        sequence_id: str,
        enriched_subs: List[Dict]
    ) -> EngagementMetrics:
        """
        Calculate engagement metrics from fact_close_activities

        Args:
            sequence_id: Close sequence ID
            enriched_subs: Enriched subscription data

        Returns:
            EngagementMetrics with email and reply stats
        """
        # Query fact_close_activities for sequence emails
        response = self.supabase.table("fact_close_activities").select(
            "activity_id, sequence_id, activity_type, is_reply"
        ).eq("sequence_id", sequence_id).eq("is_sequence_activity", True).execute()

        activities = response.data

        # Count emails sent
        total_emails_sent = sum(
            1 for a in activities
            if a.get("activity_type") == "email" and not a.get("is_reply")
        )

        # Count replies
        total_replies = sum(
            1 for a in activities
            if a.get("is_reply") is True
        )

        # Calculate reply rate
        reply_rate = (total_replies / total_emails_sent * 100) if total_emails_sent > 0 else 0.0

        # Calculate avg steps completed
        # This would require step progression data - placeholder for now
        avg_steps_completed = 0.0

        return EngagementMetrics(
            total_emails_sent=total_emails_sent,
            total_replies=total_replies,
            reply_rate=reply_rate,
            avg_steps_completed=avg_steps_completed
        )

    def to_dict(self, report: WorkflowReport) -> Dict:
        """Convert WorkflowReport to dictionary for JSON export"""
        return {
            "sequence_id": report.sequence_id,
            "sequence_name": report.sequence_name,
            "total_enrolled": report.total_enrolled,
            "status_breakdown": report.status_breakdown,
            "icp_breakdown": report.icp_breakdown,
            "industry_breakdown": report.industry_breakdown,
            "contact_breakdown": report.contact_breakdown,
            "engagement": {
                "total_emails_sent": report.engagement.total_emails_sent,
                "total_replies": report.engagement.total_replies,
                "reply_rate": report.engagement.reply_rate,
                "avg_steps_completed": report.engagement.avg_steps_completed
            }
        }
