# Enrichment Flow - Free → Apollo Free → Apollo Paid

## The 5 Main Enrichment Scripts

### 1. `run_enrichment.py` - Main Interactive Enrichment
**Purpose**: Enrich companies 5 at a time from Supabase  
**Usage**:
```bash
cd backend
python run_enrichment.py --test --domain example.com  # Test mode
python run_enrichment.py --auto --limit 100            # Auto mode
```

**What it does**:
- Pulls companies from Supabase that need enrichment
- Scrapes company websites using Browserbase (FREE)
- Extracts: phones, emails, ATL/BTL contacts, services, brands, service areas
- Syncs results back to Supabase

### 2. `scrape_domain.py` - Single Domain Quick Scraper
**Purpose**: Quick enrichment for a single company/domain  
**Usage**:
```bash
cd backend
python scrape_domain.py acmeheating.com
python scrape_domain.py "Acme Heating" acmeheating.com /about/staff
```

**What it does**:
- Same as `run_enrichment.py` but for one company
- Checks Close CRM first
- Finds/creates company in Supabase
- Scrapes and syncs

### 3. `batch_scrape_runner.py` - Alternative Batch Runner
**Purpose**: Batch scraping with CSV input or Supabase  
**Usage**:
```bash
cd backend
python batch_scrape_runner.py --auto
python batch_scrape_runner.py --start 100  # Resume from company 100
```

**What it does**:
- Alternative to `run_enrichment.py`
- Can use CSV input or Supabase
- Same scraping functionality

### 4. `enrich_apollo.py` - Apollo FREE Enrichment Service
**Purpose**: Preemptive enrichment using Apollo's FREE search/read APIs  
**Usage**:
```bash
cd backend
python enrich_apollo.py --test --domain example.com  # Test single domain
python enrich_apollo.py --test --limit 3             # Test 3 companies
python enrich_apollo.py --auto --limit 100          # Auto mode
```

**What it does**:
- Gets companies that have been website-enriched (have domain + `last_enriched_at`)
- Enriches company data: LinkedIn, founded year, employee count, industry, address
- Searches for contacts: names, titles, LinkedIn URLs (FREE search - no credits)
- Syncs all FREE Apollo data to Supabase
- Rate limiting: 6s delay between companies (600/hour Apollo limit)
- ⚠️ **NO PAID REVEAL** - Only uses free Apollo search/read APIs

### 5. `enrich_linkedin.py` - LinkedIn Enrichment Service
**Purpose**: Find, verify, and scrape LinkedIn company pages  
**Usage**:
```bash
cd backend
python enrich_linkedin.py --test --domain example.com  # Test single domain
python enrich_linkedin.py --test --limit 3             # Test 3 companies
python enrich_linkedin.py --auto --limit 100          # Auto mode
python enrich_linkedin.py --search-employee "John Doe" "Acme Corp"  # Search specific employee
```

**What it does**:
- Finds/verifies company LinkedIn page (using Google search)
- Scrapes company LinkedIn page using Browserbase:
  - Company details: employee count, industry, description, founded year
  - All employees (ATL + BTL) with pagination for big companies
  - Employee LinkedIn profile URLs
- Syncs all LinkedIn data to Supabase
- Rate limiting: 10s delay between companies (LinkedIn is strict)
- ⚠️ **Uses Browserbase** - Required for bypassing LinkedIn bot detection

---

## Enrichment Flow (Recommended Order)

### Step 1: FREE Website Scraping ✅
**Script**: `run_enrichment.py` or `scrape_domain.py`  
**Cost**: $0 (Browserbase)  
**Extracts**:
- Phone numbers (from website)
- Email addresses (from website)
- ATL/BTL contacts (names + titles from team pages)
- Company info (services, brands, service areas, certifications)
- Owner bios (personal details for rapport)

**When to use**: Always start here - it's free and gets basic data

---

### Step 2: Apollo FREE Search (Read Only) ✅
**Script**: `enrich_apollo.py`  
**Cost**: $0 (free search - no credits spent)  
**Gets**:
- **Company data**: LinkedIn URL, founded year, employee count, industry, address
- **Contact names and titles**: Up to 25 contacts per company
- **LinkedIn URLs**: For discovered contacts
- **Company structure**: Keywords, social profiles, Alexa ranking

**When to use**: After website scraping, to discover more contacts and enrich company profile with Apollo's free data

**Usage**:
```bash
cd backend
python enrich_apollo.py --test --domain acmeheating.com  # Test single domain
python enrich_apollo.py --test --limit 3                 # Test 3 companies
python enrich_apollo.py --auto --limit 100               # Auto mode
```

**What it does**:
- Gets companies that have been website-enriched (have `last_enriched_at`)
- Enriches company data using `ApolloService.enrich_company()` (FREE)
- Searches for contacts using `ApolloService.search_company_contacts()` (FREE)
- Syncs all FREE Apollo data to Supabase
- Marks companies with `apollo_enriched_at` timestamp
- Rate limiting: 6s delay between companies (600/hour limit)

---

