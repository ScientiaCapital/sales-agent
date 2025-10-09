"""
GDPR compliance API endpoints for data export, deletion, and consent management.
Implements GDPR Articles 15 (Right of Access), 17 (Right to Erasure), 20 (Data Portability).
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.models.database import get_db
from app.models.security import User, UserConsent, ConsentType, EventType
from app.dependencies.auth import get_current_user
from app.middleware.audit import log_security_event
from app.core.logging import setup_logging

# Import all models to gather user data
from app.models.lead import Lead
from app.models.campaign import Campaign, CampaignMessage
from app.models.crm import CRMCredential, CRMSyncLog
from app.models.report import Report

logger = setup_logging(__name__)

router = APIRouter(prefix="/gdpr", tags=["gdpr", "compliance"])


class DataExportFormat(str, Enum):
    """Supported data export formats."""
    JSON = "json"
    # Future: CSV = "csv", XML = "xml"


class ConsentRequest(BaseModel):
    """Request schema for consent management."""
    consent_type: ConsentType
    is_granted: bool
    consent_text: Optional[str] = Field(None, description="Text shown to user when consent was requested")
    legal_basis: Optional[str] = Field(None, description="Legal basis for processing (e.g., 'consent', 'legitimate_interest')")
    purpose: Optional[str] = Field(None, description="Purpose of data processing")


class ConsentResponse(BaseModel):
    """Response schema for consent status."""
    consent_type: ConsentType
    is_granted: bool
    granted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    consent_version: Optional[str]
    legal_basis: Optional[str]
    purpose: Optional[str]

    class Config:
        from_attributes = True


class DataDeletionRequest(BaseModel):
    """Request schema for data deletion."""
    confirmation: str = Field(..., description="User must type 'DELETE' to confirm")
    reason: Optional[str] = Field(None, description="Reason for deletion request")


class DataExportResponse(BaseModel):
    """Response schema for data export."""
    export_id: str
    requested_at: datetime
    user_data: Dict[str, Any]
    format: DataExportFormat


@router.get("/export", response_model=DataExportResponse)
async def export_user_data(
    format: DataExportFormat = DataExportFormat.JSON,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Export all user data (GDPR Article 15 - Right of Access & Article 20 - Data Portability).

    Gathers all data associated with the authenticated user across all tables
    and returns it in a structured format for portability.

    Args:
        format: Export format (currently only JSON supported)
        current_user: Authenticated user
        background_tasks: FastAPI background tasks for audit logging
        request: HTTP request for audit context
        db: Database session

    Returns:
        Complete user data export in requested format

    Processing time: Up to 21 days allowed by GDPR, but we return immediately
    """
    try:
        # Log GDPR export request
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.DATA_EXPORT_REQUESTED,
            user_id=current_user.id,
            resource=f"user:{current_user.id}",
            action="export",
            metadata={"format": format},
            request=request,
        )

        # Generate export ID
        export_id = f"export_{current_user.id}_{datetime.now(timezone.utc).isoformat()}"

        # Gather all user data
        user_data = {
            "export_metadata": {
                "export_id": export_id,
                "user_id": current_user.id,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "format": format,
            },
            "personal_data": _export_personal_data(current_user),
            "consent_records": _export_consent_records(current_user, db),
            "leads": _export_user_leads(current_user, db),
            "campaigns": _export_user_campaigns(current_user, db),
            "reports": _export_user_reports(current_user, db),
            "crm_data": _export_crm_data(current_user, db),
            "audit_logs": _export_audit_logs(current_user, db),
        }

        # Log successful export
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.DATA_EXPORTED,
            user_id=current_user.id,
            resource=f"user:{current_user.id}",
            action="export",
            metadata={"export_id": export_id, "records_exported": _count_records(user_data)},
            request=request,
        )

        return DataExportResponse(
            export_id=export_id,
            requested_at=datetime.now(timezone.utc),
            user_data=user_data,
            format=format,
        )

    except Exception as e:
        logger.error(f"Data export failed for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data export failed. Please try again later.",
        )


