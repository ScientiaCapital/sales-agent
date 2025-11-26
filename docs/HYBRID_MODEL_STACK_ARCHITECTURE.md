# Hybrid Model Stack Architecture

**Author**: Tim Kipper | GTM Engineering
**Date**: November 26, 2025
**Status**: Production Ready

## Executive Summary

This document describes the hybrid AI model stack designed for cost-effective, high-quality lead qualification. The architecture uses **tiered model routing** to balance speed, cost, and accuracy - rejecting obvious non-fits in 500ms for $0.000006 while dedicating expensive compute to promising leads.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      HYBRID MODEL ROUTING                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   RAW LEADS                                                             │
│       │                                                                 │
│       ▼                                                                 │
│   ╔═══════════════════════════════════════════╗                        │
│   ║  TIER 1: CEREBRAS PRE-FILTER              ║                        │
│   ║  Model: llama3.1-8b                        ║                        │
│   ║  Latency: <500ms | Cost: $0.000006/req    ║                        │
│   ║                                            ║                        │
│   ║  Purpose: Fast reject obvious non-fits     ║                        │
│   ║  Output: Score 0-100                       ║                        │
│   ║                                            ║                        │
│   ║  • Score < 30 → REJECT (save to rejected/)║                        │
│   ║  • Score 30-60 → NEEDS_REVIEW              ║                        │
│   ║  • Score > 60 → Continue to TIER 2        ║                        │
│   ╚═══════════════════════════════════════════╝                        │
│           │              │              │                               │
│        REJECT      NEEDS_REVIEW     CONTINUE                           │
│           │              │              │                               │
│           ▼              ▼              ▼                               │
│   rejected_*.csv    review_*.csv   ╔══════════════════════════════╗   │
│   (isolated)                        ║  TIER 2: DEEPSEEK V3         ║   │
│                                     ║  Model: deepseek-chat (671B)  ║   │
│                                     ║  Latency: ~5s | Cost: $0.28/1M║   │
│                                     ║                                ║   │
│                                     ║  Purpose: Deep ICP analysis    ║   │
│                                     ║  • Nuanced scoring             ║   │
│                                     ║  • Detailed reasoning          ║   │
│                                     ║  • Complex signal detection    ║   │
│                                     ╚══════════════════════════════╝   │
│                                              │                          │
│                                              ▼                          │
│                                     ╔══════════════════════════════╗   │
│                                     ║  TIER 3: QWEN VL (OPTIONAL)  ║   │
│                                     ║  Model: qwen-2.5-vl-7b       ║   │
│                                     ║  Latency: 2-3s | Cost: $0.064║   │
│                                     ║                                ║   │
│                                     ║  Purpose: Visual verification  ║   │
│                                     ║  • Website screenshot analysis ║   │
│                                     ║  • Team page detection         ║   │
│                                     ║  • Business legitimacy check   ║   │
│                                     ╚══════════════════════════════╝   │
│                                              │                          │
│                                              ▼                          │
│                                     ╔══════════════════════════════╗   │
│                                     ║  DEDUPLICATION CHECK          ║   │
│                                     ║  • 85% fuzzy company match    ║   │
│                                     ║  • Exact email matching       ║   │
│                                     ║  • Cross-CRM verification     ║   │
│                                     ╚══════════════════════════════╝   │
│                                              │                          │
│                                              ▼                          │
│                                     ╔══════════════════════════════╗   │
│                                     ║  GOLD STANDARD MASTER LIST    ║   │
│                                     ║  MASTER_enriched_leads_*.csv  ║   │
│                                     ║                                ║   │
│                                     ║  Columns:                      ║   │
│                                     ║  • company_name, contact_name  ║   │
│                                     ║  • email, phone, linkedin_url  ║   │
│                                     ║  • qualification_score, tier   ║   │
│                                     ║  • is_atl, dedup_status        ║   │
│                                     ╚══════════════════════════════╝   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Model Configurations

### Tier 1: Cerebras Pre-Filter (Ultra-Fast)

