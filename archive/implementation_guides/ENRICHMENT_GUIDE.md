# Lead Enrichment Guide - Clean & Simple

## ✅ What's Fixed

### 1. Clean Folder Organization
**New Structure:**
```
backend/data/enrichment_runs/
├── 2025-11-17_180840/          ← Each run gets its own folder
│   └── atl_contacts.csv        ← One clean file per run
├── 2025-11-17_201500/          ← Next run (example)
│   └── atl_contacts.csv
```

**No more confusion!** Just open the latest dated folder and there's your CSV.

### 2. Phone Numbers Added
- ✅ Hunter.io now captures phone numbers
- ✅ Automatically included in CSV export
- ⚠️ Note: Not all contacts have phone numbers in Hunter.io database

---

## 📋 How to Run Enrichment

### Simple 3-Step Process:

#### Step 1: Add your companies to inbox CSV
```bash
backend/data/csv/inbox/hvac_contractors_20.csv
```

**Format:**
```csv
Name,Domain,Industries,Revenue Band ($M),Notes on angle/tech/etc
Acme HVAC,acmehvac.com,HVAC Services,10-25,Heat pumps + service
```

#### Step 2: Run the enrichment script
```bash
source venv/bin/activate
python backend/enrich_atl_contacts.py
```

#### Step 3: Get your results
```bash
# Find the latest folder
ls -lth backend/data/enrichment_runs/

# Open the CSV
open backend/data/enrichment_runs/LATEST_FOLDER/atl_contacts.csv
```

---

## 📊 What You Get

**CSV with complete contact info:**
- ✅ company_name
- ✅ first_name, last_name
- ✅ email (with confidence 84-99%)
- ✅ **phone** (when available from Hunter.io)
- ✅ position (job title)
- ✅ linkedin (profile URL)
- ✅ is_atl (True = decision maker)
- ✅ company_industry
- ✅ company_notes

**Example Output:**
```csv
company_name,first_name,last_name,email,phone,position,linkedin
Halco Energy,Brittany,McDonald,brittany@halcoenergy.com,585-555-1234,Executive VP,https://linkedin.com/in/...
```

---

## 💡 What Happens Behind the Scenes

1. **Hunter.io Domain Search**
   - Searches each company domain
   - Finds ALL employees with job titles
   - Filters for ATL only (CEO, VP, Directors, Managers, Owners)

2. **ATL Classification**
   - Automatically identifies decision-makers
   - Job titles containing: CEO, President, Owner, VP, Director, Manager, Partner

3. **Data Quality**
   - Confidence scores: 84-99%
   - LinkedIn profiles included
   - Phone numbers when available

4. **Cost Tracking**
   - $0.01 per company domain search
   - 20 companies = $0.20 total
   - Results cached for 24 hours

---

## 📁 File Locations

### Input (your leads):
```
backend/data/csv/inbox/hvac_contractors_20.csv
```

### Output (enriched contacts):
```
backend/data/enrichment_runs/YYYY-MM-DD_HHMMSS/atl_contacts.csv
```

### Script to run:
```
backend/enrich_atl_contacts.py
```

---

## 🔒 Safety Features

### Close CRM Protection (Still Active)
- ❌ **NO writes** to Close CRM
- ✅ **YES reads** for deduplication
- ✅ **YES CSV exports** for manual review
- 🛡️ Kill switch: `CLOSE_WRITE_DISABLED=True` in `.env`

**Why CSV-only?**
- Prevents accidental bulk operations
- You review before importing
- Full control over what goes into Close

---

## 📈 Latest Run Results

**Run**: 2025-11-17 6:08 PM
**Input**: 21 companies
**Output**: 78 ATL contacts
**Success Rate**: 67% (14/21 companies had contacts)
**Cost**: $0.21

**Top Companies:**
- ReVision Energy: 31 contacts
- Brower Mechanical: 6 contacts
- Halco Energy: 6 contacts
- Barron Heating: 11 contacts

**File**: `backend/data/enrichment_runs/2025-11-17_180840/atl_contacts.csv`

---

## 🚀 Next Steps

### To Import to Close CRM:

1. **Open CSV**: `backend/data/enrichment_runs/LATEST/atl_contacts.csv`

2. **Review contacts**:
   - Check confidence scores (recommend >90%)
   - Verify job titles are decision-makers
   - Check LinkedIn profiles

3. **Manual import to Close**:
   - Option A: CSV import in Close CRM UI
   - Option B: Bulk API import (requires re-enabling writes)

4. **Filter by quality**:
   ```excel
   =FILTER(confidence >= 90)  # High confidence only
   =FILTER(linkedin <> "")     # LinkedIn verified
   ```

---

## 🎯 Pro Tips

### Get Better Results:
1. **Use full domain**: `acmehvac.com` not `www.acmehvac.com`
2. **Company size matters**: Larger companies = more contacts
3. **Tech companies**: Best Hunter.io coverage (90%+)
4. **Contractors**: Good coverage (70-80%)

### Optimize Costs:
- Hunter.io caches for 24 hours
- Re-running same companies = no extra cost
- Focus on high-value targets first

### Phone Number Availability:
- Not all contacts have phone numbers in Hunter.io
- More common for senior roles (CEO, VP)
- Alternative: LinkedIn InMail, cold email

---

## 🆘 Troubleshooting

### No contacts found?
- Check domain spelling
- Try without `www.`
- Company may not have public emails
- Try LinkedIn Sales Navigator instead

### Low confidence scores?
- Normal for smaller companies
- Scores 70-84% still valuable
- Cross-reference with LinkedIn

### Script errors?
```bash
# Check environment
source venv/bin/activate

# Check Hunter.io API key
grep HUNTER_API_KEY .env

# Test Hunter.io connection
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('HUNTER_API_KEY'))"
```

---

## Summary

**Clean, Simple, Effective:**
- ✅ One CSV per enrichment run
- ✅ Clear dated folders
- ✅ Phone numbers included
- ✅ Safe (no Close CRM writes)
- ✅ Ready for manual import

**Your latest enrichment is ready:**
```
backend/data/enrichment_runs/2025-11-17_180840/atl_contacts.csv
```

**78 decision-makers discovered across 21 companies**

Import to Close CRM when ready! 🎉
