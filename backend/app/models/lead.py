"""
Lead model for storing and managing sales leads
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Index, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class Lead(Base):
    """
    Lead model representing a sales prospect with AI-generated qualification score
    """
    __tablename__ = "leads"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for queries filtering/sorting by score and time
        Index('idx_leads_score_created', 'qualification_score', 'created_at'),
        # Standalone indexes to speed up common filters/sorts
        Index('idx_leads_created_at', 'created_at'),
        Index('idx_leads_updated_at', 'updated_at'),
        Index('idx_leads_qualified_at', 'qualified_at'),
        # CHECK constraint to enforce valid score range (0-100)
        CheckConstraint('qualification_score >= 0 AND qualification_score <= 100', name='check_score_range'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Company Information
    company_name = Column(String(255), nullable=False, index=True)
    company_website = Column(String(500))
    company_size = Column(String(100))
    industry = Column(String(200))

    # Contact Information
    contact_name = Column(String(255))
    contact_email = Column(String(255), index=True)
    contact_phone = Column(String(50))
    contact_title = Column(String(200))

    # AI-Generated Qualification
    qualification_score = Column(Float, index=True)  # 0-100 scale
    qualification_reasoning = Column(Text)  # AI explanation for score
    qualification_model = Column(String(100))  # Model used for scoring
    qualification_latency_ms = Column(Integer)  # Response time in milliseconds

    # Additional Data
    notes = Column(Text)
    additional_data = Column(JSON)  # Flexible field for additional data

    # ============================================================================
    # OEM Tracking Fields (Multi-OEM Energy Transition Scoring)
    # ============================================================================

    # OEM Category Counts (6 categories for MEP+E contractors)
    hvac_oem_count = Column(Integer, default=0, nullable=False)
    solar_oem_count = Column(Integer, default=0, nullable=False)
    battery_oem_count = Column(Integer, default=0, nullable=False)
    generator_oem_count = Column(Integer, default=0, nullable=False)
    smart_panel_oem_count = Column(Integer, default=0, nullable=False)
    iot_oem_count = Column(Integer, default=0, nullable=False)

    # OEM Details (JSON storage for certification lists and tiers)
    oems_certified = Column(JSON, default=list, nullable=False)  # ["Generac", "Tesla", "Enphase"]
    oem_tiers = Column(JSON, default=dict, nullable=False)  # {"Generac": "Elite Plus", "Enphase": "Platinum"}

    # OEM Scoring (Multi-OEM Energy Transition Score: 0-100)
    total_oem_count = Column(Integer, default=0, nullable=False)  # Sum of all category counts
    mep_e_score = Column(Integer, default=0, nullable=False)  # BuildOps-pattern MEP+E sophistication score

    # ============================================================================
    # Service Capability Flags (ICP Targeting from dealer-scraper-mvp)
    # ============================================================================

    # Energy Transition Capabilities
    has_hvac = Column(Boolean, default=False, nullable=False)
    has_solar = Column(Boolean, default=False, nullable=False)
    has_battery = Column(Boolean, default=False, nullable=False)
    has_generator = Column(Boolean, default=False, nullable=False)
    has_ev_charger = Column(Boolean, default=False, nullable=False)
    has_smart_panel = Column(Boolean, default=False, nullable=False)
    has_heat_pump = Column(Boolean, default=False, nullable=False)
    has_microgrid = Column(Boolean, default=False, nullable=False)

    # Business Model Capabilities
    has_commercial = Column(Boolean, default=False, nullable=False)  # B2B focus (higher deal sizes)
    has_ops_maintenance = Column(Boolean, default=False, nullable=False)  # Recurring revenue model

    # ============================================================================
    # ICP Category Scores (from visual map: 3-category framework)
    # ============================================================================

    renewable_readiness_score = Column(Integer, default=0, nullable=False)  # Solar/battery sophistication (0-100)
    asset_centric_score = Column(Integer, default=0, nullable=False)  # O&M, generators, preventive (0-100)
    projects_service_score = Column(Integer, default=0, nullable=False)  # Multi-trade, service model (0-100)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    qualified_at = Column(DateTime(timezone=True))  # When AI qualification occurred

    # Relationships to social media tables
    social_activity = relationship("SocialMediaActivity", back_populates="lead", cascade="all, delete-orphan")
    contact_profiles = relationship("ContactSocialProfile", back_populates="lead", cascade="all, delete-orphan")
    org_charts = relationship("OrganizationChart", back_populates="lead", cascade="all, delete-orphan")

    # Voice interaction relationship
    voice_sessions = relationship("VoiceSessionLog", back_populates="lead", cascade="all, delete-orphan")

    # Conversation intelligence relationship
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")

    # Report generation relationship
    reports = relationship("Report", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead(id={self.id}, company='{self.company_name}', score={self.qualification_score})>"