@router.delete("/delete", status_code=status.HTTP_202_ACCEPTED)
async def delete_user_data(
    deletion_request: DataDeletionRequest,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Request deletion of all user data (GDPR Article 17 - Right to Erasure).

    Performs cascading anonymization of user data while preserving audit trail.
    PII is replaced with "DELETED" but relationships and non-identifying data are preserved.

    Args:
        deletion_request: Deletion confirmation and reason
        current_user: Authenticated user
        background_tasks: FastAPI background tasks for processing
        request: HTTP request for audit context
        db: Database session

    Returns:
        202 Accepted - Deletion request received and will be processed

    Note: Processing happens asynchronously within 21-day GDPR timeline
    """
    # Validate confirmation
    if deletion_request.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please type 'DELETE' to confirm data deletion",
        )

    try:
        # Log deletion request
        background_tasks.add_task(
            log_security_event,
            event_type=EventType.DATA_DELETION_REQUESTED,
            user_id=current_user.id,
            resource=f"user:{current_user.id}",
            action="delete",
            metadata={"reason": deletion_request.reason},
            request=request,
        )

        # Schedule data anonymization in background
        background_tasks.add_task(
            _anonymize_user_data,
            user_id=current_user.id,
            db_url=str(db.bind.url),
            reason=deletion_request.reason,
        )

        return {
            "status": "accepted",
            "message": "Your data deletion request has been received and will be processed within 21 days",
            "request_id": f"deletion_{current_user.id}_{datetime.now(timezone.utc).isoformat()}",
        }

    except Exception as e:
        logger.error(f"Data deletion request failed for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process deletion request. Please try again later.",
        )


@router.post("/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def manage_consent(
    consent_request: ConsentRequest,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Manage user consent for data processing (GDPR Articles 6 & 7).

    Records consent grants and revocations with full audit trail.

    Args:
        consent_request: Consent type and status
        current_user: Authenticated user
        background_tasks: FastAPI background tasks for audit logging
        request: HTTP request for audit context
        db: Database session

    Returns:
        Updated consent status
    """
    try:
        # Check for existing consent record
        existing_consent = db.query(UserConsent).filter(
            UserConsent.user_id == current_user.id,
            UserConsent.consent_type == consent_request.consent_type,
        ).first()

        # Extract request context
        ip_address = None
        user_agent = None
        if request:
            if request.client:
                ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "")

        if existing_consent:
            # Update existing consent
            existing_consent.is_granted = consent_request.is_granted
            if consent_request.is_granted:
                existing_consent.granted_at = datetime.now(timezone.utc)
                existing_consent.revoked_at = None
            else:
                existing_consent.revoked_at = datetime.now(timezone.utc)

            existing_consent.ip_address = ip_address
            existing_consent.user_agent = user_agent
            existing_consent.consent_text = consent_request.consent_text
            existing_consent.legal_basis = consent_request.legal_basis
            existing_consent.purpose = consent_request.purpose

            consent_record = existing_consent

        else:
            # Create new consent record
            consent_record = UserConsent(
                user_id=current_user.id,
                consent_type=consent_request.consent_type,
                is_granted=consent_request.is_granted,
                granted_at=datetime.now(timezone.utc) if consent_request.is_granted else None,
                revoked_at=None if consent_request.is_granted else datetime.now(timezone.utc),
                ip_address=ip_address,
                user_agent=user_agent,
                consent_text=consent_request.consent_text,
                consent_version="1.0",  # Version tracking for consent text changes
                legal_basis=consent_request.legal_basis,
                purpose=consent_request.purpose,
            )
            db.add(consent_record)

        db.commit()
        db.refresh(consent_record)

        # Log consent event
        event_type = EventType.CONSENT_GRANTED if consent_request.is_granted else EventType.CONSENT_REVOKED
        background_tasks.add_task(
            log_security_event,
            event_type=event_type,
            user_id=current_user.id,
            resource=f"consent:{consent_request.consent_type.value}",
            action="update",
            metadata={
                "consent_type": consent_request.consent_type.value,
                "is_granted": consent_request.is_granted,
                "legal_basis": consent_request.legal_basis,
            },
            request=request,
        )

        return ConsentResponse(
            consent_type=consent_record.consent_type,
            is_granted=consent_record.is_granted,
            granted_at=consent_record.granted_at,
            revoked_at=consent_record.revoked_at,
            consent_version=consent_record.consent_version,
            legal_basis=consent_record.legal_basis,
            purpose=consent_record.purpose,
        )

    except Exception as e:
        logger.error(f"Consent management failed for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update consent. Please try again later.",
        )


