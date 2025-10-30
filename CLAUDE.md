# Sales Agent - Development Guide

## Project Overview
AI sales automation with production CRM integrations (Close, Apollo, LinkedIn), multi-agent architecture, voice capabilities, document processing, and knowledge base.

**Status**: ✅ Phase 5 Complete - 6 LangGraph agents, CSV import, ATL discovery, server stability

## Tech Stack
```
Backend: FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
Frontend: React 18 + TypeScript + Vite + Tailwind v4
AI: Cerebras (633ms), Claude, DeepSeek, Ollama
CRM: Close (bidirectional sync), Apollo (enrichment), LinkedIn (scraping)
Voice: Cartesia TTS
Infrastructure: Docker Compose, RunPod vLLM, virtual environment
Testing: pytest (96% coverage)
```

## Multi-Provider AI
- **Ultra-Fast**: Cerebras (633ms, $0.000006) - Lead qualification
- **Premium**: Claude Sonnet 4 (4026ms, $0.001743) - Complex reasoning
- **Research**: DeepSeek v3 ($0.00027) - Cost-effective analysis
- **Local**: Ollama (500ms, $0) - Private inference

## LangGraph Agents

### LCEL Chains (Simple, <1000ms)
- **QualificationAgent** - Lead scoring with Cerebras
- **EnrichmentAgent** - Apollo/LinkedIn enrichment

### StateGraphs (Complex, Multi-step)
- **GrowthAgent** - Cyclic market analysis (<5000ms)
- **MarketingAgent** - Parallel campaign generation (<4000ms)
- **BDRAgent** - Human-in-loop meeting booking (<2000ms/node)
- **ConversationAgent** - Voice-enabled AI (<1000ms/turn)

**State Management**: Redis checkpointing, database tracking, LangSmith tracing, SSE/WebSocket streaming

**LangGraph Endpoints**:
```
POST /api/langgraph/invoke          # Complete response
POST /api/langgraph/stream          # SSE streaming
GET  /api/langgraph/state/{id}      # Checkpoint state
```

## Quick Start
```bash
source venv/bin/activate             # ALWAYS activate first
docker-compose up -d                 # Start PostgreSQL + Redis
python start_server.py               # Start server
python test_api.py                   # Run tests
```

## Directory Structure
```
sales-agent/
├── backend/app/
│   ├── api/                 # FastAPI endpoints
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic validation
│   ├── services/            # Business logic
│   │   ├── crm/            # CRM integrations
│   │   ├── agents/         # LangGraph agents
│   │   └── outreach/       # Campaign services
│   ├── alembic/            # DB migrations
│   └── tests/              # Test suite
├── frontend/src/           # React app
├── .taskmaster/            # Task management
└── .env                    # API keys (never commit!)
```

## Key API Endpoints
```
# Core
GET  /api/health
GET  /api/docs

# Leads
POST /api/leads/qualify
GET  /api/leads/
POST /api/leads/import/csv

# CRM Sync
GET  /api/sync/status
POST /api/sync/trigger
GET  /api/sync/metrics

# LangGraph
POST /api/langgraph/invoke
POST /api/langgraph/stream
```

## CRM Sync System

### Platforms
- **Close CRM**: Bidirectional sync every 2 hours (API key auth)
- **Apollo.io**: Daily import at 2 AM UTC (600 req/hour)
- **LinkedIn**: Daily import at 3 AM UTC (100 req/day)

### Features
- Automated Celery Beat scheduling
- Circuit breakers + exponential backoff retry
- Last-write-wins conflict resolution
- Dead letter queue for failures
- Real-time monitoring endpoints

**Start Celery**: `cd backend && python celery_worker.py &`

See `CRM_INTERFACE_SUMMARY.md` for detailed implementation.

## Database Schema (Key Tables)

