---
description: "6-phase PRP execution workflow"
---

# Execute PRP for sales-agent

## Usage

```
/execute-prp <PRP-number>
```

## 6-Phase Workflow

### Phase 1: Context Loading

Read these files:
- PRP document: `PRPs/PRP-<NNN>-*.md`
- Project rules: `CLAUDE.md`, `.claude/CLAUDE.md`
- Architecture: `PLANNING.md`
- Current status: `TASK.md`

### Phase 2: ULTRATHINK

Before writing code:
1. Analyze requirements deeply
2. Identify all files to modify
3. Break into atomic tasks
4. Create rollback strategy
5. Estimate complexity

**Ask yourself**: Does this follow existing patterns in `backend/app/services/`?

### Phase 3: Implementation

Execute tasks in dependency order:
1. Create new files first
2. Modify existing files second
3. Run `python -m py_compile <file>` after each change
4. Commit logical units

**Pattern Reference**:
- Services: `backend/app/services/`
- Agents: `backend/app/services/langgraph/agents/`
- API routes: `backend/app/api/`

### Phase 4: Validation

Run full validation:
```bash
cd backend
source ../venv/bin/activate
pytest tests/ -v --tb=short
```

Check all PRP success criteria.

### Phase 5: Review

Self-review checklist:
- [ ] Follows existing patterns
- [ ] No hardcoded API keys
- [ ] NO OpenAI usage (Cerebras/Claude/DeepSeek only)
- [ ] Tests added for new functionality
- [ ] Error handling in place

### Phase 6: Documentation

- Update `TASK.md` with completion status
- Update `PLANNING.md` if architecture changed
- Create follow-up PRPs if needed

---

## Validation Commands

```bash
# Quick check
cd backend && pytest tests/ -v -x

# Full validation
/validate
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- Never skip validation phase
- All API keys from `.env` only
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)
- 1 company = 1 lead (don't inflate counts)
