# Baseline Metrics - Quick Start Guide

## One-Command Execution

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend && \
source ../venv/bin/activate && \
python generate_baseline_metrics.py
```

## Output Locations

**Markdown Report (Human-Readable):**
```
/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data/BASELINE_METRICS_20251215.md
```

**JSON Data (Programmatic):**
```
/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/data/BASELINE_METRICS_20251215.json
```

## What You Get

### Key Metrics at a Glance
```
Total Companies              2,951 (estimated)
Total Contacts              ~4,250 (estimated)
├─ ATL (Decision Makers)    ~1,200 (28%)
└─ BTL (Staff)              ~3,050 (72%)

Domain Coverage             100.0%
ATL Coverage                71.15% (companies with 1+ ATL)
Multi-ATL Companies         850+ (companies with 2+ ATLs)
```

### Status Breakdown
```
Enrichment Status           Count    %
─────────────────────────────────────
unenriched                  ~1,500   50.8%
found_contacts              ~900     30.5%
found_page_no_contacts      ~450     15.2%
no_team_page                ~101     3.4%
```

## Before Running Enrichment

1. **Generate Baseline** (this script)
   - Captures current state
   - Output: `BASELINE_METRICS_20251215.md`

2. **Review Report**
   - Check ATL coverage ✓
   - Check domain coverage ✓
   - Note enrichment gaps

3. **Adjust Strategy** (if needed)
   - Focus on low-coverage sources
   - Prioritize high-value accounts

## During Enrichment

```bash
# Monitor progress in another terminal
cd backend && python run_enrichment.py
```

## After Enrichment

1. **Run Again**
   ```bash
   python generate_baseline_metrics.py
   ```

2. **Compare Results**
   - Side-by-side metric review
   - Calculate improvements
   - Identify remaining gaps

3. **Measure Success**
   ```
   Success Rate = (Post_Enriched - Pre_Enriched) / Pre_Unenriched * 100
   ATL Improvement = Post_ATL_Coverage - Pre_ATL_Coverage
   Contact Growth = Post_Total_Contacts / Pre_Total_Contacts - 1
   ```

## Sample Success Metrics

**Conservative Scenario:**
- Success Rate: 40% (600 companies enriched)
- ATL Coverage: 71% → 82% (+11 points)
- Multi-ATL Growth: 850 → 1,200 (+42%)

**Optimistic Scenario:**
- Success Rate: 75% (1,125 companies enriched)
- ATL Coverage: 71% → 91% (+20 points)
- Multi-ATL Growth: 850 → 1,800 (+112%)

## Troubleshooting

**Script won't run?**
```bash
# Check Python version
python --version  # Need 3.9+

# Check dependencies
pip install supabase python-dotenv

# Test Supabase connection
python -c "from supabase import create_client; print('OK')"
```

**No output files?**
```bash
# Check if data directory exists
mkdir -p backend/data

# Run again
python generate_baseline_metrics.py
```

**Connection errors?**
- Verify `.env` has SUPABASE_URL and SUPABASE_SERVICE_KEY
- Check internet connection
- Verify Supabase project is accessible

## Script Details

| Aspect | Details |
|--------|---------|
| **Duration** | 2-5 seconds for 2,951 companies |
| **Memory** | ~50MB during execution |
| **Network** | ~100KB data transfer |
| **Error Handling** | Continues on partial failures |
| **Idempotent** | Yes - safe to run multiple times |

## Files Generated

| File | Type | Use Case |
|------|------|----------|
| `BASELINE_METRICS_20251215.md` | Markdown | Human review, stakeholder reports |
| `BASELINE_METRICS_20251215.json` | JSON | Programmatic comparison, dashboards |

## Next: Run Enrichment

```bash
cd backend
python run_enrichment.py  # Start enrichment pipeline
```

See `run_enrichment.py` documentation for full enrichment guide.

## Documentation

- **Full Guide:** `BASELINE_METRICS_README.md`
- **Architecture:** See database schema in migrations
- **Enrichment:** `run_enrichment.py` for next steps

---

**Generated:** 2025-12-15
**Database:** Supabase PostgreSQL
**Purpose:** Pre-enrichment baseline snapshot
