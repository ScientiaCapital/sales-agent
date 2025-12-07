# Monday 8 AM Launch Plan - December 9, 2025

## Goal
Process 8,000+ leads through the new agent pipeline with:
- Parallel agent execution (maximize throughput)
- 100% review gates (no auto-send without approval)
- Agent skill matching (right agent for each task)

---

## Pre-Flight Checklist (5 min)

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate

# 1. Verify Docker is running
docker-compose ps

# 2. Check Redis connection
redis-cli ping  # Should return PONG

# 3. Check PostgreSQL
docker-compose exec postgres pg_isready  # Should be accepting connections
```

---

## Startup Sequence (Terminal Commands)

### Terminal 1: FastAPI Server
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
python start_server.py
# Runs on http://localhost:8001
```

### Terminal 2: Celery Worker (Main Queue)
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
celery -A app.celery_app worker --loglevel=info -Q default,workflows
```

### Terminal 3: Celery Worker (CRM Sync Queue)
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
celery -A app.celery_app worker --loglevel=info -Q crm_sync
```

### Terminal 4: Celery Beat (Scheduler)
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
celery -A app.celery_app beat --loglevel=info
```

---

## One-Command Startup Script

Save this as `start_monday.sh`:

```bash
#!/bin/bash
# Monday 8 AM Launch Script

cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate

echo "🚀 Starting Sales Agent Platform..."

# Start Docker if not running
docker-compose up -d

# Wait for services
sleep 3

# Start all services in background with logs to files
echo "Starting FastAPI..."
nohup python start_server.py > logs/fastapi.log 2>&1 &

echo "Starting Celery Worker (default)..."
nohup celery -A app.celery_app worker --loglevel=info -Q default,workflows > logs/celery_worker.log 2>&1 &

echo "Starting Celery Worker (crm_sync)..."
nohup celery -A app.celery_app worker --loglevel=info -Q crm_sync > logs/celery_crm.log 2>&1 &

echo "Starting Celery Beat..."
nohup celery -A app.celery_app beat --loglevel=info > logs/celery_beat.log 2>&1 &

sleep 2
echo "✅ All services started!"
echo ""
echo "📊 Health check: curl http://localhost:8001/api/health"
echo "📋 Logs: tail -f logs/*.log"
```

---

## Lead Processing Pipeline

### Phase 1: Data Audit (8:00 - 8:15 AM)

**Agent**: Explore agent
**Task**: Audit current lead state in Supabase

```
In Claude Code, say:
"Audit the 8,000+ leads in Supabase. Show me:
- Total count by ICP tier (PLATINUM/GOLD/SILVER/BRONZE)
- Count with email vs without
- Count with phone vs without
- Count enriched vs unenriched
- Count with ATL contacts vs without"
```

### Phase 2: Parallel Enrichment (8:15 - 12:00 PM)

**Agent Matching**:
| Lead State | Agent | Queue | Parallelism |
|------------|-------|-------|-------------|
| No domain | ScoutAgent | default | 10 concurrent |
| Has domain, no contacts | ScoutAgent | default | 10 concurrent |
| Has contacts, no ICP | RankingAgent | default | 20 concurrent |
| PLATINUM/GOLD, no drafts | OutreachAgent | workflows | 5 concurrent |

**Launch Command** (in Claude Code):
```
"Start parallel enrichment of all unenriched leads:
1. Use ScoutAgent for website scraping (10 parallel)
2. Use RankingAgent for ICP scoring (20 parallel)
3. Use OutreachAgent for HOT leads only (5 parallel)
4. 100% review gates - no auto-send
5. Report progress every 100 leads"
```

### Phase 3: Review Gates (Rolling)

**100% Review Gate Protocol**:
1. All drafts saved to `dim_ai_drafts` table with `status = 'pending'`
2. Slack notification to #bdr-approvals for each batch
3. Dashboard shows pending drafts at `/dashboard/drafts`
4. No email/SMS sent until manually approved

**Review Cadence**:
- Every 50 enriched leads → pause for quality check
- Every 100 drafts → batch review in dashboard
- Any PLATINUM lead → immediate Slack alert for manual review

---

## Agent Skill Matching Matrix

| Task | Best Agent | Why |
|------|-----------|-----|
| Website scraping | **ScoutAgent** | Has Browserbase + extraction tools |
| LinkedIn data | **ScoutAgent** | LinkedIn session manager |
| ICP scoring | **RankingAgent** | Prediction model + tier logic |
| Contact discovery | **ScoutAgent** | ATL/BTL detection patterns |
| Email drafts | **OutreachAgent** | Personal hook integration |
| SMS drafts | **OutreachAgent** | Tone + length optimization |
| Close CRM sync | **SyncAgent** | Webhook + polling handlers |
| Morning prep | **BriefingAgent** | "Why call now" reasoning |

---

## Parallelization Strategy

### Batch Sizes (Optimized for API Rate Limits)

| Service | Rate Limit | Batch Size | Delay Between |
|---------|-----------|------------|---------------|
| Browserbase | 10 concurrent | 10 | 2s |
| Claude API | 60 RPM | 50 | 1s |
| Supabase | 1000 RPM | 100 | 0s |
| Close CRM | 100 RPM | 50 | 1s |

### Parallel Execution Pattern

```python
# Claude Code will use this pattern:
from app.tasks.scout_tasks import run_scout_for_company
from app.tasks.ranking_tasks import run_ranking_for_company_task

