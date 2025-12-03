---
description: "Create implementation blueprints (PRPs)"
---

# Generate PRP for sales-agent

## Usage

```
/generate-prp <feature-name>
```

## Process

### 1. Load Context

Read these files first:
- `CLAUDE.md` - Project rules and patterns
- `.claude/CLAUDE.md` - Detailed technical guide
- `PLANNING.md` - Architecture decisions
- `.claude/PROJECT_CONTEXT.md` - Current status

### 2. Gather Requirements

Ask the user for:
- **Feature description**: What does it do?
- **Success criteria**: How do we know it works?
- **Dependencies**: External APIs, libraries?
- **Constraints**: Performance, security, compatibility?

### 3. Research Codebase

Search for similar patterns:
- Check `backend/app/services/` for service patterns
- Check `backend/app/services/langgraph/agents/` for agent patterns
- Check `backend/tests/` for test patterns

### 4. Generate PRP

Create `PRPs/PRP-<NNN>-<feature-name>.md` using template at `PRPs/templates/prp_base.md`

### 5. Add to TASK.md

Link new PRP in task list.

---

## Key Patterns to Follow

### Supabase Pattern (Check-Then-Insert)
```python
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_map = {r['normalized_name'] for r in existing.data}
if normalized not in existing_map:
    # INSERT
else:
    # UPDATE
```

### LangGraph Agent Pattern
```python
class MyAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def run(self, state: AgentState) -> AgentState:
        # Process and return updated state
        pass
```

### Lead Scoring Pattern
```python
# 1 company = 1 lead (don't inflate with multiple contacts)
score = icp_score + phone_bonus + email_bonus
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- Include validation gates in every PRP
- Reference existing patterns, don't invent new ones
- API keys in `.env` only
