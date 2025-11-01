# Three-Phase Completion: Merge, Email Discovery, Frontend Dashboards

**Date**: 2025-11-01
**Status**: Design Complete, Ready for Implementation
**Execution Strategy**: Waterfall (complete each phase fully before next)

## Overview

Complete three major initiatives to bring sales-agent to production readiness:

1. **Merge Feature Branches** - Consolidate pipeline-testing and claude-agent-sdk into main
2. **Email Discovery** - Extract emails from websites, integrate Hunter.io fallback
3. **Frontend Dashboards** - Build React UI for cost analytics and pipeline visualization

**Total Timeline**: 2-3 days
**Approach**: Sequential validation (merge → test → email → test → frontend → test)

---

## Phase 1: Sequential Branch Merging (1-2 hours)

### Objective

Merge two feature branches into main with validation between merges to prevent compound failures.

### Current State

**Pipeline-Testing Branch** (`feature/pipeline-testing`):
- Latest commit: e0ce20a "feat: Complete pipeline testing phase with 4-phase batch import system"
- Status: Clean, no uncommitted changes
- Key features: Multi-source enrichment, review scraping, website validation
- Branch ahead of main by 5 commits

**Claude Agent SDK Branch** (`feature/claude-agent-sdk-integration`):
- Latest commit: fb45feb "docs: Add ai-cost-optimizer integration design"
- Status: Clean, no uncommitted changes
- Key features: Circuit breaker fault tolerance, session management, integration tests
- Branch ahead of main by 5 commits

### Merge Strategy: Pipeline-Testing First

**Why Pipeline-Testing First**:
1. Enrichment agent changes affect qualification flow
2. Review scraping integrated into qualification phase
3. Website validation is foundation for email discovery (Phase 2)

**Steps**:

1. **Create Pull Request**
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/pipeline-testing
gh pr create \
  --title "feat: Complete pipeline testing with multi-source enrichment" \
  --body "$(cat <<'EOF'
## Summary
4-phase batch import system for processing contractor leads through complete pipeline.

## Changes
- Multi-source enrichment (Apollo + LinkedIn)
- Review scraping (Google, Yelp, BBB, Facebook)
- Website validation with ATL contact extraction
- Parallel processing pipeline

## Testing
- 10-lead contractor test (qualification working, enrichment needs email)
- All existing tests passing
- Ready for email discovery enhancement (Phase 2)

🤖 Generated with Claude Code
EOF
)"
```

2. **Review and Merge**
```bash
gh pr view --web  # Review in GitHub UI
gh pr merge --merge  # Merge to main
```

3. **Validate in Main**
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
git checkout main
git pull origin main

# Run full test suite
pytest backend/tests/ -v

# Run pipeline sample test
cd .worktrees/pipeline-testing
./run_sample_test.sh  # Expect: qualification success, enrichment fails (needs email)
```

4. **Cleanup Pipeline-Testing**
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
rm -rf .worktrees/pipeline-testing
git worktree prune
git push origin --delete feature/pipeline-testing
git branch -D feature/pipeline-testing
```

**Success Criteria**:
- ✅ PR merged without conflicts
- ✅ All pytest tests passing
- ✅ Qualification agent working (261-430ms latency)
- ✅ Enrichment validation error expected (no email in test data)

### Merge Strategy: Claude Agent SDK Second

**Why Second**:
1. Depends on updated main (includes pipeline changes)
2. Independent Agent SDK features (circuit breakers, session management)
3. Minimal overlap with pipeline-testing

**Steps**:

1. **Rebase on Updated Main**
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/claude-agent-sdk
git fetch origin
git rebase origin/main
# Resolve conflicts if any
```

2. **Create Pull Request**
```bash
gh pr create \
  --title "feat: Complete Agent SDK integration with circuit breakers" \
  --body "$(cat <<'EOF'
## Summary
Production-ready Claude Agent SDK with fault tolerance and session management.

## Changes
- Circuit breaker pattern for LLM calls
- PostgreSQL session store with persistence
- Comprehensive integration tests (7 test suites)
- Complete documentation (200+ lines)

## Testing
- All integration tests passing
- Circuit breaker verified with fault injection
- Session persistence validated

🤖 Generated with Claude Code
EOF
)"
```

3. **Review and Merge**
```bash
gh pr view --web
gh pr merge --merge
```

4. **Validate in Main**
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
git pull origin main

# Run full test suite including Agent SDK
pytest backend/tests/ -v
pytest backend/tests/agents_sdk/ -v

