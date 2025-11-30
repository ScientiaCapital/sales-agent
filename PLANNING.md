# sales-agent - Architecture & Planning

**Last Updated**: 2025-11-30

---

## Tech Stack

Python 3.11 | FastAPI | PostgreSQL | Redis | Supabase | Cerebras | LangGraph

---

## Architecture Overview

### Data Flow
```
CSV Import → ICP Scoring → Hunter.io Enrichment → Supabase Star Schema → BDR Work Queue
```

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| LangGraph Agents | AI-powered lead processing | `backend/app/services/langgraph/agents/` |
| Lead Scorer | ICP scoring algorithm | `backend/create_gold_standard_lists.py` |
| Enrichment Pipeline | Hunter.io contact discovery | `backend/enrich_gold_standard_batch.py` |
| Supabase Sync | Data warehouse sync | `backend/sync_gold_standard_to_supabase.py` |

---

## Data Architecture (Supabase Star Schema)

### Source of Truth Tables
| Table | Purpose | Records |
|-------|---------|---------|
| `dim_companies` | Master lead list | 6,568 |
| `dim_contacts` | ATL/BTL contacts | 562 |

### Materialized Views
- `mv_icp_gold_leads` - Dashboard view
- `mv_bdr_work_queue` - Tim's prioritized tasks

### ICP Tiers
| Tier | Score Range | Meaning |
|------|-------------|---------|
| PLATINUM | 80+ | Best leads |
| GOLD | 65-79 | Strong leads |
| SILVER | 50-64 | Good leads |
| BRONZE | 35-49 | Working pipeline |

---

## Key Patterns

### Check-Then-Insert (Supabase)
```python
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_map = {r['normalized_name'] for r in existing.data}
if normalized not in existing_map:
    # INSERT
else:
    # UPDATE
```

### Phone Classification
```python
def is_unique_direct(contact_phone, company_phone):
    c_norm = normalize_phone(contact_phone)
    co_norm = normalize_phone(company_phone)
    return c_norm and c_norm != co_norm
```

### Lead Scoring
```
Unique direct phone   +100 pts
Confirmed email       +50 pts
Website/domain        +30 pts
High ATL ratio        +20 pts
Company phone         +10 pts
+ ICP score (0-100)
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- API keys in `.env` only, never hardcoded
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)
- 1 company = 1 lead - Don't inflate counts with multiple contacts

---

## Architecture Decision Records

### ADR-001: Supabase Star Schema
- **Date**: 2025-11-29
- **Decision**: Use star schema with dim_companies and dim_contacts
- **Rationale**: Enables fast dashboard queries via materialized views

### ADR-002: Check-Then-Insert Pattern
- **Date**: 2025-11-29
- **Decision**: Fetch existing records before insert, not upsert
- **Rationale**: Supabase upserts fail silently on unique constraint violations

### ADR-003: Cerebras for AI
- **Date**: 2025-11-20
- **Decision**: Use Cerebras (633ms avg) instead of OpenAI
- **Rationale**: Cost-effective, fast, NO OpenAI policy
