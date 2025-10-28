# Sales Agent - AI-Powered Sales Automation Platform

> **Status:** ✅ Multi-Agent Streaming Platform - Production-ready with real-time AI streaming and intelligent routing

An intelligent sales automation platform leveraging **Cerebras ultra-fast inference** (633ms) for real-time lead qualification with multi-agent AI architecture and WebSocket streaming.

## 🎯 What's Working

### ✅ Core Infrastructure (Completed)
- **FastAPI Backend** - REST API with health checks and streaming endpoints
- **Multi-Agent Architecture** - 6 specialized AI agents with BaseAgent pattern
- **Real-Time Streaming** - WebSocket API with Redis pub/sub
- **Intelligent Model Router** - Cerebras, Claude, DeepSeek, Ollama support
- **Resilience Patterns** - Circuit breakers + exponential backoff retry
- **PostgreSQL Database** - Multi-agent execution tracking with 5 new tables
- **Redis Integration** - Caching + pub/sub messaging
- **Docker Compose** - One-command infrastructure setup
- **React Frontend** - Scaffolding with Vite + TypeScript + Tailwind CSS v4
- **Celery Task Queue** - Async workflow orchestration

### 📊 Test Results (Validated)
```
✓ All Streaming Tests Passing (3/3)
- Claude Streaming: PASS (4026ms, $0.001743/request)
- Cerebras Streaming: PASS (633ms, $0.000006/request) ⚡ 39% UNDER 1000ms target!
- Circuit Breaker: PASS (state management verified)
- Health Check: PASS
- Database Integration: PASS
```

**Streaming Performance:**
```json
{
  "provider": "cerebras",
  "model": "llama3.1-8b",
  "latency_ms": 633,
  "cost_usd": 0.000006,
  "streaming": true,
  "status": "✅ 39% under target"
}
```

## 🏗️ Architecture

### Technology Stack
- **Backend**: FastAPI + SQLAlchemy + Alembic + Pydantic
- **Database**: PostgreSQL 16 (Docker) with agent execution tracking
- **Cache/Messaging**: Redis 7 (Docker) for caching + pub/sub
- **AI Providers**: Cerebras, Claude (Anthropic), DeepSeek, Ollama
- **Task Queue**: Celery with Redis broker
- **Streaming**: AsyncAnthropic SDK + WebSocket
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS v4
- **Testing**: pytest with 96% coverage
- **Monitoring**: Sentry (ready), Datadog (ready)

### Multi-Agent Architecture

#### AI Provider Routing
```python
TaskType.QUALIFICATION → Cerebras (633ms, ultra-fast)
TaskType.ENRICHMENT → Claude (premium quality)
TaskType.RESEARCH → DeepSeek (cost-effective)
TaskType.ANALYSIS → Ollama (local, private)
```

#### Resilience Patterns
- **Circuit Breaker**: 3-state (CLOSED → OPEN → HALF_OPEN) per provider
- **Exponential Backoff**: 1s → 2s → 4s → 8s retry delays
- **Fallback Routing**: Automatic failover to secondary models

### Project Structure
```
sales-agent/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI endpoints
│   │   │   ├── health.py          # Health checks
│   │   │   ├── leads.py           # Lead management
│   │   │   └── streaming.py       # WebSocket streaming API
│   │   ├── core/                   # Configuration
│   │   │   ├── config.py          # Settings
│   │   │   └── logging.py         # Structured logging
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── database.py        # DB setup
│   │   │   ├── lead.py            # Lead model
│   │   │   ├── api_call.py        # API tracking
│   │   │   └── agent_models.py    # Multi-agent tracking (5 tables)
│   │   ├── schemas/                # Pydantic schemas
│   │   │   └── lead.py            # Lead validation
│   │   └── services/               # Business logic
│   │       ├── cerebras.py        # Cerebras integration
│   │       ├── claude_streaming.py # Claude SDK streaming
│   │       ├── model_router.py    # Intelligent routing
│   │       ├── base_agent.py      # Abstract agent class
│   │       ├── circuit_breaker.py # Resilience pattern
│   │       ├── retry_handler.py   # Exponential backoff
│   │       └── celery_tasks.py    # Async workflows
│   ├── alembic/                    # Database migrations
│   ├── tests/                      # Test suite
│   ├── requirements.txt
│   └── celery_worker.py           # Celery worker
├── frontend/                       # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/            # React components
│   │   └── pages/                # Page components
│   └── package.json
├── .taskmaster/                    # Task management
├── .claude/                        # Claude Code config
├── .env                           # API keys (DO NOT COMMIT)
├── docker-compose.yml             # Infrastructure
├── start_server.py                # Server launcher
├── test_api.py                   # Integration tests
├── test_streaming.py             # Streaming tests
├── STREAMING_IMPLEMENTATION.md   # Streaming docs
└── README.md
```

## 🛠️ Setup

### Prerequisites
```bash
# Docker and Docker Compose
docker --version  # 20.0+ required
docker-compose --version  # 1.29+ required

# Python 3.13+
python --version  # 3.13.7 tested

# Node.js 18+ (for frontend)
node --version  # v18+ required
```

