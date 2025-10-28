# Architecture Decisions - sales-agent

## Technology Stack

### Language & Runtime
- **Python**: 3.13.7 for backend (FastAPI, agents, services)
- **TypeScript**: Frontend (React 18, strict mode)
- **Node.js**: v18+ for frontend build tooling

### Backend Framework
- **FastAPI**: Async web framework with automatic OpenAPI docs
- **SQLAlchemy**: ORM with PostgreSQL dialect
- **Pydantic**: Data validation and serialization
- **Alembic**: Database migration management

### Frontend Framework
- **React 18**: Component-based UI with hooks
- **Vite**: Fast build tool and dev server
- **Tailwind CSS v4**: Utility-first styling
- **Chart.js**: Data visualization

### Database & Caching
- **PostgreSQL 16**: Primary data store (Docker container)
- **Redis 7**: State persistence, pub/sub messaging, caching (Docker container)
- **PgAdmin**: Database administration UI (Docker container)

### AI & Agent Orchestration
- **LangChain**: Core framework for chains and tools
- **LangGraph**: StateGraph orchestration for complex agents
- **LangSmith**: Observability, tracing, debugging
- **Cerebras API**: Ultra-fast inference (633ms, llama3.1-8b)
- **Cartesia**: Text-to-speech for voice agents
- **Claude Sonnet 4**: Fallback for complex reasoning
- **DeepSeek v3**: Cost-effective research tasks

### Development Tools
- **Claude Code**: Primary AI-assisted IDE
- **Cursor**: Secondary IDE with MCP support
- **MCP Servers**: 8 specialized servers (Serena, Task Master, Sequential Thinking, etc.)
- **Docker Compose**: Local development infrastructure

## Design Patterns

### Agent Architecture: Hybrid Pattern

#### LCEL Chains (Simple Agents)
**When to use:**
- Linear workflows without branching
- Fast execution required (<1000ms)
- Simple input → process → output pattern

**Implementation:**
```python
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

chain = (
    RunnablePassthrough()
    | prompt_template
    | cerebras_llm
    | StrOutputParser()
    | score_extractor
)

result = await chain.ainvoke(input_data)
```

**Agents:**
1. **QualificationAgent** - Lead data → Cerebras → qualification score + reasoning
2. **EnrichmentAgent** - Lead + email → Apollo/LinkedIn tools → enriched data

#### LangGraph StateGraphs (Complex Agents)
**When to use:**
- Multi-step workflows with conditional logic
- Cyclic execution (research → validate → research again)
- Human-in-the-loop interrupts
- Parallel node execution
- Stateful conversations

**Implementation:**
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    current_step: str
    confidence: float

graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("analyze", analysis_node)
graph.add_conditional_edges(
    "validate",
    should_continue_research,
    {"continue": "research", "complete": END}
)

