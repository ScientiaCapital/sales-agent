# Contact Quality Audit - Action Checklist

## Pre-Cleanup Phase

### Understanding Phase (30 minutes)
- [ ] Read AUDIT_SUMMARY.txt (5 min)
- [ ] Review CONTACT_QUALITY_QUICK_REFERENCE.md (10 min)
- [ ] Understand 6 main garbage categories
- [ ] Ask questions if patterns unclear

### Technical Phase (30 minutes)
- [ ] Read CONTACT_QUALITY_TECHNICAL_DETAILS.md (optional)
- [ ] Understand false positive risks per pattern
- [ ] Review SQL verification queries
- [ ] Familiarize with dry-run output format

### Approval Phase (15 minutes)
- [ ] Get Tim's initial approval to proceed
- [ ] Verify database backup exists
- [ ] Confirm test environment available (optional)
- [ ] Schedule execution window (avoid peak hours)

**Estimated Time:** 45-60 minutes

---

## Dry-Run Phase (15 minutes)

### Execute Dry-Run
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
python clean_garbage_contacts.py --dry-run
```

- [ ] Command runs without errors
- [ ] Output shows "DRY RUN - No changes made"
- [ ] Garbage count is 7-15 (consistent with estimate)
- [ ] Sample entries look like garbage (not real contacts)
- [ ] Save output to file for review: `python clean_garbage_contacts.py --dry-run > dry_run_output.txt`

### Review Dry-Run Output

For each garbage entry shown:
- [ ] Name clearly garbage (not a legitimate contact)
- [ ] Reason for deletion makes sense
- [ ] Company context looks correct
- [ ] No unexpected legitimate contacts in list

Red flags to watch for:
- [ ] Any name that looks like "John Smith" or "Mary Johnson"
- [ ] More than 20 garbage entries (investigate why)
- [ ] Fewer than 5 garbage entries (might not have found all)
- [ ] Error messages or SQL exceptions

**If concerns:** Review specific entries in CONTACT_QUALITY_TECHNICAL_DETAILS.md

---

## Export Phase (5 minutes)

### Export Suspicious Contacts
```bash
python audit_enrichment.py
```

- [ ] Command runs without errors
- [ ] Creates AUDIT_SUSPICIOUS_*.csv file
- [ ] Creates AUDIT_NEW_CONTACTS_*.csv file
- [ ] Creates AUDIT_NO_ATL_FOUND_*.csv file

### Manual Review (30 minutes)

Open `backend/data/AUDIT_SUSPICIOUS_*.csv`:

For each suspicious entry:
- [ ] Review full_name, title, email, phone
- [ ] Assess: Is this garbage or legitimate?
- [ ] Check company context
- [ ] If unsure: Mark in spreadsheet for second opinion

Column meanings:
- **name:** Contact full name
- **title:** Job title/role
- **reason:** Why it was flagged as suspicious
- **company:** Company name
- **domain:** Company domain

Decision for each entry:
- [ ] DELETE: Clearly garbage
- [ ] KEEP: Legitimate contact
- [ ] REVIEW: Needs Tim's opinion

**If finding legitimate entries:** Update cleanup pattern rules before proceeding

---

## Pre-Execution Verification (10 minutes)

### Database Checks
```sql
-- Run in Supabase SQL editor
SELECT COUNT(*) as total_atl FROM dim_contacts WHERE is_atl = TRUE;
-- Should return: 476
```

- [ ] Total ATL count confirmed as 476
- [ ] Database connection working
- [ ] No active queries running
- [ ] No locks on dim_contacts table

### Backup Check
```bash
# Check Supabase automatic backups exist
# In Supabase dashboard: Project Settings → Backups
```

- [ ] Automatic backups enabled
- [ ] Latest backup recent (< 24 hours)
- [ ] Manual backup option available
- [ ] Recovery procedure documented

### Execution Window Check
- [ ] No scheduled batch jobs running
- [ ] BDRs not actively using contact data
- [ ] Off-peak execution time (e.g., evening/weekend)
- [ ] Tim available if issues arise

---

## Execution Phase (5 minutes)

### Execute Cleanup
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
python clean_garbage_contacts.py --execute
```

Steps during execution:
- [ ] Script starts and fetches contacts
- [ ] Shows total count: 476
- [ ] Shows garbage identified: 7-15
- [ ] Prompts: "Type 'DELETE' to confirm deletion of X contacts"
- [ ] Type: **DELETE** (exactly, case-sensitive)
- [ ] Script deletes in batches of 100
- [ ] Each batch logged with count
- [ ] Script completes with summary
- [ ] Shows remaining count: 461-469

### Monitor Execution
- [ ] No error messages
- [ ] No database connection errors
- [ ] No permission denied errors
- [ ] Completion message shows success

If errors occur:
- [ ] Stop immediately
- [ ] Check error message
- [ ] Review CONTACT_QUALITY_TECHNICAL_DETAILS.md troubleshooting
- [ ] Restore from backup if needed
- [ ] Contact database admin

**Expected Duration:** 3-5 seconds

