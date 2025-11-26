# Schema Mapping: dealer-scraper → sales-agent → Gold Standard List

**Author**: Tim Kipper | GTM Engineering
**Date**: November 26, 2025
**Purpose**: Single source of truth for data flow between projects

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA FLOW: RAW → GOLD STANDARD                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   DEALER-SCRAPER-MVP                    SALES-AGENT                         │
│   ─────────────────                     ───────────                         │
│                                                                             │
│   ┌─────────────────┐                   ┌─────────────────────┐            │
│   │  pipeline.db    │                   │  Qualification      │            │
│   │  (SQLite)       │───── CSV ────────►│  + Enrichment       │            │
│   │                 │      Export       │  + Deduplication    │            │
│   │  Tables:        │                   │                     │            │
│   │  • contractors  │                   │  Uses:              │            │
│   │  • contacts     │                   │  • Cerebras (fast)  │            │
│   │  • licenses     │                   │  • DeepSeek (deep)  │            │
│   │  • oem_certs    │                   │  • Hunter.io        │            │
│   │  • spw_rankings │                   │  • Close CRM dedup  │            │
│   └─────────────────┘                   └─────────────────────┘            │
│                                                  │                          │
│                                                  ▼                          │
│                                         ┌───────────────────────────┐      │
│                                         │  GOLD STANDARD LIST        │      │
│                                         │  MASTER_enriched_leads.csv │      │
│                                         │                            │      │
│                                         │  ZERO DUPLICATES           │      │
│                                         │  CLEAN ENOUGH TO EAT OFF   │      │
│                                         └───────────────────────────┘      │
│                                                  │                          │
│                                     ┌────────────┼────────────┐            │
│                                     ▼            ▼            ▼            │
│                              Close CRM     HubSpot      Coperniq           │
│                              (Sales)       (Marketing)  (Customer)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Source Schema: dealer-scraper-mvp

### Database: `output/master/pipeline.db` (SQLite)

#### Table: `contractors` (Company Level)

| Column | Type | Description | Maps To |
|--------|------|-------------|---------|
| `id` | INTEGER | Primary key | (internal) |
| `company_name` | TEXT | Business name | `company_name` |
| `normalized_name` | TEXT | Lowercase, no suffixes | (dedup key) |
| `street` | TEXT | Street address | `address` |
| `city` | TEXT | City | `city` |
| `state` | TEXT | State code | `state` |
| `zip` | TEXT | ZIP code | `zip` |
| `primary_phone` | TEXT | 10-digit normalized | `phone` |
| `primary_email` | TEXT | Lowercase email | `email` |
| `primary_domain` | TEXT | Company domain | `domain` |
| `website_url` | TEXT | Full website URL | `company_website` |
| `year_founded` | INTEGER | Year established | `year_founded` |
| `employee_count` | INTEGER | Employee count | `company_size` |
| `company_linkedin_url` | TEXT | LinkedIn company page | `company_linkedin` |
| `enriched_at` | TIMESTAMP | When enriched | (tracking) |

#### Table: `contacts` (Person Level)

| Column | Type | Description | Maps To |
|--------|------|-------------|---------|
| `id` | INTEGER | Primary key | (internal) |
| `contractor_id` | INTEGER | FK to contractors | (relationship) |
| `name` | TEXT | Full name | `contact_name` |
| `first_name` | TEXT | First name | `first_name` |
| `last_name` | TEXT | Last name | `last_name` |
| `email` | TEXT | Contact email | `contact_email` |
| `phone` | TEXT | Direct phone | `contact_phone` |
| `title` | TEXT | Job title | `contact_title` |
| `source` | TEXT | Data source | `source` |
| `confidence` | INTEGER | 0-100 score | `confidence` |
| `is_decision_maker` | INTEGER | ATL flag | `is_atl` |
| `linkedin_url` | TEXT | LinkedIn profile | `linkedin_url` |
| `seniority` | TEXT | Seniority level | (for ATL calc) |

#### Table: `licenses` (Trade Qualifications)

