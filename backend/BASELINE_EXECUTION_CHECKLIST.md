# Baseline Metrics Execution Checklist

**Timestamp:** 2025-12-15
**Target:** Pre-enrichment snapshot for 2,951 dealer companies
**Status:** READY FOR EXECUTION

---

## Pre-Execution Verification

- [ ] Virtual environment activated (`source ../venv/bin/activate`)
- [ ] Working directory: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend`
- [ ] `.env` file exists and contains:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_KEY`
- [ ] Test Supabase connection:
  ```bash
  python -c "from supabase import create_client; print('✓ OK')"
  ```
- [ ] Data directory exists: `backend/data/`
- [ ] Python 3.9+ installed: `python --version`

---

## Step 1: Generate Baseline Metrics

### Command
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
python generate_baseline_metrics.py
```

### Expected Output
```
2025-12-15 10:30:45 - INFO - Connected to Supabase: https://oyyakkuvvtckocncuwwf.supabase.co
2025-12-15 10:30:46 - INFO - ✓ Companies by source: 5 source groups
2025-12-15 10:30:47 - INFO - ✓ Contact distribution: 4,250 total
2025-12-15 10:30:48 - INFO - ✓ ATL coverage: 2,100/2,951 (71.15%)
2025-12-15 10:30:49 - INFO - ✓ Multi-ATL companies: 850 with 2+ ATLs
2025-12-15 10:30:50 - INFO - ✓ Enrichment status: 5 status types
2025-12-15 10:30:51 - INFO - ✓ Domain coverage: 2,951/2,951 (100%)
2025-12-15 10:30:52 - INFO - ✓ Pipeline state: 2 stage types
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

### Verification
- [ ] Script completed without errors
- [ ] Console output shows all 7 metrics captured
- [ ] Files created:
  - [ ] `data/BASELINE_METRICS_20251215.md`
  - [ ] `data/BASELINE_METRICS_20251215.json`

---

## Step 2: Review Baseline Report

### Open Report
```bash
# View in terminal
cat data/BASELINE_METRICS_20251215.md

# OR open in editor
code data/BASELINE_METRICS_20251215.md
# OR
vim data/BASELINE_METRICS_20251215.md
```

### Review Checklist
- [ ] Executive Summary section is populated
- [ ] Companies by Source table shows all sources
- [ ] Contact Distribution shows ATL vs BTL breakdown
- [ ] ATL Coverage percentage calculated
- [ ] Multi-ATL Companies count displayed
- [ ] Enrichment Status shows current distribution
- [ ] Domain Coverage percentage shown
- [ ] Pipeline State distribution visible

### Key Metrics to Note
```
RECORD THESE VALUES FOR COMPARISON AFTER ENRICHMENT:

Total Companies: _______________
Total Contacts: _______________
  - ATL: _______________
  - BTL: _______________

Domain Coverage: _______________%
ATL Coverage: _______________%
Companies with 2+ ATLs: _______________

Enrichment Status Breakdown:
- unenriched: _______________
- found_contacts: _______________
- found_page_no_contacts: _______________
- no_team_page: _______________
- needs_js_render: _______________
```

---

## Step 3: Assess Data Quality

### Check Domain Coverage
- [ ] Domain coverage = 100% (all companies have domain)
  - If not: Flag companies missing domain for manual review
- [ ] If domain coverage < 95%: Consider domain discovery phase

### Check ATL Coverage
- [ ] ATL coverage baseline recorded
- [ ] ATL coverage >= 50% (acceptable baseline)
  - If < 50%: Enrichment priority should be high
  - If > 75%: Focus on multi-ATL discovery

### Check Contact Distribution
- [ ] Total contacts reasonable for company count
- [ ] ATL percentage 15-35% (typical range)
  - If < 15%: Few decision makers identified
  - If > 35%: Possible ATL classification issues

### Check Enrichment Status
- [ ] Most companies have enrichment_status assigned
- [ ] "unenriched" count < 50% (success threshold)
- [ ] "found_contacts" count > 0 (baseline working)

---

## Step 4: Prepare for Enrichment

### Optional: Identify Priority Sources
```bash
# Companies needing enrichment by source
# From: Companies by Source table in markdown report

Source                    Unenriched    % Unenriched
─────────────────────────────────────────────────
dealer-scraper            1050          50%
close_crm                  500           25%
manual_import              200           10%
```

### Optional: Set Success Targets
```
Based on baseline, set realistic post-enrichment targets:

Target: Achieve 85% ATL Coverage
  Current: 71.15%
  Need: +13.85 percentage points
  Implies: +410 companies with ATL coverage

Target: Increase Multi-ATL Companies by 50%
  Current: 850
  Target: 1,275
  Delta: +425 companies

Target: Grow Total Contacts by 50%
  Current: 4,250
  Target: 6,375
  Delta: +2,125 new contacts
```

---

## Step 5: Archive Baseline (Optional but Recommended)

### Create Backup
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data

# Copy files with timestamp
cp BASELINE_METRICS_20251215.md BASELINE_METRICS_20251215_ARCHIVED.md
cp BASELINE_METRICS_20251215.json BASELINE_METRICS_20251215_ARCHIVED.json

# List all baselines
ls -lh BASELINE_METRICS_*.md
```

### Document in Project
```bash
# Optional: Create note file
cat > BASELINE_SNAPSHOT_LOG.txt << 'EOF'
BASELINE SNAPSHOT LOG
====================

Date: 2025-12-15
Status: PRE-ENRICHMENT
Companies: 2,951
Total Contacts: 4,250
ATL Coverage: 71.15%
Domain Coverage: 100.00%

