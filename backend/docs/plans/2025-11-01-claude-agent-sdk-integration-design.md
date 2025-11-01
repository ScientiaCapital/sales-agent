# Claude Agent SDK Integration Design
**Date**: 2025-11-01  
**Status**: Approved - Ready for Implementation  
**Timeline**: 2-3 weeks to production  

---

## Executive Summary

**Goal**: Add conversational intelligence layer over existing LangGraph automation using Claude Agent SDK.

**Architecture**: Modular monolith - SDK agents as pluggable modules in existing FastAPI app with clean interfaces and direct LangGraph agent imports.

**Three Agents**:
1. **SR/BDR Agent** (`sr_bdr.py`) - Sales rep conversational assistant
2. **Pipeline Manager** (`pipeline_manager.py`) - Interactive license import orchestration  
3. **Customer Success Agent** (`cs_agent.py`) - Onboarding and support assistant

**Key Constraints Met**:
- ✅ Fast to market (2-3 weeks)
- ✅ Production-grade reliability (circuit breakers, graceful degradation)
- ✅ Cost-optimized (caching, compression, smart tool usage)
- ✅ Easy to maintain/extend (modular structure, clear patterns)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                           │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ React UI  │  │  Slack Bot   │  │  External API Calls  │ │
│  │ (Chat)    │  │              │  │  (REST clients)      │ │
│  └─────┬─────┘  └──────┬───────┘  └──────────┬───────────┘ │
└────────┼────────────────┼───────────────────────┼───────────┘
         │                │                       │
         └────────────────┴───────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              FASTAPI SERVER (Monolith)                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  NEW ENDPOINTS                                          │ │
│ │  /api/chat/sr-bdr           (SR/BDR Agent)             │ │
│ │  /api/chat/pipeline-manager  (Pipeline Manager Agent)  │ │
│ │  /api/chat/customer-success  (CS Agent)                │ │
│ │  /api/chat/sessions          (Session management)      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                            ↓                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │       AGENTS_SDK MODULE (backend/app/agents_sdk/)      │ │
│ │  ┌──────────────────────────────────────────────────┐  │ │
│ │  │  Claude Agent SDK Agents (Conversational Layer)  │  │ │
│ │  │  - sr_bdr.py        (Sales rep assistant)        │  │ │
│ │  │  - pipeline_manager.py  (Import orchestration)   │  │ │
│ │  │  - cs_agent.py       (Customer success)          │  │ │
│ │  └─────────────────────┬────────────────────────────┘  │ │
│ │                        ↓                                 │ │
│ │  ┌──────────────────────────────────────────────────┐  │ │
│ │  │  MCP Tools Layer (backend/app/agents_sdk/tools/) │  │ │
│ │  │  - qualify_lead_tool → QualificationAgent        │  │ │
│ │  │  - enrich_company_tool → EnrichmentAgent         │  │ │
│ │  │  - get_pipeline_tool → Close CRM                 │  │ │
│ │  │  - validate_files_tool → validation scripts      │  │ │
│ │  │  - run_cross_reference_tool → Phase 1 scripts    │  │ │
│ │  └─────────────────────┬────────────────────────────┘  │ │
│ └────────────────────────┼───────────────────────────────┘ │
│                          ↓                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │       LANGGRAPH AGENTS (Existing Automation)           │ │
│ │  from app.services.langgraph.agents import...          │ │
│ │  - QualificationAgent (633ms, Cerebras)                 │ │
│ │  - EnrichmentAgent (ReAct, multi-source)                │ │
│ │  - GrowthAgent, MarketingAgent, BDRAgent, etc.          │ │
│ └───────────────────────┬─────────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           SESSION & STATE MANAGEMENT                        │
│  ┌────────────────┐         ┌───────────────────────────┐  │
│  │ Redis (Hot)    │────────▶│ PostgreSQL (Archive)      │  │
│  │ - Active sess  │  Async  │ - Conversation history    │  │
│  │ - TTL: 24h     │  Archive│ - Analytics & reporting   │  │
│  └────────────────┘         └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Design Principles**:
1. **Single Deployment** - All SDK agents run in existing FastAPI process
2. **Direct Imports** - MCP tools import LangGraph agents (no HTTP overhead)
3. **Modular Organization** - Clear `agents_sdk/` module with sub-packages
4. **Shared Infrastructure** - Reuse Redis, PostgreSQL, logging, monitoring
5. **Gradual Evolution** - Start monolithic, extract to microservices only if needed

---

## Module Structure

