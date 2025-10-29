# ATL Contact Discovery Workflow

## Complete Workflow

This script implements the exact workflow you specified:

1. **Get company name** from imported leads
2. **If domain exists** → Go to domain
3. **Find About Us, Company, or Team page**
4. **Extract executives**: CEO, COO, CFO, CTO, VP Finance, VP Operations
5. **LinkedIn fallback** (whether website found contacts or not):
   - Look up LinkedIn company page
   - Find each person/contact from company
   - Capture their personal LinkedIn profile URLs
6. **Store LinkedIn company info**: Employee count, industry, description
7. **Store blog posts** (if available) - Review capability

## Usage

### Basic Usage

```bash
# Process first 10 companies
python3 scripts/discover_atl_contacts.py --limit 10

# Process all companies
python3 scripts/discover_atl_contacts.py --limit 0

# Process specific company
python3 scripts/discover_atl_contacts.py --company-name "Acme Corp"
```

### After CSV Import

```bash
# 1. Import CSV
python3 scripts/import_csv_simple.py companies_ready_to_import.csv

# 2. Discover ATL contacts
python3 scripts/discover_atl_contacts.py --limit 10
```

## Workflow Details

### Step 1: Website Scraping

For each company with a domain:
- Tries common team page paths:
  - `/about`, `/about-us`
  - `/company`, `/our-company`
  - `/team`, `/our-team`
- Scrapes HTML for executive cards
- Extracts: Name, Title, LinkedIn Profile URL
- Looks for: CEO, COO, CFO, CTO, VP Finance, VP Operations

### Step 2: LinkedIn Discovery

**Always runs** (whether website found contacts or not):
- Constructs LinkedIn company URL from company name
- Scrapes company page for:
  - Employee count
  - Industry
  - Company description
- Discovers ATL contacts with matching titles
- Captures **personal LinkedIn profile URLs** for each contact

### Step 3: Data Storage

Stores in `lead.additional_data`:
```json
{
  "atl_contacts": [
    {
      "name": "John Doe",
      "title": "CEO",
      "linkedin_url": "https://linkedin.com/in/johndoe",
      "decision_maker_score": 100,
      "source": "linkedin",
      "source_url": "https://linkedin.com/company/acme"
    }
  ],
  "linkedin_profile_urls": [
    "https://linkedin.com/in/johndoe",
    "https://linkedin.com/in/janesmith"
  ],
  "linkedin_company_info": {
    "employee_count": "50-200",
    "industry": "Software",
    "description": "..."
  },
  "atl_discovered_at": "2025-01-28T10:00:00",
  "atl_sources": ["website:/about", "linkedin:https://linkedin.com/company/acme"]
}
```

## Reviewing Discovered Contacts

### View in Database

```sql
SELECT 
    id,
    company_name,
    contact_name,
    contact_title,
    additional_data->'atl_contacts' as atl_contacts,
    additional_data->'linkedin_company_info'->'employee_count' as employee_count
FROM leads
WHERE additional_data->'atl_contacts' IS NOT NULL
LIMIT 10;
```

### Via API

```bash
curl http://localhost:8001/api/leads/1 | jq '.additional_data.atl_contacts'
```

## LinkedIn Profile URLs

Each discovered contact includes their **personal LinkedIn profile URL**:
- Stored in `atl_contacts[].linkedin_url`
- Also in `linkedin_profile_urls[]` array
- Use these to:
  - Review blog posts
  - Scrape detailed profile data
  - Enrich with Apollo (if email found)

## Blog Posts & LinkedIn Activity

To review blog posts and LinkedIn activity:

```python
from app.services.linkedin_scraper import LinkedInScraper

scraper = LinkedInScraper()

# Get personal profile URL from lead
profile_url = lead.additional_data['linkedin_profile_urls'][0]

# Scrape profile (includes blog posts if available)
profile_data = scraper.scrape_profile(profile_url)

# Review blog posts
blog_posts = profile_data.get('blog_posts', [])
for post in blog_posts:
    print(f"Title: {post['title']}")
    print(f"URL: {post['url']}")
    print(f"Date: {post['date']}")
```

## Employee Count

LinkedIn company page provides employee count:
- Stored in `lead.additional_data['linkedin_company_info']['employee_count']`
- Example: "50-200", "200-500", "500-1000"
- Updates `lead.company_size` if available

## Output Example

```
[1/10] Processing: A & A GENPRO INC.
   ✅ Found 3 ATL contacts
   Top contact: John Smith
   Sources: website:/about, linkedin:https://linkedin.com/company/aagenpro

[2/10] Processing: ABACUS PLUMBING A/C & ELECTRICAL
   ✅ Found 2 ATL contacts
   Top contact: Jane Doe
   Sources: linkedin:https://linkedin.com/company/abacusplumbing

============================================================
📊 ATL Discovery Summary
============================================================
Companies processed:  10
Website sources:      5
LinkedIn sources:     10
Contacts discovered:  25
Failed:               0
⏱️  Duration:           45.32s
============================================================
```

## Next Steps

After discovering ATL contacts:

1. **Review contacts** in database or via API
2. **Enrich profiles** using LinkedIn profile URLs
3. **Find emails** via Apollo (using LinkedIn URLs)
4. **Qualify leads** with discovered decision-makers
5. **Create campaigns** targeting ATL contacts

---

**Ready to discover ATL contacts?**
```bash
python3 scripts/discover_atl_contacts.py --limit 10
```

