# Contact Quality Audit - Technical Implementation Details
**Database:** Supabase PostgreSQL
**Table:** dim_contacts
**Columns Analyzed:** full_name, title, source, confidence, is_atl, created_at

---

## 1. Garbage Detection Logic Deep Dive

### 1.1 Exact Garbage Names (56 entries)
Located in: `clean_garbage_contacts.py` lines 38-56

```python
GARBAGE_NAMES = {
    # Service/product categories (13 entries)
    "installation types", "battery storage", "industrial solar", "commercial solar",
    "residential solar", "solar panels", "solar energy", "solar power",
    "heating", "cooling", "plumbing", "electrical", "hvac", "roofing",
    "air conditioning", "water heater", "energy", "services",
    "ev charging", "ev chargers", "solar installation", "solar installer",
    "heat pump", "ductless", "mini split", "geothermal",

    # Placeholder names (7 entries)
    "john doe", "jane doe", "test user", "sample name", "your name",
    "first last", "name here", "full name",

    # Navigation/UI (13 entries)
    "learn more", "read more", "click here", "view all", "see more",
    "schedule now", "call now", "get quote", "request quote", "contact us",
    "about us", "our team", "meet the team", "leadership", "management",

    # Social media (6 entries)
    "facebook", "twitter", "linkedin", "instagram", "youtube", "tiktok",
}
```

**Detection Method:**
```python
name_lower = name.lower().strip()
if name_lower in GARBAGE_NAMES:
    return True  # Mark as garbage
```

**SQL Equivalent:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE LOWER(TRIM(full_name)) IN (
    'installation types', 'battery storage', 'industrial solar',
    -- ... all 56 garbage names
);
```

**Characteristics:**
- Case-insensitive matching (all converted to lowercase)
- Exact string match (no partial matching)
- High precision, zero false positives expected
- These names should NEVER appear in real ATL lists

---

### 1.2 Regex Pattern Matching (9 patterns)
Located in: `clean_garbage_contacts.py` lines 59-69

| Pattern ID | Regex | Purpose | Examples | Risk |
|-----------|-------|---------|----------|------|
| P1 | `^(schedule\|call\|contact\|...)$` | Single-word verbs/actions | "schedule", "call", "contact" | LOW |
| P2 | `^(heating\|cooling\|...\|water)$` | Trade service names | "heating", "electrical", "plumbing" | LOW |
| P3 | `^(request\|quote\|...\|me)$` | Action/business words | "quote", "estimate", "free" | MEDIUM |
| P4 | `^\d+$` | Numeric only | "123", "456", "2024" | LOW |
| P5 | `^[a-z]$` | Single letter | "a", "b", "z" | LOW |
| P6 | `(privacy\|policy\|...\|rights)` | Legal text | "privacy", "terms", "copyright" | MEDIUM |
| P7 | `(facebook\|twitter\|...\|tiktok)` | Social media | "facebook", "twitter", "linkedin" | LOW |
| P8 | `^(mr\|mrs\|ms\|dr)\.?$` | Titles without names | "Mr.", "Dr", "Mrs" | LOW |
| P9 | `(admin\|webmaster\|...\|support)@` | Email keywords in name | "admin@", "support@" | MEDIUM |

**Pattern Analysis (P1 - Main action words):**
```regex
^(schedule|call|contact|click|learn|view|see|read|get|our|the|your|my|home|about|services?)$
```
- Matches complete string (^ = start, $ = end)
- Case-insensitive via `.search(pattern, name_lower)`
- 16 verbs/prepositions that should never be names alone
- Single-word limit prevents false positives like "Contact Manager"

---

### 1.3 Concatenated Role Patterns
Located in: `clean_garbage_contacts.py` lines 72-75

```python
CONCATENATED_PATTERNS = [
    r'\w+(CEO|CFO|CTO|COO|CMO|VP|Vice|Director|Manager|Owner|Founder|President|Customer|Advocate|Designer|Specialist|Crew|Lead|Installer|Technician|Roofing)$',
]
```

**Pattern Breakdown:**
- `\w+` = One or more word characters (name part)
- `(CEO|CFO|...)` = Role suffix (no space between name and role)
- `$` = End of string

**Examples:**
- ✓ Caught: "JohnCEO", "MariaDirector", "TechnicianRoofing"
- ✓ Safe: "Jennifer" (doesn't end with role), "Chief Technology Officer" (spaced)
- ⚠️ Risky: "McCall" (ends with "L" + "L", but won't match due to capitals)
- ⚠️ Risky: "Kennedy" (ends with "Y", safe)

**False Positive Analysis:**
```
Legitimate names that might trigger this:
- Names ending in a role word followed by role suffix
- Very rare: "PrestonCEO" → "Preston" + "CEO" (caught)
- Very rare: "ViceCEO" → "Vice" + "CEO" (caught, but unlikely name)

