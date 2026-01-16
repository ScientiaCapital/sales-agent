# Action Plan: Domain Enrichment & Pipeline Opportunities

**Date**: 2026-01-12

---

## Current State Summary

### Sales-Agent Pipeline (Option D)
| Metric | Count |
|--------|-------|
| Total Companies | 4,838 |
| With Website | ~4,800 |
| With Contacts | 140 |
| **Need Contacts** | **~4,700** |
| In Close CRM | 2 |

**Opportunity**: 4,700+ companies with websites that need contact enrichment.

### Dealer-Scraper (Options A & C)
| Metric | Count |
|--------|-------|
| Contractors | 2,824 |
| With Domain | 0 |
| Source | Trane only |

**Problem**: Only Trane data exists, and Trane doesn't expose dealer websites.

---

## Option A: Re-run OEM Scrapers

### OEM Scrapers Available (capture website/domain)

| OEM | Script | Status |
|-----|--------|--------|
| Generac | `generac_automated_local.py` | ✅ Ready |
| Carrier | `test_carrier.py` | ⚠️ Test script |
| Briggs & Stratton | `finish_briggs_dedup.py` | ⚠️ Dedup only |
| Enphase | `enphase_collect_single_zip.py` | ✅ Ready |
| Cummins | `scrape_cummins_browserbase.py` | ✅ Ready |
| Mitsubishi | `fix_mitsubishi_extraction.py` | ⚠️ Fix script |
| York | `debug_york_scraper.py` | ⚠️ Debug script |
| Tesla | `diagnose_tesla.py` | ⚠️ Diagnose script |

### Recommended Order
1. **Generac** - Most complete, captures website/domain
2. **Enphase** - Solar ICP, good domain capture
3. **Cummins** - Generator dealers with websites

### Commands
```bash
cd /Users/tmk/tk_projects/dealer-scraper-mvp

# Run Generac scraper (140 SREC state ZIPs)
python scripts/generac_automated_local.py

# Run Enphase scraper
bash scripts/run_enphase_batch.sh

# Run Cummins scraper
python scripts/scrape_cummins_browserbase.py
```

**Estimated time**: 2-4 hours per OEM
**Output**: CSV files with company name, phone, website, domain

---

## Option C: Google Search Domain Enrichment

### Approach
For each Trane contractor without a domain:
1. Google search: `"Company Name" + City + State`
2. Extract domain from first result
3. Store in `primary_domain` column

### Implementation
Create script: `scripts/enrich_domains_google.py`

```python
# Uses SerpAPI or direct Google search
# Rate limit: 100 searches/day (free tier)
# Cost: $50/month for 5,000 searches (SerpAPI)
```

### Alternative: DuckDuckGo (Free)
```python
# Uses duckduckgo_search library
# No API key required
# Rate limit: ~30 requests/minute
```

### Estimated Coverage
- 2,824 Trane contractors
- ~80% domain discovery rate
- ~2,259 domains found

---

## Option D: Focus on Sales-Agent Pipeline

### Immediate Opportunities

1. **Hunter.io Email Enrichment** (4,700 companies)
   ```bash
   cd /Users/tmk/tk_projects/sales-agent/backend
   python scripts/enrich_with_hunter.py --batch 100
   ```
   - Cost: ~$0.01/lookup = $47 for all
   - Returns: Emails, confidence scores

2. **Apollo Contact Enrichment** (4,700 companies)
   ```bash
   python scripts/enrich_with_apollo.py --batch 50
   ```
   - Cost: Free tier 50/month, paid ~$0.02/lookup
   - Returns: Decision-maker contacts

3. **Push to Close CRM** (Only 2 in Close currently)
   - 44 PLATINUM tier companies ready
   - 29 GOLD tier companies ready

### Recommended Priority
1. Push PLATINUM/GOLD to Close CRM
2. Run Hunter.io on high-ICP companies
3. VLM screenshot extraction for remaining

---

## Recommended Execution Order

### Today (Quick Wins)
1. ✅ Identify high-value companies in sales-agent (PLATINUM/GOLD with websites)
2. Push top 50 to Close CRM
3. Start Generac scraper running in background

### This Week
1. Complete Generac scraper (~2,000 dealers)
2. Run Enphase scraper
3. Import OEM data to dealer-scraper DB
4. Run domain verification on new data

### Next Week
1. Hunter.io enrichment on sales-agent
2. Merge dealer-scraper domains into sales-agent
3. VLM contact extraction on enriched companies

---

## Commands Quick Reference

```bash
# Sales-Agent: Push PLATINUM to Close
cd /Users/tmk/tk_projects/sales-agent/backend
python scripts/push_to_close.py --tier PLATINUM --limit 50

# Dealer-Scraper: Run Generac
cd /Users/tmk/tk_projects/dealer-scraper-mvp
python scripts/generac_automated_local.py

# Dealer-Scraper: Google domain enrichment (to create)
python scripts/enrich_domains_duckduckgo.py --batch 100
```