# Verify cost tracking still functional
curl http://localhost:8001/api/v1/analytics/ai-costs | jq
```

5. **Cleanup Claude Agent SDK**
```bash
rm -rf .worktrees/claude-agent-sdk
git worktree prune
git push origin --delete feature/claude-agent-sdk-integration
git branch -D feature/claude-agent-sdk-integration
```

**Success Criteria**:
- ✅ PR merged without conflicts
- ✅ All tests passing (including Agent SDK tests)
- ✅ Circuit breakers functional
- ✅ Cost tracking operational across all agents
- ✅ Both worktrees removed cleanly

### Rollback Plan

If either merge causes failures:

1. **Identify failure**: Run `pytest backend/tests/ -v --tb=short`
2. **Revert merge**: `git revert <merge-commit-hash>`
3. **Fix in branch**: Return to worktree, fix issue, force push
4. **Re-merge**: Create new PR after fix validated

---

## Phase 2: Email Discovery Enhancement (4-8 hours)

### Objective

Extract emails from company websites to enable enrichment agent, with Hunter.io fallback for cases where extraction fails.

### Problem Statement

**Current Issue**: Pipeline test shows enrichment failing with:
```
VALIDATION_ERROR: At least one identifier required: email, linkedin_url, or lead_id
```

**Root Cause**: Test CSV contains only `company_name` and `website`. Enrichment agent requires at least one identifier for Apollo/LinkedIn API calls.

**Solution**: Add email discovery between qualification and enrichment.

### Sub-Phase 2A: Comprehensive Email Extraction (4-6 hours)

#### Architecture

**New Component**: `EmailExtractor` class in `backend/app/services/website_validator.py`

**Extraction Strategy**:
1. **Page Discovery** - Find contact pages, about pages, team pages via common URL patterns
2. **Pattern Matching** - Apply regex patterns for email formats
3. **Validation** - Check email format validity, filter generic emails
4. **Prioritization** - Rank emails by likelihood of decision-maker contact

**Email Patterns**:
```python
PATTERNS = [
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',  # Standard format
    r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',  # With whitespace
    r'[a-zA-Z0-9._%+-]+\s*\(at\)\s*[a-zA-Z0-9.-]+',  # Obfuscated: name (at) domain
    r'[a-zA-Z0-9._%+-]+\s*\[at\]\s*[a-zA-Z0-9.-]+',  # Obfuscated: name [at] domain
]

CONTACT_PAGE_PATTERNS = [
    '/contact', '/contact-us', '/about', '/team', '/leadership',
    '/get-in-touch', '/reach-us', '/company'
]

GENERIC_FILTERS = [
    'info@', 'admin@', 'webmaster@', 'noreply@', 'no-reply@',
    'support@', 'help@', 'contact@'
]
```

#### Implementation

**File**: `backend/app/services/email_extractor.py` (new file)

```python
"""Email extraction from company websites."""
import re
import httpx
from typing import List, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class EmailExtractor:
    """Extract and validate emails from company websites."""

    PATTERNS = [...]  # From above
    CONTACT_PAGES = [...]
    GENERIC_FILTERS = [...]

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def extract_emails(
        self,
        website: str,
        max_pages: int = 3
    ) -> List[str]:
        """
        Extract emails from website.

        Args:
            website: Company website URL
            max_pages: Maximum pages to crawl

        Returns:
            List of emails, prioritized (decision-makers first)
        """
        emails = set()

        # Try main page
        emails.update(await self._extract_from_page(website))

        # Try contact pages
        for pattern in self.CONTACT_PAGES[:max_pages]:
            contact_url = f"{website.rstrip('/')}{pattern}"
            page_emails = await self._extract_from_page(contact_url)
            emails.update(page_emails)

        # Filter and prioritize
        filtered = self._filter_generic(list(emails))
        prioritized = self._prioritize_emails(filtered, website)

        return prioritized

    async def _extract_from_page(self, url: str) -> set:
        """Extract emails from single page."""
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return set()

            html = response.text
            emails = set()

            # Apply all patterns
            for pattern in self.PATTERNS:
                matches = re.findall(pattern, html, re.IGNORECASE)
                emails.update(matches)

            # Also check mailto: links
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('a', href=re.compile(r'^mailto:')):
                email = link['href'].replace('mailto:', '').strip()
                emails.add(email)

            return emails

        except Exception as e:
            logger.warning(f"Failed to extract from {url}: {e}")
            return set()

    def _filter_generic(self, emails: List[str]) -> List[str]:
        """Remove generic emails (info@, admin@, etc.)."""
        return [
            email for email in emails
            if not any(email.lower().startswith(prefix) for prefix in self.GENERIC_FILTERS)
        ]

    def _prioritize_emails(self, emails: List[str], website: str) -> List[str]:
        """
        Prioritize emails by likelihood of decision-maker.

        Priority order:
        1. Personal names (john.smith@, jane.doe@)
        2. Sales/business related (sales@, business@)
        3. Other valid emails
        """
        domain = website.replace('http://', '').replace('https://', '').split('/')[0]

        personal = []
        business = []
        other = []

        for email in emails:
            local_part = email.split('@')[0].lower()

            # Personal name patterns (firstname.lastname or firstname)
            if '.' in local_part or len(local_part.split('.')) > 1:
                personal.append(email)
            # Business-related
            elif any(keyword in local_part for keyword in ['sales', 'business', 'owner', 'ceo', 'president']):
                business.append(email)
            else:
                other.append(email)

        return personal + business + other
```

#### Integration Point

**File**: `backend/app/services/langgraph/agents/qualification_agent.py`

**Changes**:
```python
from app.services.email_extractor import EmailExtractor

class QualificationAgent:
    def __init__(self, ...):
        # ... existing init ...
        self.email_extractor = EmailExtractor()

    async def qualify(self, ...):
        # ... existing qualification logic ...

        # AFTER website validation, BEFORE review scraping:
        if company_website and not contact_email:
            logger.info(f"Attempting email extraction for {company_name}")
            extracted_emails = await self.email_extractor.extract_emails(company_website)

            if extracted_emails:
                contact_email = extracted_emails[0]  # Use top-priority email
                logger.info(f"Extracted {len(extracted_emails)} emails, using: {contact_email}")

                # Add to qualification notes
                qualification_notes += f"\nEmails found: {', '.join(extracted_emails[:3])}"
            else:
                logger.warning(f"No emails extracted from {company_website}")

        # ... continue with review scraping and LLM qualification ...
