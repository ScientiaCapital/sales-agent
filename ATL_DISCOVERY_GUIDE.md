# ATL Contact Discovery & Enrichment Guide

## Overview

This guide shows you how to discover Above-The-Line (ATL) contacts from LinkedIn company pages and enrich them with Apollo.io.

## What are ATL Contacts?

**Above-The-Line (ATL) contacts** are decision-makers who make purchasing decisions:
- **C-level executives**: CEO, CTO, CFO, COO, CMO
- **Vice Presidents**: VP Sales, VP Marketing, VP Engineering
- **Directors**: Director of Operations, Head of Department
- **Score**: 70-100 (decision-making power)

## Quick Start

### Option 1: Full Pipeline (Recommended)

```bash
# Import CSV + Discover ATL + Enrich
python3 scripts/full_pipeline.py
```

This will:
1. Import your CSV companies
2. Enrich companies with emails using Apollo
3. Discover ATL contacts for companies without emails via LinkedIn

### Option 2: Step-by-Step

**Step 1: Import CSV**
```bash
python3 scripts/import_csv.py companies_ready_to_import.csv
```

**Step 2: Discover ATL Contacts**

Via API:
```bash
curl -X POST "http://localhost:8001/api/contacts/discover" \
  -H "Content-Type: application/json" \
  -d '{
    "company_linkedin_url": "https://linkedin.com/company/techcorp"
  }'
```

Via Python:
```python
from app.services.linkedin_scraper import LinkedInScraper

scraper = LinkedInScraper()
result = scraper.discover_atl_contacts(
    company_linkedin_url="https://linkedin.com/company/techcorp"
)

print(f"Found {result['total_atl_contacts']} ATL contacts")
for contact in result['contacts']:
    print(f"- {contact['name']}: {contact['title']} (Score: {contact['decision_maker_score']})")
```

**Step 3: Enrich Contacts**

```bash
# Enrich leads with emails
python3 scripts/batch_enrich_companies.py --mode email_only --limit 10
```

## API Endpoints

### Discover ATL Contacts

```bash
POST /api/contacts/discover
```

**Request:**
```json
{
  "company_linkedin_url": "https://linkedin.com/company/techcorp",
  "include_titles": ["CEO", "CTO", "VP"]  // Optional
}
```

**Response:**
```json
{
  "message": "ATL contacts discovered successfully",
  "company_url": "https://linkedin.com/company/techcorp",
  "total_atl_contacts": 8,
  "contacts": [
    {
      "name": "John Doe",
      "title": "CEO & Co-Founder",
      "decision_maker_score": 100,
      "contact_priority": "high",
      "profile_url": "https://linkedin.com/in/johndoe",
      "location": "San Francisco, CA",
      "tenure": "5 years"
    }
  ]
}
```

### Build Org Chart

```bash
GET /api/contacts/org-chart?company_linkedin_url=https://linkedin.com/company/techcorp&max_depth=2
```

### Scrape LinkedIn Profile

```bash
GET /api/contacts/profile/https://linkedin.com/in/johndoe
```

## Using with Imported Leads

### Discover ATL for All Imported Companies

Create a script to discover ATL contacts for all your imported leads:

```python
import asyncio
from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.linkedin_scraper import LinkedInScraper

db = SessionLocal()
scraper = LinkedInScraper()

# Get leads without contact emails
leads = db.query(Lead).filter(
    Lead.contact_email.is_(None)
).limit(10).all()

for lead in leads:
    # Try to find LinkedIn URL from website
    linkedin_url = f"https://linkedin.com/company/{lead.company_name.lower().replace(' ', '-')}"
    
    # Discover ATL contacts
    result = scraper.discover_atl_contacts(linkedin_url)
    
    if result['total_atl_contacts'] > 0:
        print(f"✅ {lead.company_name}: {result['total_atl_contacts']} ATL contacts")
        # Store in lead.additional_data
        if not lead.additional_data:
            lead.additional_data = {}
        lead.additional_data['atl_contacts'] = result['contacts']
        db.commit()
```

## LinkedIn Setup Requirements

### Browserbase Configuration

LinkedIn scraping uses Browserbase (no local Selenium needed):

```bash
# Add to .env file
BROWSERBASE_API_KEY=your_browserbase_key
BROWSERBASE_PROJECT_ID=your_project_id
```

**Get Browserbase Credentials:**
1. Sign up at https://browserbase.com
2. Create a project
3. Get API key from dashboard
4. Add to `.env` file

### LinkedIn Company URLs

