# Contact Quality Prevention Strategy
**Focus:** Reduce garbage contacts from 1.5-3% to < 0.5%
**Timeline:** Implementation over next 2-3 sprints

---

## Current State Analysis

### Problem Identification
- **Symptom:** 7-15 garbage entries among 476 ATL contacts (1.5-3% error rate)
- **Root Causes:**
  1. BeautifulSoup scraper captures navigation text alongside real names
  2. No input validation before storing contacts in database
  3. Placeholder/test names not filtered during import
  4. Concatenated names from scraper output not detected early
  5. Confidence scores not properly calibrated for filtering

### Cost of Garbage Data
- **Sales Impact:** BDRs waste time researching fake contacts
- **Email Impact:** Undeliverable emails waste email credits
- **System Impact:** Invalid contacts cause parsing errors downstream
- **Reputation:** Automated systems reaching out to "Schedule Now" hurts credibility

---

## Prevention Strategy Overview

```
TIER 1: INPUT VALIDATION (Prevent at scrape time) - HIGHEST IMPACT
  ├─ Validate names before storing (BeautifulSoup scraper)
  ├─ Reject known garbage patterns
  └─ Set minimum confidence thresholds

TIER 2: IMPORT QUALITY GATES (Prevent at import time) - HIGH IMPACT
  ├─ Validate CSV imports
  ├─ Test data detection
  └─ Deduplication checks

TIER 3: RUNTIME QUALITY FILTERS (Prevent at usage time) - MEDIUM IMPACT
  ├─ Confidence-based filtering in queries
  ├─ Quality metrics dashboard
  └─ Automated alerts for high garbage rates

TIER 4: CLEANUP AUTOMATION (Reactive fallback) - LOW IMPACT
  ├─ Scheduled garbage cleanup
  ├─ Audit trails for debugging
  └─ Quality metrics tracking
```

---

## Tier 1: Input Validation (HIGHEST PRIORITY)

### 1.1 Enhance BeautifulSoup Scraper

**File:** `backend/app/services/beautifulsoup_team_scraper.py`

**Current State:**
- Scrapes team pages and extracts names
- No validation before returning names
- Low confidence entries mixed with high confidence

**Proposed Changes:**

#### Add Name Validation Function
```python
def is_valid_contact_name(name: str, min_length: int = 3) -> tuple[bool, str]:
    """
    Validate a scraped name before storing.

    Returns: (is_valid, reason)
    """
    if not name or not name.strip():
        return False, "empty_name"

    name = name.strip()

    # Length checks
    if len(name) < min_length:
        return False, f"too_short (< {min_length})"
    if len(name) > 50:
        return False, "too_long (> 50 chars)"

    # Garbage pattern checks
    if is_garbage_pattern(name):
        return False, "garbage_pattern"

    # Case checks (names should start uppercase)
    if not name[0].isupper():
        return False, "starts_lowercase"

    # Space checks (should have at least one space for "First Last")
    if ' ' not in name.strip() and len(name) > 15:
        return False, "no_spaces_long_name"

    # Role concatenation checks
    if has_concatenated_role(name):
        return False, "concatenated_role"

    return True, "valid"


def is_garbage_pattern(name: str) -> bool:
    """Check against known garbage patterns."""
    garbage_patterns = [
        r'^(schedule|call|contact|click|learn|view|see|read|get|our|the|your|my|home|about|services?)$',
        r'^(heating|cooling|plumbing|electrical|hvac|solar|roofing|air|water)$',
        r'(privacy|policy|terms|copyright|reserved|rights)',
        r'(facebook|twitter|linkedin|instagram|youtube|tiktok)',
        r'^(mr|mrs|ms|dr)\.?$',
        r'^\d+$',
        r'^[a-z]$',
    ]

    name_lower = name.lower().strip()
    for pattern in garbage_patterns:
        if re.search(pattern, name_lower):
            return True
    return False


def has_concatenated_role(name: str) -> bool:
    """Check for concatenated roles (e.g., 'JohnCEO')."""
    role_pattern = r'\w+(CEO|CFO|CTO|COO|CMO|VP|Director|Manager|Owner|President|Technician)$'
    return bool(re.search(role_pattern, name))
```