```

#### Testing

**File**: `backend/tests/services/test_email_extractor.py`

```python
import pytest
from app.services.email_extractor import EmailExtractor

@pytest.fixture
def sample_html_with_emails():
    return """
    <html>
        <body>
            <a href="mailto:john.smith@example.com">Contact John</a>
            <p>Email us at sales@example.com or info@example.com</p>
        </body>
    </html>
    """

@pytest.mark.asyncio
async def test_extract_emails_from_html(sample_html_with_emails):
    """Test basic email extraction."""
    extractor = EmailExtractor()
    emails = await extractor._extract_from_page_html(sample_html_with_emails)

    assert 'john.smith@example.com' in emails
    assert 'sales@example.com' in emails

@pytest.mark.asyncio
async def test_filter_generic_emails():
    """Test generic email filtering."""
    extractor = EmailExtractor()
    emails = ['john.smith@example.com', 'info@example.com', 'sales@example.com']
    filtered = extractor._filter_generic(emails)

    assert 'john.smith@example.com' in filtered
    assert 'sales@example.com' in filtered
    assert 'info@example.com' not in filtered

@pytest.mark.asyncio
async def test_prioritize_emails():
    """Test email prioritization."""
    extractor = EmailExtractor()
    emails = ['contact@example.com', 'john.doe@example.com', 'sales@example.com']
    prioritized = extractor._prioritize_emails(emails, 'https://example.com')

    # Personal names first
    assert prioritized[0] == 'john.doe@example.com'
    # Business-related second
    assert prioritized[1] == 'sales@example.com'
    # Other last
    assert prioritized[2] == 'contact@example.com'
```

**Integration Test**:
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
./run_sample_test.sh

# Expected results:
# - Qualification: Success (261-430ms)
# - Email extraction: 60-80% success rate
# - Enrichment: Success for leads with extracted emails
```

### Sub-Phase 2B: Hunter.io Integration (2-4 hours)

#### Architecture

**Fallback Strategy**: Try email extraction first → Hunter.io if no emails found

**Hunter.io Capabilities**:
- **Domain Search**: Find all emails for a domain
- **Email Finder**: Find specific person's email (requires first/last name)
- **Email Verifier**: Validate email deliverability

**API Pricing**: 50 requests/month free tier, $49/month for 500 requests

#### Implementation

**File**: `backend/app/services/hunter_service.py` (new file)

```python
"""Hunter.io email discovery service."""
import os
import httpx
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class HunterService:
    """Hunter.io API integration for email discovery."""

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY")
        if not self.api_key:
            logger.warning("HUNTER_API_KEY not set, Hunter.io disabled")
        self.client = httpx.AsyncClient()

    async def domain_search(
        self,
        domain: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Find all emails for a domain.

        Args:
            domain: Company domain (e.g., "example.com")
            limit: Maximum emails to return

        Returns:
            List of email dicts with: email, first_name, last_name, position, confidence
        """
        if not self.api_key:
            return []

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/domain-search",
                params={
                    "domain": domain,
                    "api_key": self.api_key,
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()

            emails = data.get("data", {}).get("emails", [])
            logger.info(f"Hunter.io found {len(emails)} emails for {domain}")

            return emails

        except Exception as e:
            logger.error(f"Hunter.io domain search failed for {domain}: {e}")
            return []

    async def find_email(
        self,
        domain: str,
        first_name: str,
        last_name: str
    ) -> Optional[str]:
        """
        Find specific person's email.

        Args:
            domain: Company domain
            first_name: Person's first name
            last_name: Person's last name

        Returns:
            Email if found, None otherwise
        """
        if not self.api_key:
            return None

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/email-finder",
                params={
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                    "api_key": self.api_key
                }
            )
            response.raise_for_status()
            data = response.json()

            email = data.get("data", {}).get("email")
            confidence = data.get("data", {}).get("score", 0)

            if email and confidence > 50:  # Only use high-confidence results
                logger.info(f"Hunter.io found {email} (confidence: {confidence})")
                return email

            return None

        except Exception as e:
            logger.error(f"Hunter.io email finder failed: {e}")
            return None

    def extract_domain(self, website: str) -> str:
        """Extract domain from website URL."""
        domain = website.replace('http://', '').replace('https://', '')
        domain = domain.split('/')[0]
        domain = domain.replace('www.', '')
        return domain
```

#### Integration with EmailExtractor

**File**: `backend/app/services/langgraph/agents/qualification_agent.py`

