# Sales Agent - Database Schema

**Generated**: 2025-12-18 | **Database**: Supabase PostgreSQL

---

## dim_companies

Primary lead/company table for sales pipeline.

| Column | Type | Description |
|--------|------|-------------|
| company_id | UUID | Primary key |
| company_name | TEXT | Company display name |
| normalized_name | TEXT | Lowercase normalized for dedup |
| domain | TEXT | Primary website domain |
| phone | TEXT | Main phone number |
| website | TEXT | Full website URL |
| street | TEXT | Street address |
| city | TEXT | City |
| state | TEXT | State abbreviation |
| zip | TEXT | ZIP/Postal code |
| **ICP Classification** | | |
| icp_score | INT | Score 0-100 (higher = better fit) |
| icp_tier | TEXT | GOLD, SILVER, BRONZE |
| is_service_based | BOOLEAN | Has service/maintenance revenue |
| is_multi_location | BOOLEAN | Multiple locations indicator |
| is_srec_state | BOOLEAN | Located in SREC state (NJ, MA, MD, DC, PA, IL) |
| **CRM Integration** | | |
| close_lead_id | TEXT | Close CRM lead ID |
| close_pushed_at | TIMESTAMPTZ | When pushed to Close |
| funnel_stage | TEXT | new, contacted, engaged, qualified, demo, proposal, closed_won, closed_lost, nurture |
| disposition | TEXT | Lead outcome reason |
| current_stage | TEXT | Legacy stage field |
| **Enrichment Tracking** | | |
| enrichment_status | TEXT | Enrichment status |
| last_enriched_at | TIMESTAMPTZ | Last enrichment timestamp |
| total_enrichment_cost_usd | DECIMAL | Cumulative enrichment cost |
| team_page_url | TEXT | Company team page for scraping |
| **AI Enrichment** | | |
| ai_enriched_at | TIMESTAMPTZ | AI analysis timestamp |
| ai_personal_hooks | JSONB | Personalization hooks |
| ai_company_story | TEXT | AI-generated company summary |
| ai_pain_points | JSONB | Identified pain points |
| ai_buying_signals | JSONB | Buying signals detected |
| ai_confidence | INT | AI analysis confidence |
| **Metadata** | | |
| original_source | TEXT | dealer-scraper-mvp, spw_solar_contractor, amicus_om, amicus_solar |
| source_type | TEXT | Source type category |
| first_seen_at | TIMESTAMPTZ | First import timestamp |
| created_at | TIMESTAMPTZ | Record creation |
| updated_at | TIMESTAMPTZ | Last update |

### Constraints

- `icp_tier`: CHECK (icp_tier IN ('GOLD', 'SILVER', 'BRONZE'))
- `funnel_stage`: CHECK (funnel_stage IN ('new', 'contacted', 'engaged', 'qualified', 'demo', 'proposal', 'negotiation', 'closed_won', 'closed_lost', 'nurture'))

---

## dim_contacts

Individual contacts associated with companies.

| Column | Type | Description |
|--------|------|-------------|
| contact_id | UUID | Primary key |
| company_id | UUID | FK to dim_companies |
| first_name | TEXT | First name |
| last_name | TEXT | Last name |
| full_name | TEXT | Combined name |
| title | TEXT | Job title |
| email | TEXT | Email address |
| phone | TEXT | Direct phone |
| department | TEXT | Department |
| seniority | TEXT | Seniority level |
| is_atl | BOOLEAN | Above-The-Line (decision maker) |
| linkedin_url | TEXT | LinkedIn profile |
| twitter_handle | TEXT | Twitter/X handle |
| **Enrichment** | | |
| source | TEXT | Data source |
| confidence | INT | Data confidence 0-100 |
| validated | BOOLEAN | Email validated |
| **CRM Integration** | | |
| close_contact_id | TEXT | Close CRM contact ID |
| close_pushed_at | TIMESTAMPTZ | When pushed to Close |
| sequence_name | TEXT | Active sequence name |
| sequence_subscribed_at | TIMESTAMPTZ | Sequence subscription date |
| contact_status | TEXT | Contact status |
| **Engagement Metrics** | | |
| emails_sent | INT | Total emails sent |
| emails_opened | INT | Total opens |
| emails_clicked | INT | Total clicks |
| emails_replied | INT | Total replies |
| calls_made | INT | Total calls |
| last_contacted_at | TIMESTAMPTZ | Last outreach |
| **Metadata** | | |
| created_at | TIMESTAMPTZ | Record creation |
| updated_at | TIMESTAMPTZ | Last update |

---

## lead_events

Audit trail for lead lifecycle tracking.

| Column | Type | Description |
|--------|------|-------------|
| event_id | UUID | Primary key |
| company_id | UUID | FK to dim_companies |
| contact_id | UUID | FK to dim_contacts |
| event_type | TEXT | Event type (see values below) |
| event_source | TEXT | sales-agent, hunter_io, apollo, close_crm, manual, webhook |
| origination_source | TEXT | Lead origin (spw_solar_contractor, amicus_om, etc.) |
| origination_list | TEXT | List name (SPW, Amicus, Dealer) |
| close_lead_id | TEXT | Close lead ID |
| close_contact_id | TEXT | Close contact ID |
| close_sequence_id | TEXT | Close sequence ID |
| close_sequence_name | TEXT | Sequence name |
| funnel_stage | TEXT | Stage at event time |
| disposition | TEXT | Disposition at event time |
| cost_usd | DECIMAL | Event cost (enrichment) |
| revenue_usd | DECIMAL | Revenue (for closed_won) |
| metadata | JSONB | Additional event data |
| notes | TEXT | Notes |
| created_at | TIMESTAMPTZ | Event timestamp |
| created_by | TEXT | Creator (default: sales-agent) |

### Event Types

| event_type | Description |
|------------|-------------|
| scraped | Lead scraped from source |
| enriched_hunter | Hunter.io enrichment |
| enriched_apollo | Apollo enrichment |
| pushed_to_crm | Pushed to Close CRM |
| sequence_subscribed | Added to sequence |
| email_sent | Email sent |
| email_opened | Email opened |
| email_clicked | Link clicked |
| replied | Reply received |
| called | Call made |
| voicemail | Voicemail left |
| qualified | Qualified as opportunity |
| demo_scheduled | Demo booked |
| proposal_sent | Proposal sent |
| closed_won | Deal won |
| closed_lost | Deal lost |
| nurture_cold | Moved to cold nurture |
| nurture_hot | Moved to hot nurture |

---

## Record Counts (2025-12-18)

| Table | Count |
|-------|-------|
| dim_companies | 3,420 |
| dim_contacts | 12,278 |
| lead_events | 332 |

---

## Source Breakdown

| original_source | Description | Count (approx) |
|-----------------|-------------|----------------|
| dealer-scraper-mvp | Generator dealer network | 2,951 |
| spw_solar_contractor | Solar Power World list | 356 |
| amicus_om | Amicus O&M list | ~50 |
| amicus_solar | Amicus Solar list | ~50 |
| enrichment_recovery | Recovered from enrichment | varies |
| close_crm | Imported from Close | varies |

---

## ICP Scoring Logic

```
Score = base_score + modifiers

Base scores:
- pure_solar: 80
- solar_plus_generators: 90
- electrical_generators: 75
- generators_only: 70
- electrical_only: 50
- unknown: 30

Modifiers:
- service keyword: +5
- SREC state (NJ, MA, MD, DC, PA, IL): +10

Tier mapping:
- GOLD: score >= 85
- SILVER: score >= 70
- BRONZE: score < 70
```
