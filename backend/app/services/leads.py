"""
Lead Service - Business logic for lead management

Handles CRUD operations, qualification, enrichment, and lead lifecycle management.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_

from app.models import Lead
from app.core.logging import setup_logging
from app.core.exceptions import (
    LeadNotFoundError,
    LeadValidationError,
    DatabaseError
)

logger = setup_logging(__name__)


class LeadService:
    """
    Service for lead management operations

    Features:
    - CRUD operations for leads
    - Qualification scoring and updates
    - Lead enrichment data management
    - Search and filtering
    - Status tracking
    """

    def __init__(self):
        """Initialize Lead service"""
        logger.info("LeadService initialized")

    def create_lead(
        self,
        db: Session,
        company_name: str,
        **kwargs
    ) -> Lead:
        """
        Create a new lead

        Args:
            db: Database session
            company_name: Company name (required)
            **kwargs: Additional lead fields (industry, company_website, etc.)

        Returns:
            Created Lead object

        Raises:
            LeadValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            # Validate required field
            if not company_name or not company_name.strip():
                raise LeadValidationError("company_name is required")

            # Create lead instance
            lead = Lead(
                company_name=company_name.strip(),
                company_website=kwargs.get('company_website'),
                company_size=kwargs.get('company_size'),
                industry=kwargs.get('industry'),
                contact_name=kwargs.get('contact_name'),
                contact_email=kwargs.get('contact_email'),
                contact_phone=kwargs.get('contact_phone'),
                contact_title=kwargs.get('contact_title'),
                notes=kwargs.get('notes'),
                additional_data=kwargs.get('additional_data', {})
            )

            db.add(lead)
            db.commit()
            db.refresh(lead)

            logger.info(f"Created lead: {lead.id} ({company_name})")
            return lead

        except LeadValidationError:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating lead: {e}")
            raise DatabaseError(f"Failed to create lead: {str(e)}")

    def get_lead(self, db: Session, lead_id: int) -> Lead:
        """
        Get lead by ID

        Args:
            db: Database session
            lead_id: Lead ID

        Returns:
            Lead object

        Raises:
            LeadNotFoundError: If lead not found
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise LeadNotFoundError(f"Lead {lead_id} not found")
        return lead

    def get_leads(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        industry: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None
    ) -> List[Lead]:
        """
        Get list of leads with optional filtering

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            industry: Filter by industry
            min_score: Minimum qualification score
            max_score: Maximum qualification score

        Returns:
            List of Lead objects
        """
        query = db.query(Lead)

        # Apply filters
        if industry:
            query = query.filter(Lead.industry.ilike(f"%{industry}%"))

        if min_score is not None:
            query = query.filter(Lead.qualification_score >= min_score)

        if max_score is not None:
            query = query.filter(Lead.qualification_score <= max_score)

        # Order by most recent first
        query = query.order_by(Lead.created_at.desc())

        # Pagination
        leads = query.offset(skip).limit(limit).all()

        return leads

    def update_lead(
        self,
        db: Session,
        lead_id: int,
        **kwargs
    ) -> Lead:
        """
        Update lead fields

        Args:
            db: Database session
            lead_id: Lead ID
            **kwargs: Fields to update

        Returns:
            Updated Lead object

        Raises:
            LeadNotFoundError: If lead not found
            DatabaseError: If database operation fails
        """
        try:
            lead = self.get_lead(db, lead_id)

            # Update allowed fields
            allowed_fields = {
                'company_name', 'company_website', 'company_size', 'industry',
                'contact_name', 'contact_email', 'contact_phone', 'contact_title',
                'qualification_score', 'qualification_reasoning', 'qualification_model',
                'qualification_latency_ms', 'notes', 'additional_data',
                'social_activity', 'contact_profiles', 'org_charts'
            }

            for field, value in kwargs.items():
                if field in allowed_fields and hasattr(lead, field):
                    setattr(lead, field, value)

            # Update timestamp
            lead.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(lead)

            logger.info(f"Updated lead: {lead_id}")
            return lead

        except LeadNotFoundError:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating lead {lead_id}: {e}")
            raise DatabaseError(f"Failed to update lead: {str(e)}")

    def update_qualification(
        self,
        db: Session,
        lead_id: int,
        score: float,
        reasoning: str,
        model: str,
        latency_ms: Optional[float] = None
    ) -> Lead:
        """
        Update lead qualification data

        Args:
            db: Database session
            lead_id: Lead ID
            score: Qualification score (0-100)
            reasoning: Qualification reasoning
            model: Model used for qualification
            latency_ms: Qualification latency in milliseconds

        Returns:
            Updated Lead object
        """
        lead = self.get_lead(db, lead_id)

        lead.qualification_score = score
        lead.qualification_reasoning = reasoning
        lead.qualification_model = model
        lead.qualification_latency_ms = latency_ms
        lead.qualified_at = datetime.utcnow()
        lead.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(lead)

        logger.info(f"Updated qualification for lead {lead_id}: score={score}, model={model}")
        return lead

    def update_enrichment(
        self,
        db: Session,
        lead_id: int,
        enrichment_data: Dict[str, Any]
    ) -> Lead:
        """
        Update lead with enrichment data from Apollo/LinkedIn/Close

        Args:
            db: Database session
            lead_id: Lead ID
            enrichment_data: Enrichment data dictionary

        Returns:
            Updated Lead object
        """
        lead = self.get_lead(db, lead_id)

        # Merge enrichment data into additional_data
        if not lead.additional_data:
            lead.additional_data = {}

        if 'enrichment' not in lead.additional_data:
            lead.additional_data['enrichment'] = {}

        lead.additional_data['enrichment'].update(enrichment_data)
        lead.updated_at = datetime.utcnow()

        # Mark as modified for SQLAlchemy to detect JSON change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(lead, "additional_data")

        db.commit()
        db.refresh(lead)

        logger.info(f"Updated enrichment for lead {lead_id}")
        return lead

    def delete_lead(self, db: Session, lead_id: int) -> bool:
        """
        Delete lead by ID

        Args:
            db: Database session
            lead_id: Lead ID

        Returns:
            True if deleted successfully

        Raises:
            LeadNotFoundError: If lead not found
            DatabaseError: If database operation fails
        """
        try:
            lead = self.get_lead(db, lead_id)

            db.delete(lead)
            db.commit()

            logger.info(f"Deleted lead: {lead_id}")
            return True

        except LeadNotFoundError:
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting lead {lead_id}: {e}")
            raise DatabaseError(f"Failed to delete lead: {str(e)}")

    def search_leads(
        self,
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Lead]:
        """
        Search leads by company name, contact name, or email

        Args:
            db: Database session
            search_term: Search term
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching Lead objects
        """
        search_pattern = f"%{search_term}%"

        leads = db.query(Lead).filter(
            or_(
                Lead.company_name.ilike(search_pattern),
                Lead.contact_name.ilike(search_pattern),
                Lead.contact_email.ilike(search_pattern)
            )
        ).order_by(
            Lead.created_at.desc()
        ).offset(skip).limit(limit).all()

        return leads

    def get_lead_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get overall lead statistics

        Args:
            db: Database session

        Returns:
            Dictionary with lead statistics
        """
        total_leads = db.query(Lead).count()
        qualified_leads = db.query(Lead).filter(
            Lead.qualification_score.isnot(None)
        ).count()

        # Calculate average qualification score
        from sqlalchemy import func
        avg_score = db.query(
            func.avg(Lead.qualification_score)
        ).filter(
            Lead.qualification_score.isnot(None)
        ).scalar()

        return {
            'total_leads': total_leads,
            'qualified_leads': qualified_leads,
            'unqualified_leads': total_leads - qualified_leads,
            'average_qualification_score': float(avg_score) if avg_score else 0.0
        }
