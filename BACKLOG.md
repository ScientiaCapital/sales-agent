# BACKLOG.md - Project Task Board

**Project**: sales-agent
**Last Updated**: 2025-12-02
**Sprint**: Current

---

## Quick Stats

| Status | Count |
|--------|-------|
| 🔴 Blocked | 0 |
| 🟡 In Progress | 1 |
| 🟢 Ready | 2 |
| ✅ Done (this sprint) | 32 |

---

## 📋 Board View

### 🔴 Blocked
<!-- Tasks waiting on external dependencies or decisions -->

*None currently*

---

### 🟡 In Progress
<!-- Tasks actively being worked on -->

#### 1. [HIGH] Run Interactive Enrichment on 3,500 Companies
- **ID**: TASK-010
- **Assignee**: Team (Dec 2+)
- **Labels**: `enrichment`, `scraping`, `supabase`
- **Est. Time**: ~30 hours total (over several days)
- **Dependencies**: None

**Description**: Run interactive enrichment from Supabase, 5 companies at a time.

**Command**:
```bash
cd backend
source ../venv/bin/activate
python run_enrichment.py
```

**Progress**:
- [ ] Start enrichment run
- [ ] Monitor for failures (saved to FAILED_ENRICHMENT.csv)
- [ ] Continue in daily sessions (20-40 batches/day)
- [ ] Target: 3,500 companies with domains

**Acceptance Criteria**:
- [ ] All 3,500 companies with domains enriched
- [ ] Failed companies documented for troubleshooting
- [ ] dim_companies updated with last_enriched_at
- [ ] ATL contacts added to dim_contacts

---

### 🟢 Ready (Prioritized)
<!-- Tasks ready to start, ordered by priority -->

#### 1. [HIGH] Review & Import Close CRM Data
- **ID**: TASK-008
- **Assignee**: Tim
- **Labels**: `crm`, `manual-review`
- **Est. Time**: 1-2 hours
- **Dependencies**: TASK-007

**Description**: Review deep scrape output and import qualified leads to Close CRM.

**Acceptance Criteria**:
- [ ] Open `CLOSE_CRM_IMPORT_*.csv` in Excel
- [ ] Filter to leads with ATL Count > 0
- [ ] Verify data quality
- [ ] Import to Close CRM manually
- [ ] Update Supabase sync

---

#### 2. [MEDIUM] Run Hunter.io on ATL Leads
- **ID**: TASK-001
- **Assignee**: Unassigned
- **Labels**: `enrichment`, `data-quality`
- **Est. Time**: 2 hours
- **Cost**: ~$10 for 1000 domains
- **Dependencies**: TASK-007

**Description**: Enrich leads that have ATL names with Hunter.io to find email/direct phone.

**Acceptance Criteria**:
- [ ] Run `python enrich_gold_standard_batch.py --batch 2`
- [ ] Verify ATL leads enriched first
- [ ] Check cost
- [ ] Sync results to Supabase
- [ ] Re-score leads

---

#### 3. [MEDIUM] Connect Dashboard to Real Supabase Data
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

### ⏸️ Backlog (Future)
<!-- Tasks not yet prioritized for this sprint -->

| ID | Title | Priority | Labels |
|----|-------|----------|--------|
| TASK-003 | Increase HOT Lead Count (50+ target) | Medium | `data-quality` |
| TASK-004 | Voice AI calling integration | Medium | `feature`, `voice` |
| TASK-005 | CRM sync improvements | Low | `integration`, `crm` |
| TASK-006 | Email sequence automation | Medium | `feature`, `automation` |

---

### ✅ Done (This Sprint)
<!-- Completed tasks - move here when done -->

