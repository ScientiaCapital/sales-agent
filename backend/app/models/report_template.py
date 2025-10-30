"""
Report Template Model

User-defined report templates for custom analytics reports.
Supports flexible query configuration, visualization settings, and filter defaults.
"""
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.models.database import Base


class ReportTemplate(Base):
    """User-defined report templates for analytics"""
    __tablename__ = "report_templates"

    # Primary Keys
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(36), unique=True, index=True, nullable=False)

    # Basic Information
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Template Configuration
    report_type = Column(String(50), nullable=False, index=True)  # lead_analysis, campaign_performance, cost_summary, ab_test_results
    query_config = Column(JSON, nullable=False)  # SQL query parameters (table, columns, filters, aggregations, etc.)
    visualization_config = Column(JSON, nullable=True)  # Chart configurations for frontend rendering
    filter_config = Column(JSON, nullable=True)  # Default filters and available filter options

    # Metadata
    is_system_template = Column(Boolean, default=False, index=True)  # System-provided templates
    created_by = Column(String(100), nullable=True)  # User ID or email
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Usage Tracking
    usage_count = Column(Integer, default=0, nullable=False)  # Track template popularity

    def __repr__(self):
        return f"<ReportTemplate(id={self.id}, template_id='{self.template_id}', name='{self.name}', type='{self.report_type}')>"

    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            'id': self.id,
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'report_type': self.report_type,
            'query_config': self.query_config,
            'visualization_config': self.visualization_config,
            'filter_config': self.filter_config,
            'is_system_template': self.is_system_template,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'usage_count': self.usage_count,
        }
