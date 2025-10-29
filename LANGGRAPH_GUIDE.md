# LangGraph Guide - Sales Agent Platform

## Overview

This guide covers the LangGraph implementation in the Sales Agent platform, providing comprehensive documentation for building, testing, and deploying AI agents using LangChain and LangGraph frameworks.

## Architecture

### Hybrid Agent Pattern

The platform uses a hybrid approach combining two LangGraph patterns:

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

## Agent Implementation Patterns

### 1. QualificationAgent (LCEL Chain)

**Purpose:** Ultra-fast lead qualification using Cerebras AI

**Performance Target:** <1000ms (currently achieving 633ms)

**Implementation:**
```python
from app.services.langgraph.agents.qualification_agent import QualificationAgent

agent = QualificationAgent()
result = await agent.qualify(
    company_name="Acme Corp",
    industry="SaaS",
    company_size="50-200"
)

print(f"Score: {result.qualification_score}")
print(f"Reasoning: {result.qualification_reasoning}")
print(f"Tier: {result.tier}")
```

**Key Features:**
- Structured output via Pydantic models
- Cerebras LLM integration for speed
- Confidence scoring
- Tier classification (A, B, C, D)

### 2. EnrichmentAgent (ReAct Pattern)

**Purpose:** Contact enrichment using external APIs

**Performance Target:** <3000ms

**Implementation:**
```python
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent

agent = EnrichmentAgent()
result = await agent.enrich(
    company_name="Acme Corp",
    contact_email="john@acme.com"
)

print(f"Enriched data: {result.enriched_data}")
print(f"Sources: {result.sources}")
print(f"Confidence: {result.confidence_score}")
```

**Key Features:**
- Tool calling (Apollo.io, LinkedIn)
- ReAct reasoning pattern
- Source attribution
- Completeness scoring

### 3. GrowthAgent (Cyclic StateGraph)

**Purpose:** Market analysis with iterative research

**Performance Target:** <5000ms

**Implementation:**
```python
from app.services.langgraph.agents.growth_agent import GrowthAgent

agent = GrowthAgent()
result = await agent.analyze(
    company_name="Acme Corp",
    research_depth="standard"
)

print(f"Opportunities: {result.opportunities}")
print(f"Confidence: {result.confidence_score}")
print(f"Market analysis: {result.market_analysis}")
```

**Key Features:**
- Cyclic execution (research → validate → research again)
- Capability-based LLM selection
- Confidence-based termination
- Market opportunity identification

### 4. MarketingAgent (Parallel StateGraph)

**Purpose:** Multi-channel campaign generation

**Performance Target:** <4000ms

**Implementation:**
```python
from app.services.langgraph.agents.marketing_agent import MarketingAgent

agent = MarketingAgent()
result = await agent.generate(
    company_name="Acme Corp",
    industry="SaaS",
    contact_title="VP Engineering"
)

print(f"Campaigns: {result.campaigns}")
print(f"Channels: {result.channels}")
print(f"Personalization: {result.personalization_data}")
```

**Key Features:**
- Parallel node execution
- Multi-channel content generation
- A/B testing support
- Performance prediction

### 5. BDRAgent (Human-in-Loop StateGraph)

**Purpose:** Meeting booking with human approval

**Performance Target:** <2000ms per node

**Implementation:**
```python
from app.services.langgraph.agents.bdr_agent import BDRAgent

agent = BDRAgent()
result = await agent.book(
    company_name="Acme Corp",
    contact_email="john@acme.com",
    meeting_type="discovery"
)

print(f"Status: {result.status}")
print(f"Calendar link: {result.calendar_link}")
print(f"Next steps: {result.next_steps}")
```

**Key Features:**
- Human-in-loop interrupts
- Calendar integration
- Approval workflows
- Meeting type classification

### 6. ConversationAgent (Voice-Enabled StateGraph)

**Purpose:** Real-time voice conversations

**Performance Target:** <1000ms per turn

