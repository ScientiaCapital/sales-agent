# Pre-Enrichment Baseline Metrics Report

## Overview

The `generate_baseline_metrics.py` script captures a comprehensive snapshot of the sales-agent database **BEFORE** running enrichment on 2,951+ unenriched dealer companies.

This baseline report enables you to:
1. Measure enrichment pipeline effectiveness after completion
2. Track improvements in contact discovery and ATL coverage
3. Identify data quality issues before they propagate
4. Make informed decisions about enrichment prioritization

## What Gets Measured

### 1. **Companies by Source**
Tracks company distribution across different data sources with enrichment status:
- Count of companies per `original_source` (e.g., dealer-scraper, Close CRM, manual imports)
- Breakdown of enriched vs unenriched within each source
- Enrichment percentage by source

### 2. **Contact Distribution (ATL vs BTL)**
Analyzes decision-maker coverage:
- **ATL (Above The Line):** Executives, decision makers, key stakeholders
- **BTL (Below The Line):** Individual contributors, technical staff
- Percentage distribution of each type

### 3. **ATL Coverage**
Shows how many companies have at least one decision-maker contact:
- Companies with 1+ ATL contacts
- Total company count
- Coverage percentage (critical KPI)

### 4. **Multi-ATL Companies**
Identifies high-value targets with multiple decision makers:
- Companies with 2+ ATL contacts
- Distribution of ATL counts (2 ATL, 3 ATL, etc.)

### 5. **Enrichment Status Distribution**
Tracks where companies are in the enrichment pipeline:
- `unenriched` - No enrichment attempt yet
- `found_contacts` - Team page found with contacts
- `found_page_no_contacts` - Team page found but empty
- `no_team_page` - No team page exists
- `needs_js_render` - Flagged for Browserbase

### 6. **Domain Coverage**
Shows data quality:
- Companies with valid domain info
- Companies without domains
- Coverage percentage

### 7. **Pipeline State Distribution**
Current stage distribution across all companies:
- `imported` - Initial state
- Other custom pipeline stages

## Running the Script

### Prerequisites
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent

# Activate virtual environment
source venv/bin/activate

# Install dependencies (if needed)
pip install -r backend/requirements.txt
```

### Execution
```bash
cd backend
python generate_baseline_metrics.py
```

### Expected Output
```
2025-12-15 10:30:45 - INFO - Connected to Supabase: https://oyyakkuvvtckocncuwwf.supabase.co
2025-12-15 10:30:46 - INFO - ✓ Companies by source: 5 source groups
2025-12-15 10:30:47 - INFO - ✓ Contact distribution: 4,250 total (1,200 ATL, 3,050 BTL)
2025-12-15 10:30:48 - INFO - ✓ ATL coverage: 2,100/2,951 (71.15%)
2025-12-15 10:30:49 - INFO - ✓ Multi-ATL companies: 850 companies with 2+ ATLs
2025-12-15 10:30:50 - INFO - ✓ Enrichment status: 8 status types
2025-12-15 10:30:51 - INFO - ✓ Domain coverage: 2,951/2,951 (100.00%)
2025-12-15 10:30:52 - INFO - ✓ Pipeline state: 3 stage types
2025-12-15 10:30:53 - INFO - ✓ Report saved to: /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data/BASELINE_METRICS_20251215.md

======================================================================
BASELINE METRICS GENERATION COMPLETE
======================================================================

Timestamp: 2025-12-15 10:30:53
Total Companies: 2,951
Domain Coverage: 100.00%
Total Contacts: 4,250
  - ATL: 1,200
  - BTL: 3,050
ATL Coverage: 71.15%

