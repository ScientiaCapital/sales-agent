# Sales Agent - Claude Code Development Guidelines

## Project Overview

AI-powered sales automation platform with **production-ready CRM integration**, multi-agent architecture, and intelligent outreach automation. Features Close CRM, Apollo.io, and LinkedIn integrations with automated bidirectional sync, voice capabilities, document processing, and knowledge base.

**Current Status**: ✅ Phase 3 Complete - LangGraph migration with 6 specialized agents (QualificationAgent, EnrichmentAgent, GrowthAgent, MarketingAgent, BDRAgent, ConversationAgent), Redis checkpointing, database tracking, streaming support, and comprehensive testing suite.

## Architecture Principles

### Ultra-Fast Streaming First
- **Primary**: Cerebras Inference API (**633ms streaming** - 39% under 1000ms target!)
- **Model**: llama3.1-8b via Cerebras Cloud API
- **Cost**: $0.000006 per streaming request
- **Pattern**: OpenAI SDK compatible + AsyncAnthropic streaming

### Current Working Stack
```
Backend: FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
Frontend: React 18 + TypeScript + Vite + Tailwind CSS v4
AI Providers: Cerebras, Claude, DeepSeek, Ollama
CRM Integrations: Close CRM (API key, bidirectional sync), Apollo.io (enrichment), LinkedIn (scraping)
CRM Sync: Automated bidirectional sync with conflict resolution, circuit breakers, Celery Beat scheduling
Voice: Cartesia TTS + voice agent system
Documents: PDF/text processing + knowledge base
Services: Research pipeline, campaign automation, lead scoring
Resilience: Circuit Breakers + Exponential Backoff Retry
Infrastructure: Docker Compose (PostgreSQL, Redis, PgAdmin), RunPod vLLM
Testing: pytest with 96% coverage
```

### Multi-Provider AI Stack
```
Ultra-Fast: Cerebras (633ms, $0.000006) - Lead qualification
Premium: Claude Sonnet 4 (4026ms, $0.001743) - Complex reasoning
Research: DeepSeek v3 ($0.00027) - Cost-effective analysis
Local: Ollama (500ms, $0) - Private inference
Development: Claude Sonnet 4.5 - Code generation
```

## LangGraph Architecture

### Hybrid Agent Pattern

The platform uses a hybrid approach combining LangChain LCEL chains and LangGraph StateGraphs:

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
    | post_processor
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

### Performance Targets
- Qualification: <1000ms (Cerebras chain)
- Enrichment: <3000ms (Apollo + LinkedIn)
- Growth Analysis: <5000ms (DeepSeek graph)
- Marketing: <4000ms (parallel nodes)
- BDR: <2000ms per node
- Conversation: <1000ms per turn (Cerebras + Cartesia)

### Cost Targets
- Cerebras: <$0.0001 per qualification
- DeepSeek: <$0.001 per research operation
- Voice (Cartesia): Per TTS call pricing

### State Management
- **Redis Checkpointing**: Persistent state for resumable workflows
- **Database Tracking**: Execution logs, tool calls, performance metrics
- **LangSmith Tracing**: Observability and debugging
- **Streaming Support**: Real-time token delivery via SSE and WebSocket

### Tool Integration
All tools use `@tool` decorator:
```python
from langchain.tools import tool
from typing import Annotated

@tool
async def search_crm(
    company_name: Annotated[str, "The company name to search for"]
) -> dict:
    """Search Close CRM for company information."""
    # Implementation using existing CRM services
    pass
```

**Required Tools:**
- `search_crm` - Query Close CRM
- `enrich_with_apollo` - Apollo.io enrichment
- `scrape_linkedin` - LinkedIn profile data
- `analyze_tech_stack` - Technology stack analysis
- `generate_voice` - Cartesia TTS
- `search_web` - Web research

## Development Workflow

### Daily Routine
1. Start infrastructure: `docker-compose up -d`
2. Start Celery worker (optional): `cd backend && python celery_worker.py &`
3. Start server: `python start_server.py`
4. Run tests: `python test_api.py` and `python test_streaming.py`
5. Implement features following existing patterns
6. Update Task Master if using project management

### Feature Development
1. **Plan** - Review roadmap in README.md
2. **Research** - Use DeepSeek for cost-effective research if needed
3. **Implement** - Follow existing FastAPI patterns in `backend/app/`
4. **Test** - Add tests in `backend/tests/` and streaming tests
5. **Document** - Update README and tasks

## Technical Stack

### Core Dependencies
- **FastAPI 0.115.0** - REST API framework with WebSocket support
- **SQLAlchemy** - ORM for PostgreSQL
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **AsyncAnthropic 0.39.0** - Claude streaming SDK
- **OpenAI SDK** - Cerebras integration (via custom base_url)
- **Celery** - Async task queue with Redis broker
- **Redis 7** - Caching + pub/sub messaging
- **psycopg3** - PostgreSQL adapter
- **Python 3.13.7** - Runtime
- **Docker Compose** - Infrastructure orchestration (PostgreSQL + Redis + PgAdmin)

