# Next Steps - Server is Running! 🚀

# Next Steps - Server is Running! 🚀

## ✅ Server Status

Your server is now running at: **http://localhost:8001**

**IMPORTANT**: All API endpoints are prefixed with `/api/v1/` (not `/api/`)

## Quick Start Guide

### 1. Check Server Health

```bash
curl http://localhost:8001/api/v1/health
```

Or visit: http://localhost:8001/api/v1/docs (Swagger UI)

### 2. Import Your CSV File

You have `companies_ready_to_import.csv` ready to import:

```bash
# Activate venv if not already active
source venv/bin/activate

# Import CSV
python3 scripts/import_csv_simple.py companies_ready_to_import.csv
```

Or use the API directly:
```bash
curl -X POST http://localhost:8001/api/v1/leads/import/csv \
  -F "file=@companies_ready_to_import.csv"
```

### 3. Discover ATL Contacts

After importing, discover Above-The-Line contacts:

```bash
# Discover ATL contacts (website + LinkedIn)
python3 scripts/discover_atl_contacts.py --limit 10

# Or discover for all imported leads
python3 scripts/discover_atl_contacts.py
```

### 4. Enrich with Apollo (if you have API key)

```bash
# Set your Apollo API key in .env first
# Then enrich leads
python3 scripts/batch_enrich_companies.py --mode email_only --limit 10

# Or use Apollo company search
python3 scripts/batch_enrich_companies.py --mode company_search --limit 10
```

### 5. Full Pipeline (Import + Discover + Enrich)

```bash
# Run complete pipeline
python3 scripts/full_pipeline.py --limit 5
```

## Available API Endpoints

### Lead Management
- `GET /api/v1/leads/` - List all leads
- `POST /api/v1/leads/qualify` - Qualify a lead
- `POST /api/v1/leads/import/csv` - Import CSV

### Contact Discovery
- `POST /api/v1/contacts/discover` - Discover ATL contacts
- `GET /api/v1/contacts/org-chart/{company_name}` - Build org chart

### Apollo Enrichment
- `POST /api/v1/apollo/enrich` - Enrich single contact
- `POST /api/v1/apollo/enrich/bulk` - Bulk enrich

### LangGraph Agents
- `POST /api/v1/langgraph/invoke` - Run agent (qualification, enrichment, etc.)
- `POST /api/v1/langgraph/stream` - Stream agent execution

## View Your Data

### Check imported leads:
```bash
curl http://localhost:8001/api/v1/leads/ | python3 -m json.tool | head -50
```

### Check specific lead:
```bash
curl http://localhost:8001/api/v1/leads/{lead_id} | python3 -m json.tool
```

## Interactive Testing

### Use the Agent CLI:
```bash
python3 agent_cli.py
```

This gives you an interactive menu to:
- Test qualification agent
- Test enrichment agent
- Test conversation agent
- Run streaming tests

## Next Steps

1. **Import your CSV** - Start with importing your 200 companies
2. **Discover ATL contacts** - Find decision makers via website + LinkedIn
3. **Enrich with Apollo** - Add contact details and emails
4. **Test agents** - Try the qualification and enrichment agents
5. **Explore API** - Check out http://localhost:8001/api/docs

## Useful Commands

```bash
# Check server logs
tail -f /tmp/server.log  # if running in background

# Stop server
pkill -f "start_server.py|uvicorn"

# Restart server
source venv/bin/activate
python3 start_server.py
```

## Documentation

- **CSV Import**: See `CSV_IMPORT_GUIDE.md`
- **ATL Discovery**: See `ATL_DISCOVERY_GUIDE.md`
- **Quick Start**: See `QUICK_START.md`
- **Terminal Testing**: See `TERMINAL_TESTING_GUIDE.md`

---

**Ready to go!** Start by importing your CSV file and discovering ATL contacts! 🎯