| Column | Type | Description | Maps To |
|--------|------|-------------|---------|
| `state` | TEXT | State code | (qualification notes) |
| `license_type` | TEXT | CAC, CPC, etc. | (qualification notes) |
| `license_category` | TEXT | HVAC, PLUMBING, etc. | `industry` |
| `license_status` | TEXT | active/expired | (filter) |

#### Table: `oem_certifications` (Brand Partnerships)

| Column | Type | Description | Maps To |
|--------|------|-------------|---------|
| `oem_name` | TEXT | Generac, Tesla, etc. | (qualification notes) |
| `certification_tier` | TEXT | Premier, Elite | (qualification signal) |

---

## CSV Export Schema (dealer-scraper → sales-agent)

### File: `master_list_YYYYMMDD_HHMMSS.csv`

| CSV Column | Description | Required |
|------------|-------------|----------|
| `company_name` | Business name | YES |
| `domain` | Company domain | NO |
| `phone` | Company phone | YES |
| `email` | Company email | NO |
| `city` | City | NO |
| `state` | State code | YES |
| `zip` | ZIP code | NO |
| `state_count` | # states licensed | NO |
| `has_solar` | Solar capability | NO |
| `has_electrical` | Electrical | NO |
| `has_hvac` | HVAC | NO |
| `has_plumbing` | Plumbing | NO |
| `has_roofing` | Roofing | NO |
| `license_count` | Total licenses | NO |
| `in_spw` | Solar Power World | NO |
| `icp_score` | Pre-calculated score | NO |
| `icp_tier` | GOLD/SILVER/BRONZE | NO |

---

## Target Schema: sales-agent Gold Standard

### File: `MASTER_enriched_leads_YYYYMMDD.csv`

| Column | Description | Source | Dedup Key |
|--------|-------------|--------|-----------|
| `company_name` | Business name | dealer-scraper | 85% fuzzy |
| `domain` | Company domain | dealer-scraper | exact |
| `phone` | Company phone | dealer-scraper | exact |
| `email` | Company email | discovered | - |
| `city` | City | dealer-scraper | - |
| `state` | State code | dealer-scraper | - |
| `zip` | ZIP code | dealer-scraper | - |
| `company_website` | Full URL | discovered | - |
| `contact_name` | ATL contact name | Hunter.io | - |
| `contact_email` | ATL contact email | Hunter.io | exact |
| `contact_phone` | ATL direct phone | Hunter.io | - |
| `contact_title` | Job title | Hunter.io | - |
| `linkedin_url` | LinkedIn profile | Hunter.io | - |
| `is_atl` | Decision maker? | calculated | - |
| `qualification_score` | 0-100 AI score | Cerebras/DeepSeek | - |
| `tier` | hot/warm/cold | calculated | - |
| `dedup_status` | Action recommendation | Close CRM check | - |
| `dedup_match_id` | Close lead ID if match | Close CRM | - |
| `source` | Data provenance | tracking | - |
| `enrichment_cost` | $ spent on this lead | tracking | - |

---

## Deduplication Strategy: ZERO DUPLICATES

### Layer 1: dealer-scraper Internal Dedup

```
Hash Keys:
- primary_phone (10-digit normalized)
- primary_email (lowercase)
- primary_domain
- normalized_name (85% fuzzy)

Result: dedup_matches table tracks all merges
```

### Layer 2: sales-agent Import Dedup

```python
# In import_mep_batch.py
seen_companies = set()
seen_phones = set()
seen_domains = set()

for row in csv:
    # Normalize
    norm_name = normalize_company_name(row['company_name'])
    norm_phone = normalize_phone(row['phone'])
    norm_domain = extract_domain(row['domain'])

    # Check for duplicates
    if norm_phone in seen_phones:
        continue  # Skip duplicate
    if norm_domain and norm_domain in seen_domains:
        continue  # Skip duplicate
    if fuzzy_match(norm_name, seen_companies) > 0.85:
        continue  # Skip near-duplicate
```

### Layer 3: Close CRM Cross-Check

