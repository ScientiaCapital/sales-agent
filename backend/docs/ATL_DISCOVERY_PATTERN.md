# ATL Contact Discovery Pattern

## Overview

The sales-agent uses a **tiered discovery pattern** to find Above-The-Line (ATL) contacts, with graceful fallback to Below-The-Line (BTL) contacts when decision makers can't be found.

```
Company Name
    ↓
Website Discovery (if missing) ←── Google domain inference
    ↓
Website Validation (ICP qualifier) ←── HTTP check + team page detection
    ↓
Hunter.io Domain Search ←── ATL/BTL contacts with emails
    ↓
Browserbase Team Scraping ←── JavaScript rendering for React/Vue sites
    ↓                          (runs if <3 ATL found by Hunter.io)
Apollo Domain Search (DISABLED - no credits)
    ↓
Website Email Scraping ←── /contact, /about, /team page regex
    ↓
Review Scraping ←── Google, Yelp, BBB reputation data
    ↓
QUALIFICATION RESULT
    ├── ATL contacts → Primary outreach (CEO, VP, Director)
    └── BTL contacts → Marketing/nurture (PM, Estimator, etc.)
```

## Discovery Methods

### Tier 1: Hunter.io Domain Search (Primary)
- **Cost**: $0.01/search
- **Returns**: Up to 10 contacts with emails
- **ATL Detection**: Matches title against ATL keywords
- **Best For**: SMB contractors with public team pages

### Tier 1.5: Browserbase Team Scraping (NEW - ENABLED)
- **Status**: ENABLED - You have Browserbase credentials!
- **Cost**: ~$0.01/session
- **Triggers**: Runs automatically if Hunter.io found <3 ATL contacts
- **Returns**: ATL contacts from team/about pages on JavaScript-heavy sites
- **Best For**: React, Vue, Angular sites that Hunter.io can't parse
- **Key Feature**: Finds contacts even without emails (for later enrichment)

### Tier 2: Apollo Domain Search (Currently Disabled)
- **Status**: DISABLED - No credits (Nov 26, 2025)
- **Cost**: ~$0.03-0.05/contact
- **Returns**: Verified emails with phone numbers
- **Re-enable**: Purchase Apollo credits ($99/mo for 2400 credits)

### Tier 2.5: Website Email Scraping (FREE Fallback)
- **Cost**: $0
- **Scrapes**: /contact, /contact-us, /about, /team pages
- **Reliability**: 30-40% success rate
- **Returns**: Generic emails (info@, contact@)

### Tier 4: Browserbase Team Scraping (NEW)
- **Status**: ENABLED - You have credentials
- **Cost**: Browserbase session pricing
- **Returns**: ATL contacts from JS-heavy websites
- **Best For**: React/Vue sites that Hunter.io can't parse

### Tier 5: LinkedIn Profile Scraping (NEW)
- **Status**: ENABLED via Browserbase
- **Cost**: Browserbase session pricing
- **Returns**: Work history, title verification
- **Best For**: Verifying ATL status from profile

## ATL Title Detection

The system classifies contacts as ATL (decision makers) based on job title keywords:

```python
ATL_TITLES = [
    "ceo", "chief executive", "president", "owner", "founder", "co-founder",
    "cto", "chief technology", "vp", "vice president", "director",
    "head of", "manager", "partner", "principal"
]
```

## Contact Discovery Audit

Every discovery attempt is now logged via `ContactDiscoveryAudit`:

```python
# Example audit output in logs:
✅ [hunter_domain_search] ABC Corp: Found 5 contacts (3 ATL, 2 BTL) in 850ms, cost=$0.0100
❌ [apollo_domain_search] ABC Corp: Failed - DISABLED: No Apollo credits
✅ [website_email_scrape] ABC Corp: Found 1 contacts (0 ATL, 1 BTL) in 2100ms, cost=$0.0000
✅ [review_scraping] ABC Corp: Score: 78/100, Platforms: 2
```