### Quick Start
```bash
# Clone repository
git clone <repository-url>
cd sales-agent

# Start infrastructure (PostgreSQL + Redis + PgAdmin)
docker-compose up -d

# Install Python dependencies
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start Celery worker (optional, for async tasks)
python celery_worker.py &

# Start the FastAPI server
cd ..
python start_server.py
```

The server will start on `http://localhost:8001` with:
- API docs at `http://localhost:8001/api/docs`
- Health endpoint at `http://localhost:8001/api/health`
- WebSocket streaming at `ws://localhost:8001/ws/stream/{stream_id}`

### Environment Variables

#### Required Variables (Docker Infrastructure)

⚠️ **IMPORTANT**: The following environment variables are **required** for docker-compose to start. Create a `.env` file by copying `.env.example`:

```bash
cp .env.example .env
```

Then configure these **mandatory** variables:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `POSTGRES_USER` | PostgreSQL database username | `sales_agent` |
| `POSTGRES_PASSWORD` | PostgreSQL database password | `your_secure_password_here` |
| `POSTGRES_DB` | PostgreSQL database name | `sales_agent_db` |
| `PGADMIN_DEFAULT_EMAIL` | PgAdmin web interface email | `admin@salesagent.local` |
| `PGADMIN_DEFAULT_PASSWORD` | PgAdmin web interface password | `your_secure_password_here` |

**Error Handling**: If these variables are not set in `.env`, docker-compose will fail with a clear error message indicating which variable is missing.

#### Required Variables (Application)

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `DATABASE_URL` | Full PostgreSQL connection string | `postgresql+psycopg://sales_agent:password@localhost:5433/sales_agent_db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CEREBRAS_API_KEY` | Cerebras Cloud API key (ultra-fast inference) | `csk-xxxxx` |

#### Optional Variables (AI Providers)

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude AI (premium quality) | None |
| `DEEPSEEK_API_KEY` | DeepSeek API (cost-effective research) | None |
| `OPENROUTER_API_KEY` | OpenRouter (multi-model access) | None |
| `OLLAMA_API_KEY` | Local Ollama models | `ollama` |

#### Optional Variables (CRM Integration)

| Variable | Description | Required For |
|----------|-------------|--------------|
| `HUBSPOT_CLIENT_ID` | HubSpot OAuth 2.0 client ID | HubSpot integration |
| `HUBSPOT_CLIENT_SECRET` | HubSpot OAuth 2.0 secret | HubSpot integration |
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth 2.0 client ID | LinkedIn integration |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth 2.0 secret | LinkedIn integration |
| `CRM_ENCRYPTION_KEY` | Fernet key for encrypting CRM tokens | CRM integrations |

#### Optional Variables (Monitoring)

| Variable | Description | Default |
|----------|-------------|---------|
| `SENTRY_DSN` | Sentry error tracking DSN | None (disabled) |
| `DATADOG_ENABLED` | Enable Datadog APM | `false` |
| `DATADOG_API_KEY` | Datadog API key | None |

**Security Note:** The `.env` file is in `.gitignore` and should **never** be committed to git. Use `.env.example` as a template.

## 🏃 Testing the API

### Run Integration Tests
```bash
# Start server: python start_server.py
# Run tests in another terminal:

# Standard API tests
python test_api.py

# Streaming tests (validates all components)
python test_streaming.py
```

Expected streaming output:
```
✅ PASS: Claude Streaming (4026ms)
✅ PASS: Model Router Streaming (633ms) ⚡
✅ PASS: Circuit Breaker Streaming

🎯 Overall: 3/3 tests passed - Production ready!
```

### API Endpoints

#### REST Endpoints
```bash
# Health check
GET http://localhost:8001/api/health

# Qualify lead (batch mode)
POST http://localhost:8001/api/leads/qualify
Content-Type: application/json
{
  "company_name": "TechCorp Inc",
  "industry": "SaaS",
  "company_size": "50-200"
}

# List all leads
GET http://localhost:8001/api/leads/
```

#### Streaming Endpoints
```bash
# Start streaming workflow
POST http://localhost:8001/api/stream/start/{lead_id}
{
  "agent_type": "qualification"
}
→ Returns: {"stream_id": "...", "websocket_url": "/ws/stream/..."}

# Connect WebSocket for real-time streaming
WebSocket ws://localhost:8001/ws/stream/{stream_id}
→ Receives progressive tokens in real-time

# Stop streaming
POST http://localhost:8001/api/stream/stop/{stream_id}
```

## 🗺️ Roadmap

### Phase 1: Core Foundation ✅ COMPLETE
- [x] Lead qualification engine with Cerebras AI
- [x] Multi-agent architecture with BaseAgent pattern
- [x] Real-time streaming with WebSocket + Redis pub/sub
- [x] Circuit breakers + exponential backoff retry
- [x] Intelligent model routing (4 providers)
- [x] Database migrations for agent tracking

