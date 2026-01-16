# Dealer Scraper Sync API - Quick Reference

## Endpoint Created

**Location**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/app/api/sync_from_scraper.py`

**Registered in**: `app/main.py` (line 236)

**API Prefix**: `/api/v1/scraper`

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/scraper/contractors` | Receive batch of scraped contractors |
| POST | `/api/v1/scraper/contacts` | Receive batch of scraped contacts |
| GET | `/api/v1/scraper/status` | Get sync status and last sync time |

---

## Quick Test

```bash
# Start server
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
source venv/bin/activate
cd backend
python start_server.py

# Test contractor import (new terminal)
curl -X POST http://localhost:8001/api/v1/scraper/contractors \
  -H "Content-Type: application/json" \
  -d '{
    "contractors": [{
      "company_name": "Test HVAC",
      "normalized_name": "test hvac",
      "domain": "testhvac.com",
      "state": "tx",
      "oem_brands": ["Carrier"],
      "source_scraper": "test"
    }],
    "batch_id": "test_001",
    "source_scraper": "test"
  }'

# Check status
curl http://localhost:8001/api/v1/scraper/status

# View API docs
open http://localhost:8001/api/v1/docs#/dealer-scraper
```

---

## Key Features

1. **Deduplication** - Matches by normalized_name → phone → domain
2. **OEM Brand Merging** - Combines brands from multiple sources
3. **Audit Logging** - All imports logged to `lead_audit_log`
4. **Error Handling** - Partial success with detailed error array
5. **Batch Processing** - Optimized for 100-500 records per batch

---

## Files Created

| File | Purpose |
|------|---------|
| `app/api/sync_from_scraper.py` | Main endpoint (500+ lines) |
| `DEALER_SCRAPER_API.md` | Full API documentation |
| `INTEGRATION_GUIDE.md` | Integration guide for dealer-scraper-mvp |
| `tests/test_sync_from_scraper.py` | Unit tests |
| `app/api/README_SCRAPER_SYNC.md` | This file |

---

## Next Steps

1. **Test locally** - Run curl commands above
2. **Update dealer-scraper-mvp** - Add Celery task to push data
3. **Monitor imports** - Check Supabase `dim_companies` and `lead_audit_log`
4. **Scale up** - Increase batch sizes as needed

---

## Documentation

**Full API Docs**: `/backend/DEALER_SCRAPER_API.md`

**Integration Guide**: `/backend/INTEGRATION_GUIDE.md`

**Swagger UI**: http://localhost:8001/api/v1/docs#/dealer-scraper