app = graph.compile(checkpointer=redis_checkpointer)
```

**Agents:**
1. **GrowthAgent** - Cyclic: research → analyze → validate → (loop if confidence low)
2. **MarketingAgent** - Parallel: generate angles → [draft messages || create subjects] → optimize
3. **BDRAgent** - Human-in-loop: qualify → calendar → propose → await confirmation → book
4. **ConversationAgent** - Voice-enabled: transcribe → intent → respond → TTS (Cartesia)

### Resilience Patterns

#### Circuit Breaker
**Purpose:** Prevent cascade failures when external services fail

**Implementation:** `backend/app/services/circuit_breaker.py`
- 3 states: CLOSED → OPEN → HALF_OPEN
- Failure threshold: 3-10 failures (provider-dependent)
- Recovery timeout: 30-120 seconds
- Used for: Cerebras, Apollo, LinkedIn, CRM APIs

#### Exponential Backoff Retry
**Purpose:** Handle transient failures gracefully

**Implementation:** `backend/app/services/retry_handler.py`
- Base delay: 1-2 seconds
- Max retries: 3
- Max delay: 60 seconds
- Strategy types: standard, conservative, aggressive

## Key Components

### Agent System

#### LangChain Integrations (`backend/app/services/langchain/`)
- **cerebras_llm.py** - Custom `BaseLLM` wrapper for Cerebras API
- **cartesia_tool.py** - LangChain `@tool` for text-to-speech

#### LangGraph Agents (`backend/app/services/langgraph/agents/`)
1. **qualification_agent.py** - LCEL chain for <1000ms lead scoring
2. **enrichment_agent.py** - Chain with Apollo/LinkedIn tools
3. **growth_agent.py** - Cyclic StateGraph for market analysis
4. **marketing_agent.py** - Parallel StateGraph for campaign generation
5. **bdr_agent.py** - Human-in-loop StateGraph for booking
6. **conversation_agent.py** - Voice-enabled StateGraph with Cartesia

#### LangGraph Framework (`backend/app/services/langgraph/`)
- **base.py** - Utilities (state helpers, error handling, streaming)
- **schemas.py** - TypedDict state definitions for all agents
- **tools.py** - LangChain `@tool` implementations (CRM, Apollo, LinkedIn)
- **redis_checkpointer.py** - State persistence for resumable workflows

#### Legacy Agents (`backend/app/services/agents/legacy/`)
- **base_agent.py** - Abstract BaseAgent class (preserved as reference)
- **analysis_agent.py** - Original analysis implementation
- **search_agent.py** - Original research implementation
- **synthesis_agent.py** - Original synthesis implementation

### CRM Integration

#### Providers (`backend/app/services/crm/`)
- **base.py** - Abstract `CRMProvider` interface
- **close.py** - Close CRM implementation (API key auth)
- **apollo.py** - Apollo.io enrichment (read-only)
- **linkedin.py** - LinkedIn scraper (Browserbase)

#### Sync Orchestration
- **crm_sync_service.py** - Bidirectional sync engine
  - Conflict resolution (last-write-wins)
  - Circuit breakers + retry logic
  - Dead letter queue for failed syncs
  - Celery Beat scheduling (Close: 2h, Apollo/LinkedIn: daily)

### API Layer (`backend/app/api/`)

#### Core Endpoints
- **health.py** - Health checks with service status
- **leads.py** - Lead CRUD operations
- **streaming.py** - WebSocket streaming API

#### LangGraph Endpoints (NEW)
- **langgraph_agents.py** - REST endpoints for all 6 agents
  - `POST /api/agents/qualify` - QualificationAgent
  - `POST /api/agents/enrich` - EnrichmentAgent
  - `POST /api/agents/growth` - GrowthAgent
  - `POST /api/agents/marketing` - MarketingAgent
  - `POST /api/agents/bdr` - BDRAgent
  - `POST /api/agents/conversation` - ConversationAgent
  - `WebSocket /ws/agents/{type}/{session_id}` - Streaming

#### CRM Endpoints
- **crm/close.py** - Close CRM operations
- **sync.py** - Sync monitoring and manual triggers
- **apollo.py** - Apollo enrichment
- **linkedin.py** - LinkedIn integration

## Data Flow

### Lead Qualification Flow (LCEL Chain)
```
User Input (Lead Data)
    ↓
FastAPI Endpoint: POST /api/agents/qualify
    ↓
QualificationAgent (LCEL Chain)
    ↓
[Input Validation] → [Prompt Template] → [Cerebras LLM] → [Score Extractor]
    ↓
Response: {score: 0-100, reasoning: str, confidence: float}
    ↓
Database: Save to agent_executions table
    ↓
LangSmith: Trace entire chain
```
**Target Latency:** <1000ms (Cerebras: 633ms average)

### Lead Enrichment Flow (Chain with Tools)
```
User Input (Lead + Email)
    ↓
FastAPI Endpoint: POST /api/agents/enrich
    ↓
EnrichmentAgent (LCEL Chain)
    ↓
[Validate Input] → [Apollo Tool] → [LinkedIn Tool] → [Merge Data] → [Validate Output]
    ↓
Response: {enriched_lead: {...}, sources: [...]}
    ↓
Database: Update leads table + CRM sync
    ↓
LangSmith: Trace chain + tool calls
```
**Target Latency:** <3000ms

### Growth Analysis Flow (StateGraph)
```
User Input (Company Name)
    ↓
FastAPI Endpoint: POST /api/agents/growth
    ↓
GrowthAgent (StateGraph)
    ↓
[Research Node] → [Analysis Node] → [Validation Node]
       ↑                                    ↓
       └──────── (if confidence < 0.8) ────┘
    ↓
