# BACKLOG.md - Project Task Board

**Project**: sales-agent
**Last Updated**: 2025-12-07 (Vite Migration Complete)
**Sprint**: Current
**NOTE**: Last updated Dec 7. For current status, see TASK.md (updated Dec 13). BACKLOG needs refresh with latest progress on website enrichment and VLM integration.

---

## Quick Stats

| Status | Count |
|--------|-------|
| 🔴 Blocked | 0 |
| 🟡 In Progress | 0 |
| 🟢 Ready | 10 |
| ✅ Done (this sprint) | 54 (Phase 1-4 + Vite Migration) |

---

## 📋 Board View

### 🔴 Blocked
<!-- Tasks waiting on external dependencies or decisions -->

*None currently*

---

### 🟡 In Progress
<!-- Tasks actively being worked on -->

#### 1. [HIGH] Phase 4: Dashboard Real Data Verification
- **ID**: TASK-027, TASK-028, TASK-029
- **Assignee**: Claude (Dec 6 Evening)
- **Labels**: `dashboard`, `verification`, `phase-4`
- **Est. Time**: 3 hours (2h with parallelization)
- **Dependencies**: Phase 3 ✅

**Description**: Ensure ALL dashboard cards display REAL API data, not mock/empty states.

**Execution Plan**:
```
PARALLEL: TASK-027 (Backend) + TASK-028 (Frontend)
SEQUENTIAL: TASK-029 (E2E verification)
GATE: Code review before merge
```

**Progress**:
- [ ] TASK-027: Backend connectivity verification (Agent: debugger)
- [ ] TASK-028: Frontend API proxy + error states (Agent: frontend-developer)
- [ ] TASK-029: E2E verification + cleanup (Agent: general-purpose)
- [ ] Code review gate

**Acceptance Criteria**:
- [ ] ALL 5 tabs show real data
- [ ] NO mock data anywhere
- [ ] NO empty states where data should exist
- [ ] Screenshot evidence of working dashboard

---

#### 2. [MEDIUM] Run Interactive Enrichment on 3,500 Companies
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

#### 1. [HIGH] Production Email Test (Monday) - Phase 3
- **ID**: TASK-015
- **Assignee**: Tim
- **Labels**: `testing`, `deliverability`
- **Dependencies**: TASK-014 (completed)

**Description**: Test email deliverability before enabling warming.

**Steps**:
1. Configure real SMTP credentials
2. Send test emails to known mailboxes
3. Check spam folder placement
4. Verify SPF/DKIM/DMARC records

**Acceptance Criteria**:
- [ ] Test emails delivered to inbox
- [ ] SPF/DKIM/DMARC passing
- [ ] Deliverability documented

---

#### 2. [HIGH] Email Warming Engine - Phase 3
- **ID**: TASK-016
- **Assignee**: Unassigned
- **Labels**: `feature`, `warming`
- **Dependencies**: TASK-015

**Description**: Gradual volume increase to build sender reputation. Day 1-7: 10/day → Day 29+: 50/day.

**Files to Create**:
- `backend/app/services/warming/engine.py`
- `backend/app/services/warming/tracker.py`
- `backend/app/api/warming.py`

**Acceptance Criteria**:
- [ ] Warming engine created
- [ ] Progressive limits working
- [ ] Engagement tracking
- [ ] Tests passing

---

## 🚀 Close CRM GTM Automation (Dec 6+)

> **MAJOR DISCOVERY**: 95% of Close CRM infrastructure is already built! Just needs enabling.

| Capability | Status | File |
|------------|--------|------|
| SMS Sending | ✅ ENABLED | `close_sms.py` (368 lines) |
| Calling | ✅ ENABLED | `close_calling.py` (404 lines) |
| Lead Management | ✅ ENABLED | `close.py` |
| API Endpoints | ✅ 14 endpoints ready | `close_outreach.py` |
| **Email via Close** | ✅ BUILT Dec 6 | `close_email.py` (544 lines) |
| **OutreachAgent** | ✅ BUILT Dec 6 | `outreach_agent.py` (310 lines) |
| **Outreach Tools** | ✅ BUILT Dec 6 | `outreach_tools.py` (443 lines) |