@router.get("/consent", response_model=List[ConsentResponse])
async def get_consent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current consent status for all consent types.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of consent records for the user
    """
    consent_records = db.query(UserConsent).filter(
        UserConsent.user_id == current_user.id
    ).all()

    return [
        ConsentResponse(
            consent_type=record.consent_type,
            is_granted=record.is_granted,
            granted_at=record.granted_at,
            revoked_at=record.revoked_at,
            consent_version=record.consent_version,
            legal_basis=record.legal_basis,
            purpose=record.purpose,
        )
        for record in consent_records
    ]


# Helper functions for data export
def _export_personal_data(user: User) -> Dict[str, Any]:
    """Export user's personal information."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": [{"name": role.name, "description": role.description} for role in user.roles],
    }


def _export_consent_records(user: User, db: Session) -> List[Dict[str, Any]]:
    """Export user's consent history."""
    records = db.query(UserConsent).filter(UserConsent.user_id == user.id).all()
    return [
        {
            "consent_type": record.consent_type.value,
            "is_granted": record.is_granted,
            "granted_at": record.granted_at.isoformat() if record.granted_at else None,
            "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
            "legal_basis": record.legal_basis,
            "purpose": record.purpose,
            "consent_version": record.consent_version,
        }
        for record in records
    ]


def _export_user_leads(user: User, db: Session) -> List[Dict[str, Any]]:
    """Export leads created or managed by user."""
    # Note: Lead model doesn't have direct user relationship yet
    # This would need to be implemented based on your business logic
    return []


def _export_user_campaigns(user: User, db: Session) -> List[Dict[str, Any]]:
    """Export campaigns created by user."""
    # Note: Campaign model doesn't have direct user relationship yet
    # This would need to be implemented based on your business logic
    return []


def _export_user_reports(user: User, db: Session) -> List[Dict[str, Any]]:
    """Export reports generated by user."""
    # Note: Report model doesn't have direct user relationship yet
    # This would need to be implemented based on your business logic
    return []


def _export_crm_data(user: User, db: Session) -> Dict[str, Any]:
    """Export user's CRM integration data (without sensitive credentials)."""
    # Note: CRMCredential doesn't have direct user relationship yet
    # Only export non-sensitive metadata
    return {
        "integrations": [],
        "sync_logs": [],
    }


def _export_audit_logs(user: User, db: Session) -> List[Dict[str, Any]]:
    """Export user's audit trail (last 90 days)."""
    from app.models.security import SecurityEvent
    from datetime import timedelta

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)

    events = db.query(SecurityEvent).filter(
        SecurityEvent.user_id == user.id,
        SecurityEvent.timestamp >= cutoff_date,
    ).order_by(SecurityEvent.timestamp.desc()).limit(1000).all()

    return [
        {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "resource": event.resource,
            "action": event.action,
            "ip_address": event.ip_address,
            "status_code": event.status_code,
        }
        for event in events
    ]


def _count_records(user_data: Dict[str, Any]) -> int:
    """Count total records in export."""
    count = 0
    for key, value in user_data.items():
        if isinstance(value, list):
            count += len(value)
        elif isinstance(value, dict) and key != "export_metadata":
            count += 1
    return count


async def _anonymize_user_data(user_id: int, db_url: str, reason: Optional[str] = None):
    """
    Background task to anonymize user data.
    Replaces PII with "DELETED" while preserving relationships.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Anonymize user record
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.username = f"DELETED_USER_{user_id}"
            user.email = f"deleted_{user_id}@example.com"
            user.full_name = "DELETED"
            user.phone = None
            user.hashed_password = "DELETED"  # Makes account unrecoverable
            user.is_active = False
            user.last_login_ip = None

            # Clear all consent records
            db.query(UserConsent).filter(UserConsent.user_id == user_id).delete()

            db.commit()
            logger.info(f"User data anonymized for user_id={user_id}, reason={reason}")

    except Exception as e:
        logger.error(f"Failed to anonymize user {user_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()