### Cerebras Integration

The Cerebras service is already implemented in `backend/app/services/cerebras.py`:

```python
from openai import OpenAI
import os

# Cerebras uses OpenAI SDK with custom base_url
client = OpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

# Ultra-fast inference call
response = client.chat.completions.create(
    model="llama3.1-8b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=500,
    temperature=0.7
)
```

## Code Organization

### Current Directory Structure
```
sales-agent/
├── backend/
│   ├── app/
│   │   ├── api/                        # FastAPI endpoints
│   │   │   ├── health.py              # Health checks
│   │   │   ├── leads.py               # Lead management
│   │   │   ├── streaming.py           # WebSocket streaming
│   │   │   ├── voice.py               # Voice agent endpoints
│   │   │   ├── transfer.py            # Agent transfer
│   │   │   ├── apollo.py              # Apollo enrichment API
│   │   │   ├── linkedin.py            # LinkedIn integration
│   │   │   ├── campaigns.py           # Campaign management
│   │   │   ├── contacts.py            # Contact management
│   │   │   ├── customers.py           # Customer endpoints
│   │   │   ├── documents.py           # Document processing
│   │   │   ├── knowledge.py           # Knowledge base API
│   │   │   ├── refine.py              # Iterative refinement
│   │   │   ├── reports.py             # Report generation
│   │   │   ├── research.py            # Research pipeline
│   │   │   ├── sync.py                # CRM sync monitoring
│   │   │   └── crm/                   # CRM endpoints
│   │   │       ├── __init__.py
│   │   │       └── hubspot.py         # HubSpot OAuth (COMMENTED OUT - replaced with Close CRM)
│   │   ├── core/                       # Configuration
│   │   │   ├── config.py              # Settings
│   │   │   └── logging.py             # Structured logging
│   │   ├── models/                     # SQLAlchemy models
│   │   │   ├── database.py            # DB setup
│   │   │   ├── lead.py                # Lead model
│   │   │   ├── api_call.py            # API tracking
│   │   │   ├── agent_models.py        # Multi-agent tracking
│   │   │   ├── campaign.py            # Campaign models
│   │   │   ├── crm.py                 # CRM models
│   │   │   ├── customer_models.py     # Customer models
│   │   │   ├── report.py              # Report models
│   │   │   ├── social_media.py        # Social media models
│   │   │   └── voice_models.py        # Voice models
│   │   ├── schemas/                    # Pydantic schemas
│   │   │   └── lead.py                # Lead validation
│   │   └── services/                   # Business logic
│   │       ├── cerebras.py            # Cerebras integration
│   │       ├── claude_streaming.py    # Claude streaming
│   │       ├── model_router.py        # Intelligent routing
│   │       ├── llm_router.py          # LLM routing
│   │       ├── base_agent.py          # Abstract agent class
│   │       ├── agent_transfer.py      # Agent handoff
│   │       ├── voice_agent.py         # Voice agent
│   │       ├── circuit_breaker.py     # Resilience pattern
│   │       ├── retry_handler.py       # Exponential backoff
│   │       ├── apollo.py              # Apollo service
│   │       ├── linkedin_oauth.py      # LinkedIn OAuth
│   │       ├── linkedin_scraper.py    # LinkedIn scraper
│   │       ├── document_processor.py  # Document processing
│   │       ├── knowledge_base.py      # Knowledge base
│   │       ├── lead_scorer.py         # Lead scoring
│   │       ├── report_generator.py    # Report generation
│   │       ├── research_pipeline.py   # Research pipeline
│   │       ├── iterative_refinement.py # Iterative refinement
│   │       ├── social_media_scraper.py # Social scraping
│   │       ├── customer_service.py    # Customer service
│   │       ├── cartesia_service.py    # Voice TTS
│   │       ├── csv_importer.py        # CSV import
│   │       ├── runpod_vllm.py         # RunPod vLLM
│   │       ├── runpod_storage.py      # RunPod storage
│   │       ├── agents/                # Specialized agents
│   │       │   ├── __init__.py
│   │       │   ├── analysis_agent.py
│   │       │   ├── search_agent.py
│   │       │   └── synthesis_agent.py
│   │       ├── outreach/              # Outreach services
│   │       │   ├── __init__.py
│   │       │   ├── campaign_service.py
│   │       │   └── message_generator.py
│   │       ├── crm_sync_service.py    # CRM sync orchestration
│   │       └── crm/                   # CRM integrations
│   │           ├── __init__.py
│   │           ├── base.py            # Abstract CRM interface
│   │           ├── close.py           # Close CRM provider
│   │           ├── apollo.py          # Apollo provider
│   │           ├── linkedin.py        # LinkedIn provider
│   │           └── hubspot.py         # HubSpot provider (COMMENTED OUT)
│   ├── alembic/                        # Database migrations
│   ├── tests/                          # Test suite
│   ├── requirements.txt
│   └── celery_worker.py               # Celery worker
├── frontend/                           # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/                # React components
│   │   └── pages/                    # Page components
│   └── package.json
├── .taskmaster/                        # Task management
├── .claude/                            # Claude Code config
├── .env                               # API keys (DO NOT COMMIT)
├── docker-compose.yml                 # Infrastructure
├── start_server.py                    # Server launcher
├── test_api.py                       # Integration tests
├── CRM_INTERFACE_SUMMARY.md          # CRM implementation docs
└── README.md
```

