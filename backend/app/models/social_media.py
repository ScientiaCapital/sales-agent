"""
Social Media Data Models

Database models for storing social media activity, mentions, and contact information.
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models.database import Base


class SocialMediaActivity(Base):
    """
    Social media mentions and activity tracking

    Stores posts, tweets, and mentions across multiple platforms for sentiment analysis
    and engagement tracking.
    """
    __tablename__ = "social_media_activity"

    id = Column(Integer, primary_key=True, index=True)

    # Platform identification
    platform = Column(String(50), nullable=False, index=True)  # twitter, reddit, instagram, facebook
    platform_post_id = Column(String(255), unique=True, index=True)  # Unique ID from platform
    post_url = Column(String(1000))  # Full URL to the post

    # Company/Lead association
    company_name = Column(String(255), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)  # Optional link to lead

    # Content
    title = Column(String(500))  # For Reddit posts
    text_content = Column(Text)  # Post/tweet text
    author_username = Column(String(255))
    author_name = Column(String(255))

    # Engagement metrics
    likes_count = Column(Integer, default=0)
    retweets_count = Column(Integer, default=0)  # Twitter
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)  # Facebook/LinkedIn
    upvotes_count = Column(Integer, default=0)  # Reddit
    engagement_score = Column(Float)  # Calculated engagement metric

    # AI Sentiment Analysis (via Cerebras)
    sentiment = Column(String(20))  # positive, negative, neutral
    sentiment_score = Column(Float)  # 0-100 scale
    sentiment_reasoning = Column(Text)  # AI explanation

    # Metadata
    posted_at = Column(DateTime(timezone=True))  # When post was created on platform
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())  # When we scraped it
    additional_data = Column(JSON)  # Flexible field for platform-specific data

    # Relationships
    lead = relationship("Lead", back_populates="social_activity")

    def __repr__(self):
        return f"<SocialMediaActivity(platform='{self.platform}', company='{self.company_name}', sentiment='{self.sentiment}')>"


class ContactSocialProfile(Base):
    """
    Social media profiles for discovered contacts

    Links contacts (ATL decision makers) to their social media profiles
    for relationship tracking and engagement monitoring.
    """
    __tablename__ = "contact_social_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Contact identification
    contact_name = Column(String(255), nullable=False, index=True)
    contact_email = Column(String(255), index=True)
    company_name = Column(String(255), nullable=False, index=True)
    job_title = Column(String(255))
    
    # Lead association
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)

    # LinkedIn Profile (primary)
    linkedin_url = Column(String(500), unique=True, index=True)
    linkedin_headline = Column(String(500))
    linkedin_location = Column(String(255))
    linkedin_connections = Column(String(50))  # "500+", "1000+"
    current_company = Column(String(255))
    current_title = Column(String(255))
    tenure = Column(String(100))  # "3 years 2 months"
    
    # Decision maker scoring
    decision_maker_score = Column(Integer, default=0)  # 0-100 based on title/seniority
    contact_priority = Column(String(20))  # high, medium, low
    is_c_level = Column(Boolean, default=False)
    is_vp_level = Column(Boolean, default=False)

    # Other social profiles (optional)
    twitter_url = Column(String(500))
    twitter_username = Column(String(100))
    facebook_url = Column(String(500))
    instagram_url = Column(String(500))

    # Professional details
    experience_years = Column(Integer)  # Total years of experience
    skills = Column(JSON)  # List of skills from LinkedIn
    education = Column(JSON)  # Education history
    work_history = Column(JSON)  # Previous positions

    # Engagement tracking
    last_activity_date = Column(DateTime(timezone=True))  # Last social media activity
    engagement_frequency = Column(String(50))  # daily, weekly, monthly
    topics_discussed = Column(JSON)  # Topics they post about

    # Scraping metadata
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    scraping_method = Column(String(100))  # browserbase, api, manual
    data_quality_score = Column(Integer)  # 0-100 based on data completeness

    # Relationships
    lead = relationship("Lead", back_populates="contact_profiles")

    def __repr__(self):
        return f"<ContactSocialProfile(name='{self.contact_name}', company='{self.company_name}', score={self.decision_maker_score})>"


class OrganizationChart(Base):
    """
    Company organizational hierarchy

    Stores inferred org chart data from LinkedIn employee scraping
    for understanding reporting structures and identifying decision paths.
    """
    __tablename__ = "organization_charts"

    id = Column(Integer, primary_key=True, index=True)

    # Company identification
    company_name = Column(String(255), nullable=False, index=True)
    company_linkedin_url = Column(String(500), unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)

    # Org chart data
    hierarchy_data = Column(JSON, nullable=False)  # Full org chart structure
    total_employees_analyzed = Column(Integer)
    key_decision_makers_count = Column(Integer)
    
    # C-level executives
    c_level_contacts = Column(JSON)  # List of C-level profiles
    
    # VP level
    vp_level_contacts = Column(JSON)  # List of VP profiles
    
    # Director level
    director_level_contacts = Column(JSON)  # List of Director profiles

    # Reporting paths
    reporting_relationships = Column(JSON)  # Who reports to whom
    team_structures = Column(JSON)  # Department/team breakdown

    # Analysis metadata
    chart_depth = Column(Integer)  # How many levels deep (1, 2, 3)
    confidence_score = Column(Float)  # 0-100 based on data completeness
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    lead = relationship("Lead", back_populates="org_charts")

    def __repr__(self):
        return f"<OrganizationChart(company='{self.company_name}', employees={self.total_employees_analyzed})>"
