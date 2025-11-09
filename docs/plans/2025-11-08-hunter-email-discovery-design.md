# Hunter.io Email Discovery - Design Document

**Date**: November 8, 2025
**Feature**: Email Discovery Sub-Phase 2B (Hunter.io Fallback)
**Status**: Design Complete, Ready for Implementation
**Author**: Sales-Agent Development Team

## Executive Summary

This design completes the email discovery feature by adding Hunter.io API fallback to the existing website email extraction system. The two-tier cascade architecture attempts free website scraping first, then calls the paid Hunter.io API when scraping fails. This maximizes email discovery while minimizing API costs.

**Key Metrics**:
- Hunter.io API: Starter tier (500 requests/month, $0.01-0.02 per call)
- Expected cost: $0.50-$5.00/month depending on scraping success rate
- Testing budget: 50-100 API calls for comprehensive validation

**Merge Criteria**:
1. Hunter.io integration working end-to-end
2. Comprehensive test coverage (unit + integration)

## Architecture

### Two-Tier Email Discovery Cascade

The QualificationAgent attempts email discovery in two tiers:

**Tier 1 - Website Scraping** (Free, already implemented)
- Scrapes company website for email addresses
- Checks homepage, /contact, /contact-us, /about pages
- Returns prioritized list: personal names → business roles → generic
- Success: Use discovered email, skip Tier 2
- Failure: Fall through to Tier 2

**Tier 2 - Hunter.io API** (Paid, $0.01-0.02 per call)
- Calls Hunter.io Email Finder API with company domain
- Filters results by confidence score (minimum 70%)
- Returns highest-confidence email with metadata
- Success: Use Hunter email, track cost
- Failure: Continue qualification without email (non-blocking)

### Data Flow

```
Lead Input → QualificationAgent.qualify()
    ↓
Tier 1: EmailExtractor.extract_emails(website)
    ├─ Success → contact_email = extracted_emails[0]
    │            extraction_method = "scraping"
    │            hunter_cost = 0.0
    └─ Failure ↓
Tier 2: HunterService.find_email(domain)
    ├─ Success → contact_email = hunter_result["email"]
    │            extraction_method = "hunter"
    │            hunter_cost = 0.01
    └─ Failure → contact_email = None
                  extraction_method = "none"
                  hunter_cost = 0.0
    ↓
Return metadata {
    extracted_email: contact_email,
    extraction_method: "scraping" | "hunter" | "none",
    hunter_cost_usd: 0.0 | 0.01
}
    ↓
PipelineOrchestrator extracts metadata
    ↓
Updates request.lead["email"]
    ↓
Passes to EnrichmentAgent
```

## Components

### 1. HunterService Class

**Location**: `backend/app/services/hunter_service.py`

**Interface**:
```python
class HunterService:
    """Hunter.io API integration for email discovery"""

    async def find_email(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Optional[dict]:
        """
        Find email using Hunter.io Email Finder API.

        Args:
            domain: Company domain (e.g., "example.com")
            first_name: Contact first name (optional)
            last_name: Contact last name (optional)

        Returns:
            {
                "email": "john@example.com",
                "score": 95,
                "sources": [...],
                "cost": 0.01
            } or None on failure
        """
```

**Implementation Details**:
- API endpoint: `GET https://api.hunter.io/v2/email-finder`
- Authentication: API key in query params (`?api_key={HUNTER_API_KEY}`)
- Timeout: 10 seconds (matching EmailExtractor pattern)
- Confidence filter: Only return results with score > 70
- Error handling: Try/except with detailed logging, returns None
- Environment: Reads `HUNTER_API_KEY` from .env

**Error Scenarios**:
- 404: Domain not found → returns None
- 429: Rate limit exceeded → logs warning, returns None
- 500: Server error → logs error, returns None
- Timeout: Connection timeout → logs warning, returns None
- Low confidence (score ≤ 70): Filter out, returns None

### 2. QualificationAgent Integration

**Location**: `backend/app/services/langgraph/agents/qualification_agent.py`

**Changes Required**:

**Initialization** (add to `__init__`):
```python
self.hunter_service = HunterService()
```

**Email Discovery Logic** (insert after line 507):
```python
# Tier 2: Hunter.io fallback (NEW CODE)
if not contact_email and company_website:
    try:
        domain = extract_domain(company_website)
        hunter_result = await self.hunter_service.find_email(domain)

        if hunter_result and hunter_result.get("score", 0) > 70:
            contact_email = hunter_result["email"]
            extraction_method = "hunter"
            hunter_cost = hunter_result.get("cost", 0.01)
            notes += f"\nEmail found via Hunter.io: {contact_email} "
            notes += f"(confidence: {hunter_result['score']}%)"
    except Exception as e:
        logger.warning(f"Hunter.io fallback failed for {company_website}: {e}")
        extraction_method = "none"
        hunter_cost = 0.0
```

**Metadata Return** (update around line 694):
```python
metadata = {
    ...existing fields...,
    "extracted_email": contact_email,
    "extraction_method": extraction_method,  # "scraping", "hunter", "none"
    "hunter_cost_usd": hunter_cost if extraction_method == "hunter" else 0.0
}
```

**Utility Function** (add to file):
```python
def extract_domain(url: str) -> str:
    """Extract domain from URL. Example: https://example.com/path → example.com"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc or parsed.path
```

