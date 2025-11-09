# Sales Agent Architecture

## 1. Technology Stack

### Core Framework & Runtime
- **Language**: Python 3.13
- **Web Framework**: FastAPI (production-ready async API framework)
- **AI/ML Framework**: LangGraph (multi-agent orchestration)
- **AI Model Integration**: Likely OpenAI GPT, Anthropic Claude, or local models via Cerebras inference

### Data Layer
- **Primary Database**: PostgreSQL (transactional data, agent state persistence)
- **Cache & Session Store**: Redis (checkpointing, real-time state management)
- **Vector Database**: (Inferred) Likely Pinecone, Chroma, or Weaviate for semantic search

### Infrastructure & Tooling
- **Testing Framework**: pytest (confirmed by "Has Tests: True")
- **API Documentation**: Auto-generated FastAPI Swagger/OpenAPI
- **Monitoring**: Likely Prometheus + Grafana (production metrics)
- **Message Queue**: (Inferred) Redis Pub/Sub or Celery for async tasks

## 2. Design Patterns

### Primary Patterns Identified
- **Factory Pattern**: Agent creation and initialization
- **Abstract Base Class (ABC)**: Unified agent interface across 6 specialized types
- **Circuit Breaker**: Fault tolerance for external API calls (CRM, enrichment services)
- **State Machine**: LangGraph StateGraph for complex multi-step workflows
- **Observer Pattern**: Real-time streaming and event publishing
- **Strategy Pattern**: Interchangeable AI models and inference engines

### Architectural Patterns
- **Multi-Agent System (MAS)**: 6 specialized agents with distinct responsibilities
- **Hybrid Architecture**: LCEL Chains (simple tasks) + StateGraphs (complex workflows)
- **Microservices-inspired**: Independent agent execution with shared state
- **Event-Driven**: Redis-based checkpointing and state synchronization

## 3. Key Components

### Core Agent System
```
sales-agent/
├── agents/
│   ├── qualification_agent.py     # 633ms lead scoring
│   ├── enrichment_agent.py        # Apollo + LinkedIn data
│   ├── growth_analysis_agent.py   # Market opportunity research
│   ├── marketing_agent.py         # Multi-channel campaigns
│   ├── bdr_workflow_agent.py      # Human-in-loop booking
│   └── conversation_agent.py      # Voice-enabled chat
├── core/
│   ├── agent_factory.py           # Factory pattern implementation
│   ├── base_agent.py              # ABC for all agents
│   └── circuit_breaker.py         # Fault tolerance
├── graph/
│   ├── state_graphs.py            # LangGraph StateGraph definitions
│   └── workflow_orchestrator.py   # Multi-agent coordination
└── api/
    ├── routes/
    │   └── langgraph.py           # FastAPI endpoint handlers
    └── models/                    # Pydantic request/response models
```

### Infrastructure Components
- **Redis Checkpointing**: Persistent agent state across restarts
- **Cerebras Inference**: Ultra-fast model execution (sub-second responses)
- **CRM Integrations**: Salesforce, HubSpot, or custom CRM connectors
- **Voice Processing**: STT/TTS integration for conversation agent

## 4. Data Flow

### Lead Processing Pipeline
```
1. Lead Ingestion
   ↓
2. Qualification Agent (633ms)
   ├── Company analysis
   ├── Industry scoring
   └── Tier classification
   ↓
3. Enrichment Agent (<3s)
   ├── Apollo.io data enrichment
   ├── LinkedIn profile analysis
   └── Contact information validation
   ↓
4. Growth Analysis Agent (<5s)
   ├── Market opportunity assessment
   ├── Competitive landscape
   └── Growth potential scoring
   ↓
5. Marketing Agent (<4s)
   ├── Campaign strategy generation
   ├── Multi-channel planning
   └── Content personalization
   ↓
6. BDR Workflow Agent (<2s/node)
   ├── Human-in-loop coordination
   ├── Meeting scheduling
   └── Follow-up automation
   ↓
7. Conversation Agent (<1s/turn)
   ├── Voice-enabled interactions
   ├── Real-time responses
   └── Intent recognition
```

### State Management Flow
```python
# LangGraph State Definition
$1

## 4.5. Pipeline Testing System

### Architecture (Phase 6 - In Development)
```
Pipeline Test Flow:
1. CSV Lead Import → LeadCSVImporter
2. Pipeline Execution → PipelineOrchestrator
   ├── Qualification Agent
   ├── Enrichment Agent  
   ├── Deduplication Check
   └── Close CRM Sync
