# Deep Scrape Setup and Execution Guide

## Overview
This guide walks through setting up and running the deep scrape on 1,000 companies using Browserbase and Playwright.

**Deep scrape extracts:**
- ATL contacts (CEO, Owner, President, VP, Director, Founder)
- BTL contacts (Managers, Coordinators, Sales, etc.)
- Phone numbers with source tracking (NEW vs VERIFIED)
- Email addresses (general + team member emails)
- Physical addresses for territory assignment
- LinkedIn employee count and visible employees

---

## Prerequisites

### 1. Phase 2 Must Be Complete
Deep scrape requires enriched company data from Phase 2:
- Expected input: `backend/data/final_enrichment_output/*.csv`
- Must contain domains and company names

### 2. Environment Variables Required
Add to `.env` file:
```bash
# Required
BROWSERBASE_API_KEY=your_api_key_here
BROWSERBASE_PROJECT_ID=your_project_id_here

# Optional (recommended)
DATABASE_URL=your_postgres_connection_string
REDIS_URL=redis://localhost:6379
APOLLO_API_KEY=your_apollo_key_here
BROWSERBASE_MAX_CONCURRENT=10  # Default: 10
```

### 3. System Requirements
- Python 3.9+
- Virtual environment activated
- 8+ hours for full 1,000 company scrape
- Stable internet connection (Browserbase cloud browsers)

---

## Installation Steps

### Step 1: Activate Virtual Environment
```bash
source venv/bin/activate
```

### Step 2: Install Dependencies
All dependencies should already be installed. If not:
```bash
pip install pandas playwright psycopg2-binary redis supabase httpx python-dotenv
playwright install chromium
```

### Step 3: Create Required Directories
```bash
mkdir -p backend/data/final_enrichment_output
mkdir -p backend/logs
mkdir -p backend/data/apollo_cache
mkdir -p backend/data/scrape_sessions
```

### Step 4: Validate Prerequisites
Run the validation script to check everything is ready:
```bash
python backend/validate_deep_scrape_prerequisites.py
```

**Expected output:**
- `Exit code 0` = All checks passed (ready for production)
- `Exit code 2` = Warnings only (can proceed with limited features)
- `Exit code 1` = Critical failures (cannot proceed)

**Fix common issues:**
```bash
# Missing Playwright
pip install playwright && playwright install chromium

# Missing pandas
pip install pandas

# Missing environment variables
# Edit .env file and add BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID
```

---

## Running Deep Scrape

### Option 1: Test Scrape (RECOMMENDED FIRST)
Test on 10 companies before running full production scrape:

```bash
# Using test script (recommended)
./backend/test_deep_scrape.sh

# Or manually
python backend/deep_scrape_companies.py --top 10
```

**Expected duration:** 2-5 minutes
**Output:** `backend/data/final_enrichment_output/DEEP_SCRAPE_10_*.csv`

**Verify test results:**
1. Open output CSV file
2. Check ATL contacts found
3. Verify phone numbers and emails
4. Review audit trail (NEW vs VERIFIED phones)

### Option 2: Production Scrape (1,000 Companies)
After successful test, run full scrape:

```bash
# Top 1,000 companies by ICP score
python backend/deep_scrape_companies.py --top 1000

# Or scrape all companies in input file
python backend/deep_scrape_companies.py --all
```

**Expected duration:** 8-10 hours with 10 concurrent sessions
**Output:** `backend/data/final_enrichment_output/DEEP_SCRAPE_1000_*.csv`

### Option 3: Resume Interrupted Scrape
If scrape is interrupted, resume from progress file:

```bash
python backend/deep_scrape_companies.py --resume
```

---

## Output Files

### Main Output: `DEEP_SCRAPE_1000_*.csv`
Contains all scraped data with the following columns:

**Company Information:**
- `company_name`, `domain`
- `website_reachable`, `linkedin_found`
- `pages_scraped` (list of URLs visited)

**Contact Counts:**
- `atl_count` (Above The Line contacts)
- `btl_count` (Below The Line contacts)
- `phone_count`, `email_count`

**Phone Audit Trail:**
- `new_phones` (phones NOT in existing data)
- `verified_phones` (phones that MATCH existing data)
- `new_phone_count`, `verified_phone_count`

**ATL Contacts (JSON):**
- `atl_contacts` - Array of: `{name, title, source, email, phone, linkedin_url}`

**BTL Contacts (JSON):**
- `btl_contacts` - Array of: `{name, title, source, email, phone, linkedin_url}`

**Address:**
- `address`, `city`, `state`, `zip_code`

**LinkedIn:**
- `linkedin_url`, `linkedin_employee_count`

### Close CRM Export: `CLOSE_CRM_IMPORT_*.csv`
Ready-to-import format for Close CRM with:
- `Company Name`, `Website`, `Lead Status`
- `Contact Name`, `Contact Title`, `Contact Email`, `Contact Phone`
- `Phone`, `Address`, `City`, `State`, `Zip`
- `LinkedIn`, `Employee Count`
- `ATL Count`, `BTL Count`, `Phone Audit`

### JSON Backup: `DEEP_SCRAPE_1000_*.json`
Complete raw data in JSON format for custom processing

---

## Monitoring Progress

### Real-time Logs
Monitor scraping progress:
```bash
tail -f backend/logs/deep_scrape_*.log
```

**Log indicators:**
- `Starting scrape:` - Company scraping started
- `COMPLETE:` - Company scraping finished
- `ERROR:` - Issue encountered (logged but continues)
- `Session cleanup` - Browserbase session closed

