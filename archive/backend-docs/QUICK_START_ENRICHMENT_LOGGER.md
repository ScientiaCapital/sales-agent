# EnrichmentLogger Quick Start

## 1. Import (run_enrichment.py)

```python
from app.services.enrichment_logger import log_enrichment_attempt, log_stage_transition
```

## 2. Log Enrichment

```python
import time

# Before enrichment
start = time.time()

try:
    # Do enrichment
    contacts = hunter_search(domain)

    # Log success
    log_enrichment_attempt(
        supabase_client=supabase,
        company_id=company_id,
        method='hunter',
        success=True,
        contacts_found=len(contacts),
        emails_found=sum(1 for c in contacts if c.get('email')),
        cost_usd=0.05,
        latency_ms=int((time.time() - start) * 1000)
    )

except Exception as e:
    # Log failure
    log_enrichment_attempt(
        supabase_client=supabase,
        company_id=company_id,
        method='hunter',
        success=False,
        cost_usd=0.0,
        latency_ms=int((time.time() - start) * 1000),
        error_message=str(e)
    )
```

## 3. Log Stage Changes

```python
# When batch starts
log_stage_transition(supabase, company_id, from_stage='discovery', to_stage='enrichment')

# When enrichment completes
log_stage_transition(supabase, company_id, from_stage='enrichment', to_stage='qualification')

# If enrichment fails
log_stage_transition(supabase, company_id, from_stage='enrichment', to_stage='failed')
```

## 4. Methods

| Method | Cost | Description |
|--------|------|-------------|
| `hunter` | $0.05 | Hunter.io email search |
| `apollo` | $0.10 | Apollo.io contact lookup |
| `browserbase` | $0.015 | Browserbase website scraping |
| `website_scrape` | $0.00 | Direct scraping |
| `review_scrape` | $0.00 | Review sites |

## 5. Stages

```
discovery → enrichment → qualification → outreach
            ↓
          failed
```

## 6. Test

```bash
cd backend
python test_enrichment_logger.py
```

## 7. Verify in Supabase

```sql
-- Recent enrichments
SELECT * FROM fact_enrichments
ORDER BY enriched_at DESC LIMIT 10;

-- Stage transitions
SELECT * FROM fact_pipeline_stages
ORDER BY changed_at DESC LIMIT 10;

-- Cost per method
SELECT
    method,
    SUM(cost_usd) as total_cost,
    SUM(contacts_found) as contacts,
    ROUND(SUM(cost_usd) / NULLIF(SUM(contacts_found), 0), 4) as cost_per_contact
FROM fact_enrichments
WHERE success = true
GROUP BY method;
```

## Full Docs

- `ENRICHMENT_LOGGER_README.md` - Complete documentation
- `enrichment_logger_example.py` - 5 detailed examples
- `INTEGRATION_SUMMARY.md` - Overview and next steps
