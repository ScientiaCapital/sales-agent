# Pipeline Cleanup & Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up enrichment pipeline, review contact quality, audit scraper scripts, and update dependencies.

**Architecture:** Parallel execution of independent review tasks (Tasks 1-3) with a serialized dependency update (Task 4). Each task uses a specialized agent with code review gates.

**Tech Stack:** Python 3.11 | Supabase | BeautifulSoup | Browserbase

---

## Execution Strategy

```
Phase 1 (PARALLEL):
├── Task 1: FAILED_ENRICHMENT retry       [Explore agent]
├── Task 2: Contact quality audit         [database-design:sql-pro agent]
└── Task 3: Scraper script audit          [feature-dev:code-reviewer agent]

Phase 2 (SERIAL, after Phase 1):
└── Task 4: Dependency updates            [python-development:python-pro agent]

Review Gates:
├── Gate 1: After each parallel task completes
├── Gate 2: Before committing any changes
└── Gate 3: After dependency updates (run tests)
```

---

## Task 1: Retry FAILED_ENRICHMENT Candidates

**Agent:** `Explore` (quick)
**Estimated Effort:** 5 minutes
**Parallelizable:** Yes

**Files:**
- Read: `backend/data/final_enrichment_output/FAILED_ENRICHMENT.csv`
- Modify: None (assessment only)

### Current Status
Only 1 failed company: `EnerWealth Solutions` (enerwealthsol.com)
- Error: `BrowserType.connect_over_cdp: WebSocket error: 500 Internal Server`
- Cause: Browserbase infrastructure issue (not our code)

### Step 1: Verify domain is still valid

```bash
curl -I -L https://enerwealthsol.com 2>&1 | head -20
```

Expected: HTTP 200 or redirect chain

### Step 2: Decision

| If Result | Action |
|-----------|--------|
| Domain responds | Add to retry queue - Browserbase was temporarily down |
| Domain 404/timeout | Remove from pipeline - company may be defunct |
| Domain redirects | Update domain in Supabase if redirect is permanent |

### Step 3: Execute retry (if valid)

```bash
cd backend
python run_enrichment.py --company-id 1d651c74-cf1e-455c-9ff2-abde4548adf9
```

**Review Gate 1:** Report findings before any action.

---

## Task 2: Contact Quality Audit (2,749 Contacts)

**Agent:** `database-design:sql-pro`
**Estimated Effort:** 15 minutes
**Parallelizable:** Yes

**Files:**
- Query: Supabase `dim_contacts` table
- Create: `backend/data/contact_quality_audit_20251215.csv` (export)

### Step 1: Run quality assessment query

```sql
-- Count contacts by quality indicators
SELECT
    CASE
        WHEN title ILIKE '%owner%' OR title ILIKE '%ceo%' OR title ILIKE '%president%' THEN 'ATL-Executive'
        WHEN title ILIKE '%director%' OR title ILIKE '%vp%' OR title ILIKE '%manager%' THEN 'ATL-Manager'
        WHEN title ILIKE '%tech%' OR title ILIKE '%install%' OR title ILIKE '%dispatch%' THEN 'BTL-Operations'
        WHEN title IS NULL OR title = '' THEN 'NO-TITLE'
        ELSE 'OTHER'
    END as contact_tier,
    COUNT(*) as count
FROM dim_contacts
GROUP BY contact_tier
ORDER BY count DESC;
```

### Step 2: Identify garbage ATLs

```sql
-- Find garbage entries (navigation text, service terms, legal text)
SELECT contact_id, name, title, phone, email, company_id
FROM dim_contacts
WHERE
    -- Navigation garbage
    name ILIKE '%schedule%' OR name ILIKE '%call now%' OR name ILIKE '%get quote%'
    OR name ILIKE '%privacy%' OR name ILIKE '%terms%' OR name ILIKE '%copyright%'
    -- Single word names (likely garbage)
    OR (name NOT LIKE '% %' AND LENGTH(name) < 4)
    -- All caps (likely headers)
    OR name = UPPER(name) AND LENGTH(name) > 3
ORDER BY name;
```

### Step 3: Export garbage candidates for review

```bash
# Run via Supabase SQL editor or psql
# Export to CSV for human review
```

### Step 4: Generate cleanup script (DO NOT EXECUTE without approval)

