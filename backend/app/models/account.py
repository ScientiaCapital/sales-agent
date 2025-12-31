"""
Account model for multi-stakeholder engagement tracking.

The Account represents a top-level entity grouping companies by domain,
enabling enterprise sales workflows with multiple stakeholders per account.
"""
from enum import Enum
from typing import Optional, List
from uuid import UUID as PyUUID

from sqlalchemy import Column, String, Integer, Float, Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .database import Base


class AccountStage(str, Enum):
    """Pipeline stages for account progression."""
    PROSPECT = "prospect"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    OPPORTUNITY = "opportunity"
    CUSTOMER = "customer"
    CHURNED = "churned"


class Account(Base):
    """
    Account model representing a company entity for multi-stakeholder sales.

    Accounts group companies by domain and track aggregate engagement metrics
    across all contacts and sequences. This enables account-based marketing
    and sales strategies.

    Key metrics:
    - total_contacts: Count of all contacts at this account
    - engaged_contacts: Contacts with activity (emails opened, replied, etc.)
    - stakeholder_score: % of ATL (decision makers) that are engaged
    - account_stage: Pipeline progression stage
    """
    __tablename__ = "dim_accounts"

    __table_args__ = (
        Index('idx_accounts_stage_industry', 'account_stage', 'industry'),
    )

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=func.gen_random_uuid())

    # Account Identification
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), unique=True, nullable=True, index=True)
    industry = Column(String(100), nullable=True)
    employee_count = Column(Integer, nullable=True)

    # Rollup Metrics (denormalized for performance)
    total_contacts = Column(Integer, default=0, nullable=False)
    engaged_contacts = Column(Integer, default=0, nullable=False)
    total_activities = Column(Integer, default=0, nullable=False)
    stakeholder_score = Column(Float, nullable=True)

    # Pipeline Tracking
    account_stage = Column(
        String(50),
        default=AccountStage.PROSPECT.value,
        nullable=False,
        index=True
    )
    deal_value = Column(Numeric(12, 2), nullable=True)
    probability = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    # Relationships (back_populates will be added to related models)
    # companies = relationship("Company", back_populates="account")
    # sequences = relationship("Sequence", back_populates="account")

    def __repr__(self) -> str:
        return (
            f"<Account(id={self.id}, name='{self.name}', "
            f"domain='{self.domain}', stage='{self.account_stage}')>"
        )

    @property
    def engagement_rate(self) -> float:
        """Calculate the percentage of contacts that are engaged."""
        if self.total_contacts == 0:
            return 0.0
        return (self.engaged_contacts / self.total_contacts) * 100

    @property
    def is_active(self) -> bool:
        """Check if account is in an active pipeline stage."""
        active_stages = {
            AccountStage.ENGAGED.value,
            AccountStage.QUALIFIED.value,
            AccountStage.OPPORTUNITY.value
        }
        return self.account_stage in active_stages

    @property
    def is_customer(self) -> bool:
        """Check if account has converted to customer."""
        return self.account_stage == AccountStage.CUSTOMER.value

    @property
    def weighted_deal_value(self) -> Optional[float]:
        """Calculate probability-weighted deal value."""
        if self.deal_value is None or self.probability is None:
            return None
        return float(self.deal_value) * self.probability

    def to_dict(self) -> dict:
        """Convert account to dictionary for API responses."""
        return {
            "id": str(self.id) if self.id else None,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "total_contacts": self.total_contacts,
            "engaged_contacts": self.engaged_contacts,
            "total_activities": self.total_activities,
            "stakeholder_score": self.stakeholder_score,
            "engagement_rate": round(self.engagement_rate, 2),
            "account_stage": self.account_stage,
            "deal_value": float(self.deal_value) if self.deal_value else None,
            "probability": self.probability,
            "weighted_deal_value": self.weighted_deal_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