### API Endpoints

Current working endpoints (24+ endpoints across multiple domains):

#### Core Endpoints
```
GET  /                      # Root endpoint
GET  /api/health           # Health check with service status
GET  /api/docs             # OpenAPI documentation
```

#### Lead Management
```
POST /api/leads/qualify    # Qualify a lead with Cerebras
GET  /api/leads/           # List all leads
```

#### CRM Integration
```
POST /api/apollo/...       # Apollo.io enrichment
GET  /api/linkedin/...     # LinkedIn integration
GET  /api/contacts/...     # Contact management
```

#### CRM Sync Operations
```
GET  /api/sync/status            # All platforms sync status
GET  /api/sync/status/{platform} # Platform-specific status
GET  /api/sync/history           # Sync operation history
POST /api/sync/trigger           # Manual sync trigger
GET  /api/sync/metrics           # Aggregate sync metrics
GET  /api/sync/health            # Sync system health
```

#### Campaigns & Outreach
```
GET  /api/campaigns/...    # Campaign management
POST /api/campaigns/...    # Create campaign
```

#### Research & Documents
```
POST /api/research/...     # Research pipeline
POST /api/documents/...    # Document processing
GET  /api/knowledge/...    # Knowledge base queries
POST /api/refine/...       # Iterative refinement
POST /api/reports/...      # Report generation
```

#### Voice & Agents
```
POST /api/voice/...        # Voice agent endpoints
POST /api/transfer/...     # Agent transfer/handoff
POST /api/streaming/...    # Streaming endpoints
```

#### LangGraph Agents (NEW)
```
POST /api/langgraph/invoke         # Invoke agent and return complete response
POST /api/langgraph/stream         # Stream agent execution via SSE
GET  /api/langgraph/state/{thread_id} # Retrieve conversation state from checkpoint
```

**Supported Agents:**
- `qualification` - Lead qualification with Cerebras AI (<1000ms)
- `enrichment` - Contact enrichment with Apollo/LinkedIn tools (<3000ms)
- `growth` - Market analysis with cyclic research (<5000ms)
- `marketing` - Multi-channel campaign generation (<4000ms)
- `bdr` - Human-in-loop meeting booking (<2000ms/node)
- `conversation` - Voice-enabled conversational AI (<1000ms/turn)

#### Customer Management
```
GET  /api/customers/...    # Customer endpoints
```

## CRM Sync System

### Overview

The CRM sync system provides automated bidirectional synchronization between the local PostgreSQL database and multiple CRM platforms (Close CRM, Apollo.io, LinkedIn). Built with production-grade resilience patterns including circuit breakers, exponential backoff retry, and dead letter queues.

**Key Features:**
- **Multi-Platform Support**: Close CRM (full CRUD), Apollo.io (enrichment), LinkedIn (scraping)
- **Automated Scheduling**: Celery Beat periodic syncs (Close: 2 hours, Apollo/LinkedIn: daily)
- **Conflict Resolution**: Last-write-wins strategy with manual review flagging for critical fields
- **Resilience**: Circuit breakers + exponential backoff retry for fault tolerance
- **Monitoring**: Real-time status, metrics, and health check endpoints
- **Manual Control**: Trigger syncs on-demand via REST API

### Close CRM Integration

**Authentication**: API key via Basic auth (`Authorization: Basic {base64(api_key:)}`)

**Base URL**: `https://api.close.com/api/v1/`

**Data Model**: Leads contain multiple contacts. Each lead has a `name` field and a `contacts[]` array with contact details (emails, phones, etc.)

**Sync Operations**:
```python
# Bidirectional sync (import + export)
from app.services.crm_sync_service import CRMSyncService

sync_service = CRMSyncService(db=db)
result = await sync_service.sync_platform(
    platform="close",
    direction="bidirectional",
    filters={"query": "company:Acme", "date_created__gte": "2025-01-01"}
)
```

**Rate Limiting**: Variable by endpoint group, tracked via RateLimit headers

**Implementation**: `backend/app/services/crm/close.py`

### Apollo.io Integration

**Authentication**: API key via `Api-Key` header

**Base URL**: `https://api.apollo.io/v1/`

**Data Model**: Email-based enrichment (read-only platform)

**Sync Operations**:
```python
# Import enrichment data (requires emails list)
result = await sync_service.sync_platform(
    platform="apollo",
    direction="import",
    filters={"emails": ["john@acme.com", "jane@corp.com"]}
)
```

**Rate Limiting**: 600 requests/hour, tracked in Redis

**Implementation**: `backend/app/services/crm/apollo.py`

### LinkedIn Integration

**Authentication**: Cookie-based session via Browserbase

**Data Model**: Profile URL-based scraping (read-only)

