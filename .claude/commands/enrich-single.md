---
description: "Quick single-lead enrichment via ParallelPipeline"
---

# Single Lead Enrichment

Fast enrichment for one company through the ParallelPipeline.

## Usage

Provide a company ID or name to enrich:

```
/enrich-single <company_id or name>
```

## Workflow

### Step 1: Fetch Company
Query Supabase `dim_companies` by ID or fuzzy name match.

```python
# Via Python
from supabase import create_client
supabase = create_client(url, key)

# By ID
result = supabase.table("dim_companies").select("*").eq("company_id", company_id).single().execute()

# By name (fuzzy)
result = supabase.table("dim_companies").select("*").ilike("name", f"%{name}%").limit(5).execute()
```

### Step 2: Run Pipeline
Execute ParallelPipeline with the lead data:

```python
from app.services.parallel_pipeline import ParallelPipeline

pipeline = ParallelPipeline()
result = await pipeline.execute(
    lead=company_data,
    options={"skip_marketing": False}
)
```

### Step 3: Display Results
Show enrichment results:

| Field | Value |
|-------|-------|
| Lead Tier | `result.lead_tier` (PLATINUM/GOLD/SILVER/BRONZE) |
| Contacts Found | From `result.enrichment` |
| Personal Hooks | From `result.sales_intel` |
| Email Draft | From `result.bdr_draft` |
| Total Cost | `result.total_cost_usd` |
| Latency | `result.total_latency_ms` |

### Step 4: Update Supabase
Write enrichment data back to `dim_companies`:

```python
supabase.table("dim_companies").update({
    "last_enriched_at": datetime.utcnow().isoformat(),
    "icp_tier": result.lead_tier,
    "ai_personal_hooks": result.sales_intel.get("personal_hooks"),
    "ai_company_story": result.sales_intel.get("company_story"),
}).eq("company_id", company_id).execute()
```

## Pipeline Stages

```
Qualification (Cerebras) → CRM Check (Close) →
Enrichment (Apollo/Hunter) → SalesIntel (extract hooks) →
Marketing + BDR Draft → Finalize
```

## Quick Test

```bash
# Via API (if server running)
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{"lead": {"company_id": "xxx", "name": "Test Company"}}'
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `skip_enrichment` | false | Skip Apollo/Hunter calls |
| `skip_marketing` | false | Skip content generation |
| `skip_bdr_draft` | false | Skip outreach draft |
