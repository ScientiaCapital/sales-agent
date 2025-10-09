"""
Customer and knowledge base models for multi-tenant platform
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.models.database import Base


class Customer(Base):
    """
    Customer model for multi-tenant platform
    
    Each customer has isolated:
    - Knowledge base documents
    - Agent teams
    - API quotas and usage tracking
    """
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Customer Information
    company_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # API Access
    api_key = Column(String(128), unique=True, nullable=False, index=True)  # Generated API key
    api_key_hash = Column(String(256))  # Hashed version for security
    
    # Subscription & Status
    subscription_tier = Column(String(50), default="free")  # free, starter, pro, enterprise
    status = Column(String(50), default="active", index=True)  # active, suspended, cancelled
    
    # Contact Information
    contact_name = Column(String(255))
    contact_title = Column(String(200))
    company_website = Column(String(500))
    company_size = Column(String(100))
    industry = Column(String(200))
    
    # Settings
    settings = Column(JSON, default=dict)  # Custom customer settings
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    knowledge_documents = relationship("KnowledgeDocument", back_populates="customer", cascade="all, delete-orphan")
    agents = relationship("CustomerAgent", back_populates="customer", cascade="all, delete-orphan")
    quotas = relationship("CustomerQuota", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, company='{self.company_name}', tier='{self.subscription_tier}')>"


class KnowledgeDocument(Base):
    """
    Knowledge base documents with vector embeddings for similarity search
    
    Stores customer-specific documents (PDFs, DOCX, TXT) with:
    - Text content and metadata
    - Vector embeddings for semantic search
    - ICP (Ideal Customer Profile) criteria extraction
    """
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Customer Isolation
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Document Metadata
    document_id = Column(String(128), unique=True, nullable=False, index=True)  # Firebase document ID
    filename = Column(String(500), nullable=False)
    content_type = Column(String(100))  # MIME type
    file_size = Column(Integer)  # Bytes
    
    # RunPod S3 Storage
    runpod_storage_path = Column(String(1000))  # Path in RunPod S3 bucket
    runpod_url = Column(String(2000))  # Public or presigned URL

    # Content
    text_content = Column(Text)  # Full extracted text
    text_length = Column(Integer)  # Character count
    
    # Vector Embeddings (384 dimensions for all-MiniLM-L6-v2)
    embedding = Column(Vector(384))  # pgvector column for similarity search
    
    # ICP Extraction
    target_industries = Column(JSON)  # List of target industries
    company_sizes = Column(JSON)  # List of target company sizes
    decision_makers = Column(JSON)  # List of decision maker titles
    target_regions = Column(JSON)  # List of geographic regions
    
    # Search and Indexing
    icp_data = Column(JSON)  # Full ICP criteria dictionary
    tags = Column(JSON)  # Custom tags for categorization
    
    # Processing Status
    processing_status = Column(String(50), default="completed")  # pending, processing, completed, failed
    processing_error = Column(Text)  # Error message if processing failed

    # Document Analysis (Gist Memory)
    summary = Column(Text)  # AI-generated document summary
    key_items = Column(JSON)  # Extracted entities, dates, key phrases, actions
    page_gists = Column(JSON)  # List of page-level summaries from gist memory
    page_metadata = Column(JSON)  # Metadata about pages (word counts, etc.)
    analysis_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    analysis_error = Column(Text)  # Error message if analysis failed
    analyzed_at = Column(DateTime(timezone=True))  # When analysis was completed

    # Analysis Statistics
    page_count = Column(Integer)  # Number of pages from gist memory
    compression_ratio = Column(Float)  # Gist compression ratio
    processing_time_ms = Column(Integer)  # Analysis processing time

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="knowledge_documents")
    
    def __repr__(self):
        return f"<KnowledgeDocument(id={self.id}, customer_id={self.customer_id}, filename='{self.filename}')>"


class CustomerAgent(Base):
    """
    Agent deployments for customers
    
    Tracks customer-specific agent teams with:
    - Agent configuration and status
    - Performance metrics
    - Resource allocation
    """
    __tablename__ = "customer_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Customer Isolation
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Agent Configuration
    agent_name = Column(String(255), nullable=False)
    agent_type = Column(String(100), nullable=False)  # lead_qualifier, outreach, researcher, etc.
    agent_role = Column(String(100))  # Specific role in multi-agent team
    
    # Deployment
    deployment_id = Column(String(128), unique=True, index=True)  # Unique deployment identifier
    status = Column(String(50), default="deployed", index=True)  # deployed, paused, terminated
    
    # Configuration
    config = Column(JSON, default=dict)  # Agent-specific configuration
    model = Column(String(100))  # AI model being used
    
    # Performance Metrics
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    average_latency_ms = Column(Float)
    
    # Resource Usage
    total_api_calls = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    
    # Timestamps
    deployed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active_at = Column(DateTime(timezone=True))
    terminated_at = Column(DateTime(timezone=True))
    
    # Relationships
    customer = relationship("Customer", back_populates="agents")
    
    def __repr__(self):
        return f"<CustomerAgent(id={self.id}, customer_id={self.customer_id}, name='{self.agent_name}', status='{self.status}')>"


class CustomerQuota(Base):
    """
    Resource quotas and usage limits for customers
    
    Enforces:
    - API call limits
    - Agent deployment limits
    - Storage limits
    - Cost caps
    """
    __tablename__ = "customer_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Customer Isolation (one-to-one relationship)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True, index=True)
    
    # API Quotas
    max_api_calls_per_day = Column(Integer, default=1000)
    max_api_calls_per_month = Column(Integer, default=30000)
    api_calls_today = Column(Integer, default=0)
    api_calls_this_month = Column(Integer, default=0)
    
    # Agent Quotas
    max_agents = Column(Integer, default=5)
    max_concurrent_agents = Column(Integer, default=3)
    active_agents_count = Column(Integer, default=0)
    
    # Lead Quotas
    max_leads_per_month = Column(Integer, default=1000)
    leads_this_month = Column(Integer, default=0)
    
    # Storage Quotas
    max_storage_mb = Column(Integer, default=1000)  # 1GB default
    storage_used_mb = Column(Float, default=0.0)
    max_documents = Column(Integer, default=100)
    documents_count = Column(Integer, default=0)
    
    # Cost Limits
    max_cost_per_month_usd = Column(Float, default=100.0)
    cost_this_month_usd = Column(Float, default=0.0)
    
    # Rate Limiting
    rate_limit_per_second = Column(Integer, default=10)
    rate_limit_per_minute = Column(Integer, default=100)
    
    # Reset Tracking
    last_daily_reset = Column(DateTime(timezone=True))
    last_monthly_reset = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="quotas")
    
    def __repr__(self):
        return f"<CustomerQuota(customer_id={self.customer_id}, api_calls={self.api_calls_today}/{self.max_api_calls_per_day})>"
