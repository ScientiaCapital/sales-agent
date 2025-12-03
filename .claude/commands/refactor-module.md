# Refactor Module Workflow

Quick 4-phase refactor workflow for cleaning up technical debt.

**Usage**: `/refactor-module [module_path]`

---

## PHASE 1: PLAN & BASELINE

### 1.1 Brainstorm Refactor Plan
Use the brainstorming skill to identify:
- Code bloat and duplicates
- Dependency issues
- Anti-patterns to fix
- Test strategy

### 1.2 Create Baseline Snapshot
```bash
git add -A && git commit -m "baseline: before refactor of $ARGUMENTS"
```

---

## PHASE 2: REFACTOR + TEST (Parallel)

### 2a. Main Refactor Work
Analyze the module at `$ARGUMENTS`:
- Identify legacy patterns to modernize
- Remove dead code and duplicates
- Simplify complex logic
- Apply current project patterns

### 2b. Generate/Update Tests
Ensure test coverage:
- Unit tests for refactored functions
- Integration tests if boundaries changed
- Edge cases for new logic

### 2c. Performance Check (if applicable)
- Profile if performance-critical code
- Check for N+1 queries, unnecessary loops
- Verify no memory leaks introduced

---

## PHASE 3: VALIDATE

### 3.1 Run Tests
```bash
cd backend && source ../venv/bin/activate
pytest tests/ -v --tb=short
```

### 3.2 Check Diff
```bash
git diff --stat
git diff $ARGUMENTS
```

### 3.3 Lint Check
```bash
ruff check $ARGUMENTS
```

---

## PHASE 4: SHIP IF CLEAN

### 4.1 Code Review
Launch code-reviewer agent to verify:
- No regressions introduced
- Tests actually test behavior
- Code follows project patterns

### 4.2 Commit & Push
**IF CLEAN** (all tests pass, no lint errors):
```bash
git add -A
git commit -m "refactor: modernize $ARGUMENTS

- [list key changes]
- [improved X]
- [removed Y]"
git push origin main
```

**IF ISSUES FOUND**:
1. Fix the issues
2. Re-run tests
3. Re-review
4. Then commit

---

## Quality Gates

| Gate | Requirement |
|------|-------------|
| Tests | All pass |
| Lint | No errors |
| Review | No critical issues |
| Diff | Changes make sense |

**No exceptions. Fix before shipping.**