| ID | Title | Completed | By |
|----|-------|-----------|-----|
| **AI Command Center (Dec 2 Evening)** | | | |
| TASK-D34 | AI Outreach API (7 FastAPI endpoints) | 2025-12-02 | Claude |
| TASK-D35 | CommandCenter.tsx (two-panel lead enrichment) | 2025-12-02 | Claude |
| TASK-D36 | DraftReviewQueue.tsx (bulk review UI) | 2025-12-02 | Claude |
| TASK-D37 | AIInsightsPanel.tsx (personal hooks display) | 2025-12-02 | Claude |
| TASK-D38 | dim_ai_drafts Supabase migration | 2025-12-02 | Claude |
| **OEM Brand Expansion (Dec 2 PM)** | | | |
| TASK-D30 | Expanded OEM brands to 100+ (solar, battery, EV, VRF) | 2025-12-02 | Claude |
| TASK-D31 | Added maintenance plan extraction (BDR opener gold) | 2025-12-02 | Claude |
| TASK-D32 | Improved false positive filtering (service areas, contacts) | 2025-12-02 | Claude |
| TASK-D33 | Fixed varchar(255) overflow errors in contact sync | 2025-12-02 | Claude |
| **Code Cleanup (Dec 2 AM)** | | | |
| TASK-D26 | Archived 49 obsolete Python scripts | 2025-12-02 | Claude |
| TASK-D27 | Updated CLAUDE.md, PLANNING.md, TASK.md, BACKLOG.md | 2025-12-02 | Claude |
| TASK-D28 | Created run_enrichment.py (interactive batch runner) | 2025-12-02 | Claude |
| TASK-D29 | Enhanced scraper: service areas, HVAC brands, BTL contacts, owner quotes | 2025-12-02 | Claude |
| **Phase 2: Security & Database (Dec 1)** | | | |
| TASK-D14 | Migration 015: Enable RLS on 14 tables | 2025-12-01 | Agent 7 |
| TASK-D15 | Migration 016: Performance indexes | 2025-12-01 | Agent 7 |
| TASK-D16 | Migration 009: Consolidate duplicate policies | 2025-12-01 | Agent 7 |
| TASK-D17 | Fixed 40-50 of 113 Supabase issues | 2025-12-01 | Agent 7 |
| TASK-D18 | Created deployment checklists | 2025-12-01 | Agent 7 |
| TASK-D19 | PgAdmin email configuration fixed | 2025-12-01 | Agent 10 |
| **Phase 1: Infrastructure (Dec 1)** | | | |
| TASK-D08 | Supabase CLI installation | 2025-12-01 | Agent 1 |
| TASK-D09 | Docker infrastructure setup | 2025-12-01 | Agent 2 |
| TASK-D10 | Categorized all 113 Supabase issues | 2025-12-01 | Agent 4 |
| TASK-D11 | API key validation report | 2025-12-01 | Agent 3 |
| TASK-D12 | Code quality baseline (96.5/100) | 2025-12-01 | Agent 6 |
| TASK-D13 | Deep scrape code review | 2025-12-01 | Agent 5 |
| **Previous Work** | | | |
| TASK-D01 | Multi-source enrichment on 1,000 leads | 2025-12-01 | Claude |
| TASK-D02 | Deep scraper with ATL extraction | 2025-12-01 | Claude |
| TASK-D03 | Phone audit trail (NEW/VERIFIED) | 2025-12-01 | Claude |
| TASK-D04 | Close CRM export format | 2025-12-01 | Claude |
| TASK-D05 | run_deep_scrape.sh runner script | 2025-12-01 | Claude |
| **Phase 3: LinkedIn Enrichment (Dec 1 PM)** | | | |
| TASK-D20 | Browserbase session pool with stealth mode | 2025-12-01 | Claude |
| TASK-D21 | Parallel LinkedIn company scraper | 2025-12-01 | Claude |
| TASK-D22 | Parallel LinkedIn profile scraper | 2025-12-01 | Claude |
| TASK-D23 | Supabase sync for LinkedIn data | 2025-12-01 | Claude |
| TASK-D24 | run_linkedin_enrichment.py orchestrator | 2025-12-01 | Claude |
| TASK-D25 | Security audit - API key exposure fix | 2025-12-01 | Claude |
| TASK-000 | Gold Standard Lead Pipeline | 2025-11-29 | Claude |
| TASK-000 | Context Engineering Setup | 2025-11-30 | Claude |
| TASK-000 | Lead Scoring Algorithm | 2025-11-29 | Claude |

