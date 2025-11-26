"""
Lead Audit Service - Tracks lead lifecycle for GTM agent context.

Provides:
- Event logging at each pipeline stage
- Query methods for GTM agents to get lead history
- Duplicate prevention via recently-processed checks
- Session summaries for pipeline run analysis

Usage:
    service = LeadAuditService(db_session)

    # Log an event
    await service.log_event(
        session_id="session_123",
        company_name="ABC Corp",
        event_type=LeadAuditEventType.LEAD_QUALIFIED,
        stage="qualification",
        decision_data={"score": 85, "tier": "gold"}
    )

    # Query history for GTM agents
    history = await service.get_lead_history(company_name="ABC Corp")
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_audit import (
    LeadAuditLog,
    LeadAuditEventType,
    LeadAuditStage
)

logger = logging.getLogger(__name__)


class LeadAuditService:
    """
    Service for managing lead audit trail.

    Provides logging and querying capabilities for the lead lifecycle,
    enabling GTM agents to understand context about each lead.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize audit service with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    # =========================================================================
    # Event Logging Methods
    # =========================================================================

    async def log_event(
        self,
        session_id: str,
        company_name: str,
        event_type: LeadAuditEventType,
        stage: str,
        decision_data: Dict[str, Any],
        lead_id: Optional[UUID] = None,
        source_file: Optional[str] = None,
        source_row: Optional[int] = None,
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        created_by: str = "system"
    ) -> LeadAuditLog:
        """
        Log an audit event for a lead.

        Args:
            session_id: Pipeline execution session ID
            company_name: Company name (denormalized for querying)
            event_type: Type of event (see LeadAuditEventType)
            stage: Pipeline stage (import, qualification, etc.)
            decision_data: JSON data with decision context
            lead_id: Optional reference to leads table
            source_file: CSV filename if applicable
            source_row: Row number in CSV if applicable
            latency_ms: Processing time for this stage
            cost_usd: API costs for this operation
            created_by: User or agent identifier

        Returns:
            Created LeadAuditLog record
        """
        try:
            audit_log = LeadAuditLog(
                id=uuid4(),
                lead_id=lead_id,
                company_name=company_name,
                session_id=session_id,
                event_type=event_type.value if isinstance(event_type, LeadAuditEventType) else event_type,
                stage=stage,
                decision_data=decision_data,
                source_file=source_file,
                source_row=source_row,
                created_by=created_by,
                latency_ms=latency_ms,
                cost_usd=Decimal(str(cost_usd)) if cost_usd else None
            )

            self.db.add(audit_log)
            await self.db.commit()
            await self.db.refresh(audit_log)

            logger.debug(
                f"Audit logged: {event_type} for '{company_name}' "
                f"in session {session_id}"
            )

            return audit_log

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            await self.db.rollback()
            raise

    async def log_import(
        self,
        session_id: str,
        company_name: str,
        source_file: str,
        source_row: int,
        decision_data: Dict[str, Any],
        created_by: str = "system"
    ) -> LeadAuditLog:
        """Convenience method for logging import events."""
        return await self.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_IMPORTED,
            stage=LeadAuditStage.IMPORT.value,
            decision_data=decision_data,
            source_file=source_file,
            source_row=source_row,
            created_by=created_by
        )

    async def log_qualification(
        self,
        session_id: str,
        company_name: str,
        score: float,
        tier: str,
        is_atl: bool,
        decision_data: Dict[str, Any],
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        created_by: str = "system"
    ) -> LeadAuditLog:
        """Convenience method for logging qualification events."""
        data = {
            "score": score,
            "tier": tier,
            "is_atl": is_atl,
            **decision_data
        }
        return await self.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_QUALIFIED,
            stage=LeadAuditStage.QUALIFICATION.value,
            decision_data=data,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            created_by=created_by
        )

    async def log_enrichment(
        self,
        session_id: str,
        company_name: str,
        sources_tried: List[str],
        sources_succeeded: List[str],
        contacts_found: int,
        decision_data: Dict[str, Any],
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        created_by: str = "system"
    ) -> LeadAuditLog:
        """Convenience method for logging enrichment events."""
        data = {
            "sources_tried": sources_tried,
            "sources_succeeded": sources_succeeded,
            "contacts_found": contacts_found,
            **decision_data
        }
        return await self.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_ENRICHED,
            stage=LeadAuditStage.ENRICHMENT.value,
            decision_data=data,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            created_by=created_by
        )

    async def log_dedup_decision(
        self,
        session_id: str,
        company_name: str,
        recommendation: str,
        company_confidence: float,
        contact_confidence: Optional[float],
        decision_data: Dict[str, Any],
        created_by: str = "system"
    ) -> LeadAuditLog:
        """
        Log a deduplication decision.

        Args:
            recommendation: One of: create_new, add_contact, skip_duplicate, update_existing
            company_confidence: Fuzzy match confidence (0-100)
            contact_confidence: Email match confidence (0-100)
        """
        # Map recommendation to event type
        event_map = {
            "create_new": LeadAuditEventType.DEDUP_CREATE_NEW,
            "add_contact_to_existing": LeadAuditEventType.DEDUP_ADD_CONTACT,
            "add_contact": LeadAuditEventType.DEDUP_ADD_CONTACT,
            "skip_duplicate": LeadAuditEventType.DEDUP_SKIP_DUPLICATE,
            "update_existing_contact": LeadAuditEventType.DEDUP_UPDATE_EXISTING,
            "update_existing": LeadAuditEventType.DEDUP_UPDATE_EXISTING
        }
        event_type = event_map.get(recommendation, LeadAuditEventType.DEDUP_CREATE_NEW)

        data = {
            "recommendation": recommendation,
            "company_confidence": company_confidence,
            "contact_confidence": contact_confidence,
            **decision_data
        }

        return await self.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=event_type,
            stage=LeadAuditStage.DEDUPLICATION.value,
            decision_data=data,
            created_by=created_by
        )

    async def log_export(
        self,
        session_id: str,
        company_name: str,
        output_file: str,
        row_number: int,
        decision_data: Dict[str, Any],
        created_by: str = "system"
    ) -> LeadAuditLog:
        """Convenience method for logging export events."""
        data = {
            "output_file": output_file,
            "row_number": row_number,
            **decision_data
        }
        return await self.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=LeadAuditEventType.LEAD_EXPORTED,
            stage=LeadAuditStage.EXPORT.value,
            decision_data=data,
            created_by=created_by
        )

    # =========================================================================
    # Query Methods (for GTM Agents)
    # =========================================================================

    async def get_lead_history(
        self,
        company_name: Optional[str] = None,
        lead_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[LeadAuditLog]:
        """
        Get full audit history for a lead.

        Used by GTM agents to understand what happened to a company.

        Args:
            company_name: Company name to search
            lead_id: Lead ID to search
            limit: Max records to return

        Returns:
            List of audit records ordered by created_at DESC
        """
        query = select(LeadAuditLog)

        if company_name:
            query = query.where(LeadAuditLog.company_name == company_name)
        elif lead_id:
            query = query.where(LeadAuditLog.lead_id == lead_id)
        else:
            raise ValueError("Must provide company_name or lead_id")

        query = query.order_by(LeadAuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_session_summary(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get summary statistics for a pipeline session.

        Args:
            session_id: Pipeline execution session ID

        Returns:
            {
                "session_id": "...",
                "total_events": 150,
                "companies_processed": 30,
                "by_event_type": {"lead_imported": 30, "lead_qualified": 28, ...},
                "by_stage": {"import": 30, "qualification": 28, ...},
                "total_cost_usd": 0.45,
                "total_latency_ms": 125000,
                "first_event": "2025-11-26T10:00:00",
                "last_event": "2025-11-26T10:15:00"
            }
        """
        # Get all events for session
        query = select(LeadAuditLog).where(
            LeadAuditLog.session_id == session_id
        )
        result = await self.db.execute(query)
        events = list(result.scalars().all())

        if not events:
            return {
                "session_id": session_id,
                "total_events": 0,
                "companies_processed": 0,
                "by_event_type": {},
                "by_stage": {},
                "total_cost_usd": 0,
                "total_latency_ms": 0,
                "first_event": None,
                "last_event": None
            }

        # Calculate stats
        by_event_type: Dict[str, int] = {}
        by_stage: Dict[str, int] = {}
        companies = set()
        total_cost = Decimal("0")
        total_latency = 0

        for event in events:
            # Count by event type
            by_event_type[event.event_type] = by_event_type.get(event.event_type, 0) + 1

            # Count by stage
            by_stage[event.stage] = by_stage.get(event.stage, 0) + 1

            # Track unique companies
            companies.add(event.company_name)

            # Sum costs
            if event.cost_usd:
                total_cost += event.cost_usd

            # Sum latency
            if event.latency_ms:
                total_latency += event.latency_ms

        # Get time range
        sorted_events = sorted(events, key=lambda x: x.created_at)

        return {
            "session_id": session_id,
            "total_events": len(events),
            "companies_processed": len(companies),
            "by_event_type": by_event_type,
            "by_stage": by_stage,
            "total_cost_usd": float(total_cost),
            "total_latency_ms": total_latency,
            "first_event": sorted_events[0].created_at.isoformat(),
            "last_event": sorted_events[-1].created_at.isoformat()
        }

    async def get_dedup_decisions(
        self,
        company_name: str
    ) -> List[LeadAuditLog]:
        """
        Get all deduplication decisions for a company.

        Used by GTM agents to understand why a company was skipped/merged.

        Args:
            company_name: Company name to search

        Returns:
            List of dedup audit records
        """
        query = select(LeadAuditLog).where(
            and_(
                LeadAuditLog.company_name == company_name,
                LeadAuditLog.event_type.like("dedup_%")
            )
        ).order_by(LeadAuditLog.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def check_recently_processed(
        self,
        company_name: str,
        hours: int = 24
    ) -> bool:
        """
        Check if a company was processed recently.

        Used to prevent duplicate processing within a time window.

        Args:
            company_name: Company name to check
            hours: Time window in hours (default 24)

        Returns:
            True if processed within the time window
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = select(func.count()).select_from(LeadAuditLog).where(
            and_(
                LeadAuditLog.company_name == company_name,
                LeadAuditLog.created_at >= cutoff
            )
        )

        result = await self.db.execute(query)
        count = result.scalar()

        return count > 0

    async def get_recent_activity(
        self,
        hours: int = 24,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[LeadAuditLog]:
        """
        Get recent audit activity.

        Used for monitoring dashboards and GTM agent awareness.

        Args:
            hours: Time window in hours
            event_types: Optional filter by event types
            limit: Max records to return

        Returns:
            List of recent audit records
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = select(LeadAuditLog).where(
            LeadAuditLog.created_at >= cutoff
        )

        if event_types:
            query = query.where(LeadAuditLog.event_type.in_(event_types))

        query = query.order_by(LeadAuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_by_decision_data(
        self,
        key: str,
        value: Any,
        limit: int = 100
    ) -> List[LeadAuditLog]:
        """
        Search audit logs by decision_data JSON field.

        Example: Find all leads with score > 80
            await service.search_by_decision_data("score", {"$gt": 80})

        Args:
            key: JSON key to search
            value: Value to match
            limit: Max records

        Returns:
            Matching audit records
        """
        # Use JSONB containment for exact match
        query = select(LeadAuditLog).where(
            LeadAuditLog.decision_data[key].astext == str(value)
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())


# Singleton instance for non-DI usage
_audit_service: Optional[LeadAuditService] = None


async def get_lead_audit_service(db: AsyncSession) -> LeadAuditService:
    """
    Get or create LeadAuditService instance.

    For FastAPI dependency injection:
        audit_service: LeadAuditService = Depends(get_lead_audit_service)
    """
    return LeadAuditService(db)
