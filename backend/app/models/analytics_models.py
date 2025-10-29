"""
Analytics Database Models

SQLAlchemy models for comprehensive analytics and reporting system.
Tracks user sessions, lead metrics, campaign performance, system health, and A/B tests.

Supports:
- Real-time dashboard metrics
- Performance analytics
- A/B test tracking
- Custom report generation
- Data export functionality
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from app.models.database import Base


class AnalyticsUserSession(Base):
    """
    Track user sessions and activity for analytics.
    
    Provides insights into user engagement, API usage patterns, and session metrics.
    """
    __tablename__ = "analytics_user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Session metadata
    session_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=True, index=True)  # Optional user identification
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    
    # Session timing
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Activity metrics
    api_calls_count = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    agents_used = Column(JSON, nullable=True)  # List of agent types used
    leads_processed = Column(Integer, default=0)
    
    # Session metadata
    session_data = Column(JSON, nullable=True)  # Additional session context
    referrer = Column(String(500), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    
    def __repr__(self):
        return f"<AnalyticsUserSession(id={self.id}, user_id='{self.user_id}', duration={self.duration_seconds}s)>"


class AnalyticsLeadMetrics(Base):
    """
    Track lead-specific analytics and conversion metrics.
    
    Provides detailed insights into lead processing, qualification scores, and conversion rates.
    """
    __tablename__ = "analytics_lead_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Lead identification
    lead_id = Column(Integer, nullable=True, index=True)  # Reference to Lead model
    external_lead_id = Column(String(100), nullable=True, index=True)  # CRM lead ID
    
    # Lead source and context
    source = Column(String(100), nullable=True, index=True)  # website, api, import, etc.
    campaign_id = Column(String(100), nullable=True, index=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    
    # Qualification metrics
    qualification_score = Column(Float, nullable=True, index=True)
    qualification_tier = Column(String(10), nullable=True, index=True)  # A, B, C, D
    qualification_reasoning = Column(Text, nullable=True)
    
    # Processing metrics
    processing_time_ms = Column(Integer, nullable=True)
    agents_used = Column(JSON, nullable=True)  # List of agents that processed this lead
    enrichment_sources = Column(JSON, nullable=True)  # Apollo, LinkedIn, etc.
    
    # Conversion tracking
    conversion_status = Column(String(50), nullable=True, index=True)  # qualified, contacted, meeting_booked, closed_won, closed_lost
    conversion_date = Column(DateTime(timezone=True), nullable=True)
    revenue_attributed = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AnalyticsLeadMetrics(id={self.id}, lead_id={self.lead_id}, score={self.qualification_score})>"


class AnalyticsCampaignMetrics(Base):
    """
    Track marketing campaign performance and analytics.
    
    Provides insights into campaign effectiveness, conversion rates, and ROI.
    """
    __tablename__ = "analytics_campaign_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Campaign identification
    campaign_id = Column(String(100), nullable=False, index=True)
    campaign_name = Column(String(200), nullable=False)
    campaign_type = Column(String(50), nullable=False, index=True)  # email, linkedin, apollo, etc.
    
    # Campaign metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    leads_generated = Column(Integer, default=0)
    
    # Performance metrics
    click_through_rate = Column(Float, nullable=True)  # clicks / impressions
    conversion_rate = Column(Float, nullable=True)  # conversions / clicks
    cost_per_click = Column(Float, nullable=True)
    cost_per_conversion = Column(Float, nullable=True)
    revenue_generated = Column(Float, nullable=True)
    roi_percentage = Column(Float, nullable=True)
    
    # Timing
    campaign_start_date = Column(DateTime(timezone=True), nullable=True)
    campaign_end_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Campaign metadata
    campaign_data = Column(JSON, nullable=True)  # Additional campaign context
    
    def __repr__(self):
        return f"<AnalyticsCampaignMetrics(id={self.id}, campaign='{self.campaign_name}', conversions={self.conversions})>"


class AnalyticsSystemMetrics(Base):
    """
    Track system performance and health metrics.
    
    Provides insights into system performance, error rates, and resource usage.
    """
    __tablename__ = "analytics_system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)  # response_time, error_rate, cpu_usage, etc.
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)  # ms, %, count, etc.
    
    # Categorization
    category = Column(String(50), nullable=False, index=True)  # performance, error, resource, business
    subcategory = Column(String(50), nullable=True, index=True)  # api, database, redis, etc.
    
    # Context
    tags = Column(JSON, nullable=True)  # Additional context tags
    agent_type = Column(String(50), nullable=True, index=True)  # If metric is agent-specific
    endpoint = Column(String(200), nullable=True, index=True)  # If metric is endpoint-specific
    
    # Timing
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    
    # Additional context
    metric_metadata = Column(JSON, nullable=True)  # Additional metric context
    
    def __repr__(self):
        return f"<AnalyticsSystemMetrics(id={self.id}, metric='{self.metric_name}', value={self.metric_value})>"


class AnalyticsABTest(Base):
    """
    Track A/B test experiments and statistical analysis.
    
    Provides comprehensive A/B testing capabilities with statistical significance tracking.
    """
    __tablename__ = "analytics_ab_tests"

    id = Column(Integer, primary_key=True, index=True)
    
    # Test identification
    test_id = Column(String(100), nullable=False, unique=True, index=True)
    test_name = Column(String(200), nullable=False)
    test_description = Column(Text, nullable=True)
    
    # Test configuration
    variant_a_name = Column(String(100), nullable=False)
    variant_b_name = Column(String(100), nullable=False)
    test_type = Column(String(50), nullable=False, index=True)  # agent_performance, ui_element, campaign, etc.
    
    # Test metrics
    participants_a = Column(Integer, default=0)
    participants_b = Column(Integer, default=0)
    conversions_a = Column(Integer, default=0)
    conversions_b = Column(Integer, default=0)
    
    # Statistical analysis
    conversion_rate_a = Column(Float, nullable=True)
    conversion_rate_b = Column(Float, nullable=True)
    statistical_significance = Column(Float, nullable=True)  # p-value
    confidence_level = Column(Float, nullable=True)  # 95%, 99%, etc.
    winner = Column(String(10), nullable=True)  # A, B, or inconclusive
    
    # Test status
    status = Column(String(20), nullable=False, index=True, default="draft")  # draft, running, completed, paused
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Test configuration
    test_config = Column(JSON, nullable=True)  # Additional test parameters
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    def __repr__(self):
        return f"<AnalyticsABTest(id={self.id}, test='{self.test_name}', status='{self.status}')>"


class AnalyticsReport(Base):
    """
    Store generated analytics reports and their metadata.
    
    Provides report history, caching, and sharing capabilities.
    """
    __tablename__ = "analytics_reports"

    id = Column(Integer, primary_key=True, index=True)
    
    # Report identification
    report_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    report_name = Column(String(200), nullable=False)
    report_type = Column(String(50), nullable=False, index=True)  # dashboard, custom, scheduled, etc.
    
    # Report configuration
    report_parameters = Column(JSON, nullable=True)  # Parameters used to generate report
    time_range_start = Column(DateTime(timezone=True), nullable=True)
    time_range_end = Column(DateTime(timezone=True), nullable=True)
    
    # Report data
    data_snapshot = Column(JSON, nullable=True)  # Cached report data
    chart_configs = Column(JSON, nullable=True)  # Chart configurations
    
    # Report metadata
    generated_by = Column(String(100), nullable=True)  # User who generated the report
    generated_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # TTL for cached reports
    
    # Report status
    status = Column(String(20), nullable=False, index=True, default="generated")  # generating, generated, failed
    file_path = Column(String(500), nullable=True)  # Path to exported file if applicable
    
    def __repr__(self):
        return f"<AnalyticsReport(id={self.id}, name='{self.report_name}', type='{self.report_type}')>"


# Indexes for performance optimization
Index('idx_analytics_session_user_time', AnalyticsUserSession.user_id, AnalyticsUserSession.started_at)
Index('idx_analytics_lead_source_time', AnalyticsLeadMetrics.source, AnalyticsLeadMetrics.created_at)
Index('idx_analytics_lead_conversion', AnalyticsLeadMetrics.conversion_status, AnalyticsLeadMetrics.conversion_date)
Index('idx_analytics_campaign_type_time', AnalyticsCampaignMetrics.campaign_type, AnalyticsCampaignMetrics.created_at)
Index('idx_analytics_system_category_time', AnalyticsSystemMetrics.category, AnalyticsSystemMetrics.recorded_at)
Index('idx_analytics_ab_test_status', AnalyticsABTest.status, AnalyticsABTest.start_date)
Index('idx_analytics_report_type_time', AnalyticsReport.report_type, AnalyticsReport.generated_at)