**Sync Operations**:
```python
# Import profile data (requires profile URLs)
result = await sync_service.sync_platform(
    platform="linkedin",
    direction="import",
    filters={"profile_urls": ["https://linkedin.com/in/johndoe"]}
)
```

**Rate Limiting**: 100 requests/day, tracked in Redis

**Implementation**: `backend/app/services/crm/linkedin.py`

### Sync Orchestration

**Service**: `CRMSyncService` in `backend/app/services/crm_sync_service.py`

**Architecture**:
1. **Provider Factory**: Initializes platform-specific CRM providers from database credentials
2. **Resilience Wrapper**: Wraps sync operations with circuit breaker + exponential backoff retry
3. **Conflict Resolution**: Last-write-wins based on `updated_at` timestamps
4. **Audit Logging**: All sync operations logged to `CRMSyncLog` table

**Usage Example**:
```python
from app.services.crm_sync_service import CRMSyncService
from app.models.database import get_db

db = next(get_db())
sync_service = CRMSyncService(db=db, redis_client=redis_client)

# Sync a specific platform
result = await sync_service.sync_platform(
    platform="close",
    direction="bidirectional",
    filters={"query": "status:lead"}
)

# Process webhook event
await sync_service.process_webhook_event(platform="close", event=webhook_event)

# Get sync status
status = await sync_service.get_sync_status(platform="close")
```

### Automated Scheduling (Celery Beat)

**Configuration**: `backend/app/celery_app.py` lines 78-98

**Schedule**:
- **Close CRM**: Every 2 hours (bidirectional sync)
- **Apollo.io**: Daily at 2 AM UTC (import enrichment)
- **LinkedIn**: Daily at 3 AM UTC (import profiles)

**Celery Task**: `sync_crm_contacts` in `backend/app/tasks/agent_tasks.py`

**Start Celery Beat**:
```bash
cd backend
celery -A app.celery_app beat --loglevel=info
```

### Monitoring Endpoints

**Sync Status**: `GET /api/sync/status` or `GET /api/sync/status/{platform}`
- Returns: last_sync_at, contacts_processed, contacts_created, contacts_updated, contacts_failed, duration_seconds, errors

**Sync History**: `GET /api/sync/history?platform=close&status=completed&page=1`
- Paginated sync operation history with filtering

**Manual Trigger**: `POST /api/sync/trigger`
```json
{
  "platform": "close",
  "direction": "bidirectional",
  "filters": {"query": "company:Acme"}
}
```

**Aggregate Metrics**: `GET /api/sync/metrics?platform=close&days=7`
- Returns: total_syncs, contacts_processed, success_rate_percent, avg_duration_seconds

**Health Check**: `GET /api/sync/health`
- Returns: configured_platforms, syncs_last_24h, failures_last_24h, health_status

**Implementation**: `backend/app/api/sync.py`

### Database Models

**CRMCredential**: Stores encrypted API keys and OAuth tokens for each platform
- Fields: platform, api_key, access_token, refresh_token, scopes, is_active

**CRMContact**: Local contact records synced with CRM platforms
- Fields: crm_platform, external_id, email, first_name, last_name, company, title, phone, linkedin_url, enrichment_data, last_synced_at

**CRMSyncLog**: Audit trail for all sync operations
- Fields: platform, operation, contacts_processed, contacts_created, contacts_updated, contacts_failed, errors, started_at, completed_at, duration_seconds, status

**Implementation**: `backend/app/models/crm.py`

### Conflict Resolution Strategy

**Algorithm**: Last-write-wins based on `updated_at` timestamps

**Process**:
1. Compare `updated_at` timestamp between local and remote contact
2. Choose newer record as the winner
3. Merge enrichment data from both sources
4. Flag conflicts on critical fields (email, name) for manual review

**Implementation**: `CRMSyncService.resolve_conflict()` in `backend/app/services/crm_sync_service.py:296-376`

### Error Handling

**Circuit Breaker**: Prevents cascade failures by opening circuit after repeated failures
- Implementation: `backend/app/services/circuit_breaker.py`

**Exponential Backoff Retry**: Automatic retry with increasing delays (max 3 retries, 2s base delay, 60s max delay)
- Implementation: `backend/app/services/retry_handler.py`

**Dead Letter Queue**: Failed syncs after max retries stored in Redis for manual review
- Key pattern: `crm:dlq:{platform}:{timestamp}`

**Rate Limit Handling**: Respects platform rate limits, pauses sync when limit exceeded

## MCP Server Usage

### Task Master AI
```bash
# Project management with AI assistance
task-master list
task-master next
task-master show <id>
task-master set-status --id=<id> --status=done
```

### Serena (Code Intelligence)
```bash
# Use for codebase navigation
# Automatically invoked by Claude Code
# Focus on symbolic tools for Python modules
```

### Sequential Thinking
```bash
# Use for complex problem solving
# Break down multi-step implementations
```

### Memory MCP
```bash
# Save project knowledge
# Store architectural decisions
```

### Shrimp Task Manager
```bash
# Detailed planning and verification
# Track multi-phase features
```