**Enhanced flow**:
```python
from app.services.email_extractor import EmailExtractor
from app.services.hunter_service import HunterService

class QualificationAgent:
    def __init__(self, ...):
        # ... existing init ...
        self.email_extractor = EmailExtractor()
        self.hunter_service = HunterService()

    async def qualify(self, ...):
        # ... existing qualification logic ...

        # Email discovery with fallback
        if company_website and not contact_email:
            # Phase 1: Try extraction (free, instant)
            logger.info(f"Attempting email extraction for {company_name}")
            extracted_emails = await self.email_extractor.extract_emails(company_website)

            if extracted_emails:
                contact_email = extracted_emails[0]
                logger.info(f"Extracted email: {contact_email}")
            else:
                # Phase 2: Try Hunter.io (costs API credit)
                logger.info(f"No extracted emails, trying Hunter.io for {company_name}")
                domain = self.hunter_service.extract_domain(company_website)
                hunter_emails = await self.hunter_service.domain_search(domain, limit=5)

                if hunter_emails:
                    # Prioritize by position (owner, ceo, president, sales)
                    for email_data in hunter_emails:
                        position = email_data.get('position', '').lower()
                        if any(title in position for title in ['owner', 'ceo', 'president', 'founder']):
                            contact_email = email_data['value']
                            logger.info(f"Hunter.io found decision-maker: {contact_email} ({position})")
                            break

                    # If no decision-maker, use first email
                    if not contact_email and hunter_emails:
                        contact_email = hunter_emails[0]['value']
                        logger.info(f"Hunter.io using first email: {contact_email}")
                else:
                    logger.warning(f"No emails found via extraction or Hunter.io for {company_name}")

        # ... continue with review scraping and LLM qualification ...
```

#### Cost Tracking for Hunter.io

Track Hunter.io API calls in `ai_cost_tracking` table:

```python
# After Hunter.io call
if hunter_emails:
    tracking = AICostTracking(
        agent_type='email_discovery',
        agent_mode='hunter_api',
        lead_id=lead_id,
        provider='hunter.io',
        model='domain_search',
        cost_usd=0.02,  # Approximate cost per call
        latency_ms=hunter_latency_ms,
        prompt_text=f"Domain: {domain}",
        completion_text=f"Found {len(hunter_emails)} emails"
    )
    db.add(tracking)
```

#### Testing

**Integration Test with Real API**:
```python
import pytest
from app.services.hunter_service import HunterService

@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("HUNTER_API_KEY"), reason="Hunter.io API key required")
async def test_hunter_domain_search_real():
    """Test Hunter.io domain search with real API."""
    hunter = HunterService()
    emails = await hunter.domain_search("stripe.com", limit=5)

    assert len(emails) > 0
    assert all('value' in email for email in emails)
    assert all('first_name' in email for email in emails)

@pytest.mark.asyncio
async def test_hunter_fallback_when_no_key():
    """Test graceful degradation without API key."""
    os.environ.pop("HUNTER_API_KEY", None)
    hunter = HunterService()
    emails = await hunter.domain_search("example.com")

    assert emails == []  # Should return empty list, not crash
```

**End-to-End Pipeline Test**:
```bash
# Set Hunter.io API key
export HUNTER_API_KEY="your_key_here"

# Run sample test (should now complete enrichment)
./run_sample_test.sh

# Expected results:
# - Qualification: Success (261-430ms)
# - Email extraction: 60-80% success
# - Hunter.io fallback: 15-30% of remaining
# - Enrichment: 75-95% success rate (up from 0%)
```

#### Environment Variables

**File**: `.env`

```bash
# Email Discovery (Phase 2)
HUNTER_API_KEY=your_hunter_api_key_here  # 50 free requests/month
```

**File**: `backend/README.md` (update)

```markdown
## Email Discovery

Automatic email extraction from company websites with Hunter.io fallback:

```python
# Extraction (free, 60-80% success)
extracted_emails = await email_extractor.extract_emails(website)

# Fallback to Hunter.io (costs API credit, 90%+ success)
hunter_emails = await hunter_service.domain_search(domain)
```

Set `HUNTER_API_KEY` in `.env` for fallback functionality.
```

### Phase 2 Success Criteria

- ✅ EmailExtractor class implemented and tested
- ✅ 60-80% email extraction success rate on contractor test set
- ✅ Hunter.io integration functional with fallback logic
- ✅ 75-95% combined email discovery success rate
- ✅ Enrichment agent no longer fails with VALIDATION_ERROR
- ✅ Pipeline test completes successfully end-to-end
- ✅ Cost tracking captures Hunter.io API usage

---

## Phase 3: Frontend Cost Analytics Dashboard (6-10 hours)

### Objective

Build React dashboards for real-time cost visibility and pipeline monitoring, enabling data-driven optimization decisions.

### Current State

**Backend APIs Ready**:
- `GET /api/v1/analytics/ai-costs` - Complete analytics endpoint
- Returns: total_cost, by_agent, by_lead, cache_stats, time_series
- Query params: agent_type, start_date, end_date, lead_id

**Frontend Stack Configured**:
- React 18 + TypeScript
- Tailwind v4
- Vite build tool
- React Router

### Architecture

**New Route Structure**:
```
/dashboard              → Overview (redirects to cost analytics)
/dashboard/costs        → Cost Analytics Dashboard
/dashboard/pipeline     → Pipeline Visualization Dashboard
```

**Component Hierarchy**:
```
App
├── DashboardLayout (navigation, header)
│   ├── CostAnalyticsDashboard
│   │   ├── SummaryCards (4 metrics)
│   │   ├── CostTrendChart (7-day line chart)
│   │   ├── AgentBreakdownChart (bar chart)
│   │   └── ExpensiveLeadsTable (top 10)
│   └── PipelineDashboard
│       ├── PipelineFunnel (conversion stages)
│       └── ActivityFeed (recent actions)
```

### Dashboard 1: Cost Analytics (Priority 1)

