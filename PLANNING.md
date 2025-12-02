# sales-agent - Architecture & Planning

**Last Updated**: 2025-12-02

---

## Tech Stack

Python 3.11 | FastAPI | PostgreSQL | Redis | Supabase | Cerebras | LangGraph | Browserbase

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