Response: {opportunities: [...], confidence: float}
    ↓
Redis: Checkpoint state (resumable)
    ↓
Database: Save to agent_executions + langgraph_checkpoints
    ↓
LangSmith: Trace entire graph
```
**Target Latency:** <5000ms

### Conversation Flow (Voice-Enabled Graph)
```
User Input (Audio)
    ↓
WebSocket: ws://localhost:8001/ws/agents/conversation/{session_id}
    ↓
ConversationAgent (StateGraph)
    ↓
[Transcribe Node] → [Intent Node] → [Response Node] → [TTS Node (Cartesia)]
    ↑                                                          ↓
    └──────────────── (new audio input) ─────────────────────┘
    ↓
Streaming Output: {type: "audio_chunk", data: bytes}
    ↓
Redis: Persist conversation state
    ↓
LangSmith: Trace multi-turn conversation
```
**Target Latency:** <1000ms per turn

## External Dependencies

### AI APIs
- **Cerebras Cloud API**: Ultra-fast inference (633ms, $0.000006/request)
- **Anthropic Claude API**: Fallback reasoning ($0.001743/request)
- **DeepSeek API**: Cost-effective research ($0.00027/request)
- **Cartesia API**: Text-to-speech for voice agents
- **OpenRouter**: Multi-model routing (optional)

### CRM & Enrichment
- **Close CRM API**: Lead/contact management (API key auth)
- **Apollo.io API**: Contact enrichment (600 req/hour limit)
- **LinkedIn**: Profile scraping via Browserbase (100 req/day limit)

### Infrastructure
- **LangSmith**: Agent tracing and observability
- **Sentry**: Error tracking (optional)
- **Datadog**: APM and metrics (optional)

### Development
- **MCP Servers**: 8 servers for enhanced development
  - Serena (code intelligence)
  - Task Master AI (task management)
  - Sequential Thinking (problem-solving)
  - Context7 (library docs)
  - Shrimp (task planning)
  - Memory (knowledge storage)
  - Neon (database)
  - GitHub (repository)

## API Design

### REST Principles
- Resource-based URLs (`/api/agents/{type}`, `/api/leads/{id}`)
- HTTP verbs: GET (read), POST (create/action), PUT (update), DELETE (delete)
- Status codes: 200 (OK), 201 (Created), 400 (Bad Request), 404 (Not Found), 500 (Server Error)
- JSON request/response bodies
- OpenAPI documentation at `/api/docs`

### WebSocket Streaming
**Pattern:** Long-lived connections for real-time updates

**Endpoints:**
- `/ws/stream/{stream_id}` - Legacy streaming
- `/ws/agents/{agent_type}/{session_id}` - LangGraph agent streaming

**Message Format:**
```json
{
  "type": "chunk|state_update|complete|error",
  "content": "...",
  "metadata": {
    "node": "current_node_name",
    "confidence": 0.85,
    "tokens_used": 250
  }
}
```

### Agent API Specification

#### POST /api/agents/qualify
**Request:**
```json
{
  "company_name": "TechCorp Inc",
  "industry": "SaaS",
  "company_size": "50-200",
  "contact_title": "VP Engineering"
}
```

**Response:**
```json
{
  "score": 82,
  "reasoning": "Strong product fit...",
  "confidence": 0.91,
  "metadata": {
    "latency_ms": 627,
    "model": "llama3.1-8b",
    "cost_usd": 0.000006
  }
}
```

#### POST /api/agents/growth
**Request:**
```json
{
  "company_name": "TechCorp Inc",
  "research_depth": "standard"
}
```

**Response:**
```json
{
  "opportunities": [
    {
      "type": "product_fit",
      "description": "...",
      "priority": "high",
      "confidence": 0.88
    }
  ],
  "status": "complete",
  "confidence": 0.85,
  "metadata": {
    "nodes_executed": ["research", "analyze", "validate"],
    "total_latency_ms": 4523,
    "cost_usd": 0.00089
  }
}
```

## Database Schema

### Core Tables
- **leads** - Lead information and qualification scores
- **agent_executions** - Track all agent runs (legacy + LangGraph)
- **crm_contacts** - Synced CRM contact data
- **crm_sync_logs** - Audit trail for CRM sync operations

### LangGraph Tables (NEW)
- **langgraph_executions** - LangGraph-specific agent runs
- **langgraph_checkpoints** - State snapshots for resumable workflows
- **langgraph_tool_calls** - Tool invocation tracking

## Security Considerations

### API Keys & Secrets
- **Storage**: `.env` file (never committed to git)
- **Required Keys**:
  - `CEREBRAS_API_KEY` - Cerebras Cloud API
  - `LANGCHAIN_API_KEY` - LangSmith tracing
  - `CARTESIA_API_KEY` - Text-to-speech
  - `CLOSE_API_KEY` - Close CRM
  - `APOLLO_API_KEY` - Apollo.io
  - `ANTHROPIC_API_KEY` - Claude fallback (optional)
  - `DEEPSEEK_API_KEY` - Research (optional)

### Data Protection
- **PII Handling**: Compliance with data protection regulations
- **Encryption**: At-rest (database) and in-transit (HTTPS)
- **Access Control**: API key rotation, least-privilege principles
- **Audit Logging**: All CRM operations logged to database

### Rate Limiting
- **Apollo**: 600 requests/hour (tracked in Redis)
- **LinkedIn**: 100 requests/day (tracked in Redis)
- **Close CRM**: Variable by endpoint (RateLimit headers)
- **Cerebras**: No known limits (monitor usage)

## Performance Optimization

### Agent Performance Targets
| Agent | Pattern | Target Latency | Cost Target |
|-------|---------|---------------|-------------|
| Qualification | LCEL Chain | <1000ms | <$0.0001 |
| Enrichment | Chain + Tools | <3000ms | <$0.0005 |
| Growth | StateGraph | <5000ms | <$0.001 |
| Marketing | StateGraph | <4000ms | <$0.0008 |
| BDR | StateGraph | <2000ms/node | <$0.0005 |
| Conversation | StateGraph | <1000ms/turn | <$0.0001 |

### Optimization Strategies
1. **Cerebras for Speed**: Use for qualification, intent recognition (<1000ms)
2. **DeepSeek for Cost**: Use for research, analysis tasks ($0.00027)
3. **Parallel Execution**: LangGraph nodes run concurrently when possible
4. **Redis Caching**: Cache enrichment data, LLM responses (TTL: 24h)
5. **Database Indexing**: Compound indexes on high-query columns
6. **Connection Pooling**: PostgreSQL pool (min=5, max=20)

### Streaming Optimization
- Token-by-token streaming from Cerebras (TTFT: ~100ms)
- WebSocket batching: send every 10 tokens or 50ms
- Redis pub/sub for real-time updates
- Backpressure handling in graph nodes

## Deployment Strategy

### Local Development
```bash
# Start infrastructure
docker-compose up -d  # PostgreSQL + Redis + PgAdmin

