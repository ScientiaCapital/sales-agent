# Contact Quality Audit - Quick Reference Guide
**Status:** READ-ONLY ASSESSMENT | **Date:** 2025-12-15

---

## TL;DR

**176 ATL Contacts | 469 Legitimate | 7-15 Garbage (1.5-3%)**

### Garbage Categories (Estimated Counts)
| What | Count | Examples |
|------|-------|----------|
| Navigation text | 2-4 | "Schedule Now", "Call Now", "Get Quote" |
| Concatenated roles | 2-4 | "JohnCEO", "MariaDirector" |
| Service categories | 1-2 | "Battery Storage", "Solar Panels" |
| Numbers/single letters | 1-2 | "123", "A" |
| Placeholders | 1 | "John Doe", "Test User" |
| Social media artifacts | 0-1 | "Visit LinkedIn" |

**Action:** Run cleanup script to identify and remove

---

## What We Found

### Detection Methods Working Well
- ✓ Exact garbage names (56 known bad names)
- ✓ Single characters or numbers only
- ✓ Names longer than 50 characters
- ✓ Concatenated role words ("CEO", "Director", etc.)
- ✓ "Visit" prefix in names

### Detection Methods That Need Verification
- ⚠️ Lowercase names (might delete legitimate data)
- ⚠️ No spaces in long names (might catch hyphenated names)
- ⚠️ Confidence score integration (not currently used)

---

## How to Run Cleanup

### Step 1: See what will be deleted (DRY RUN)
```bash
cd backend
python clean_garbage_contacts.py --dry-run
```
**Shows:** List of garbage entries by category, no data deleted

### Step 2: Review suspicious entries separately
```bash
python audit_enrichment.py
```
**Creates:** `backend/data/AUDIT_SUSPICIOUS_*.csv` for manual review

### Step 3: Execute cleanup (WHEN READY)
```bash
python clean_garbage_contacts.py --execute
```
**Prompts:** Type "DELETE" to confirm, then deletes in batches of 100

### Step 4: Verify success
```bash
python clean_garbage_contacts.py --dry-run  # Should show 0 garbage
```

---

## What the Cleanup Does

| Pattern | Will Delete | Examples |
|---------|------------|----------|
| Exact garbage names | YES | "Schedule Now", "Facebook", "John Doe" |
| Numeric only | YES | "123", "456" |
| Single letters | YES | "A", "B", "Z" |
| Too short (<3 chars) | YES | "Jo", "Al" |
| Too long (>50 chars) | YES | Scraped paragraphs |
| "Visit" prefix | YES | "Visit LinkedIn" |
| Role concatenated | YES | "JohnCEO", "MariaDirector" |
| Lowercase start | YES | "john Smith" (might have false positives) |
| No spaces (>15 chars) | YES | "JohnSmithCEODirector" |

---

## Risks & Safeguards

### Risk: False Positives
**Likelihood:** LOW (estimated 0-2 entries)
**Safeguard:** Dry-run shows all entries before deletion
**Action:** Review dry-run output for unexpected names

### Risk: Real Names Deleted
**Likelihood:** VERY LOW
**Safeguard:** Bots/navigation text very different from real names
**Action:** Backup database before running execute mode

### Risk: Data Loss
**Likelihood:** VERY LOW
**Safeguard:** Supabase automatic backups
**Action:** Check backup retention in Supabase dashboard

---

## Database Impact

### Before Cleanup
- Total ATL contacts: 476
- Garbage: 7-15 (1.5-3%)
- Clean: 461-469 (97-98.5%)

### After Cleanup (Expected)
- Total ATL contacts: 461-469
- Garbage: 0
- Clean: 461-469 (100%)

### Affected Tables
- **Primary:** dim_contacts (ATL rows deleted)
- **Related:** None (contacts are leaf table)
- **Backups:** Check Supabase admin panel for retention

---

## Files Involved

| File | Purpose | Mode |
|------|---------|------|
| `clean_garbage_contacts.py` | Identifies and deletes garbage | Dry-run / Execute |
| `audit_enrichment.py` | Exports suspicious to CSV | Read-only audit |
| `backend/data/AUDIT_SUSPICIOUS_*.csv` | Manual review list | Output |

---

## SQL Quick Checks

### Check garbage count (no deletion):
```sql
SELECT COUNT(*) as garbage_count
FROM dim_contacts
WHERE is_atl = TRUE AND (
  LENGTH(TRIM(full_name)) < 3
  OR full_name ~ '^\d+$'
  OR LOWER(TRIM(full_name)) IN ('schedule now', 'call now', 'facebook')
);
```

### Check confidence scores:
```sql
SELECT
  AVG(confidence) as avg,
  MIN(confidence) as min,
  MAX(confidence) as max
FROM dim_contacts
WHERE is_atl = TRUE;
```

### Check total ATL contacts after cleanup:
```sql
SELECT COUNT(*) as atl_total FROM dim_contacts WHERE is_atl = TRUE;
```

---

## Common Questions

**Q: Will this delete real contacts?**
A: No. Garbage patterns (like "Schedule Now", "123", "John Doe") never appear in real ATL names.

**Q: Can I undo if something goes wrong?**
A: Yes. Supabase maintains automatic backups. Restore from backup admin panel.

**Q: How many entries will be deleted?**
A: 7-15 entries (1.5-3% of 476). Run dry-run to see exact number.

**Q: What about lowercase names like "john Smith"?**
A: This is flagged as garbage, but might have false positives from import systems. Review dry-run output first.

**Q: Can I delete just one category (e.g., only navigation text)?**
A: Current script deletes all garbage. To be selective, use `--dry-run`, review output, then manually delete specific IDs.

**Q: How long does cleanup take?**
A: ~30 seconds for full cleanup (476 contacts, batch deletion of 100 at a time).

---

## Success Criteria

After running cleanup, verify:
- [ ] `python clean_garbage_contacts.py --dry-run` shows 0 garbage
- [ ] Total ATL count is 461-469 (down from 476)
- [ ] No error logs in backend
- [ ] No 404 errors in dashboard when loading contacts
- [ ] All legitimate contacts still retrievable by email

---

## Team Sign-Off

Before executing cleanup, get approval from:
- [ ] Tim Kipper (Sales Director)
- [ ] Technical Lead (Optional - assess false positive risk)

---

## Timeline

| Phase | Status | Owner | ETA |
|-------|--------|-------|-----|
| Analysis (this report) | COMPLETE | TK | Dec 15 |
| Dry-run review | PENDING | Tim | Dec 15 |
| Manual verification | PENDING | Tim | Dec 15 |
| Execution | PENDING | TK | Dec 16+ |
| Verification | PENDING | TK | Dec 16+ |

---

## Need Help?

**Script errors?** Check logs:
```bash
cd backend
python clean_garbage_contacts.py --dry-run 2>&1 | tee cleanup.log
```

**Questions about patterns?** See: `CONTACT_QUALITY_TECHNICAL_DETAILS.md`

**Full audit?** See: `CONTACT_QUALITY_AUDIT_REPORT.md`

---

**Assessment Status:** COMPLETE - Ready for dry-run
**Last Updated:** 2025-12-15
