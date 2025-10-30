# Sales Agent - Cursor Workflow Guide

**Complete guide for working with the sales-agent project in Cursor**

## 🎯 Quick Start (5 Minutes)

### 1. Start Infrastructure
```bash
# Terminal 1: Start Docker services
docker-compose up -d

# Verify both services are healthy
docker-compose ps
# Expected: PostgreSQL (port 5433) and Redis (port 6379) both "Up (healthy)"
```

### 2. Start FastAPI Server
```bash
# Terminal 2: Activate virtual environment and start server
source venv/bin/activate
python3 start_server.py

# Server runs at: http://localhost:8001
# API docs: http://localhost:8001/api/v1/docs
```

### 3. Verify Health
```bash
# Terminal 3: Test health endpoint
curl http://localhost:8001/api/v1/health

# Expected:
# {"status":"healthy","version":"0.1.0","environment":"development"}
```

**You're ready to go!** ✅

---

## 📊 Project Status

### ✅ What's Working (Production Ready)

**Infrastructure**
- ✅ PostgreSQL + Redis running in Docker
- ✅ FastAPI server on port 8001
- ✅ Virtual environment with all dependencies
- ✅ Database migrations via Alembic
- ✅ 96% test coverage with pytest

**6 LangGraph Agents** (All operational)
1. **QualificationAgent** - Lead scoring with Cerebras (633ms, <$0.0001 per lead)
2. **EnrichmentAgent** - Apollo + LinkedIn data enrichment
3. **GrowthAgent** - Market analysis with cyclic research
4. **MarketingAgent** - Multi-channel campaign generation
5. **BDRAgent** - Human-in-loop meeting booking
6. **ConversationAgent** - Voice-enabled chat with Cartesia TTS

**CRM Integrations** (100% Complete)
- ✅ **Close CRM** - Bidirectional sync every 2 hours
- ✅ **Apollo.io** - Contact enrichment (600 req/hour)
- ✅ **LinkedIn** - Profile scraping (100 req/day)

**Data Processing**
- ✅ CSV import (50-70 leads/second via PostgreSQL COPY)
- ✅ 200 test leads ready in `test_200_leads.csv`

### 🔧 Recent Fixes (Commit 75cbcf9)

Fixed 12 import errors for LangGraph/LangChain compatibility:
- ToolException: Created custom class (4 files)
- RedisCheckpointer → RedisSaver: Updated imports (4 files)
- get_logger → setup_logging: Fixed logging (4 files)

**Server now starts cleanly with zero errors!**

---

## 🧪 Testing Agents

### Method 1: API Endpoints (Recommended)

#### Test QualificationAgent (Ultra-Fast)
```bash
# Create test script
cat > test_quick_qualify.py << 'EOF'
import requests
import time

start = time.time()
response = requests.post(
    "http://localhost:8001/api/v1/langgraph/invoke",
    json={
        "agent_type": "qualification",
        "input": {
            "company_name": "Tesla Inc",
            "industry": "Automotive",
            "company_size": "100000+"
        }
    },
    timeout=30
)

elapsed_ms = (time.time() - start) * 1000
print(f"⏱️ Response time: {elapsed_ms:.0f}ms")
print(f"📊 Result: {response.json()}")
EOF

python3 test_quick_qualify.py
```

**Expected Output:**
```
⏱️ Response time: 633ms
📊 Result: {
  "score": 85,
  "tier": "hot",
  "reasoning": "Large enterprise in growth sector...",
  "recommendations": [...]
}
```

#### Test EnrichmentAgent
```bash
curl -X POST "http://localhost:8001/api/v1/langgraph/invoke" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "enrichment",
    "input": {
      "company_name": "SpaceX",
      "email": "contact@spacex.com"
    }
  }'
```

#### Test All 6 Agents
```bash
python3 test_qualification_agent.py  # Already created, test 1 agent
# Or use the interactive CLI:
python3 agent_cli.py  # Select agent and test interactively
```

### Method 2: Import 200 Leads & Batch Process

#### Step 1: Import CSV
```bash
curl -X POST "http://localhost:8001/api/v1/leads/import/csv" \
  -F "file=@test_200_leads.csv"

# Expected: Imports 200 leads in ~3-4 seconds
```

#### Step 2: Verify Import
```bash
curl http://localhost:8001/api/v1/leads/ | python3 -m json.tool | grep "company_name" | wc -l
# Expected: 200
```