Risk level: LOW - Most people don't have concatenated roles in their names
```

---

### 1.4 Additional Validation Checks
Located in: `clean_garbage_contacts.py` lines 109-124

#### Check 1: Name Too Short (< 3 characters)
```python
if len(name_lower) < 3:
    reasons.append("name too short")
```

**Impact:**
- Catches: "Jo", "Al", "Bo", "Mo"
- False positives: "Bob" (3 chars, safe), "Eva" (3 chars, safe), "Tim" (3 chars, safe)
- Threshold of 3 is reasonable for English names

#### Check 2: Name Too Long (> 50 characters)
```python
if len(name) > 50:
    reasons.append("name too long (>50 chars)")
```

**Impact:**
- Catches: Scraped paragraphs or descriptions
- Example: "John Smith, VP of Sales, Texas Region Manager" (47+ chars)
- False positives: Very rare (only hyphenated names in USA)
- Threshold of 50 is conservative and safe

#### Check 3: No Spaces in Long Names (> 15 chars, no space)
```python
if ' ' not in name.strip() and len(name) > 15:
    reasons.append("no spaces in long name")
```

**Impact:**
- Catches: "JohnSmithCEODirector", "CompanyNameHere", "NavigationMenuText"
- False positives: "Mary-Anne-Thompson" (15+ chars, has hyphens not spaces)
- Risk: MEDIUM - Hyphenated names might be marked garbage
- Mitigation: Could modify to `if ' ' not in name.strip() and '-' not in name.strip()`

#### Check 4: "Visit" Prefix/Suffix
```python
if name.startswith("Visit ") or name.endswith(" Visit"):
    reasons.append("starts/ends with 'Visit'")
```

**Impact:**
- Catches: "Visit LinkedIn", "Visit Our Page", "Our Page Visit"
- False positives: Zero (no one named "Visit")
- Source: Website footer/navigation scraping artifacts

#### Check 5: Role Concatenated to Lowercase
```python
if re.search(r'[a-z](Customer|Designer|Specialist|Advocate|Engineer|Technician)', name):
    reasons.append("role concatenated to name")
```

**Impact:**
- Catches: "JohnCustomer", "JenniferSpecialist"
- False positives: Low (requires capital role word after lowercase letter)
- Complements CONCATENATED_PATTERNS with subset of roles

---

## 2. Data Quality Metrics Queries

### 2.1 Count Garbage by Category

**Find exact garbage names:**
```sql
SELECT
    COUNT(*) as garbage_count,
    COUNT(DISTINCT company_id) as unique_companies
FROM dim_contacts
WHERE is_atl = TRUE
AND LOWER(TRIM(full_name)) IN (
    'installation types', 'battery storage', 'industrial solar',
    'john doe', 'jane doe', 'test user',
    'learn more', 'schedule now', 'call now',
    'facebook', 'twitter', 'linkedin', 'instagram'
    -- ... all 56 garbage names from GARBAGE_NAMES
);
```

**Find single-character names:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND LENGTH(TRIM(full_name)) = 1
ORDER BY full_name;
```