**Tim's Close CRM Configuration** (VERIFIED Dec 6):
- ✅ `Tim Kipper <tim@coperniq.io>` - Default for automated workflows
- ✅ BCC: `coperniq_inc-5rskqabn@leads.close.com`
- ✅ 4 phone numbers (Primary: +1 415-430-9565)
- ✅ Signature with photo configured

---

## 🎯 GTM Automation Implementation Plan (Dec 6+)

> **Implementation Strategy**: 3 Phases with parallelization + code review gates
> **Code Review**: `superpowers:code-reviewer` agent after each phase before advancing

### Phase 1: Reply Processing + Celery (PARALLEL)

| Task | Agent | Files | Est. |
|------|-------|-------|------|
| TASK-021a | `feature-dev:code-architect` | `reply_classifier.py`, `reply_router.py` | 2h |
| TASK-021b | `api-scaffolding:fastapi-pro` | `close_reply_webhook.py` | 1.5h |
| TASK-022 | `general-purpose` | `celery_app.py`, `tasks/close_sync.py` | 2h |

**→ CODE REVIEW GATE: `superpowers:code-reviewer` before Phase 2**

### Phase 2: Close Sequences (SEQUENTIAL)

| Task | Agent | Files | Est. |
|------|-------|-------|------|
| TASK-023 | `api-scaffolding:backend-architect` | `close_sequences.py`, update `outreach_tools.py` | 3h |

**→ CODE REVIEW GATE: `superpowers:code-reviewer` before Phase 3**

### Phase 3: BDR Cockpit (TIM'S CONTROL CENTER) ✅ COMPLETE

| Task | Agent | Files | Status |
|------|-------|-------|--------|
| TASK-024 | `application-performance:frontend-developer` | `CockpitDashboard.tsx`, `AgentStatusPanel.tsx` | ✅ Done |
| TASK-025 | `api-scaffolding:fastapi-pro` | Agent control endpoints, WebSocket | ✅ Done |
| TASK-026 | `application-performance:frontend-developer` | `AlertFeed.tsx`, `SequenceManager.tsx` | ✅ Done |

**→ CODE REVIEW: ✅ PASSED (Dec 6 Evening) - 4 fixes applied (FIX-CR1 through FIX-CR4)**

---

### Phase 4: Dashboard Real Data Verification (CURRENT)

> **Goal**: Ensure ALL dashboard cards display REAL API data, not mock/empty states
> **Status**: 🟡 IN PROGRESS
> **Strategy**: Backend verification first, then frontend connectivity, then E2E testing

**Exploration Findings (Dec 6 Evening)**:
- ✅ All frontend components already use SWR with real API endpoints
- ✅ All backend endpoints query real databases (Supabase, PostgreSQL, Redis)
- ⚠️ Issue: Backend server may not be running / Database connections need verification

| Task | Agent | Files | Est. | Parallelizable |
|------|-------|-------|------|----------------|
| TASK-027 | `error-debugging:debugger` | Backend connectivity verification | 1h | ✅ Yes (with 028) |
| TASK-028 | `application-performance:frontend-developer` | Frontend API proxy + error states | 1h | ✅ Yes (with 027) |
| TASK-029 | `general-purpose` | E2E verification + cleanup | 1h | ❌ Sequential |

**→ CODE REVIEW GATE: `superpowers:code-reviewer` before merge**

---

#### 3. ✅ [HIGH] Enable Close CRM Writes - DONE
- **ID**: TASK-017
- **Status**: ✅ **COMPLETE** (Dec 6, 2025)
- **Completed By**: Claude

**Changes Made**:
- [x] Set `CLOSE_WRITE_DISABLED=False` in `.env`
- [x] Close CRM writes now enabled for GTM automation

---

