# EnrichmentLogger Service

Logs enrichment events to Supabase fact tables for cost tracking, performance monitoring, and funnel analysis.

## Overview

The `EnrichmentLogger` service writes to two Supabase tables:
- **`fact_enrichments`**: Tracks every enrichment attempt with costs, performance, and results
- **`fact_pipeline_stages`**: Tracks stage transitions for funnel analysis (SCD Type 2 pattern)

This enables:
- Cost per contact/email analysis
- Enrichment method performance comparison
- Success rate tracking by method
- Funnel conversion analysis
- ROI calculation for each enrichment source

## Quick Start

### Synchronous Usage (run_enrichment.py)

```python
from app.services.enrichment_logger import log_enrichment_attempt, log_stage_transition

# Get Supabase client
supabase = get_supabase()

# Log enrichment attempt
log_enrichment_attempt(
    supabase_client=supabase,
    company_id="uuid-here",
    method="hunter",
    success=True,
    contacts_found=5,
    emails_found=3,
    cost_usd=0.05,
    latency_ms=1250
)

# Log stage transition
log_stage_transition(
    supabase_client=supabase,
    company_id="uuid-here",
    from_stage="discovery",
    to_stage="enrichment"
)
```

### Async Usage (FastAPI endpoints)

```python
from supabase import create_client
from app.services.enrichment_logger import EnrichmentLogger
import os

# Initialize
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)
logger = EnrichmentLogger(supabase)

# Log enrichment
await logger.log_enrichment_attempt(
    company_id="uuid-here",
    method="apollo",
    success=True,
    contacts_found=7,
    emails_found=5,
    cost_usd=0.10,
    latency_ms=2300
)

# Get stats
stats = await logger.get_enrichment_stats(since_hours=24)
print(f"Cost: ${stats['total_cost_usd']:.2f}")
print(f"Success rate: {stats['success_rate']*100:.1f}%")
```

## Enrichment Methods

Track different enrichment sources with the `method` parameter:

| Method | Description | Typical Cost |
|--------|-------------|--------------|
| `hunter` | Hunter.io email search | $0.05 per search |
| `apollo` | Apollo.io contact lookup | $0.10 per lookup |
| `browserbase` | Browserbase website scraping | $0.015 per session |
| `website_scrape` | Direct website scraping | $0.00 (self-hosted) |
| `review_scrape` | Review site scraping | $0.00 (self-hosted) |

## Pipeline Stages

Track company progression through the pipeline:

| Stage | Description |
|-------|-------------|
| `discovery` | Company discovered, not yet enriched |
| `enrichment` | Actively being enriched |
| `qualification` | Enrichment complete, being qualified |
| `outreach` | Qualified, ready for outreach |
| `failed` | Enrichment failed |

## Integration with run_enrichment.py

### Step 1: Import at top of file

```python
from app.services.enrichment_logger import log_enrichment_attempt, log_stage_transition
```

### Step 2: Log stage transition when batch starts

```python
# After get_unenriched_batch()
for company in companies:
    log_stage_transition(
        supabase_client=supabase,
        company_id=company['company_id'],
        from_stage='discovery',
        to_stage='enrichment'
    )
```

### Step 3: Log enrichment attempt after each method

```python
# After Hunter.io search
import time
start = time.time()

try:
    contacts = hunter_search(domain)
    latency_ms = int((time.time() - start) * 1000)

    log_enrichment_attempt(
        supabase_client=supabase,
        company_id=company_id,
        method='hunter',
        success=True,
        contacts_found=len(contacts),
        emails_found=sum(1 for c in contacts if c.get('email')),
        cost_usd=0.05,
        latency_ms=latency_ms
    )
except Exception as e:
    latency_ms = int((time.time() - start) * 1000)

    log_enrichment_attempt(
        supabase_client=supabase,
        company_id=company_id,
        method='hunter',
        success=False,
        cost_usd=0.0,
        latency_ms=latency_ms,
        error_message=str(e)
    )
```

### Step 4: Log final stage transition