```
backend/app/agents_sdk/
├── __init__.py                    # Package exports
├── cli.py                         # 🆕 Interactive CLI for testing
├── config.py                      # SDK configuration & settings
│
├── agents/                        # 🆕 Claude Agent SDK agents
│   ├── __init__.py
│   ├── base_agent.py             # Shared base class for all SDK agents
│   ├── sr_bdr.py                 # SR/BDR conversational agent
│   ├── pipeline_manager.py       # Pipeline orchestration agent
│   └── cs_agent.py               # Customer success agent
│
├── tools/                         # 🆕 MCP tools (wrap LangGraph agents)
│   ├── __init__.py
│   ├── qualification_tools.py    # qualify_lead_tool → QualificationAgent
│   ├── enrichment_tools.py       # enrich_company_tool → EnrichmentAgent
│   ├── crm_tools.py              # get_pipeline_tool → Close CRM queries
│   ├── pipeline_tools.py         # Pipeline import tools (Phase 0-3)
│   └── analytics_tools.py        # Reporting & metrics tools
│
├── sessions/                      # 🆕 Session management (Redis + PostgreSQL)
│   ├── __init__.py
│   ├── session_manager.py        # Create, retrieve, archive sessions
│   ├── redis_store.py            # Hot session storage (TTL: 24h)
│   └── postgres_store.py         # Cold session archive & analytics
│
└── schemas/                       # 🆕 Pydantic models for SDK agents
    ├── __init__.py
    ├── chat.py                   # ChatMessage, ChatSession, StreamChunk
    ├── tools.py                  # Tool input/output schemas
    └── sessions.py               # SessionState, SessionMetadata
```

**New FastAPI Routes**:
```python
# backend/app/api/v1/endpoints/chat.py (NEW FILE)

@router.post("/chat/sr-bdr")
async def sr_bdr_chat(request: ChatRequest, user: User = Depends(get_current_user)):
    """SR/BDR agent chat endpoint with streaming"""

@router.post("/chat/pipeline-manager")
async def pipeline_manager_chat(request: ChatRequest):
    """Pipeline manager agent endpoint"""

@router.post("/chat/customer-success")
async def customer_success_chat(request: ChatRequest):
    """Customer success agent endpoint"""

@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieve session history"""

@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete/archive session"""
```

---

## Data Flow: User Message to Agent Response

**Example**: Sales rep asks "What are my top 5 leads today?"

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: User sends message                                   │
└──────────────────────────────────────────────────────────────┘
React Chat UI → POST /api/chat/sr-bdr
{
  "user_id": "rep_123",
  "message": "What are my top 5 leads today?",
  "stream": true
}

┌──────────────────────────────────────────────────────────────┐
│ STEP 2: FastAPI endpoint receives request                    │
└──────────────────────────────────────────────────────────────┘
# backend/app/api/v1/endpoints/chat.py
async def sr_bdr_chat(request: ChatRequest):
    # 1. Get or create session
    session = await session_manager.get_or_create(
        user_id=request.user_id,
        agent_type="sr_bdr"
    )
    
    # 2. Initialize SR/BDR Agent
    agent = SRBDRAgent()
    
    # 3. Stream response back to user
    return StreamingResponse(
        agent.chat(session_id=session.id, message=request.message),
        media_type="text/event-stream"
    )

┌──────────────────────────────────────────────────────────────┐
│ STEP 3: SR/BDR Agent processes message                       │
└──────────────────────────────────────────────────────────────┘
# backend/app/agents_sdk/agents/sr_bdr.py
async def chat(self, session_id: str, message: str):
    # 1. Load session context from Redis
    session = await self.session_manager.load(session_id)
    
    # 2. Add user message to conversation history
    session.add_message("user", message)
    
    # 3. Claude Agent SDK processes with tools
    async with ClaudeSDKClient(options=self.options) as client:
        await client.query(message)
        
        # 4. Stream responses as they arrive
        async for chunk in client.receive_messages():
            yield format_sse(chunk)  # Send to frontend
            
            # 5. If Claude calls a tool...
            if chunk.type == "tool_call":
                # Execute MCP tool (e.g., qualify_lead_tool)
                result = await self.execute_tool(chunk.tool_name, chunk.args)
                # Tool result goes back to Claude
                await client.send_tool_result(result)

┌──────────────────────────────────────────────────────────────┐
│ STEP 4: MCP Tool calls LangGraph Agent                       │
└──────────────────────────────────────────────────────────────┘
# backend/app/agents_sdk/tools/qualification_tools.py
@tool("qualify_lead", "Qualify and score a lead")
async def qualify_lead_tool(args: dict):
    # Direct Python import - no HTTP overhead!
    from app.services.langgraph.agents import QualificationAgent
    
    # Call existing agent
    agent = QualificationAgent(provider="cerebras")
    result, latency, metadata = await agent.qualify(
        company_name=args["company_name"],
        industry=args.get("industry")
    )
    
    # Return structured result to Claude
    return {
        "score": result.qualification_score,
        "tier": result.tier,
        "reasoning": result.qualification_reasoning,
        "latency_ms": latency
    }

