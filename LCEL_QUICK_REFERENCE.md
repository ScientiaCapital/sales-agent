# LCEL 2025 - Quick Reference Guide
## Key Patterns for Lead Qualification Agent

---

## 1. Basic LCEL Chain (30 seconds)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# Chain: Prompt → Model → Parser
chain = (
    ChatPromptTemplate.from_template("Qualify this lead: {lead}")
    | ChatOpenAI(model="gpt-4o")
    | StrOutputParser()
)

result = chain.invoke({"lead": "John from Acme Corp..."})
```

---

## 2. Structured Output (PRIMARY PATTERN - 2025)

```python
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

class LeadScore(BaseModel):
    score: float = Field(description="0.0-1.0")
    action: str = Field(description="next step")

# This is the modern way
llm = ChatOpenAI(model="gpt-4o", temperature=0)
structured_llm = llm.with_structured_output(LeadScore)

# Returns LeadScore object, not string
result = structured_llm.invoke("Qualify: John from Acme...")
print(result.score)  # 0.85 (float, not string!)
```

**Why it's better than PydanticOutputParser:**
- ✅ Guaranteed to return Pydantic object (no parsing failures)
- ✅ Type-safe (IDE autocomplete works)
- ✅ No need to parse JSON strings
- ✅ Works with all major LLM providers

---

## 3. Cerebras Integration (Ultra-Fast)

```python
from langchain_openai import ChatOpenAI

# Same OpenAI SDK interface, Cerebras backend
llm = ChatOpenAI(
    model="llama3.1-8b",
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1",
)

# Works seamlessly in any LCEL chain
chain = prompt | llm | output_parser

# Benchmark: 633ms average latency, $0.000006 per request!
```

---

## 4. Streaming (For Real-Time UI)

```python
# Sync streaming
for chunk in chain.stream({"lead": lead_data}):
    print(chunk, end="", flush=True)

# Async streaming (production)
async for chunk in chain.astream({"lead": lead_data}):
    await websocket.send(chunk)
```

---

## 5. Batching (For Throughput)

```python
# Process 100 leads in parallel
leads = [lead1, lead2, ..., lead100]

# Synchronous
results = chain.batch(leads)

# Asynchronous (better)
results = await chain.abatch(leads, config={"max_concurrency": 5})

# Get results as they complete (don't wait for all)
async for idx, result in chain.abatch_as_completed(leads):
    process(result)  # Start immediately, don't wait
```

---

## 6. Pipe Operator Composition

```python
# Sequential composition with |
chain = prompt | llm | parser

# Parallel execution
from langchain_core.runnables import RunnableParallel

parallel = RunnableParallel(
    score=qualification_chain,
    enrichment=enrichment_chain,
)
result = parallel.invoke(lead_data)
# Returns: {"score": ..., "enrichment": ...}

# Add custom logic
chain = (
    RunnableLambda(preprocess)
    | prompt
    | llm
    | RunnableLambda(postprocess)
)
```

---

## 7. Performance Tips

| Technique | Latency Impact | Cost Impact | When to Use |
|-----------|----------------|------------|------------|
| **Streaming** | ↓ Perceived latency | Same | Real-time UI updates |
| **Batching** | Same (parallel) | ↓ Can use cheaper models | Background jobs |
| **Caching** | ↓ 100x for cache hits | ↓ Skip API calls | Repeated queries |
| **Async** | ↓ Better concurrency | Same | Production servers |
| **Cerebras** | ↓ 633ms avg | ↓ 300x cheaper | High volume |

---

## 8. Common Gotchas ⚠️

| Mistake | Impact | Fix |
|---------|--------|-----|
| Using string parser for structured data | String, not object | Use `with_structured_output()` |
| Blocking I/O in stream loop | Pipeline hangs | Use async/await |
| No temperature setting | Random results | Set `temperature=0` for deterministic |
| Ignoring timeouts | Can hang forever | Add `asyncio.timeout()` |
| Wrong Pydantic types | Parse failures | Use `Field(description=...)` |
| Not streaming for UI | Slow perceived speed | Use `.astream()` by default |

---

## 9. Production Checklist

```python
# ✅ DO
structured_llm = llm.with_structured_output(MySchema)  # Guaranteed structure
chain = prompt | llm | parser                           # LCEL composition
results = await chain.abatch(leads)                     # Async + parallel
async for chunk in chain.astream(lead):                 # Stream to UI
    yield chunk

cerebras_llm = ChatOpenAI(base_url="https://api.cerebras.ai/v1")  # Cost efficient

# ❌ DON'T
from langchain.chains import LLMChain              # Legacy
result = llm.invoke(...)                           # Blocking, not async
chain = prompt | llm | PydanticOutputParser(...)   # Use with_structured_output()
for chunk in chain.stream(lead):                   # Blocking I/O
    db.write_sync(chunk)                           # Pauses pipeline
```

---

## 10. Implementation Roadmap

### Phase 1: Basic (30 min)
- [ ] Set up Cerebras ChatOpenAI
- [ ] Create LeadScore Pydantic model
- [ ] Build basic chain with `|` operator
- [ ] Use `with_structured_output()`

### Phase 2: Production Ready (1-2 hours)
- [ ] Add async/streaming support
- [ ] Implement batching with `max_concurrency`
- [ ] Add error handling + timeouts
- [ ] Add caching for repeated leads

### Phase 3: Optimized (2-4 hours)
- [ ] Implement model routing (Cerebras vs Claude)
- [ ] Add WebSocket streaming to frontend
- [ ] Monitor costs and latency
- [ ] Add circuit breaker for failures

---

## Files to Reference

- **Full Guide**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/LCEL_PATTERNS_2025.md`
- **Project Code**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/app/`
- **Existing Pattern**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/app/services/cerebras.py`

---

## Latest API Status (Oct 2025)

| API | Status | Notes |
|-----|--------|-------|
| Pipe operator `\|` | ✅ Standard | Use this for everything |
| `with_structured_output()` | ✅ Recommended | Primary pattern |
| `PydanticOutputParser` | ⚠️ Legacy | Still works, not preferred |
| `LLMChain` | ⚠️ Legacy | Use LCEL instead |
| `.astream()` / `.abatch()` | ✅ Preferred | Use in production |
| Caching | ✅ Full support | InMemory or SQLite |

---

**Research Completed**: October 28, 2025
**Confidence Level**: High (sourced from official Context7 + LangChain docs)
**Ready to Implement**: Yes ✅
