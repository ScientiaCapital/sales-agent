# EnrichmentAgent ReAct Patterns

## Overview
LangGraph ReAct agent orchestrating enrichment tools for intelligent data gathering and merging.

## Agent Location
```
backend/app/services/langgraph/agents/enrichment_agent.py
```

## Architecture

### Agent Type
**LCEL Chain** (simple, synchronous, <3000ms)

### Tools Available
1. **get_linkedin_profile_tool** - Browserbase LinkedIn scraper
2. **get_lead_tool** - Fetch existing CRM data from Close
3. ~~**enrich_contact_tool**~~ - Apollo.io enrichment (DISABLED - no API access)

## ReAct Orchestration Strategy

### Decision Tree
```
if linkedin_url exists:
    → Use get_linkedin_profile_tool (priority for career history)
    
if linkedin_fails OR no linkedin_url:
    → Use get_lead_tool (CRM fallback for contact info)
    
NEVER use Apollo (disabled per user requirements)
```

### Intelligent Tool Selection
```python
# Agent reasoning process
1. Analyze lead data completeness
2. Identify missing fields (email, job_title, company_size)
3. Select best tool based on:
   - Data availability (LinkedIn URL present?)
   - Tool success rate (LinkedIn > CRM)
   - Cost (Browserbase free within limits)
4. Execute tool
5. Merge results with existing data
6. Calculate confidence score
```

## Data Merging Logic

### Merge Priority
```python
# Higher priority = more trusted source
1. LinkedIn scraper (most current, direct from profile)
2. CRM data (Close) (verified, but may be outdated)
3. CSV import (dealer-scraper ICP data)
```

### Field-Specific Rules
```python
# Email
preferred_source = CRM > LinkedIn > CSV

# Job Title / Seniority
preferred_source = LinkedIn > CRM > CSV

# Company Info
preferred_source = LinkedIn > CSV > CRM

# Contact Phone
preferred_source = CRM > CSV > LinkedIn
```

### Merge Implementation
```python
def merge_enrichment_data(lead: Lead, linkedin_data: dict, crm_data: dict) -> dict:
    merged = {
        "email": crm_data.get("email") or linkedin_data.get("email") or lead.contact_email,
        "job_title": linkedin_data.get("title") or crm_data.get("title"),
        "company_name": linkedin_data.get("company") or lead.company_name,
        "phone": crm_data.get("phone") or lead.phone,
        "linkedin_url": linkedin_data.get("url") or lead.enrichment_metadata.get("linkedin_url"),
        "career_history": linkedin_data.get("experience", []),
        "seniority": calculate_seniority(linkedin_data.get("title")),
    }
    return merged
```

## Confidence Scoring Algorithm

### Formula
```python
confidence_score = (
    data_completeness_score * 0.4 +  # 40% weight
    source_quality_score * 0.3 +      # 30% weight
    data_freshness_score * 0.3        # 30% weight
)
```

### Component Calculations
```python
# Data Completeness (0.0 to 1.0)
required_fields = ["email", "job_title", "company_name", "linkedin_url"]
completeness = sum(field is not None for field in required_fields) / len(required_fields)

# Source Quality (0.0 to 1.0)
source_weights = {
    "linkedin": 1.0,
    "crm": 0.8,
    "csv_import": 0.6,
    "none": 0.0
}

# Data Freshness (0.0 to 1.0)
days_since_update = (now - last_updated).days
if days_since_update < 30:
    freshness = 1.0
elif days_since_update < 90:
    freshness = 0.7
elif days_since_update < 180:
    freshness = 0.5
else:
    freshness = 0.3
```

## Error Handling

### Tool Failure Cascade
```python
try:
    if linkedin_url:
        result = get_linkedin_profile_tool(linkedin_url)
except LinkedInScrapingError:
    logger.warning("LinkedIn scraping failed, falling back to CRM")
    result = get_lead_tool(lead_id)
except Exception as e:
    logger.error(f"All enrichment tools failed: {e}")
    result = {"error": "enrichment_failed", "confidence": 0.0}
```

### Retry Strategy
- LinkedIn failures: No retry (respect rate limits)
- CRM failures: 3 retries with exponential backoff
- Network errors: Immediate retry once

## Performance Targets
- **Total latency**: <3000ms per lead
- **Tool execution**: <2000ms
- **Data merging**: <100ms
- **Confidence calculation**: <50ms

## Integration with QualificationAgent

### Handoff Pattern
```python
# Step 1: EnrichmentAgent enriches lead
enriched_lead = enrichment_agent.invoke(lead)

# Step 2: Pass to QualificationAgent
qualification = qualification_agent.invoke({
    "lead": enriched_lead,
    "confidence": enriched_lead.confidence_score
})

# Step 3: Store final result
lead.qualification_score = qualification.score
lead.enrichment_status = "completed"
lead.confidence_score = enriched_lead.confidence_score
```

## State Management

### Redis Checkpointing
```python
# Save intermediate state
checkpoint_id = f"enrichment_{lead_id}_{timestamp}"
redis.setex(checkpoint_id, 3600, json.dumps({
    "lead_id": lead_id,
    "tools_executed": ["get_linkedin_profile_tool"],
    "partial_results": linkedin_data,
    "status": "in_progress"
}))
```

### PostgreSQL Tracking
```sql
INSERT INTO agent_executions (
    agent_type, 
    lead_id, 
    status, 
    latency_ms, 
    cost_usd,
    tools_used,
    confidence_score
) VALUES (
    'EnrichmentAgent',
    123,
    'completed',
    2456,
    0.0,
    ARRAY['get_linkedin_profile_tool', 'get_lead_tool'],
    0.87
);
```

## Best Practices
1. **Always calculate confidence scores** - Don't trust enriched data blindly
2. **Log tool selection reasoning** - Debug why agent chose specific tools
3. **Cache LinkedIn data** - Avoid re-scraping same profiles
4. **Respect rate limits** - Track API usage across all tools
5. **Graceful degradation** - Return partial results if tools fail
