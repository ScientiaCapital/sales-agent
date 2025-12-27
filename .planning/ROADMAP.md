# Roadmap: Close CRM Enhancements

## Overview

Transform the existing Close CRM integration from basic lead/contact management into a full-featured sales platform with pipeline visibility, activity sync, analytics, and automated workflows. Each phase delivers independently useful functionality while building toward the complete vision.

## Phases

- [x] **Phase 1: Pipeline Models** - Database models + Close API for opportunities/pipelines
- [x] **Phase 2: Activity Sync** - Bi-directional activity logging (calls, emails, meetings)
- [ ] **Phase 3: Analytics Dashboard** - Conversion funnel, pipeline health, trend analysis
- [ ] **Phase 4: Workflow Automation** - Stage change triggers, alerts, automated actions

## Phase Details

### Phase 1: Pipeline Models
**Goal**: Add Opportunity and Pipeline SQLAlchemy models, extend CloseProvider with pipeline API methods
**Depends on**: Nothing (first phase)
**Plans**: 3 plans

Plans:
- [x] 01-01: Database Models + Alembic Migration
- [x] 01-02: CloseProvider Methods (get_pipelines, get/create/update_opportunity)
- [x] 01-03: FastAPI Endpoints (/close/opportunities, /close/pipelines)

### Phase 2: Activity Sync
**Goal**: Bi-directional sync for calls, emails, and meetings between local DB and Close
**Depends on**: Phase 1
**Plans**: 3 plans

Plans:
- [x] 02-01: Meeting Activities (create_meeting, reply router integration, meeting sync)
- [x] 02-02: Task Activities (CloseTaskClient, auto-task creation, task sync)
- [x] 02-03: Activity Enhancements (call recordings, status tracking, opportunity attribution)

### Phase 3: Analytics Dashboard
**Goal**: Real-time pipeline visibility and conversion metrics
**Depends on**: Phase 2
**Plans**: 3 plans

Plans:
- [x] 03-01: Funnel Metrics (funnel-metrics, conversion-rates endpoints)
- [x] 03-02: Pipeline Health (pipeline-health, revenue-forecast endpoints)
- [ ] 03-03: Trend Analysis (activity-trends, period-comparison endpoints)

### Phase 4: Workflow Automation
**Goal**: Automated triggers for stage changes, alerts, and follow-up actions
**Depends on**: Phase 3
**Plans**: TBD after detailed planning

Key work:
- Workflow rule engine
- Stage change webhooks/polling
- Alert system (Slack, email)
- Automated task creation

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Models | 3/3 | Complete | 2025-12-26 |
| 2. Activity Sync | 3/3 | Complete | 2025-12-26 |
| 3. Analytics Dashboard | 2/3 | In progress | - |
| 4. Workflow Automation | 0/TBD | Not started | - |