3. Metrics Tracking → PipelineTestExecution (database)
4. API Response → PipelineTestResponse (schema)
```

### Database Model
```python
class PipelineTestExecution(Base):
    """Tracks end-to-end pipeline test runs"""
    id: int
    lead_name: str
    csv_index: Optional[int]
    
    # Results
    success: bool
    error_stage: Optional[str]
    error_message: Optional[Text]
    
    # Performance Metrics
    total_latency_ms: int
    total_cost_usd: float
    stages_json: JSON  # Per-stage timing and cost
    
    # Test Configuration
    stop_on_duplicate: bool
    skip_enrichment: bool
    create_in_crm: bool
    dry_run: bool
```

### API Schemas
```python
class PipelineTestRequest(BaseModel):
    lead: Dict[str, Any]
    options: PipelineTestOptions = PipelineTestOptions()

class PipelineTestResponse(BaseModel):
    success: bool
    total_latency_ms: int
    total_cost_usd: float
    lead_name: str
    stages: Dict[str, PipelineStageResult]
    error_stage: Optional[str]
    timeline: Optional[List[Dict]]

class CSVLeadImportRequest(BaseModel):
    csv_path: str
    lead_index: int  # 0-199 for dealer-scraper dataset
    options: PipelineTestOptions
```

### Components
- **LeadCSVImporter**: Loads dealer-scraper CSV, maps fields to pipeline format
- **PipelineOrchestrator**: Coordinates 4-stage execution with timing/cost tracking
- **Test API Endpoints**: `/api/leads/test-pipeline`, `/api/leads/test-pipeline/quick`

## 4.6. Email Discovery System (✅ Sub-Phase 2A Complete)

### Architecture
```
Email Discovery Flow:
1. Lead Input (no email) → QualificationAgent
2. Email Extraction Attempt → EmailExtractor Service
   ├── Website Scraping (/, /contact, /contact-us, /about)
   ├── Multi-Pattern Detection (mailto, standard, obfuscated)
   ├── Smart Prioritization (personal > business > generic)
   └── Spam Filtering (noreply@, info@, admin@, etc.)
3. Metadata Propagation → qualification_result.metadata
4. Pipeline Extraction → PipelineOrchestrator
5. Lead Update → request.lead["email"] = extracted_email
6. Enrichment Agent → receives extracted email
```

### EmailExtractor Service
```python
class EmailExtractor:
    """Web scraping-based email discovery service (185 lines)"""

    async def extract_emails(self, website_url: str) -> List[str]:
        """
        Multi-page email extraction with smart prioritization

        Returns:
            List of emails sorted by priority:
            1. Personal names (john.doe@example.com)
            2. Business roles (sales@, contact@)
            3. Generic addresses (info@, hello@)

        Features:
        - Parallel page crawling (main + 3 subpages)
        - 10-second timeout per request
        - Graceful failure (returns empty list)
        - BeautifulSoup + regex pattern matching
        """
```

### Integration Points

#### QualificationAgent (lines 487-507, 694)
```python
# Email extraction during qualification
if not contact_email and company_website:
    extracted_emails = await self.email_extractor.extract_emails(company_website)
    if extracted_emails:
        contact_email = extracted_emails[0]
        notes += f"\nEmails found: {', '.join(extracted_emails[:3])}"

# Metadata return (line 694)
metadata = {
    "extracted_email": contact_email,  # CRITICAL for pipeline
    # ... other metadata
}
```

#### PipelineOrchestrator
**Line 187** - Pass contact_email to trigger extraction:
```python
result = await self.qualification_agent.qualify(
    company_name=lead.get("name"),
    company_website=lead.get("website"),
    contact_email=lead.get("email") or lead.get("contact_email"),  # ✅ Added
    # ... other parameters
)
```

**Lines 97-102** - Extract from metadata and update lead:
```python
if qual_result.output and "metadata" in qual_result.output:
    extracted_email = qual_result.output["metadata"].get("extracted_email")
    if extracted_email and not request.lead.get("email"):
        request.lead["email"] = extracted_email
        logger.info(f"Using extracted email for enrichment: {extracted_email}")
