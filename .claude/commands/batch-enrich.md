---
description: "Start parallel batch enrichment with real-time monitoring"
---

# Batch Enrichment Pipeline

Execute the parallel batch enrichment workflow for leads in Supabase.

## Workflow

### Phase 1: Select Leads
1. Query Supabase `dim_companies` for companies needing enrichment
2. Filter by ICP tier (PLATINUM/GOLD first, then SILVER)
3. Check rate limit quotas before starting

```bash
# Check current rate limits
curl http://localhost:8001/api/batch/rate-limits/status
```

### Phase 2: Start Batch
1. Select company IDs from the query results
2. Call POST `/api/batch/start` with configuration
3. Options: `skip_marketing`, `skip_bdr_draft`, priority level

```bash
# Start a batch (example)
curl -X POST http://localhost:8001/api/batch/start \
  -H "Content-Type: application/json" \
  -d '{
    "name": "December Enrichment",
    "company_ids": ["uuid1", "uuid2"],
    "priority": "high",
    "options": {"skip_marketing": true}
  }'
```

### Phase 3: Monitor Progress
1. Connect WebSocket for real-time updates
2. Display stage completions as they happen
3. Track cost/latency metrics

```bash
# Check batch status
curl http://localhost:8001/api/batch/{batch_id}

# List all batches
curl http://localhost:8001/api/batch/
```

### Phase 4: Control Operations
- **Pause**: `POST /api/batch/{id}/pause`
- **Resume**: `POST /api/batch/{id}/resume`
- **Cancel**: `POST /api/batch/{id}/cancel`

## Pipeline Stages (LangGraph)

```
Group A (Parallel): Qualification + CRM Check
        ↓
    Conditional: should_enrich?
        ↓
Group B (Parallel): Enrichment + SalesIntel
        ↓
Group C (Parallel): Marketing + BDR Draft
        ↓
    Finalize → Update Supabase
```

**Performance**: 8-12s per lead (~40% faster than sequential)

## Rate Limits Protected

| Service | Limit | Tracked Via |
|---------|-------|-------------|
| Apollo | 200/hour, 2000/day | Redis |
| Hunter.io | 50/month | Redis |
| Browserbase | 5 concurrent | Redis semaphore |

## Quick Start

```bash
# 1. Start services
docker-compose up -d
python start_server.py

# 2. Query leads needing enrichment
# (Use Supabase dashboard or query dim_companies)

# 3. Start batch via API or BatchControlPanel UI
```