┌──────────────────────────────────────────────────────────────┐
│ STEP 5: Claude synthesizes conversational response           │
└──────────────────────────────────────────────────────────────┘
Claude receives tool results and generates:

"Here are your top 5 leads to focus on today:

🔥 **HOT LEADS** (Immediate outreach)
1. **Acme Corp** (Score: 85) - Multi-state contractor...
2. **TechCo** (Score: 82) - Recently expanded...

🌡️ **WARM LEADS** (Nurture campaign)
3. **BuilderPro** (Score: 78) - Good fit but single location...

**Recommended Actions:**
- Call Acme Corp today - they just got licensed in TX
- Send BuilderPro case study about multi-OEM success"

┌──────────────────────────────────────────────────────────────┐
│ STEP 6: Session archived to PostgreSQL (async)               │
└──────────────────────────────────────────────────────────────┘
# After conversation ends or reaches TTL
await session_manager.archive_session(session_id)
# Redis → PostgreSQL (keeps Redis clean, enables analytics)
```

**Key Performance Characteristics**:
- **Zero Network Overhead**: Direct Python imports (QualificationAgent stays 633ms!)
- **Streaming UX**: Real-time responses as Claude thinks and calls tools
- **Session Memory**: Redis keeps 24h hot, PostgreSQL for long-term analytics
- **Cost-Optimized**: Tool results cached in session (no re-scoring)

---

## Agent Specifications

### 1. SR/BDR Agent (`sr_bdr.py`)

**Purpose**: Conversational assistant for sales reps to prioritize leads and research prospects.

**System Prompt**:
```
You are an expert sales assistant for B2B contractor sales. Help sales reps:
1. Prioritize leads by ICP score and tier
2. Research companies using enrichment data
3. Check pipeline status in Close CRM
4. Recommend outreach strategies

Be concise and action-oriented. Always provide next steps.
```

**Available Tools**:
- `qualify_lead_tool` - Score and tier a lead (→ QualificationAgent)
- `enrich_company_tool` - Get company data (→ EnrichmentAgent)
- `get_pipeline_tool` - Query Close CRM pipeline
- `search_leads_tool` - Find leads by filters
- `get_recent_activity_tool` - Show recent touchpoints

**Example Queries**:
- "What are my top 5 leads today?"
- "Tell me about Acme Corp"
- "Show me all PLATINUM tier leads in Texas"
- "What's the best way to reach out to TechCo?"

**Target Response Time**: <3 seconds (with 2-3 tool calls)

---

### 2. Pipeline Manager Agent (`pipeline_manager.py`)

**Purpose**: Interactive orchestrator for 4-phase contractor license import pipeline (from `production_deployment.md`).

**System Prompt**:
```
You are a pipeline orchestration assistant for contractor license imports. Guide users through:

Phase 0: Aggregate OEM master database
Phase 1: Cross-reference state licenses (CA, TX, FL, etc.)
Phase 2: Multi-state detection
Phase 3: ICP scoring and tiering

Validate files before processing. Provide progress updates. Generate quality reports.
Be proactive about data quality issues.
```

**Available Tools**:
- `validate_files_tool` - Check license CSV quality (→ validate_input_data.py)
- `aggregate_oem_tool` - Phase 0 aggregation (→ 00_aggregate_oem_master.py)
- `cross_reference_tool` - Phase 1 state-specific cross-reference
- `multi_state_detection_tool` - Phase 2 multi-state contractor detection
- `icp_scoring_tool` - Phase 3 scoring and tiering
- `generate_quality_report_tool` - Post-processing quality metrics

**Example Queries**:
- "I have 5 new license lists to import: CA, TX, FL, AZ, NV"
- "Validate these files before I start"
- "Run Phase 1 cross-reference for California"
- "Show me the quality report for the last import"

**Target Response Time**: <20 seconds per phase (network/file I/O bound)

---

### 3. Customer Success Agent (`cs_agent.py`)

**Purpose**: Onboarding and support assistant for new customers.

**System Prompt**:
```
You are a friendly customer success assistant. Help new users:
1. Learn platform features
2. Import their first leads
3. Set up integrations (Close CRM, Apollo, LinkedIn)
4. Troubleshoot common issues