# Start backend
python start_server.py

# Start frontend
cd frontend && npm run dev
```

### Production (Planned)
- **Platform**: Docker containers on cloud provider
- **Database**: Managed PostgreSQL (AWS RDS / Supabase / Neon)
- **Cache**: Managed Redis (AWS ElastiCache / Upstash)
- **Monitoring**: Sentry (errors) + Datadog (APM) + LangSmith (agents)
- **CI/CD**: GitHub Actions for automated testing and deployment

## Architectural Evolution

### Phase 1: Core Foundation ✅
- FastAPI backend with PostgreSQL
- Cerebras integration for fast inference
- Multi-agent architecture with BaseAgent pattern
- Circuit breakers + retry logic

### Phase 2: CRM Integration ✅
- Close CRM bidirectional sync
- Apollo.io enrichment
- LinkedIn scraper integration
- Automated sync orchestration with Celery Beat

### Phase 3: LangChain/LangGraph Migration 🚧 (Current)
- Migrate to LangChain LCEL chains (simple agents)
- Adopt LangGraph StateGraphs (complex agents)
- Implement LangSmith tracing
- Create hybrid pattern (chains + graphs)
- Preserve legacy agents for reference

### Future Phases
- **Phase 4**: Frontend-backend integration with WebSocket streaming
- **Phase 5**: Production deployment with monitoring
- **Phase 6**: Analytics dashboards and reporting

---

**Last Updated**: 2025-01-26
**Architecture Status**: Phase 3 (LangChain/LangGraph Migration) in progress
