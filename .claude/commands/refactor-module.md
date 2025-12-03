# Refactor Module

4-phase workflow for cleaning up technical debt.

**Usage**: `/refactor-module [module_path]`

---

## Phase 1: Plan & Baseline

### Brainstorm
- Code bloat and duplicates
- Dependency issues
- Anti-patterns to fix
- Test strategy

### Baseline Snapshot
```bash
git add -A && git commit -m "baseline: before refactor"
```

---

## Phase 2: Refactor + Test

### Refactor Work
- Remove dead code
- Simplify complex logic
- Apply project patterns

### Update Tests
- Unit tests for refactored functions
- Integration tests if needed
- Edge cases

### Performance Check
- Check for N+1 queries
- Remove unnecessary loops
- Verify no memory leaks

---

## Phase 3: Validate

```bash
cd backend && source ../venv/bin/activate

# Tests
pytest tests/ -v --tb=short

# Diff
git diff --stat

# Lint
ruff check app/
```

---

## Phase 4: Ship

### Code Review
Launch code-reviewer agent to verify:
- No regressions
- Tests cover behavior
- Follows patterns

### Commit
```bash
git add -A
git commit -m "refactor: modernize [module]

- Key change 1
- Key change 2"
git push origin main
```

---

## Quality Gates

| Gate | Requirement |
|------|-------------|
| Tests | All pass |
| Lint | No errors |
| Review | No critical issues |

**Fix before shipping.**
