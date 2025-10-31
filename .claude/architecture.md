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
class AgentState(TypedDict):
    lead_data: dict
    qualification_score: int
    enrichment_data: dict
    growth_insights: list
    marketing_plan: dict
    bdr_actions: list
    conversation_history: list
    current_agent: str
```

## 5. External Dependencies

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