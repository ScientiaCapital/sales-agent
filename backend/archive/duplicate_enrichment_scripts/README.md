# Archived Duplicate Enrichment Scripts

**Archived**: 2025-12-02  
**Reason**: Tech debt cleanup - duplicate/unused enrichment scripts

## Main Scripts (Keep Using)

1. **`backend/run_enrichment.py`** - Main interactive enrichment (5 at a time from Supabase)
   - Test mode: `python run_enrichment.py --test --domain example.com`
   - Auto mode: `python run_enrichment.py --auto --limit 100`

2. **`backend/scrape_domain.py`** - Single domain quick scraper
   - Usage: `python scrape_domain.py acmeheating.com`

3. **`backend/batch_scrape_runner.py`** - Alternative batch runner with CSV input
   - Usage: `python batch_scrape_runner.py --auto`

4. **`backend/enrich_gold_standard_batch.py`** - Hunter.io enrichment (paid service)
   - Usage: `python enrich_gold_standard_batch.py --batch 1`

## Archived Scripts (Do Not Use)

These scripts were archived because they duplicate functionality or are incomplete:

- `batch_enrich_companies.py` - Apollo.io enrichment (duplicate of enrichment_agent)
- `csv_enrichment_pipeline.py` - CSV pipeline using Cerebras (duplicate functionality)
- `playwright_enrichment_pipeline.py` - Playwright CSV pipeline (duplicate functionality)
- `task28_linkedin_enrichment.py` - Task script (incomplete/old)
- `task29_enrichment_simple.py` - Task script (incomplete/old)
- `task29_enrichment_agent_react.py` - Task script (incomplete/old)

## Notes

- All archived scripts are preserved in case they contain useful code patterns
- Main scripts use Browserbase for scraping (no local browser setup needed)
- Test mode added to `run_enrichment.py` for easy testing (2-5 companies max)

