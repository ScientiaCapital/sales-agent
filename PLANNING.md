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

## Deep Scraper Architecture (NEW)

### Technology
- **Browserbase**: Cloud browser automation (avoids bot detection)
- **Playwright**: Browser control
- **Concurrent scraping**: 10 companies at once

### Pages Scraped Per Company
1. Landing page (homepage)
2. Team / Management page
3. About Us page
4. Contact page
5. LinkedIn company page (via Google search)

### ATL Extraction Methods
1. **Structured**: Cards with name + title
2. **Text patterns**: "Founded by X", "Owner: X", "President: X"

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