Remember context across conversations. Be patient and educational.
```

**Available Tools**:
- `get_onboarding_checklist_tool` - Show progress through onboarding
- `search_documentation_tool` - Find relevant help articles
- `check_integration_status_tool` - Verify API keys and connections
- `create_support_ticket_tool` - Escalate to human support
- `schedule_demo_tool` - Book calendar time with team

**Example Queries**:
- "How do I import my first lead list?"
- "My Close CRM integration isn't working"
- "What features are available in my plan?"
- "Can you schedule a demo for my team?"

**Target Response Time**: <2 seconds (mostly documentation lookups)

---

## Session Management (Hybrid Redis + PostgreSQL)

### Redis (Hot Storage - 24h TTL)

**Purpose**: Fast access to active conversation sessions.

**Schema**:
```python
# Key: session:{session_id}
{
  "session_id": "sess_abc123",
  "user_id": "rep_123",
  "agent_type": "sr_bdr",
  "created_at": "2025-11-01T10:00:00Z",
  "last_activity_at": "2025-11-01T10:15:00Z",
  "messages": [
    {"role": "user", "content": "What are my top leads?", "timestamp": "..."},
    {"role": "assistant", "content": "Here are your top 5...", "timestamp": "..."}
  ],
  "tool_results_cache": {
    "qualify_lead:Acme Corp": {...},  # Cached for 1 hour
    "enrich_company:TechCo": {...}
  },
  "metadata": {
    "message_count": 5,
    "tool_calls": 8,
    "total_cost_usd": 0.024
  }
}
```

**Operations**:
- `get_or_create_session(user_id, agent_type)` - Retrieve or initialize
- `load_session(session_id)` - Get from Redis
- `update_session(session_id, message)` - Add message, extend TTL
- `cache_tool_result(session_id, tool, args, result, ttl)` - Cache tool outputs
- `expire_session(session_id)` - Manual cleanup

**TTL Strategy**:
- Active sessions: 24 hours from last activity
- Tool result cache: 1 hour (configurable per tool)
- Automatic eviction on TTL expiry

---

### PostgreSQL (Cold Storage - Permanent Archive)

**Purpose**: Long-term conversation history, analytics, compliance.

**New Table: `agent_conversations`**
```sql
CREATE TABLE agent_conversations (
  id SERIAL PRIMARY KEY,
  session_id VARCHAR(255) UNIQUE NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  agent_type VARCHAR(50) NOT NULL,  -- 'sr_bdr', 'pipeline_manager', 'cs_agent'
  
  -- Conversation data
  messages JSONB NOT NULL,           -- Full conversation history
  tool_results JSONB,                -- All tool calls and results
  
  -- Metrics
  message_count INTEGER DEFAULT 0,
  tool_call_count INTEGER DEFAULT 0,
  total_cost_usd DECIMAL(10,6),
  avg_response_time_ms INTEGER,
  
  -- Timestamps
  started_at TIMESTAMP NOT NULL,
  ended_at TIMESTAMP,
  archived_at TIMESTAMP DEFAULT NOW(),
  
  -- Metadata
  metadata JSONB,                    -- User feedback, tags, etc.
  
  -- Indexes
  INDEX idx_user_agent (user_id, agent_type),
  INDEX idx_started_at (started_at),
  INDEX idx_archived_at (archived_at)
);
```

**Archival Strategy**:
```python
# Async background job (Celery)
@celery_app.task
async def archive_expired_sessions():
    """Archive Redis sessions to PostgreSQL after TTL expiry"""
    
    # Find sessions about to expire (TTL < 1 hour)
    expiring_sessions = await redis_store.get_expiring_sessions(threshold=3600)
    
    for session in expiring_sessions:
        # Archive to PostgreSQL
        await postgres_store.archive_session(session)
        
        # Delete from Redis (keep it lean)
        await redis_store.delete_session(session.session_id)
        
    logger.info(f"Archived {len(expiring_sessions)} sessions")

# Run every hour
celery_app.conf.beat_schedule = {
    'archive-sessions': {
        'task': 'app.agents_sdk.sessions.tasks.archive_expired_sessions',
        'schedule': crontab(minute=0),  # Every hour
    }
}
```

**Analytics Queries**:
```sql
-- Most popular tools by agent
SELECT agent_type, 
       jsonb_array_elements(tool_results)->'tool_name' AS tool,
       COUNT(*) AS usage_count
FROM agent_conversations
GROUP BY agent_type, tool
ORDER BY usage_count DESC;

-- Average conversation cost by user
SELECT user_id, 
       AVG(total_cost_usd) AS avg_cost,
       SUM(total_cost_usd) AS total_cost
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY user_id
ORDER BY total_cost DESC;

-- Response time distribution
SELECT agent_type,
       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avg_response_time_ms) AS p50,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_response_time_ms) AS p95,
       PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY avg_response_time_ms) AS p99
