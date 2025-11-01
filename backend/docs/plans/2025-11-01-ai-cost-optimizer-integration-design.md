# AI Cost Optimizer Integration Design

**Date**: November 1, 2025
**Status**: Design Approved
**Author**: Claude + Tom Kipper

## Executive Summary

Integrate [ai-cost-optimizer](https://github.com/ScientiaCapital/ai-cost-optimizer) into sales-agent to track costs and optimize model selection across all AI operations. Use a hybrid strategy: LangGraph agents track costs in passthrough mode (preserve proven behavior), Agent SDK agents use smart routing (optimize new conversational layer).

**Expected Impact:**
- Complete cost visibility: track every AI call with agent_type + lead_id tags
- Per-lead unit economics: calculate total AI cost from raw data to qualified lead
- 15-20% cost savings on Agent SDK through intelligent routing
- Foundation for data-driven optimization decisions

## Business Goals

### Primary: "Eat Our Own Dog Food"
Deploy ai-cost-optimizer in production to validate its value proposition. Sales-agent provides the perfect test case: diverse AI workloads (qualification, enrichment, conversations), high volume (1000+ leads/day), cost-sensitive operations.

### Secondary: Unit Economics
Answer the question: "What does it cost to process a lead?" Track AI spend per lead through the complete pipeline (qualification → enrichment → nurturing) to measure ROI and identify optimization opportunities.

### Tertiary: Intelligent Optimization
Enable automatic model selection for new Agent SDK agents. These conversational agents benefit from complexity analysis and caching without requiring manual provider tuning.

## Architecture

### Unified Proxy Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                    Sales Agent System                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐         ┌────────────────────────┐   │
│  │  LangGraph Agents    │         │   Agent SDK Agents     │   │
│  │  (Existing)          │         │   (New Conversational) │   │
│  │                      │         │                        │   │
│  │  • QualificationAgent│         │  • SR/BDR Agent       │   │
│  │  • EnrichmentAgent   │         │  • Pipeline Manager   │   │
│  │  • GrowthAgent       │         │  • Customer Success   │   │
│  │  • MarketingAgent    │         │                        │   │
│  │  • BDRAgent          │         │                        │   │
│  │  • ConversationAgent │         │                        │   │
│  └─────────┬────────────┘         └──────────┬─────────────┘   │
│            │ Direct Calls                    │ Smart Routing   │
│            │ (Cerebras/Claude)               │                 │
│            ▼                                 ▼                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         CostOptimizedLLMProvider (Unified Proxy)         │  │
│  │                                                           │  │
│  │  ┌─────────────────┐      ┌──────────────────────────┐  │  │
│  │  │  PassThrough    │      │  Smart Router            │  │  │
│  │  │  Mode           │      │  (from ai-cost-optimizer)│  │  │
│  │  │                 │      │                          │  │  │
│  │  │  Track cost     │      │  • Complexity analysis   │  │  │
│  │  │  Use agent's    │      │  • Model selection       │  │  │
│  │  │  chosen provider│      │  • Response caching      │  │  │
│  │  └─────────────────┘      └──────────────────────────┘  │  │
│  │                                                           │  │
│  │              ┌──────────────────────┐                    │  │
│  │              │   Cost Tracker        │                   │  │
│  │              │   • agent_id          │                   │  │
│  │              │   • lead_id           │                   │  │
│  │              │   • tokens, cost      │                   │  │
│  │              └──────────┬────────────┘                   │  │
│  └─────────────────────────┼──────────────────────────────┘  │
│                            │                                  │
│                            ▼                                  │
│              ┌──────────────────────────────────────┐         │
│              │     PostgreSQL Database              │         │
│              │     • ai_cost_tracking (new table)  │         │
│              │     • agent_conversations (existing)│         │
│              │     • leads (existing)              │         │
│              └──────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Hybrid Strategy**: Balance risk and reward. LangGraph agents keep their proven provider choices (Cerebras for qualification, Claude for reasoning) but add cost tracking. Agent SDK agents use intelligent routing to optimize new conversational workloads.

**Git Submodule Integration**: Add ai-cost-optimizer as submodule at `backend/lib/ai-cost-optimizer`. Install in editable mode for bidirectional development. Changes in either project reflect immediately during development. Lock specific commits for production stability.

**Zero Network Overhead**: Import ai-cost-optimizer as Python library, not HTTP service. Direct function calls add <1ms tracking overhead. Critical for maintaining 633ms qualification target.

**Rich Context Tagging**: Tag every AI call with agent_type, lead_id, session_id, user_id. Enables multi-dimensional analysis: costs by agent, costs by lead, costs by user, costs by session.

## Database Schema

### New Table: ai_cost_tracking

```sql
CREATE TABLE ai_cost_tracking (
    id SERIAL PRIMARY KEY,

    -- Request identification
    request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Context tagging
    agent_type VARCHAR(50) NOT NULL,
    agent_mode VARCHAR(20),  -- "passthrough" or "smart_router"
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

    -- Quality
    quality_score FLOAT,
    feedback_count INTEGER DEFAULT 0,

    INDEX idx_agent_type (agent_type),
    INDEX idx_lead_id (lead_id),
    INDEX idx_session_id (session_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_cache_hit (cache_hit)
);
```

### Views for Analytics

```sql
-- Per-agent cost summary
CREATE VIEW agent_cost_summary AS
SELECT
    agent_type,
    COUNT(*) as total_requests,
    SUM(cost_usd) as total_cost_usd,
    AVG(cost_usd) as avg_cost_per_request,
    AVG(latency_ms) as avg_latency_ms,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as cache_hit_rate
FROM ai_cost_tracking
GROUP BY agent_type;

-- Per-lead cost summary
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

## Implementation

### CostOptimizedLLMProvider Class

```python
# backend/app/core/cost_optimized_llm.py

from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from ai_cost_optimizer.app.router import Router
from ai_cost_optimizer.app.complexity import score_complexity
from app.models.ai_cost_tracking import AICostTracking
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class LLMConfig:
    """Configuration for an LLM call."""
    agent_type: str
    lead_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    mode: Literal["passthrough", "smart_router"] = "passthrough"
    provider: Optional[str] = None  # For passthrough
    model: Optional[str] = None  # For passthrough

class CostOptimizedLLMProvider:
    """
    Unified proxy for all AI calls.

    Modes:
    - passthrough: Use agent's provider, track cost only
    - smart_router: Use ai-cost-optimizer's routing
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.router = Router(providers=None)

    async def complete(
        self,
        prompt: str,
        config: LLMConfig,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Execute LLM completion with cost tracking."""
        import time
        start_time = time.time()

        if config.mode == "passthrough":
            result = await self._passthrough_call(
                prompt, config.provider, config.model,
                max_tokens, temperature
            )
        else:
            complexity = score_complexity(prompt)
            result = await self.router.route_and_complete(
                prompt, complexity, max_tokens
            )

        latency_ms = int((time.time() - start_time) * 1000)

        await self._track_cost(config, prompt, result, latency_ms)

        return {**result, "latency_ms": latency_ms}
```

### Usage Examples

**LangGraph Agent (Passthrough Mode):**
```python
class QualificationAgent:
    async def qualify(self, company_name: str, lead_id: int, db: AsyncSession):
        llm = CostOptimizedLLMProvider(db)

        result = await llm.complete(
            prompt=f"Qualify lead: {company_name}...",
            config=LLMConfig(
                agent_type="qualification",
                lead_id=lead_id,
                mode="passthrough",
                provider="cerebras",
                model="llama3.1-8b"
            )
        )

        return result["response"]
```

**Agent SDK Agent (Smart Router Mode):**
```python
class SRBDRAgent:
    async def chat(self, message: str, session_id: str, db: AsyncSession):
        llm = CostOptimizedLLMProvider(db)

        result = await llm.complete(
            prompt=message,
            config=LLMConfig(
                agent_type="sr_bdr",
                session_id=session_id,
                mode="smart_router"
            ),
            max_tokens=2000
        )

        return result
```

## Migration Strategy

### Phase 1: Foundation (Day 1)

```bash
# Add submodule
git submodule add https://github.com/ScientiaCapital/ai-cost-optimizer \
  backend/lib/ai-cost-optimizer

# Install in editable mode
cd backend
pip install -e ./lib/ai-cost-optimizer

# Create migration
alembic revision --autogenerate -m "Add ai_cost_tracking table"
alembic upgrade head

# Create core components
# - app/core/cost_optimized_llm.py
# - app/models/ai_cost_tracking.py
```

### Phase 2: LangGraph Agents (Day 2)

Migrate 6 agents to passthrough mode:

1. QualificationAgent (Cerebras)
2. EnrichmentAgent (Claude)
3. GrowthAgent (DeepSeek)
4. MarketingAgent (Claude)
5. BDRAgent (Claude)
6. ConversationAgent (Claude)

**Before:**
```python
cerebras = CerebrasProvider(model="llama3.1-8b")
response = await cerebras.complete(prompt)
```

**After:**
```python
llm = CostOptimizedLLMProvider(db)
result = await llm.complete(
    prompt=prompt,
    config=LLMConfig(
        agent_type="qualification",
        lead_id=lead.id,
        mode="passthrough",
        provider="cerebras",
        model="llama3.1-8b"
    )
)
```

### Phase 3: Agent SDK (Day 3)

Migrate 3 agents to smart router mode:

1. SR/BDR Agent
2. Pipeline Manager Agent
3. Customer Success Agent

These agents benefit from automatic optimization: simple queries route to Gemini Flash (cheap), complex queries route to Claude (quality).

### Phase 4: Analytics API (Day 4)

```python
# New endpoint: GET /api/analytics/ai-costs
@router.get("/analytics/ai-costs")
async def get_ai_cost_analytics(
    agent_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI cost analytics.

    Returns:
        - Total costs by agent
        - Total costs by lead
        - Trends over time
        - Cache hit rates
        - Cost savings from smart routing
    """
    # Query ai_cost_tracking with filters
    # Return analytics
```

## Testing Strategy

### Unit Tests

```python
# tests/core/test_cost_optimized_llm.py

@pytest.mark.asyncio
async def test_passthrough_preserves_behavior(mock_db):
    """Verify passthrough doesn't change behavior."""
    llm = CostOptimizedLLMProvider(mock_db)

    result = await llm.complete(
        prompt="What is AI?",
        config=LLMConfig(
            agent_type="test",
            mode="passthrough",
            provider="cerebras",
            model="llama3.1-8b"
        )
    )

    assert result["provider"] == "cerebras"
    assert result["tokens_out"] > 0

    # Verify tracking
    tracking = await mock_db.query(AICostTracking).first()
    assert tracking.agent_type == "test"
    assert tracking.agent_mode == "passthrough"

@pytest.mark.asyncio
async def test_smart_router_saves_cost(mock_db):
    """Verify smart router optimizes simple queries."""
    llm = CostOptimizedLLMProvider(mock_db)

    result = await llm.complete(
        prompt="What is 2+2?",
        config=LLMConfig(
            agent_type="test",
            mode="smart_router"
        )
    )

    assert result["provider"] == "gemini"  # Cheaper
    assert result["cost_usd"] < 0.0001

@pytest.mark.asyncio
async def test_per_lead_aggregation(mock_db):
    """Verify per-lead cost tracking."""
    llm = CostOptimizedLLMProvider(mock_db)

    # Multiple calls for same lead
    for _ in range(3):
        await llm.complete(
            prompt="Qualify",
            config=LLMConfig(
                agent_type="qualification",
                lead_id=123,
                mode="passthrough",
                provider="cerebras",
                model="llama3.1-8b"
            )
        )

    # Query summary
    summary = await mock_db.execute(
        select(LeadCostSummary).where(LeadCostSummary.lead_id == 123)
    )
    result = summary.scalar_one()

    assert result.ai_calls == 3
    assert result.total_cost_usd > 0
    assert "qualification" in result.agents_used
```

### Integration Tests

Test complete flows:
- Lead qualification → enrichment → nurturing (verify cost aggregation)
- Agent SDK multi-turn conversation (verify smart routing + caching)
- High volume stress test (verify performance under load)

## Success Metrics

### Phase 1 Complete When:
- All 6 LangGraph agents track costs in passthrough mode
- Zero regression in performance (<1% latency increase)
- Cost data captured for 1000+ leads

### Phase 2 Complete When:
- Agent SDK agents use smart routing
- Cache hit rate >30% after 1 week
- Smart routing saves >15% on Agent SDK calls

### Long-term Success (30 days):
- Cost per lead <$0.05 (vs $0.08 baseline)
- 95% cost tracking coverage
- Analytics dashboard used daily
- Unit economics drive optimization

## Monitoring

### Key Metrics

```python
metrics = {
    "cost_efficiency": {
        "total_spend_today": "$12.45",
        "cost_per_lead": "$0.042",
        "cache_hit_rate": "37%",
        "smart_router_savings": "$3.21 (21%)"
    },

    "agent_performance": {
        "qualification": {
            "requests": 1543,
            "avg_cost": "$0.000006",
            "avg_latency_ms": 633,
            "provider": "cerebras"
        },
        "sr_bdr": {
            "requests": 287,
            "avg_cost": "$0.004",
            "avg_latency_ms": 2100,
            "provider": "smart_router"
        }
    },

    "lead_economics": {
        "avg_cost_to_qualify": "$0.006",
        "avg_cost_to_enrich": "$0.018",
        "total_cost_per_lead": "$0.024"
    }
}
```

### Automated Alerts

```python
alerts = {
    "daily_spend_threshold": "$50",
    "cost_per_lead_spike": ">$0.10",
    "cache_hit_rate_drop": "<20%",
    "smart_router_failure_rate": ">5%"
}
```

## Risk Mitigation

### Risk: Performance Degradation
**Mitigation**: Passthrough mode preserves existing behavior. Track latency_ms in ai_cost_tracking. Alert if p95 latency increases >5%. Roll back if performance degrades.

### Risk: Cost Tracking Overhead
**Mitigation**: Library import (not HTTP). Async database writes. Batch inserts for high volume. Expected overhead <1ms per call.

### Risk: Breaking Changes in ai-cost-optimizer
**Mitigation**: Git submodule pins exact commit. Test thoroughly before updating submodule. Maintain compatibility layer if API changes.

### Risk: Database Growth
**Mitigation**: Partition ai_cost_tracking by month. Archive old data after 90 days. Aggregate to summary tables for long-term analytics.

## Future Enhancements

### Phase 2 (Q1 2026)
- Real-time cost dashboard (WebSocket updates)
- Per-user cost quotas and billing
- A/B testing framework (compare provider performance)
- Automated cost optimization recommendations

### Phase 3 (Q2 2026)
- Cost-aware circuit breakers (fallback to cheaper models under load)
- Predictive cost budgeting (forecast monthly spend)
- Multi-region provider routing (optimize for latency + cost)
- Quality feedback loop (learn from user ratings)

## References

- ai-cost-optimizer repo: https://github.com/ScientiaCapital/ai-cost-optimizer
- Design discussion: (this document)
- Implementation branch: `feature/ai-cost-optimizer-integration`
- Related: Agent SDK integration (completed), LangGraph agents (existing)

---

**Approved by**: Tom Kipper
**Ready for implementation**: Yes
**Target completion**: 4 days (November 5, 2025)