### Step 3: LinkedIn Scraping ✅
**Script**: `enrich_linkedin.py`  
**Cost**: Browserbase session pricing (check https://browserbase.com/pricing)  
**Gets**:
- **Company LinkedIn page**: Finds/verifies company LinkedIn URL
- **Company details**: Employee count, industry, description, founded year, headquarters
- **All employees**: ATL + BTL contacts with pagination (up to 100 per company)
- **Employee LinkedIn URLs**: Profile URLs for all discovered employees
- **Employee titles**: Current job titles for all employees

**When to use**: After Apollo enrichment, to get comprehensive employee list and verify company LinkedIn page

**Usage**:
```bash
cd backend
python enrich_linkedin.py --test --domain acmeheating.com  # Test single domain
python enrich_linkedin.py --test --limit 3                 # Test 3 companies
python enrich_linkedin.py --auto --limit 100               # Auto mode
python enrich_linkedin.py --search-employee "John Doe" "Acme Corp"  # Search specific employee
```

**What it does**:
- Gets companies that have been website-enriched (have `domain` + `last_enriched_at`)
- Finds/verifies company LinkedIn page using Google search
- Scrapes company LinkedIn page using Browserbase:
  - Extracts company details from company page
  - Navigates to `/people/` page
  - Scrolls to load more employees (pagination for big companies)
  - Extracts employee names, titles, LinkedIn URLs
- Syncs all LinkedIn data to Supabase
- Marks companies with `linkedin_enriched_at` timestamp
- Rate limiting: 10s delay between companies (LinkedIn is strict)

---

### Step 4: Apollo PAID Reveal (Email + Phone) 💰
**Method**: `ApolloService.search_and_enrich_contacts()` with `reveal_emails=True, reveal_phones=True`  
**Cost**: ~1-2 credits per contact  
**Gets**:
- Verified email addresses (real emails, not placeholders)
- Phone numbers (if available)

**When to use**: Only for high-priority leads after free methods exhausted

**Example**:
```python
from app.services.apollo import ApolloService

apollo = ApolloService()
enriched = await apollo.search_and_enrich_contacts(
    domain="acmeheating.com",
    job_titles=["CEO", "Owner"],
    max_results=5,  # Limit to top 5 to control costs
    reveal_emails=True,   # Costs credits
    reveal_phones=True    # Costs credits
)
# Returns verified emails + phones - COSTS CREDITS
```

---

## Recommended Workflow

1. **Run FREE website scraping** on all companies:
   ```bash
   python run_enrichment.py --auto --limit 8000
   ```

2. **Run Apollo FREE enrichment** to discover more contacts and enrich company data:
   ```bash
   python enrich_apollo.py --auto --limit 8000
   ```
   This runs AFTER website scraping and adds:
   - Company LinkedIn, employee count, industry, founded year
   - Contact names, titles, LinkedIn URLs (FREE search)

3. **Run LinkedIn enrichment** to get comprehensive employee list:
   ```bash
   python enrich_linkedin.py --auto --limit 8000
   ```
   This runs AFTER Apollo enrichment and adds:
   - Verified company LinkedIn page
   - All employees (ATL + BTL) with LinkedIn URLs
   - Company details from LinkedIn

4. **Run Apollo PAID reveal** only for high-priority leads:
   ```python
   # Only for HOT leads or when you need verified emails
   enriched = await apollo.search_and_enrich_contacts(
       domain, 
       reveal_emails=True, 
       reveal_phones=True
   )
   ```

---

## Current Status

✅ **Step 1 (FREE scraping)**: Fully implemented in `run_enrichment.py`, `scrape_domain.py`, `batch_scrape_runner.py`  
✅ **Step 2 (Apollo FREE search)**: Fully implemented in `enrich_apollo.py` - separate service for preemptive enrichment  
✅ **Step 3 (LinkedIn scraping)**: Fully implemented in `enrich_linkedin.py` - uses Browserbase for scraping  
⚠️ **Step 4 (Apollo PAID reveal)**: Available in `ApolloService` but not integrated into main scripts  

---

## Next Steps

To complete the enrichment flow, we should:

1. ✅ **Apollo FREE enrichment**: Complete! Use `enrich_apollo.py` as separate service
   - Runs after website scraping
   - Gets company data + contacts (FREE search)
   - Syncs to Supabase with `apollo_enriched_at` timestamp

2. **Add Apollo PAID reveal** as optional final step:
   - Add `--apollo-reveal` flag to `run_enrichment.py`
   - Only reveal emails/phones when flag is set
   - Use `search_and_enrich_contacts()` with `reveal_emails=True, reveal_phones=True`
   - Mark source as `apollo_enriched` (paid)

3. **Cost tracking**:
   - Track Apollo credits used per company
   - Log to Supabase for cost analysis

---

## Cost Summary

| Step | Script | Cost | What You Get |
|------|--------|------|--------------|
| 1 | `run_enrichment.py` | $0 | Phones, emails, contacts, company info (website scraping) |
| 2 | `enrich_apollo.py` | $0 | Company LinkedIn, employee count, industry, contacts (names/titles/LinkedIn) |
| 3 | `enrich_linkedin.py` | Browserbase pricing | Verified LinkedIn page, all employees (ATL+BTL), employee LinkedIn URLs |
| 4 | (Future) | ~1-2 credits/contact | Verified emails + phone numbers (paid reveal) |

**Recommendation**: Use Steps 1 & 2 for all companies, Step 3 only for HOT leads or when verified contact info is critical.