FROM agent_conversations
GROUP BY agent_type;
```

---

## Error Handling & Reliability

### Graceful Degradation

**Claude API Failure**:
```python
async def chat(self, session_id: str, message: str):
    try:
        async for chunk in self.claude_sdk.stream(message):
            yield chunk
            
    except AnthropicAPIError as e:
        logger.error(f"Claude API error: {e}")
        
        # Fallback to cached responses from last session
        yield format_error_message(
            "I'm having trouble connecting right now. "
            "Let me show you cached data from your last session..."
        )
        cached_data = await self.session_manager.get_cached_response(session_id)
        yield format_cached_response(cached_data)
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        
        # Graceful failure message
        yield format_error_message(
            "Something went wrong. Our team has been notified. "
            "Try asking again, or contact support."
        )
        
        # Alert monitoring
        await self.alert_service.send_alert(
            severity="high",
            message=f"Agent failed: {e}",
            context={"session_id": session_id}
        )
```

**Tool Execution Failure**:
```python
@tool("qualify_lead", "Qualify and score a lead")
async def qualify_lead_tool(args: dict):
    try:
        # Try primary provider (Cerebras)
        agent = QualificationAgent(provider="cerebras")
        result = await agent.qualify(**args)
        return {"status": "success", "data": result}
        
    except CerebrasAPIError:
        # Fallback to Claude
        logger.warning("Cerebras unavailable, using Claude fallback")
        agent = QualificationAgent(provider="claude")
        result = await agent.qualify(**args)
        return {"status": "success_fallback", "data": result}
        
    except Exception as e:
        # Complete failure - return graceful error
        logger.error(f"Qualification failed: {e}")
        return {
            "status": "error",
            "message": f"Unable to qualify lead: {str(e)}",
            "suggestion": "Try enrichment tool to gather more data first"
        }
```

### Circuit Breaker Pattern

**Prevent cascade failures when LangGraph agents are slow/down**:
```python
from app.core.circuit_breaker import CircuitBreaker

qualification_breaker = CircuitBreaker(
    failure_threshold=5,      # Open after 5 failures
    timeout_duration=30,      # 30 second timeout
    recovery_timeout=60       # Try again after 60 seconds
)

@qualification_breaker.protected
async def qualify_lead_tool(args: dict):
    # Tool implementation...
    pass
```

**Circuit Breaker States**:
- **CLOSED**: Normal operation, requests go through
- **OPEN**: Too many failures, requests fail fast (no LangGraph calls)
- **HALF_OPEN**: Testing recovery, allow 1 request through

---

## Cost Optimization

### Strategy 1: Smart Tool Result Caching

**Implementation**:
```python
# Cache tool results in Redis session
session.cache_tool_result(
    tool_name="qualify_lead",
    args={"company_name": "Acme Corp"},
    result=qualification_data,
    ttl=3600  # 1 hour cache
)

# When Claude calls same tool again with same args...
if cached := session.get_cached_tool_result(tool_name, args):
    return cached  # No LangGraph call, no API cost!
```

**Expected Savings**: ~40% reduction in tool calls (common queries like "tell me more about X")

---

### Strategy 2: Conversation History Compression

**Implementation**:
```python
# After 10 messages, compress history
if len(session.messages) > 10:
    compressed = await self.compress_session(session)
    # Keep: system prompt, last 5 messages, important tool results
    # Discard: old conversational filler, redundant tool results
```

**Expected Savings**: ~40% token reduction on long conversations (10+ messages)

---

### Strategy 3: Streaming Interruption

**Implementation**:
```python
async def chat_with_interruption(session_id: str, message: str):
    async for chunk in self.claude_sdk.stream(message):
        yield chunk
        
        # User clicked "Stop" or got enough info
        if await self.check_interruption(session_id):
            await self.claude_sdk.interrupt()
            break  # Stop paying for tokens we don't need
```

**Expected Savings**: ~10-20% on queries where user gets answer early

---

### Projected Costs

**Per-Conversation Costs (Claude Sonnet 4)**:
```
Without Optimization:
- SR/BDR query (2 tool calls):        $0.008
- Pipeline manager (5 tool calls):    $0.015
- Customer success (1 tool call):     $0.005

With Full Optimization (caching + compression + interruption):
- SR/BDR query:         $0.004  (50% reduction)
- Pipeline manager:     $0.008  (47% reduction)
- Customer success:     $0.003  (40% reduction)
```

**Monthly Projections @ 1000 conversations/day**:
```
Without optimization: $240/month
With optimization:    $120/month
Total savings:        $120/month (50% reduction)
```

---

## Testing Strategy

### Unit Tests

**Agent Tests**:
```python
# backend/tests/agents_sdk/test_sr_bdr_agent.py
@pytest.mark.asyncio
async def test_sr_bdr_lead_query():
    """Test SR/BDR agent can query leads"""
    agent = SRBDRAgent()
    
    # Mock LangGraph agent responses
    with mock.patch('app.services.langgraph.agents.QualificationAgent') as mock_qual:
        mock_qual.return_value.qualify = AsyncMock(
            return_value=(LeadQualificationResult(...), 633, {})
        )
        
        # Send message
        response_chunks = []
        async for chunk in agent.chat("test_session", "What are my top leads?"):
            response_chunks.append(chunk)
        
        # Verify
        assert mock_qual.called
        assert "top leads" in "".join(response_chunks).lower()

