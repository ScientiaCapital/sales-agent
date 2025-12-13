# sales-agent - Current Tasks

**Last Updated**: 2025-12-13

---

## CURRENT STATUS

| Metric | Count |
|--------|-------|
| Total Companies | 4,408 |
| With Websites | 3,320 |
| ATL Contacts | 476 |
| Legit ATLs | 469 |
| Companies with 2+ ATLs | 64 |
| Exported for Outreach | 15 |

---

## LATEST UPDATE (Dec 13 - Website Enrichment + VLM Integration)

### FREE Website Enrichment System - COMPLETE ✅

**The Problem**: Need to scrape 3,320 company websites for ATL contacts and signals without expensive Browserbase costs.

**The Solution**: BeautifulSoup-based FREE scraping with VLM fallback for JS-heavy sites.

| Component | File | Status |
|-----------|------|--------|
| BeautifulSoup Team Scraper | `app/services/beautifulsoup_team_scraper.py` | ✅ NEW |
| Website Content Scraper | `app/services/website_content_scraper.py` | ✅ NEW |
| VLM Website Analyzer | `app/services/vlm_website_analyzer.py` | ✅ NEW |
| URL Validator (SSRF Protection) | `app/services/url_validator.py` | ✅ NEW |
| LangGraph Tools | `app/services/langgraph/tools/website_scraping_tools.py` | ✅ UPDATED |

### New LangGraph Tools

| Tool | Purpose | Cost |
|------|---------|------|
| `scrape_company_team_tool` | ATL extraction (BS + Browserbase fallback) | FREE-$$ |
| `scrape_website_content_tool` | Landing page signals | FREE |
| `analyze_website_screenshot_tool` | VLM screenshot analysis (Qwen 2.5 VL) | ~$0.0008/img |
| `scrape_team_free_tool` | FREE BeautifulSoup-only scraping | FREE |

### VLM Integration (vlm-core)

Integrated `scientia-vlm-core` v0.1.0 for Vision Language Model analysis:
- Uses Qwen 2.5 VL via OpenRouter
- 3 model tiers: fast ($0.0003), balanced ($0.0008), best ($0.0015) per image
- Circuit breaker + retry patterns for resilience

### Security Hardening

**SSRF Protection** - All scrapers now validate URLs before making requests:
- Blocks: localhost, private IPs (192.168.x.x, 10.x.x.x)
- Blocks: Cloud metadata endpoints (169.254.169.254, metadata.google.internal)
- Blocks: File URLs, non-HTTP schemes

### Signal Detection (Website Content)

| Signal | Detection | Use Case |
|--------|-----------|----------|
| `is_hiring` | "we're hiring", "join our team" | Growth indicator |
| `has_funding` | "Series A", "raised $X" | Funded startup |
| `tech_stack` | Salesforce, AWS, React, etc. | Tech fit |
| `growth_indicators` | "Inc 5000", "fastest growing" | Success signals |

### Test Results

| Site | ATL Contacts | Hiring | Funding | Method |
|------|--------------|--------|---------|--------|
| linear.app | 20 | ✅ | ✅ | BeautifulSoup |
| stripe.com | 8 | ✅ | ✅ | BeautifulSoup |

### Next Steps (Tomorrow)

1. Run FREE enrichment on 3,320 companies with websites
2. Use VLM fallback for JS-heavy sites with no ATL results
3. Store signals in Supabase for agent context

---

## PREVIOUS UPDATE (Dec 8 - Signal-Based Outreach)

### Signal Detection System - COMPLETE ✅

**The Problem**: Drafts were being generated with ZERO context - no "why now", no signal, no strategy. Just spray-and-pray cold emails.

**The Solution**: Signal-aware draft generation that detects the context before writing.

| Component | File | Status |
|-----------|------|--------|
| SignalDetector Service | `app/services/outreach/signal_detector.py` | ✅ NEW |
| Signal-aware SalesIntelAgent | `app/services/langgraph/agents/sales_intel_agent.py` | ✅ UPDATED |
| Signal integration in AI outreach | `app/api/ai_outreach.py` | ✅ UPDATED |
| Database migration | `supabase/migrations/20251208_add_signal_columns.sql` | ✅ NEW |

### Signal Types

| Signal | Priority | Email Tone | When to Use |
|--------|----------|------------|-------------|
| `SQL_BOOKING` | 1 | booking | Sales Qualified - ready for demo |
| `REPLY` | 2 | followup | They responded - immediate follow-up |
| `OPPORTUNITY_PROGRESS` | 3 | deal_progression | Active opportunity - move deal forward |
| `SAL_FOLLOWUP` | 4 | followup_sequence | Sales Accepted - needs follow-up sequence |
| `NURTURE_REENGAGE` | 5 | reengagement | In nurture - checking back in |
| `STALE_LEAD` | 6 | reengagement | 90+ days since last contact |
| `COLD_NEW` | 7 | first_touch | Net new lead - first touch |

### New Database Columns (dim_ai_drafts)

```sql
signal_type TEXT           -- SQL_BOOKING, NURTURE_REENGAGE, etc.
signal_source TEXT         -- close_status, supabase_icp, activity_date
signal_reason TEXT         -- Human-readable "why now"
close_lead_status TEXT     -- Current Close CRM status
correspondence_summary TEXT -- Recent activity summary
```

### How It Works

1. **Before generating draft**: Signal detector checks Close CRM lead status + activity history
2. **Selects appropriate prompt**: SIGNAL_AWARE_PROMPT (contextual) vs SALES_INTEL_PROMPT (cold)
3. **Generates contextual draft**: Email tone, CTA, and content match the signal
4. **Stores signal with draft**: Full audit trail of why the draft was created

**Run migration**:
```bash
supabase db push
```

---

## PREVIOUS UPDATE (Dec 4 Evening)

### ICP Scoring + CRM Export Pipeline - COMPLETE

| Deliverable | Status | Location |
|-------------|--------|----------|
| Close CRM exclusion (5,926 leads) | DONE | Built into export scripts |
| Customer exclusion (63 Won deals) | DONE | Built into export scripts |
| ATL contact quality audit | DONE | 7 garbage filtered |
| FINAL_CLEAN export (15 co, 69 ATLs) | DONE | `backend/data/final_enrichment_output/` |
| TOP30_FINAL export (30 co, 30 ATLs) | DONE | `backend/data/final_enrichment_output/` |

**New Scripts Created**:
- `score_and_export_top30.py` - Main ICP scoring + export
- `export_hot_leads_top30.py` - Hot leads filter
- `export_non_close_hot_leads.py` - Close CRM exclusion logic

**Ready for CTO Import**:
```
CLOSE_CRM_IMPORT_FINAL_CLEAN_20251204.csv  <- 15 companies, 69 ATL contacts
```

---

## PREVIOUS UPDATE (Dec 2 Night)

### AI Command Center - COMPLETE
Full-stack AI outreach system merged to main:

| Component | Files | Status |
|-----------|-------|--------|
| Backend API | `backend/app/api/ai_outreach.py` (7 endpoints) | ✅ |
| Frontend | `dashboard/src/components/ai/` (3 components) | ✅ |
| Database | `supabase/migrations/20251202_*.sql` (2 migrations) | ✅ |
| Tests | `backend/tests/api/test_ai_outreach.py` (40 tests) | ✅ |

**Next**: Run Supabase migrations to create `dim_ai_drafts` table

---

## PREVIOUS UPDATE (Dec 2 Evening)

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
