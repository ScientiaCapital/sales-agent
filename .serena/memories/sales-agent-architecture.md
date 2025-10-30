# Sales Agent Architecture

## System Overview
AI-powered sales automation platform for dealer enrichment and GTM workflows.

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS v4
- **AI Providers**: 
  - Cerebras (ultra-fast, 633ms, $0.000006) - Lead qualification
  - Claude Sonnet 4 (premium reasoning)
  - DeepSeek v3 (cost-effective research)
  - Ollama (local inference)
- **CRM**: Close (bidirectional sync), Apollo (enrichment), LinkedIn (scraping via Browserbase)
- **Voice**: Cartesia TTS
- **Infrastructure**: Docker Compose, RunPod vLLM, Python 3.13 venv

## LangGraph Agents

### LCEL Chains (Simple)
- **QualificationAgent**: Lead scoring with Cerebras (<1000ms)
- **EnrichmentAgent**: Apollo/LinkedIn enrichment with ReAct orchestration

### StateGraphs (Complex)
- **GrowthAgent**: Cyclic market analysis (<5000ms)
- **MarketingAgent**: Parallel campaign generation (<4000ms)
- **BDRAgent**: Human-in-loop meeting booking
- **ConversationAgent**: Voice-enabled AI

**State Management**: Redis checkpointing, PostgreSQL tracking, LangSmith tracing, SSE/WebSocket streaming

## Key Patterns

### Multi-Provider AI Routing
```python
# Cost-optimized routing strategy
CEREBRAS → DeepSeek → Claude (fallback)
```

### CRM Sync Architecture
- Close CRM: Bidirectional sync every 2 hours
- Apollo: Daily import at 2 AM UTC (600 req/hour limit)
- LinkedIn: Daily import at 3 AM UTC (100 req/day limit)
- Celery Beat scheduling + circuit breakers + exponential backoff

### Database Schema (Key Tables)
- `leads`: company_name, email, qualification_score, status, created_at
- `cerebras_api_calls`: lead_id, latency_ms, cost, tokens
- `agent_executions`: agent_type, lead_id, status, latency_ms, cost_usd
- `crm_contacts`: crm_platform, external_id, email, enrichment_data
- `crm_sync_log`: platform, operation, contacts_processed, errors

## Performance Targets
- Qualification: <1000ms (Cerebras)
- Enrichment: <3000ms (Apollo + LinkedIn)
- Growth Analysis: <5000ms (DeepSeek)
- Database queries: <50ms
- Circuit breaker overhead: <10ms

## File Structure
```
backend/app/
├── api/                 # FastAPI endpoints
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic validation
├── services/
│   ├── crm/            # CRM integrations
│   ├── agents/         # LangGraph agents
│   └── outreach/       # Campaign services
├── alembic/            # DB migrations
└── tests/              # Test suite (96% coverage)
```

## Development Workflow
1. `source venv/bin/activate` (ALWAYS first)
2. `docker-compose up -d` (PostgreSQL + Redis)
3. `python start_server.py` (starts on port 8001)
4. `alembic revision --autogenerate -m "description"`
5. `pytest -v`