```python
# backend/clean_garbage_contacts.py already exists
# Review its logic before running
python backend/clean_garbage_contacts.py --dry-run
```

**Review Gate 2:** Present garbage count and sample before any deletion.

---

## Task 3: Scraper Script Production-Readiness Audit

**Agent:** `feature-dev:code-reviewer`
**Estimated Effort:** 20 minutes
**Parallelizable:** Yes

**Files:**
- Audit: `backend/push_dealer_leads.py`
- Audit: `backend/scrape_amicus_members.py`
- Audit: `backend/scrape_spw_lists.py`
- Audit: `shared/` directory

### Audit Checklist

For each script, verify:

| Criterion | Check |
|-----------|-------|
| No hardcoded API keys | `grep -r "sk-" file` returns empty |
| Uses .env for secrets | `load_dotenv()` called |
| Has dry-run mode | `--dry-run` flag implemented |
| Error handling | try/except with logging |
| Rate limiting | Delays between requests |
| Duplicate prevention | Checks existing records before insert |
| Logging (no print) | Uses `logging` module |
| Type hints | Function signatures typed |
| Docstrings | Module and function docs |

### Step 1: Run security scan

```bash
# Check for hardcoded secrets
grep -rn "sk-\|api_key\s*=\s*['\"]" backend/push_dealer_leads.py backend/scrape_amicus_members.py backend/scrape_spw_lists.py
```

Expected: No matches (all from .env)

### Step 2: Audit push_dealer_leads.py

**Current Assessment:**
- Uses `load_dotenv()`
- Has `--dry-run` flag
- Checks existing domains before insert
- Batch inserts with error recovery
- Missing: logging module (uses print)
- Missing: type hints

**Verdict:** Production-ready with minor improvements

### Step 3: Audit scrape_amicus_members.py

**Review for:**
- BeautifulSoup + httpx usage
- Browserbase fallback for JS pages
- Supabase integration
- Rate limiting between requests

### Step 4: Audit scrape_spw_lists.py

**Review for:**
- Same criteria as amicus scraper
- Multiple list URL support
- `--limit` flag for testing

### Step 5: Audit shared/ module

```bash
ls -la shared/
# Check structure:
# - agents/    - Shared agent definitions
# - audit/     - Audit utilities
# - config/    - Configuration management
# - providers/ - Provider abstractions
```

**Review Gate 3:** Present audit findings with recommendation matrix.

---

## Task 4: Dependency Updates

**Agent:** `python-development:python-pro`
**Estimated Effort:** 15 minutes
**Parallelizable:** No (run after Phase 1)

**Files:**
- Modify: `requirements.txt` or `pyproject.toml`
- Run: Test suite

### Step 1: Check current versions

```bash
pip list | grep -E "anthropic|celery"
```

### Step 2: Review changelogs

| Package | Current | Target | Breaking Changes |
|---------|---------|--------|------------------|
| anthropic | 0.64.x | 0.75.x | Check migration guide |
| celery | 5.4.x | 5.6.x | Check release notes |

### Step 3: Update in isolated environment

```bash
pip install anthropic==0.75.0 celery==5.6.0
```

### Step 4: Run test suite

```bash
pytest -v --tb=short
```

Expected: All 145 tests pass

### Step 5: Commit if tests pass

```bash
git add requirements.txt
git commit -m "chore: update anthropic 0.64→0.75, celery 5.4→5.6"
```

**Review Gate 4:** Show test results before commit.

---

## Commit Strategy

| Phase | Commit | Message |
|-------|--------|---------|
| After Task 1 | Optional | `fix: retry failed enrichment for EnerWealth Solutions` |
| After Task 2 | If cleanup | `chore: remove N garbage contacts from dim_contacts` |
| After Task 3 | If ready | `feat: add dealer/amicus/spw scrapers and shared module` |
| After Task 4 | Required | `chore: update anthropic 0.64→0.75, celery 5.4→5.6` |

---

## Execution Command

```bash
# Phase 1: Launch 3 parallel agents
Task 1: Explore agent → FAILED_ENRICHMENT assessment
Task 2: sql-pro agent → Contact quality audit
Task 3: code-reviewer agent → Scraper script audit

# Gate 1: Review all Phase 1 outputs

# Phase 2: Serial execution
Task 4: python-pro agent → Dependency updates

# Gate 2: Final review and commit
```
