  # Claude Agent SDK Integration

**Conversational intelligence layer** over existing LangGraph automation using Claude Agent SDK.

## Overview

The Agent SDK provides three specialized conversational agents that interact with users through natural language while leveraging existing LangGraph automation under the hood:

1. **SR/BDR Agent** - Sales rep conversational assistant for lead prioritization
2. **Pipeline Manager Agent** - Interactive license import orchestration
3. **Customer Success Agent** - Onboarding and support assistant

## Quick Start

### CLI Testing (Development)

Test agents interactively during development:

```bash
# Activate virtual environment
source venv/bin/activate

# Test SR/BDR agent
python -m app.agents_sdk.cli sr_bdr

# Test Pipeline Manager
python -m app.agents_sdk.cli pipeline_manager

# Test Customer Success
python -m app.agents_sdk.cli cs_agent
```

**CLI Commands:**
- `/quit` or `/exit` - Exit CLI
- `/clear` - Start new session
- `/help` - Show agent capabilities and example queries

### API Endpoints

The agents are accessible via FastAPI endpoints with streaming support:

```bash
# SR/BDR Agent Chat
curl -X POST http://localhost:8001/api/chat/sr-bdr \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "rep_123",
    "message": "What are my top 5 leads today?",
    "stream": true
  }'

# Pipeline Manager Chat
curl -X POST http://localhost:8001/api/chat/pipeline-manager \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ops_user",
    "message": "Validate these files: CA.csv, TX.csv, FL.csv",
    "stream": false
  }'

# Customer Success Chat
curl -X POST http://localhost:8001/api/chat/customer-success \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "new_customer",
    "message": "How do I import my first lead list?",
    "stream": true
  }'
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Frontend (React Chat UI / Slack Bot)  │
└──────────────────┬──────────────────────┘
                   │ HTTP POST
                   ↓
┌─────────────────────────────────────────┐
│      FastAPI Chat Endpoints             │
│  /api/chat/sr-bdr                       │
│  /api/chat/pipeline-manager             │
│  /api/chat/customer-success             │
└──────────────────┬──────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────┐
│      Claude Agent SDK Agents            │
│  - SR/BDR Agent (sr_bdr.py)            │
│  - Pipeline Manager (pipeline_manager) │
│  - Customer Success (cs_agent.py)      │
└──────────────────┬──────────────────────┘
                   │ Tool Calls
                   ↓
┌─────────────────────────────────────────┐
│         MCP Tools Layer                 │
│  qualify_lead_tool → QualificationAgent │
│  enrich_company_tool → EnrichmentAgent  │
│  search_leads_tool → Database queries   │
└──────────────────┬──────────────────────┘
                   │ Direct Import (no HTTP)
                   ↓
┌─────────────────────────────────────────┐
│    LangGraph Agents (Existing)         │
│  - QualificationAgent (633ms Cerebras) │
│  - EnrichmentAgent (Apollo/LinkedIn)   │
│  - GrowthAgent, MarketingAgent, etc.   │
└─────────────────────────────────────────┘
```

**Key Design Principles:**
- **Zero Network Overhead**: MCP tools import LangGraph agents directly (no HTTP calls)
- **Hybrid Storage**: Redis for hot sessions (<24h), PostgreSQL for cold archive
- **Circuit Breakers**: Fault tolerance prevents cascade failures
- **Cost Optimization**: Tool result caching, conversation compression

## Agents

### 1. SR/BDR Agent (`sr_bdr.py`)

**Purpose**: Conversational assistant for sales reps to prioritize leads and research prospects.

**Example Queries:**
```
- "What are my top 5 leads today?"
- "Tell me about Acme Corp"
- "Show me all PLATINUM tier leads in Texas"
- "Qualify this lead: TechCorp, Construction industry, 50 employees"
```

**Available Tools:**
- `qualify_lead_tool` - Score and tier leads (→ QualificationAgent)
- `search_leads_tool` - Find leads by filters (→ Database)
- `enrich_company_tool` - Get detailed company data (→ EnrichmentAgent)

**Response Time Target**: <3 seconds (with 2-3 tool calls)

---

### 2. Pipeline Manager Agent (`pipeline_manager.py`)

**Purpose**: Interactive orchestrator for 4-phase contractor license import pipeline.

**Example Queries:**
```
- "I have 5 new license lists to import: CA, TX, FL, AZ, NV"
- "Validate these files before I start"
- "Run Phase 1 cross-reference for California"
- "Show me the quality report for the last import"
```

**Available Tools:**
- `validate_files_tool` - Check CSV quality
- `cross_reference_tool` - State license matching
- `multi_state_detection_tool` - Find multi-state contractors
- `icp_scoring_tool` - Qualify and tier leads

**Response Time Target**: <20 seconds per phase (file I/O bound)

---

### 3. Customer Success Agent (`cs_agent.py`)

