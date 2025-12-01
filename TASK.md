# sales-agent - Current Tasks

**Last Updated**: 2025-12-01

---

## NEXT ACTION (Dec 2)

### 1. Add API Keys to .env

**Required keys** (see `API_KEYS_VALIDATION_REPORT.md`):
- CEREBRAS_API_KEY
- ANTHROPIC_API_KEY
- BROWSERBASE_API_KEY
- BROWSERBASE_PROJECT_ID
- HUNTER_API_KEY
- CLOSE_API_KEY
- SUPABASE_URL
- SUPABASE_SERVICE_KEY
- CRM_ENCRYPTION_KEY (already generated)

### 2. Deploy Supabase Migrations

```bash
cd backend
alembic upgrade head  # Apply migrations 015, 016, 009
```

**See**: `DEPLOYMENT_CHECKLIST_RLS_MIGRATION.md` for full deployment guide

### 3. Run LinkedIn Enrichment Pipeline (NEW)

```bash
cd backend
python run_linkedin_enrichment.py --limit 100  # Test with 100
./run_linkedin_scrape.sh 1000                  # Full run
```

**Time**: ~4-5 hours for 1000 companies
**Output**: LinkedIn URLs + ATL employees synced to Supabase

**What it does**:
- Scrapes LinkedIn company /people/ pages
- Extracts employees with ATL classification
- Searches for personal LinkedIn profiles
- Syncs all data to dim_companies and dim_contacts

### 4. Run Deep Scrape on 1,000 Companies

```bash
./run_deep_scrape.sh 1000
```

**Time**: ~2-4 hours (revised from 8 hours)
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
| **Phase 3: LinkedIn Enrichment Pipeline** | |
| Browserbase session pool with stealth mode | DONE |
| Parallel LinkedIn company scraper | DONE |
| Parallel LinkedIn profile scraper | DONE |
| Supabase sync for LinkedIn data | DONE |
| Orchestrator script (run_linkedin_enrichment.py) | DONE |
| Security audit - API key exposure fix (4 files) | DONE |
| All print() replaced with logger | DONE |
| **Phase 1: Infrastructure Setup** | |
| Supabase CLI installed and linked | DONE |
| Docker infrastructure (PostgreSQL, Redis, Neo4j) | DONE |
| All 113 Supabase issues categorized | DONE |
| API key validation report created | DONE |
| Code quality baseline (96.5/100) | DONE |
| Deep scrape code review (70% ready) | DONE |
| **Phase 2: Security & Database Fixes** | |
| Migration 015: RLS enabled on 14 tables | DONE |
| Migration 016: Performance indexes created | DONE |
| Migration 009: Duplicate policies consolidated | DONE |
| Fixed 40-50 of 113 Supabase issues | DONE |
| Created deployment checklists | DONE |
| PgAdmin email configuration fixed | DONE |
| **Previous Work** | |
| Multi-source enrichment on 1,000 leads | DONE |
| Deep scraper with ATL extraction | DONE |
| Phone audit trail (NEW/VERIFIED) | DONE |
| Close CRM export format | DONE |
| Git commit and push | DONE |

### Up Next (Dec 2)
| Task | Priority | Est. Time |
|------|----------|-----------|
| Add API keys to .env | HIGH | 15 min |
| Deploy Supabase migrations (015, 016, 009) | HIGH | 30 min |
| Test migrations and verify RLS | HIGH | 30 min |
| Run deep scrape on 1,000 companies | HIGH | 2-4 hours |
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