---

## Post-Execution Verification (10 minutes)

### Immediate Verification
```bash
# Verify no garbage remains
python clean_garbage_contacts.py --dry-run
```

- [ ] Dry-run shows "Garbage contacts: 0"
- [ ] "DRY RUN - No changes made"
- [ ] No errors in output

### Count Verification
```sql
-- Run in Supabase SQL editor
SELECT COUNT(*) as total_atl FROM dim_contacts WHERE is_atl = TRUE;
-- Should return: 461-469 (depending on actual garbage count)
```

- [ ] Total ATL count is 461-469
- [ ] Reduction is 7-15 entries
- [ ] No unexpected drops (e.g., < 450)

### Sample Data Check
```sql
-- Verify legitimate contacts still exist
SELECT full_name, title, email
FROM dim_contacts
WHERE is_atl = TRUE
ORDER BY created_at DESC
LIMIT 10;
```

- [ ] Results show real names with proper titles
- [ ] Emails are valid format
- [ ] No "Schedule Now" or similar garbage
- [ ] Timestamps look reasonable

### Application Check
- [ ] Backend starts without errors
- [ ] Dashboard loads contacts without 404
- [ ] No database connection warnings
- [ ] API endpoints responding normally

---

## Documentation Phase (10 minutes)

### Document Results
- [ ] Record: Original count (476)
- [ ] Record: Deleted count (7-15)
- [ ] Record: Final count (461-469)
- [ ] Record: Execution date and time
- [ ] Record: Any issues encountered

### Create Execution Report
Create `EXECUTION_REPORT_[DATE].txt`:
```
CONTACT QUALITY CLEANUP - EXECUTION REPORT
Date: 2025-12-15
Time: HH:MM UTC

BEFORE:
- Total ATL contacts: 476
- Estimated garbage: 7-15

EXECUTION:
- Dry-run completed successfully
- Audit CSV reviewed
- Manual verification passed
- Cleanup executed: [time]
- Duration: ~5 seconds

AFTER:
- Total ATL contacts: [final count]
- Garbage deleted: [count]
- Verification: PASSED

ISSUES: [None / describe any issues]

VERIFICATION:
- Dry-run shows 0 garbage: YES
- All legitimate contacts remain: YES
- No application errors: YES
- No database errors: YES

APPROVED BY: [Tim name]
EXECUTED BY: [Your name]
```

- [ ] Save report to backend/data/
- [ ] Share report with Tim
- [ ] Archive for compliance

---

## Follow-Up Phase (Daily for 1 week)

### Day 1 (After execution)
- [ ] Check backend logs for errors
- [ ] Monitor dashboard for issues
- [ ] Verify BDRs can access contacts
- [ ] Test contact search functionality
- [ ] Confirm no data integrity issues

### Days 2-7 (Week after execution)
- [ ] Monitor application performance
- [ ] Watch for user-reported missing contacts
- [ ] Track if any false positives reported
- [ ] Collect feedback on data quality
- [ ] Update quality metrics

### Incident Response (If issues found)
- [ ] Restore from backup immediately
- [ ] Document what went wrong
- [ ] Analyze failure patterns
- [ ] Review for false positives
- [ ] Adjust rules and retry

---

## Long-Term (After cleanup complete)

### Prevention Implementation
- [ ] Schedule discussion: Prevention strategy
- [ ] Identify Tier-1 changes (input validation)
- [ ] Plan implementation roadmap
- [ ] Assign owners and sprints
- [ ] Track metrics monthly

### Quality Monitoring
- [ ] Set up quality metrics dashboard
- [ ] Configure automated alerts
- [ ] Schedule monthly quality reviews
- [ ] Adjust rules based on patterns
- [ ] Document lessons learned

### Team Training
- [ ] Brief Tim on results
- [ ] Educate team on quality standards
- [ ] Share prevention strategy
- [ ] Document best practices
- [ ] Create troubleshooting guide

---

## Sign-Off

**Pre-Cleanup Approval**
- [ ] Tim Kipper: Approves cleanup
- [ ] Date: ___________
- [ ] Notes: ___________

**Post-Execution Approval**
- [ ] Verification complete: All checks passed
- [ ] Data quality improved: Confirmed
- [ ] No issues found: Confirmed
- [ ] Tim Kipper: Approves final results
- [ ] Date: ___________

---

## Documents Reference

| Document | Purpose | Read Time |
|----------|---------|-----------|
| AUDIT_SUMMARY.txt | Executive summary | 10 min |
| CONTACT_QUALITY_QUICK_REFERENCE.md | Step-by-step guide | 15 min |
| CONTACT_QUALITY_TECHNICAL_DETAILS.md | Deep technical reference | 30 min |
| CONTACT_QUALITY_AUDIT_REPORT.md | Full analysis and recommendations | 30 min |
| CONTACT_QUALITY_PREVENTION_STRATEGY.md | Long-term strategy | 20 min |

---

**Checklist Status:** Ready to use
**Last Updated:** 2025-12-15
**Estimated Total Time:** 2-3 hours (including reviews)