**Purpose**: Onboarding and support assistant for new customers.

**Example Queries:**
```
- "How do I import my first lead list?"
- "My Close CRM integration isn't working"
- "What features are available in my plan?"
- "Show me how to set up the pipeline import"
```

**Available Tools:**
- `qualify_lead_tool` - Help customers test qualification
- `search_documentation_tool` - Find help articles
- `check_integration_status_tool` - Verify API connections

**Response Time Target**: <2 seconds (mostly documentation lookups)

## Session Management

### Hot Storage (Redis - 24h TTL)

Active conversation sessions stored in Redis for fast access:

```python
# Session structure
{
  "session_id": "sess_abc123",
  "user_id": "rep_123",
  "agent_type": "sr_bdr",
  "created_at": "2025-11-01T10:00:00Z",
  "last_activity_at": "2025-11-01T10:15:00Z",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "..."},
    {"role": "assistant", "content": "...", "timestamp": "..."}
  ],
  "tool_results_cache": {
    "qualify_lead:Acme Corp": {...},  # Cached 1h
  },
  "metadata": {
    "message_count": 5,
    "tool_calls": 8,
    "total_cost_usd": 0.024
  }
}
```

**Operations:**
```python
from app.agents_sdk.sessions import SessionManager

manager = await SessionManager.create()

# Get or create session
session_id = await manager.get_or_create_session(
    user_id="rep_123",
    agent_type="sr_bdr"
)

# Add message
from app.agents_sdk.schemas.chat import ChatMessage
msg = ChatMessage(role="user", content="Show me leads")
await manager.add_message(session_id, msg)

# Cache tool result (1h TTL)
await manager.cache_tool_result(
    session_id=session_id,
    tool_name="qualify_lead",
    args={"company_name": "Acme"},
    result={"score": 85}
)
```

### Cold Storage (PostgreSQL - Permanent)

Sessions archived after TTL expiry for analytics and compliance:

```sql
-- Query conversation history
SELECT * FROM agent_conversations
WHERE user_id = 'rep_123'
  AND agent_type = 'sr_bdr'
ORDER BY started_at DESC;

-- Analytics: Average cost by agent
SELECT agent_type,
       AVG(total_cost_usd) AS avg_cost,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_response_time_ms) AS p95_latency
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY agent_type;
```

## Error Handling & Reliability

### Circuit Breakers

Protect against cascade failures when external services are down:

```python
from app.core.circuit_breaker import qualification_breaker

# Circuit breaker states:
# - CLOSED: Normal operation (requests go through)
# - OPEN: Too many failures (fail fast, no API calls)
# - HALF_OPEN: Testing recovery (allow 1 request)

# Get circuit state
stats = qualification_breaker.get_stats()
print(f"State: {stats['state']}, Failures: {stats['failure_count']}")

# Manual reset (admin/testing only)
await qualification_breaker.reset()
```

**Thresholds:**
- Qualification: 5 failures → OPEN (30s timeout)
- Enrichment: 3 failures → OPEN (60s timeout)
- CRM: 10 failures → OPEN (30s timeout)

### Graceful Degradation

Multi-level fallback when services fail:

1. **Primary**: Cerebras (633ms, ultra-fast)
2. **Fallback**: Claude (4000ms, reliable)
3. **Cache**: Return cached results from last session
4. **Error**: User-friendly message with suggestion

```python
# Example: qualify_lead_tool execution
try:
    result = await qualification_breaker.call(qualify_with_cerebras)
    return {"status": "success", "provider": "cerebras", ...}
except CircuitBreakerOpenError:
    # Fallback to Claude
    result = await qualify_with_claude()
    return {"status": "success_fallback", "provider": "claude", ...}
except Exception:
    # Return cached data or error
    return {"status": "error", "message": "...", "suggestion": "..."}
```

## Cost Optimization

### Tool Result Caching

Cache tool results in Redis session to avoid redundant API calls:

```python
# Cached for 1 hour
await session.cache_tool_result(
    tool_name="qualify_lead",
    args={"company_name": "Acme Corp"},
    result=qualification_data,
    ttl=3600
)

# Subsequent calls use cache (no LangGraph call, no cost!)
cached = await session.get_cached_tool_result(
    tool_name="qualify_lead",
    args={"company_name": "Acme Corp"}
)
```

**Expected Savings**: ~40% reduction in tool calls

### Projected Costs

**Per-Conversation Costs (Claude Sonnet 4):**
- SR/BDR query (2 tool calls): $0.004 (with optimization)
- Pipeline manager (5 tool calls): $0.008 (with optimization)
- Customer success (1 tool call): $0.003 (with optimization)

**Monthly @ 1000 conversations/day**: $120/month (50% savings vs no optimization)

## Testing

### Unit Tests