**Find numeric-only names:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND full_name ~ '^\d+$'
ORDER BY full_name;
```

**Find names too short (<3 chars):**
```sql
SELECT contact_id, full_name, LENGTH(full_name) as name_length, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND LENGTH(TRIM(full_name)) < 3
ORDER BY name_length;
```

**Find names too long (>50 chars):**
```sql
SELECT contact_id, full_name, LENGTH(full_name) as name_length, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND LENGTH(full_name) > 50
ORDER BY name_length DESC;
```

**Find concatenated roles:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND full_name ~* '\w+(CEO|CFO|CTO|COO|CMO|VP|Director|Manager|Owner|President|Technician|Roofing)$'
ORDER BY full_name;
```

**Find "Visit" prefixed names:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND (full_name ILIKE 'Visit %' OR full_name ILIKE '% Visit')
ORDER BY full_name;
```

**Find lowercase names:**
```sql
SELECT contact_id, full_name, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND SUBSTRING(full_name, 1, 1) ~ '[a-z]'
ORDER BY full_name;
```

**Find names without spaces (>15 chars):**
```sql
SELECT contact_id, full_name, LENGTH(full_name) as name_length, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND LENGTH(TRIM(full_name)) > 15
AND full_name NOT LIKE '% %'
AND full_name NOT LIKE '%-%'
ORDER BY name_length DESC;
```

---

### 2.2 Quality Metrics Summary

```sql
SELECT
    COUNT(*) as total_atl,
    SUM(CASE WHEN LENGTH(TRIM(full_name)) < 3 THEN 1 ELSE 0 END) as too_short,
    SUM(CASE WHEN LENGTH(full_name) > 50 THEN 1 ELSE 0 END) as too_long,
    SUM(CASE WHEN full_name ~ '^\d+$' THEN 1 ELSE 0 END) as numeric_only,
    SUM(CASE WHEN full_name ~ '^[a-z]$' THEN 1 ELSE 0 END) as single_letter,
    SUM(CASE WHEN SUBSTRING(full_name, 1, 1) ~ '[a-z]' THEN 1 ELSE 0 END) as starts_lowercase,
    AVG(confidence) as avg_confidence,
    MIN(confidence) as min_confidence,
    MAX(confidence) as max_confidence
FROM dim_contacts
WHERE is_atl = TRUE;
```

---

### 2.3 Confidence Score Analysis

```sql
SELECT
    confidence,
    COUNT(*) as contact_count,
    COUNT(DISTINCT source) as source_count,
    STRING_AGG(DISTINCT source, ', ') as sources
FROM dim_contacts
WHERE is_atl = TRUE
GROUP BY confidence
ORDER BY confidence DESC;
```

**Confidence < 50 (potential low quality):**
```sql
SELECT contact_id, full_name, title, source, confidence, company_id
FROM dim_contacts
WHERE is_atl = TRUE
AND confidence < 50
ORDER BY confidence ASC
LIMIT 50;
```

---

### 2.4 Source-Specific Quality

```sql
SELECT
    source,
    COUNT(*) as total,
    COUNT(CASE WHEN LENGTH(TRIM(full_name)) < 3 THEN 1 END) as too_short_pct,
    ROUND(100.0 * COUNT(CASE WHEN LENGTH(TRIM(full_name)) < 3 THEN 1 END) / COUNT(*), 2) as pct_too_short,
    AVG(confidence) as avg_confidence,
    MIN(confidence) as min_confidence
FROM dim_contacts
WHERE is_atl = TRUE
GROUP BY source
ORDER BY total DESC;
```

---

## 3. Cleanup Execution Flow

### 3.1 Dry Run Analysis

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
python clean_garbage_contacts.py --dry-run
```

**Expected Output Structure:**
```
================================================================================
GARBAGE CONTACT CLEANUP
================================================================================

Fetching contacts...
Total contacts: 476

Results:
  Clean contacts: 461-469
  Garbage contacts: 7-15

================================================================================
GARBAGE CONTACTS TO DELETE
================================================================================

[garbage name: 'schedule now'] - 2 contacts
  • Schedule Now                      | Company A
  • Schedule Now                      | Company B

[matches pattern: '^\d+$'] - 1 contacts
  • 123                               | Company C

[concatenated role] - 3 contacts
  • JohnCEO                           | Company D
  • MariaDirector                     | Company E
  • TechnicianRoofing                 | Company F

[name too short] - 2 contacts
  • Jo                                | Company G
  • Al                                | Company H

================================================================================
DRY RUN - No changes made
================================================================================
Would delete 10 garbage contacts
```