@pytest.mark.asyncio
async def test_graceful_degradation():
    """Test agent handles API failures gracefully"""
    agent = SRBDRAgent()
    
    # Simulate Claude API failure
    with mock.patch('anthropic.AnthropicBedrock.stream') as mock_stream:
        mock_stream.side_effect = AnthropicAPIError("API down")
        
        # Should not crash - should return cached fallback
        response_chunks = []
        async for chunk in agent.chat("test_session", "test message"):
            response_chunks.append(chunk)
        
        assert "trouble connecting" in "".join(response_chunks).lower()
```

**Tool Tests**:
```python
# backend/tests/agents_sdk/tools/test_qualification_tools.py
@pytest.mark.asyncio
async def test_qualify_lead_tool():
    """Test qualification tool calls LangGraph agent"""
    
    # Mock QualificationAgent
    with mock.patch('app.services.langgraph.agents.QualificationAgent') as mock_agent:
        mock_agent.return_value.qualify = AsyncMock(
            return_value=(
                LeadQualificationResult(
                    qualification_score=85,
                    tier="hot",
                    qualification_reasoning="Multi-state contractor..."
                ),
                633,
                {}
            )
        )
        
        # Call tool
        result = await qualify_lead_tool({
            "company_name": "Acme Corp",
            "industry": "Construction"
        })
        
        # Verify
        assert result["status"] == "success"
        assert result["data"]["score"] == 85
        assert result["data"]["tier"] == "hot"

@pytest.mark.asyncio
async def test_tool_fallback_on_provider_failure():
    """Test tool falls back to Claude when Cerebras fails"""
    
    with mock.patch('app.services.langgraph.agents.QualificationAgent') as mock_agent:
        # First call (Cerebras) raises error
        mock_agent.return_value.qualify = AsyncMock(
            side_effect=CerebrasAPIError("Cerebras down")
        )
        
        # Second call (Claude) succeeds
        mock_agent_claude = mock.Mock()
        mock_agent_claude.qualify = AsyncMock(
            return_value=(LeadQualificationResult(...), 4000, {})
        )
        
        with mock.patch('app.services.langgraph.agents.QualificationAgent', 
                       side_effect=[mock_agent, mock_agent_claude]):
            
            result = await qualify_lead_tool({"company_name": "Test"})
            
            # Should succeed with fallback
            assert result["status"] == "success_fallback"
```

**Session Tests**:
```python
# backend/tests/agents_sdk/sessions/test_session_manager.py
@pytest.mark.asyncio
async def test_session_creation_and_retrieval():
    """Test session lifecycle"""
    manager = SessionManager()
    
    # Create session
    session = await manager.create_session(
        user_id="test_user",
        agent_type="sr_bdr"
    )
    
    assert session.session_id
    assert session.user_id == "test_user"
    assert session.agent_type == "sr_bdr"
    
    # Retrieve from Redis
    retrieved = await manager.load_session(session.session_id)
    assert retrieved.session_id == session.session_id
    
    # Add messages
    retrieved.add_message("user", "Hello")
    retrieved.add_message("assistant", "Hi there!")
    await manager.update_session(retrieved)
    
    # Verify persistence
    reloaded = await manager.load_session(session.session_id)
    assert len(reloaded.messages) == 2

@pytest.mark.asyncio
async def test_session_archival():
    """Test Redis → PostgreSQL archival"""
    manager = SessionManager()
    
    # Create and populate session
    session = await manager.create_session("user_123", "sr_bdr")
    session.add_message("user", "Test message")
    await manager.update_session(session)
    
    # Archive to PostgreSQL
    await manager.archive_session(session.session_id)
    
    # Verify in PostgreSQL
    archived = await manager.postgres_store.get_archived_session(session.session_id)
    assert archived is not None
    assert len(archived["messages"]) == 1
    
    # Verify deleted from Redis
    with pytest.raises(SessionNotFoundError):
        await manager.load_session(session.session_id)
```

### Integration Tests

**End-to-End Flow**:
```python
# backend/tests/integration/test_sr_bdr_flow.py
@pytest.mark.asyncio
async def test_sr_bdr_complete_conversation():
    """Test complete SR/BDR conversation flow"""
    
    # Start FastAPI test client
    async with AsyncClient(app=app, base_url="http://test") as client:
        
        # 1. Start conversation
        response = await client.post("/api/chat/sr-bdr", json={
            "user_id": "test_rep",
            "message": "What are my top 3 leads?",
            "stream": False  # Non-streaming for test simplicity
        })
        
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        assert "top" in data["response"].lower()
        assert "leads" in data["response"].lower()
        
        # 2. Follow-up question (tests session memory)
        response = await client.post("/api/chat/sr-bdr", json={
            "user_id": "test_rep",
            "session_id": session_id,
            "message": "Tell me more about the first one"
        })
        
        assert response.status_code == 200
        # Should remember context and provide details about first lead
        
        # 3. Get session history
        response = await client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        history = response.json()
        assert len(history["messages"]) >= 4  # 2 user + 2 assistant
