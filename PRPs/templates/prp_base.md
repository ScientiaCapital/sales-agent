# PRP: {{FEATURE_NAME}}

**Project**: sales-agent
**Date**: {{DATE}}
**Status**: Draft | In Progress | Complete | Abandoned

---

## Goal

[What problem does this solve? Why now?]

## Success Criteria

- [ ] Implementation complete
- [ ] Unit tests pass (`pytest tests/ -v`)
- [ ] `/validate` passes 100%
- [ ] Documentation updated

---

## Technical Design

### Tech Stack

Python 3.11 | FastAPI | PostgreSQL | Redis | Supabase | Cerebras | LangGraph

### Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/app/services/...` | Create/Modify | ... |
| `backend/tests/...` | Create | ... |

### Implementation Tasks

1. [ ] Task 1 - Description
2. [ ] Task 2 - Description
3. [ ] Task 3 - Description

---

## Existing Patterns to Follow

### Supabase Check-Then-Insert
```python
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_map = {r['normalized_name'] for r in existing.data}
```

### LangGraph Agent Structure
```python
class MyAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: AgentState) -> AgentState:
        pass
```

### Lead Scoring
```python
# 1 company = 1 lead
score = icp_score + phone_bonus + email_bonus
```

---

## Validation Gates

### Gate 1: Syntax Check
```bash
cd backend
python -m py_compile app/path/to/new_file.py
```

### Gate 2: Unit Tests
```bash
cd backend
pytest tests/ -v --tb=short
```

### Gate 3: Full Validation
```bash
/validate
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- API keys in `.env` only, never hardcoded
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)
- 1 company = 1 lead - Don't inflate counts with multiple contacts

---

## Gotchas

- Supabase upserts fail on unique constraints - use check-then-insert pattern
- Phone numbers must be normalized before comparison
- FK constraints prevent deletion - mark as `[DUPLICATE]` instead
