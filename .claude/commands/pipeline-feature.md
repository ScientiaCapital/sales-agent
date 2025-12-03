# Pipeline: Feature Development

6-phase TDD workflow with gate controls at every phase.

**Usage**: `/pipeline-feature [feature-description]`

**Example**: `/pipeline-feature Add batch enrichment API endpoint`

---

## Overview

This pipeline enforces:
- TDD approach throughout
- No OpenAI models (Cerebras/Claude/DeepSeek only)
- API keys in .env only
- Code review before commit
- Gate approval at every phase

---

## Phase 0: Planning

### Step 1: Brainstorm
```
I'm using the superpowers:brainstorming skill to refine the feature.

Gather:
- Feature purpose and scope
- Success criteria
- Constraints
- Dependencies on existing code
```

### Step 2: Create Plan
```
I'm using the superpowers:writing-plans skill to create the implementation plan.

Output:
- Database schema (if needed)
- API endpoints
- Service layer changes
- Test specifications
```

### Gate 0: Plan Approval
**Checklist:**
- [ ] Requirements clearly defined
- [ ] Implementation plan created
- [ ] No OpenAI dependencies
- [ ] Scope reasonable

**Ask:** "Phase 0 complete. Proceed to Phase 1 (Database)? (yes/no)"

---

## Phase 1: Database (Sequential Foundation)

### Step 1: Schema Design
```
If database changes needed:
- Design Supabase PostgreSQL schema
- Include RLS policies
- Generate migration SQL
```

### Step 2: Migration File
```sql
-- migrations/XXX_[feature_name].sql
CREATE TABLE IF NOT EXISTS [table_name] (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- columns
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS policies
ALTER TABLE [table_name] ENABLE ROW LEVEL SECURITY;
```

### Gate 1: Schema Approval
**Verification:**
```bash
# Verify no hardcoded keys
! grep -r "sk-" --include="*.sql" . || exit 1
```

**Checklist:**
- [ ] Migration file created (if needed)
- [ ] RLS policies defined
- [ ] No hardcoded keys

**Ask:** "Phase 1 complete. Proceed to Phase 2 (Implementation)? (yes/no)"

---

## Phase 2: Implementation

### Step 1: Write Tests First (TDD)
```
Using superpowers:test-driven-development skill.

Write failing tests FIRST:
- Unit tests for new functions
- Integration tests for API endpoints
- Edge cases
```

### Step 2: Implement Backend
```
Implement in backend/app/:
- Services: backend/app/services/
- API routes: backend/app/api/
- Models: backend/app/models/

Follow FastAPI async patterns.
```

### Step 3: Verify Tests Pass (GREEN)
```bash
cd backend && source ../venv/bin/activate
pytest tests/ -v --tb=short -x
```

### Gate 2: Implementation Review
**Verification:**
```bash
# Lint
ruff check backend/app/ --fix

# Tests exist
test -f backend/tests/test_*.py || echo "No tests created"

# No OpenAI
! grep -r "OPENAI" --include="*.py" backend/app/ || exit 1
```

**Checklist:**
- [ ] Tests written first (TDD)
- [ ] Implementation complete
- [ ] Linter passes
- [ ] Tests passing

**Ask:** "Phase 2 complete. Proceed to Phase 3 (Integration)? (yes/no)"

---

## Phase 3: Integration & Security

### Step 1: Wire Components
- Add API endpoints to router in `backend/app/main.py`
- Update `__init__.py` exports
- Register in appropriate modules

### Step 2: Security Scan
```bash
# No OpenAI references
! grep -r "OPENAI" --include="*.py" backend/app/ || {
    echo "ERROR: OpenAI reference found"; exit 1
}

# No hardcoded keys
! grep -r "sk-" --include="*.py" backend/app/ || {
    echo "ERROR: Hardcoded key found"; exit 1
}

# Verify imports work
cd backend && python -c "from app.main import app" || {
    echo "ERROR: Import failed"; exit 1
}
```

### Gate 3: Security Verification
**Checklist:**
- [ ] Components wired together
- [ ] Imports working
- [ ] No OpenAI references
- [ ] No hardcoded API keys

**Ask:** "Phase 3 complete. Proceed to Phase 4 (Testing)? (yes/no)"

---

## Phase 4: Testing

### Run Full Test Suite
```bash
cd backend && source ../venv/bin/activate

# All tests
pytest tests/ -v --tb=short

# With coverage (if configured)
pytest tests/ -v --cov=app --cov-report=term-missing
```

### Verify Specific Feature Tests
```bash
pytest tests/test_[feature].py -v
```

### Gate 4: All Tests Pass
**Checklist:**
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] No regressions

**Ask:** "Phase 4 complete. Proceed to Phase 5 (Code Review)? (yes/no)"

---

## Phase 5: Code Review (BLOCKING)

**THIS GATE CANNOT BE SKIPPED**

### Step 1: Dispatch Code Reviewer
```
Dispatching superpowers:code-reviewer agent...

Review focus:
- Code quality and patterns
- Security vulnerabilities
- Test coverage gaps
```

### Step 2: Final Verification
```bash
# Final security check
! grep -r "OPENAI" --include="*.py" backend/app/ || exit 1
! grep -r "sk-" --include="*.py" backend/app/ || exit 1

# Final test run
cd backend && pytest tests/ -v --tb=short

# Final lint
ruff check backend/app/
```

### Gate 5: Code Review (BLOCKING)
**Checklist:**
- [ ] Code review completed
- [ ] All issues addressed
- [ ] No OpenAI references
- [ ] No hardcoded keys
- [ ] Tests passing

**On PASS:** "Phase 5 complete. Proceed to Phase 6 (Commit)? (yes/no)"

**On FAIL:**
```
Phase 5 FAILED.

Issues found:
[list of issues]

Options:
1. Fix and re-review
2. Manual fix, then re-review

NOTE: Skip NOT available for Phase 5.
```

---

## Phase 6: Commit/PR

### Pre-requisites
- Phase 5 passed with zero errors
- All tests passing
- No security issues

### Verify Tests One More Time
```bash
cd backend && pytest tests/ -v --tb=short
```

### Commit
```bash
git add .
git commit -m "$(cat <<'EOF'
feat: [feature-description]

- [Key change 1]
- [Key change 2]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

git push origin main
```

---

## Gate Failure Handling

When any gate fails (except Phase 5):
```
Gate [N] FAILED

Failed checks:
- [ ] [failed check]

Options:
1. Fix and retry
2. Manual fix, then retry
3. Skip phase (NOT for Phase 5)
4. Abort pipeline

Which option?
```

---

## Phase Summary

```
Phase 0 (Planning) ──► Gate 0 (Plan Approved?)
        │
        ▼
Phase 1 (Database) ──► Gate 1 (Schema Approved?)
        │
        ▼
Phase 2 (Implementation) ──► Gate 2 (Tests Pass?)
        │
        ▼
Phase 3 (Integration) ──► Gate 3 (Security OK?)
        │
        ▼
Phase 4 (Testing) ──► Gate 4 (All Pass?)
        │
        ▼
Phase 5 (Review) ──► Gate 5 (100% Clean?) ◄── BLOCKING
        │
        ▼
Phase 6 (Commit) ──► DONE
```

---

## Critical Rules

- **NO OpenAI** - Cerebras, Claude, DeepSeek only
- **API keys in .env only** - Never hardcode
- **TDD** - Write tests first, then implementation
- **Close CRM is read-only** - `CLOSE_WRITE_DISABLED=True`