```

### Performance Characteristics
- **Latency**: +2-4 seconds per lead (non-blocking)
- **Cost**: $0 (web scraping, no API costs)
- **Success Rate**: ~80% for contractor/SMB leads
- **Caching**: Redis qualification cache prevents redundant scraping
- **Failure Mode**: Non-blocking - qualification continues without email

### Test Coverage
```python
# Unit Tests (185 lines): tests/services/test_email_extractor.py
- test_extract_mailto_link_emails()
- test_extract_standard_format_emails()
- test_extract_obfuscated_emails()
- test_extract_multiple_emails()
- test_prioritize_personal_over_generic()
- test_filter_generic_emails()
- test_handle_404_gracefully()

# Integration Tests (139 lines): tests/services/langgraph/test_qualification_email_integration.py
- test_qualification_extracts_email_when_missing()
- test_qualification_skips_extraction_when_email_provided()
- test_qualification_continues_without_email_on_failure()
```

### Database Impact
**None** - Email extraction is stateless and relies only on:
- Redis caching (qualification results)
- No new tables or migrations required

### Next: Sub-Phase 2B (Hunter.io Fallback)
```python
class HunterService:
    """Hunter.io API integration for email discovery"""

    async def find_email(self, domain: str, first_name: str = None,
                        last_name: str = None) -> Optional[str]:
        """
        Fallback email discovery via Hunter.io Email Finder API
        Cost: $0.01-0.02 per lookup
        Rate Limits: 50 requests/month (free), 500/month (starter)
        """
```

**Integration Strategy**:
1. Website scraping (EmailExtractor) - Try first (free)
2. Hunter.io API (HunterService) - Fallback if scraping fails (paid)
3. Cost tracking - Track Hunter.io costs separately in metadata
4. Graceful degradation - Continue without email if both fail

$2

### AI/ML Dependencies
```python
# Core AI Framework
langgraph == "latest"          # Multi-agent orchestration
langchain == "0.1.x"           # LCEL chains and components
openai == "1.x"                # GPT model integration
anthropic == "0.7.x"           # Claude model integration

# Optional Local Inference
cerebras-sdk == "latest"       # Ultra-fast inference engine
```

### Data & Infrastructure
```python
# Database & Cache
psycopg2-binary == "2.9.x"     # PostgreSQL adapter
redis == "5.0.x"               # Redis client for checkpointing

# Web Framework
fastapi == "0.104.x"           # API framework
uvicorn == "0.24.x"            # ASGI server
pydantic == "2.5.x"            # Data validation

# External Services
requests == "2.31.x"           # HTTP client for CRM APIs
aiohttp == "3.9.x"             # Async HTTP for enrichment
```

### Development & Testing
```python
pytest == "7.4.x"              # Testing framework
pytest-asyncio == "0.21.x"     # Async test support
httpx == "0.25.x"              # Test HTTP client
```

## 6. API Design

### FastAPI Endpoint Structure
```python
# Main LangGraph Invocation Endpoint
@app.post("/api/langgraph/invoke")
async def invoke_agent(
    agent_type: AgentType,
    input: AgentInput,
    stream: bool = False
) -> AgentResponse:
    """
    Invoke specific agent type with input data
    Supports real-time streaming for conversation agent
    """

# Agent Management Endpoints
@app.get("/api/agents/status")
async def get_agent_status() -> Dict[str, AgentStatus]

@app.post("/api/agents/{agent_type}/reset")
async def reset_agent_state(agent_type: AgentType)

# Monitoring Endpoints  
@app.get("/metrics")
async def get_performance_metrics() -> PerformanceMetrics

@app.get("/health")
async def health_check() -> HealthStatus
```

### Request/Response Models
```python
class AgentInput(BaseModel):
    company_name: str
    industry: str
    company_size: str
    contact_info: Optional[Dict] = None

class QualificationResponse(BaseModel):
    score: int
    tier: Literal["A", "B", "C", "D"]
    reasoning: str
    processing_time: float
```

## 7. Database Schema

### PostgreSQL Tables
```sql
-- Leads and Company Data
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    company_size VARCHAR(50),
    qualification_score INTEGER,
    tier VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Agent Execution History
CREATE TABLE agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    agent_type VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    processing_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    executed_at TIMESTAMP DEFAULT NOW()
);

