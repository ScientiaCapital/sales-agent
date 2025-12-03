---
description: "Full pipeline: test → lint → review → commit → auto-push"
---

# Pipeline Review & Commit Workflow

Automated multi-phase pipeline with quality gates. **Auto-push enabled** - commits push automatically if all gates pass.

## PHASE 0: PLANNING
Analyze current changes and prepare for review.

```bash
git status
git diff --stat
```

- Identify files changed
- Categorize by type (backend/frontend/tests)

## PHASE 1: TESTING (Parallel)

Run all validation in parallel:

```bash
# Backend tests
pytest backend/tests/ -v --tb=short

# Type checking
cd backend && mypy app/

# Linting
ruff check backend/app/

# Frontend type check (if applicable)
cd frontend && npm run typecheck
```

**GATE**: All tests must pass. If ANY fail → STOP and fix before proceeding.

## PHASE 2: CODE REVIEW (Blocking)

Launch code-reviewer agent to audit changes:

1. Check for security vulnerabilities
2. Verify no hardcoded API keys
3. Review logic for bugs and race conditions
4. Ensure proper error handling

**GATE**:
- Zero HIGH priority issues → Proceed
- HIGH issues found → STOP + fix issues → Re-run Phase 2

## PHASE 3: COMMIT + AUTO-PUSH

If all gates pass:

```bash
# Stage all changes
git add .

# Commit with standard format
git commit -m "feat: <description>

<bullet points of changes>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Auto-push (no confirmation needed)
git push origin main
```

**FINAL GATE**: Commit + push successful → Done!

## Quality Gates Summary

| Phase | Gate | On Failure |
|-------|------|------------|
| 1 | All tests pass | STOP, fix tests |
| 2 | Zero HIGH issues | STOP, fix issues |
| 3 | Push succeeds | Retry or notify |

## Quick Reference

```bash
# Run this workflow
/pipeline-review-commit

# Skip to specific phase (manual)
pytest backend/tests/ -v          # Phase 1
ruff check backend/app/ --fix     # Phase 1
# Then run code review agent       # Phase 2
git add . && git commit && git push # Phase 3
```

## Agent Assignments

| Phase | Agent | Purpose |
|-------|-------|---------|
| 0 | Explore | Analyze changes |
| 1 | - | Bash commands |
| 2 | code-reviewer | Security + quality audit |
| 3 | - | Git commands |