Report: /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data/BASELINE_METRICS_20251215.md
======================================================================
```

## Output Files

### 1. Markdown Report
**File:** `backend/data/BASELINE_METRICS_YYYYMMDD.md`

Human-readable report with:
- Executive summary table
- Detailed metrics tables
- Status definitions
- Next steps for enrichment
- Technical implementation details

### 2. JSON Snapshot
**File:** `backend/data/BASELINE_METRICS_YYYYMMDD.json`

Machine-readable metrics for:
- Programmatic comparison with post-enrichment results
- Integration with dashboards
- Historical tracking

**Example structure:**
```json
{
  "timestamp": "2025-12-15T10:30:53.123456",
  "metrics": {
    "companies_by_source": [
      {
        "source": "dealer-scraper",
        "total_companies": 2100,
        "enriched_count": 1050,
        "unenriched_count": 1050,
        "enrichment_pct": 50.0
      }
    ],
    "contact_distribution": {
      "total_contacts": 4250,
      "by_type": [
        {"contact_type": "ATL (Above The Line)", "total": 1200, "percentage": 28.24},
        {"contact_type": "BTL (Below The Line)", "total": 3050, "percentage": 71.76}
      ]
    },
    ...
  }
}
```

## Using the Baseline Report

### Before Enrichment
1. Generate baseline metrics (this script)
2. Review report to identify focus areas
3. Adjust enrichment strategy if needed

### During Enrichment
1. Monitor `run_enrichment.py` progress
2. Watch for failures or data quality issues
3. Reference baseline stats for context

### After Enrichment
1. Run script again with new timestamp
2. Compare metrics side-by-side
3. Calculate improvements:
   - Success rate = (post_enriched - pre_enriched) / pre_unenriched
   - ATL coverage improvement
   - Contact discovery rate
   - Domain coverage change

### Example Comparison
```
Metric                  | Before | After | Delta  | % Improvement
------------------------|--------|-------|--------|---------------
ATL Coverage            | 71.15% | 85.00%| +13.85%| +19.5%
Companies with 2+ ATLs  | 850    | 1,500 | +650   | +76.5%
Total Contacts          | 4,250  | 8,500 | +4,250 | +100.0%
Domain Coverage         | 100%   | 100%  | —      | —
```

## Database Schema Reference

### dim_companies
- `company_id` (UUID, PK)
- `company_name` (VARCHAR)
- `domain` (VARCHAR)
- `original_source` (VARCHAR) - Where company came from
- `enrichment_status` (VARCHAR) - Current enrichment state
- `current_stage` (VARCHAR) - Pipeline stage
- `icp_score`, `icp_tier` - Scoring metrics
- `created_at`, `updated_at` (TIMESTAMPTZ)

### dim_contacts
- `contact_id` (UUID, PK)
- `company_id` (UUID, FK)
- `full_name`, `first_name`, `last_name` (VARCHAR)
- `email` (VARCHAR)
- `title` (VARCHAR)
- `is_atl` (BOOLEAN) - TRUE for decision makers
- `confidence` (INTEGER, 0-100)
- `source` (VARCHAR) - enrichment source (hunter, apollo, browserbase, etc.)
- `created_at`, `updated_at` (TIMESTAMPTZ)

## Troubleshooting

### Connection Issues
```python
# Check Supabase credentials in .env
SUPABASE_URL=https://oyyakkuvvtckocncuwwf.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIs...
```

### Query Failures
- Check if tables exist in Supabase dashboard
- Verify service role has SELECT permissions
- Review logs in stderr output

### Missing Metrics
- Some metrics may fail independently
- Script continues on partial failures
- JSON will contain null values for failed queries

## Performance Considerations

- **Query Time:** ~2-5 seconds for 2,951 companies
- **Memory:** ~50MB for full dataset in memory
- **Rate Limiting:** No rate limits (service role)
- **Concurrent Runs:** Safe to run multiple instances

## Security

- **Credentials:** Uses SUPABASE_SERVICE_KEY from .env (never hardcoded)
- **Permissions:** Service role has full read access
- **Output:** Reports contain no sensitive data (aggregated metrics only)
- **Storage:** Local files on disk, not transmitted externally

## Next Steps

### 1. Run Enrichment Pipeline
```bash
cd backend
python run_enrichment.py
```

### 2. Monitor Progress
```bash
python live_enrichment_monitor.py
```

### 3. Generate Post-Enrichment Report
```bash
# Rerun this script after enrichment completes
python generate_baseline_metrics.py
```

### 4. Compare Results
```bash
# Manual comparison or use diff tools:
diff -u backend/data/BASELINE_METRICS_20251215.json backend/data/BASELINE_METRICS_20251216.json
```

## Related Files

- **Enrichment Runner:** `backend/run_enrichment.py`
- **Live Monitor:** `backend/live_enrichment_monitor.py`
- **Enrichment Audit:** `backend/audit_enrichment.py`
- **Contact Quality:** `backend/CONTACT_QUALITY_AUDIT_REPORT.md`

## Questions or Issues?

Refer to the generated markdown report for detailed metrics and technical implementation notes.
