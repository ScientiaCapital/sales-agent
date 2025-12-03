# Generate PRP

Create an implementation plan (PRP document).

**Usage**: `/generate-prp [feature-name]`

---

## Process

### 1. Gather Requirements
Ask about:
- What does it do?
- How do we know it works?
- External dependencies?
- Constraints?

### 2. Research Codebase
```bash
# Find similar patterns
ls backend/app/services/
ls backend/app/api/
ls backend/tests/
```

### 3. Create PRP
Save to `PRPs/PRP-<NNN>-<feature-name>.md`

Template:
```markdown
# PRP-<NNN>: Feature Name

## Summary
Brief description

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Implementation Steps
1. Step 1
2. Step 2

## Files to Modify
- `backend/app/...`

## Tests Required
- Test case 1
```

---

## Key Patterns

### Supabase (Check-Then-Insert)
```python
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_map = {r['normalized_name'] for r in existing.data}
if normalized not in existing_map:
    # INSERT
```

### Lead Scoring
```python
# 1 company = 1 lead (don't inflate with contacts)
score = icp_score + phone_bonus + email_bonus
```

---

## Critical Rules

- **NO OpenAI** - Cerebras, Claude, DeepSeek only
- API keys in `.env` only
