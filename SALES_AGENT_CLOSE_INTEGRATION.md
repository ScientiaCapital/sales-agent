# Sales Agent → Close CRM Integration

**Complete tracking from enrichment discovery to closed won/lost deals.**

## 🎯 What This Does

Ensures **ZERO data loss** and **full attribution** by:

1. ✅ **Enriches companies** from website scraping + Apollo
2. ✅ **Syncs to Close CRM** with `sales-agent-enrichment` tag
3. ✅ **Tracks ATL contacts** discovered by scraper
4. ✅ **Monitors pipeline** from Lead → Opportunity → Won/Lost
5. ✅ **Attributes revenue** back to sales-agent enrichment

---

## 📊 Data Flow

```
┌─────────────────┐
│  Sales Agent    │  Scrapes websites, finds ATL names
│  Enrichment     │  Lookups via Apollo, Hunter
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Supabase      │  dim_companies + dim_contacts
│   Database      │  ICP scoring, enrichment timestamps
└────────┬────────┘
         │
         ↓ (Automatic Sync)
┌─────────────────┐
│   Close CRM     │  Tagged: custom.sales_agent_source = "sales-agent-enrichment"
│   Leads         │  Assigned to BDR/SDR for outreach
└────────┬────────┘
         │
         ↓ (Sales Team Works Lead)
┌─────────────────┐
│  Opportunity    │  Demo → Proposal → Negotiation
│  Created        │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Closed Won/    │  Tracked in fact_opportunities
│  Closed Lost    │  Full attribution maintained
└─────────────────┘
```

---

## 🚀 Quick Start

### 1. Run Initial Sync (After Enrichment Batch)

```bash
cd backend
source ../venv/bin/activate

# DRY RUN first (see what would happen)
python sales_agent_close_integration.py --sync-companies --dry-run --limit 50

# REAL SYNC (creates/updates Close leads)
python sales_agent_close_integration.py --sync-companies --limit 50
```

This creates Close CRM leads for all enriched companies with:
- ✅ Custom field: `sales_agent_source = "sales-agent-enrichment"`
- ✅ Enrichment timestamp
- ✅ ICP score and tier
- ✅ Company details (domain, address, phone)

### 2. Sync ATL Contacts

```bash
# Sync discovered ATL contacts to Close leads
python sales_agent_close_integration.py --sync-contacts --limit 100
```

This attaches ATL contacts (CEO, Owner, VP) to their Close leads.

### 3. Track Pipeline Progress

```bash
# Pull opportunity updates from Close CRM
python sales_agent_close_integration.py --track-pipeline
```

This monitors:
- New opportunities created from sales-agent leads
- Stage progressions (Demo, Proposal, etc.)
- Won/Lost outcomes
- Deal values

### 4. Generate Attribution Report

```bash
# See full ROI from sales-agent enrichment
python sales_agent_close_integration.py --report
```

Shows:
```
🎯 SALES AGENT ATTRIBUTION REPORT
================================================================================

📊 ENRICHMENT:
   Companies Enriched:       200

📈 PIPELINE:
   Total Opportunities:       45  ($1,250,000)
   Active:                    30  ($  900,000)
   Won:                       12  ($  300,000)
   Lost:                       3

🎯 PERFORMANCE:
   Win Rate:                 80.0%
   Avg Deal Size:         $ 25,000
```

---

## 🔄 Automated Sync Schedule

Add to Celery Beat (`backend/app/celery_app.py`):

```python
# Sync enriched companies to Close every 4 hours
'sync-enriched-to-close': {
    'task': 'sync_enriched_to_close_task',
    'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    'options': {'queue': 'crm_sync'}
},

# Track pipeline updates hourly
'track-close-pipeline': {
    'task': 'track_close_pipeline_task',
    'schedule': crontab(minute=30),  # Every hour at :30
    'options': {'queue': 'crm_sync'}
},
```

---

## 📋 Database Schema

### fact_opportunities

Tracks every opportunity from sales-agent enrichment:

| Column | Type | Description |
|--------|------|-------------|
| `opportunity_id` | UUID | Primary key |
| `company_id` | UUID | References dim_companies |
| `close_opportunity_id` | VARCHAR(100) | Close CRM opp ID |
| `status` | VARCHAR(20) | 'active', 'won', 'lost' |
| `stage` | VARCHAR(50) | 'Demo', 'Proposal', etc. |
| `value` | DECIMAL | Deal size ($) |
| `confidence` | INTEGER | 0-100% |
| `expected_close_date` | TIMESTAMPTZ | Forecast close |
| `actual_close_date` | TIMESTAMPTZ | When won/lost |
| `close_reason` | TEXT | Why won/lost |
| `sales_agent_attribution` | BOOLEAN | TRUE if from enrichment |