#### Layout Design

**Visual Mockup**:
```
┌────────────────────────────────────────────────────────────┐
│  Sales Agent - Cost Analytics                   [Refresh]  │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Total    │  │ Avg/Lead │  │ Daily    │  │ Savings  │  │
│  │ $42.18   │  │ $0.021   │  │ $6.03    │  │ 68%      │  │
│  │ ▲ 12%    │  │ ▼ 5%     │  │ ▲ 8%     │  │ ▲ 3%     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Cost Trend (Last 7 Days)                             │  │
│  │                                          ╱            │  │
│  │                                    ╱────╱             │  │
│  │              ╱────╱────╱────╱────╱                   │  │
│  │  ╱────╱────╱                                          │  │
│  │ Mon  Tue  Wed  Thu  Fri  Sat  Sun                    │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Cost by Agent Type                                    │  │
│  │ qualification    ████████████ $18.50 (44%)           │  │
│  │ enrichment       ████████ $12.30 (29%)               │  │
│  │ sr_bdr           ████ $6.20 (15%)                    │  │
│  │ growth           ██ $3.18 (8%)                       │  │
│  │ marketing        █ $2.00 (5%)                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Top 10 Most Expensive Leads                           │  │
│  │ Company               Cost    Agents Used    Actions  │  │
│  │ ACS Commercial       $0.145   qual,enrich    [View]  │  │
│  │ Freedom Services     $0.138   qual,enrich    [View]  │  │
│  │ ABC Services         $0.132   qual,enrich    [View]  │  │
│  │ ...                                                    │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

#### Implementation

**File**: `frontend/src/pages/CostAnalyticsDashboard.tsx`

```typescript
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { SummaryCard } from '../components/SummaryCard';
import { CostTrendChart } from '../components/CostTrendChart';
import { AgentBreakdownChart } from '../components/AgentBreakdownChart';
import { ExpensiveLeadsTable } from '../components/ExpensiveLeadsTable';
import { fetchCostAnalytics } from '../api/analytics';

export const CostAnalyticsDashboard: React.FC = () => {
  // Fetch cost analytics data
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['costAnalytics'],
    queryFn: () => fetchCostAnalytics({
      start_date: getSevenDaysAgo(),
      end_date: getToday()
    }),
    refetchInterval: 30000 // Auto-refresh every 30 seconds
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const {
    total_cost_usd,
    total_requests,
    by_agent,
    by_lead,
    cache_stats,
    time_series
  } = data;

  // Calculate metrics
  const avgCostPerLead = total_cost_usd / (by_lead?.length || 1);
  const dailyRate = time_series?.[time_series.length - 1]?.total_cost_usd || 0;
  const cacheSavings = cache_stats?.cache_hit_rate * 100 || 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Cost Analytics</h1>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Spend"
          value={`$${total_cost_usd.toFixed(2)}`}
          change={12}
          trend="up"
        />
        <SummaryCard
          title="Avg per Lead"
          value={`$${avgCostPerLead.toFixed(3)}`}
          change={-5}
          trend="down"
        />
        <SummaryCard
          title="Daily Rate"
          value={`$${dailyRate.toFixed(2)}`}
          change={8}
          trend="up"
        />
        <SummaryCard
          title="Cache Savings"
          value={`${cacheSavings.toFixed(0)}%`}
          change={3}
          trend="up"
        />
      </div>

      {/* Cost Trend Chart */}
      <CostTrendChart data={time_series} />

      {/* Agent Breakdown */}
      <AgentBreakdownChart data={by_agent} />

      {/* Expensive Leads Table */}
      <ExpensiveLeadsTable leads={by_lead?.slice(0, 10)} />
    </div>
  );
};
```

**File**: `frontend/src/components/SummaryCard.tsx`

```typescript
import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface SummaryCardProps {
  title: string;
  value: string;
  change: number;
  trend: 'up' | 'down';
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  value,
  change,
  trend
}) => {
  const isPositive = (trend === 'up' && change > 0) || (trend === 'down' && change < 0);
  const TrendIcon = trend === 'up' ? TrendingUp : TrendingDown;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-sm font-medium text-gray-600 mb-2">{title}</h3>
      <div className="flex items-baseline justify-between">
        <p className="text-3xl font-bold">{value}</p>
        <div className={`flex items-center text-sm ${
          isPositive ? 'text-green-600' : 'text-red-600'
        }`}>
          <TrendIcon className="w-4 h-4 mr-1" />
          {Math.abs(change)}%
        </div>
      </div>
    </div>
  );
};
```

**File**: `frontend/src/components/CostTrendChart.tsx`

```typescript
import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface CostTrendChartProps {
  data: Array<{
    date: string;
    total_cost_usd: number;
    total_requests: number;
  }>;
}

export const CostTrendChart: React.FC<CostTrendChartProps> = ({ data }) => {
  const chartData = {
    labels: data.map(d => new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' })),
    datasets: [
      {
        label: 'Daily Spend',
        data: data.map(d => d.total_cost_usd),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4
      }
    ]
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        display: false
      },
      title: {
        display: true,
        text: 'Cost Trend (Last 7 Days)'
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value: number) => `$${value.toFixed(2)}`
        }
      }
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <Line data={chartData} options={options} />
    </div>
  );
};
```

**File**: `frontend/src/components/AgentBreakdownChart.tsx`

```typescript
import React from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface AgentBreakdownChartProps {
  data: Array<{
    agent_type: string;
    agent_mode: string;
    total_cost_usd: number;
    total_requests: number;
  }>;
}