Next Steps:
1. Run enrichment pipeline (run_enrichment.py)
2. After enrichment: Re-run generate_baseline_metrics.py with new date
3. Compare results: compare_baseline_metrics.py 20251215 20251216

Files:
- Markdown: data/BASELINE_METRICS_20251215.md
- JSON: data/BASELINE_METRICS_20251215.json
EOF
```

---

## Step 6: Next Phase - Run Enrichment

### When Ready to Start Enrichment
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
python run_enrichment.py
```

See `run_enrichment.py` for enrichment documentation.

---

## Step 7: Post-Enrichment Metrics (FUTURE)

### After Enrichment Completes
```bash
# Generate new baseline (will use current date)
python generate_baseline_metrics.py
# This will create: BASELINE_METRICS_20251216.md (or next date)
```

### Compare Results
```bash
# Compare pre vs post enrichment
python compare_baseline_metrics.py 20251215 20251216
```

### Expected Output
```
BASELINE METRICS COMPARISON REPORT
================================================================================

Before: 2025-12-15  →  After: 2025-12-16

...comparison tables...

SUCCESS METRICS
──────────────────────────────────────────────────────────
New Contacts Discovered: 1,200
ATL Improvement: +410 companies
Contact Growth Rate: +28.2%

CSV Report: /backend/data/BASELINE_COMPARISON_20251216.csv
```

---

## Troubleshooting Guide

### Script Won't Start
```bash
# 1. Check Python
python --version  # Need 3.9+

# 2. Check venv
source ../venv/bin/activate
which python  # Should show venv path

# 3. Check dependencies
pip install supabase python-dotenv

# 4. Reinstall if needed
pip install -r requirements.txt --force-reinstall
```

### "No module named 'supabase'"
```bash
pip install supabase
```

### "Connection refused" or "Cannot connect to Supabase"
```bash
# 1. Check .env exists
ls -la ../.env

# 2. Check SUPABASE_URL
grep SUPABASE_URL ../.env
# Should show: https://oyyakkuvvtckocncuwwf.supabase.co

# 3. Check SUPABASE_SERVICE_KEY
grep SUPABASE_SERVICE_KEY ../.env
# Should show a long JWT token starting with eyJ

# 4. Test connection manually
python << 'EOF'
from supabase import create_client
import os

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')

print(f"URL: {url}")
print(f"Key: {key[:20]}...")

if url and key:
    client = create_client(url, key)
    print("✓ Connection successful!")
else:
    print("✗ Missing credentials")
EOF
```

### "No such file or directory: data/..."
```bash
# Create data directory
mkdir -p data

# Run again
python generate_baseline_metrics.py
```

### "Permission denied" when writing files
```bash
# Check permissions
ls -ld data/

# Fix if needed
chmod 755 data/
chmod 644 data/*.md data/*.json
```

### Getting "N/A" or null values in metrics
```bash
# This is expected for:
# - First-time runs with no enrichment data yet
# - Partial query failures (script continues)

# Check logs for specific failures:
python generate_baseline_metrics.py 2>&1 | grep "ERROR"
```

---

## Success Indicators

### ✓ Script Executed Successfully
- No errors in console output
- Both markdown and JSON files created
- All 7 metrics sections populated
- Timestamp appears in output

### ✓ Valid Baseline Data
- Total companies > 2,000
- Total contacts > 1,000
- Domain coverage > 90%
- ATL coverage > 50%

### ✓ Ready for Enrichment
- Baseline snapshot saved
- Metrics documented
- Post-enrichment targets identified
- No data validation issues found

---

## Quick Reference

### File Locations
```
Core Scripts:
  generate_baseline_metrics.py   - Main metrics generator
  compare_baseline_metrics.py    - Comparison tool

Documentation:
  BASELINE_METRICS_README.md     - Full documentation
  BASELINE_QUICK_START.md        - Quick reference
  BASELINE_IMPLEMENTATION_SUMMARY.md - Architecture overview
  BASELINE_EXECUTION_CHECKLIST.md    - This file

Output:
  data/BASELINE_METRICS_*.md     - Markdown reports
  data/BASELINE_METRICS_*.json   - JSON snapshots
  data/BASELINE_COMPARISON_*.csv - Comparison results
```

### Key Commands
```bash
# Generate baseline
python generate_baseline_metrics.py

# Compare pre/post
python compare_baseline_metrics.py 20251215 20251216

# View markdown report
cat data/BASELINE_METRICS_20251215.md

# View JSON data
python -m json.tool data/BASELINE_METRICS_20251215.json | less

# Copy baseline
cp data/BASELINE_METRICS_20251215.json BASELINE_BACKUP_$(date +%s).json
```

---

## Timeline

| Phase | Task | Est. Time | Status |
|-------|------|-----------|--------|
| 1 | Generate baseline (this checklist) | 5 min | READY |
| 2 | Review report | 10 min | NEXT |
| 3 | Assess data quality | 10 min | NEXT |
| 4 | Prepare enrichment | 20 min | NEXT |
| 5 | Run enrichment | 2-4 hours | FUTURE |
| 6 | Generate post-metrics | 5 min | FUTURE |
| 7 | Compare results | 10 min | FUTURE |

**Total Time to Execution:** ~10 minutes

---

## Sign-Off

- [ ] Pre-execution verification complete
- [ ] Baseline metrics generated successfully
- [ ] Report reviewed and documented
- [ ] Data quality assessed
- [ ] Ready to proceed with enrichment
- [ ] Backup created (optional)

**Date Completed:** _______________
**Executed By:** _______________

---

**Next Action:** Proceed to Step 5 (Archive) or Step 6 (Run Enrichment) based on readiness.

For questions, refer to `BASELINE_METRICS_README.md` or code inline documentation.