#### 4. ✅ [HIGH] Create CloseEmailClient - DONE
- **ID**: TASK-018
- **Status**: ✅ **COMPLETE** (Dec 6, 2025)
- **Completed By**: Claude

**Files Created**:
- `backend/app/services/crm/close_email.py` (544 lines)
- 7 email endpoints added to `close_outreach.py`

**Methods Implemented**:
- [x] `send_email()` - Send via tim@coperniq.io
- [x] `create_draft()` - Draft for review
- [x] `send_draft()` - Send existing draft
- [x] `schedule_email()` - Future delivery
- [x] `get_email_history()` - Lead email history
- [x] `cancel_scheduled()` - Cancel scheduled email
- [x] `delete_email()` - Delete draft/scheduled

---

#### ✅ [HIGH] Connect tim@coperniq in Close - ALREADY DONE
- **ID**: TASK-019
- **Status**: ✅ **COMPLETE** (verified from screenshots Dec 6)

**Verified Configuration**:
- ✅ `Tim Kipper <tim@coperniq.io>` is DEFAULT for automated workflows
- ✅ BCC: `coperniq_inc-5rskqabn@leads.close.com`
- ✅ Signature with photo configured
- ✅ 4 phone numbers ready (Primary: +1 415-430-9565)

---

#### 5. ✅ [HIGH] Create OutreachAgent - DONE
- **ID**: TASK-020
- **Status**: ✅ **COMPLETE** (Dec 6, 2025)
- **Completed By**: Claude

**Files Created**:
- `backend/app/services/langgraph/tools/outreach_tools.py` (443 lines)
- `backend/app/services/langgraph/agents/outreach_agent.py` (310 lines)

**Tools Implemented**:
- [x] `send_email_tool` - Send email via Close
- [x] `create_email_draft_tool` - Create draft for review
- [x] `send_sms_tool` - Send SMS via Close
- [x] `log_call_tool` - Log completed calls
- [x] `get_outreach_history_tool` - Get all outreach history

---

#### 6. ✅ [HIGH] Reply Processing (Webhook + Polling) - PHASE 1 COMPLETE
- **ID**: TASK-021
- **Status**: ✅ **COMPLETE** (Dec 6, 2025 Evening)
- **Completed By**: Claude

**Files Created**:
- `backend/app/services/outreach/reply_classifier.py` (207 lines) - Claude AI classification
- `backend/app/services/outreach/reply_router.py` (452 lines) - 8 intent handlers + Slack alerts
- `backend/app/api/webhooks/close_reply.py` (199 lines) - Webhook endpoint

**Reply Intents Implemented**:
| Intent | Handler | Action |
|--------|---------|--------|
| `interested` | `_handle_interested()` | 🔥 HOT Slack alert, stop sequence |
| `meeting_request` | `_handle_meeting_request()` | 📅 Calendar link, create opportunity |
| `question` | `_handle_question()` | ❓ Pause sequence, queue human response |
| `not_interested` | `_handle_not_interested()` | Stop sequence, schedule nurture 6mo |
| `unsubscribe` | `_handle_unsubscribe()` | 🚫 COMPLIANCE: Stop all, mark DNC |
| `out_of_office` | `_handle_out_of_office()` | Pause 7 days, auto-resume |
| `auto_reply` | `_handle_auto_reply()` | Continue sequence |
| `unknown` | `_handle_unknown()` | Queue for human review |

---

#### 7. ✅ [HIGH] Celery Beat Schedules for Close - PHASE 1 COMPLETE
- **ID**: TASK-022
- **Status**: ✅ **COMPLETE** (Dec 6, 2025 Evening)
- **Completed By**: Claude

**Files Created/Updated**:
- `backend/app/tasks/close_sync.py` (119 lines) - 3 Celery tasks
- `backend/app/celery_app.py` - Added sync schedules

**Tasks Implemented**:
| Task | Schedule | Purpose |
|------|----------|---------|
| `sync_close_activities` | Every 15 min | Sync email/SMS/call data |
| `poll_email_replies` | Every 5 min | Polling fallback for replies |
| `advance_sequences` | Hourly | Move leads through sequences |

