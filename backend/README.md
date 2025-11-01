# Sales Agent Backend

Production-ready AI sales automation platform with 6 specialized LangGraph agents, 3 Agent SDK conversational agents, and complete AI cost tracking.

## Quick Start

```bash
cd backend
source ../venv/bin/activate
docker-compose up -d                 # Start PostgreSQL + Redis
alembic upgrade head                 # Run migrations
python start_server.py               # Start server on :8001
```

## AI Cost Tracking

All AI calls are automatically tracked via `CostOptimizedLLMProvider` with two modes:

### Passthrough Mode (LangGraph Agents)

Preserves existing behavior, tracks costs only. Used by proven LangGraph agents.

```python
from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig

# Initialize with database session
llm = CostOptimizedLLMProvider(db)

# Qualification agent - Cerebras for ultra-fast scoring
result = await llm.complete(
    prompt="Qualify TechCorp Inc as a lead...",
    config=LLMConfig(
        agent_type="qualification",
        lead_id=123,
        mode="passthrough",
        provider="cerebras",
        model="llama3.1-8b"
    ),
    max_tokens=1000
)

# Enrichment agent - Claude for data extraction
result = await llm.complete(
    prompt="Enrich company data...",
    config=LLMConfig(
        agent_type="enrichment",
        lead_id=123,
        mode="passthrough",
        provider="claude",
        model="claude-3-haiku-20240307"
    )
)
```

### Smart Router Mode (Agent SDK)

Automatically selects optimal provider based on complexity. Used by conversational agents.

```python
# SR/BDR Agent - optimizes based on query complexity
result = await llm.complete(
    prompt="Show me top 3 leads",  # Simple query -> Gemini Flash
    config=LLMConfig(
        agent_type="sr_bdr",
        session_id="sess_abc123",
        user_id="rep_456",
        mode="smart_router"  # No provider/model needed
    )
)

# Complex analysis -> Claude automatically
result = await llm.complete(
    prompt="Analyze this deal's blockers and recommend strategy...",
    config=LLMConfig(
        agent_type="pipeline_manager",
        session_id="sess_xyz789",
        mode="smart_router"
    )
)
```

### Analytics API

```bash
# Get overall costs
curl http://localhost:8001/api/v1/analytics/ai-costs

# Filter by agent type
curl http://localhost:8001/api/v1/analytics/ai-costs?agent_type=qualification

# Filter by date range
curl "http://localhost:8001/api/v1/analytics/ai-costs?start_date=2025-01-15T00:00:00&end_date=2025-01-16T23:59:59"

# Filter by lead
curl http://localhost:8001/api/v1/analytics/ai-costs?lead_id=123
```

**Example Response:**

```json
{
  "total_cost_usd": 0.042153,
  "total_requests": 1247,
  "by_agent": [
    {
      "agent_type": "qualification",
      "agent_mode": "passthrough",
      "total_requests": 823,
      "total_cost_usd": 0.004938,
      "avg_cost_per_request": 0.000006,
      "avg_latency_ms": 645.2,
      "primary_provider": "cerebras",
      "primary_model": "llama3.1-8b"
    },
    {
      "agent_type": "sr_bdr",
      "agent_mode": "smart_router",
      "total_requests": 234,
      "total_cost_usd": 0.018432,
      "avg_cost_per_request": 0.000079,
      "avg_latency_ms": 1823.5,
      "primary_provider": "gemini",
      "primary_model": "gemini-1.5-flash"
    }
  ],
  "by_lead": [
    {
      "lead_id": 123,
      "company_name": "TechCorp Inc",
      "total_cost_usd": 0.000234,
      "total_requests": 5,
      "agents_used": ["qualification", "enrichment", "growth"]
    }
  ],
  "cache_stats": {
    "total_requests": 1247,
    "cache_hits": 287,
    "cache_hit_rate": 0.2301,
    "estimated_savings_usd": 0.001725
  },
  "time_series": [
    {
      "date": "2025-01-15",
      "total_cost_usd": 0.021067,
      "total_requests": 623
    }
  ]
}
```

### Cost Monitoring Utilities

```python
from app.core.cost_monitoring import (
    get_daily_spend,
    get_cost_per_lead_avg,
    get_cache_hit_rate,
    check_cost_alerts
)

# Get today's total spend
daily_spend = await get_daily_spend(db)
# {"date": "2025-01-15", "total_cost_usd": 0.0421, "total_requests": 1247}

# Average cost per lead (last 7 days)
avg_cost = await get_cost_per_lead_avg(db, days=7)
# 0.000125  ($0.000125 per lead)

# Cache effectiveness (last 24 hours)
cache_stats = await get_cache_hit_rate(db, hours=24)
# {"cache_hit_rate": 0.23, "total_requests": 450, "cache_hits": 104}

# Check budget alerts
alerts = await check_cost_alerts(db, daily_budget=10.0)
# {
#   "severity": "info",
#   "message": "Daily spend within budget: $0.0421/$10.00 (0.4%)",
#   "current_spend": 0.0421
# }
```

