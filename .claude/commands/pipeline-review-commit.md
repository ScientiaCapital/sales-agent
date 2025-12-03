# Pipeline Review & Commit

Full pipeline: test → lint → review → commit → push.

**Usage**: `/pipeline-review-commit`

---

## Phase 0: Check Changes

```bash
git status
git diff --stat
```

---

## Phase 1: Test

```bash
cd backend && source ../venv/bin/activate

# Run tests
pytest tests/ -v --tb=short

# Lint
ruff check app/

# Type check (if configured)
mypy app/ --ignore-missing-imports
```

**GATE**: All must pass. Fix before proceeding.

---

## Phase 2: Review

Launch code-reviewer to check:
- Security vulnerabilities
- No hardcoded API keys
- Logic bugs
- Error handling

**GATE**: Zero HIGH issues to proceed.

---

## Phase 3: Commit & Push

```bash
git add .
git commit -m "feat: <description>

- Change 1
- Change 2

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin main
```

---

## Quality Gates

| Phase | Gate | On Failure |
|-------|------|------------|
| 1 | Tests pass | Fix tests |
| 2 | No HIGH issues | Fix issues |
| 3 | Push succeeds | Retry |
