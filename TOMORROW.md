# TOMORROW.md - Next Steps (Nov 29, 2025)

## Today's Accomplishments (Nov 28, 2025)

### Star Schema + Dashboard LIVE
- **Supabase URL**: `https://oyyakkuvvtckocncuwwf.supabase.co`
- **Dashboard URL**: `https://sales-agent-dashboard-fawn.vercel.app`
- **Tables**: `dim_companies`, `dim_contacts`, `dim_users`, `fact_activities`, `fact_opportunities`, `fact_enrichments`
- **Views**: `mv_icp_gold_leads`, `mv_bdr_work_queue`, `v_stale_enrichments`, `v_pipeline_funnel`

### BDR Work Queue Customer Exclusions Fixed
- Added `map_close_status_to_stage()` function to sync script
- Excludes: `customer`, `not_interested`, `disqualified`, `bad_data`, `do_not_contact`, `won`, `lost`, `junk`
- 500 leads synced with proper stage mapping

### Action Solar Enrichment Complete
- Removed stale Trey Lackey (now at Same Day Solar)
- Added 8 new ATL contacts from Hunter.io:
  - Scott Clawson (Owner) - sclawson@actionsolar.com
  - Moroni Musser (COO) - mmusser@actionsolar.com
  - Brian Esplin (CFO) - besplin@actionsolar.com
  - Kyle Moore (Chief Sales Officer) - kmoore@actionsolar.com
  - Bobby Milbourn (VP Business Development)
  - Tyler Jacobsen (Director Supply Chain)
  - Koby Campbell (Sales Manager)
  - Alysa Matsumori (VP Sales)

---

## Priority Tasks for Tomorrow

### P1 - Dashboard Data Verification (1 hour)
- [ ] Verify BDR Work Queue shows in dashboard
- [ ] Check ICP Queue view shows PLATINUM leads (Action Solar, Solar States, Carbon Recall)
- [ ] Test Close CRM links work from dashboard
- [ ] Verify Recent Activity section pulls from `fact_activities`

### P2 - Run Enrichment on Top Leads (2 hours)
- [ ] Identify top 10 leads for enrichment (PLATINUM/GOLD tier, missing contacts)
- [ ] Run Hunter.io domain search on each
- [ ] Add new contacts to `dim_contacts`
- [ ] Refresh materialized views

### P3 - Sync Script Improvements (1 hour)
- [ ] Add unique constraint on `close_lead_id` to prevent duplicates
- [ ] Fix deprecated `datetime.utcnow()` warnings
- [ ] Add activity sync (currently only syncing 1/1000)

### P4 - Close CRM Contact Sync (1 hour)
- [ ] Consider re-enabling Close CRM writes for contacts only
- [ ] Sync new Hunter.io contacts back to Close CRM
- [ ] Or: Export to CSV for manual import

---

## Current Database State

### dim_companies (687 records)
| Stage | Count |
|-------|-------|
| imported | 460 |
| qualified | 91 |
| customer | 49 (excluded from queue) |
| nurture | 47 |
| opportunity | 27 |
| bad_data | 9 (excluded) |
| do_not_contact | 4 (excluded) |

### ICP Tier Distribution
| Tier | Count | Notes |
|------|-------|-------|
| PLATINUM | 4 | Action Solar, Solar States, Carbon Recall, ECC Energy |
| GOLD | ~87 | Score >= 70 |
| SILVER | ~150 | Score 50-69 |
| BRONZE | ~446 | Score < 50 |

### Top Leads to Work (PLATINUM Tier)
1. **Action Solar** - 8 ATL contacts (enriched today)
2. **Solar States** - needs enrichment
3. **Carbon Recall Kalispell** - needs enrichment
4. **ECC Energy** - needs enrichment

---

## Key Files Modified Today

```
backend/sync_close_to_star_schema.py   # Added map_close_status_to_stage()
supabase/migrations/007_star_schema_views.sql  # Updated exclusion lists
dashboard/src/components/dashboard/BDRWorkQueue.tsx
dashboard/src/components/dashboard/RecentActivity.tsx
```

---

## Commands for Tomorrow

```bash
# Start fresh
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
source venv/bin/activate

# Re-sync Close CRM data
python backend/sync_close_to_star_schema.py --limit 500 --days 90

# Check current stage distribution
curl -s "https://oyyakkuvvtckocncuwwf.supabase.co/rest/v1/dim_companies?select=current_stage" \
  -H "apikey: $SUPABASE_SERVICE_KEY" | python3 -c "import sys,json; from collections import Counter; d=json.load(sys.stdin); print(Counter(x['current_stage'] for x in d))"

# Refresh materialized views
curl -X POST "https://oyyakkuvvtckocncuwwf.supabase.co/rest/v1/rpc/refresh_star_schema_views" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Content-Type: application/json" -d '{}'

# Check top leads
curl -s "https://oyyakkuvvtckocncuwwf.supabase.co/rest/v1/mv_bdr_work_queue?select=company_name,icp_tier,recommended_action&limit=20" \
  -H "apikey: $SUPABASE_SERVICE_KEY"
```

---

## Notes

- Close CRM writes still DISABLED for safety
- Hunter.io working well for contact discovery
- Dashboard deployed at Vercel, auto-refreshes every 60s
- Supabase project: `oyyakkuvvtckocncuwwf` (different from dealer-scraper!)