```python
# After enrichment complete
log_stage_transition(
    supabase_client=supabase,
    company_id=company_id,
    from_stage='enrichment',
    to_stage='qualification'
)
```

## Analytics Queries

### Cost per contact by method

```sql
SELECT
    method,
    SUM(cost_usd) as total_cost,
    SUM(contacts_found) as total_contacts,
    ROUND(SUM(cost_usd) / NULLIF(SUM(contacts_found), 0), 4) as cost_per_contact
FROM fact_enrichments
WHERE success = true
GROUP BY method
ORDER BY cost_per_contact ASC;
```

### Success rate by method

```sql
SELECT
    method,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM fact_enrichments
GROUP BY method
ORDER BY success_rate DESC;
```

### Average latency by method

```sql
SELECT
    method,
    ROUND(AVG(latency_ms), 0) as avg_latency_ms,
    ROUND(AVG(latency_ms) / 1000.0, 2) as avg_latency_seconds
FROM fact_enrichments
WHERE latency_ms IS NOT NULL
GROUP BY method
ORDER BY avg_latency_ms ASC;
```

### Funnel analysis

```sql
SELECT
    to_stage,
    COUNT(DISTINCT company_id) as companies,
    COUNT(*) as transitions
FROM fact_pipeline_stages
GROUP BY to_stage
ORDER BY companies DESC;
```

### Conversion rates between stages

```sql
WITH stage_counts AS (
    SELECT
        to_stage as stage,
        COUNT(DISTINCT company_id) as count
    FROM fact_pipeline_stages
    GROUP BY to_stage
)
SELECT
    stage,
    count,
    ROUND(100.0 * count / LAG(count) OVER (ORDER BY count DESC), 2) as conversion_rate_pct
FROM stage_counts;
```

## Cost Tracking Example

```python
async def analyze_enrichment_costs():
    """Analyze enrichment costs over the last week."""
    logger = EnrichmentLogger(supabase)

    stats = await logger.get_enrichment_stats(since_hours=168)  # 7 days

    print(f"Total Enrichment Spend: ${stats['total_cost_usd']:.2f}")
    print(f"Total Contacts Found: {stats['total_contacts']}")
    print(f"Cost per Contact: ${stats['total_cost_usd'] / stats['total_contacts']:.3f}")
    print(f"Success Rate: {stats['success_rate']*100:.1f}%")
    print(f"\nBy Method:")
    for method, count in stats['by_method'].items():
        print(f"  {method}: {count} attempts")
```

## Schema Reference

### fact_enrichments

```sql
CREATE TABLE fact_enrichments (
    enrichment_id UUID PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    source_id UUID REFERENCES dim_sources(source_id),
    method VARCHAR(50) NOT NULL,
    contacts_found INTEGER DEFAULT 0,
    atl_found INTEGER DEFAULT 0,
    emails_found INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    enriched_at TIMESTAMPTZ DEFAULT NOW()
);
```

### fact_pipeline_stages

```sql
CREATE TABLE fact_pipeline_stages (
    stage_change_id UUID PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    changed_by UUID REFERENCES dim_users(user_id),
    from_stage VARCHAR(50),
    to_stage VARCHAR(50) NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Error Handling

The logger uses defensive error handling:
- Logging failures won't break enrichment flow
- Errors are logged but not raised
- Returns empty dict/list on failure
- All exceptions are caught and logged

```python
try:
    log_enrichment_attempt(...)
except Exception as e:
    # Logging error won't crash the enrichment
    logger.error(f"Failed to log: {e}")
```

## Next Steps

1. Import `log_enrichment_attempt` and `log_stage_transition` into `run_enrichment.py`
2. Add logging after each enrichment method (Hunter, Browserbase, etc.)
3. Add stage transitions at batch start/end
4. Build analytics dashboard using fact tables
5. Set up cost alerts based on `fact_enrichments` data

## Files

- `/backend/app/services/enrichment_logger.py` - Main service
- `/backend/app/services/enrichment_logger_example.py` - Usage examples
- `/supabase/migrations/006_star_schema_facts.sql` - Table definitions