### Audit in Qualification Notes

The audit summary is automatically appended to qualification notes:

```
==================================================
CONTACT DISCOVERY AUDIT
==================================================
Company: ABC Corp
Website: abccorp.com

DISCOVERY METHODS ATTEMPTED:
  ✅ hunter_domain_search: 5 contacts (3 ATL, 2 BTL)
  ❌ apollo_domain_search: DISABLED - No Apollo credits
  ✅ website_email_scrape: 1 contacts (0 ATL, 1 BTL)
  ✅ review_scraping: No contacts (Score: 78/100)

TOTAL: 5 contacts (3 ATL, 2 BTL)
COST: $0.0100
LATENCY: 3850ms

ATL CONTACTS (Decision Makers):
  1. John Smith (CEO)
     📧 john@abccorp.com [hunter]
  2. Jane Doe (VP Sales)
     📧 jane@abccorp.com [hunter]
  3. Mike Johnson (Director)
     📧 mike@abccorp.com [hunter]

BTL CONTACTS (Champions): 2 found
  • Sarah Wilson (Project Manager)
  • Tom Brown (Estimator)
==================================================
```

## Fallback Logic

```python
# 1. Prefer ATL contacts for primary outreach
if atl_contacts:
    contact_email = atl_contacts[0]["email"]  # Best ATL contact

# 2. Fallback to BTL if no ATL found
elif btl_contacts:
    contact_email = btl_contacts[0]["email"]  # Best BTL contact

# 3. Fallback to any scraped email
elif scraped_emails:
    contact_email = scraped_emails[0]  # Generic email
```

## Configuration

### Environment Variables

```bash
# Hunter.io
HUNTER_API_KEY=your_hunter_api_key

# Apollo (currently disabled)
# APOLLO_API_KEY=your_apollo_api_key

# Browserbase (LinkedIn + Team scraping)
BROWSERBASE_API_KEY=bb_live_xxx
BROWSERBASE_PROJECT_ID=your_project_id
```

### Enabling/Disabling Methods

Edit `backend/app/services/langgraph/agents/qualification_agent.py`:

```python
# To re-enable Apollo when credits purchased:
# Uncomment the Apollo section around lines 630-710
```

Edit `backend/app/services/langgraph/agents/enrichment_agent.py`:

```python
# LinkedIn is now enabled via get_linkedin_profile_tool
# To disable, comment out line 222
```

## Rate Limits

| Service | Daily Limit | Per-Request Limit |
|---------|-------------|-------------------|
| Hunter.io | 500 searches | 5/second |
| Apollo | 2400/month (paid) | 10/second |
| Browserbase | Based on plan | 3 concurrent |
| LinkedIn | 500 ops/user/day | Rate-limited |

## Costs Summary

| Method | Cost | Success Rate | Speed |
|--------|------|--------------|-------|
| Hunter.io | $0.01/search | 70-80% | ~1s |
| Apollo | $0.03-0.05/contact | 80-90% | ~2s |
| Website Scraping | $0 | 30-40% | 2-4s |
| Browserbase | ~$0.01/session | 60-70% | 3-5s |
| LinkedIn | ~$0.01/profile | 50-60% | 4-6s |

## Monitoring

Check discovery performance via:

```bash
# View recent audit logs
tail -f logs/pipeline.log | grep "discovery_audit"

# View in pipeline output
curl http://localhost:8001/api/v1/audit/lead/ABC%20Corp
```

## Related Files

- `backend/app/services/contact_discovery_audit.py` - Audit service
- `backend/app/services/langgraph/agents/qualification_agent.py` - Discovery logic
- `backend/app/services/langgraph/agents/enrichment_agent.py` - Additional enrichment
- `backend/app/services/hunter_service.py` - Hunter.io integration
- `backend/app/services/browserbase_team_scraper.py` - Browserbase scraping
- `backend/app/services/email_extractor.py` - Website email scraping
