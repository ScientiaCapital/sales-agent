# Unified Claude SDK - Intelligent Routing Between Anthropic & DeepSeek

## 🚀 Overview

The **Unified Claude SDK Service** provides intelligent routing between **Anthropic Claude** (premium quality) and **DeepSeek** (cost-optimized) models using the same Anthropic Python SDK interface.

### Why This Matters

**DeepSeek provides an Anthropic-compatible API**, which means you can use the exact same SDK for both providers by simply changing the `base_url`. This enables:

- ✅ **11x cheaper input tokens** with DeepSeek vs Claude
- ✅ **14x cheaper output tokens** with DeepSeek vs Claude
- ✅ **Same SDK interface** - no code changes needed
- ✅ **Intelligent auto-routing** based on task complexity
- ✅ **Budget-aware decisions** to maximize cost efficiency

---

## 💰 Cost Comparison

| Provider | Input (per 1M tokens) | Output (per 1M tokens) | Best For |
|----------|----------------------|------------------------|----------|
| **Anthropic Claude** | $3.00 | $15.00 | Complex reasoning, creativity, quality |
| **DeepSeek v3** | $0.27 (11x cheaper) | $1.10 (14x cheaper) | Simple tasks, classification, parsing |

### Real-World Example

**Qualifying 1000 leads:**

| Scenario | Provider | Cost | Savings |
|----------|----------|------|---------|
| All with Claude | Anthropic | $11.00 | - |
| Simple leads with DeepSeek | DeepSeek | $1.00 | **$10.00 (91%)** |
| Hybrid (auto-route) | Mixed | $3.50 | **$7.50 (68%)** |

---

## 🎯 How It Works

### Architecture

```
Lead Input
    ↓
Complexity Detection
    ↓
Routing Decision
    ├─→ SIMPLE → DeepSeek (11x cheaper)
    ├─→ MEDIUM → Auto-route based on budget
    └─→ COMPLEX → Claude (best quality)
    ↓
Same Anthropic SDK
    ├─→ base_url: https://api.anthropic.com (Claude)
    └─→ base_url: https://api.deepseek.com (DeepSeek)
    ↓
Response
```

### Key Innovation: Same SDK, Different Endpoint

```python
from anthropic import AsyncAnthropic

# Claude client
claude_client = AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://api.anthropic.com"  # Anthropic
)

# DeepSeek client (same SDK!)
deepseek_client = AsyncAnthropic(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"  # DeepSeek (Anthropic-compatible!)
)
```

---

## 🔧 Setup

### 1. Environment Variables

Add to your `.env` file:

```bash
# Anthropic Claude (already set up)
ANTHROPIC_API_KEY=your_anthropic_key_here

# DeepSeek (NEW - add this)
DEEPSEEK_API_KEY=your_deepseek_key_here
```

### 2. Get DeepSeek API Key

1. Visit https://platform.deepseek.com/
2. Sign up / Log in
3. Generate API key
4. Add to `.env`

### 3. Installation

The Anthropic SDK is already installed:
```bash
# Already in requirements.txt:
anthropic==0.41.0
```

No additional dependencies needed!

---

## 📖 Usage

### Basic Usage

```python
from app.services.unified_claude_sdk import get_unified_claude_client

# Get singleton client
client = await get_unified_claude_client()

# Auto-routing based on complexity
response = await client.generate(
    prompt="Qualify this lead: TechCorp Inc, SaaS, 50-200 employees",
    complexity="simple",  # Will use DeepSeek (cheap)
    max_tokens=500
)

print(f"Provider: {response.provider}")  # deepseek
print(f"Cost: ${response.cost_usd:.6f}")  # $0.0001
print(f"Content: {response.content}")
```

### Force Specific Provider

```python
# Force Claude for quality
response = await client.generate(
    prompt="Analyze this complex business scenario...",
    provider="anthropic",  # Force Claude
    max_tokens=2000
)

# Force DeepSeek for cost
response = await client.generate(
    prompt="Simple classification task",
    provider="deepseek",  # Force DeepSeek
    max_tokens=200
)
```

### Streaming Responses

```python
# Real-time streaming for better UX
async for chunk in client.generate_stream(
    prompt="Write a marketing email...",
    complexity="medium"  # Auto-routes
):
    print(chunk, end="", flush=True)
```

### Prompt Caching (90% Cost Savings)

```python
# Anthropic only - cache system prompts
system_prompt = """You are an expert sales agent..."""  # Long prompt

# First request (full cost)
response1 = await client.generate(
    prompt="Qualify lead A",
    system_prompt=system_prompt,
    enable_caching=True,  # Enable caching
    provider="anthropic"
)

# Subsequent requests (90% cheaper!)
response2 = await client.generate(
    prompt="Qualify lead B",
    system_prompt=system_prompt,  # Same system prompt - cached!
    enable_caching=True
)

print(f"First: ${response1.cost_usd:.6f}")   # $0.0011
print(f"Second: ${response2.cost_usd:.6f}")  # $0.0001 (cached!)
```