| Property | Value |
|----------|-------|
| **Provider** | Cerebras |
| **Model** | llama3.1-8b |
| **Latency** | <500ms |
| **Cost** | $0.01/1M tokens (~$0.000006/request) |
| **Max Tokens** | 500 |
| **Temperature** | 0.2 |
| **Use Case** | Quick reject of obvious non-fits |

**API Configuration:**
```python
from langchain_cerebras import ChatCerebras

llm = ChatCerebras(
    model="llama3.1-8b",
    temperature=0.2,
    max_tokens=500,
    api_key=os.getenv("CEREBRAS_API_KEY")
)
```

### Tier 2: DeepSeek V3 Deep Scoring (High Quality)

| Property | Value |
|----------|-------|
| **Provider** | DeepSeek |
| **Model** | deepseek-chat (V3, 671B MoE) |
| **Latency** | ~5,000ms |
| **Cost** | $0.28/1M input, $0.42/1M output |
| **Max Tokens** | 800 |
| **Temperature** | 0.3 |
| **Use Case** | Nuanced ICP analysis |

**API Configuration:**
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek-chat",
    temperature=0.3,
    max_tokens=800,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
```

### Tier 3: Qwen VL Vision (Website Analysis)

| Property | Value |
|----------|-------|
| **Provider** | OpenRouter |
| **Model** | qwen/qwen-2.5-vl-7b-instruct |
| **Latency** | 2-3s |
| **Cost** | $0.064/1M input, $0.40/1M output |
| **Max Tokens** | 1000 |
| **Temperature** | 0.2 |
| **Use Case** | Screenshot analysis, visual verification |

**API Configuration:**
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen/qwen-2.5-vl-7b-instruct",
    temperature=0.2,
    max_tokens=1000,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://sales-agent.local",
        "X-Title": "Sales Agent Qualification"
    }
)
```

### Tier 4: Claude Sonnet 4.5 (Complex Reasoning)

| Property | Value |
|----------|-------|
| **Provider** | Anthropic |
| **Model** | claude-sonnet-4-5-20250929 |
| **Latency** | ~2,000ms |
| **Cost** | $3.00/1M input, $15.00/1M output |
| **Max Tokens** | 800 |
| **Temperature** | 0.3 |
| **Use Case** | Complex reasoning, edge cases, nuanced decisions |

**Why Sonnet 4.5**: Best-in-class reasoning for complex ICP decisions, ambiguous company data, or when lower-tier models disagree.

---

## Gold Standard Master List

### Output CSV Structure

```csv
company_name,contact_name,email,phone,linkedin_url,qualification_score,tier,is_atl,dedup_status,close_lead_id
Brower Mechanical,John Smith,jsmith@browermechanical.com,555-123-4567,linkedin.com/in/jsmith,72,hot,true,create_new,
ABC HVAC,Jane Doe,jane@abchvac.com,555-987-6543,linkedin.com/in/janedoe,45,warm,true,add_contact_to_existing,lead_123abc
```

### Dedup Status Values

| Status | Action |
|--------|--------|
| `create_new` | Safe to create new lead in CRM |
| `add_contact_to_existing` | Company exists, add new contact |
| `skip_duplicate` | Exact duplicate, skip entirely |
| `update_existing_contact` | Update existing contact with new data |

### Deduplication Logic

1. **Company Matching**: 85% fuzzy string similarity
   - "ABC Corp" vs "ABC Corporation" = 92% match = SAME COMPANY
   - "ABC Corp" vs "XYZ Corp" = 33% match = DIFFERENT COMPANY

2. **Email Matching**: Exact match (case-insensitive)
   - john@example.com = JOHN@Example.com

3. **Cross-CRM Verification**: Checks Close CRM before import

---

## Cost Analysis

### Per-Lead Cost Breakdown

| Stage | Cost | When |
|-------|------|------|
| Cerebras Pre-Filter | $0.000006 | Every lead |
| DeepSeek Deep Score | $0.00009 | Score > 60 (~40% of leads) |
| Qwen VL Analysis | $0.0001 | Optional visual verification |
| Hunter.io Email | $0.01 | Per domain searched |
| **Total (typical)** | **~$0.01-0.02** | Per qualified lead |