**leads**: company_name, email, qualification_score, status, created_at
**cerebras_api_calls**: lead_id, latency_ms, cost, tokens
**agent_executions**: agent_type, lead_id, status, latency_ms, cost_usd
**crm_contacts**: crm_platform, external_id, email, enrichment_data, last_synced_at
**crm_sync_log**: platform, operation, contacts_processed, errors, duration_seconds

## Coding Standards

### Python (FastAPI)
```python
@router.post("/endpoint", response_model=Response, status_code=201)
async def endpoint_name(
    data: Schema,
    db: Session = Depends(get_db)
) -> Response:
    """Docstring with Args and Returns."""
    try:
        result = service.method(data)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error message")
```

**Best Practices**:
- ✅ Type hints, docstrings, tests
- ✅ Environment variables for config
- ✅ Alembic migrations for schema changes
- ✅ Redis caching for repeated queries
- ❌ Never hardcode API keys
- ❌ Never skip error handling

## Development Workflow

### Daily Routine
1. `source venv/bin/activate`
2. `docker-compose up -d`
3. `python start_server.py`
4. Implement following existing patterns
5. `alembic revision --autogenerate -m "description"`
6. `pytest -v`
7. Update Task Master: `task-master set-status --id=X --status=done`

### Feature Development
1. **Plan** - Review roadmap, use Sequential Thinking MCP
2. **Research** - Use Serena MCP for codebase patterns
3. **Verify** - Use Context7 for library docs (via subagent)
4. **Implement** - Follow FastAPI patterns in `backend/app/`
5. **Test** - Add tests in `backend/tests/`
6. **Document** - Update README and tasks

## MCP Workflow (MANDATORY)

**Before ANY implementation**:
1. **Sequential Thinking** - Break down problem
2. **Serena** - Navigate codebase patterns
3. **Context7** - Verify library docs (use subagent)
4. **Desktop Commander** - Execute file operations
5. **Task Master/Shrimp** - Track progress

## Subagent Orchestration

### Available Agents
**Built-in**: task-orchestrator, task-executor, task-checker
**Custom**: ai-systems-architect, api-design-expert, fullstack-mvp-engineer, security-compliance-engineer, testing-automation-architect

### Pattern for Complex Features
1. Launch `task-orchestrator` to analyze dependencies
2. Launch parallel `task-executor` agents (one per subtask)
3. Each follows: Sequential Thinking → Serena → Context7 → Implementation
4. Launch `task-checker` to verify all implementations
5. Git commit and push if verification passes

## Environment Variables
Required in `.env`:
```bash
CEREBRAS_API_KEY=csk-...
DATABASE_URL=postgresql+psycopg://sales_agent:***@localhost:5433/sales_agent_db
REDIS_URL=redis://localhost:6379/0
CLOSE_API_KEY=...
APOLLO_API_KEY=...
LINKEDIN_CLIENT_ID=...
ANTHROPIC_API_KEY=...
```

## Testing
```bash
pytest -v                                    # All tests
pytest --cov=app --cov-report=term-missing  # With coverage
python test_api.py                           # Integration tests
python test_streaming.py                     # Streaming validation
```

## Performance Targets
- Qualification: <1000ms (Cerebras)
- Enrichment: <3000ms (Apollo + LinkedIn)
- Growth Analysis: <5000ms (DeepSeek)
- Marketing: <4000ms (parallel nodes)
- Database queries: <50ms
- Circuit breaker overhead: <10ms

## Resources
- API Docs: http://localhost:8001/api/v1/docs
- Cerebras: https://inference-docs.cerebras.ai
- Close CRM: https://developer.close.com/
- Apollo: https://apolloio.github.io/apollo-api-docs/
- FastAPI: https://fastapi.tiangolo.com
- Task Master: `.taskmaster/CLAUDE.md`

---

**Current Status**: ✅ Server running. ✅ CSV import ready. ✅ ATL discovery ready. ✅ 6 LangGraph agents complete.

**Next Phase**: Frontend UI/UX completion, production deployment, performance dashboards

**Note**: Never use OpenAI or Firebase (removed). Use RunPod for infrastructure. Always activate `venv/` before starting server.
