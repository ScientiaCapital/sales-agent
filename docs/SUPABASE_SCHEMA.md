# Supabase Schema Documentation

**Last Updated:** 2025-12-23
**Database:** PostgreSQL via Supabase
**Architecture:** Star Schema (dimensional modeling)

---

## Quick Reference

| Use Case | Primary Table | Key Columns |
|----------|--------------|-------------|
| Lead Storage | `dim_companies` | company_id, company_name, icp_score, icp_tier |
| Contact Storage | `dim_contacts` | contact_id, company_id, full_name, title, email |
| Activity Tracking | `fact_activities`, `fact_close_activities` | activity_type, direction, outcome |
| Enrichment Tracking | `fact_enrichments`, `fact_enrichment_attempts` | method, cost_usd, contacts_found |
| Website Crawling | `fact_website_content` | page_url, page_type, team_members_detected |
| Pipeline Stages | `fact_pipeline_stages` | from_stage, to_stage, changed_at |
| Audit Trail | `lead_audit_log` | event_type, stage, decision_data |

---

## Dimension Tables (Master Data)

### `dim_companies` - Master Lead List

**Purpose:** Single source of truth for all leads. All companies from dealer-scraper, Close CRM, manual imports, and VLM extraction go here.

**Key Columns:**
```
company_id          UUID PRIMARY KEY
company_name        VARCHAR(255) NOT NULL
normalized_name     VARCHAR(255)          -- Lowercase, no suffixes (for dedup)
domain              VARCHAR(255)          -- Website domain
website             VARCHAR(500)          -- Full URL
phone               VARCHAR(50)
street, city, state, zip                  -- Location
icp_score           INTEGER (0-100)       -- Lead score
icp_tier            VARCHAR(20)           -- PLATINUM, GOLD, SILVER, BRONZE
current_stage       VARCHAR(50)           -- Pipeline stage
close_lead_id       VARCHAR(100)          -- Close CRM ID
source_type         VARCHAR(50)           -- dealer_scraper, close_crm, manual
team_page_url       TEXT                  -- Discovered team page URL
enrichment_status   VARCHAR(50)           -- found_contacts, found_page_no_contacts, no_team_page
```

**ICP Signal Columns (HIGH VALUE - 10-15 points each):**
| Column | Description |
|--------|-------------|
| `has_design_build` | Design-build capability |
| `has_engineering` | In-house engineering/CAD |
| `has_medical_specialization` | Medical gas, healthcare |
| `has_building_automation` | BMS, controls, smart buildings |
| `has_oem_partnerships` | Carrier, Generac certified |
| `has_awards` | Industry recognition |
| `has_emergency_service` | 24/7 availability |

**Standard Signal Columns (5 points each):**
| Column | Description |
|--------|-------------|
| `has_generators` | Generator sales/service |
| `has_commercial` | Commercial projects |
| `has_industrial` | Industrial/manufacturing |
| `has_membership` | Maintenance plans |
| `has_specials` | Promotional offers |
| `has_financing` | Financing options |

---

### `dim_contacts` - People at Companies

**Purpose:** Contacts extracted from websites, Apollo, Hunter.io, VLM screenshots.

**Key Columns:**
```
contact_id          UUID PRIMARY KEY
company_id          UUID FK -> dim_companies
full_name           VARCHAR(255)
first_name          VARCHAR(100)
last_name           VARCHAR(100)
email               VARCHAR(255)
phone               VARCHAR(50)
title               VARCHAR(255)          -- Job title
is_atl              BOOLEAN               -- Above The Line (decision maker)
department          VARCHAR(100)
seniority           VARCHAR(50)
linkedin_url        VARCHAR(500)
confidence          INTEGER (0-100)       -- Confidence score
source              VARCHAR(50)           -- hunter, apollo, browserbase, vlm_screenshot, manual
validated           BOOLEAN               -- Email/phone validated
```

**Source Values:**
- `hunter` - Hunter.io API
- `apollo` - Apollo.io API
- `browserbase` - Playwright scraping (legacy)
- `vlm_screenshot` - VLM screenshot extraction (NEW - 80-90% accuracy)
- `manual` - Manual entry