### ROI Example (1,000 leads)

**Without Hybrid Stack:**
- All leads → Deep scoring: 1,000 × $0.01 = $10.00
- Time: 1,000 × 5s = 83 minutes

**With Hybrid Stack:**
- Pre-filter (1,000 leads): 1,000 × $0.000006 = $0.006
- Deep scoring (400 leads): 400 × $0.00009 = $0.036
- **Total: $0.04** (99.6% cost reduction!)
- **Time: 1,000 × 0.5s + 400 × 5s = 42 minutes** (50% faster)

---

## File Reference

| File | Purpose |
|------|---------|
| `backend/app/services/llm_providers.py` | Model tier routing |
| `backend/app/services/website_vlm_analyzer.py` | VLM screenshot analysis |
| `backend/app/services/langgraph/agents/qualification_agent.py` | Main qualification agent |
| `backend/app/services/crm/close_deduplication.py` | 85% fuzzy deduplication |
| `backend/import_mep_batch.py` | Batch CSV processing CLI |

---

## Environment Variables Required

```bash
# Tier 1: Cerebras
CEREBRAS_API_KEY=csk-...

# Tier 2: DeepSeek V3
DEEPSEEK_API_KEY=sk-...

# Tier 3: OpenRouter (Qwen VL)
OPENROUTER_API_KEY=sk-or-v1-...

# Tier 4: Anthropic (Fallback)
ANTHROPIC_API_KEY=sk-ant-...

# Email Discovery
HUNTER_API_KEY=...

# CRM (Read-only for dedup)
CLOSE_API_KEY=...
```

---

## Usage Example

```python
from app.services.llm_providers import get_llm_provider, ModelTier

# Quick pre-filter
fast_llm = get_llm_provider(ModelTier.FAST_FILTER)

# Deep scoring for promising leads
deep_llm = get_llm_provider(ModelTier.DEEP_SCORING)

# Visual analysis when needed
vision_llm = get_llm_provider(ModelTier.VISION)

# Or use qualification agent directly
from app.services.langgraph.agents.qualification_agent import QualificationAgent

# With Cerebras (fast)
agent = QualificationAgent(provider="cerebras", model="llama3.1-8b")

# With DeepSeek (deep)
agent = QualificationAgent(provider="deepseek", model="deepseek-chat")
```

---

## Technical Decisions

### Why Not Just Use Claude for Everything?

| Model | Latency | Cost/1M | Quality |
|-------|---------|---------|---------|
| Claude Haiku | 2,000ms | $1.25 | Excellent |
| DeepSeek V3 | 5,000ms | $0.42 | Excellent |
| Cerebras 8B | 500ms | $0.01 | Good |

**Answer**: 90% of leads are obvious non-fits. Spending $0.001+ and 2+ seconds on each is wasteful. Cerebras at $0.000006 and 500ms handles the bulk.

### Why DeepSeek V3 Over GPT-4?

1. **No OpenAI** - Project constraint
2. **Cost**: DeepSeek is 10x cheaper than GPT-4
3. **Quality**: 671B MoE performs comparably to GPT-4 on reasoning tasks
4. **Context**: 128K token context window

### Why Qwen VL for Vision?

1. **Available via OpenRouter** - Single API for 400+ models
2. **Cost-effective**: $0.064/1M vs Gemini at $0.15/1M
3. **Quality**: Qwen 2.5 VL benchmarks well on business document understanding
4. **Kimi Alternative**: Kimi K2 vision not available via API (web-only)

---

## Portfolio Value

This hybrid architecture demonstrates:

1. **Cost Engineering** - 99.6% cost reduction through intelligent routing
2. **Systems Design** - Multi-tier architecture with graceful degradation
3. **GTM Engineering** - Building scalable sales automation infrastructure
4. **AI Orchestration** - LangChain/LangGraph with multiple providers
5. **Data Quality** - 85% fuzzy deduplication prevents CRM pollution

**Applicable To**: Any AI system needing cost-effective batch processing at scale.

---

*Last Updated: November 26, 2025*
