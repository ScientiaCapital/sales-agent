# Execute PRP

Execute an implementation plan (PRP document).

**Usage**: `/execute-prp [PRP-number]`

---

## Workflow

### Phase 1: Load Context
```bash
# Read the PRP
cat PRPs/PRP-<number>-*.md

# Read project rules
cat CLAUDE.md .claude/CLAUDE.md
```

### Phase 2: Plan
- Break into atomic tasks
- Identify dependencies
- Create rollback strategy

### Phase 3: Implement
- Create new files first
- Modify existing files second
- Test after each change

### Phase 4: Validate
```bash
cd backend && source ../venv/bin/activate
pytest tests/ -v --tb=short
```

### Phase 5: Review
- [ ] Follows existing patterns
- [ ] No hardcoded API keys
- [ ] NO OpenAI (Cerebras/Claude only)
- [ ] Tests added
- [ ] Error handling

### Phase 6: Ship
```bash
git add -A && git commit -m "feat: implement PRP-<number>"
git push origin main
```

---

## Critical Rules

- **NO OpenAI models** - Cerebras, Claude, DeepSeek only
- API keys from `.env` only
- Close CRM is read-only