### 3. Pipeline Orchestrator

**No changes required**. The existing metadata extraction code (lines 97-102) already handles `extracted_email` from qualification metadata and updates the lead object correctly.

## Testing Strategy

### Unit Tests

**File**: `backend/tests/services/test_hunter_service.py` (~150 lines)

**Test Cases**:
1. `test_find_email_success()` - Mock Hunter.io returning high-confidence email
2. `test_find_email_low_confidence()` - Filter out results with score < 70
3. `test_find_email_api_error()` - Handle 404, 429, 500 errors gracefully
4. `test_find_email_timeout()` - Handle connection timeout (10s)
5. `test_find_email_invalid_domain()` - Handle malformed domain input
6. `test_find_email_missing_api_key()` - Error when HUNTER_API_KEY not set

**Mocking**:
- Use `pytest-httpx` for HTTP request mocking
- Mock all API calls to preserve quota during testing
- Validate request parameters (domain, api_key) in assertions

### Integration Tests

**File**: `backend/tests/services/langgraph/test_hunter_integration.py` (~180 lines)

**Test Cases**:
1. `test_qualification_hunter_fallback()` - Website scraping fails, Hunter.io succeeds
2. `test_qualification_scraping_skips_hunter()` - Website succeeds, Hunter.io not called
3. `test_qualification_both_fail_gracefully()` - Both tiers fail, qualification continues
4. `test_metadata_tracking()` - Verify extraction_method and hunter_cost_usd values
5. `test_cost_tracking_accuracy()` - Confirm $0.01 cost when Hunter.io used
6. `test_confidence_filtering()` - Only high-confidence results (score > 70) used

**Mocking**:
- Mock EmailExtractor to simulate scraping success/failure
- Mock HunterService to simulate various API responses
- Assert Hunter.io called only when website scraping fails

### End-to-End Validation

**Manual Testing** (10-15 real API calls):
1. Test 5 companies with emails on websites → verify scraping wins
2. Test 5 companies without website emails → verify Hunter.io fallback
3. Test 3 invalid/unreachable domains → verify graceful failure

**Validation Checklist**:
- [ ] Hunter.io called only when website scraping fails
- [ ] Emails discovered and passed to enrichment
- [ ] Cost tracking accurate ($0.01 per Hunter.io call)
- [ ] Total API calls < 15 during testing
- [ ] No crashes or unhandled exceptions

## Cost Tracking & Observability

### Metadata Fields

Every qualification returns these metadata fields:

- `extracted_email`: Email address found, or None
- `extraction_method`: "scraping" | "hunter" | "none"
- `hunter_cost_usd`: 0.01 if Hunter.io used, else 0.0

### Logging

**Log Levels**:
- INFO: Successful email discovery via either tier
- WARNING: Hunter.io fallback failures, low confidence results
- ERROR: Critical failures (missing API key, unexpected errors)

**Example Logs**:
```
INFO: Email discovery: website scraping found john@example.com
INFO: Email discovery: website scraping failed, trying Hunter.io...
INFO: Hunter.io found email sales@example.com (confidence: 92%, cost: $0.01)
WARNING: Hunter.io fallback failed: API rate limit exceeded
```

### Cost Estimates

**Monthly costs based on lead volume** (assumes 30% need Hunter.io):

| Leads/Month | Hunter.io Calls | Cost    |
|-------------|----------------|---------|
| 50          | 15             | $0.15   |
| 200         | 60             | $0.60   |
| 500         | 150            | $1.50   |
| 1000        | 300            | $3.00   |

**Best case** (90% scraping success): ~$0.50/month for 500 leads
**Worst case** (100% need Hunter.io): ~$5.00/month for 500 leads

### Optional Database Tracking

For historical cost analysis, add a `hunter_api_calls` table (similar to `cerebras_api_calls`):

```sql
CREATE TABLE hunter_api_calls (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id),
    domain VARCHAR(255),
    email_found VARCHAR(255),
    confidence_score INTEGER,
    cost_usd DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT NOW()
);
```

This enhancement is optional and not required for merge.

## Implementation Checklist

**Phase 4 Completion** (Design Documentation):
- [x] Design document written
- [ ] Design document reviewed
- [ ] Design document committed to git

**Phase 5** (Worktree Setup):
- [ ] Worktree already exists (`.worktrees/email-discovery`)
- [ ] Switch to worktree: `cd .worktrees/email-discovery`

**Phase 6** (Implementation Plan):
- [ ] Task breakdown created
- [ ] Implementation tasks assigned
- [ ] Ready to begin coding

## Next Steps

1. **Review this design** - Validate architecture and approach
2. **Commit design document** - Save to git before implementation
3. **Create implementation plan** - Use writing-plans skill for detailed tasks
4. **Begin implementation** - Follow TDD approach with tests first

## References

- **Hunter.io API Docs**: https://hunter.io/api-documentation/v2
- **Sub-Phase 2A HANDOFF**: `.worktrees/email-discovery/HANDOFF_EMAIL_DISCOVERY.md`
- **Existing EmailExtractor**: `backend/app/services/email_extractor.py`
- **QualificationAgent**: `backend/app/services/langgraph/agents/qualification_agent.py`
