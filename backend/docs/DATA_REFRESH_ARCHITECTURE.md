# Data Refresh Architecture

## Overview

This document describes how to maintain clean, up-to-date lead data across 6-12 month refresh cycles as scrapers are fixed and new data becomes available.

**Philosophy**: All scripts must be idempotent - running them twice should produce the same result, with only legitimate changes applied.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA REFRESH CYCLE                                 │
│                                                                              │
│   SCRAPER OUTPUT                 SALES-AGENT PIPELINE                        │
│   (dealer-scraper-mvp)          (idempotent processing)                     │
│                                                                              │
│   ┌─────────────────┐      ┌──────────────────────────────────┐             │
│   │  grandmaster/   │      │                                  │             │
│   │  OEM lists      │──┬──▶│  1. create_gold_standard_lists.py│             │
│   │  (CSV files)    │  │   │     - Score + rank leads         │             │
│   └─────────────────┘  │   │     - Deduplicate                │             │
│                        │   │     - Export tiers               │             │
│   ┌─────────────────┐  │   └──────────────┬───────────────────┘             │
│   │  Fixed scrapers │──┤                  │                                  │
│   │  (new data)     │  │                  ▼                                  │
│   └─────────────────┘  │   ┌──────────────────────────────────┐             │
│                        │   │                                  │             │
│   ┌─────────────────┐  │   │  2. enrich_gold_standard_batch.py│             │
│   │  Manual fixes   │──┘   │     - Hunter.io contact discovery│             │
│   │  (Tim's updates)│      │     - Track enrichment costs     │             │
│   └─────────────────┘      │     - Skip already-enriched      │             │
│                            └──────────────┬───────────────────┘             │
│                                           │                                  │
│                                           ▼                                  │
│                            ┌──────────────────────────────────┐             │
│                            │                                  │             │
│                            │  3. sync_gold_standard_to_supabase│            │
│                            │     - Upsert companies           │             │
│                            │     - Upsert contacts            │             │
│                            │     - Track change history       │             │
│                            │     - Archive stale data         │             │
│                            └──────────────────────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Principles

### 1. Idempotent Scripts

Every script checks "has this been done?" before acting:

```python
# Good - Check then act
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_set = {r['normalized_name'] for r in existing.data}

for lead in new_leads:
    if lead.normalized_name in existing_set:
        # UPDATE existing record
        update_company(lead)
    else:
        # INSERT new record
        insert_company(lead)
```

```python
# Bad - Blind insert
for lead in new_leads:
    insert_company(lead)  # Fails on duplicates or creates garbage
```

### 2. Timestamp Tracking

Every record tracks when it was last updated from each source:

```sql
-- dim_companies columns for refresh tracking
created_at TIMESTAMP NOT NULL DEFAULT NOW(),
updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
last_scraped_at TIMESTAMP,      -- When scraper last saw this company
last_enriched_at TIMESTAMP,     -- When Hunter.io/Apollo ran
last_validated_at TIMESTAMP,    -- When website/phone verified
stale_after TIMESTAMP,          -- When re-enrichment needed (30-90 days)
```

### 3. Change Detection

Track what changed for audit and debugging:

```sql
-- lead_change_log table
CREATE TABLE lead_change_log (
    change_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    change_type VARCHAR(20),  -- 'insert', 'update', 'archive', 'restore'
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    change_source VARCHAR(50),  -- 'scraper_refresh', 'hunter_enrichment', 'manual'
    changed_at TIMESTAMP DEFAULT NOW()
);
```

## Refresh Scenarios

### Scenario 1: New Scraper Run (6-12 months)

**Trigger**: dealer-scraper-mvp produces new grandmaster list

**What Happens**:
1. New leads → INSERT into dim_companies
2. Updated leads → UPDATE fields that changed
3. Missing leads → Mark `is_stale = true`, NOT deleted

```bash
# Run from backend/
python create_gold_standard_lists.py --refresh

# This will:
# - Load new scraper output
# - Compare against existing leads (by normalized_name)
# - Update scores, tiers, metadata
# - Flag leads missing from new scrape as "stale"
```

### Scenario 2: Broken Scraper Fixed

**Trigger**: A scraper that was returning bad data is now fixed

**What Happens**:
1. Re-run affected leads through pipeline
2. "Stale" leads from that source get updated
3. Change log shows what was wrong before

```bash
# Re-import from a specific source
python import_mep_batch.py data/csv/fixed_schneider_dealers.csv --source schneider_fixed

# Mark old bad data as superseded
python mark_superseded.py --source schneider_broken --superseded-by schneider_fixed
```

### Scenario 3: Tim Adds Contacts Manually

**Trigger**: Tim finds contacts via LinkedIn/research, adds to Close CRM

**What Happens**:
1. Cron runs every 30 minutes
2. New/updated Close contacts synced to dim_contacts
3. Links to existing dim_companies via company name fuzzy match

```bash
# Cron job (already configured)
*/30 * * * * cd /path/to/backend && python sync_close_contacts_to_supabase.py
```

### Scenario 4: Re-Enrichment Needed

**Trigger**: 30+ days since last enrichment OR contact bounced

**What Happens**:
1. Flag company in `re_enrich_queue`
2. Next batch enrichment picks it up
3. New contacts replace/supplement old

```bash
# Check what needs re-enrichment
python check_reenrich_queue.py --stats

# Process re-enrichment queue
python enrich_gold_standard_batch.py --reenrich
```

## Database Schema for Refresh

### dim_companies additions

```sql
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS
    is_stale BOOLEAN DEFAULT FALSE,
    stale_reason VARCHAR(100),
    stale_since TIMESTAMP,
    source_refresh_id UUID,
    previous_version_id UUID REFERENCES dim_companies(company_id);
```

### re_enrich_queue (cross-project)

```sql
CREATE TABLE re_enrich_queue (
    queue_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    normalized_name VARCHAR(255),
    domain VARCHAR(255),
    reason VARCHAR(100),  -- 'time_based', 'manual_flag', 'bounce_detected', 'new_info'
    priority INTEGER DEFAULT 0,  -- Higher = more urgent
    queued_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'  -- 'pending', 'processing', 'done', 'failed'
);
```

## Commands Reference

### Full Refresh (After Major Scraper Update)

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend

# Step 1: Re-score all leads with new data
python create_gold_standard_lists.py --refresh

# Step 2: Run enrichment on top 500 (or budget allows)
python enrich_gold_standard_batch.py --batch 1

# Step 3: Sync everything to Supabase
python sync_gold_standard_to_supabase.py
python sync_gold_standard_to_supabase.py --refresh-views

# Step 4: Generate report on what changed
python generate_refresh_report.py --compare-to 20251129
```

### Incremental Update (Weekly)

```bash
# Sync any manual changes from Close CRM
python sync_close_contacts_to_supabase.py --hours 168  # 7 days

# Process re-enrichment queue
python enrich_gold_standard_batch.py --reenrich --max 50
```

### OEM-Focused Campaign

```bash
# Filter for specific OEM campaign
python filter_leads_by_oem.py schneider --top 100
python filter_leads_by_oem.py carrier --top 200
python filter_leads_by_oem.py --multi --min-oems 3
```

## Change History Example

When data is refreshed, the change log captures:

```
| company        | field      | old_value | new_value  | source          | date       |
|----------------|------------|-----------|------------|-----------------|------------|
| ABC Heating    | phone      | NULL      | 555-1234   | hunter_enrichment | 2025-11-29 |
| ABC Heating    | icp_score  | 45        | 72         | scraper_refresh  | 2025-11-29 |
| XYZ Solar      | is_stale   | false     | true       | scraper_refresh  | 2025-11-29 |
| XYZ Solar      | stale_reason | NULL    | not_in_new_scrape | scraper_refresh | 2025-11-29 |
```

## Best Practices

### DO

- ✅ Always use normalized_name for matching (lowercase, stripped)
- ✅ Track timestamps for every data source
- ✅ Keep change logs for debugging
- ✅ Mark stale instead of delete
- ✅ Test scripts with --dry-run before production

### DON'T

- ❌ DELETE leads that aren't in new scrape (mark stale instead)
- ❌ Overwrite good data with NULL from incomplete sources
- ❌ Run enrichment on already-enriched leads without checking
- ❌ Skip the change log - you'll regret it during debugging

## Monitoring

### Dashboard Metrics to Track

1. **Freshness**: % of leads enriched in last 30/60/90 days
2. **Stale Rate**: % of leads marked stale
3. **Change Velocity**: Leads updated per week
4. **Coverage**: % of leads with phone, email, ATL contact

### Alerts to Set

- `stale_count > 1000` - Too many stale leads, check scrapers
- `enrichment_age > 60 days` - Need re-enrichment batch
- `contact_bounce_rate > 10%` - Data quality issue