---

### 3.2 Batch Deletion Strategy

The cleanup script deletes in batches of 100 (line 263):

```python
batch_size = 100
contact_ids = [g['contact_id'] for g in garbage]

for i in range(0, len(contact_ids), batch_size):
    batch = contact_ids[i:i+batch_size]
    supabase.table('dim_contacts').delete().in_('contact_id', batch).execute()
```

**Safety Considerations:**
- Batches of 100 are reasonable
- Each batch is logged
- ON DELETE CASCADE will remove from related tables (if any)
- Supabase maintains automatic backups (typically 7-30 days)

---

## 4. Risk Assessment Matrix

### 4.1 False Positives by Pattern

| Pattern | False Positive Risk | Mitigation | Recommendation |
|---------|-------------------|------------|-----------------|
| Exact garbage names | VERY LOW | None needed | SAFE TO DELETE |
| Numeric only (^\d+$) | VERY LOW | None needed | SAFE TO DELETE |
| Single letter (^[a-z]$) | VERY LOW | None needed | SAFE TO DELETE |
| Too short (<3) | LOW | Review "Bob", "Eva", "Tim" | REVIEW first |
| Too long (>50) | VERY LOW | None needed | SAFE TO DELETE |
| "Visit" prefix | VERY LOW | None needed | SAFE TO DELETE |
| Concatenated role | LOW | Watch "McCall" false pos | REVIEW first |
| No spaces (>15) | MEDIUM | Hyphenated names caught | REVIEW first |
| Lowercase start | HIGH | Import artifacts common | DISABLE or REVIEW |

---

### 4.2 Data Loss Risk

**Current Protection:**
- Supabase automatic backups (check admin panel)
- ON DELETE CASCADE documented in schema
- No actual foreign key cascade needed if contacts are leaf table

**Backup Strategy Before Cleanup:**
```bash
# Export contacts before cleanup
psql $SUPABASE_CONNECTION_STRING -c \
  "COPY dim_contacts TO STDOUT" > dim_contacts_backup_20251215.sql
```

---

## 5. Post-Cleanup Verification

### 5.1 Verify Cleanup Success

```sql
-- Should return no results (all garbage deleted)
SELECT contact_id, full_name
FROM dim_contacts
WHERE is_atl = TRUE
AND LENGTH(TRIM(full_name)) < 3;

SELECT contact_id, full_name
FROM dim_contacts
WHERE is_atl = TRUE
AND full_name ~ '^\d+$';

-- Check total count
SELECT COUNT(*) as remaining_atl
FROM dim_contacts
WHERE is_atl = TRUE;
-- Expected: 464-469 (depending on garbage count)
```

### 5.2 Run Audit Again

```bash
python audit_enrichment.py
# Should show less suspicious contacts than before
```

---

## 6. Implementation Recommendations

### Phase 1: Analysis (CURRENT)
- [x] Read cleanup_garbage_contacts.py
- [x] Read audit_enrichment.py
- [x] Document all patterns
- [ ] Run SQL queries above to get actual counts
- [ ] Export suspicious CSV for team review

### Phase 2: Validation (NEXT)
- [ ] Execute `python clean_garbage_contacts.py --dry-run`
- [ ] Review generated garbage list
- [ ] Validate confidence score distribution
- [ ] Check for false positives in lowercase names
- [ ] Get approval from Tim/team

### Phase 3: Execution (WHEN READY)
- [ ] Create backup of dim_contacts table
- [ ] Execute `python clean_garbage_contacts.py --execute`
- [ ] Verify cleanup with SQL queries
- [ ] Run audit_enrichment.py to confirm
- [ ] Monitor application logs for downstream errors

### Phase 4: Prevention (ONGOING)
- [ ] Add pre-import validation to beautifulsoup_team_scraper.py
- [ ] Implement confidence threshold warnings
- [ ] Create quality metrics dashboard
- [ ] Set up automated monthly audits

---

**Document Status:** COMPLETE - Technical reference
**Database:** Supabase PostgreSQL
**Last Updated:** 2025-12-15
