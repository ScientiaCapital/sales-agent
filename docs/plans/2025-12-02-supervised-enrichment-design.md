# Supervised Enrichment Pipeline Design

**Date**: 2025-12-02
**Status**: Approved
**Author**: Tim + Claude

---

## Overview

A supervised batch enrichment system that processes companies through 4 sequential stages with manual checkpoints between batches. Designed for Claude Code collaboration with interactive terminal control.

---

## Requirements

| Requirement | Decision |
|-------------|----------|
| Goal | Supervised Batch + Claude Code Collaboration |
| Stage Order | Apollo Free → LinkedIn → Hunter.io → Apollo Paid (sequential per company) |
| Company Parallelism | 2 companies at a time |
| Flow Control | Manual approval (continue/stop/retry) |
| Data Storage | Redis (real-time state) + Supabase (persistence) |
| Cost Control | Per-batch budget limits |

---

## Architecture

### Pipeline Flow

```
                    ┌──────────────────────┐
                    │   1. SELECT BATCH    │
                    │   Query Supabase for │
                    │   2 unenriched leads │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  2. PARALLEL STAGE   │
                    │  asyncio.gather(     │
                    │    enrich(company1), │
                    │    enrich(company2)  │
                    │  )                   │
                    └──────────┬───────────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │           PER-COMPANY SEQUENTIAL STAGES             │
    │                                                      │
    │   Company 1              Company 2                   │
    │   ┌───────────┐          ┌───────────┐              │
    │   │Apollo Free│          │Apollo Free│  (parallel)  │
    │   └─────┬─────┘          └─────┬─────┘              │
    │         ▼                      ▼                     │
    │   ┌───────────┐          ┌───────────┐              │
    │   │ LinkedIn  │          │ LinkedIn  │  (parallel)  │
    │   └─────┬─────┘          └─────┬─────┘              │
    │         ▼                      ▼                     │
    │   ┌───────────┐          ┌───────────┐              │
    │   │ Hunter.io │          │ Hunter.io │  (parallel)  │
    │   └─────┬─────┘          └─────┬─────┘              │
    │         ▼                      ▼                     │
    │   ┌───────────┐          ┌───────────┐              │
    │   │Apollo Paid│          │Apollo Paid│  (parallel)  │
    │   └─────┬─────┘          └─────┬─────┘              │
    └─────────┼──────────────────────┼────────────────────┘
              │                      │
              └──────────┬───────────┘
                         │
              ┌──────────▼───────────┐
              │  3. SAVE TO REDIS    │
              │  + SUPABASE          │
              └──────────┬───────────┘
                         │
              ┌──────────▼───────────┐
              │  4. CHECKPOINT       │
              │  [c]ontinue          │
              │  [s]top              │
              │  [r]etry failed      │
              └──────────────────────┘
```

### Technology Choice

**Pure Asyncio + Interactive Terminal**

- Single process, no Celery dependency
- `asyncio.gather()` for 2-company parallelism
- Simple to debug and monitor
- Progress saved on every checkpoint

---

## Data Model

### Supabase (Source of Truth)

`dim_companies` table columns for enrichment tracking:

| Column | Type | Purpose |
|--------|------|---------|
| `enrichment_status` | text | pending/in_progress/completed/failed |
| `apollo_enriched_at` | timestamp | When Apollo Free completed |
| `linkedin_enriched_at` | timestamp | When LinkedIn scrape completed |
| `hunter_enriched_at` | timestamp | When Hunter.io completed |
| `apollo_paid_at` | timestamp | When Apollo Paid completed |
| `enrichment_cost_usd` | decimal | Total cost for this company |
| `enrichment_error` | text | Last error message if failed |

### Redis (Real-time State)

**Per-company status:**
```json
enrichment:{company_id}:status
{
  "stage": "linkedin",
  "apollo_free": "done",
  "linkedin": "running",
  "hunter": "pending",
  "apollo_paid": "pending",
  "cost_usd": 0.02,
  "started_at": "2025-12-02T10:30:00Z"
}
```

**Batch budget tracking:**
```json
enrichment:batch:{batch_id}:budget
{
  "limit_usd": 5.00,
  "spent_usd": 1.23,
  "companies_processed": 4,
  "companies_remaining": 96,
  "stop_reason": null
}
```

---

## Cost Controls

| Stage | Typical Cost | Rate Limit |
|-------|--------------|------------|
| Apollo Free | $0.00 | 100/day |
| LinkedIn | $0.00 | Browserbase sessions |
| Hunter.io | $0.01/lookup | 500/month |
| Apollo Paid | $0.05/credit | Budget-dependent |

