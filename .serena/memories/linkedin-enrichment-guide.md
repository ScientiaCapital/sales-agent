# LinkedIn Enrichment with Browserbase

## Overview
LinkedIn scraping for ATL (Above-The-Line) contact discovery using Browserbase headless browser infrastructure.

## Configuration
```bash
# .env file (user adds manually)
BROWSERBASE_API_KEY=your_browserbase_api_key_here
BROWSERBASE_PROJECT_ID=your_browserbase_project_id_here
```

## LinkedIn Scraper Location
```
backend/app/services/linkedin_scraper.py
```

## Core Capabilities

### 1. Company Page Scraping
```python
scrape_company_page(linkedin_url: str) -> dict
```
**Extracts**:
- Company info (name, industry, size)
- Employee count
- HQ location
- Company description

### 2. Employee Discovery
```python
discover_company_contacts(linkedin_url: str, max_employees: int = 50) -> list
```
**Searches for**:
- CEO, CTO, VP Sales, VP Engineering
- Directors, Senior Managers
- Max 50 employees per company

### 3. ATL Contact Scoring
**Priority Scoring**:
- C-level (CEO, CTO, CFO, CMO): 100 points
- VP-level: 85 points
- Director-level: 70 points
- Manager-level: 50 points

**Filters**:
- Focus on decision-makers (C-level, VP)
- Skip individual contributors unless relevant

## Rate Limits
- **LinkedIn Basic Tier**: 100 requests/day
- **Browserbase**: Based on plan (typically 1,000 sessions/month)

## Integration with EnrichmentAgent

### Tool Definition
```python
@tool
def get_linkedin_profile_tool(url: str) -> dict:
    """Scrape LinkedIn profile for career history."""
    return linkedin_scraper.scrape_profile(url)
```

### ReAct Orchestration Flow
1. **Input**: Lead with linkedin_url from dealer-scraper CSV
2. **Tool Selection**: EnrichmentAgent chooses get_linkedin_profile_tool
3. **Scraping**: Browserbase executes LinkedIn scrape
4. **Data Extraction**: Parse job titles, seniority, company history
5. **Storage**: Save enriched contact to crm_contacts table

## Error Handling

### Common Failures
- **Rate Limited**: HTTP 429 → Wait 24 hours, retry
- **Profile Not Found**: HTTP 404 → Mark as unavailable
- **CAPTCHA**: Browserbase handles automatically
- **Session Expired**: Auto-reconnect with new session

### Fallback Strategy
```python
if linkedin_scraping_fails:
    # Fall back to CRM data (Close)
    return get_lead_tool(lead_id)
```

## Performance Targets
- **Single profile scrape**: <5 seconds
- **Company employee discovery**: <30 seconds (max 50 employees)
- **ATL contact extraction**: <10 seconds

## Data Quality Metrics
```python
confidence_score = (
    data_completeness * 0.4 +     # Name, title, company present
    source_quality * 0.3 +         # LinkedIn > Apollo > CRM
    data_freshness * 0.3           # <30 days = high freshness
)
```

## Storage Schema
```sql
CREATE TABLE crm_contacts (
    id SERIAL PRIMARY KEY,
    crm_platform VARCHAR(50) DEFAULT 'linkedin',
    external_id VARCHAR(255),     -- LinkedIn profile ID
    email VARCHAR(255),
    enrichment_data JSONB,         -- Full LinkedIn data
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Best Practices
1. **Batch Processing**: Process leads in batches of 10-20 to stay under rate limits
2. **Caching**: Store LinkedIn data for 30 days to avoid re-scraping
3. **Error Tracking**: Log all failures to crm_sync_log table
4. **Monitoring**: Track scraping success rate (target: >90%)
5. **Compliance**: Respect LinkedIn's terms of service (no bulk scraping)