---

#### 8. ✅ [HIGH] Close Sequences Integration - PHASE 2 COMPLETE
- **ID**: TASK-023
- **Status**: ✅ **COMPLETE** (Dec 6, 2025 Evening)
- **Completed By**: Claude

**Files Created**:
- `backend/app/services/crm/close_sequences.py` (545 lines) - CloseSequencesClient
- `backend/app/services/langgraph/tools/sequence_tools.py` (403 lines) - 8 LangGraph tools
- Updated `outreach_agent.py` with combined tools (13 total)

**Sequence Tools Implemented**:
| Tool | Purpose |
|------|---------|
| `list_sequences_tool` | List available sequences |
| `subscribe_to_sequence_tool` | Enroll contact by sequence ID |
| `enroll_in_sequence_by_name_tool` | Find by name and enroll |
| `pause_sequence_tool` | Pause subscription (OOO) |
| `resume_sequence_tool` | Resume paused subscription |
| `stop_sequence_tool` | Stop individual subscription |
| `stop_all_sequences_tool` | Stop ALL sequences (compliance) |
| `get_contact_sequence_status_tool` | Check progress |

**OutreachAgent Now Has**:
- 5 outreach tools (email, SMS, call, draft, history)
- 8 sequence tools (list, enroll, pause, resume, stop, status)
- 13 total tools for complete GTM automation

---

## 🎛️ BDR Cockpit - Tim's GTM Control Center (PHASE 3) - READY TO START

> **Status**: ✅ Phase 1 & 2 COMPLETE - Phase 3 READY
> **Code Review Gate**: Passed (Dec 6 Evening)
> **Location**: Existing dashboard (`dashboard-scientia-capital.vercel.app`)
> **Purpose**: Full control center for monitoring, alerts, triggers, and real-time intervention

### Cockpit Capabilities

| Category | Features |
|----------|----------|
| **Monitor** | Agent status (running/idle/error), outreach metrics, sequence progress, reply signals |
| **Alerts** | Slack notifications for hot leads, errors, approvals needed; in-dashboard alert feed |
| **Trigger** | Manually kick off any agent, approve/reject BDR drafts, enroll leads in sequences |
| **Control** | Pause/resume agents, override decisions, stop sequences, mark DNC, real-time intervention |

### Phase 3 Implementation Strategy

> **Parallelization Plan**: 2 agents can work simultaneously
> **Agent Matching**: Frontend + Backend in parallel
> **Code Review**: `superpowers:code-reviewer` after all tasks before merge

```
┌────────────────────────────────────────────────────────────────┐
│                    PHASE 3: PARALLEL EXECUTION                  │
├────────────────────────────────────────────────────────────────┤
│  Agent A (Frontend)              │  Agent B (Backend)          │
│  application-performance:        │  api-scaffolding:           │
│  frontend-developer              │  fastapi-pro                │
├──────────────────────────────────┼─────────────────────────────┤
│  TASK-024a: CockpitDashboard.tsx │  TASK-025a: agents.py       │
│  TASK-024b: AgentStatusPanel.tsx │  TASK-025b: websocket.py    │
│  TASK-024c: OutreachMetrics.tsx  │  TASK-025c: alerts.py       │
├──────────────────────────────────┴─────────────────────────────┤
│                    INTEGRATION PHASE                            │
├────────────────────────────────────────────────────────────────┤
│  TASK-026a: AlertFeed.tsx (needs websocket.py)                 │
│  TASK-026b: SequenceManager.tsx (needs agents.py)              │
│  TASK-026c: LeadInterventionPanel.tsx                          │
├────────────────────────────────────────────────────────────────┤
│  → FINAL CODE REVIEW: superpowers:code-reviewer                │
└────────────────────────────────────────────────────────────────┘
```

---

## 📊 Phase 4: Dashboard Real Data Verification Tasks

> **Execution Strategy**: Backend + Frontend in parallel, then E2E verification
> **Code Review Gate**: 100% review before declaring Phase 4 complete