## Comprehensive Guide

See [docs/cost-tracking-guide.md](docs/cost-tracking-guide.md) for:

- Architecture overview
- Integration patterns for new agents
- Database schema details
- Performance characteristics
- Troubleshooting guide
- Best practices

## Architecture

### Multi-Agent System

**LangGraph Agents (Passthrough Mode):**
- QualificationAgent - Cerebras for 633ms lead scoring
- EnrichmentAgent - Claude for data extraction
- GrowthAgent - DeepSeek for market analysis
- MarketingAgent - Claude for campaign generation
- BDRAgent - Claude for meeting workflows
- ConversationAgent - Claude for voice interactions

**Agent SDK Agents (Smart Router Mode):**
- SR/BDR Agent - Conversational sales rep assistant
- Pipeline Manager - Deal pipeline management
- Customer Success - Onboarding and support

### Database Schema

```sql
-- Main tracking table
CREATE TABLE ai_cost_tracking (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now(),

    -- Context tags
    agent_type VARCHAR(50) NOT NULL,
    agent_mode VARCHAR(20),  -- 'passthrough' or 'smart_router'
    lead_id INTEGER REFERENCES leads(id),
    session_id VARCHAR(255),
    user_id VARCHAR(255),

    -- Request details
    prompt_text TEXT,
    prompt_tokens INTEGER NOT NULL,
    prompt_complexity VARCHAR(20),

    -- Response details
    completion_text TEXT,
    completion_tokens INTEGER NOT NULL,

    -- Provider & cost
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    cost_usd DECIMAL(10, 8) NOT NULL,

    -- Performance
    latency_ms INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,

    -- Quality (for learning)
    quality_score FLOAT,
    feedback_count INTEGER DEFAULT 0
);

-- Indexes for fast queries
CREATE INDEX idx_agent_type ON ai_cost_tracking(agent_type);
CREATE INDEX idx_lead_id ON ai_cost_tracking(lead_id);
CREATE INDEX idx_session_id ON ai_cost_tracking(session_id);
CREATE INDEX idx_timestamp ON ai_cost_tracking(timestamp);
CREATE INDEX idx_cache_hit ON ai_cost_tracking(cache_hit);
```

### Analytics Views

```sql
-- Per-agent summary
CREATE VIEW agent_cost_summary AS
SELECT
    agent_type,
    COUNT(*) as total_requests,
    SUM(cost_usd) as total_cost_usd,
    AVG(cost_usd) as avg_cost_per_request,
    AVG(latency_ms) as avg_latency_ms,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as cache_hit_rate
FROM ai_cost_tracking
GROUP BY agent_type;

-- Per-lead summary
CREATE VIEW lead_cost_summary AS
SELECT
    lead_id,
    COUNT(*) as ai_calls,
    SUM(cost_usd) as total_cost_usd,
    array_agg(DISTINCT agent_type) as agents_used
FROM ai_cost_tracking
WHERE lead_id IS NOT NULL
GROUP BY lead_id;
```

## Performance Characteristics

- **Tracking overhead:** <1ms per call
- **Query latency:** <100ms for analytics
- **Analytics endpoint:** <500ms
- **Zero performance regression** on existing agents

## Testing

```bash
# All tests
pytest tests/ -v

# Just cost tracking tests
pytest tests/core/test_cost_optimized_llm.py -v
pytest tests/api/test_analytics.py -v
pytest tests/integration/test_complete_cost_tracking.py -v

# With coverage
pytest --cov=app --cov-report=term-missing
```

## Environment Variables

```bash
# AI Providers
CEREBRAS_API_KEY=csk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...  # For Gemini Flash
OPENROUTER_API_KEY=...  # For DeepSeek

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/sales_agent
REDIS_URL=redis://localhost:6379/0
```

## Development Workflow

1. **Make changes** to agents or cost tracking code
2. **Run tests** to verify behavior
3. **Check analytics** to monitor costs
4. **Update migrations** if schema changes
5. **Document** new features

## Troubleshooting

### Cost tracking not working

**Check database session:**
```python
agent = QualificationAgent(db=db)  # Must pass db parameter
```

### Analytics endpoint returns empty data

**Check date range:**
```bash
# Default is last 30 days, extend if needed
curl "http://localhost:8001/api/v1/analytics/ai-costs?start_date=2025-01-01T00:00:00"
```

### High costs detected

**Review agent breakdown:**
```bash
curl http://localhost:8001/api/v1/analytics/ai-costs | jq '.by_agent | sort_by(.total_cost_usd) | reverse'
```

## API Documentation

Full API docs available at: http://localhost:8001/docs

## License

Proprietary