### Context7 (Library Documentation)
```bash
# Use for up-to-date library documentation
# Always review before implementing features
# Ensures use of latest API patterns
```

## Advanced MCP Workflow Integration

### Mandatory Workflow: Sequential Thinking → Serena → Context7

**CRITICAL**: Before starting any task or todo implementation, ALWAYS follow this workflow in order:

#### Phase 1: Sequential Thinking (Problem Decomposition)
```
1. Use Sequential Thinking MCP to break down the problem
2. Identify key technical challenges and dependencies
3. Create a step-by-step implementation plan
4. Document assumptions and edge cases
```

**Example Sequential Thinking Process:**
- Thought 1-3: Analyze the requirement and break it into components
- Thought 4-6: Identify technical challenges and dependencies
- Thought 7-9: Create implementation strategy
- Thought 10: Finalize approach and next steps

#### Phase 2: Serena (Codebase Navigation)
```
1. Use Serena to explore relevant code patterns
2. Find existing implementations to follow
3. Identify integration points in the codebase
4. Understand current architecture constraints
```

**Serena Best Practices:**
- Start with `get_symbols_overview` for file structure
- Use `find_symbol` for specific components
- Use `find_referencing_symbols` to understand dependencies
- Read only what's necessary - don't over-fetch code

#### Phase 3: Context7 (Library Documentation)
```
1. Launch a subagent to review Context7 documentation
2. Verify latest API usage patterns for required libraries
3. Check for breaking changes or deprecated methods
4. Confirm implementation approach with current best practices
```

**Context7 Usage Pattern:**
```
Before implementing ANY feature using external libraries:
1. Identify required libraries (e.g., FastAPI, SQLAlchemy, React)
2. Use Task tool with general-purpose agent to query Context7
3. Review returned documentation for latest patterns
4. Apply learned patterns to implementation
```

### Workflow Example: Adding New API Endpoint

```markdown
## Task: Add POST /api/leads/enrich endpoint

### Step 1: Sequential Thinking
- Analyze: Need to enrich lead data with external API
- Break down: API route → Service layer → Database update
- Dependencies: External API service, Lead model, validation

### Step 2: Serena Exploration
- Find existing endpoint pattern: /api/leads/qualify
- Review service pattern: cerebras.py
- Check Lead model: models/lead.py
- Understand validation: schemas/lead.py

### Step 3: Context7 Documentation (via Subagent)
Query: "FastAPI endpoint with external API call and database update"
- Review latest FastAPI dependency injection patterns
- Check SQLAlchemy async session best practices
- Verify Pydantic schema validation approaches

### Step 4: Implementation
Now implement following the discovered patterns and latest docs
```

### MCP Tool Priority Order

When using multiple MCPs together:

1. **Sequential Thinking** - ALWAYS start here for planning
2. **Serena** - Navigate codebase to find patterns
3. **Context7 (via subagent)** - Verify library usage before coding
4. **Desktop Commander** - Execute file operations
5. **Task Master / Shrimp** - Track progress and verify completion

### Subagent Usage for Context7

**MANDATORY**: Always use a subagent to query Context7 before implementation:

```
Example subagent invocation:
- Use Task tool with general-purpose agent
- Prompt: "Use Context7 to find latest documentation for [library] 
  focusing on [specific feature]. Return key patterns and examples."
- Review subagent findings before proceeding
```

## Subagent Orchestration & Team Management

### Available Subagent Teams

#### Core Orchestration Agents (Built-in)
```
1. task-orchestrator - Analyzes dependencies and coordinates parallel execution
2. task-executor - Implements individual tasks with full MCP access
3. task-checker - Verifies implementation quality and completeness
```

#### Custom User Agents (~/.claude/agents)
```
1. ai-systems-architect - Multi-agent AI systems, LLM routing, RAG pipelines
2. api-design-expert - REST/GraphQL/gRPC API design and documentation
3. data-pipeline-engineer - ETL/ELT, Apache Airflow, Kafka streams
4. developer-experience-engineer - CLI tools, dev productivity, onboarding
5. fullstack-mvp-engineer - Rapid TypeScript/React/Next.js prototypes
6. infrastructure-devops-engineer - IaC, Kubernetes, CI/CD pipelines
7. react-performance-optimizer - Core Web Vitals, bundle optimization
8. realtime-systems-optimizer - WebSocket, ultra-low latency (<10ms)
9. security-compliance-engineer - Auth, encryption, GDPR/PCI compliance
10. testing-automation-architect - Test pyramids, coverage, CI/CD gates
```

### Mandatory Subagent Workflow

**ALL subagents MUST follow this workflow:**

```
1. Sequential Thinking - Break down the problem
2. Serena MCP - Navigate codebase patterns
3. Context7 - Verify library documentation (via subagent)
4. Desktop Commander - Execute file operations
5. Taskmaster-AI / Shrimp - Track progress
```

### Orchestration Pattern: Parallel Execution

**For complex features with independent subtasks:**