```

### Performance Tests

**Load Testing**:
```python
# backend/tests/performance/test_concurrent_sessions.py
@pytest.mark.asyncio
async def test_100_concurrent_conversations():
    """Test system handles 100 concurrent agent sessions"""
    
    async def simulate_conversation(user_id: str):
        async with AsyncClient(app=app) as client:
            response = await client.post("/api/chat/sr-bdr", json={
                "user_id": user_id,
                "message": "What are my top leads?"
            })
            return response.status_code
    
    # Launch 100 concurrent requests
    tasks = [simulate_conversation(f"user_{i}") for i in range(100)]
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(status == 200 for status in results)
    
    # Check Redis capacity (should have 100 active sessions)
    session_count = await redis_client.dbsize()
    assert session_count >= 100
```

---

## Monitoring & Observability

### Logging Strategy

**Structured Logging**:
```python
import structlog

logger = structlog.get_logger(__name__)

# Log all agent interactions
logger.info(
    "agent_interaction",
    agent_type="sr_bdr",
    user_id=user_id,
    session_id=session_id,
    message_length=len(message),
    tools_called=tool_names,
    response_time_ms=latency,
    cost_usd=estimated_cost,
    success=True
)
```

**Log Aggregation**:
- All logs to stdout (Docker captures)
- Consider: DataDog, CloudWatch, or ELK stack
- Alert on: error rates >1%, p99 latency >10s, Claude API errors

---

### Metrics Collection

**PostgreSQL Analytics**:
```python
# Track every interaction in agent_conversations table
await metrics.track_agent_interaction(
    agent_type="sr_bdr",
    user_id=user_id,
    session_id=session_id,
    tools_called=["qualify_lead", "get_pipeline"],
    conversation_length=len(session.messages),
    response_time_ms=latency,
    cost_usd=estimated_cost,
    user_satisfaction=session.feedback_score  # If user rates
)
```

**Dashboard Queries**:
```sql
-- Average response time by agent
SELECT agent_type, 
       AVG(avg_response_time_ms) AS avg_latency,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_response_time_ms) AS p95_latency
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY agent_type;

-- Most used tools
SELECT jsonb_array_elements(tool_results)->'tool_name' AS tool,
       COUNT(*) AS usage_count,
       AVG((jsonb_array_elements(tool_results)->>'latency_ms')::int) AS avg_latency
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY tool
ORDER BY usage_count DESC
LIMIT 10;

-- Cost per user per month
SELECT user_id,
       SUM(total_cost_usd) AS total_cost,
       COUNT(*) AS conversation_count,
       AVG(total_cost_usd) AS avg_cost_per_conversation
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY user_id
ORDER BY total_cost DESC;

-- Session abandonment rate
SELECT agent_type,
       COUNT(*) FILTER (WHERE message_count = 1) AS single_message_sessions,
       COUNT(*) AS total_sessions,
       ROUND(COUNT(*) FILTER (WHERE message_count = 1)::numeric / COUNT(*) * 100, 2) AS abandonment_rate_pct
