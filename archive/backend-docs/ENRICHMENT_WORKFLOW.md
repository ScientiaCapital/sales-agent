# Complete Enrichment Workflow
================================

## Overview

This document describes the complete enrichment pipeline from website scraping through paid Apollo reveal. All scripts sync with Supabase and can be spot-checked as they run.

## The 6 Main Enrichment Scripts

### 1. `run_enrichment.py` - Website Deep Scrape ✅
**Purpose**: Deep scrape company websites for phones, emails, contacts, company info  
**Cost**: $0 (Browserbase)  
**Usage**:
```bash
cd backend
python run_enrichment.py --batch-size 5   # Process 5 at a time (default)
python run_enrichment.py --batch-size 10  # Process 10 at a time
python run_enrichment.py --test --domain example.com  # Test single domain
python run_enrichment.py --auto --limit 100  # Auto mode
```

**What it does**:
- Pulls companies from Supabase that need enrichment
- Scrapes company websites using Browserbase (FREE)
- Extracts: phones, emails, ATL/BTL contacts, services, brands, service areas
- Syncs results back to Supabase
- **Spot check**: Watch it process 5-10 companies at a time, press Enter to continue

### 2. `scrape_domain.py` - Single Domain Quick Scraper ✅
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

### 3. `enrich_apollo.py` - Apollo FREE Enrichment ✅
**Purpose**: Preemptive enrichment using Apollo's FREE search/read APIs  
**Cost**: $0 (FREE - no credits spent)  
**Usage**:
```bash
cd backend
python enrich_apollo.py --test --domain example.com  # Test single domain
python enrich_apollo.py --test --limit 3             # Test 3 companies
python enrich_apollo.py --auto --limit 100          # Auto mode
```

**What it does**:
- Gets companies that have been website-enriched (have `last_enriched_at`)
- Enriches company data: LinkedIn, founded year, employee count, industry, address
- Searches for contacts: names, titles, LinkedIn URLs (FREE search - no credits)
- Syncs all FREE Apollo data to Supabase
- Rate limiting: 6s delay between companies (600/hour Apollo limit)

### 4. `enrich_linkedin.py` - LinkedIn Enrichment ✅
**Purpose**: Find, verify, and scrape LinkedIn company pages  
**Cost**: Browserbase session pricing  
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

### 5. `enrich_hunter.py` - Hunter.io Enrichment ✅
**Purpose**: Find verified emails and direct phone numbers  
**Cost**: ~$0.01 per domain searched  
**Usage**:
```bash
cd backend
python enrich_hunter.py --test --domain example.com  # Test single domain
python enrich_hunter.py --test --limit 3             # Test 3 companies
python enrich_hunter.py --auto --limit 100          # Auto mode
```

**What it does**:
- Gets companies that have been website-enriched (have `last_enriched_at`)
- Uses Hunter.io domain search to find ATL contacts
- Gets verified emails, direct phone numbers, LinkedIn URLs
- Syncs all Hunter.io data to Supabase
- Rate limiting: 2s delay between companies

### 6. `enrich_apollo_paid.py` - Apollo PAID Reveal ✅
**Purpose**: Get verified emails and phones for high-priority leads  
**Cost**: ~1-2 credits per contact (PAID - uses Apollo tokens)  
**Usage**:
```bash
cd backend
python enrich_apollo_paid.py --test --domain example.com  # Test single domain
python enrich_apollo_paid.py --test --limit 3             # Test 3 companies
python enrich_apollo_paid.py --auto --limit 50 --min-score 80  # Only ICP score 80+
```

**What it does**:
- Gets companies that have been enriched with other services
- Uses Apollo PAID reveal APIs to get verified emails and phones
- Only enriches contacts that don't already have verified emails/phones
- Filters by ICP score (use `--min-score 80` for high-priority only)
- Syncs verified contact data to Supabase
- Rate limiting: 6s delay between companies
- ⚠️ **WARNING**: Uses Apollo credits - use sparingly!

---

## Recommended Workflow Order