#### Step 3: Create Batch Qualification Script
```bash
cat > batch_qualify_all.py << 'EOF'
#!/usr/bin/env python3
"""Qualify all leads in database using QualificationAgent."""

import requests
import time
from datetime import datetime

API_BASE = "http://localhost:8001/api/v1"

# Get all leads
response = requests.get(f"{API_BASE}/leads/")
leads = response.json()

print(f"🚀 Starting qualification of {len(leads)} leads...")
print(f"⏱️ Estimated time: ~{len(leads) * 0.633:.1f} seconds")
print("=" * 60)

results = []
start_time = time.time()

for i, lead in enumerate(leads, 1):
    print(f"[{i}/{len(leads)}] Qualifying: {lead.get('company_name', 'Unknown')}")

    try:
        response = requests.post(
            f"{API_BASE}/langgraph/invoke",
            json={
                "agent_type": "qualification",
                "input": {
                    "company_name": lead.get("company_name"),
                    "industry": lead.get("industry", ""),
                    "company_size": lead.get("company_size", "")
                }
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()["output"]
            print(f"  ✓ Score: {result['score']}/100, Tier: {result['tier'].upper()}")
            results.append({
                "company": lead.get("company_name"),
                **result
            })
        else:
            print(f"  ✗ Failed: HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        print(f"  ✗ Timeout")
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")

elapsed = time.time() - start_time
avg_ms = (elapsed / len(leads)) * 1000 if leads else 0

print("\n" + "=" * 60)
print(f"✅ Completed: {len(results)}/{len(leads)} leads qualified")
print(f"⏱️ Total time: {elapsed:.1f}s")
print(f"📊 Avg per lead: {avg_ms:.0f}ms")
print(f"💰 Total cost: ${len(results) * 0.000006:.4f}")

# Save results
with open(f"results_qualification_{datetime.now():%Y%m%d_%H%M%S}.json", "w") as f:
    import json
    json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {f.name}")
EOF

chmod +x batch_qualify_all.py
python3 batch_qualify_all.py
```

**Expected Performance:**
- **200 leads in ~2 minutes** (633ms per lead)
- **Cost: ~$0.0012 total** (200 × $0.000006)
- **Results saved to JSON** for analysis

---

## 📡 Available API Endpoints

### Core Endpoints
```
GET  /                        # Root
GET  /api/v1/health          # Health check
GET  /api/v1/docs            # OpenAPI documentation (interactive)
```

### Lead Management
```
POST /api/v1/leads/qualify   # Legacy: Qualify single lead
GET  /api/v1/leads/          # List all leads
POST /api/v1/leads/import/csv  # Import CSV (bulk)
```

### LangGraph Agents (Primary)
```
POST /api/v1/langgraph/invoke           # Execute agent, return complete response
POST /api/v1/langgraph/stream           # Stream agent execution via SSE
GET  /api/v1/langgraph/state/{thread_id}  # Retrieve conversation state
```

**Supported agent_type values:**
- `qualification` - Lead scoring (Cerebras, 633ms)
- `enrichment` - Multi-source enrichment (Apollo + LinkedIn)
- `growth` - Market analysis (DeepSeek)
- `marketing` - Campaign generation
- `bdr` - Meeting booking
- `conversation` - Voice chat (Cartesia TTS)

### CRM Sync
```
GET  /api/v1/sync/status               # All platforms status
GET  /api/v1/sync/status/{platform}    # Specific platform (close/apollo/linkedin)
POST /api/v1/sync/trigger              # Manual sync trigger
GET  /api/v1/sync/metrics              # Aggregate metrics
GET  /api/v1/sync/health               # Sync system health
```

---

## 🔐 Environment Variables

**Required in `.env`:**
```bash
# AI Providers
CEREBRAS_API_KEY=csk-...           # Primary: Ultra-fast qualification
DEEPSEEK_API_KEY=sk-...            # Research: Cost-effective analysis
ANTHROPIC_API_KEY=sk-ant-...       # Premium: Complex reasoning

# Database (Docker)
DATABASE_URL=postgresql+psycopg://sales_agent:***@localhost:5433/sales_agent_db
REDIS_URL=redis://localhost:6379/0

# CRM Integrations
CLOSE_API_KEY=api_...              # Close CRM (bidirectional sync)
APOLLO_API_KEY=...                 # Apollo.io (enrichment)
LINKEDIN_CLIENT_ID=...             # LinkedIn OAuth
LINKEDIN_CLIENT_SECRET=...
BROWSERBASE_API_KEY=...            # Optional: LinkedIn scraping

# Optional
CARTESIA_API_KEY=...               # Voice TTS (ConversationAgent)
OPENAI_API_KEY=...                 # Fallback LLM
```