**Implementation:**
```python
from app.services.langgraph.agents.conversation_agent import ConversationAgent

agent = ConversationAgent()
result = await agent.converse(
    user_input="Hello, I'm interested in your SaaS solution",
    session_id="voice_session_123"
)

print(f"Response: {result.response}")
print(f"Audio data: {result.audio_data}")
print(f"Sentiment: {result.sentiment}")
```

**Key Features:**
- Voice-enabled with Cartesia TTS
- Real-time streaming
- Sentiment analysis
- Intent recognition

## Tool Integration

### CRM Tools

**Search CRM:**
```python
from app.services.langgraph.tools.crm_tools import search_crm

@tool
async def search_crm(company_name: str) -> dict:
    """Search Close CRM for company information."""
    # Implementation using existing CRM services
    pass
```

**Available CRM Tools:**
- `search_crm` - Query Close CRM
- `create_contact` - Add new contact
- `update_contact` - Update existing contact
- `sync_contact` - Bidirectional sync

### Enrichment Tools

**Apollo.io Integration:**
```python
from app.services.langgraph.tools.apollo_tools import enrich_with_apollo

@tool
async def enrich_with_apollo(email: str) -> dict:
    """Enrich contact data using Apollo.io."""
    # Implementation using Apollo API
    pass
```

**LinkedIn Integration:**
```python
from app.services.langgraph.tools.linkedin_tools import scrape_linkedin

@tool
async def scrape_linkedin(profile_url: str) -> dict:
    """Scrape LinkedIn profile data."""
    # Implementation using Browserbase
    pass
```

### Voice Tools

**Cartesia TTS:**
```python
from app.services.langgraph.tools.cartesia_tools import generate_voice

@tool
async def generate_voice(text: str, voice_id: str = "default") -> bytes:
    """Generate voice output using Cartesia TTS."""
    # Implementation using Cartesia API
    pass
```

## State Management

### Redis Checkpointing

**Setup:**
```python
from app.services.langgraph.graph_utils import get_redis_checkpointer

checkpointer = await get_redis_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
```

**Configuration:**
```python
from app.services.langgraph.graph_utils import create_streaming_config

config = create_streaming_config(
    thread_id="user_123_conversation_456",
    stream_mode="messages",
    recursion_limit=25
)
```

**State Retrieval:**
```python
from app.services.langgraph.graph_utils import get_checkpoint_config

config = get_checkpoint_config("user_123")
checkpoint = await checkpointer.aget(config)
```

### State Schemas

**QualificationAgentState:**
```python
from typing import TypedDict, Annotated
from typing_extensions import TypedDict

class QualificationAgentState(TypedDict):
    company_name: str
    industry: str
    company_size: str
    qualification_score: float
    qualification_reasoning: str
    tier: str
    confidence_score: float
```

**GrowthAgentState:**
```python
class GrowthAgentState(TypedDict):
    company_name: str
    research_depth: str
    opportunities: Annotated[list, add_messages]
    market_analysis: dict
    confidence_score: float
    research_iterations: int
    current_step: str
```

## Streaming Implementation

### Server-Sent Events (SSE)

**Endpoint:** `POST /api/langgraph/stream`

**Usage:**
```bash
curl -X POST http://localhost:8001/api/langgraph/stream \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qualification",
    "input": {
      "company_name": "Acme Corp",
      "industry": "SaaS"
    },
    "stream_mode": "messages"
  }'
```

**Event Types:**
- `start` - Agent initialization
- `message` - Progress updates
- `update` - State changes
- `complete` - Final result
- `error` - Error handling

### WebSocket Streaming

**Endpoint:** `ws://localhost:8001/ws/langgraph/{agent_type}/{thread_id}`

**Implementation:**
```python
import websockets
import json

async def stream_agent_websocket():
    uri = "ws://localhost:8001/ws/langgraph/qualification/thread_123"
    async with websockets.connect(uri) as websocket:
        async for message in websocket:
            data = json.loads(message)
            print(f"Received: {data}")
```

## Database Integration

### Execution Tracking

**LangGraphExecution Model:**
```python
from app.models.langgraph_models import LangGraphExecution

execution = LangGraphExecution(
    execution_id=str(uuid.uuid4()),
    agent_type="qualification",
    thread_id="thread_123",
    status="running",
    input_data={"company_name": "Acme Corp"},
    graph_type="chain"
)
```