```markdown
Step 1: Use task-orchestrator to analyze task dependencies
Step 2: Launch multiple task-executor agents in parallel (one per subtask)
Step 3: Each executor follows: Sequential Thinking → Serena → Context7 → Implementation
Step 4: Use task-checker to verify all implementations
Step 5: Git commit and push if verification passes
```

**Example Multi-Agent Orchestration:**

```
Main Agent (You):
├── Launch task-orchestrator
│   └── Returns: Tasks 1.1, 1.2, 1.3 can run in parallel
│
├── Launch 3 task-executor agents in parallel:
│   ├── Agent 1: Implements Task 1.1 (Backend API)
│   │   └── Uses: Sequential Thinking → Serena → Context7 → Desktop Commander
│   ├── Agent 2: Implements Task 1.2 (Frontend Component)
│   │   └── Uses: Sequential Thinking → Serena → Context7 → Desktop Commander
│   └── Agent 3: Implements Task 1.3 (Database Migration)
│       └── Uses: Sequential Thinking → Serena → Context7 → Desktop Commander
│
└── Launch task-checker
    ├── Verifies all implementations
    ├── Runs tests if applicable
    └── Reports: ✅ All tasks complete and verified
```

### Specialized Agent Selection Guide

**Match tasks to the right specialized agent:**

| Task Type | Agent to Use |
|-----------|-------------|
| AI/LLM integration, multi-agent systems | ai-systems-architect |
| REST/GraphQL API design | api-design-expert |
| Data pipelines, ETL, streaming | data-pipeline-engineer |
| CLI tools, dev tooling, DX improvements | developer-experience-engineer |
| Full-stack MVP, rapid prototypes | fullstack-mvp-engineer |
| Infrastructure, Kubernetes, IaC | infrastructure-devops-engineer |
| React optimization, Core Web Vitals | react-performance-optimizer |
| WebSocket, real-time, low latency | realtime-systems-optimizer |
| Security, auth, compliance | security-compliance-engineer |
| Testing strategy, test automation | testing-automation-architect |

### Agent MCP Configuration

**Each subagent inherits full MCP access:**
- ✅ Desktop Commander (file operations)
- ✅ Sequential Thinking (problem decomposition)
- ✅ Taskmaster-AI (task tracking)
- ✅ Shrimp Task Manager (detailed planning)
- ✅ Serena (codebase navigation)
- ✅ Context7 (library documentation)
- ✅ Memory (knowledge persistence)

### Verification & Git Workflow

**MANDATORY final steps for every implementation:**

```bash
# Step 1: Launch task-checker subagent
task-checker verifies:
  ✓ All requirements implemented
  ✓ Code follows project patterns
  ✓ Tests pass (if applicable)
  ✓ No errors or warnings

# Step 2: If verification passes, sync to GitHub
git add .
git commit -m "feat: [description]

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
git push

# Step 3: Report completion to user
```

### Example: Complete Feature Implementation

```markdown
## Task: Implement Lead Enrichment API

### Phase 1: Orchestration
Main Agent: Launch task-orchestrator
- Analyzes: POST /api/leads/enrich endpoint
- Identifies subtasks: API route, service layer, database schema, tests
- Determines: Tasks 1-3 can run in parallel, Task 4 depends on 1-3

### Phase 2: Parallel Execution
Main Agent: Launch 3 task-executor agents simultaneously

Agent 1 (Backend API):
1. Sequential Thinking: Plan FastAPI endpoint structure
2. Serena: Find /api/leads/qualify pattern
3. Context7: Query latest FastAPI async patterns
4. Desktop Commander: Create /api/leads/enrich route
5. Taskmaster: Mark subtask 1 complete

Agent 2 (Service Layer):
1. Sequential Thinking: Plan enrichment service
2. Serena: Review cerebras.py pattern
3. Context7: Check external API integration best practices
4. Desktop Commander: Create enrichment_service.py
5. Taskmaster: Mark subtask 2 complete

Agent 3 (Database):
1. Sequential Thinking: Plan schema changes
2. Serena: Review existing Lead model
3. Context7: Check SQLAlchemy migration patterns
4. Desktop Commander: Create Alembic migration
5. Taskmaster: Mark subtask 3 complete

### Phase 3: Dependent Task
Agent 4 (Testing) - Waits for Agents 1-3:
1. Sequential Thinking: Plan test strategy
2. Serena: Review test patterns in tests/
3. Context7: Get pytest best practices
4. Desktop Commander: Create test_lead_enrichment.py
5. Taskmaster: Mark subtask 4 complete

### Phase 4: Verification & Sync
Main Agent: Launch task-checker
- Verifies all 4 implementations
- Runs: python test_api.py
- Checks: All tests pass ✅

Main Agent: Git sync
git add .
git commit -m "feat(leads): Add lead enrichment API endpoint..."
git push
```

### Agent Communication Protocol

**Main Agent responsibilities:**
1. Analyze user requirements
2. Launch appropriate specialized/orchestration agents
3. Monitor parallel execution
4. Consolidate results
5. Run final verification via task-checker
6. Execute git workflow
7. Report to user