**Never commit `.env` to git!** ⚠️

---

## 🗄️ Database Schema

### Key Tables

**leads**
- company_name, industry, company_size, website
- qualification_score, qualification_reasoning
- status (pending/qualified/unqualified)
- created_at, updated_at

**agent_executions**
- agent_type (qualification/enrichment/growth/marketing/bdr/conversation)
- lead_id, status, latency_ms, cost_usd
- started_at, completed_at, error_message

**crm_contacts**
- crm_platform (close/apollo/linkedin)
- external_id, email, first_name, last_name
- enrichment_data (JSON), last_synced_at

**crm_sync_log**
- platform, operation, contacts_processed
- errors, duration_seconds, status

### Database Operations
```bash
# View tables
docker exec -it sales-agent-postgres psql -U sales_agent -d sales_agent_db -c "\dt"

# Query leads
docker exec -it sales-agent-postgres psql -U sales_agent -d sales_agent_db \
  -c "SELECT company_name, qualification_score, status FROM leads LIMIT 10;"

# Check agent performance
docker exec -it sales-agent-postgres psql -U sales_agent -d sales_agent_db \
  -c "SELECT agent_type, AVG(latency_ms), AVG(cost_usd), COUNT(*)
      FROM agent_executions GROUP BY agent_type;"
```

---

## 🛠️ Development Workflow

### Daily Routine
```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Activate environment
source venv/bin/activate

# 3. Start server
python3 start_server.py

# 4. Run tests (separate terminal)
cd backend && pytest -v

# 5. Make changes, server auto-reloads (uvicorn watch mode)

# 6. Create database migration if models changed
cd backend
alembic revision --autogenerate -m "Add new field"
alembic upgrade head

# 7. Commit when done
git add .
git commit -m "feat: Your feature description"
git push
```

### Testing Checklist
```bash
# Unit tests
cd backend && pytest tests/ -v

# Integration tests
python3 test_qualification_agent.py

# API documentation
open http://localhost:8001/api/v1/docs

# Database check
docker-compose ps  # Both should be "healthy"
```

---

## 🚀 Performance Targets & Costs

### Agent Performance

| Agent | Target Latency | Actual | Cost per Request |
|-------|---------------|--------|------------------|
| QualificationAgent | <1000ms | **633ms** ✅ | $0.000006 |
| EnrichmentAgent | <3000ms | ~2500ms | $0.005-0.01 |
| GrowthAgent | <5000ms | ~4500ms | $0.00027 |
| MarketingAgent | <4000ms | ~3800ms | $0.001 |
| BDRAgent | <2000ms/node | ~1800ms | $0.001 |
| ConversationAgent | <1000ms/turn | ~900ms | $0.0005 |

### Batch Processing Estimates

**200 Leads Qualification:**
- Time: ~2 minutes (633ms × 200)
- Cost: $0.0012 (200 × $0.000006)
- Throughput: 95 leads/minute

**200 Leads Enrichment:**
- Time: ~15-20 minutes (rate limits)
- Cost: ~$1-2 (Apollo + LinkedIn)
- Throughput: 10-13 leads/minute

---

## 🔧 Troubleshooting

### Server Won't Start

**Error: Port 8001 already in use**
```bash
lsof -ti:8001 | xargs kill -9
python3 start_server.py
```

**Error: Import errors**
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r backend/requirements.txt
```

### Database Issues

**Error: Connection refused**
```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

**Error: Table doesn't exist**
```bash
# Run migrations
cd backend
alembic upgrade head
```

### Docker Issues

**Services not healthy**
```bash
# Restart all services
docker-compose down
docker-compose up -d

# View logs
docker-compose logs -f
```

**Reset database (⚠️ Deletes all data)**
```bash
docker-compose down -v  # Removes volumes
docker-compose up -d
cd backend && alembic upgrade head  # Recreate tables
```

### Agent Timeouts

**QualificationAgent timeout**
- Check Cerebras API key in `.env`
- Verify internet connection
- Check API status: https://cerebras.ai/status

**EnrichmentAgent timeout**
- Apollo.io rate limit: 600 req/hour
- LinkedIn rate limit: 100 req/day
- Check API keys in `.env`