FROM agent_conversations
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY agent_type;
```

---

## Deployment Strategy

### Phase 1: Development & Testing (Week 1)
```bash
# Local development
1. Install Claude Agent SDK: pip install claude-agent-sdk==0.1.5
2. Create agents_sdk module structure
3. Build base_agent.py with shared patterns
4. Implement MCP tools (wrap LangGraph agents)
5. Build SR/BDR agent (most valuable)
6. Test via CLI: python -m app.agents_sdk.cli
7. Write unit tests for agents + tools
```

### Phase 2: FastAPI Integration (Week 2)
```bash
# API endpoints + session management
1. Create /api/chat/* endpoints
2. Implement session_manager.py (Redis + PostgreSQL)
3. Add SSE streaming support
4. Build pipeline_manager.py agent
5. Build cs_agent.py agent
6. Write integration tests
7. Test via Postman/cURL
```

### Phase 3: Frontend & Production (Week 3)
```bash
# UI + deployment
1. Add React chat widget to frontend
2. Implement Slack bot integration
3. Add monitoring/alerting
4. Load testing (100 concurrent sessions)
5. Deploy to staging environment
6. User acceptance testing
7. Deploy to production
```

---

## Rollout Plan

### Beta Testing (Week 1-2)
- **Users**: 5 internal sales reps
- **Agents**: SR/BDR agent only
- **Goal**: Validate conversational UX, tool accuracy, response quality
- **Metrics**: Response time, tool call accuracy, user satisfaction

### Limited Release (Week 3)
- **Users**: 20 sales reps + 3 ops team members
- **Agents**: SR/BDR + Pipeline Manager
- **Goal**: Stress test session management, validate pipeline orchestration
- **Metrics**: Concurrent session handling, Redis memory usage, archival performance

### General Availability (Week 4)
- **Users**: All sales reps + customers
- **Agents**: All 3 agents (SR/BDR, Pipeline Manager, Customer Success)
- **Goal**: Full production deployment with monitoring
- **Metrics**: All metrics tracked, alerts configured, cost monitoring active

---

## Success Metrics

### Technical KPIs
- **Response Time (p95)**: <5 seconds for SR/BDR, <20 seconds for Pipeline Manager
- **Uptime**: 99.5% availability (excluding scheduled maintenance)
- **Error Rate**: <1% of conversations encounter errors
- **Cost per Conversation**: <$0.010 on average (with optimization)

### Business KPIs
- **Adoption Rate**: 60% of sales reps use SR/BDR agent weekly by Week 4
- **Pipeline Efficiency**: 50% reduction in time to import license lists (Pipeline Manager)
- **Customer Onboarding**: 30% faster time-to-first-value (Customer Success Agent)
- **User Satisfaction**: >4.0/5.0 average rating on agent interactions

---

## Future Enhancements (Post-MVP)

### Phase 2 (Month 2)
1. **Message Queue Integration** - Replace direct imports with Celery for long-running tasks
2. **Advanced Caching** - Semantic similarity search for cached tool results
3. **Multi-Agent Collaboration** - SR/BDR agent can transfer to Pipeline Manager mid-conversation
4. **Voice Interface** - Integrate Cartesia TTS for voice-enabled conversations

### Phase 3 (Month 3+)
1. **Custom Training** - Fine-tune Claude on company-specific sales terminology
2. **Proactive Agents** - Agents initiate conversations ("New hot lead detected!")
3. **Mobile Apps** - WhatsApp/SMS integration for field reps
4. **Analytics Dashboard** - React UI for conversation analytics and insights

---

## Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Claude API rate limits | High | Medium | Implement request queuing, fallback to cached responses |
| Session storage overflow (Redis memory) | Medium | Medium | Aggressive TTL (24h), automatic archival to PostgreSQL |
| Tool execution failures | High | Low | Circuit breakers, multi-provider fallbacks (Cerebras → Claude) |
| Poor response quality | High | Low | Iterative prompt engineering, A/B testing system prompts |
| Cost overruns | Medium | Medium | Real-time cost tracking, conversation length limits, compression |

---

## Appendix: Key Files to Create

```
New Files:
backend/app/agents_sdk/__init__.py
backend/app/agents_sdk/cli.py
backend/app/agents_sdk/config.py
backend/app/agents_sdk/agents/base_agent.py
backend/app/agents_sdk/agents/sr_bdr.py
backend/app/agents_sdk/agents/pipeline_manager.py
backend/app/agents_sdk/agents/cs_agent.py
backend/app/agents_sdk/tools/qualification_tools.py
backend/app/agents_sdk/tools/enrichment_tools.py
backend/app/agents_sdk/tools/crm_tools.py
backend/app/agents_sdk/tools/pipeline_tools.py
backend/app/agents_sdk/tools/analytics_tools.py
backend/app/agents_sdk/sessions/session_manager.py
backend/app/agents_sdk/sessions/redis_store.py
backend/app/agents_sdk/sessions/postgres_store.py
backend/app/agents_sdk/schemas/chat.py
backend/app/agents_sdk/schemas/tools.py
backend/app/agents_sdk/schemas/sessions.py
backend/app/api/v1/endpoints/chat.py

Modified Files:
backend/app/main.py (add chat routes)
backend/app/models/__init__.py (add agent_conversations table)
backend/requirements.txt (add claude-agent-sdk==0.1.5)

Test Files:
backend/tests/agents_sdk/test_sr_bdr_agent.py
backend/tests/agents_sdk/test_pipeline_manager.py
backend/tests/agents_sdk/tools/test_qualification_tools.py
backend/tests/agents_sdk/sessions/test_session_manager.py
backend/tests/integration/test_sr_bdr_flow.py
backend/tests/performance/test_concurrent_sessions.py
```

---

**Status**: ✅ Design Complete - Ready for Implementation
**Next Steps**: 
1. Create git worktree for isolated development
2. Generate detailed implementation plan
3. Begin Phase 1 development (Week 1)