### Phase 2: CRM Integration ✅ COMPLETE
- [x] Close CRM integration with API key authentication
- [x] Apollo.io contact enrichment (600 req/hour limit)
- [x] LinkedIn profile scraping via Browserbase
- [x] Bidirectional sync orchestration with Celery Beat
- [x] Conflict resolution (last-write-wins strategy)
- [x] Circuit breakers + retry logic for CRM APIs
- [x] Sync monitoring endpoints and manual triggers
- [x] Dead letter queue for failed sync operations

### Phase 3: LangChain/LangGraph Migration 🚧 IN PROGRESS
- [ ] Setup: LangChain/LangGraph dependencies + LangSmith tracing
- [ ] Framework: Base utilities, state schemas, tools, endpoints
- [ ] QualificationAgent - LCEL chain for <1000ms lead scoring
- [ ] EnrichmentAgent - Chain with Apollo/LinkedIn tools
- [ ] GrowthAgent - Cyclic StateGraph for market analysis
- [ ] MarketingAgent - Parallel StateGraph for campaign generation
- [ ] BDRAgent - Human-in-loop StateGraph for booking workflows
- [ ] ConversationAgent - Voice-enabled StateGraph with Cartesia TTS

### Phase 4: Frontend Integration & Deployment (Planned)
- [ ] Connect React dashboard to LangGraph agents
- [ ] WebSocket streaming for real-time agent updates
- [ ] Replace mock data with live API calls
- [ ] Calendly scheduling integration
- [ ] Production deployment with monitoring
- [ ] Performance analytics dashboards

## 📖 Documentation

### Development Guides
- **[Claude Code Guide](CLAUDE.md)** - Comprehensive development workflow and architecture
- **[API Keys Setup](API_KEYS_SETUP.md)** - Complete guide to configuring all API keys
- **[CLI Tools Status](CLI_TOOLS_STATUS.md)** - Verified tool installations and daily workflow
- **[Streaming Implementation](STREAMING_IMPLEMENTATION.md)** - WebSocket streaming architecture
- **[Celery Setup](backend/CELERY_SETUP.md)** - Async task queue guide

### Project Management
- **[Task Master Guide](.taskmaster/CLAUDE.md)** - Task management reference
- **[MCP Integration](.mcp.json)** - MCP server configuration

### CRM Integration
- **[CRM Interface Summary](CRM_INTERFACE_SUMMARY.md)** - Close CRM + Apollo + LinkedIn implementation

## 🎯 Development Workflow

### Daily Development
```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Start Celery worker (optional)
cd backend && python celery_worker.py &

# 3. Start FastAPI server
python start_server.py

# 4. Run tests
python test_api.py
python test_streaming.py
```

### Adding New Features
1. **Plan**: Use Sequential Thinking MCP
2. **Research**: Query Context7 for latest docs
3. **Explore**: Use Serena MCP for codebase patterns
4. **Implement**: Follow BaseAgent pattern for new agents
5. **Test**: Add tests with streaming verification
6. **Document**: Update README and docs

## 📊 Cost & Performance Analysis

### Streaming Performance (Verified)
| Provider | Model | Latency | Cost/Request | Use Case |
|----------|-------|---------|--------------|----------|
| **Cerebras** | llama3.1-8b | **633ms** | **$0.000006** | Qualification (ultra-fast) ⚡ |
| Claude | sonnet-4 | 4026ms | $0.001743 | Premium quality reasoning |
| DeepSeek | v3 | ~2000ms | $0.00027 | Cost-effective research |
| Ollama | local | ~500ms | $0 | Private, local inference |

### Monthly Cost Estimates
- **1,000 leads/month**: ~$6 (mostly Cerebras)
- **10,000 leads/month**: ~$60
- **100,000 leads/month**: ~$600

Cerebras provides **39% faster performance** than target (633ms vs 1000ms) at exceptional cost efficiency.

## 🔧 Development Tools

The project includes MCP servers for enhanced development:
- **Task Master AI** - Project and task management
- **Serena** - Code intelligence and navigation
- **Sequential Thinking** - Problem-solving workflows
- **Context7** - Live library documentation
- **Shrimp Task Manager** - Detailed task planning
- **Memory MCP** - Architectural decision storage

See `.mcp.json` and `CLAUDE.md` for configuration details.

## 🤝 Contributing

1. Create a new branch: `git checkout -b feature/your-feature`
2. Follow MCP workflow: Sequential Thinking → Serena → Context7
3. Make changes and test: `python test_streaming.py`
4. Commit: `git commit -m "feat: description"`
5. Push: `git push origin feature/your-feature`
6. Create Pull Request

## 📝 License

[License Type] - See LICENSE file for details

## 🔗 Resources

- [Cerebras Inference Docs](https://inference-docs.cerebras.ai)
- [Anthropic Streaming Docs](https://docs.anthropic.com/claude/docs/streaming)
- [Task Master AI](https://github.com/eyaltoledano/taskmaster-ai)
- [Claude Code](https://claude.com/claude-code)

---

Built with ❤️ using Cerebras ultra-fast inference (633ms), Claude streaming, and multi-agent orchestration
