# sales-agent - Current Tasks

**Last Updated**: 2025-12-01

---

## NEXT ACTION (Dec 2)

### Run Deep Scrape on 1,000 Companies

```bash
./run_deep_scrape.sh 1000
```

**Time**: ~8 hours
**Output**: `backend/data/final_enrichment_output/CLOSE_CRM_IMPORT_1000_*.csv`

**What it does**:
- Scrapes company websites (landing, team, about, contact pages)
- Extracts ATL names (CEO, Owner, President, VP, Director)
- Tracks phone audit trail (NEW vs VERIFIED)
- Creates Close CRM import file

---

## Active Work

### Completed (Dec 1)
| Task | Status |
|------|--------|
| Multi-source enrichment on 1,000 leads | DONE |
| Deep scraper with ATL extraction | DONE |
| Phone audit trail (NEW/VERIFIED) | DONE |
| Close CRM export format | DONE |
| Git commit and push | DONE |

### Up Next
| Task | Priority | Est. Time |
|------|----------|-----------|
| Run deep scrape on 1,000 companies | HIGH | 8 hours |
| Review `CLOSE_CRM_IMPORT_*.csv` | HIGH | 30 min |
| Manual import to Close CRM | HIGH | 1 hour |
| Run Hunter.io on ATL leads | MEDIUM | ~$10, 1 hour |

---

## Pipeline Outputs

**Location**: `backend/data/final_enrichment_output/`

| File | Purpose | Use |
|------|---------|-----|
| `CLOSE_CRM_IMPORT_*.csv` | Close CRM import | Tim reviews, imports manually |
| `DEEP_SCRAPE_*.csv` | Full scrape results | Analysis |
| `DEEP_SCRAPE_*.json` | Detailed audit trail | Debugging |
| `TOP_1000_PRIORITIZED_*.csv` | Daily caller list | Tim's call list |

---

## Quick Commands

```bash
# Activate environment
source venv/bin/activate

# DEEP SCRAPE (new - Dec 1)
./run_deep_scrape.sh 1000              # Full run (~8 hours)
./run_deep_scrape.sh 100               # Test (~1 hour)
./run_deep_scrape.sh 10                # Quick test (~15 min)

# Lead pipeline
python backend/create_gold_standard_lists.py      # ICP scoring
python backend/enrich_gold_standard_batch.py --batch 2  # Hunter.io
python backend/sync_gold_standard_to_supabase.py        # Sync to DB

# Cleanup
python backend/cleanup_output_files.py --dry-run
```

---

## Workflow: CSV to Close CRM

```
1. Run deep scrape
   ./run_deep_scrape.sh 1000

2. Review output
   - Open CLOSE_CRM_IMPORT_1000_*.csv in Excel
   - Check ATL Count column
   - Remove any bad data

3. Import to Close CRM
   - Close → Settings → Import
   - Upload cleaned CSV
   - Map columns to Close fields
```

---

## Blockers

- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`) - by design
- ATL extraction depends on websites having owner names visible (5-15% expected)

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- API keys in `.env` only
- Close CRM: export only, manual import
- 1 company = 1 lead
