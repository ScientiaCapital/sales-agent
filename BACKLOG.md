# BACKLOG.md - Project Task Board

**Project**: sales-agent
**Last Updated**: 2025-11-30
**Sprint**: Current

---

## Quick Stats

| Status | Count |
|--------|-------|
| 🔴 Blocked | 0 |
| 🟡 In Progress | 0 |
| 🟢 Ready | 3 |
| ✅ Done (this sprint) | 5 |

---

## 📋 Board View

### 🔴 Blocked
<!-- Tasks waiting on external dependencies or decisions -->

*None currently*

---

### 🟡 In Progress
<!-- Tasks actively being worked on -->

*None currently*

---

### 🟢 Ready (Prioritized)
<!-- Tasks ready to start, ordered by priority -->

#### 1. [HIGH] Run Hunter.io Batch 2 Enrichment
- **ID**: TASK-001
- **Assignee**: Unassigned
- **Labels**: `enrichment`, `data-quality`
- **Est. Time**: 2 hours
- **Dependencies**: None

**Description**: Enrich leads 501-1000 with Hunter.io to find more direct phone numbers.

**Acceptance Criteria**:
- [ ] Run `python enrich_gold_standard_batch.py --batch 2`
- [ ] Verify 500 new leads enriched
- [ ] Check cost (~$5 for 500 domains)
- [ ] Sync results to Supabase
- [ ] Update lead scores

---

#### 2. [MEDIUM] Connect Dashboard to Real Supabase Data
- **ID**: TASK-002
- **Assignee**: Unassigned
- **Labels**: `frontend`, `integration`
- **Est. Time**: 4 hours
- **Dependencies**: None

**Description**: Replace mock data in dashboard with live Supabase queries.

**Acceptance Criteria**:
- [ ] Update BDR Work Queue to query `mv_bdr_work_queue`
- [ ] Connect Lead Pipeline to `dim_companies`
- [ ] Add real-time refresh
- [ ] Test with production data

---

#### 3. [LOW] Increase HOT Lead Count
- **ID**: TASK-003
- **Assignee**: Unassigned
- **Labels**: `data-quality`, `strategy`
- **Est. Time**: Ongoing
- **Dependencies**: TASK-001

**Description**: Currently only 2 HOT leads (unique direct phone + email). Need more enrichment batches.

**Acceptance Criteria**:
- [ ] Run multiple Hunter.io batches
- [ ] Achieve 50+ HOT leads
- [ ] Document discovery patterns

---

### ⏸️ Backlog (Future)
<!-- Tasks not yet prioritized for this sprint -->

| ID | Title | Priority | Labels |
|----|-------|----------|--------|
| TASK-004 | Add voice AI calling integration | Medium | `feature`, `voice` |
| TASK-005 | CRM sync improvements | Low | `integration`, `crm` |
| TASK-006 | Email sequence automation | Medium | `feature`, `automation` |

---

### ✅ Done (This Sprint)
<!-- Completed tasks - move here when done -->

| ID | Title | Completed | By |
|----|-------|-----------|-----|
| TASK-000 | Gold Standard Lead Pipeline | 2025-11-29 | Claude |
| TASK-000 | Context Engineering Setup | 2025-11-30 | Claude |
| TASK-000 | Lead Scoring Algorithm | 2025-11-29 | Claude |
| TASK-000 | Supabase Star Schema | 2025-11-29 | Claude |
| TASK-000 | ICP Tier System | 2025-11-29 | Claude |

---

## 📊 Sprint Metrics

### Velocity
- **Last Sprint**: 5 tasks completed
- **This Sprint Target**: 3 tasks
- **Avg Task Time**: 3 hours

### Quality
- **Tests Passing**: ✅
- **Type Errors**: 0
- **Lint Issues**: 0

---

## 🔄 Workflow

### Task Lifecycle
```
Ready → In Progress → Review → Done
         ↓
       Blocked (if dependencies)
```

### How to Use This File

**Starting a task**:
1. Move task from "Ready" to "In Progress"
2. Add your name as Assignee
3. Update the date

**Completing a task**:
1. Check all acceptance criteria boxes
2. Move to "Done" section
3. Add completion date

**Adding a new task**:
1. Add to "Backlog" table first
2. When prioritized, create full entry in "Ready"
3. Include: ID, description, acceptance criteria

---

## 🚨 Blockers & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hunter.io rate limits | Medium | Space out batch runs |
| Close CRM write disabled | Low | Read-only is intentional |

---

## 📝 Notes

### Decisions Made
- 2025-11-29: Close CRM writes disabled for safety
- 2025-11-29: 1 company = 1 lead philosophy adopted
- 2025-11-30: Context engineering deployed

### Questions to Resolve
- When to re-enable Close CRM writes?
- What's the HOT lead target for Tim's list?

---

## 🔗 Related Files

- `CLAUDE.md` - Project overview and rules
- `PLANNING.md` - Architecture decisions
- `TASK.md` - Quick task reference
- `PRPs/` - Implementation plans

---

## Critical Rules Reminder

- **NO OpenAI** - Use Cerebras, Claude, DeepSeek only
- **API keys in .env only** - Never hardcode
- **Close CRM WRITE DISABLED** - Read-only for safety
- **Run `/validate` before marking tasks done**
- **Update this file as work progresses**

---

*This file is the source of truth for project tasks. Update it as work progresses.*
