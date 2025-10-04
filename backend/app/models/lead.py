"""
Lead model for storing and managing sales leads
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.sql import func
from .database import Base


class Lead(Base):
    """
    Lead model representing a sales prospect with AI-generated qualification score
    """
    __tablename__ = "leads"

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

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    qualified_at = Column(DateTime(timezone=True))  # When AI qualification occurred

    def __repr__(self):
        return f"<Lead(id={self.id}, company='{self.company_name}', score={self.qualification_score})>"
