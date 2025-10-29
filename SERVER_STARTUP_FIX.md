# Server Startup Fix Guide

## Issue: Missing Dependencies

The server requires Python packages that may not be installed. Install them:

### Quick Fix

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent

# Install all dependencies
pip3 install -r backend/requirements.txt

# Or install minimal set for CSV import/enrichment:
pip3 install fastapi uvicorn sqlalchemy psycopg3-binary python-dotenv httpx beautifulsoup4 requests
```

### Optional Dependencies (Server works without these)

**pgvector** - For knowledge base vector search (optional):
```bash
pip3 install pgvector
```

**cerebras** - For Cerebras AI integration (optional for CSV import):
```bash
pip3 install cerebras-cloud-sdk
```

### After Installing Dependencies

```bash
# Start server
python3 start_server.py

# Should see:
# ✓ Environment variables loaded successfully
# ⚠️  Notification system error (non-fatal): ...
#    Continuing without notifications...
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Quick Test

```bash
# Test server health
curl http://localhost:8001/api/health

# Should return: {"status":"healthy",...}
```

## Minimal Setup (Just CSV Import)

If you only need CSV import (no AI agents), install minimal dependencies:

```bash
pip3 install fastapi uvicorn sqlalchemy psycopg3-binary python-dotenv httpx beautifulsoup4 requests pydantic
```

Then start server - it will work for CSV import even without Cerebras/Apollo.

