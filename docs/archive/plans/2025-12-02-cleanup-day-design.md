# Cleanup Day Design: Parallel Sandbox Refactoring

**Date**: 2025-12-02
**Focus**: Enrichment Services + LangGraph Agents
**Approach**: Parallel agent execution with quality gates

---

## Goals

1. Fix 579 lint errors → 0
2. Archive stale services and agents
3. Improve test coverage for batch system
4. Ship only if all quality gates pass

---

## Baseline Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Lint errors | 579 | 0 |
| Test pass rate | TBD | 100% |
| Active services | 74 | ~50 |
| LangGraph agents | 16 | ~10 |

---

## Parallel Agent Architecture

```
LINT AGENT ──────┐
                 │
REFACTOR AGENT ──┼──→ COMPOSE & VALIDATE ──→ SHIP or ROLLBACK
                 │
TEST AGENT ──────┘
```

### Lint Agent
- `ruff check backend/app/ --fix` (468 auto-fixes)
- Manual fixes for remaining errors
- Target: 0 errors

### Refactor Agent

**Enrichment Services:**
| File | Action |
|------|--------|
| `apollo.py` | Keep |
| `apollo_rate_limited.py` | Keep |
| `apollo_enrichment_queue.py` | Archive |
| `hunter_service.py` | Keep |
| `hunter_email_service.py` | Merge → archive |
| `browserbase_session_pool.py` | Keep |
| `browserbase_team_scraper.py` | Keep |

**LangGraph Agents:**
| Agent | Action |
|-------|--------|
| `qualification_agent.py` | Keep (core) |
| `enrichment_agent.py` | Keep (core) |
| `marketing_agent.py` | Keep (core) |
| `bdr_agent.py` | Keep (core) |
| `sales_intel_agent.py` | Keep (new) |
| `conversation_agent.py` | Keep (voice) |
| `license_auditor_agent.py` | Archive |
| `social_research_agent.py` | Archive |
| `linkedin_post_writer.py` | Archive |
| `reasoner_agent.py` | Archive |

### Test Agent
- Fix Redis mock in `test_batch_processing.py`
- Add tests for `apollo_rate_limited.py`
- Improve `parallel_pipeline.py` coverage
- Target: 100% pass rate

---

## Quality Gates

| Gate | Criteria | Blocker |
|------|----------|---------|
| G1: Lint | `ruff check` → 0 errors | YES |
| G2: Tests | `pytest` → 100% pass | YES |
| G3: Imports | App boots without errors | YES |
| G4: Review | No HIGH priority issues | YES |

**Ship only if ALL gates pass.**

---

## Execution Order

1. Create git worktree for cleanup branch
2. Run LINT AGENT (parallel)
3. Run REFACTOR AGENT (parallel)
4. Run TEST AGENT (parallel)
5. Compose results
6. Run quality gates
7. Code review
8. Commit + push (if perfect)

---

## Rollback Plan

If any gate fails:
```bash
git checkout main
git worktree remove ../sales-agent-cleanup
git branch -D cleanup/2025-12-02
```