**Checkpoint Storage:**
```python
from app.models.langgraph_models import LangGraphCheckpoint

checkpoint = LangGraphCheckpoint(
    checkpoint_id=str(uuid.uuid4()),
    execution_id=execution.id,
    thread_id="thread_123",
    checkpoint_data={"state": "research_complete"},
    node_name="analyze"
)
```

**Tool Call Tracking:**
```python
from app.models.langgraph_models import LangGraphToolCall

tool_call = LangGraphToolCall(
    tool_call_id=str(uuid.uuid4()),
    execution_id=execution.id,
    tool_name="search_crm",
    tool_type="crm",
    tool_input={"company_name": "Acme Corp"},
    success=True
)
```

## Testing Strategies

### Unit Tests

**Agent Testing:**
```python
@pytest.mark.asyncio
async def test_qualification_agent():
    from app.services.langgraph.agents.qualification_agent import QualificationAgent
    
    agent = QualificationAgent()
    result = await agent.qualify(
        company_name="Test Corp",
        industry="SaaS"
    )
    
    assert result.qualification_score >= 0
    assert result.qualification_score <= 100
    assert result.tier in ["A", "B", "C", "D"]
```

### Integration Tests

**End-to-End Testing:**
```python
@pytest.mark.asyncio
async def test_agent_end_to_end():
    response = client.post(
        "/api/langgraph/invoke",
        json={
            "agent_type": "qualification",
            "input": {
                "company_name": "Test Corp",
                "industry": "SaaS"
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "output" in data
```

### Streaming Tests

**SSE Testing:**
```python
@pytest.mark.asyncio
async def test_streaming():
    response = client.post(
        "/api/langgraph/stream",
        json={
            "agent_type": "qualification",
            "input": {"company_name": "Test Corp"}
        }
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
    
    content = response.text
    lines = content.strip().split('\n')
    data_lines = [line for line in lines if line.startswith('data: ')]
    assert len(data_lines) > 0
```

## Performance Optimization

### Caching Strategies

**Redis Caching:**
```python
import redis
import json

redis_client = redis.Redis.from_url("redis://localhost:6379/0")

async def cached_agent_call(agent_type: str, input_data: dict):
    cache_key = f"agent:{agent_type}:{hash(str(input_data))}"
    
    # Check cache first
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    # Execute agent
    result = await execute_agent(agent_type, input_data)
    
    # Cache result (TTL: 1 hour)
    redis_client.setex(cache_key, 3600, json.dumps(result))
    
    return result
```

### Parallel Execution

**MarketingAgent Parallel Nodes:**
```python
from langgraph.graph import StateGraph

def create_marketing_graph():
    graph = StateGraph(MarketingAgentState)
    
    # Add parallel nodes
    graph.add_node("generate_subjects", generate_subjects_node)
    graph.add_node("generate_messages", generate_messages_node)
    graph.add_node("generate_angles", generate_angles_node)
    
    # Parallel execution
    graph.add_edge(START, "generate_subjects")
    graph.add_edge(START, "generate_messages")
    graph.add_edge(START, "generate_angles")
    
    # Converge to optimization
    graph.add_edge("generate_subjects", "optimize")
    graph.add_edge("generate_messages", "optimize")
    graph.add_edge("generate_angles", "optimize")
    
    return graph
```

## Error Handling

### Circuit Breaker Integration

**Node Wrapping:**
```python
from app.services.langgraph.graph_utils import wrap_node_with_resilience
from app.services.circuit_breaker import CircuitBreaker

# Create circuit breaker
apollo_breaker = CircuitBreaker(
    name="apollo_api",
    failure_threshold=5,
    recovery_timeout=60
)

# Wrap node with resilience
resilient_enrich = wrap_node_with_resilience(
    enrich_with_apollo,
    circuit_breaker=apollo_breaker,
    max_retries=3
)

# Add to graph
graph.add_node("enrich", resilient_enrich)
```

### Graceful Degradation