---

### `dim_users` - Sales Team Members

**Purpose:** BDRs, AEs, Managers from Close CRM.

```
user_id             UUID PRIMARY KEY
close_user_id       VARCHAR(100)          -- Close CRM user ID
name                VARCHAR(255)
email               VARCHAR(255)
role                VARCHAR(50)           -- BDR, AE, Manager
```

---

### `dim_sources` - Data Origin Tracking

**Purpose:** Track where data came from for attribution.

```
source_id           UUID PRIMARY KEY
source_name         VARCHAR(100)          -- dealer-scraper, hunter-io, apollo, vlm-screenshot
source_type         VARCHAR(50)           -- scraper, crm, api, manual
project             VARCHAR(100)          -- Origin project
```

---

## Fact Tables (Events/Transactions)

### `fact_website_content` - Crawled Web Pages

**Purpose:** Store pages crawled by VLM pipeline for contact extraction.

```
content_id              UUID PRIMARY KEY
company_id              UUID FK -> dim_companies
page_url                VARCHAR(1000) NOT NULL
page_type               VARCHAR(50)           -- team, about, contact, homepage, other
page_title              VARCHAR(500)
extracted_text          TEXT
raw_html                TEXT
meta_description        TEXT
scrape_status           VARCHAR(20)           -- pending, success, failed
http_status_code        INTEGER
scraped_at              TIMESTAMP
ai_analyzed_at          TIMESTAMP
scrape_error            TEXT
team_members_detected   JSONB                 -- VLM extraction results
services_detected       JSONB
hiring_signals          JSONB
tech_stack_detected     JSONB
```

---

### `fact_enrichments` - Enrichment Attempts

**Purpose:** Track every enrichment attempt for cost/ROI analysis.

```
enrichment_id       UUID PRIMARY KEY
company_id          UUID FK -> dim_companies
source_id           UUID FK -> dim_sources
method              VARCHAR(50)           -- hunter, apollo, browserbase, vlm_screenshot
contacts_found      INTEGER
atl_found           INTEGER
emails_found        INTEGER
cost_usd            DECIMAL(10,6)
latency_ms          INTEGER
success             BOOLEAN
error_message       TEXT
enriched_at         TIMESTAMP
```

---

### `fact_enrichment_attempts` - Detailed Attempt Tracking

**Purpose:** More detailed enrichment tracking with raw responses.

```
attempt_id          UUID PRIMARY KEY
company_id          UUID FK -> dim_companies
company_name        TEXT
domain              TEXT NOT NULL
source              TEXT NOT NULL         -- vlm_screenshot, apollo, hunter, etc.
session_id          TEXT                  -- Batch session ID
batch_id            UUID                  -- Batch job ID
contacts_found      INTEGER
atl_found           INTEGER
btl_found           INTEGER
emails_found        INTEGER
phones_found        INTEGER
cost_usd            DECIMAL
api_credits_used    INTEGER
latency_ms          INTEGER
success             BOOLEAN
error_message       TEXT
raw_response        JSONB                 -- Full API response
attempted_at        TIMESTAMP
created_at          TIMESTAMP
```

---

### `fact_activities` - Close CRM Activities

**Purpose:** Calls, emails, SMS, meetings synced from Close.

```
activity_id         UUID PRIMARY KEY
close_activity_id   VARCHAR(100)
company_id          UUID FK -> dim_companies
contact_id          UUID FK -> dim_contacts
user_id             UUID FK -> dim_users
activity_type       VARCHAR(50)           -- call, email, sms, meeting
direction           VARCHAR(20)           -- inbound, outbound
outcome             VARCHAR(100)          -- connected, voicemail, no_answer, meeting_booked
duration_seconds    INTEGER
subject             VARCHAR(500)
body_preview        TEXT
activity_at         TIMESTAMP
synced_at           TIMESTAMP
```

---

### `fact_pipeline_stages` - Stage Transitions

**Purpose:** Track every stage change for funnel analysis.