---

#### 9. [HIGH] Backend Connectivity Verification - PHASE 4 (PARALLEL A)
- **ID**: TASK-027
- **Assignee**: Agent A
- **Labels**: `backend`, `debugging`, `phase-4`, `parallel-a`
- **Est. Time**: 1 hour
- **Dependencies**: Phase 3 ✅
- **Agent**: `error-debugging:debugger`

**Description**: Verify all backend APIs return real data from databases. Can run in PARALLEL with TASK-028.

**Verification Checklist**:
- [ ] Backend server starts successfully on port 8001
- [ ] PostgreSQL connection working (sequences, leads)
- [ ] Supabase connection working (dim_companies, dim_contacts, dim_alerts)
- [ ] Redis connection working (agent status, pub/sub)
- [ ] All `/api/v1/*` endpoints return 200 with real data

**API Endpoints to Verify**:
```
GET /api/v1/metrics/outreach     → fact_close_activities
GET /api/v1/agents/status        → Redis agent tracking
GET /api/v1/alerts               → dim_alerts
GET /api/v1/sequences            → PostgreSQL Sequence table
WS  /api/v1/ws/cockpit           → Redis pub/sub
```

**Acceptance Criteria**:
- [ ] All database connections verified
- [ ] All endpoints return real data (not empty/error)
- [ ] Connection errors documented and fixed

---

#### 10. [HIGH] Frontend API Proxy + Error States - PHASE 4 (PARALLEL B)
- **ID**: TASK-028
- **Assignee**: Agent B
- **Labels**: `frontend`, `debugging`, `phase-4`, `parallel-b`
- **Est. Time**: 1 hour
- **Dependencies**: Phase 3 ✅
- **Agent**: `application-performance:frontend-developer`

**Description**: Verify frontend correctly proxies to backend and handles errors gracefully. Can run in PARALLEL with TASK-027.

**Verification Checklist**:
- [ ] `next.config.ts` API proxy configured for `/api/v1/*` → `localhost:8001`
- [ ] `.env.local` has correct `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL`
- [ ] All SWR hooks have proper error boundaries
- [ ] Loading states display correctly while fetching
- [ ] Error states display user-friendly messages

**Components to Verify**:
| Component | Endpoint | Expected Data |
|-----------|----------|---------------|
| ExecutiveSummary | `/api/metrics` | Lead counts, conversion rates |
| BDRWorkQueue | `/api/workqueue` | Prioritized leads |
| ICPQueue | `/api/icp-queue` | ICP-scored leads |
| OutreachMetrics | `/api/outreach` | Email/SMS/call stats |
| AlertFeed | `/api/v1/alerts` | Real-time alerts |
| SequenceManager | `/api/v1/sequences` | Active sequences |
| AgentStatusPanel | `/api/v1/agents/status` | Agent health |

**Acceptance Criteria**:
- [ ] API proxy working (no CORS errors)
- [ ] All components show loading → data (not error)
- [ ] Error boundaries prevent blank screens

---

#### 11. [HIGH] E2E Verification + Cleanup - PHASE 4 (SEQUENTIAL)
- **ID**: TASK-029
- **Assignee**: After TASK-027 + TASK-028
- **Labels**: `testing`, `verification`, `phase-4`, `sequential`
- **Est. Time**: 1 hour
- **Dependencies**: TASK-027 ✅, TASK-028 ✅
- **Agent**: `general-purpose`

**Description**: End-to-end verification that all dashboard pages display real data. Sequential after parallel tasks complete.

**E2E Test Checklist**:
- [ ] Start backend: `cd backend && python start_server.py`
- [ ] Start frontend: `cd dashboard && npm run dev`
- [ ] Open http://localhost:3000 (or 3001 if port in use)
- [ ] Navigate through ALL tabs and verify real data displays