**Fallback Strategies:**
```python
async def enrich_with_fallback(state: dict) -> dict:
    try:
        # Try Apollo first
        result = await enrich_with_apollo(state["email"])
        return {"enriched_data": result, "source": "apollo"}
    except Exception as e:
        logger.warning(f"Apollo enrichment failed: {e}")
        
        try:
            # Fallback to LinkedIn
            result = await scrape_linkedin(state["linkedin_url"])
            return {"enriched_data": result, "source": "linkedin"}
        except Exception as e2:
            logger.error(f"LinkedIn enrichment failed: {e2}")
            
            # Return partial data
            return {
                "enriched_data": {"email": state["email"]},
                "source": "partial",
                "error": "Full enrichment unavailable"
            }
```

## LangSmith Integration

### Tracing Setup

**Configuration:**
```python
import os
from langsmith import traceable

# Set LangSmith API key
os.environ["LANGCHAIN_API_KEY"] = "your_langsmith_api_key"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "sales-agent-development"
```

**Agent Tracing:**
```python
@traceable(name="qualification_chain", tags=["lead", "qualification"])
async def qualify_lead(lead_data: dict) -> dict:
    # Agent implementation
    pass
```

**Graph Tracing:**
```python
@traceable(name="growth_analysis_graph", tags=["growth", "analysis"])
async def analyze_growth_opportunities(company_data: dict) -> dict:
    # Graph implementation
    pass
```

### Monitoring

**LangSmith Dashboard:**
- URL: https://smith.langchain.com
- Project: sales-agent-development
- Track latency, token usage, costs
- Debug failed executions
- Monitor tool call patterns

## Deployment Considerations

### Environment Variables

**Required:**
```bash
# LangSmith
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sales-agent-development

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Providers
CEREBRAS_API_KEY=your_cerebras_api_key
CARTESIA_API_KEY=your_cartesia_api_key

# CRM Integrations
CLOSE_API_KEY=your_close_api_key
APOLLO_API_KEY=your_apollo_api_key
```

### Scaling Considerations

**Horizontal Scaling:**
- Multiple FastAPI instances behind load balancer
- Shared Redis for checkpointing
- Database connection pooling
- Stateless agent implementations

**Vertical Scaling:**
- Increase worker memory for large graphs
- Optimize Redis memory usage
- Database query optimization
- Connection pool tuning

## Best Practices

### Development

1. **Always use structured output** with Pydantic models
2. **Implement proper error handling** with circuit breakers
3. **Use Redis checkpointing** for stateful workflows
4. **Test streaming endpoints** thoroughly
5. **Monitor performance metrics** via LangSmith

### Production

1. **Set appropriate timeouts** for external API calls
2. **Implement retry logic** with exponential backoff
3. **Use connection pooling** for database and Redis
4. **Monitor resource usage** and scale accordingly
5. **Implement proper logging** for debugging

### Security

1. **Validate all inputs** before processing
2. **Use environment variables** for API keys
3. **Implement rate limiting** for external APIs
4. **Sanitize outputs** before returning to clients
5. **Use HTTPS** for all external communications

## Troubleshooting

### Common Issues

**Redis Connection Errors:**
```bash
# Check Redis status
redis-cli ping

# Verify connection string
echo $REDIS_URL
```

**Agent Execution Failures:**
```python
# Check LangSmith traces
# URL: https://smith.langchain.com
# Look for error details in trace logs
```

**Streaming Issues:**
```python
# Verify SSE headers
headers = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"
}
```

### Debug Mode

**Enable Debug Logging:**
```python
import logging
logging.getLogger("app.services.langgraph").setLevel(logging.DEBUG)
```

**LangSmith Debug:**
```python
os.environ["LANGCHAIN_VERBOSE"] = "true"
```

## Conclusion

This LangGraph implementation provides a robust foundation for AI-powered sales automation. The hybrid pattern (chains + graphs) allows for both simple, fast operations and complex, stateful workflows. With proper testing, monitoring, and deployment practices, this system can scale to handle enterprise-level sales automation requirements.

For additional support or questions, refer to:
- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangChain Documentation: https://python.langchain.com/
- LangSmith Documentation: https://docs.smith.langchain.com/