For ATL discovery, you need LinkedIn company page URLs:
- Format: `https://linkedin.com/company/company-name`
- Find URLs: Search company name on LinkedIn

**Add LinkedIn URLs to Leads:**

Option 1: Add to CSV (before import):
```csv
company_name,company_website,notes
Acme Corp,https://acme.com,"ICP Score: 72.8 | Domain: acme.com | LinkedIn: https://linkedin.com/company/acme-corp"
```

Option 2: Update via API after import:
```bash
curl -X PUT "http://localhost:8001/api/leads/1" \
  -H "Content-Type: application/json" \
  -d '{
    "additional_data": {
      "linkedin_url": "https://linkedin.com/company/acme-corp"
    }
  }'
```

## Decision-Maker Scoring

**Scoring System:**
- **C-level (CEO, CTO, CFO, etc.)**: 100 points
- **VP / Vice President**: 85 points
- **Director / Head of**: 70 points
- **Manager**: 50 points

**Priority Levels:**
- **High**: Score >= 85 (C-level, VP)
- **Medium**: Score >= 70 (Director)
- **Low**: Score < 70

## Enrichment Workflow

### Step 1: Discover ATL Contacts

```bash
python3 scripts/full_pipeline.py --skip-import --limit 10
```

This discovers ATL contacts for companies without emails.

### Step 2: Extract Email Addresses

After discovering ATL contacts, you can:
1. Use Apollo to find emails for LinkedIn profiles
2. Manual research via company website
3. Use Apollo company search (if available)

### Step 3: Enrich with Apollo

```bash
# Enrich discovered contacts
python3 scripts/batch_enrich_companies.py --mode email_only --limit 0
```

## Batch Processing

### Process All Imported Leads

```bash
# Full pipeline: Import → Discover → Enrich
python3 scripts/full_pipeline.py --limit 0
```

### Process Specific Companies

```python
from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.linkedin_scraper import LinkedInScraper

db = SessionLocal()
scraper = LinkedInScraper()

# Get specific companies
companies = ["Acme Corp", "TechStart", "DataLabs"]

for company_name in companies:
    lead = db.query(Lead).filter(Lead.company_name == company_name).first()
    if lead:
        linkedin_url = f"https://linkedin.com/company/{company_name.lower().replace(' ', '-')}"
        result = scraper.discover_atl_contacts(linkedin_url)
        print(f"{company_name}: {result['total_atl_contacts']} ATL contacts")
```

## Troubleshooting

### Error: "Browserbase not configured"

**Fix:** Add Browserbase credentials to `.env`:
```bash
BROWSERBASE_API_KEY=your_key
BROWSERBASE_PROJECT_ID=your_project_id
```

### Error: "Invalid LinkedIn company URL"

**Fix:** Ensure URL format is correct:
- ✅ `https://linkedin.com/company/techcorp`
- ❌ `https://linkedin.com/company/techcorp/` (trailing slash OK but not necessary)
- ❌ `linkedin.com/company/techcorp` (missing https://)

### No ATL Contacts Found

**Possible reasons:**
1. Company LinkedIn page doesn't exist
2. Company page is private/restricted
3. No employees match ATL criteria (CEO, VP, Director)
4. Browserbase scraping failed

**Debug:**
```python
from app.services.linkedin_scraper import LinkedInScraper

scraper = LinkedInScraper()
result = scraper.discover_employees(
    "https://linkedin.com/company/techcorp",
    max_employees=100
)
print(f"Total employees found: {len(result)}")
```

## Performance

- **LinkedIn Discovery**: ~5-10 seconds per company
- **ATL Contact Scoring**: Instant
- **Apollo Enrichment**: ~15 seconds per contact
- **Batch Processing**: ~5 contacts concurrently

## Best Practices

1. **Start Small**: Test with 5-10 companies first
2. **Verify LinkedIn URLs**: Check URLs before batch processing
3. **Rate Limits**: Respect LinkedIn and Browserbase rate limits
4. **Store Results**: Save discovered contacts in `lead.additional_data`
5. **Enrichment Priority**: Enrich high-priority contacts first (score >= 85)

## Next Steps

After discovering ATL contacts:

1. **Review discovered contacts** in lead records
2. **Extract email addresses** via Apollo or manual research
3. **Enrich full profiles** using enrichment agent
4. **Qualify leads** using qualification agent
5. **Create campaigns** for qualified ATL contacts

---

**Ready to discover ATL contacts?** Run:
```bash
python3 scripts/full_pipeline.py
```

