# Project: sales-agent
Last Updated: 2025-01-26T15:30:00
Language: Python 3.13.7
Framework: FastAPI + React + LangChain/LangGraph

## Current Sprint/Focus
- [x] Phase 1: Core Foundation - COMPLETE
- [x] Phase 2: CRM Integration - COMPLETE
- [ ] Phase 3: LangChain/LangGraph Migration - IN PROGRESS
  - [ ] Setup LangChain/LangGraph dependencies
  - [ ] Build LangGraph framework (base classes, tools, schemas)
  - [ ] Implement 2 simple agents (chains): Qualification, Enrichment
  - [ ] Implement 4 complex agents (graphs): Growth, Marketing, BDR, Conversation
  - [ ] Integration testing with LangSmith tracing
  - [ ] Documentation and guides

## Architecture Overview
- **Framework**: FastAPI (backend) + React 18 + Vite (frontend)
- **Language**: Python 3.13.7, TypeScript
- **Project Type**: AI-powered sales automation platform
- **Agent Framework**: LangChain/LangGraph (migrating from custom BaseAgent)
- **Integration**: MCP servers, Claude Code, Cursor, LangSmith observability

### Core Stack
- **Backend**: FastAPI, SQLAlchemy, Pydantic, Alembic migrations
- **Database**: PostgreSQL 16 (Docker), Redis 7 (state + pub/sub)
- **AI Providers**:
  - Cerebras (ultra-fast, 633ms, llama3.1-8b)
  - Cartesia (text-to-speech for voice agents)
  - Claude Sonnet 4 (fallback for complex reasoning)
  - DeepSeek v3 (cost-effective research)
- **Agent Orchestration**: LangChain LCEL chains + LangGraph StateGraphs
- **CRM Integrations**: Close CRM, Apollo.io, LinkedIn (bidirectional sync)
- **Observability**: LangSmith tracing, Sentry, Datadog APM
- **Task Queue**: Celery with Redis broker

## Project Description
AI-powered sales automation platform that qualifies leads in <1000ms, enriches with CRM/LinkedIn/Apollo data, generates personalized campaigns, automates BDR booking workflows, and provides voice-enabled conversational AI. Features automated bidirectional CRM sync with Close, Apollo, and LinkedIn.

### Key Features
- **Ultra-fast Lead Qualification**: <1000ms using Cerebras + LangChain LCEL chains
- **CRM Integration**: Bidirectional sync with Close CRM, Apollo enrichment, LinkedIn scraping
- **Multi-Agent System**: 6 specialized agents (Qualification, Enrichment, Growth, Marketing, BDR, Conversation)
- **Voice AI**: Cartesia TTS integration for voice-enabled agents
- **Real-time Streaming**: WebSocket streaming for token-by-token agent responses
- **State Management**: Redis checkpointer for resumable LangGraph workflows

## Recent Changes
- 2025-01-26: **Starting LangChain/LangGraph migration**
  - Replaced .cursorrules with sales-agent configuration
  - Updated project context with LangGraph architecture
  - Planning hybrid agent pattern (chains for simple, graphs for complex)
- 2025-01-25: **Dashboard redesign complete**
  - Professional UI with modern SaaS aesthetics (dadbd5d)
  - Realistic mock data for leads, campaigns, reports
- 2025-01-24: **Phase 2 CRM integration complete**
  - Close CRM with API key auth and bidirectional sync
  - Apollo.io enrichment integration
  - LinkedIn scraper with Browserbase
  - Automated sync orchestration with Celery Beat
  - Conflict resolution and circuit breakers
- 2025-01-20: **Firebase removed, migrated to RunPod**
  - RunPod vLLM integration for local inference
  - Completely replaced Firebase infrastructure

## Blockers
- None currently identified
- LangSmith API key needed for Phase 1 setup (can start with free tier)

## Next Steps
1. **Phase 1: Setup & Dependencies** (1-2 hours)
   - Add LangChain/LangGraph to requirements.txt
   - Configure LangSmith tracing in .env
   - Create Cerebras LLM wrapper for LangChain
   - Create Cartesia TTS tool for LangChain

2. **Phase 2: LangGraph Framework** (2-3 hours)
   - Build base utilities (state management, error handling)
   - Define TypedDict schemas for all agent states
   - Create LangChain tools (CRM, Apollo, LinkedIn, research)
   - Set up FastAPI endpoints for LangGraph agents