```python
# In close_deduplication.py

class CloseDeduplication:
    COMPANY_FUZZY_MATCH_THRESHOLD = 85.0
    EMAIL_EXACT_MATCH_REQUIRED = True

    async def check_duplicate(self, company_name, contact_email):
        # 1. Search Close for company name
        matches = await self.search_close(company_name)

        # 2. Find best fuzzy match
        best = self.find_best_match(company_name, matches)

        # 3. If company exists, check contacts
        if best and best.confidence >= 85:
            existing_contacts = await self.get_lead_contacts(best.lead_id)

            for contact in existing_contacts:
                if contact.email.lower() == contact_email.lower():
                    return "skip_duplicate"

            return "add_contact_to_existing"

        return "create_new"
```

### Layer 4: LLM/VLM Verification (NEW)

```python
# Use AI to catch edge cases human rules miss

# 1. Company name variations AI can't fuzzy match
#    "ABC Corp" vs "ABC Corporation Inc" vs "A.B.C. Corp."
#    → DeepSeek: "Are these the same company?"

# 2. Website verification
#    → Qwen VL: "Is this website active? Same business?"

# 3. Contact verification
#    → DeepSeek: "Is John Smith, CEO at ABC likely the same as
#                 J. Smith, President at ABC Corporation?"
```

---

## Dedup Status Values (Output)

| Status | Meaning | CRM Action |
|--------|---------|------------|
| `create_new` | No match found | Create new lead |
| `add_contact_to_existing` | Company exists, new contact | Add contact to lead |
| `skip_duplicate` | Exact duplicate | DO NOT IMPORT |
| `update_existing_contact` | Same contact, new data | Update contact fields |
| `needs_review` | AI uncertain | Manual review |

---

## Data Quality Rules

### MUST HAVE (Required Fields)

```
✅ company_name (not empty, not OEM brand)
✅ phone OR email (at least one contact method)
✅ state (for territory assignment)
```

### MUST NOT HAVE (Auto-Reject)

```
❌ OEM brands as company names (Generac, Carrier, etc.)
❌ Placeholder emails (.png extension, wix.com domain)
❌ Disconnected phones (from validation)
❌ Parked/placeholder domains (from VLM check)
```

### SHOULD HAVE (Quality Signals)

```
⭐ Website (active, not placeholder)
⭐ ATL contact (CEO, Owner, VP)
⭐ Direct phone (not just company main line)
⭐ Multiple licenses (shows established business)
⭐ OEM certifications (shows quality)
```

---

## File Locations

### dealer-scraper-mvp
```
/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/
├── output/
│   ├── master/
│   │   ├── pipeline.db          # SQLite database
│   │   └── master_list_*.csv    # CSV export
│   └── sources/                 # Raw source files
```

### sales-agent
```
/Users/tmkipper/Desktop/tk_projects/sales-agent/
├── backend/
│   ├── data/
│   │   ├── csv/
│   │   │   └── scraper_output/  # Symlink to dealer-scraper output
│   │   └── final_enrichment_output/
│   │       └── MASTER_enriched_leads_*.csv  # GOLD STANDARD
│   ├── import_mep_batch.py      # Import CLI
│   └── app/services/
│       └── crm/
│           └── close_deduplication.py  # Dedup logic
```

---

## Usage: Creating Gold Standard List

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend

# 1. Export fresh list from dealer-scraper
cd ../dealer-scraper-mvp
python export_master_list.py --output csv

# 2. Import to sales-agent with full pipeline
cd ../sales-agent/backend
python import_mep_batch.py ../dealer-scraper-mvp/output/master/master_list_*.csv

# 3. Output: backend/data/final_enrichment_output/MASTER_enriched_leads_*.csv
```

---

## Verification Checklist

Before importing to CRM:

- [ ] All `dedup_status` values reviewed
- [ ] No `skip_duplicate` rows included
- [ ] All `needs_review` rows manually checked
- [ ] No OEM brand names in company_name
- [ ] No placeholder emails (.png, wix.com)
- [ ] ATL contacts have valid titles
- [ ] Phone numbers are 10 digits
- [ ] Total count matches expected

---

**"Clean enough to eat off" = Zero duplicates, verified contacts, AI-validated**

*Last Updated: November 26, 2025*
