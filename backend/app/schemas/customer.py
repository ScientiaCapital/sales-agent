"""
Pydantic schemas for customer and knowledge base APIs
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime


# === Customer Registration Schemas ===

class CustomerRegistrationRequest(BaseModel):
    """Request schema for customer registration"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    company_name: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = Field(None, max_length=255)
    company_website: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    subscription_tier: Optional[str] = Field("free", pattern="^(free|starter|pro|enterprise)$")


class CustomerRegistrationResponse(BaseModel):
    """Response schema for customer registration"""
    customer_id: int
    firebase_uid: str
    email: str
    company_name: str
    api_key: str  # Shown only once during registration
    subscription_tier: str
    status: str
    created_at: str
    
    model_config = ConfigDict(from_attributes=True)


# === Agent Deployment Schemas ===

class AgentDeploymentRequest(BaseModel):
    """Request schema for deploying an agent"""
    agent_name: str = Field(..., min_length=1, max_length=255)
    agent_type: str = Field(..., description="Agent type: lead_qualifier, outreach, researcher, etc.")
    agent_role: Optional[str] = None
    config: Optional[Dict] = Field(default_factory=dict)
    model: Optional[str] = Field("llama3.1-8b", description="AI model to use")


class AgentDeploymentResponse(BaseModel):
    """Response schema for agent deployment"""
    agent_id: int
    deployment_id: str
    agent_name: str
    agent_type: str
    agent_role: Optional[str]
    status: str
    model: str
    deployed_at: str
    
    model_config = ConfigDict(from_attributes=True)


class AgentPerformance(BaseModel):
    """Agent performance metrics"""
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    average_latency_ms: Optional[float]


class AgentResourceUsage(BaseModel):
    """Agent resource usage"""
    total_api_calls: int
    total_cost_usd: float


class AgentStatusResponse(BaseModel):
    """Response schema for agent status"""
    agent_id: int
    deployment_id: str
    agent_name: str
    agent_type: str
    agent_role: Optional[str]
    status: str
    model: str
    performance: AgentPerformance
    resource_usage: AgentResourceUsage
    deployed_at: str
    last_active_at: Optional[str]
    terminated_at: Optional[str]


# === Knowledge Base Schemas ===

class DocumentUploadResponse(BaseModel):
    """Response schema for document upload"""
    document_id: str
    filename: str
    file_url: str
    text_preview: str
    text_length: int
    embedding_dimension: int
    icp_criteria: Dict
    created_at: str


class ICPCriteria(BaseModel):
    """ICP (Ideal Customer Profile) criteria extracted from documents"""
    target_industries: List[str]
    company_sizes: List[str]
    decision_makers: List[str]
    target_regions: List[str]
    extracted_at: str


class DocumentSearchResult(BaseModel):
    """Search result for similar documents"""
    document_id: str
    filename: str
    file_url: str
    icp_criteria: Dict
    created_at: str
    similarity_score: float


class DocumentSearchRequest(BaseModel):
    """Request schema for document similarity search"""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: Optional[int] = Field(10, ge=1, le=100, description="Maximum results")
    similarity_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity score")


class DocumentListResponse(BaseModel):
    """Response schema for listing customer documents"""
    document_id: str
    customer_id: int
    filename: str
    content_type: Optional[str]
    file_size: Optional[int]
    firebase_url: Optional[str]
    text_length: Optional[int]
    icp_data: Optional[Dict]
    processing_status: str
    created_at: str
    
    model_config = ConfigDict(from_attributes=True)


# === Customer Quota Schemas ===

class CustomerQuotaResponse(BaseModel):
    """Response schema for customer quotas"""
    customer_id: int
    
    # API Quotas
    max_api_calls_per_day: int
    max_api_calls_per_month: int
    api_calls_today: int
    api_calls_this_month: int
    
    # Agent Quotas
    max_agents: int
    max_concurrent_agents: int
    active_agents_count: int
    
    # Lead Quotas
    max_leads_per_month: int
    leads_this_month: int
    
    # Storage Quotas
    max_storage_mb: int
    storage_used_mb: float
    max_documents: int
    documents_count: int
    
    # Cost Limits
    max_cost_per_month_usd: float
    cost_this_month_usd: float
    
    # Rate Limiting
    rate_limit_per_second: int
    rate_limit_per_minute: int
    
    model_config = ConfigDict(from_attributes=True)