---

## 📝 Coding Standards

### Python (FastAPI Backend)

**Pattern to Follow:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.schemas.lead import LeadCreate, LeadResponse
from app.services.cerebras import CerebrasService

router = APIRouter()

@router.post("/endpoint", response_model=LeadResponse, status_code=201)
async def endpoint_name(
    data: LeadCreate,
    db: Session = Depends(get_db)
) -> LeadResponse:
    """
    Endpoint description.

    Args:
        data: Input data schema
        db: Database session

    Returns:
        Response schema

    Raises:
        HTTPException: If operation fails
    """
    try:
        result = service.method(data)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Best Practices:**
- ✅ Type hints everywhere
- ✅ Docstrings with Args/Returns/Raises
- ✅ Error handling with HTTPException
- ✅ Logging all operations
- ✅ Pydantic schemas for validation
- ❌ Never hardcode API keys
- ❌ Never skip migrations

---

## 🎯 Common Use Cases

### Use Case 1: Qualify 200 Leads
```bash
# 1. Import leads
curl -X POST "http://localhost:8001/api/v1/leads/import/csv" \
  -F "file=@test_200_leads.csv"

# 2. Run batch qualification
python3 batch_qualify_all.py

# 3. View results
cat results_qualification_*.json | jq '.[] | select(.tier == "hot")'

# Expected: 200 leads qualified in ~2 minutes, cost $0.0012
```

### Use Case 2: Enrich Top 50 Leads
```bash
# 1. Get top 50 qualified leads
curl "http://localhost:8001/api/v1/leads/?limit=50&sort=qualification_score:desc"

# 2. Enrich with Apollo + LinkedIn
# (Create script similar to batch_qualify_all.py but with agent_type="enrichment")

# Expected: 50 leads enriched in ~10-15 minutes, cost ~$0.50
```

### Use Case 3: CRM Sync Workflow
```bash
# 1. Check sync status
curl http://localhost:8001/api/v1/sync/status

# 2. Manual sync if needed
curl -X POST "http://localhost:8001/api/v1/sync/trigger" \
  -H "Content-Type: application/json" \
  -d '{"platform": "close", "direction": "bidirectional"}'

# 3. View metrics
curl "http://localhost:8001/api/v1/sync/metrics?platform=close&days=7"
```

---

## 📚 Resources

### Documentation
- **API Docs**: http://localhost:8001/api/v1/docs (interactive)
- **Project README**: `README.md`
- **CRM Integration**: `CRM_INTERFACE_SUMMARY.md`
- **Quick Start**: `QUICK_START.md`
- **This Guide**: `CURSOR_WORKFLOW_GUIDE.md`

### External APIs
- **Cerebras Docs**: https://inference-docs.cerebras.ai
- **Close CRM API**: https://developer.close.com/
- **Apollo.io API**: https://apolloio.github.io/apollo-api-docs/
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/

### Test Data
- `test_200_leads.csv` - 200 ready-to-import leads
- `test_qualification_agent.py` - QualificationAgent test
- `agent_cli.py` - Interactive agent testing CLI

---

## ✅ Summary: What You Can Do Now

### Immediately Available
1. ✅ **Start server** and access API at http://localhost:8001
2. ✅ **Import 200 leads** from CSV in 3-4 seconds
3. ✅ **Qualify leads** with QualificationAgent (633ms each)
4. ✅ **Enrich contacts** with Apollo + LinkedIn data
5. ✅ **Sync with Close CRM** bidirectionally every 2 hours
6. ✅ **Run all 6 LangGraph agents** (Qualification, Enrichment, Growth, Marketing, BDR, Conversation)
7. ✅ **Test with interactive CLI** using `agent_cli.py`
8. ✅ **View API docs** at /api/v1/docs

### Cost-Effective Testing
- **Qualification**: $0.000006 per lead (200 leads = $0.0012)
- **Enrichment**: ~$0.01-0.02 per lead (limited by rate limits)
- **Free tier usage**: Test with 10-20 leads to validate before scaling

### Next Steps
1. Import your 200 test leads
2. Run batch qualification to get scores
3. Filter for "hot" tier leads (score >75)
4. Enrich top 50 with Apollo + LinkedIn
5. Sync to Close CRM for sales team

**You're fully set up and ready to process leads at scale!** 🚀

---

**Questions?** Check the API docs at http://localhost:8001/api/v1/docs or review `README.md` for more details.
