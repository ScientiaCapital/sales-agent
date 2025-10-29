# Testing Complete Workflow

## Test Plan

This document tracks testing of the complete CSV import → ATL discovery → enrichment workflow.

## Test Steps

### 1. CSV Import Test

**Command:**
```bash
python3 scripts/import_csv_simple.py companies_ready_to_import.csv
```

**Expected:**
- ✅ 200 companies imported successfully
- ✅ Duration: ~3-4 seconds
- ✅ ~50-70 leads/second import rate

**Actual Results:**
- [ ] Run test
- [ ] Verify import count
- [ ] Check database records

### 2. ATL Contact Discovery Test

**Command:**
```bash
python3 scripts/discover_atl_contacts.py --limit 5
```

**Expected:**
- ✅ Companies processed successfully
- ✅ Website sources found (where domain exists)
- ✅ LinkedIn sources used
- ✅ ATL contacts discovered
- ✅ Personal LinkedIn profile URLs captured

**Actual Results:**
- [ ] Run test
- [ ] Verify contacts discovered
- [ ] Check lead.additional_data structure
- [ ] Verify LinkedIn profile URLs stored

### 3. Apollo Company Search Test

**Command:**
```bash
python3 scripts/batch_enrich_companies.py --mode company_search --limit 5
```

**Expected:**
- ✅ Contacts found via Apollo search
- ✅ Domain-based contact discovery
- ✅ ATL titles filtered (CEO, COO, CFO, CTO, VP Finance, VP Operations)
- ✅ Lead records updated with contact info

**Actual Results:**
- [ ] Run test
- [ ] Verify Apollo search_company_contacts() works
- [ ] Check contacts found
- [ ] Verify lead updates

### 4. Apollo Enrichment Test

**Command:**
```bash
python3 scripts/batch_enrich_companies.py --mode email_only --limit 5
```

**Expected:**
- ✅ Contacts enriched with Apollo
- ✅ Contact info updated (name, title, phone)
- ✅ Enrichment metadata stored
- ✅ Confidence scores recorded

**Actual Results:**
- [ ] Run test
- [ ] Verify enrichment works
- [ ] Check contact data updates
- [ ] Verify enrichment metadata

### 5. Full Pipeline Test

**Command:**
```bash
python3 scripts/full_pipeline.py --limit 5
```

**Expected:**
- ✅ CSV import works
- ✅ ATL discovery works
- ✅ Apollo enrichment works
- ✅ All data stored correctly

**Actual Results:**
- [ ] Run test
- [ ] Verify complete workflow
- [ ] Check all lead records updated
- [ ] Verify data completeness

## Verification Queries

### Check Imported Leads

```sql
SELECT COUNT(*) as total_leads FROM leads;
SELECT company_name, contact_email, contact_name FROM leads LIMIT 10;
```

### Check ATL Contacts

```sql
SELECT 
    id,
    company_name,
    contact_name,
    contact_title,
    jsonb_array_length(additional_data->'atl_contacts') as atl_count
FROM leads
WHERE additional_data->'atl_contacts' IS NOT NULL
LIMIT 10;
```

### Check Apollo Contacts

```sql
SELECT 
    id,
    company_name,
    contact_email,
    jsonb_array_length(additional_data->'apollo_contacts') as apollo_count
FROM leads
WHERE additional_data->'apollo_contacts' IS NOT NULL
LIMIT 10;
```

### Check Enrichment Status

```sql
SELECT 
    id,
    company_name,
    contact_name,
    contact_title,
    additional_data->'enrichment'->>'confidence' as enrichment_confidence
FROM leads
WHERE additional_data->'enrichment' IS NOT NULL
LIMIT 10;
```

## Test Results Summary

**Date:** [Date]
**Tester:** [Name]

### CSV Import
- Status: [ ] Pass [ ] Fail
- Notes: 

### ATL Discovery
- Status: [ ] Pass [ ] Fail
- Notes: 

### Apollo Company Search
- Status: [ ] Pass [ ] Fail
- Notes: 

### Apollo Enrichment
- Status: [ ] Pass [ ] Fail
- Notes: 

### Full Pipeline
- Status: [ ] Pass [ ] Fail
- Notes: 

## Issues Found

1. [Issue description]
   - Severity: [High/Medium/Low]
   - Workaround: 
   - Fix: 

## Performance Metrics

- CSV Import: [X] seconds for [Y] companies
- ATL Discovery: [X] seconds for [Y] companies
- Apollo Search: [X] seconds for [Y] companies
- Apollo Enrichment: [X] seconds for [Y] contacts

## Next Steps

- [ ] Fix any issues found
- [ ] Re-run tests
- [ ] Document any changes needed
- [ ] Update documentation if workflow changes