**Tab-by-Tab Verification**:
| Tab | Cards to Verify | Real Data Source |
|-----|-----------------|------------------|
| Dashboard | ExecutiveSummary, PipelineFunnel, RecentActivity | Supabase |
| Leads | BDRWorkQueue, ICPQueue, NeedsAttention | Supabase |
| Outreach | OutreachMetrics, LeadLifecycle | fact_close_activities |
| Command Center | CommandCenter, DraftReviewQueue | dim_ai_drafts |
| Cockpit | AgentStatus, AlertFeed, SequenceManager | PostgreSQL + Redis |

**Cleanup Tasks**:
- [ ] Remove any remaining mock data fallbacks
- [ ] Update error messages to be user-friendly
- [ ] Ensure consistent styling across all cards

**Acceptance Criteria**:
- [ ] ALL 5 tabs show real data
- [ ] NO mock data anywhere
- [ ] NO empty states where data should exist
- [ ] Screenshot evidence of working dashboard

---

### Phase 4 Execution Plan

```
STEP 1: Launch TASK-027 + TASK-028 in PARALLEL
        ├─ Agent A: error-debugging:debugger (Backend)
        └─ Agent B: frontend-developer (Frontend)

STEP 2: TASK-029 (Sequential - needs both complete)
        └─ Agent: general-purpose (E2E verification)

STEP 3: CODE REVIEW GATE
        └─ superpowers:code-reviewer (100% review)

STEP 4: UPDATE BACKLOG.md
        └─ Move Phase 4 tasks to Done
```

**Estimated Total Time**: 3 hours (but ~2 hours wall-clock with parallelization)

---

## 🎛️ BDR Cockpit - Reference (PHASE 3 COMPLETE)

#### ✅ [HIGH] Cockpit Dashboard + Agent Status - PHASE 3 (PARALLEL A)
- **ID**: TASK-024
- **Status**: ✅ **COMPLETE** (Dec 6, 2025 Evening)
- **Completed By**: Claude
- **Agent**: `application-performance:frontend-developer`

**Description**: Main BDR Cockpit view with agent status monitoring. Ran in PARALLEL with TASK-025.

**Files to Create**:
```
frontend/src/components/Cockpit/
├── CockpitDashboard.tsx      # Main control center view (TASK-024a)
├── AgentStatusPanel.tsx      # Live agent status + health (TASK-024b)
├── OutreachMetrics.tsx       # Emails sent, replies, conversion (TASK-024c)
└── AgentControls.tsx         # Start/stop/pause agents (TASK-024d)
```

**Subtasks** (can be parallelized within agent):
- [ ] TASK-024a: CockpitDashboard.tsx - Main layout with 4 panels
- [ ] TASK-024b: AgentStatusPanel.tsx - 11 agents with status indicators
- [ ] TASK-024c: OutreachMetrics.tsx - Email/SMS/call counters
- [ ] TASK-024d: AgentControls.tsx - Start/stop/pause buttons

**Acceptance Criteria**:
- [ ] CockpitDashboard layout with 4 panels
- [ ] AgentStatusPanel shows all 11 agents with status
- [ ] OutreachMetrics shows email/SMS/call counts
- [ ] AgentControls can start/stop agents
- [ ] Responsive design for Tim's workflow

---

#### 10. [HIGH] Agent Control API + WebSocket - PHASE 3 (PARALLEL B)
- **ID**: TASK-025
- **Assignee**: Agent B
- **Labels**: `backend`, `api`, `websocket`, `phase-3`, `parallel-b`
- **Est. Time**: 2 hours
- **Dependencies**: TASK-023 ✅ (Phase 2 complete)
- **Agent**: `api-scaffolding:fastapi-pro`

**Description**: Backend endpoints for agent control and real-time updates. Can run in PARALLEL with TASK-024.

**Files to Create**:
```
backend/app/api/
├── agents.py                 # Agent control endpoints (TASK-025a)
├── websocket.py              # WebSocket for live updates (TASK-025b)
└── alerts.py                 # Alert CRUD endpoints (TASK-025c)
```

**Subtasks** (can be parallelized within agent):
- [ ] TASK-025a: agents.py - Start/stop/status endpoints
- [ ] TASK-025b: websocket.py - Real-time cockpit connection
- [ ] TASK-025c: alerts.py - Alert history and acknowledgment

