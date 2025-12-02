# sales-agent - Current Tasks

**Last Updated**: 2025-12-02

---

## CURRENT STATUS

| Metric | Count |
|--------|-------|
| Total Companies | 8,889 |
| With Domains | 3,643 |
| Needing Enrichment | ~3,500 |
| Already Enriched | ~75 |

---

## LATEST UPDATE (Dec 2 Evening)

### Comprehensive OEM Brand Coverage (100+ brands)
The scraper now detects contractors across ALL Coperniq verticals:
- **HVAC**: Carrier, Trane, Lennox, Mitsubishi, Daikin, York, Goodman, etc.
- **Solar Inverters**: Enphase, SMA, Fronius, SolarEdge (resi vs commercial)
- **Battery Storage**: Tesla Powerwall/Megapack, Generac, BYD, Sonnen
- **EV Chargers**: ChargePoint, JuiceBox, ABB Terra, Tritium, Kempower
- **VRF Commercial**: Daikin VRV, Mitsubishi City Multi, LG Multi V
- **Generators**: Generac, Kohler, Cummins

### BDR Opener Gold - Maintenance Plans
Now extracts membership/subscription names:
- Comfort Club, Service Agreement, Maintenance Plan, Annual Tune-Up, VIP Program

### Additional Extractions
- **Service Areas** - Cities served (company footprint indicator)
- **BTL Contacts** - Technicians/staff alongside ATL decision makers
- **Owner Quotes** - "- Name, Owner" attribution patterns

### Output Format
```
OK 25s (1 ATL, 3 BTL, 2 ph, 5 svc, 36 areas, 11 brands, 2 plans)
```

---

## NEXT ACTION (Dec 2)

### Run Interactive Enrichment

```bash
cd backend
source ../venv/bin/activate
python run_enrichment.py
```

**What it does**:
- Pulls unenriched companies directly from Supabase
- Scrapes 5 companies at a time
- Extracts: ATL/BTL contacts, phones, emails, services, service areas, OEM brands (100+), maintenance plans
- Syncs results back to Supabase (dim_companies, dim_contacts)
- Saves failed companies to `FAILED_ENRICHMENT.csv` for troubleshooting
- Press Enter to continue, 'q' to quit

**Time**: ~2.5 minutes per batch of 5 (~27s per company)

**Est. Total**: ~3,500 companies / 5 per batch = 700 batches × 2.5 min = ~30 hours total
- Can run in sessions of 20-40 batches per day

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
