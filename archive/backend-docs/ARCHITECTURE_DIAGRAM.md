# Dealer Scraper → Sales Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEALER-SCRAPER-MVP PROJECT                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│  Carrier Scraper  │  │  Generac Scraper  │  │  Enphase Scraper  │
│                   │  │                   │  │                   │
│  - Parse dealers  │  │  - Parse dealers  │  │  - Parse dealers  │
│  - Extract data   │  │  - Extract data   │  │  - Extract data   │
│  - Normalize      │  │  - Normalize      │  │  - Normalize      │
└─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
          │                      │                      │
          │  Contractors[]       │  Contractors[]       │  Contractors[]
          │  Contacts[]          │  Contacts[]          │  Contacts[]
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Celery Task (tasks.py)│
                    │                        │
                    │  push_scrape_results_  │
                    │  to_sales_agent()      │
                    │                        │
                    │  - Batch contractors   │
                    │  - Batch contacts      │
                    │  - HTTP POST           │
                    └───────────┬────────────┘
                                │
                                │ HTTP POST
                                │ /api/v1/scraper/contractors
                                │ /api/v1/scraper/contacts
                                ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          SALES-AGENT PROJECT                                │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌────────────────────────┐
                    │  FastAPI Server        │
                    │  (Port 8001)           │
                    │                        │
                    │  sync_from_scraper.py  │
                    └───────────┬────────────┘
                                │
                    ┌───────────┴────────────┐
                    │                        │
         ┌──────────▼──────────┐  ┌─────────▼─────────┐
         │ POST /contractors   │  │ POST /contacts     │
         │                     │  │                    │
         │ 1. Load existing    │  │ 1. Load existing   │
         │    companies        │  │    companies       │
         │                     │  │                    │
         │ 2. Build lookup     │  │ 2. Find matching   │
         │    maps:            │  │    company         │
         │    - normalized_name│  │                    │
         │    - phone          │  │ 3. Check if        │
         │    - domain         │  │    contact exists  │
         │                     │  │    - (co_id, email)│
         │ 3. For each record: │  │    - (co_id, phone)│
         │    - Match existing │  │                    │
         │    - Merge OEM      │  │ 4. INSERT/UPDATE   │
         │      brands         │  │    contact         │
         │    - UPDATE or      │  │                    │
         │      INSERT         │  │ 5. Log to audit    │
         │                     │  │                    │
         │ 4. Log to audit     │  └────────┬───────────┘
         │                     │           │
         └──────────┬──────────┘           │
                    │                      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │  Supabase PostgreSQL   │
                    │                        │
                    │  dim_companies         │
                    │  - company_id (PK)     │
                    │  - company_name        │
                    │  - normalized_name     │
                    │  - phone               │
                    │  - domain              │
                    │  - oem_brands[]        │
                    │  - source_scraper      │
                    │                        │
                    │  dim_contacts          │
                    │  - contact_id (PK)     │
                    │  - company_id (FK)     │
                    │  - full_name           │
                    │  - email               │
                    │  - phone               │
                    │  - is_decision_maker   │
                    │                        │
                    │  lead_audit_log        │
                    │  - company_name        │
                    │  - event_type          │
                    │  - session_id          │
                    │  - decision_data       │
                    │  - created_by          │
                    └────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEDUPLICATION LOGIC                               │
└─────────────────────────────────────────────────────────────────────────────┘

Contractors:
  ┌─────────────────────┐
  │ New Contractor      │
  │ - ABC HVAC          │
  │ - 555-123-4567      │
  │ - abchvac.com       │
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ Check Existing      │
  │ 1. normalized_name? │──YES──> UPDATE (merge brands)
  │ 2. phone?           │──YES──> UPDATE (merge brands)
  │ 3. domain?          │──YES──> UPDATE (merge brands)
  │ 4. No match?        │──YES──> INSERT (new company)
  └─────────────────────┘

