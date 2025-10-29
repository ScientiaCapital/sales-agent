# CSV Import & Enrichment - Quick Reference

## ✅ What's Ready

All scripts and guides are ready to use!

## 📋 Step-by-Step Process

### Step 1: Transform Your CSV

Your CSV file has been transformed! Check:
```bash
ls -lh companies_ready_to_import.csv
head -3 companies_ready_to_import.csv
```

**Already done:** ✅ 200 companies transformed

### Step 2: Start Server

**Important:** Start the FastAPI server first:

```bash
# In a terminal window
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
python3 start_server.py
```

Keep this terminal open! Server runs at `http://localhost:8001`

### Step 3: Import CSV

**Option A: Using the quick import script (recommended)**
```bash
python3 scripts/quick_import.py
```

**Option B: Using the import script directly**
```bash
python3 scripts/import_csv.py companies_ready_to_import.csv
```

**Option C: Using curl**
```bash
curl -X POST "http://localhost:8001/api/leads/import/csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@companies_ready_to_import.csv"
```

### Step 4: Verify Import

```bash
# Check how many leads were imported
curl http://localhost:8001/api/leads/ | python3 -m json.tool | grep total

# View first 5 leads
curl http://localhost:8001/api/leads/ | python3 -m json.tool | head -50
```

### Step 5: Enrich Contacts with Apollo

**Enrich leads that have emails:**
```bash
python3 scripts/batch_enrich_companies.py --mode email_only --limit 10
```

**Enrich company data (for leads without emails):**
```bash
python3 scripts/batch_enrich_companies.py --mode company_search --limit 10
```

**Enrich all leads:**
```bash
python3 scripts/batch_enrich_companies.py --mode email_only --limit 0
```

## 📁 Files Created

1. **`scripts/transform_dealer_csv.py`** - Transforms dealer CSV to import format ✅
2. **`scripts/import_csv.py`** - Python script for CSV import ✅
3. **`scripts/quick_import.py`** - Quick import with server check ✅
4. **`scripts/batch_enrich_companies.py`** - Batch enrichment script ✅
5. **`CSV_IMPORT_GUIDE.md`** - Complete import guide ✅
6. **`TERMINAL_TESTING_GUIDE.md`** - Agent testing guide ✅
7. **`CSV_TEMPLATE.csv`** - Example CSV format ✅
8. **`companies_ready_to_import.csv`** - Your transformed CSV (200 companies) ✅

## 🎯 Quick Commands

```bash
# 1. Transform CSV (already done)
python3 scripts/transform_dealer_csv.py

# 2. Start server (in separate terminal)
python3 start_server.py

# 3. Import CSV
python3 scripts/quick_import.py

# 4. Test agents
python3 agent_cli.py

# 5. Enrich contacts
python3 scripts/batch_enrich_companies.py --mode email_only --limit 10
```

## 📊 Expected Results

**CSV Import:**
- ✅ 200 companies imported in ~3-4 seconds
- ✅ ~50-70 leads/second import rate

**Enrichment:**
- ✅ ~15 seconds per contact (with Apollo API)
- ✅ ~5 contacts processed concurrently
- ✅ Respects Apollo rate limits (600/hour)

## ⚠️ Troubleshooting

**Server won't start:**
- Check if port 8001 is already in use: `lsof -i :8001`
- Check Docker services: `docker-compose ps`
- Check environment variables: `cat .env | grep DATABASE_URL`

**Import fails:**
- Verify server is running: `curl http://localhost:8001/api/health`
- Check CSV format: `head -1 companies_ready_to_import.csv`
- Check file exists: `ls -lh companies_ready_to_import.csv`

**Enrichment fails:**
- Check Apollo API key: `echo $APOLLO_API_KEY`
- Check rate limits (Apollo: 600 requests/hour)
- Check database connection: `docker-compose ps`

## 📚 Documentation

- **CSV Import Guide:** `CSV_IMPORT_GUIDE.md`
- **Terminal Testing:** `TERMINAL_TESTING_GUIDE.md`
- **API Docs:** http://localhost:8001/api/docs (when server running)

## 🚀 Next Steps

1. **Import your CSV** (200 companies ready)
2. **Test agents** with `python3 agent_cli.py`
3. **Enrich contacts** with Apollo
4. **Qualify leads** using Qualification Agent
5. **Create campaigns** for qualified leads

---

**Ready to go!** Start the server and run the import. 🎉

