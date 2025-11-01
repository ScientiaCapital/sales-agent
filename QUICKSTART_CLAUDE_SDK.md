# 🚀 Quick Start: Unified Claude SDK with DeepSeek

Get your sales agents running with 11x cheaper AI in 5 minutes!

## Step 1: Get DeepSeek API Key (2 mins)

1. Visit https://platform.deepseek.com/
2. Sign up / Log in
3. Click "API Keys" in sidebar
4. Click "Create API Key"
5. Copy the key (starts with `sk-`)

## Step 2: Add to Environment (1 min)

Edit your `.env` file:

```bash
# You already have this:
ANTHROPIC_API_KEY=sk-ant-api03-...

# Add this (NEW):
DEEPSEEK_API_KEY=sk-...
```

## Step 3: Test the Integration (2 mins)

```bash
# Activate virtual environment
source venv/bin/activate

# Run example
python backend/app/services/langgraph/agents/qualification_agent_v2.py
```

Expected output:
```
✅ QualificationAgentV2 connected to Unified Claude SDK
🚀 Unified Claude SDK ready with providers: ['anthropic', 'deepseek']
🔍 Qualifying lead: Small Startup Inc (complexity=simple, provider=auto)
✅ Lead qualified: Small Startup Inc → WARM (score=65, provider=deepseek, cost=$0.000100, latency=1823ms)

Simple Lead: warm ($0.000100, 1823ms)
Complex Lead: hot ($0.001100, 2956ms)
Forced DeepSeek: hot ($0.000270, 1654ms)

Agent Stats: {
  "providers": {
    "anthropic": {"requests": 1, "total_cost": 0.0011, "total_tokens": 632},
    "deepseek": {"requests": 2, "total_cost": 0.00037, "total_tokens": 1264}
  },
  "total": {
    "requests": 3,
    "cost_usd": 0.00147,
    "average_cost_per_request": 0.00049
  },
  "savings": {
    "deepseek_vs_claude_input": "11x cheaper",
    "deepseek_vs_claude_output": "14x cheaper"
  }
}
```

## Step 4: Integrate with Your Agents

### Option A: Use New V2 Agent (Recommended)

```python
from app.services.langgraph.agents.qualification_agent_v2 import QualificationAgentV2

# Create agent
agent = QualificationAgentV2()
await agent.initialize()

# Qualify leads (auto-routes to cheapest provider)
result = await agent.qualify_lead({
    "company_name": "Acme Corp",
    "industry": "SaaS",
    "company_size": "50-200"
})

print(f"Tier: {result.tier}")  # hot/warm/cold/unqualified
print(f"Score: {result.qualification_score}")  # 0-100
print(f"Provider: {result.provider_used}")  # deepseek or anthropic
print(f"Cost: ${result.cost_usd:.6f}")  # Actual cost
```

### Option B: Use Unified SDK Directly

```python
from app.services.unified_claude_sdk import get_unified_claude_client

# Get client
client = await get_unified_claude_client()

# Generate response (auto-routes)
response = await client.generate(
    prompt="Qualify this lead: TechCorp Inc, SaaS, 100 employees",
    complexity="simple",  # simple/medium/complex
    max_tokens=500
)

print(f"Provider: {response.provider}")  # deepseek
print(f"Cost: ${response.cost_usd:.6f}")  # $0.0001
print(f"Response: {response.content}")
```

## Step 5: Monitor Savings

```python
# Get usage stats
client = await get_unified_claude_client()
stats = client.get_stats()

print(f"Total requests: {stats['total']['requests']}")
print(f"Total cost: ${stats['total']['cost_usd']:.6f}")
print(f"Average cost per request: ${stats['total']['average_cost_per_request']:.6f}")

# Compare providers
print(f"DeepSeek requests: {stats['providers']['deepseek']['requests']}")
print(f"DeepSeek cost: ${stats['providers']['deepseek']['total_cost']:.6f}")
print(f"Claude requests: {stats['providers']['anthropic']['requests']}")
print(f"Claude cost: ${stats['providers']['anthropic']['total_cost']:.6f}")
```

## 🎯 What You Get

### Cost Savings

| Scenario | Before (All Claude) | After (Hybrid) | Savings |
|----------|---------------------|----------------|---------|
| 100 simple leads | $1.10 | $0.10 | **$1.00 (91%)** |
| 100 complex leads | $1.10 | $1.10 | $0 (quality worth it) |
| 50 simple + 50 complex | $1.10 | $0.60 | **$0.50 (45%)** |
| 1000 leads/day | $11.00/day | $3.00/day | **$8/day = $240/month** |

### Intelligent Routing