Contacts:
  ┌─────────────────────┐
  │ New Contact         │
  │ - John Smith        │
  │ - john@abchvac.com  │
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │ Find Company        │
  │ by normalized_name  │
  └──────────┬──────────┘
             │
       Found?├──NO──> SKIP (log error)
             │
            YES
             │
             ▼
  ┌─────────────────────┐
  │ Check Existing      │
  │ 1. (co_id, email)?  │──YES──> UPDATE
  │ 2. (co_id, phone)?  │──YES──> UPDATE
  │ 3. No match?        │──YES──> INSERT (new contact)
  └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           OEM BRAND MERGING                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Existing: ["Carrier", "Trane"]
     +
New:      ["trane", "Lennox", "Carrier"]
     =
Result:   ["Carrier", "Trane", "Lennox"]  (case-insensitive dedup)

┌─────────────────────────────────────────────────────────────────────────────┐
│                           BATCH PROCESSING                                  │
└─────────────────────────────────────────────────────────────────────────────┘

dealer-scraper-mvp                   sales-agent API

┌────────────────┐
│ 10,000 records │
└────────┬───────┘
         │
    Split into 100
     batches of 100
         │
         ├──> Batch 1 (100)  ──> POST /contractors ──> Supabase
         │                         (2-3 seconds)
         ├──> Batch 2 (100)  ──> POST /contractors ──> Supabase
         │                         (2-3 seconds)
         ├──> Batch 3 (100)  ──> POST /contractors ──> Supabase
         │                         (2-3 seconds)
         └──> ...
              (parallel processing via Celery group)

Total time: ~5 minutes for 10,000 records (vs. 3+ hours for sequential)

┌─────────────────────────────────────────────────────────────────────────────┐
│                           MONITORING & OBSERVABILITY                        │
└─────────────────────────────────────────────────────────────────────────────┘

1. API Logs (FastAPI)
   ─────────────────
   backend/logs/sales-agent.log
   - Request/response logging
   - Error tracking
   - Performance metrics

2. Audit Log (Supabase)
   ────────────────────
   lead_audit_log table
   - Every insert/update
   - Batch tracking
   - Source tracking

3. Status Endpoint
   ───────────────
   GET /api/v1/scraper/status
   - Last sync timestamp
   - Total contractors synced
   - Total contacts synced
   - Last batch ID

4. Swagger UI
   ──────────
   http://localhost:8001/api/v1/docs#/dealer-scraper
   - Interactive API testing
   - Request/response schemas
   - Try it out feature
```

---

## Component Responsibilities

### dealer-scraper-mvp
- Scrape dealer locators
- Extract contractor/contact data
- Normalize company names
- Push to sales-agent via HTTP

### sales-agent API
- Receive batches via FastAPI
- Deduplicate companies
- Merge OEM brands
- Link contacts to companies
- Log all imports

### Supabase
- Store companies (dim_companies)
- Store contacts (dim_contacts)
- Track audit log (lead_audit_log)

---

## Error Handling Flow

```
dealer-scraper-mvp                   sales-agent API
       │                                    │
       │ POST /contractors                  │
       ├───────────────────────────────────>│
       │                                    │
       │                           ┌────────▼────────┐
       │                           │ Validate        │
       │                           │ - Required      │
       │                           │   fields?       │
       │                           └────────┬────────┘
       │                                    │
       │                              Valid?├──NO──> 422 Validation Error
       │                                    │
       │                                   YES
       │                                    │
       │                           ┌────────▼────────┐
       │                           │ Process Batch   │
       │                           │ - Some succeed  │
       │                           │ - Some fail     │
       │                           └────────┬────────┘
       │                                    │
       │                           ┌────────▼────────┐
       │<──────────────────────────┤ Return Result   │
       │  200 OK (partial_success) │ - inserted: 8   │
       │                           │ - updated: 1    │
       │                           │ - skipped: 1    │
       │                           │ - errors: [...]  │
       │                           └─────────────────┘
       │
       ├──> Log errors
       ├──> Retry failed records (optional)
       └──> Continue processing
```