#### Integrate into Scraper Output
```python
class BeautifulSoupTeamScraper:
    async def scrape_team_page(self, url: str) -> List[ContactData]:
        """Scrape team page and validate results."""
        raw_contacts = await self._extract_names(url)

        validated_contacts = []
        rejected_contacts = []

        for contact in raw_contacts:
            is_valid, reason = is_valid_contact_name(contact.full_name)

            if is_valid:
                # Boost confidence for validated names
                contact.confidence = min(100, contact.confidence + 10)
                validated_contacts.append(contact)
            else:
                # Track rejection reason
                contact.validation_error = reason
                rejected_contacts.append(contact)
                logger.info(f"Rejected name: '{contact.full_name}' - {reason}")

        # Log rejection rate
        rejection_rate = len(rejected_contacts) / len(raw_contacts) * 100
        logger.info(f"Scrape validation: {len(validated_contacts)} valid, "
                   f"{len(rejected_contacts)} rejected ({rejection_rate:.1f}%)")

        return validated_contacts
```

#### Set Minimum Confidence Threshold
```python
class BeautifulSoupTeamScraper:
    MIN_CONFIDENCE_THRESHOLD = 40  # Don't store entries < 40

    async def scrape_team_page(self, url: str) -> List[ContactData]:
        """Only return contacts meeting minimum confidence."""
        contacts = await self._extract_names(url)

        filtered = [c for c in contacts if c.confidence >= self.MIN_CONFIDENCE_THRESHOLD]

        if len(filtered) < len(contacts):
            logger.info(f"Filtered {len(contacts) - len(filtered)} low-confidence contacts")

        return filtered
```

---

### 1.2 Add Pre-Store Validation in Sync Layer

**File:** `backend/app/services/sync/` (new file: `contact_sync_validator.py`)

```python
class ContactSyncValidator:
    """Validate contacts before syncing to database."""

    GARBAGE_NAMES = {
        'schedule now', 'call now', 'get quote', 'john doe',
        'jane doe', 'test user', 'facebook', 'twitter', 'linkedin',
        # ... all 56 from clean_garbage_contacts.py
    }

    @staticmethod
    def validate_contact(contact: dict) -> tuple[bool, Optional[str]]:
        """Validate contact data before storage."""
        name = contact.get('full_name', '').strip()
        confidence = contact.get('confidence', 0)

        # Check against exact garbage names
        if name.lower() in ContactSyncValidator.GARBAGE_NAMES:
            return False, f"garbage_name: {name}"

        # Check basic validity
        if len(name) < 3:
            return False, f"too_short: {name}"

        if len(name) > 50:
            return False, f"too_long: {name}"

        # Check confidence threshold (absolute minimum)
        if confidence < 20:
            return False, f"confidence_too_low: {confidence}"

        return True, None

    @staticmethod
    def validate_batch(contacts: List[dict]) -> tuple[List[dict], List[dict]]:
        """Validate batch of contacts."""
        valid = []
        rejected = []

        for contact in contacts:
            is_valid, error = ContactSyncValidator.validate_contact(contact)
            if is_valid:
                valid.append(contact)
            else:
                contact['validation_error'] = error
                rejected.append(contact)

        return valid, rejected
```

---

## Tier 2: Import Quality Gates

### 2.1 CSV Import Validation

**File:** `backend/app/services/csv_import_service.py` (enhancement)