# Batch 1: 10 parallel scout tasks
for company_id in batch_1_ids:
    run_scout_for_company.delay(company_id)

# Wait for completion, then...

# Batch 2: 20 parallel ranking tasks
for company_id in enriched_ids:
    run_ranking_for_company_task.delay(company_id)
```

---

## Review Gate Checkpoints

### Checkpoint 1: After Enrichment (Every 100 leads)
```
Verify:
- [ ] ATL contacts discovered?
- [ ] Phones/emails captured?
- [ ] Brands detected?
- [ ] Service areas extracted?
- [ ] No garbage contacts (3-layer filter working)?
```

### Checkpoint 2: After ICP Scoring (Every 100 leads)
```
Verify:
- [ ] Scores in expected ranges?
- [ ] Tier distribution reasonable?
- [ ] PLATINUM/GOLD flagged correctly?
- [ ] No scoring anomalies?
```

### Checkpoint 3: After Draft Generation (Every 50 drafts)
```
Verify:
- [ ] Personal hooks relevant?
- [ ] Tone appropriate?
- [ ] No hallucinated data?
- [ ] Call-to-action clear?
- [ ] All drafts in 'pending' status?
```

---

## Progress Tracking Dashboard

### Key Metrics to Monitor

| Metric | Target | Check Command |
|--------|--------|---------------|
| Enriched/hour | 200+ | `curl localhost:8001/api/dashboard/metrics` |
| ICP scored/hour | 500+ | Same |
| Drafts pending | Track | `curl localhost:8001/api/dashboard/outreach` |
| Errors | 0 | `tail -f logs/*.log | grep ERROR` |

### Real-Time Monitoring

```bash
# Watch Celery task queue
watch -n 5 'celery -A app.celery_app inspect active'

# Watch logs for errors
tail -f logs/*.log | grep -E "(ERROR|WARNING|SUCCESS)"

# Check Supabase counts
curl -s localhost:8001/api/dashboard/metrics | jq '.total_leads, .enriched_count'
```

---

## Emergency Stop Procedure

If something goes wrong:

```bash
# Stop all Celery workers gracefully
pkill -f "celery.*worker"

# Stop beat scheduler
pkill -f "celery.*beat"

# Check what's still running
ps aux | grep celery

# Force kill if needed
pkill -9 -f celery
```

---

## End of Day Checklist

- [ ] All pending drafts reviewed
- [ ] No 'pending' outreach left unreviewed
- [ ] Progress logged in `START_HERE_DEC_9.md`
- [ ] Errors investigated and documented
- [ ] Metrics captured (before/after counts)
- [ ] Git commit with any fixes

---

## Quick Reference

```bash
# Health check
curl http://localhost:8001/api/health

# Lead counts
curl http://localhost:8001/api/dashboard/metrics

# Agent status
curl http://localhost:8001/api/dashboard/agents

# Pending drafts
curl http://localhost:8001/api/dashboard/outreach

# Queue depth
celery -A app.celery_app inspect reserved
```

---

*Ready for Monday 8 AM launch!*