**Budget enforcement:**
- Check `spent_usd < limit_usd` before each company
- If budget exceeded, pause and prompt user
- Allow user to increase budget or stop

---

## Terminal Interface

```
$ python run_supervised_enrichment.py --batch-size 2 --budget 5.00

╔══════════════════════════════════════════════════════════════════╗
║  SUPERVISED ENRICHMENT PIPELINE v2.0                             ║
║  Budget: $5.00 | Parallelism: 2 companies | Stages: 4            ║
╚══════════════════════════════════════════════════════════════════╝

📊 Batch 1 of 50 (100 companies queued)
┌────────────────────────────────────────────────────────────────┐
│ Company                    │ Apollo │ LinkedIn │ Hunter │ Paid │
├────────────────────────────┼────────┼──────────┼────────┼──────┤
│ Acme HVAC Solutions        │   ✓    │    ✓     │   ◐    │  ○   │
│ Pacific Solar Installers   │   ✓    │    ✓     │   ◐    │  ○   │
└────────────────────────────────────────────────────────────────┘

💰 Cost: $0.02 / $5.00 budget (0.4%)
⏱️  Elapsed: 12.3s | Est. remaining: 10m 15s
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `c` | Continue to next batch of 2 |
| `s` | Stop gracefully, save all progress |
| `r` | Retry any failed companies from this batch |
| `v` | View detailed results |
| `q` | Quit (progress saved) |

---

## Slash Commands

### /enrich-supervised

Start the supervised enrichment pipeline with Claude guidance.

```
Usage: /enrich-supervised [--budget 5.00] [--batch-size 2]
```

Claude will:
- Query Supabase for unenriched companies
- Launch the terminal-based pipeline
- Interpret results and suggest next actions
- Help debug any failures

### /enrich-status

Check current enrichment progress across all companies.

Claude will:
- Query Redis for in-progress state
- Query Supabase for overall stats
- Show: completed, in-progress, failed, remaining

### /enrich-single <company_id or name>

Quick single-company enrichment with all 4 stages.

Claude will:
- Find company in Supabase
- Run Apollo Free → LinkedIn → Hunter → Apollo Paid
- Show results inline
- Update Supabase

### /enrich-retry-failed

Retry all companies that failed in previous batches.

Claude will:
- Query FAILED_ENRICHMENT.csv or Redis failures
- Re-attempt with exponential backoff
- Report success/failure

---

## File Structure

```
backend/
├── run_supervised_enrichment.py    # NEW - main entry point
├── app/
│   └── services/
│       └── supervised_pipeline/    # NEW - pipeline module
│           ├── __init__.py
│           ├── orchestrator.py     # Asyncio orchestration
│           ├── stages/
│           │   ├── __init__.py
│           │   ├── apollo_free.py
│           │   ├── linkedin.py
│           │   ├── hunter.py
│           │   └── apollo_paid.py
│           ├── state_manager.py    # Redis + Supabase sync
│           └── budget_tracker.py   # Cost controls
├── enrich_apollo.py                # EXISTING - reuse
├── enrich_linkedin.py              # EXISTING - reuse
├── enrich_hunter.py                # EXISTING - reuse
└── enrich_apollo_paid.py           # EXISTING - reuse

.claude/commands/
├── enrich-supervised.md            # NEW
├── enrich-status.md                # NEW
├── enrich-single.md                # EXISTING - update
└── enrich-retry-failed.md          # NEW
```

---

## Implementation Phases

### Phase 1: Core Pipeline (MVP)
- [ ] Create `supervised_pipeline/` module structure
- [ ] Implement `orchestrator.py` with asyncio.gather
- [ ] Wire existing `enrich_*.py` scripts as stages
- [ ] Add basic terminal UI with progress display

### Phase 2: State Management
- [ ] Implement Redis state tracking
- [ ] Add Supabase sync after each company
- [ ] Budget tracking and enforcement

### Phase 3: Interactive Controls
- [ ] Keyboard controls (c/s/r/v/q)
- [ ] Retry logic for failed companies
- [ ] Detailed results view

### Phase 4: Claude Code Integration
- [ ] Create `/enrich-supervised` command
- [ ] Create `/enrich-status` command
- [ ] Update `/enrich-single` command
- [ ] Create `/enrich-retry-failed` command

---

## Success Criteria

- [ ] Can process 100 companies with 2-at-a-time parallelism
- [ ] Manual checkpoint after each batch works reliably
- [ ] Budget limits enforced correctly
- [ ] Progress survives terminal restart (Redis + Supabase)
- [ ] All 4 slash commands functional
- [ ] Claude Code can guide user through entire workflow
