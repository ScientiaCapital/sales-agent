# Enrichment Status

Check current enrichment progress across all companies.

## Usage
```
/enrich-status
```

## What This Shows

1. **Overall Progress** - Total, completed, failed, pending
2. **Recent Activity** - Last enrichment batches
3. **Cost Summary** - Spent today, budget remaining

## Execution

Query Supabase for counts:
```sql
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE enrichment_status = 'completed') as completed,
  COUNT(*) FILTER (WHERE enrichment_status = 'failed') as failed,
  COUNT(*) FILTER (WHERE enrichment_status IS NULL) as pending
FROM dim_companies;
```

## Example Output

```
Enrichment Status
─────────────────
Total Companies: 8,889
✅ Completed: 156
❌ Failed: 3
⏳ Pending: 8,730

Recent Batches:
- batch-20251202-143000: 10 companies, $0.45
- batch-20251202-120000: 8 companies, $0.32
```