```
stage_change_id     UUID PRIMARY KEY
company_id          UUID FK -> dim_companies
from_stage          VARCHAR(50)           -- Previous stage (NULL if first)
to_stage            VARCHAR(50) NOT NULL  -- New stage
changed_by          UUID FK -> dim_users
changed_at          TIMESTAMP
```

---

## Audit & Tracking Tables

### `lead_audit_log` - Complete Audit Trail

**Purpose:** Every decision made about every lead for GTM agent context.

```
id                  UUID PRIMARY KEY
lead_id             UUID                  -- Optional FK
company_name        VARCHAR(255)          -- Denormalized for fast queries
session_id          VARCHAR(100)          -- Pipeline run ID
event_type          VARCHAR(50)           -- lead_imported, lead_qualified, dedup_*, etc.
stage               VARCHAR(50)           -- import, qualification, enrichment, etc.
decision_data       JSONB                 -- Score, sources, match reasons
source_file         VARCHAR(255)
source_row          INTEGER
cost_usd            DECIMAL(10,6)
latency_ms          INTEGER
created_by          VARCHAR(100)
created_at          TIMESTAMP
```

---

## GTM Use Case Mapping

| GTM Use Case | Tables Used | Query Pattern |
|--------------|-------------|---------------|
| **Lead Scoring** | `dim_companies` | Filter by icp_tier, icp_score, has_* signals |
| **Contact Enrichment** | `dim_contacts`, `fact_enrichment_attempts` | Join on company_id, track source |
| **Website Intelligence** | `fact_website_content` | Filter by scrape_status, page_type |
| **Activity Tracking** | `fact_activities`, `fact_close_activities` | Join on company_id, contact_id |
| **Pipeline Analysis** | `fact_pipeline_stages`, `lead_current_state` | Track stage transitions over time |
| **Cost Analysis** | `fact_enrichment_attempts` | Sum cost_usd by source, calculate ROI |
| **VLM Extraction** | `fact_website_content`, `dim_contacts` | Store team_members_detected, create contacts |

---

## Schema Gaps Identified

### For VLM Pipeline:
1. **VLM cost tracking** - Need to add `vlm_screenshot` to `dim_sources` seed data
2. **Screenshot storage** - Currently `/tmp/screenshots/` - consider Supabase Storage for persistence
3. **Crawl session tracking** - Could add `crawl_session_id` to group pages from same crawl

### For Full GTM:
1. **Opportunities** - `fact_opportunities` partially implemented, needs Close sync
2. **Campaign sequences** - GTME tables exist but not fully integrated
3. **A/B test tracking** - No dedicated table for outreach experiments

### Missing Indexes:
- `dim_contacts` could use composite index on (company_id, is_atl)
- `fact_website_content` could use index on (scrape_status, scraped_at)

---

## Migration Files

Located in `/supabase/migrations/`:

| Migration | Purpose |
|-----------|---------|
| `001_lead_audit_log.sql` | Audit trail |
| `002_dashboard_tables.sql` | Dashboard + alerts |
| `005_star_schema_dimensions.sql` | Core dimensions |
| `006_star_schema_facts.sql` | Fact tables |
| `20251213_add_team_page_tracking.sql` | VLM preparation |
| `20251222_add_high_value_signals.sql` | ICP signal columns |
| `20251222_add_standard_signals.sql` | Standard signals |

---

## Common Queries

### Find companies ready for VLM extraction:
```sql
SELECT company_id, company_name, website
FROM dim_companies
WHERE website IS NOT NULL
  AND enrichment_status IS NULL
  AND icp_tier IN ('PLATINUM', 'GOLD')
ORDER BY icp_score DESC
LIMIT 20;
```

### Get contact counts by source:
```sql
SELECT source, COUNT(*) as count, AVG(confidence) as avg_confidence
FROM dim_contacts
WHERE source IS NOT NULL
GROUP BY source
ORDER BY count DESC;
```

### Track enrichment costs:
```sql
SELECT source,
       COUNT(*) as attempts,
       SUM(cost_usd) as total_cost,
       SUM(contacts_found) as contacts,
       SUM(cost_usd) / NULLIF(SUM(contacts_found), 0) as cost_per_contact
FROM fact_enrichment_attempts
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY source;
```