---

## 🤖 Integration with Existing Agents

### QualificationAgent V2 (Example)

See `backend/app/services/langgraph/agents/qualification_agent_v2.py` for a complete example.

```python
from app.services.langgraph.agents.qualification_agent_v2 import QualificationAgentV2

# Initialize agent
agent = QualificationAgentV2()
await agent.initialize()

# Auto-routing
result = await agent.qualify_lead({
    "company_name": "Acme Corp",
    "industry": "SaaS",
    "company_size": "50-200"
})

print(f"Score: {result.qualification_score}")
print(f"Tier: {result.tier}")
print(f"Provider: {result.provider_used}")  # deepseek or anthropic
print(f"Cost: ${result.cost_usd:.6f}")
```

### Migrating Existing Agents

**Before (LangChain only):**
```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
result = llm.invoke("Analyze this...")
```

**After (Unified SDK with cost optimization):**
```python
from app.services.unified_claude_sdk import get_unified_claude_client

client = await get_unified_claude_client()
response = await client.generate(
    prompt="Analyze this...",
    complexity="medium"  # Auto-routes to cheapest suitable provider
)
```

**Best Approach (Hybrid - keep both):**
```python
# Keep LangChain for orchestration
from langchain_anthropic import ChatAnthropic

# Add Unified SDK for advanced features
from app.services.unified_claude_sdk import get_unified_claude_client

class MyAgent:
    def __init__(self):
        # LangChain for agent orchestration
        self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

        # Unified SDK for cost optimization
        self.claude_sdk = None

    async def initialize(self):
        self.claude_sdk = await get_unified_claude_client()

    async def process(self, input_data):
        # Use LangChain for complex agent workflows
        if self.requires_tools():
            return self.llm.invoke(input_data)

        # Use Unified SDK for simple tasks with cost optimization
        return await self.claude_sdk.generate(
            prompt=input_data,
            complexity="simple"  # DeepSeek - 11x cheaper!
        )
```

---

## 🎨 Complexity Detection

The system auto-detects task complexity to route intelligently:

### Simple → DeepSeek
- Lead qualification (limited data)
- Classification tasks
- Simple parsing
- Straightforward Q&A

### Medium → Auto-route (budget-aware)
- Summarization
- Basic analysis
- Content generation
- Medium-complexity tasks

### Complex → Claude
- Complex reasoning
- Creative writing
- Multi-step analysis
- High-quality content
- Vision tasks (images)

### Manual Override

```python
# Let the system decide
response = await client.generate(
    prompt="...",
    complexity=None  # Auto-detect (default: MEDIUM)
)

# Force complexity level
response = await client.generate(
    prompt="...",
    complexity="simple"  # Force DeepSeek routing
)
```

---

## 📊 Statistics & Monitoring

### Get Usage Stats

```python
client = await get_unified_claude_client()

# Get statistics
stats = client.get_stats()

print(stats)
# Output:
# {
#   "providers": {
#     "anthropic": {"requests": 10, "total_cost": 0.011, "total_tokens": 5000},
#     "deepseek": {"requests": 90, "total_cost": 0.009, "total_tokens": 45000}
#   },
#   "total": {
#     "requests": 100,
#     "cost_usd": 0.020,
#     "average_cost_per_request": 0.0002
#   },
#   "savings": {
#     "deepseek_vs_claude_input": "11x cheaper",
#     "deepseek_vs_claude_output": "14x cheaper"
#   }
# }
```

### Cost Estimation

```python
# Estimate before making request
estimated_cost = client.estimate_cost(
    prompt="Long prompt here...",
    max_tokens=1000,
    provider="deepseek"
)

print(f"Estimated cost: ${estimated_cost:.6f}")

# Check if within budget
if estimated_cost < budget_limit:
    response = await client.generate(...)
```

---

## 🔬 Testing

Run the test suite:

```bash
# Unit tests (no API keys needed)
pytest backend/tests/test_unified_claude_sdk.py -v

# Integration tests (requires API keys)
pytest backend/tests/test_unified_claude_sdk.py -v -m integration

# Performance benchmarks
pytest backend/tests/test_unified_claude_sdk.py -v -m benchmark
```

---

## 🚀 Production Best Practices

### 1. Budget Management

```python
# Set budget limit
response = await client.generate(
    prompt="...",
    budget_limit_usd=0.001,  # Max $0.001 per request
    complexity="medium"  # Will choose DeepSeek if possible
)
```

### 2. Fallback Strategy