### Step 1: Website Deep Scrape (FREE)
```bash
python run_enrichment.py --batch-size 5 --auto --limit 8000
```
- **Cost**: $0
- **What you get**: Phones, emails, contacts, company info from websites
- **Spot check**: Watch it process 5-10 at a time, press Enter to continue

### Step 2: Apollo FREE Enrichment (FREE)
```bash
python enrich_apollo.py --auto --limit 8000
```
- **Cost**: $0
- **What you get**: Company LinkedIn, employee count, industry, contacts (names/titles/LinkedIn)
- **When**: After website scraping

### Step 3: LinkedIn Enrichment (Browserbase)
```bash
python enrich_linkedin.py --auto --limit 8000
```
- **Cost**: Browserbase session pricing
- **What you get**: Verified LinkedIn page, all employees (ATL+BTL), employee LinkedIn URLs
- **When**: After Apollo FREE enrichment

### Step 4: Hunter.io Enrichment (PAID - $0.01/domain)
```bash
python enrich_hunter.py --auto --limit 8000
```
- **Cost**: ~$0.01 per domain
- **What you get**: Verified emails, direct phone numbers, LinkedIn URLs for ATL contacts
- **When**: After LinkedIn enrichment

### Step 5: Apollo PAID Reveal (PAID - 1-2 credits/contact)
```bash
python enrich_apollo_paid.py --auto --limit 50 --min-score 80
```
- **Cost**: ~1-2 credits per contact
- **What you get**: Verified emails + phone numbers for high-priority leads
- **When**: Only for high-priority leads (ICP score 80+) after all other enrichment
- ⚠️ **Use sparingly** - only for leads that need verified contact info

---

## Cost Summary

| Step | Script | Cost | What You Get |
|------|--------|------|--------------|
| 1 | `run_enrichment.py` | $0 | Phones, emails, contacts, company info (website scraping) |
| 2 | `enrich_apollo.py` | $0 | Company LinkedIn, employee count, industry, contacts (names/titles/LinkedIn) |
| 3 | `enrich_linkedin.py` | Browserbase pricing | Verified LinkedIn page, all employees (ATL+BTL), employee LinkedIn URLs |
| 4 | `enrich_hunter.py` | ~$0.01/domain | Verified emails, direct phone numbers for ATL contacts |
| 5 | `enrich_apollo_paid.py` | ~1-2 credits/contact | Verified emails + phone numbers (high-priority only) |

**Recommendation**: 
- Use Steps 1-4 for all companies
- Use Step 5 only for high-priority leads (ICP score 80+) that need verified contact info

---

## Spot Checking & Monitoring

All scripts support:
- **Interactive mode**: Press Enter to continue, 'q' to quit
- **Auto mode**: `--auto` flag for continuous processing
- **Test mode**: `--test` flag for testing with 2-5 companies
- **Progress tracking**: All sync to Supabase with timestamps:
  - `last_enriched_at` - Website scraping complete
  - `apollo_enriched_at` - Apollo FREE enrichment complete
  - `linkedin_enriched_at` - LinkedIn enrichment complete
  - `hunter_enriched_at` - Hunter.io enrichment complete
  - `apollo_paid_enriched_at` - Apollo PAID reveal complete

---

## Database Migrations

Run these migrations to add enrichment tracking columns:

```bash
# Run all migrations
psql $DATABASE_URL -f supabase/migrations/20251202_add_apollo_enrichment_columns.sql
psql $DATABASE_URL -f supabase/migrations/20251202_add_linkedin_enrichment_columns.sql
psql $DATABASE_URL -f supabase/migrations/20251202_add_hunter_apollo_paid_columns.sql
```

---

## Quick Start

```bash
cd backend
source ../venv/bin/activate

# Step 1: Website scraping (5-10 at a time)
python run_enrichment.py --batch-size 5

# Step 2: Apollo FREE enrichment
python enrich_apollo.py --auto

# Step 3: LinkedIn enrichment
python enrich_linkedin.py --auto

# Step 4: Hunter.io enrichment
python enrich_hunter.py --auto

# Step 5: Apollo PAID reveal (high-priority only)
python enrich_apollo_paid.py --auto --min-score 80 --limit 50
```