```
Simple Task (e.g., classification)
    → DeepSeek (11x cheaper)
    → Cost: $0.0001, Latency: <2000ms

Medium Task (e.g., summarization)
    → Auto-route (budget-aware)
    → Cost: $0.0001-$0.001, Latency: <3000ms

Complex Task (e.g., reasoning)
    → Claude (best quality)
    → Cost: $0.0011, Latency: <4000ms
```

## 🔥 Advanced Features

### Prompt Caching (90% Savings on Claude)

```python
# Cache long system prompts
SYSTEM_PROMPT = """You are an expert sales agent..."""  # Long prompt

# First request: full cost
response1 = await client.generate(
    prompt="Qualify lead A",
    system_prompt=SYSTEM_PROMPT,
    enable_caching=True,
    provider="anthropic"
)
# Cost: $0.0011

# Subsequent requests: 90% cheaper!
response2 = await client.generate(
    prompt="Qualify lead B",
    system_prompt=SYSTEM_PROMPT,  # Cached!
    enable_caching=True,
    provider="anthropic"
)
# Cost: $0.0001 (10x cheaper!)
```

### Streaming for Real-time UX

```python
# Stream responses as they're generated
async for chunk in client.generate_stream(
    prompt="Write a marketing email...",
    complexity="medium"
):
    print(chunk, end="", flush=True)
```

### Vision API (Claude Only)

```python
import base64

with open("document.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

response = await client.generate_with_vision(
    prompt="Extract contact info from this document",
    image_data=image_data,
    max_tokens=500
)
```

## 📊 Dashboard Integration

Add cost tracking to your dashboard:

```python
# In your FastAPI endpoint
from app.services.unified_claude_sdk import get_unified_claude_client

@router.get("/api/costs/ai")
async def get_ai_costs():
    client = await get_unified_claude_client()
    stats = client.get_stats()

    return {
        "total_requests": stats["total"]["requests"],
        "total_cost_usd": stats["total"]["cost_usd"],
        "cost_per_request": stats["total"]["average_cost_per_request"],
        "providers": stats["providers"],
        "savings_vs_claude_only": calculate_savings(stats)
    }
```

## 🎓 Best Practices

### 1. Start with Auto-Routing

```python
# Let the system decide
response = await client.generate(
    prompt="...",
    complexity=None  # Auto-detect based on task
)
```

### 2. Monitor and Adjust

```python
# Check stats after 100 requests
if stats["providers"]["deepseek"]["requests"] < 50:
    # Too much Claude usage - adjust complexity detection
    complexity = "simple"  # Force more DeepSeek usage
```

### 3. Use Caching for Repeated Prompts

```python
# System prompts that don't change
if using_same_system_prompt:
    enable_caching = True
```

### 4. Budget Limits

```python
# Prevent overspending
response = await client.generate(
    prompt="...",
    budget_limit_usd=0.001  # Max $0.001 per request
)
```

## 🐛 Troubleshooting

### "Provider not available" Error

Check your `.env` file:
```bash
cat .env | grep DEEPSEEK_API_KEY
# Should output: DEEPSEEK_API_KEY=sk-...
```

### DeepSeek Not Being Used

Check complexity setting:
```python
# Force DeepSeek for testing
response = await client.generate(
    prompt="...",
    provider="deepseek"  # Force DeepSeek
)
```

### High Costs

Check provider distribution:
```python
stats = client.get_stats()
deepseek_pct = stats["providers"]["deepseek"]["requests"] / stats["total"]["requests"]
print(f"DeepSeek usage: {deepseek_pct:.0%}")  # Should be >50% for savings
```

## ✅ Success Metrics

After running for 24 hours, you should see:

- ✅ DeepSeek handling 60-80% of requests
- ✅ Average cost per request < $0.0005
- ✅ Total cost reduction of 50-70%
- ✅ Quality maintained for complex tasks

## 🎉 You're Done!

Your sales agents are now using intelligent AI routing with 11x cost savings on simple tasks!

**Next Steps:**
1. Run 100 test leads to see savings
2. Monitor stats dashboard
3. Adjust routing based on your use case
4. Explore advanced features (caching, vision, streaming)

**Questions?** See full docs in `UNIFIED_CLAUDE_SDK.md`

---

**Cost Savings Calculator:**

```
Daily leads: 1000
% Simple tasks: 60%
% Complex tasks: 40%

Before (All Claude):
  1000 × $0.0011 = $11.00/day

After (Hybrid):
  600 × $0.0001 (DeepSeek) = $0.06/day
  400 × $0.0011 (Claude) = $4.40/day
  Total = $4.46/day

Savings: $6.54/day = $196/month = $2,352/year 🎉
```