### dim_companies (New Columns)

| Column | Type | Description |
|--------|------|-------------|
| `synced_to_close_at` | TIMESTAMPTZ | Last sync timestamp |
| `close_sync_status` | VARCHAR(20) | 'pending', 'synced', 'failed' |

---

## 🎯 Custom Fields in Close CRM

You'll need to create these custom fields in Close:

1. **`sales_agent_source`** (Text)
   - Values: `"sales-agent-enrichment"`, `"manual"`, `"referral"`, etc.
   - Purpose: Track lead source attribution

2. **`enriched_at`** (Date)
   - Value: Timestamp when enriched
   - Purpose: Track enrichment recency

3. **`icp_score`** (Number)
   - Value: 0-115 (ICP score)
   - Purpose: Prioritize outreach

4. **`icp_tier`** (Text)
   - Values: `"PLATINUM"`, `"GOLD"`, `"SILVER"`, `"BRONZE"`, `"LEAD"`
   - Purpose: Segmentation for campaigns

---

## 📊 Reports You Can Generate

### 1. Enrichment ROI

```sql
SELECT
    COUNT(*) FILTER (WHERE sales_agent_attribution = TRUE) as sales_agent_opps,
    COUNT(*) as total_opps,
    SUM(value) FILTER (WHERE status = 'won' AND sales_agent_attribution = TRUE) as sales_agent_revenue,
    SUM(value) FILTER (WHERE status = 'won') as total_revenue
FROM fact_opportunities;
```

### 2. Conversion Funnel

```sql
SELECT
    COUNT(DISTINCT dc.company_id) as enriched_companies,
    COUNT(DISTINCT dc.company_id) FILTER (WHERE dc.close_lead_id IS NOT NULL) as synced_to_close,
    COUNT(DISTINCT fo.opportunity_id) as opportunities_created,
    COUNT(DISTINCT fo.opportunity_id) FILTER (WHERE fo.status = 'won') as closed_won
FROM dim_companies dc
LEFT JOIN fact_opportunities fo ON dc.company_id = fo.company_id
WHERE dc.apollo_enriched_at IS NOT NULL;
```

### 3. Time to Close

```sql
SELECT
    AVG(EXTRACT(DAY FROM (actual_close_date - created_at))) as avg_days_to_close,
    stage,
    status
FROM fact_opportunities
WHERE status IN ('won', 'lost')
GROUP BY stage, status;
```

---

## ⚠️ Important Notes

1. **CLOSE_WRITE_DISABLED must be FALSE** to sync to Close CRM
   - In `.env`: `CLOSE_WRITE_DISABLED=False`
   - Default is TRUE (read-only) for safety

2. **Run dry-run first** before syncing
   - Use `--dry-run` flag to preview changes

3. **Incremental syncs** work automatically
   - Only syncs companies enriched since last run
   - Updates existing Close leads instead of creating duplicates

4. **Custom field IDs** need to match your Close instance
   - Update `CUSTOM_FIELD_*` constants in `sales_agent_close_integration.py`
   - Get IDs from Close CRM → Settings → Custom Fields

---

## 🔧 Troubleshooting

### "Custom field not found" error

Create the custom field in Close CRM first:
1. Settings → Custom Fields → Add Custom Field
2. Copy the field ID (e.g., `cf_xxx`)
3. Update constants in integration script

### Duplicate leads created

Check domain matching logic:
```python
# Script searches by: url:"{domain}"
# Ensure domain format matches Close's url field
```

### Missing opportunities in report

Verify `sales_agent_source` custom field is set:
```python
# Check in Close CRM that field exists and has value
# Re-run sync to update existing leads
```

---

## 🎉 Success Criteria

You'll know it's working when:

1. ✅ Enriched companies appear in Close CRM with `sales-agent-enrichment` tag
2. ✅ ATL contacts are attached to Close leads
3. ✅ Opportunities created in Close show up in `fact_opportunities` table
4. ✅ Attribution report shows revenue from sales-agent leads
5. ✅ Conversion funnel shows path: Enrichment → Lead → Opp → Won

---

**Next Steps:**
1. Apply migration: `20251208_fact_opportunities_tracking.sql`
2. Create custom fields in Close CRM
3. Run initial sync with `--dry-run` to verify
4. Enable automated sync via Celery Beat
5. Monitor attribution report weekly