```python
class CSVImportValidator:
    """Validate CSV imports before database sync."""

    @staticmethod
    def validate_contact_row(row: dict) -> tuple[bool, Optional[str]]:
        """Validate single contact row from CSV."""

        # Required fields
        if not row.get('full_name') or not row.get('full_name').strip():
            return False, "missing_name"

        # Name validation
        name = row['full_name'].strip()
        if len(name) < 3:
            return False, f"too_short: {name}"

        # Email validation (if present)
        if row.get('email') and not is_valid_email(row['email']):
            return False, f"invalid_email: {row.get('email')}"

        # Company validation (if foreign key)
        if not row.get('company_id'):
            return False, "missing_company_id"

        return True, None

    @staticmethod
    def validate_csv_file(filepath: str) -> tuple[List[dict], List[dict]]:
        """
        Validate entire CSV before import.

        Returns: (valid_rows, rejected_rows)
        """
        valid = []
        rejected = []

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # start=2 skips header
                is_valid, error = CSVImportValidator.validate_contact_row(row)
                if is_valid:
                    valid.append(row)
                else:
                    row['_row_number'] = row_num
                    row['_validation_error'] = error
                    rejected.append(row)

        # Log statistics
        logger.info(f"CSV validation: {len(valid)} valid, {len(rejected)} rejected")
        if rejected:
            logger.warning(f"First rejection: {rejected[0]['_validation_error']}")

        return valid, rejected
```

---

### 2.2 Test Data Detection

```python
class TestDataDetector:
    """Detect and reject test/placeholder data."""

    TEST_KEYWORDS = {
        'test', 'demo', 'sample', 'fake', 'placeholder',
        'example', 'john doe', 'jane doe', 'admin',
    }

    TEST_EMAIL_PATTERNS = [
        r'^test@',
        r'^demo@',
        r'^sample@',
        r'@example\.com$',
        r'@test\.com$',
    ]

    @staticmethod
    def is_test_data(contact: dict) -> tuple[bool, Optional[str]]:
        """Check if contact looks like test data."""

        name = (contact.get('full_name') or '').lower()
        email = (contact.get('email') or '').lower()
        company = (contact.get('company_name') or '').lower()

        # Check name keywords
        for keyword in TestDataDetector.TEST_KEYWORDS:
            if keyword in name or keyword in company:
                return True, f"test_keyword: {keyword}"

        # Check email patterns
        for pattern in TestDataDetector.TEST_EMAIL_PATTERNS:
            if re.search(pattern, email):
                return True, f"test_email_pattern: {pattern}"

        return False, None
```

---

## Tier 3: Runtime Quality Filters

### 3.1 Confidence-Based Filtering

**Update query patterns to include confidence threshold:**

```python
# In agent queries, add confidence filter
result = supabase.table('dim_contacts').select('*').where(
    'is_atl', 'eq', True
).filter('confidence', 'gte', 50).execute()  # Only >= 50 confidence
```

### 3.2 Quality Metrics Dashboard

**New endpoint:** `GET /api/quality/contact-metrics`

```python
@app.get("/api/quality/contact-metrics")
async def get_contact_quality_metrics():
    """Return contact quality metrics for dashboard."""

    # Get metrics
    result = supabase.rpc('get_contact_quality_metrics').execute()

    return {
        'total_atl': result['total_atl'],
        'avg_confidence': result['avg_confidence'],
        'low_confidence_count': result['low_confidence'],  # < 40
        'recent_garbage_rate': result['garbage_rate_last_7d'],
        'by_source': {
            'beautifulsoup': result['bs_count'],
            'apollo': result['apollo_count'],
            'hunter': result['hunter_count'],
        },
        'status': 'healthy' if result['garbage_rate_last_7d'] < 0.5 else 'warning'
    }
```

### 3.3 Automated Quality Alerts

**New job:** `backend/jobs/quality_monitor.py`

```python
async def monitor_contact_quality():
    """
    Daily job to monitor contact quality.
    Alert if garbage rate exceeds threshold.
    """

    garbage_rate = await calculate_garbage_rate()

    if garbage_rate > 0.05:  # > 5%
        logger.warning(f"Garbage rate high: {garbage_rate:.1%}")
        await notify_team(
            subject="High contact garbage rate detected",
            body=f"Garbage: {garbage_rate:.1%}\nRun cleanup_garbage_contacts.py"
        )

    # Log trend
    await log_quality_metric('garbage_rate', garbage_rate)
```

---

## Tier 4: Cleanup Automation

### 4.1 Scheduled Garbage Cleanup

**New script:** `backend/jobs/scheduled_cleanup.py`