**New Endpoints**:
```
# Agent Control (agents.py)
POST   /api/v1/agents/{name}/start      # Trigger agent
POST   /api/v1/agents/{name}/stop       # Stop agent
GET    /api/v1/agents/status            # All agent statuses

# Real-time (websocket.py)
WS     /api/v1/ws/cockpit               # WebSocket for live updates

# Alerts (alerts.py)
GET    /api/v1/alerts                   # Alert history
POST   /api/v1/alerts/{id}/acknowledge  # Mark alert handled

# Intervention (agents.py)
POST   /api/v1/leads/{id}/override      # Override lead handling
POST   /api/v1/sequences/{id}/pause     # Pause sequence for lead
```

**Acceptance Criteria**:
- [ ] Agent start/stop endpoints working
- [ ] WebSocket broadcasting agent status changes
- [ ] Alert CRUD endpoints
- [ ] Lead override endpoint
- [ ] Sequence pause endpoint

---

#### 11. [HIGH] Alert Feed + Sequence Manager UI - PHASE 3 (INTEGRATION)
- **ID**: TASK-026
- **Assignee**: After TASK-024 + TASK-025
- **Labels**: `frontend`, `cockpit`, `phase-3`, `integration`
- **Est. Time**: 2 hours
- **Dependencies**: TASK-024 ✅, TASK-025 ✅
- **Agent**: `application-performance:frontend-developer`

**Description**: Real-time alert feed and sequence management UI. Requires backend endpoints from TASK-025.

**Files to Create**:
```
frontend/src/components/Cockpit/
├── AlertFeed.tsx             # Real-time alert stream (TASK-026a)
├── SequenceManager.tsx       # View/manage active sequences (TASK-026b)
└── LeadInterventionPanel.tsx # Override lead handling (TASK-026c)
```

**Subtasks**:
- [ ] TASK-026a: AlertFeed.tsx - WebSocket-connected alert stream
- [ ] TASK-026b: SequenceManager.tsx - Sequence list with pause/resume
- [ ] TASK-026c: LeadInterventionPanel.tsx - Manual lead overrides

**Acceptance Criteria**:
- [ ] AlertFeed shows real-time alerts via WebSocket
- [ ] Alerts can be acknowledged/dismissed
- [ ] SequenceManager shows all active sequences
- [ ] Can pause/resume sequences from UI
- [ ] LeadInterventionPanel allows manual overrides

---

### Phase 3 Execution Plan

**Tomorrow Start Here**:
1. Launch 2 agents in parallel:
   - Agent A: `application-performance:frontend-developer` → TASK-024
   - Agent B: `api-scaffolding:fastapi-pro` → TASK-025
2. After both complete → TASK-026 (integration)
3. Final code review: `superpowers:code-reviewer`

**Estimated Total Time**: 7 hours (but only ~4 hours wall-clock with parallelization)

---

