"""
Domain model for managing email domains and DNS configuration
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from sqlalchemy.sql import func
from .database import Base


class Domain(Base):
    """
    Domain model representing managed domains for email sending infrastructure.
    Tracks DNS configuration status for SPF, DKIM, and DMARC records.
    """
    __tablename__ = "dim_domains"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for active domain queries
        Index('idx_domains_active_registrar', 'is_active', 'registrar'),
        # Index for expiration monitoring
        Index('idx_domains_expires_at', 'expires_at'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Domain Information
    name = Column(String(255), unique=True, nullable=False, index=True)

    # Purchase Info
    purchased_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    registrar = Column(String(100), default="godaddy")

    # DNS Status Tracking
    dns_configured = Column(Boolean, default=False, nullable=False)
    spf_configured = Column(Boolean, default=False, nullable=False)
    dkim_configured = Column(Boolean, default=False, nullable=False)
    dmarc_configured = Column(Boolean, default=False, nullable=False)

    # GoDaddy Integration
    godaddy_domain_id = Column(String(100))

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Domain(id={self.id}, name='{self.name}', active={self.is_active})>"

    @property
    def is_fully_configured(self) -> bool:
        """Check if all DNS records are configured"""
        return all([
            self.dns_configured,
            self.spf_configured,
            self.dkim_configured,
            self.dmarc_configured
        ])

    @property
    def dns_status_summary(self) -> dict:
        """Get summary of DNS configuration status"""
        return {
            "dns_configured": self.dns_configured,
            "spf_configured": self.spf_configured,
            "dkim_configured": self.dkim_configured,
            "dmarc_configured": self.dmarc_configured,
            "fully_configured": self.is_fully_configured
        }