```python
# Try DeepSeek first, fall back to Claude
try:
    response = await client.generate(
        prompt="...",
        provider="deepseek",
        max_tokens=500
    )
except Exception as e:
    logger.warning(f"DeepSeek failed: {e}, falling back to Claude")
    response = await client.generate(
        prompt="...",
        provider="anthropic",
        max_tokens=500
    )
```

### 3. Caching Strategy (Anthropic only)

```python
# Cache long system prompts for 90% savings
SYSTEM_PROMPT = """Very long system prompt..."""  # This gets cached

# All requests with same system prompt are 90% cheaper
for lead in leads:
    response = await client.generate(
        prompt=f"Qualify: {lead}",
        system_prompt=SYSTEM_PROMPT,  # Cached!
        enable_caching=True,
        provider="anthropic"
    )
```

### 4. Health Monitoring

```python
# Check provider health
health = await client.health_check()

if not health.get("deepseek"):
    logger.error("DeepSeek unavailable - using Claude")
    # Route all traffic to Claude
```

---

## 🔐 Security & Rate Limiting

### API Key Management

```bash
# Store securely in environment
ANTHROPIC_API_KEY=sk-ant-api03-...
DEEPSEEK_API_KEY=sk-...

# Never commit to git
echo ".env" >> .gitignore
```

### Rate Limits

| Provider | Rate Limit | Tokens per Minute |
|----------|------------|-------------------|
| **Anthropic** | 50 requests/min | 40,000 TPM (Tier 1) |
| **DeepSeek** | 100 requests/min | 300,000 TPM |

The Unified SDK automatically handles rate limiting via retry logic.

---

## 📈 Performance Targets

| Task Type | Provider | Target Latency | Target Cost |
|-----------|----------|----------------|-------------|
| Simple qualification | DeepSeek | <2000ms | $0.0001 |
| Medium analysis | DeepSeek | <3000ms | $0.0003 |
| Complex reasoning | Claude | <4000ms | $0.0011 |
| Cached request | Claude | <1500ms | $0.0001 |

---

## 🎓 Advanced Features

### Vision API (Anthropic Only)

```python
# Analyze images with Claude
import base64

with open("business_card.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

response = await client.generate_with_vision(
    prompt="Extract contact information from this business card",
    image_data=image_data,
    image_media_type="image/jpeg",
    max_tokens=500
)

print(response.content)  # Extracted contact info
```

### Custom Model Selection

```python
# Use specific models
response = await client.generate(
    prompt="...",
    provider="anthropic",
    model_override="claude-3-5-haiku-20241022"  # Faster, cheaper Claude
)

response = await client.generate(
    prompt="...",
    provider="deepseek",
    model_override="deepseek-reasoner"  # DeepSeek reasoning model
)
```

---

## 🐛 Troubleshooting

### DeepSeek API Key Not Working

```bash
# Test API key
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Provider Not Available

```python
# Check which providers are initialized
client = await get_unified_claude_client()
print(client.clients.keys())  # Should show both providers

# If missing, check .env file
import os
print(os.getenv("ANTHROPIC_API_KEY"))  # Should not be empty
print(os.getenv("DEEPSEEK_API_KEY"))  # Should not be empty
```

### Cost Tracking Not Working

```bash
# Ensure cost optimizer is running
curl http://localhost:8000/health
```

---

## 📚 Resources

- **DeepSeek API Docs**: https://api-docs.deepseek.com/guides/anthropic_api
- **Anthropic SDK**: https://github.com/anthropics/anthropic-sdk-python
- **DeepSeek Models**: https://platform.deepseek.com/models
- **Prompt Caching**: https://docs.anthropic.com/claude/docs/prompt-caching

---

## 🎯 Next Steps

1. **Get DeepSeek API Key**: https://platform.deepseek.com/
2. **Add to `.env`**: `DEEPSEEK_API_KEY=sk-...`
3. **Test integration**: `python backend/app/services/langgraph/agents/qualification_agent_v2.py`
4. **Monitor savings**: Check `client.get_stats()` after running leads
5. **Optimize agents**: Migrate simple tasks to DeepSeek for 11x cost savings

---

## 💡 Tips for Maximum Savings

1. ✅ **Use DeepSeek for simple tasks** (qualification, classification)
2. ✅ **Use Claude for complex tasks** (reasoning, creativity)
3. ✅ **Enable caching for repeated system prompts** (90% savings on Claude)
4. ✅ **Set budget limits** to prevent cost overruns
5. ✅ **Monitor statistics** to optimize routing decisions
6. ✅ **Batch simple requests** to DeepSeek for volume discounts
7. ✅ **Use haiku models** for faster, cheaper Claude responses when quality isn't critical

---

**Result**: Save **60-90% on AI costs** while maintaining quality where it matters! 🎉
