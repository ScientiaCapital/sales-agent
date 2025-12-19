# sales-agent - Architecture & Planning

**Last Updated**: 2025-12-18

---

## Tech Stack

Python 3.11 | FastAPI | PostgreSQL | Redis | Supabase | Cerebras | LangGraph | Browserbase | Chart.js

---

## Architecture Overview

### Data Flow
```
Supabase dim_companies → Interactive Enrichment (5 at a time) → Supabase sync
                                      ↓
                          Terminal batch processing
```

### Pipeline Stages
| Stage | Script | Output |
|-------|--------|--------|
| 1. ICP Scoring | `create_gold_standard_lists.py` | Scored leads by tier |
| 2. Interactive Enrichment | `run_enrichment.py` | Phone/email/ATL extraction |
| 3. Batch Enrichment (alt) | `batch_scrape_runner.py` | Same with CSV input |
| 4. Supabase Sync | (automatic) | Updates dim_companies, dim_contacts |

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| LangGraph Agents | AI-powered lead processing | `backend/app/services/langgraph/agents/` |
| Enrichment Runner | Interactive batch scraper | `backend/run_enrichment.py` |
| Lead Scorer | ICP scoring algorithm | `backend/create_gold_standard_lists.py` |
| Hunter.io Enrichment | Contact discovery (paid) | `backend/enrich_gold_standard_batch.py` |
| Supabase Sync | Data warehouse sync | `backend/sync_gold_standard_to_supabase.py` |

### Active Scripts (14 files kept in `/backend/`)

| Script | Purpose |
|--------|---------|
| `run_enrichment.py` | **MAIN** - Interactive 5-at-a-time enrichment |
| `batch_scrape_runner.py` | Alternative batch runner |
| `create_gold_standard_lists.py` | ICP scoring |
| `enrich_gold_standard_batch.py` | Hunter.io enrichment |
| `sync_gold_standard_to_supabase.py` | Supabase sync |
| `cleanup_output_files.py` | Archive old files |

### Archived Scripts (49 files in `/backend/archive/`)

| Folder | Count | Contents |
|--------|-------|----------|
| `archive/tests/` | 10 | Test/debug scripts |
| `archive/voice_ai/` | 6 | RunPod/voice AI scripts |
| `archive/old_enrichment/` | 7 | Superseded enrichment pipelines |
| `archive/old_linkedin/` | 6 | Old LinkedIn scrapers |
| `archive/one_off_tools/` | 20 | One-time utility scripts |

---

## Data Architecture (Supabase Star Schema)

### Source of Truth Tables
| Table | Purpose | Records |
|-------|---------|---------|
| `dim_companies` | Master lead list | 6,568 |
| `dim_contacts` | ATL/BTL contacts | 562 |

### Materialized Views
- `mv_icp_gold_leads` - Dashboard view
- `mv_bdr_work_queue` - Tim's prioritized tasks

### ICP Tiers
| Tier | Score Range | Meaning |
|------|-------------|---------|
| PLATINUM | 80+ | Best leads |
| GOLD | 65-79 | Strong leads |
| SILVER | 50-64 | Good leads |
| BRONZE | 35-49 | Working pipeline |

---

## Deep Scraper Architecture (Updated Dec 2)

### Technology
- **Browserbase**: Cloud browser automation (avoids bot detection)
- **Playwright**: Browser control
- **Sequential scraping**: 5 companies at a time (interactive)

### Pages Scraped Per Company
1. Landing page (homepage)
2. Team / Meet-the-team pages (priority order)
3. About Us page
4. Service area pages (`/areas-served`, `/service-area`, etc.)
5. Contact page

### Data Extraction

**ATL Contacts (Decision Makers)**:
- Owner, Founder, CEO, President, VP, Director, GM

**BTL Contacts (Staff)**:
- Technician, Installer, Dispatcher, Coordinator, Estimator

**Extraction Methods**:
1. **Structured**: Cards with name + title (team page pattern)
2. **Text patterns**: "Founded by X", "Owner: X", "President: X"
3. **Quote attributions**: "- Name, Owner" format

**ICP Signals Extracted**:
- **Service Areas**: Cities served (company footprint indicator)
- **HVAC Brands**: 28 brands (Carrier, Trane, Lennox, etc.)
- **Services**: AC repair, maintenance plans, commercial HVAC