**Subagent responsibilities:**
1. Follow Sequential Thinking → Serena → Context7 workflow
2. Use Desktop Commander for all file operations
3. Track progress in Taskmaster/Shrimp
4. Report completion status to Main Agent
5. Return detailed implementation summary

## Coding Standards

### Python (FastAPI Backend)
```python
# Follow existing patterns in backend/app/
# Use type hints
# Document with docstrings
# Keep functions focused and testable

from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadResponse
from app.services.cerebras import CerebrasService

@router.post("/leads/qualify", response_model=LeadResponse, status_code=201)
async def qualify_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db)
) -> LeadResponse:
    """
    Qualify a lead using Cerebras AI inference.

    Args:
        lead: Lead data for qualification
        db: Database session

    Returns:
        Lead with qualification score and reasoning
    """
    # Implementation following existing pattern
```

### Error Handling
```python
# Always handle API errors gracefully
from fastapi import HTTPException

try:
    response = cerebras_service.qualify_lead(lead_data)
except Exception as e:
    logger.error(f"Cerebras API error: {e}")
    raise HTTPException(status_code=500, detail="Lead qualification failed")
```

### Database Operations
```python
# Use SQLAlchemy ORM
from app.models.lead import Lead

# Create
db_lead = Lead(**lead_data)
db.add(db_lead)
db.commit()
db.refresh(db_lead)

# Query
leads = db.query(Lead).filter(Lead.status == "qualified").all()

# Update
db_lead.qualification_score = new_score
db.commit()
```

## Testing Strategy

### Current Tests
```bash
# Run all tests
cd backend
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

### Test Structure
```python
# backend/tests/test_health.py - Health endpoint tests
# backend/tests/test_leads.py - Lead management tests (to be added)
# Use TestClient from fastapi.testclient
# Mock Cerebras API calls for unit tests
```

## Environment Variables

Required in `.env` (already configured):
```bash
# Cerebras (primary)
CEREBRAS_API_KEY=csk-...
CEREBRAS_API_BASE=https://api.cerebras.ai/v1

# DeepSeek (research) - NEVER hardcode!
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-...

# Database (Docker)
DATABASE_URL=postgresql+psycopg://sales_agent:dev_password_change_in_production@localhost:5433/sales_agent_db
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=dev_password_change_in_production
POSTGRES_DB=sales_agent_db

# Redis (Docker)
REDIS_URL=redis://localhost:6379/0

# CRM Integrations
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8001/api/linkedin/callback
BROWSERBASE_API_KEY=your_browserbase_key  # For LinkedIn scraping (optional)
BROWSERBASE_PROJECT_ID=your_project_id

# Optional
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## Database Schema

### Current Tables

**leads**
- id (Integer, primary key)
- company_name (String)
- company_website (String, nullable)
- company_size (String, nullable)
- industry (String, nullable)
- contact_name (String, nullable)
- contact_email (String, nullable)
- contact_title (String, nullable)
- notes (Text, nullable)
- qualification_score (Float, nullable)
- qualification_reasoning (Text, nullable)
- qualification_latency_ms (Integer, nullable)
- status (String, default="pending")
- created_at (DateTime)
- updated_at (DateTime)

**cerebras_api_calls**
- id (Integer, primary key)
- lead_id (Integer, foreign key)
- model (String)
- prompt_tokens (Integer)
- completion_tokens (Integer)
- total_tokens (Integer)
- latency_ms (Integer)
- cost (Float)
- created_at (DateTime)

### Multi-Agent Tracking Tables (New)

**agent_executions**
- id (Integer, primary key)
- agent_type (String) - qualification, enrichment, growth, marketing, bdr, conversation
- lead_id (Integer, foreign key)
- status (Enum) - pending, running, success, failed
- started_at (DateTime)
- completed_at (DateTime, nullable)
- latency_ms (Integer, nullable)
- cost_usd (Float, nullable)
- error_message (Text, nullable)

**qualification_results**
- id (Integer, primary key)
- execution_id (Integer, foreign key → agent_executions)
- score (Float)
- reasoning (Text)
- metadata (JSON)

**enrichment_results**
- id (Integer, primary key)
- execution_id (Integer, foreign key → agent_executions)
- enriched_data (JSON)
- source (String) - apollo, clay, etc.

**conversation_messages**
- id (Integer, primary key)
- execution_id (Integer, foreign key → agent_executions)
- role (String) - user, assistant
- content (Text)
- timestamp (DateTime)

**workflow_state**
- id (Integer, primary key)
- lead_id (Integer, foreign key)
- current_agent (String, nullable)
- status (Enum) - pending, running, completed, failed
- metadata (JSON)

## Performance Requirements

Current metrics (verified):
- **Cerebras streaming latency**: 633ms (39% under 1000ms target!)
- **Claude streaming latency**: 4026ms (premium quality)
- **Cost**: $0.000006 per Cerebras request, $0.001743 per Claude request
- **Database**: <50ms query time
- **WebSocket streaming**: Real-time token delivery with Redis pub/sub
- **Circuit breaker overhead**: <10ms per request

## Best Practices