---

## 📊 Sprint Metrics

### Velocity
- **Last Sprint**: 5 tasks completed
- **This Sprint**: 32 tasks completed (Phase 1: 6, Phase 2: 6, Phase 3: 6, Security: 3, Dec 2 AM: 8, AI Command Center: 5)
- **Avg Task Time**: 1.5 hours

### Security Status (Dec 1)
| Metric | Before | After |
|--------|--------|-------|
| Supabase Issues | 113 | ~63-73 (40-50 fixed) |
| Tables Without RLS | 16 | 2 (14 secured) |
| Duplicate Policies | 8+ | 0 (all consolidated) |
| Missing Indexes | 7+ | 0 (all added) |
| Code Quality Score | Unknown | 96.5/100 (A+) |

### Data Quality (Dec 2)
| Metric | Count |
|--------|-------|
| Total Companies | 8,889 |
| With Domains | 3,643 |
| Needing Enrichment | ~3,500 |
| Already Enriched | ~75 |
| Active Scripts | 14 |
| Archived Scripts | 49 |

---

## 🔄 Workflow

### Pipeline Flow
```
CSV Import → ICP Scoring → Multi-source Enrichment → Deep Scrape → Close CRM Export
                                                            ↓
                                              Manual Import to Close CRM
```

### Task Lifecycle
```
Ready → In Progress → Review → Done
         ↓
       Blocked (if dependencies)
```

---

## 🚨 Blockers & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| ATL extraction rate (5-15% expected) | Medium | Many sites don't list owner names |
| Hunter.io rate limits | Medium | Space out batch runs |
| Close CRM write disabled | Low | Read-only is intentional |

---

## 📝 Notes

### Decisions Made
- 2025-12-01: **Supabase RLS security hardening** - 14 tables secured (ADR-006)
- 2025-12-01: Manual Close CRM import only (no auto-push)
- 2025-12-01: Browserbase for website scraping (ADR-004)
- 2025-11-29: Close CRM writes disabled for safety
- 2025-11-29: 1 company = 1 lead philosophy adopted

### Key Outputs (Dec 1)
| File | Purpose |
|------|---------|
| **Migrations** | |
| `015_enable_rls_security.py` | RLS policies for 14 tables |
| `016_add_star_schema_performance_indexes.py` | Performance indexes |
| `009_consolidate_duplicate_policies.sql` | Duplicate policy cleanup |
| **Documentation** | |
| `AGENT_7_RLS_SECURITY_FIXES_REPORT.md` | Complete security analysis |
| `DEPLOYMENT_CHECKLIST_RLS_MIGRATION.md` | Deployment guide |
| `SUPABASE_ISSUES_CATEGORIZED.md` | All 113 issues categorized |
| `CODE_QUALITY_BASELINE_REPORT.md` | Baseline: 96.5/100 |
| **Data Outputs** | |
| `DEEP_SCRAPE_*.csv` | Full scrape results |
| `CLOSE_CRM_IMPORT_*.csv` | Tim's manual import |
| `TOP_1000_PRIORITIZED_*.csv` | Daily caller list |

---

## 🔗 Related Files

- `.claude/CLAUDE.md` - Project overview and rules
- `PLANNING.md` - Architecture decisions
- `TASK.md` - Quick task reference
- `run_deep_scrape.sh` - Deep scraper runner

---

## Critical Rules Reminder

- **NO OpenAI** - Use Cerebras, Claude, DeepSeek only
- **API keys in .env only** - Never hardcode
- **Close CRM WRITE DISABLED** - Read-only for safety
- **Manual import only** - Review CSV before importing
- **Run `/validate` before marking tasks done**

---

*This file is the source of truth for project tasks. Update it as work progresses.*