### Progress Tracking
Check progress files:
```bash
ls -lh backend/data/scrape_sessions/
```

### Performance Metrics
Track in logs:
- Companies per minute
- Success rate (website reachable %)
- ATL contact discovery rate
- Phone/email extraction rate

---

## Troubleshooting

### Issue: "ERROR: pandas is not installed"
**Solution:**
```bash
source venv/bin/activate
pip install pandas
```

### Issue: "ERROR: Playwright is not installed"
**Solution:**
```bash
pip install playwright
playwright install chromium
```

### Issue: "ERROR: BROWSERBASE_API_KEY must be set"
**Solution:**
1. Check `.env` file exists in project root
2. Add missing environment variables:
```bash
BROWSERBASE_API_KEY=your_api_key_here
BROWSERBASE_PROJECT_ID=your_project_id_here
```

### Issue: "No CSV files found in backend/data/final_enrichment_output"
**Solution:**
- Phase 2 must be complete before running deep scrape
- Check for enriched CSV files: `ls backend/data/final_enrichment_output/*.csv`
- If missing, run Phase 2 first

### Issue: Browserbase session creation fails
**Solution:**
1. Verify API key is valid: check Browserbase dashboard
2. Check project ID matches your Browserbase project
3. Verify internet connection
4. Check Browserbase service status

### Issue: Scrape is very slow
**Possible causes:**
- Low `BROWSERBASE_MAX_CONCURRENT` (default: 10)
- Browserbase rate limiting
- Network latency

**Solution:**
```bash
# Increase concurrent sessions (if Browserbase plan allows)
BROWSERBASE_MAX_CONCURRENT=20
```

### Issue: High failure rate (many unreachable websites)
**This is expected:**
- ~30-40% of websites may be unreachable (offline, broken, etc.)
- Script continues scraping remaining companies
- LinkedIn scraping provides fallback data

### Issue: Memory usage is high
**Solution:**
- Reduce `BROWSERBASE_MAX_CONCURRENT` to 5-8
- Monitor system resources: `top` or Activity Monitor
- Restart scrape if memory issues persist

---

## Expected Results

### Success Metrics (Target)
- **Website Reachable:** 60-70%
- **LinkedIn Found:** 80-90%
- **Companies with ATL:** 40-60%
- **Average ATL per company:** 2-4
- **Average phones per company:** 1-3
- **Average emails per company:** 2-5

### Performance Benchmarks
- **Speed:** 20-40 companies per hour (10 concurrent)
- **Duration:** 8-10 hours for 1,000 companies
- **Success Rate:** 85-95% completion (some domains will fail)

---

## After Scrape Completion

### 1. Review Output Files
```bash
# Open main results
open backend/data/final_enrichment_output/DEEP_SCRAPE_1000_*.csv

# View Close CRM import file
open backend/data/final_enrichment_output/CLOSE_CRM_IMPORT_*.csv
```

### 2. Validate Data Quality
Check for:
- ATL contacts found (CEO, Owner, President, etc.)
- Phone numbers with proper audit trail
- Email addresses extracted
- LinkedIn data populated

### 3. Import to Close CRM
Use the `CLOSE_CRM_IMPORT_*.csv` file:
1. Open Close CRM
2. Go to Leads → Import
3. Upload CSV file
4. Map fields (should auto-detect)
5. Review and confirm import

### 4. Archive Results
```bash
# Create backup
mkdir -p backend/data/archives/
cp backend/data/final_enrichment_output/DEEP_SCRAPE_*.* backend/data/archives/
```

---

## Command Reference

### Validation
```bash
# Check all prerequisites
python backend/validate_deep_scrape_prerequisites.py
```

### Testing
```bash
# Test script (10 companies)
./backend/test_deep_scrape.sh

# Manual test
python backend/deep_scrape_companies.py --top 10
```

### Production
```bash
# Top 1,000 companies
python backend/deep_scrape_companies.py --top 1000

# All companies in input file
python backend/deep_scrape_companies.py --all

# Resume interrupted scrape
python backend/deep_scrape_companies.py --resume
```

### Monitoring
```bash
# Watch logs in real-time
tail -f backend/logs/deep_scrape_*.log

# Check latest log file
ls -t backend/logs/deep_scrape_*.log | head -1

# View output files
ls -lh backend/data/final_enrichment_output/DEEP_SCRAPE_*
```

---

## Support

### Log Files
All execution logs saved to:
- Location: `backend/logs/deep_scrape_YYYYMMDD_HHMMSS.log`
- Format: Timestamped with INFO/WARNING/ERROR levels
- Keep for debugging and audit trail

### Progress Files
Session progress tracked in:
- Location: `backend/data/scrape_sessions/`
- Contains checkpoint data for resume functionality

### Common Questions

**Q: Can I run multiple scrapes simultaneously?**
A: No - Browserbase sessions are managed per scrape instance

**Q: What happens if my computer loses connection?**
A: Use `--resume` to continue from last checkpoint

**Q: How much does Browserbase cost?**
A: Check Browserbase pricing for your plan - typically billed per session minute

**Q: Can I scrape more than 1,000 companies?**
A: Yes - modify input file or use `--all` flag

---

## Contact

For issues or questions:
1. Check logs: `backend/logs/deep_scrape_*.log`
2. Review validation: `python backend/validate_deep_scrape_prerequisites.py`
3. Verify Phase 2 completion
4. Contact project maintainer

---

**Document Version:** 1.0
**Last Updated:** 2025-12-01
**Script Version:** deep_scrape_companies.py (989 lines)