#### 12. [HIGH] Review & Import Close CRM Data
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
| **Vite + React Migration (Dec 7)** | | | |
| TASK-030 | Vite Setup + Config (path aliases, proxy, theme) | 2025-12-07 | Claude |
| TASK-031 | Component Migration (12 dashboard + 6 UI + 3 AI) | 2025-12-07 | Claude |
| TASK-032 | Vercel Deployment Configuration | 2025-12-07 | Claude |
| TASK-033 | Delete Next.js Dashboard, Rename dashboard-new → dashboard | 2025-12-07 | Claude |
| **Close CRM GTM Automation - Phases 1 & 2 (Dec 6 Evening)** | | | |
| TASK-021 | Reply Processing (classifier + router + webhook) | 2025-12-06 | Claude |
| TASK-022 | Celery Beat Schedules for Close sync | 2025-12-06 | Claude |
| TASK-023 | Close Sequences Integration (8 tools + OutreachAgent) | 2025-12-06 | Claude |
| **Close CRM GTM Automation - Foundation (Dec 6)** | | | |
| TASK-017 | Enable Close CRM Writes (`CLOSE_WRITE_DISABLED=False`) | 2025-12-06 | Claude |
| TASK-018 | Create CloseEmailClient (`close_email.py` - 544 lines) | 2025-12-06 | Claude |
| TASK-020 | Create OutreachAgent + Tools (753 lines total) | 2025-12-06 | Claude |
| **Cold-Reach Integration (Dec 6)** | | | |
| TASK-011 | User Authentication (Supabase) - 11 endpoints, JWT validation | 2025-12-06 | Claude |
| TASK-012 | Close CRM SMS/Voice Integration - 7 endpoints, 2,269 lines | 2025-12-06 | Claude |
| TASK-013 | Merge cold-reach Models (5 models + Alembic migration) | 2025-12-06 | Claude |
| TASK-014 | Merge Sequence Engine (engine.py + sender.py) | 2025-12-06 | Claude |
| TASK-014B | Auth Protection for 45 endpoints | 2025-12-06 | Claude |
| FIX-M1 | Due email delay logic fix in engine.py | 2025-12-06 | Claude |
| FIX-M2 | Password encryption (Fernet AES-128) | 2025-12-06 | Claude |
| FIX-M4 | Rate limiting per mailbox (daily limits) | 2025-12-06 | Claude |
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

## 🔒 Security Audit Fixes (Dec 6, 2025)

> **Audit Status**: ✅ Completed | **Grade**: B+ | **Critical Issues**: 2 (FIXED)

### Audit Summary

| Category | Status |
|----------|--------|
| API Keys in Code | ✅ PASS |
| Git History | ✅ PASS |
| .gitignore | ✅ PASS |
| Auth/JWT | ✅ PASS |
| CORS | ✅ PASS |
| Rate Limiting | ✅ PASS |
| Encryption | ✅ PASS |
| SQL Injection | ✅ PASS |
| Supabase RLS | ✅ FIXED |
| Security Headers | ✅ FIXED |
| XSS | ✅ FIXED |

### ✅ Completed (Dec 6 Late Night)

| Task | Status | Files Modified |
|------|--------|----------------|
| SEC-001: Fix XSS in CallTranscriptViewer | ✅ DONE | `frontend/src/components/CallTranscriptViewer.tsx` |
| SEC-002: Add Security Headers Middleware | ✅ DONE | `backend/app/main.py` |
| SEC-003: Enable RLS on Master Tables | ✅ DONE | `supabase/migrations/020_enable_rls_master_tables.sql` |
| SEC-004: Replace print() with logger | ✅ DONE | `optimizer_client.py`, `system_templates.py` |
| SEC-005: Add Production CORS Origins | ✅ DONE | `backend/app/core/config.py` |

### Security Headers Now Enabled

- `X-Frame-Options: DENY` (clickjacking protection)
- `X-Content-Type-Options: nosniff` (MIME sniffing protection)
- `X-XSS-Protection: 1; mode=block` (legacy XSS filter)
- `Strict-Transport-Security` (HTTPS enforcement in production)
- `Content-Security-Policy` (resource loading restrictions)

### RLS Enabled Tables

| Table | Policy |
|-------|--------|
| `dim_companies` | service_role only |
| `dim_contacts` | service_role only |
| `scraper_batches` | service_role only |
| `scraper_imports` | service_role only |

### Production CORS Origins

- `https://sales-agent-seven-eta.vercel.app`
- `https://sales-agent-b3096zdcs-scientia-capital.vercel.app`

---

## Critical Rules Reminder

- **NO OpenAI** - Use Cerebras, Claude, DeepSeek only
- **API keys in .env only** - Never hardcode
- **Close CRM WRITES ENABLED** - ✅ Dec 6: `CLOSE_WRITE_DISABLED=False` for GTM automation
- **Manual import only** - Review CSV before importing
- **Run `/validate` before marking tasks done**

---

*This file is the source of truth for project tasks. Update it as work progresses.*