```python
async def scheduled_garbage_cleanup():
    """
    Weekly job to automatically clean garbage contacts.
    Dry-run mode logs only, doesn't delete.
    """

    logger.info("Starting scheduled garbage cleanup")

    garbage = await identify_garbage_contacts()

    if garbage:
        logger.info(f"Found {len(garbage)} garbage contacts")

        # Log what would be deleted
        for g in garbage:
            logger.debug(f"Would delete: {g['full_name']} ({g['reason']})")

        # Auto-delete if garbage_rate < 5% (safe threshold)
        garbage_rate = len(garbage) / total_atl
        if garbage_rate < 0.05:
            await auto_delete_garbage(garbage)
            logger.info(f"Auto-deleted {len(garbage)} garbage contacts")
        else:
            logger.warning(f"Garbage rate {garbage_rate:.1%} too high, manual review needed")
            await notify_team(f"Manual cleanup needed: {len(garbage)} garbage entries")
```

---

## Implementation Roadmap

### Sprint 1: Foundation (Week 1)
- [ ] Create `ContactSyncValidator` class
- [ ] Add validation to BeautifulSoup scraper
- [ ] Add confidence threshold filtering
- [ ] Deploy to staging and test

### Sprint 2: Quality Gates (Week 2)
- [ ] Enhance CSV import validator
- [ ] Add test data detection
- [ ] Create quality metrics endpoint
- [ ] Update API documentation

### Sprint 3: Monitoring (Week 3)
- [ ] Build quality metrics dashboard
- [ ] Implement automated alerts
- [ ] Set up scheduled cleanup job
- [ ] Train team on monitoring

### Sprint 4: Optimization (Week 4)
- [ ] Review garbage patterns from production
- [ ] Fine-tune validation rules
- [ ] Measure improvement (target: < 0.5% garbage)
- [ ] Document best practices

---

## Success Metrics

### Baseline (Current)
- Garbage rate: 1.5-3%
- Manual cleanup frequency: As-needed
- Time per cleanup: ~30 min + review

### Target (After Implementation)
- Garbage rate: < 0.5% (90% improvement)
- Manual cleanup frequency: Monthly or less
- Time per cleanup: Automated, < 5 min

### Key Metrics to Track
```python
metrics = {
    'garbage_rate': len(garbage) / total_atl,
    'rejection_rate_at_import': rejected_count / total_attempted,
    'false_positive_rate': legitimate_deleted / total_deleted,
    'time_to_cleanup': total_minutes,
    'alerts_per_month': count,
}
```

---

## Risk Mitigation

| Risk | Prevention | Fallback |
|------|-----------|----------|
| Over-aggressive validation | Start with audit mode, review weekly | Relax rules based on data |
| Legitimate names rejected | Whitelist test data, monitor false positives | Manual approval list |
| Performance impact | Async validation, batch processing | Queue validation jobs |
| Team adoption | Dashboard + alerts, minimal manual work | Training sessions |

---

## Cost-Benefit Analysis

### Implementation Cost
- Development: 3-4 sprints × 40 hours = 120-160 hours
- Testing: 20-30 hours
- Deployment & monitoring: 10-20 hours
- **Total:** ~150-210 hours

### Benefits
- **Operational:** ~5-10 hours/month manual cleanup saved
- **Sales:** ~2-5% improvement in BDR efficiency (fewer false leads)
- **System:** Reduced email errors, lower DNS query rate
- **Data:** Higher confidence in contact data
- **ROI:** Payback in 30-60 days, ongoing savings

---

## Conclusion

Moving from reactive cleanup to proactive prevention will:
1. **Reduce garbage** from 1.5-3% to < 0.5%
2. **Eliminate manual work** through automation
3. **Improve data quality** at the source
4. **Enable scaling** without quality degradation
5. **Build trust** in contact database

Recommended approach:
- **Phase 1:** Add validation to BeautifulSoup scraper (highest impact)
- **Phase 2:** Implement quality dashboard (visibility)
- **Phase 3:** Automate cleanup (operational efficiency)

---

**Document Status:** COMPLETE - Strategic planning
**Last Updated:** 2025-12-15