-- Enrichment Data Cache
CREATE TABLE enrichment_cache (
    company_name VARCHAR(255) PRIMARY KEY,
    apollo_data JSONB,
    linkedin_data JSONB,
    market_data JSONB,
    cached_at TIMESTAMP DEFAULT NOW(),
    ttl_hours INTEGER DEFAULT 24
);
```

### Redis Schema
```python
# Checkpointing Keys
CHECKPOINT_PREFIX = "agent:checkpoint:"
# Format: agent:checkpoint:{lead_id}:{agent_type}

# Session Management
SESSION_PREFIX = "session:"
# Format: session:{session_id}:state

# Rate Limiting
RATE_LIMIT_PREFIX = "ratelimit:"
# Format: ratelimit:{agent_type}:{hour}
```

## 8. Security Considerations

### FastAPI Security
```python
# API Security Middleware
middleware = [
    Middleware(SessionMiddleware, secret_key=settings.secret_key),
    Middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts),
    Middleware(CORSMiddleware, allow_origins=settings.cors_origins)
]

# Authentication (if required)
@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    # JWT token validation or API key authentication
    pass
```

### Data Security
- **PII Handling**: Mask sensitive data in logs and caching
- **CRM Integration**: Secure credential storage using environment variables
- **Redis Security**: Password protection and network isolation
- **Data Encryption**: TLS for all external API calls

### AI Security
- **Prompt Injection**: Input validation and sanitization
- **Model Safety**: Content filtering and output validation
- **Rate Limiting**: Prevent abuse of expensive AI operations

## 9. Performance Optimization

### Latency Optimization Strategies
```python
# 1. Cerebras Inference Optimization
cerebras_config = {
    "batch_size": 1,  # Real-time optimization
    "precision": "float16",
    "optimization_level": "max_speed"
}

# 2. Redis Checkpointing Strategy
redis_config = {
    "checkpoint_ttl": 3600,  # 1 hour retention
    "compression": True,     # Reduce memory usage
    "lazy_saving": True      # Non-blocking writes
}

# 3. Database Optimization
indexes = [
    "CREATE INDEX idx_leads_industry ON leads(industry)",
    "CREATE INDEX idx_agent_executions_agent_type ON agent_executions(agent_type)",
    "CREATE INDEX idx_enrichment_cache_ttl ON enrichment_cache(cached_at)"
]
```

### Caching Strategy
- **L1 Cache**: In-memory agent state (short-lived)
- **L2 Cache**: Redis checkpointing (medium-term persistence)
- **L3 Cache**: PostgreSQL enrichment data (long-term storage)

### Concurrent Execution
```python
# Async Agent Execution
async def execute_agent_pipeline(lead_data: Dict) -> Dict:
    qualification = await qualification_agent.process(lead_data)
    enrichment = await enrichment_agent.process(lead_data)
    
    # Parallel execution where possible
    results = await asyncio.gather(
        qualification,
        enrichment,
        return_exceptions=True
    )
```

## 10. Deployment Strategy

### Current State (No Docker)
```bash
# Manual Deployment Process
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database Setup
python scripts/setup_database.py
python scripts/seed_initial_data.py

# Service Startup
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Recommended Production Deployment

#### Containerization Strategy
```dockerfile
# Multi-stage Dockerfile recommendation
FROM python:3.13-slim as builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.13-slim
COPY --from=builder /root/.local /root/.local
COPY . /app
WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### Infrastructure Requirements
```yaml
# docker-compose.yml recommendation
version: '3.8'
services:
  sales-agent:
    build: .
    ports:
      - "8001:8001"
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/sales_agent
      - REDIS_URL=redis://redis:6379

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=sales_agent
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

  redis:
    image: redis:7-alpine
```

#### Scaling Strategy
- **Horizontal Scaling**: Stateless agents allow multiple instances
- **Load Balancing**: Nginx or cloud load balancer for API distribution
- **Database Connection Pooling**: PgBouncer for PostgreSQL
- **Redis Cluster**: For high-availability checkpointing

### Monitoring & Observability
```python
# Performance Metrics Collection
metrics = {
    "agent_latency": Histogram('agent_processing_seconds', 
                              ['agent_type'], 
                              buckets=[0.1, 0.5, 1.0, 2.0, 5.0]),
    "success_rate": Counter('agent_success_total', ['agent_type']),
    "error_rate": Counter('agent_errors_total', ['agent_type', 'error_code'])
}
```

This architecture provides a production-ready foundation for the multi-agent sales automation platform while maintaining the sub-second performance characteristics demonstrated in the performance metrics.