```bash
# Run all Agent SDK tests
pytest tests/agents_sdk/ -v

# Run specific test file
pytest tests/agents_sdk/test_integration.py -v

# Run with coverage
pytest tests/agents_sdk/ --cov=app.agents_sdk --cov-report=term-missing
```

### Integration Tests

End-to-end conversation flows:

```bash
# Test complete SR/BDR flow
pytest tests/agents_sdk/test_integration.py::test_sr_bdr_complete_conversation_flow -v

# Test session archival
pytest tests/agents_sdk/test_integration.py::test_session_archival_flow -v

# Test circuit breaker protection
pytest tests/agents_sdk/test_integration.py::test_error_recovery_in_conversation -v
```

## Monitoring

### Session Analytics

```python
from app.agents_sdk.sessions.postgres_store import PostgreSQLSessionStore

postgres_store = PostgreSQLSessionStore()

# Get user conversation history
conversations = await postgres_store.get_user_conversations(
    user_id="rep_123",
    agent_type="sr_bdr",
    limit=10,
    db=db_session
)

# Get analytics (last 7 days)
analytics = await postgres_store.get_analytics(
    agent_type="sr_bdr",
    days=7,
    db=db_session
)
print(f"Total conversations: {analytics['total_conversations']}")
print(f"Avg messages per conversation: {analytics['avg_messages_per_conversation']}")
print(f"Total cost: ${analytics['total_cost_usd']}")
```

### Circuit Breaker Stats

```python
from app.core.circuit_breaker import qualification_breaker, enrichment_breaker, crm_breaker

# Check all circuit breaker states
breakers = {
    "qualification": qualification_breaker,
    "enrichment": enrichment_breaker,
    "crm": crm_breaker
}

for name, breaker in breakers.items():
    stats = breaker.get_stats()
    print(f"{name}: {stats['state']} (failures: {stats['failure_count']})")
```

## Development

### Project Structure

```
backend/app/agents_sdk/
├── __init__.py                 # Package exports
├── cli.py                      # Interactive CLI for testing
├── config.py                   # SDK configuration
│
├── agents/                     # Claude Agent SDK agents
│   ├── base_agent.py          # Shared base class
│   ├── sr_bdr.py              # SR/BDR agent
│   ├── pipeline_manager.py    # Pipeline Manager agent
│   └── cs_agent.py            # Customer Success agent
│
├── tools/                      # MCP tools (wrap LangGraph)
│   ├── qualification_tools.py # qualify_lead_tool, search_leads_tool
│   ├── enrichment_tools.py    # enrich_company_tool
│   └── ...
│
├── sessions/                   # Session management
│   ├── session_manager.py     # Hybrid Redis + PostgreSQL coordinator
│   ├── redis_store.py         # Hot storage (24h TTL)
│   └── postgres_store.py      # Cold storage (permanent)
│
└── schemas/                    # Pydantic models
    ├── chat.py                # ChatMessage, ChatSession
    └── ...
```

### Adding New Tools

1. Create tool function in `tools/`:

```python
from langchain_core.tools import tool

@tool
async def my_new_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Tool description for Claude."""
    # Import LangGraph agent
    from app.services.langgraph.agents import MyAgent

    # Execute
    agent = MyAgent()
    result = await agent.execute(args)

    return {"status": "success", "data": result}
```

2. Add to agent's `get_tools()` method:

```python
# app/agents_sdk/agents/sr_bdr.py
def get_tools(self) -> List[Any]:
    return [
        qualify_lead_tool,
        search_leads_tool,
        my_new_tool  # Add here
    ]
```

3. Update agent system prompt to document tool usage.

## Troubleshooting

### Agent Not Responding

Check circuit breaker state:

```python
from app.core.circuit_breaker import qualification_breaker

stats = qualification_breaker.get_stats()
if stats['state'] == 'open':
    # Circuit open - wait for recovery timeout
    print(f"Circuit breaker OPEN. Wait {stats['timeout_duration']}s")
    await qualification_breaker.reset()  # Manual reset
```

### Session Not Found

Session may have expired (24h TTL) or been archived:

```python
# Check Redis
session = await redis_store.get_session(session_id)
if session is None:
    # Check PostgreSQL archive
    archived = await postgres_store.get_archived_session(session_id, db)
```

### High Costs

Enable tool result caching (already enabled by default):

```python
# Verify cache hits in logs
logger.info("Cache hit for qualify_lead:Acme Corp (saved $0.00006)")
```

## Reference

- **Design Doc**: `backend/docs/plans/2025-11-01-claude-agent-sdk-integration-design.md`
- **FastAPI Docs**: http://localhost:8001/api/docs
- **Claude Agent SDK**: https://docs.anthropic.com/agent-sdk
- **LangChain Tools**: https://python.langchain.com/docs/modules/tools

---

**Status**: ✅ Phase 1-2 Complete (Agents, Tools, API Endpoints, Session Management, Testing, Error Handling)

**Next**: Frontend integration, production deployment, performance dashboards