### False Positive Filtering
Skip words prevent detecting menu items as contacts:
- Navigation: schedule, now, call, today, quote
- Services: heating, cooling, installation, maintenance
- Legal: privacy, policy, terms, copyright

### Output Files
| File | Purpose |
|------|---------|
| `DEEP_SCRAPE_*.csv` | Full results |
| `DEEP_SCRAPE_*.json` | Detailed audit trail |
| `CLOSE_CRM_IMPORT_*.csv` | Tim's manual import |

---

## Key Patterns

### Check-Then-Insert (Supabase)
```python
existing = supabase.table('dim_companies').select('normalized_name').execute()
existing_map = {r['normalized_name'] for r in existing.data}
if normalized not in existing_map:
    # INSERT
else:
    # UPDATE
```

### Phone Classification
```python
def is_unique_direct(contact_phone, company_phone):
    c_norm = normalize_phone(contact_phone)
    co_norm = normalize_phone(company_phone)
    return c_norm and c_norm != co_norm
```

### Phone Audit Trail
```python
if phone in existing_phones:
    audit_status = 'VERIFIED'  # Confirmed existing
else:
    audit_status = 'NEW'       # Discovered new
```

### Lead Scoring
```
Unique direct phone   +100 pts
Confirmed email       +50 pts
Website/domain        +30 pts
High ATL ratio        +20 pts
Company phone         +10 pts
+ ICP score (0-100)
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- API keys in `.env` only, never hardcoded
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)
- 1 company = 1 lead - Don't inflate counts with multiple contacts
- **Manual import only** - Review `CLOSE_CRM_IMPORT_*.csv` before importing

---

## Architecture Decision Records

### ADR-001: Supabase Star Schema
- **Date**: 2025-11-29
- **Decision**: Use star schema with dim_companies and dim_contacts
- **Rationale**: Enables fast dashboard queries via materialized views

### ADR-002: Check-Then-Insert Pattern
- **Date**: 2025-11-29
- **Decision**: Fetch existing records before insert, not upsert
- **Rationale**: Supabase upserts fail silently on unique constraint violations

### ADR-003: Cerebras for AI
- **Date**: 2025-11-20
- **Decision**: Use Cerebras (633ms avg) instead of OpenAI
- **Rationale**: Cost-effective, fast, NO OpenAI policy

### ADR-004: Browserbase for Scraping
- **Date**: 2025-12-01
- **Decision**: Use Browserbase for website scraping instead of direct HTTP
- **Rationale**: Cloud browsers avoid bot detection, handle JavaScript-heavy sites

### ADR-005: Manual Close CRM Import
- **Date**: 2025-12-01
- **Decision**: Export CSV for manual import, no auto-push to Close
- **Rationale**: Tim reviews leads before adding to CRM, avoids data quality issues

### ADR-006: Supabase RLS Security Hardening
- **Date**: 2025-12-01
- **Decision**: Enable Row Level Security on all 14 public tables
- **Rationale**: 113 Supabase audit issues identified - 40-50 critical security issues (missing RLS policies) fixed in migration 015
- **Migrations Created**:
  - `015_enable_rls_security.py` - Enables RLS on 14 tables, adds service role policies
  - `016_add_star_schema_performance_indexes.py` - Performance indexes (JSONB GIN, composite)
  - `009_consolidate_duplicate_policies.sql` - Removes duplicate RLS policies
- **Impact**: Protects dim_companies, dim_contacts, fact_opportunities, re_enrich_queue from unauthorized access

### ADR-007: LinkedIn Enrichment Pipeline with Browserbase Session Pool
- **Date**: 2025-12-01
- **Decision**: Create dedicated LinkedIn scraping pipeline with session pooling
- **Rationale**: Need LinkedIn employee data for ATL discovery, existing deep scraper only does website scraping
- **Components Created**:
  - `browserbase_session_pool.py` - Managed browser sessions with stealth mode
  - `parallel_linkedin_company_scraper.py` - Company /people/ page scraper
  - `parallel_linkedin_profile_scraper.py` - Personal profile URL finder
  - `sync_linkedin_to_supabase.py` - Syncs LinkedIn data to star schema
  - `run_linkedin_enrichment.py` - Full pipeline orchestrator
- **Security**: API key exposure fixed in 4 files (never construct URL with API key)
- **Rate Limits**: 30 companies/hr, 10 profiles/hr (conservative)

### ADR-008: Enhanced ICP Signal Extraction (Service Areas + Brands)
- **Date**: 2025-12-02
- **Decision**: Extend deep scraper to capture service areas and HVAC brand partnerships
- **Rationale**: Service areas indicate company footprint/scale; HVAC brands indicate established contractor status
- **New Extractions**:
  - **Service Areas**: Cities served from `/service-area`, `/areas-we-serve` pages
  - **HVAC Brands**: 28 brands detected (Carrier, Trane, Lennox, Bryant, etc.)
  - **BTL Contacts**: Technicians/installers captured alongside ATL decision makers
  - **Owner Quotes**: "- Name, Owner" attribution patterns from message sections
- **False Positive Filtering**: Expanded skip_words to filter menu items, service terms, legal text
- **Impact**: Better ICP qualification - contractors serving 50+ cities with multiple brand partnerships = larger operations

### ADR-009: Comprehensive OEM Brand Coverage (100+ brands)
- **Date**: 2025-12-02 (Evening)
- **Decision**: Massively expand brand detection to cover full Coperniq ICP across all verticals
- **Rationale**: Coperniq serves HVAC, solar, storage, and EV charging contractors - need to identify dealers in all verticals
- **Brand Categories Added**:
  - **Solar Inverters (Resi)**: Enphase IQ7/IQ8, SolarEdge, Hoymiles, APsystems
  - **Solar Inverters (Commercial)**: SMA Sunny Tripower, Fronius Eco, Sungrow, Huawei
  - **Battery Storage (Resi)**: Tesla Powerwall, Generac PWRcell, Enphase IQ, Sonnen, FranklinWH
  - **Battery Storage (Commercial)**: Tesla Megapack, BYD Commercial, Fluence, Powin
  - **EV Chargers (Resi)**: ChargePoint Home, JuiceBox, Wallbox Pulsar, Grizzl-E
  - **EV Chargers (Commercial)**: ABB Terra, Tritium, Kempower, Blink
  - **VRF/Commercial HVAC**: Daikin VRV, Mitsubishi City Multi, LG Multi V, Samsung DVM
  - **Generators**: Generac, Kohler, Cummins, Briggs & Stratton
- **Maintenance Plans Extraction**: Detects membership/subscription names (Comfort Club, Service Agreement, etc.) for BDR openers
- **Impact**: Full-spectrum contractor identification for Coperniq intelligence layer

### ADR-010: FREE Website Enrichment with VLM Fallback
- **Date**: 2025-12-13
- **Decision**: Create FREE BeautifulSoup-based website scraping with VLM fallback for JS-heavy sites
- **Rationale**: Need to enrich 3,320 companies with websites without expensive Browserbase costs
- **Components Created**:
  - `beautifulsoup_team_scraper.py` - FREE ATL extraction from team/about pages
  - `website_content_scraper.py` - Landing page content and signal detection
  - `vlm_website_analyzer.py` - Qwen 2.5 VL screenshot analysis via OpenRouter
  - `url_validator.py` - SSRF protection for all scrapers
- **LangGraph Tools**: 4 new tools added to `website_scraping_tools.py`
  - `scrape_company_team_tool` - Full scraping with Browserbase fallback
  - `scrape_website_content_tool` - Signal extraction (hiring, funding, tech stack)
  - `analyze_website_screenshot_tool` - VLM-powered screenshot analysis
  - `scrape_team_free_tool` - FREE BeautifulSoup-only scraping
- **VLM Integration**: `scientia-vlm-core` v0.1.0 installed from local repo
  - 3 model tiers: fast ($0.0003), balanced ($0.0008), best ($0.0015) per image
  - Circuit breaker + retry patterns for resilience
- **Cost Structure**:
  - BeautifulSoup: FREE
  - VLM (if needed): ~$0.0008/image for 30B model
  - Est. 3,320 sites @ 10% VLM fallback = ~$2.65 total
- **Impact**: Can enrich all 3,320 companies for under $3

### ADR-011: SSRF Protection for All Scrapers
- **Date**: 2025-12-13
- **Decision**: Add URL validation to prevent Server-Side Request Forgery attacks
- **Rationale**: Security audit identified critical SSRF vulnerability in all URL-accepting functions
- **Implementation**: `url_validator.py` with `validate_website_url()` function
- **Blocked Targets**:
  - Localhost and loopback addresses (127.0.0.1, ::1)
  - Private IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
  - Cloud metadata endpoints (169.254.169.254, metadata.google.internal)
  - File URLs and non-HTTP schemes
  - .local and .internal domain suffixes
- **DNS Resolution Check**: Validates resolved IP isn't private (prevents DNS rebinding)
- **Integration**: All scrapers call `validate_website_url()` before making requests
- **Impact**: Protects against SSRF attacks that could expose cloud credentials or internal services

### ADR-012: Company Deduplication & Prevention System
- **Date**: 2025-12-13
- **Decision**: Implement database-level deduplication with unique constraints and RPC functions
- **Rationale**: Found 62% duplicate rate in dim_companies (14,801 → 5,687 unique) due to lack of unique constraint
- **Implementation**:
  - `backend/supabase_deduplicate.py` - One-time cleanup script with batch processing
  - `supabase/migrations/025_prevent_duplicates.sql` - Prevention migration
  - `backend/app/services/company_dedup.py` - Python helper for safe upserts
- **Deduplication Priority**:
  1. Keep record with `close_lead_id` (linked to CRM)
  2. If tie: keep highest `icp_score`
  3. If tie: keep most recent `updated_at`
- **Prevention Components**:
  - `normalize_company_name()` - PostgreSQL function for name normalization
  - Trigger: Auto-populates `normalized_name` on INSERT/UPDATE
  - `UNIQUE INDEX` on `normalized_name` (partial, ignores NULL)
  - `upsert_company()` - RPC function for safe inserts
  - `sync_company_from_close()` - RPC function for Close CRM sync
- **Migration Order**:
  1. Run `supabase_deduplicate.py --execute` (one-time cleanup)
  2. Apply migration 025 (prevents future duplicates)
  3. Update sync scripts to use RPC functions
- **Impact**: Guarantees 1 company = 1 record, prevents duplicate accumulation

### ADR-013: SQLAlchemy Pool Configuration for Test Compatibility
- **Date**: 2025-12-18
- **Decision**: Make database pool parameters conditional based on database type (SQLite vs PostgreSQL)
- **Rationale**: Test collection failing with 7 errors - SQLite's SingletonThreadPool doesn't support `pool_size`, `max_overflow`, `pool_timeout` parameters
- **Implementation**: `backend/app/models/database.py`
  - Added `IS_SQLITE` check based on `DATABASE_URL` prefix
  - SQLite: Uses `SingletonThreadPool` with `check_same_thread=False`
  - PostgreSQL: Uses `QueuePool` with full pooling parameters
  - Async engine disabled for SQLite with runtime error in `get_async_db()`
- **Impact**:
  - Test collection: 7 errors → 0 errors
  - Tests collecting: 976 tests
  - Tests passing: 739 (76%)

### ADR-014: Pydantic V1 to V2 Validator Migration
- **Date**: 2025-12-18
- **Decision**: Migrate Pydantic V1 validators to V2 patterns
- **Rationale**: Deprecation warnings appearing for V1-style `@validator` decorators
- **Files Updated**:
  - `backend/app/services/lead_scorer.py`: `@validator('*')` → `@model_validator(mode='after')`
  - `backend/app/services/agents/search_agent.py`: `@validator` → `@field_validator` + `@classmethod`
  - `backend/app/services/agents/analysis_agent.py`: Same pattern
- **V2 Patterns**:
  - Single field: `@field_validator('field_name')` + `@classmethod` + type hints
  - All fields: `@model_validator(mode='after')` returning `self`
- **Impact**: Cleaner validator code, no deprecation warnings, V3 ready

### ADR-015: Port Standardization (8000)
- **Date**: 2025-12-18
- **Decision**: Standardize all backend port references to 8000
- **Rationale**: Mixed references to ports 8000 and 8001 causing connectivity issues
- **Files Updated**:
  - `dashboard/vite.config.ts` - Proxy target
  - `dashboard/.env.example` - API URL
  - Root `.env.example` - ngrok, LinkedIn, HubSpot callbacks
- **Impact**: Consistent backend connectivity across all environments