3. **Phase 3: Simple Agents (Chains)** (2 hours)
   - QualificationAgent - LCEL chain with Cerebras (<1000ms)
   - EnrichmentAgent - Chain with Apollo/LinkedIn tools

4. **Phase 4: Complex Agents (Graphs)** (4-5 hours)
   - GrowthAgent - Cyclic graph for market analysis
   - MarketingAgent - Parallel graph for campaign generation
   - BDRAgent - Human-in-loop graph for booking
   - ConversationAgent - Voice-enabled stateful graph

5. **Phase 5: Integration & Testing** (2 hours)
   - Database models for LangGraph executions
   - Redis checkpointer for state persistence
   - WebSocket streaming integration
   - Test suite with LangSmith tracing

6. **Phase 6: Documentation** (1 hour)
   - Update CLAUDE.md with LangGraph architecture
   - Create LANGGRAPH_GUIDE.md
   - Update README.md with new architecture diagram

## Development Workflow
- **IDE**: Claude Code (primary), Cursor (secondary)
- **Version Control**: Git with conventional commits
- **Context Management**: project-context-manager skill
- **Memory Storage**: MCP memory server
- **Task Tracking**: TodoWrite for multi-step tasks
- **Observability**: LangSmith for agent tracing and debugging

### Daily Routine
1. Start infrastructure: `docker-compose up -d`
2. Start Celery worker (optional): `cd backend && python celery_worker.py &`
3. Start server: `python start_server.py`
4. Run tests: `python test_api.py`, `python test_streaming.py`
5. Check LangSmith traces: https://smith.langchain.com

## Agent Architecture (LangChain/LangGraph)

### Hybrid Pattern
- **Simple agents** → LCEL chains (linear, fast)
  - QualificationAgent: Lead data → Cerebras → score + reasoning
  - EnrichmentAgent: Lead → Apollo/LinkedIn tools → enriched data

- **Complex agents** → LangGraph StateGraphs (cyclic, stateful)
  - GrowthAgent: Research → analyze → validate → (loop if needed)
  - MarketingAgent: Generate angles → draft messages (parallel) → optimize
  - BDRAgent: Qualify → check calendar → propose → await confirmation
  - ConversationAgent: Transcribe → intent → respond → TTS (Cartesia)

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

## Notes
- **Legacy agents preserved**: Existing BaseAgent implementations moved to `backend/app/services/agents/legacy/`
- **Dual system during migration**: Both legacy and LangGraph agents available via different endpoints
- **LangSmith from day 1**: All agents traced for debugging and optimization
- **Redis state persistence**: Long-running workflows can be paused/resumed
- **CRM tools**: Existing Close/Apollo/LinkedIn integrations wrapped as LangChain tools
- **Streaming everywhere**: Real-time UX via WebSocket for all agents

## Key Files
- `CLAUDE.md` - Comprehensive development guide
- `README.md` - Project overview and setup
- `LANGGRAPH_GUIDE.md` - LangGraph patterns (to be created)
- `.cursorrules` - Cursor/IDE configuration
- `backend/app/services/langgraph/` - New LangGraph agent implementations
- `backend/app/services/langchain/` - LangChain integrations (Cerebras, Cartesia)
- `backend/app/services/agents/legacy/` - Legacy BaseAgent implementations
- `.env` - Environment variables (includes LANGCHAIN_API_KEY)

## MCP Integrations
- **Task Master AI**: Project task management
- **Serena**: Codebase navigation and analysis
- **Sequential Thinking**: Problem decomposition
- **Context7**: Live library documentation
- **Shrimp**: Detailed task planning
- **Memory**: Architecture decision storage
- **Neon**: Database operations
- **GitHub**: Repository management

## Project Metrics (Current)
- **API Endpoints**: 24+ across multiple domains
- **Database Tables**: 15+ (leads, CRM, agents, workflows)
- **Test Coverage**: 96% backend, frontend in progress
- **Performance**: Cerebras 633ms (39% under 1000ms target)
- **Cost**: $0.000006 per Cerebras request

---

**Current Priority**: Complete LangChain/LangGraph migration while maintaining existing FastAPI infrastructure. Focus on learning modern agent patterns (chains vs graphs) with hands-on implementation experience.