### DO
✅ Follow existing FastAPI patterns
✅ Use type hints everywhere
✅ Write tests for new endpoints
✅ Log all API calls and errors
✅ Use environment variables for config
✅ Update database via Alembic migrations
✅ Cache repeated queries in Redis
✅ Use DeepSeek for research (cost-effective)

### DON'T
❌ Hardcode API keys anywhere
❌ Skip database migrations
❌ Commit `.env` files
❌ Modify models without migrations
❌ Skip error handling
❌ Use expensive models for simple queries
❌ Bypass the ORM with raw SQL

## Debugging

### Backend Issues
```bash
# Check server logs
python start_server.py
# Look for startup errors

# Test database connection
docker-compose ps
# Verify PostgreSQL is running

# Test Cerebras API
python backend/tests/test_cerebras.py
```

### Database Issues
```bash
# Check migrations
cd backend
alembic current
alembic history

# Reset database (DANGER)
alembic downgrade base
alembic upgrade head
```

### Frontend Issues
```bash
cd frontend
npm run dev
# Check console for errors
```

## Development Roadmap

### Phase 1: Core Foundation ✅ COMPLETE
- [x] Development infrastructure setup (Docker, PostgreSQL, Redis)
- [x] Lead qualification engine with Cerebras AI
- [x] Automated report generation system
- [x] Multi-agent architecture with BaseAgent pattern
- [x] Circuit breakers + exponential backoff retry
- [x] Intelligent model routing (Cerebras, Claude, DeepSeek, Ollama)
- [x] Security hardening (global exception handling, structured logging, CORS fixes, API key rotation)
- [x] Database connection pooling

### Phase 2: CRM Integration ✅ 100% COMPLETE
- [x] Task 5.1: Abstract CRM interface (base.py)
- [x] Task 5.2: ~~HubSpot~~ → Close CRM integration with API key auth (HubSpot commented out)
- [x] Task 5.3: Apollo.io integration for contact enrichment
- [x] Task 5.4: LinkedIn connector with OAuth 2.0 + Browserbase scraping
- [x] Task 5.5: Data sync with automated bidirectional sync orchestration, conflict resolution, circuit breakers, and Celery Beat scheduling

### Phase 3: Advanced Features ✅ PARTIALLY COMPLETE
- [x] Voice agent system with Cartesia TTS
- [x] Agent transfer/handoff capability
- [x] Document processing pipeline
- [x] Knowledge base system
- [x] Research pipeline with multi-agent search
- [x] Campaign automation and message generation
- [x] Lead scoring system
- [x] Iterative refinement system
- [x] Social media scraping
- [x] Customer service endpoints
- [x] CSV import functionality
- [x] RunPod vLLM integration
- [ ] Frontend UI/UX completion
- [ ] Production deployment with monitoring
- [ ] Performance analytics dashboards

## Quick Reference

### Start Development
```bash
# Start infrastructure
docker-compose up -d

# Start Celery worker (optional, for async tasks)
cd backend && python celery_worker.py &

# Start backend
python start_server.py

# Start frontend (separate terminal)
cd frontend && npm run dev

# Run tests
python test_api.py          # Standard API tests
python test_streaming.py    # Streaming tests (validates all components)
```

### Common Commands
```bash
# Database migrations
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head

# Install dependencies
cd backend && pip install -r requirements.txt
cd frontend && npm install

# Run tests
cd backend && pytest -v
```

### API Testing
```bash
# Health check
curl http://localhost:8001/api/health

# Qualify lead
curl -X POST http://localhost:8001/api/leads/qualify \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Test Corp", "industry": "SaaS"}'

# List leads
curl http://localhost:8001/api/leads/
```

## Resources

- **API Docs**: http://localhost:8001/api/docs (when running)
- **CRM Integration Summary**: CRM_INTERFACE_SUMMARY.md (HubSpot + Apollo implementation)
- **Cerebras Docs**: https://inference-docs.cerebras.ai
- **HubSpot API**: https://developers.hubspot.com/docs/api/overview
- **Apollo.io API**: https://apolloio.github.io/apollo-api-docs/
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org
- **Task Master Guide**: .taskmaster/CLAUDE.md

---

**Remember**: This is a comprehensive sales automation platform with:
- **CRM Integration**: HubSpot (OAuth 2.0) + Apollo.io (enrichment) + LinkedIn (OAuth 2.0 + Scraping) - 80% complete
- **Multi-Agent System**: BaseAgent pattern, voice agent, agent transfer
- **Document Processing**: Knowledge base, research pipeline, report generation
- **Campaign Automation**: Message generation, outreach management
- **AI Routing**: Cerebras, Claude, DeepSeek, Ollama with intelligent selection
- **Resilience**: Circuit breakers + exponential backoff retry
- **Infrastructure**: Docker Compose (PostgreSQL + Redis), RunPod vLLM

**Next Task**: Data sync and error handling (Task 5.5) - See `.taskmaster/CLAUDE.md` for workflow.

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines from the main CLAUDE.md file.**
@.taskmaster/CLAUDE.md
- we are not using Firebase it has been removed do not add it to any code, we use RunPod for this project