export const AgentBreakdownChart: React.FC<AgentBreakdownChartProps> = ({ data }) => {
  const sortedData = [...data].sort((a, b) => b.total_cost_usd - a.total_cost_usd);

  const chartData = {
    labels: sortedData.map(d => d.agent_type),
    datasets: [
      {
        label: 'Cost (USD)',
        data: sortedData.map(d => d.total_cost_usd),
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
      }
    ]
  };

  const options = {
    indexAxis: 'y' as const,
    responsive: true,
    plugins: {
      legend: {
        display: false
      },
      title: {
        display: true,
        text: 'Cost by Agent Type'
      }
    },
    scales: {
      x: {
        beginAtZero: true,
        ticks: {
          callback: (value: number) => `$${value.toFixed(2)}`
        }
      }
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <Bar data={chartData} options={options} />
    </div>
  );
};
```

**File**: `frontend/src/components/ExpensiveLeadsTable.tsx`

```typescript
import React from 'react';
import { Eye } from 'lucide-react';

interface Lead {
  lead_id: number;
  company_name: string;
  total_cost_usd: number;
  total_requests: number;
  agents_used: string[];
}

interface ExpensiveLeadsTableProps {
  leads: Lead[];
}

export const ExpensiveLeadsTable: React.FC<ExpensiveLeadsTableProps> = ({ leads }) => {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold">Top 10 Most Expensive Leads</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Company
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Total Cost
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Agents Used
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {leads?.map((lead) => (
              <tr key={lead.lead_id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">
                    {lead.company_name}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    ${lead.total_cost_usd.toFixed(4)}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {lead.agents_used.map((agent) => (
                      <span
                        key={agent}
                        className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded"
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    onClick={() => window.location.href = `/leads/${lead.lead_id}`}
                    className="text-blue-600 hover:text-blue-900 flex items-center"
                  >
                    <Eye className="w-4 h-4 mr-1" />
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```

**File**: `frontend/src/api/analytics.ts`

```typescript
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api/v1';

export interface CostAnalyticsParams {
  agent_type?: string;
  start_date?: string;
  end_date?: string;
  lead_id?: number;
}

export interface CostAnalyticsResponse {
  total_cost_usd: number;
  total_requests: number;
  by_agent: Array<{
    agent_type: string;
    agent_mode: string;
    total_requests: number;
    total_cost_usd: number;
    avg_cost_per_request: number;
    avg_latency_ms: number;
    primary_provider: string;
    primary_model: string;
  }>;
  by_lead: Array<{
    lead_id: number;
    company_name: string;
    total_cost_usd: number;
    total_requests: number;
    agents_used: string[];
  }>;
  cache_stats: {
    total_requests: number;
    cache_hits: number;
    cache_hit_rate: number;
    estimated_savings_usd: number;
  };
  time_series: Array<{
    date: string;
    total_cost_usd: number;
    total_requests: number;
  }>;
}

export async function fetchCostAnalytics(
  params: CostAnalyticsParams = {}
): Promise<CostAnalyticsResponse> {
  const response = await axios.get(`${API_BASE}/analytics/ai-costs`, { params });
  return response.data;
}
```

**File**: `frontend/src/hooks/useCostAnalytics.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchCostAnalytics, CostAnalyticsParams } from '../api/analytics';

export function useCostAnalytics(params: CostAnalyticsParams = {}) {
  return useQuery({
    queryKey: ['costAnalytics', params],
    queryFn: () => fetchCostAnalytics(params),
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 20000
  });
}
```

### Dashboard 2: Pipeline Visualization (Priority 2)

#### Layout Design

**Visual Mockup**:
```
┌────────────────────────────────────────────────────────────┐
│  Sales Agent - Pipeline Flow                    [Refresh]  │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Pipeline Funnel (Last 7 Days)                              │
│                                                              │
│  ████████████████████████ 1000 Qualified (100%)            │
│  ██████████████████ 850 Enriched (85%)                     │
│  ██████████ 420 Contacted (42%)                            │
│  ██ 85 Won (8.5%)                                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Conversion Rates                                      │  │
│  │ Qualified → Enriched:   85% (target: 90%)            │  │
│  │ Enriched → Contacted:   49% (target: 50%)            │  │
│  │ Contacted → Won:        20% (target: 15%) ✓          │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Recent Activity                                        │  │
│  │ • ACS COMMERCIAL qualified (score: 45) - 2m ago      │  │
│  │ • FREEDOM SERVICES enriched - 5m ago                 │  │
│  │ • ABC HOME contacted - 12m ago                       │  │
│  │ • NJR SERVICES qualified (score: 45) - 15m ago      │  │
│  │ • ABLE BUSINESS qualified (score: 40) - 18m ago     │  │
│  │ [Load More...]                                         │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

#### Implementation

**File**: `frontend/src/pages/PipelineDashboard.tsx`

```typescript
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { PipelineFunnel } from '../components/PipelineFunnel';
import { ActivityFeed } from '../components/ActivityFeed';
import { fetchPipelineData } from '../api/pipeline';

export const PipelineDashboard: React.FC = () => {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['pipelineData'],
    queryFn: fetchPipelineData,
    refetchInterval: 30000
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Pipeline Flow</h1>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      <PipelineFunnel data={data.funnel} />
      <ActivityFeed activities={data.recent_activities} />
    </div>
  );
};
```

**File**: `frontend/src/components/PipelineFunnel.tsx`

```typescript
import React from 'react';

interface FunnelStage {
  stage: string;
  count: number;
  percentage: number;
}

interface PipelineFunnelProps {
  data: FunnelStage[];
}

export const PipelineFunnel: React.FC<PipelineFunnelProps> = ({ data }) => {
  const maxCount = data[0]?.count || 1;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-6">Pipeline Funnel (Last 7 Days)</h2>
      <div className="space-y-4">
        {data.map((stage, index) => {
          const width = (stage.count / maxCount) * 100;
          const colors = ['bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-purple-500'];

          return (
            <div key={stage.stage} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{stage.stage}</span>
                <span className="text-gray-600">
                  {stage.count} ({stage.percentage.toFixed(1)}%)
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-8">
                <div
                  className={`${colors[index % colors.length]} h-8 rounded-full flex items-center justify-end pr-4 text-white font-medium`}
                  style={{ width: `${width}%` }}
                >
                  {stage.count}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
```

**File**: `frontend/src/components/ActivityFeed.tsx`

```typescript
import React from 'react';
import { CheckCircle, Mail, Phone, Trophy } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface Activity {
  id: number;
  type: 'qualified' | 'enriched' | 'contacted' | 'won';
  company_name: string;
  details: string;
  timestamp: string;
}

interface ActivityFeedProps {
  activities: Activity[];
}

const ICONS = {
  qualified: CheckCircle,
  enriched: Mail,
  contacted: Phone,
  won: Trophy
};

const COLORS = {
  qualified: 'text-blue-600',
  enriched: 'text-green-600',
  contacted: 'text-yellow-600',
  won: 'text-purple-600'
};

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ activities }) => {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold">Recent Activity</h2>
      </div>
      <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
        {activities.map((activity) => {
          const Icon = ICONS[activity.type];
          const colorClass = COLORS[activity.type];

          return (
            <div key={activity.id} className="px-6 py-4 hover:bg-gray-50 flex items-start">
              <Icon className={`w-5 h-5 mt-0.5 mr-3 ${colorClass}`} />
              <div className="flex-1">
                <p className="text-sm">
                  <span className="font-medium">{activity.company_name}</span>{' '}
                  {activity.details}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {formatDistanceToNow(new Date(activity.timestamp), { addSuffix: true })}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
```

**File**: `frontend/src/api/pipeline.ts`

```typescript
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api/v1';

export interface PipelineData {
  funnel: Array<{
    stage: string;
    count: number;
    percentage: number;
  }>;
  recent_activities: Array<{
    id: number;
    type: 'qualified' | 'enriched' | 'contacted' | 'won';
    company_name: string;
    details: string;
    timestamp: string;
  }>;
}

export async function fetchPipelineData(): Promise<PipelineData> {
  // Combine data from multiple endpoints
  const [costData, leads] = await Promise.all([
    axios.get(`${API_BASE}/analytics/ai-costs`),
    axios.get(`${API_BASE}/leads`)
  ]);

  // Calculate funnel stages from cost tracking data
  const qualified = costData.data.by_agent.find(a => a.agent_type === 'qualification')?.total_requests || 0;
  const enriched = costData.data.by_agent.find(a => a.agent_type === 'enrichment')?.total_requests || 0;

  // Get contacted/won from leads table
  const contacted = leads.data.filter(l => l.status === 'contacted').length;
  const won = leads.data.filter(l => l.status === 'won').length;

  return {
    funnel: [
      { stage: 'Qualified', count: qualified, percentage: 100 },
      { stage: 'Enriched', count: enriched, percentage: (enriched / qualified) * 100 },
      { stage: 'Contacted', count: contacted, percentage: (contacted / qualified) * 100 },
      { stage: 'Won', count: won, percentage: (won / qualified) * 100 }
    ],
    recent_activities: leads.data.slice(0, 10).map((lead, i) => ({
      id: i,
      type: lead.status,
      company_name: lead.company_name,
      details: `score: ${lead.qualification_score}`,
      timestamp: lead.updated_at
    }))
  };
}
```

### Routing and Navigation

**File**: `frontend/src/App.tsx`

```typescript
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { CostAnalyticsDashboard } from './pages/CostAnalyticsDashboard';
import { PipelineDashboard } from './pages/PipelineDashboard';

const queryClient = new QueryClient();

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard/costs" replace />} />
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route path="costs" element={<CostAnalyticsDashboard />} />
            <Route path="pipeline" element={<PipelineDashboard />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
```

**File**: `frontend/src/layouts/DashboardLayout.tsx`

```typescript
import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { DollarSign, TrendingUp } from 'lucide-react';

export const DashboardLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold">Sales Agent</h1>
              </div>
              <div className="ml-6 flex space-x-8">
                <NavLink
                  to="/dashboard/costs"
                  className={({ isActive }) =>
                    `inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      isActive
                        ? 'border-blue-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300'
                    }`
                  }
                >
                  <DollarSign className="w-4 h-4 mr-2" />
                  Cost Analytics
                </NavLink>
                <NavLink
                  to="/dashboard/pipeline"
                  className={({ isActive }) =>
                    `inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      isActive
                        ? 'border-blue-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300'
                    }`
                  }
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Pipeline Flow
                </NavLink>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6">
        <Outlet />
      </main>
    </div>
  );
};
```

### Testing

**File**: `frontend/src/__tests__/CostAnalyticsDashboard.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CostAnalyticsDashboard } from '../pages/CostAnalyticsDashboard';
import { fetchCostAnalytics } from '../api/analytics';

jest.mock('../api/analytics');

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } }
});

const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('CostAnalyticsDashboard', () => {
  it('renders summary cards with data', async () => {
    (fetchCostAnalytics as jest.Mock).mockResolvedValue({
      total_cost_usd: 42.18,
      total_requests: 2000,
      by_agent: [],
      by_lead: [],
      cache_stats: { cache_hit_rate: 0.23 },
      time_series: []
    });

    render(<CostAnalyticsDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('$42.18')).toBeInTheDocument();
      expect(screen.getByText('23%')).toBeInTheDocument(); // Cache savings
    });
  });

  it('shows loading state initially', () => {
    (fetchCostAnalytics as jest.Mock).mockReturnValue(new Promise(() => {}));

    render(<CostAnalyticsDashboard />, { wrapper });

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });
});
```

### Dependencies

**File**: `frontend/package.json` (add)

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "chart.js": "^4.4.0",
    "react-chartjs-2": "^5.2.0",
    "date-fns": "^3.0.0",
    "lucide-react": "^0.300.0"
  }
}
```

Install:
```bash
cd frontend
npm install
```

### Development Server

```bash
cd frontend
npm run dev  # Start Vite dev server on http://localhost:5173
```

### Phase 3 Success Criteria

- ✅ Cost Analytics Dashboard renders with real backend data
- ✅ Summary cards show accurate metrics (total spend, avg/lead, daily rate, cache savings)
- ✅ Cost trend chart displays 7-day historical data
- ✅ Agent breakdown chart shows cost by agent type
- ✅ Expensive leads table lists top 10 by cost
- ✅ Pipeline Dashboard displays funnel with conversion rates
- ✅ Activity feed shows recent lead actions
- ✅ Auto-refresh working (30-second interval)
- ✅ Navigation between dashboards functional
- ✅ Responsive layout works on mobile/tablet/desktop

---

## Success Metrics (Overall Project)

### Phase 1 Metrics
- ✅ 2 branches merged without conflicts
- ✅ All tests passing (96%+ coverage maintained)
- ✅ No performance regressions (<1ms cost tracking overhead)

### Phase 2 Metrics
- ✅ 75-95% combined email discovery success rate
- ✅ Enrichment validation error resolved
- ✅ End-to-end pipeline test completes successfully
- ✅ Hunter.io API cost tracked in analytics

### Phase 3 Metrics
- ✅ Real-time cost visibility achieved (<30s refresh)
- ✅ All 4 priority metrics displayed (total, avg/lead, daily, savings)
- ✅ Pipeline conversion rates tracked
- ✅ User can identify cost optimization opportunities

### Production Readiness
- ✅ Complete AI cost visibility across all 9 agents
- ✅ Email discovery enabling 75-95% enrichment success
- ✅ Frontend dashboards for data-driven decisions
- ✅ Zero performance regression maintained
- ✅ <$0.05 cost per lead target achieved

---

## Risk Mitigation

### Phase 1 Risks
**Risk**: Merge conflicts between branches
**Mitigation**: Sequential merge with validation between. Revert capability via git.

**Risk**: Tests fail after merge
**Mitigation**: Comprehensive pytest suite runs before/after. Rollback plan documented.

### Phase 2 Risks
**Risk**: Email extraction success rate too low (<60%)
**Mitigation**: Hunter.io fallback provides 90%+ success for missed cases.

**Risk**: Hunter.io costs exceed budget
**Mitigation**: Track usage in analytics. Set monthly limit (50 free, then $49 for 500).

**Risk**: Extracted emails are generic (info@, admin@)
**Mitigation**: Smart filtering and prioritization logic. Personal names ranked first.

### Phase 3 Risks
**Risk**: Backend API too slow for real-time dashboard
**Mitigation**: Analytics endpoint already optimized (<500ms). Add caching if needed.

**Risk**: Chart.js bundle size too large
**Mitigation**: Use code splitting. Lazy load charts. Target <100KB additional bundle.

**Risk**: Data refresh causes UI flicker
**Mitigation**: Use React Query optimistic updates. Smooth transitions with CSS.

---

## Timeline Summary

| Phase | Description | Estimated Time | Dependencies |
|-------|-------------|----------------|--------------|
| **1** | Merge pipeline-testing + claude-agent-sdk | 1-2 hours | None |
| **2A** | Email extraction implementation | 4-6 hours | Phase 1 complete |
| **2B** | Hunter.io integration | 2-4 hours | Phase 2A complete |
| **3** | Frontend dashboards (costs + pipeline) | 6-10 hours | Phase 1 complete (Phase 2 optional) |
| **Total** | All three phases complete | **13-22 hours** (~2-3 days) | Sequential execution |

---

## Next Steps

After design validation:
1. Create implementation plan with writing-plans skill
2. Set up git worktree for Option 2 work (if not using main directly)
3. Execute phases sequentially with validation checkpoints

**Ready to proceed with implementation planning?**
