"""Audit logging for pipeline events."""
import logging
from typing import Dict, Any, Optional

from app.models.lead_audit import LeadAuditEventType

logger = logging.getLogger(__name__)


async def log_audit(
    audit_service: Optional[Any],
    session_id: str,
    company_name: str,
    event_type: LeadAuditEventType,
    stage: str,
    decision_data: Dict[str, Any],
    source_file: Optional[str] = None,
    source_row: Optional[int] = None,
    latency_ms: Optional[int] = None,
    cost_usd: Optional[float] = None
) -> None:
    """
    Log audit event (non-blocking - failures don't break pipeline).

    Used to track lead lifecycle for GTM agent context.
    """
    if not audit_service:
        return

    try:
        await audit_service.log_event(
            session_id=session_id,
            company_name=company_name,
            event_type=event_type,
            stage=stage,
            decision_data=decision_data,
            source_file=source_file,
            source_row=source_row,
            latency_ms=latency_ms,
            cost_usd=cost_usd
        )
    except Exception as e:
        logger.warning(f"Audit logging failed (non-blocking): {e}")
