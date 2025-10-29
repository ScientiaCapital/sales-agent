# Terminal Testing Guide

## Quick Start

This guide shows you how to test LangGraph agents via the interactive terminal CLI.

## Prerequisites

### 1. Environment Setup

```bash
# Activate virtual environment (if using one)
source venv/bin/activate  # or: source backend/venv/bin/activate

# Install dependencies (if not already done)
pip install -r backend/requirements.txt
```

### 2. Start Infrastructure

```bash
# Start Docker services
docker-compose up -d

# Verify services
docker-compose ps
```

### 3. Start FastAPI Server (Optional - for API testing)

```bash
# In a separate terminal
python3 start_server.py
```

Server runs at: `http://localhost:8001`

## Agent CLI Usage

### Interactive Mode (Recommended)

```bash
python3 agent_cli.py
```

You'll see a menu:
```
┌─────────────────────────────────┐
│        Sales Agent CLI         │
│  Interactive terminal for      │
│     LangGraph agents           │
└─────────────────────────────────┘

Select an agent:
1. Qualification Agent - Score leads (<1000ms)
2. Enrichment Agent - Enrich contacts (<3000ms)
3. Conversation Agent - Voice chat (<1000ms/turn)
4. Exit

Choice: 
```

### Direct Agent Invocation

**Qualification Agent:**
```bash
python3 agent_cli.py --agent qualify
```

**Enrichment Agent:**
```bash
python3 agent_cli.py --agent enrich
```

**Conversation Agent:**
```bash
python3 agent_cli.py --agent converse
```

### Enable LangSmith Tracing

```bash
python3 agent_cli.py --trace
```

This enables tracing to LangSmith for debugging and monitoring.

## Testing Individual Agents

### 1. Qualification Agent

**Purpose:** Score leads using Cerebras AI (<1000ms target)

**Interactive Example:**
```bash
python3 agent_cli.py
# Select: 1
# Enter:
#   Company name: Acme Corp
#   Industry: SaaS
#   Company size: 50-200
```

**Expected Output:**
```
┌─────────────────────────────────┐
│        Qualification Results    │
├─────────────┬───────────────────┤
│ Score       │ 85/100            │
│ Tier        │ HOT               │
│ Latency     │ 450ms             │
│ Cost        │ $0.000045         │
└─────────────┴───────────────────┘

Reasoning:
Strong SaaS alignment with mid-market size...
```

**API Testing:**
```bash
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qualification",
    "input": {
      "company_name": "Acme Corp",
      "industry": "SaaS",
      "company_size": "50-200"
    }
  }'
```

### 2. Enrichment Agent

**Purpose:** Enrich contacts with Apollo.io and LinkedIn data (<3000ms target)

**Interactive Example:**
```bash
python3 agent_cli.py
# Select: 2
# Enter:
#   Email: john@acme.com
#   LinkedIn URL (optional): https://linkedin.com/in/johndoe
```

**Expected Output:**
```
┌─────────────────────────────────┐
│        Enrichment Results        │
├─────────────┬───────────────────┤
│ Sources     │ Apollo, LinkedIn │
│ Confidence  │ 92%              │
│ Latency     │ 2.1s             │
└─────────────┴───────────────────┘

Enriched Data:
- Name: John Doe
- Title: CEO
- Company: Acme Corp
...
```

**API Testing:**
```bash
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "enrichment",
    "input": {
      "email": "john@acme.com",
      "linkedin_url": "https://linkedin.com/in/johndoe"
    }
  }'
```

### 3. Conversation Agent

**Purpose:** Voice-enabled conversational AI (<1000ms/turn target)

**Interactive Example:**
```bash
python3 agent_cli.py
# Select: 3
# Enter messages:
#   User: Hello, I'm interested in your services
#   Agent: [Responds with voice output]
```

**API Testing:**
```bash
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "conversation",
    "input": {
      "user_input": "Hello, I need help with lead qualification"
    }
  }'
```

## Testing with Imported Leads

After importing leads via CSV, test agents on real data:

### 1. Get Lead IDs

```bash
# Get all leads
curl http://localhost:8001/api/leads/ | jq '.leads[0:5] | .[] | {id, company_name, contact_email}'
```

### 2. Test Qualification on Imported Leads

```bash
# Get a lead
LEAD_ID=1
curl http://localhost:8001/api/leads/$LEAD_ID | jq

# Qualify it
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qualification",
    "input": {
      "company_name": "A & A GENPRO INC.",
      "industry": "Generator/Electrical Services",
      "company_size": ""
    },
    "lead_id": '$LEAD_ID'
  }'
```

### 3. Test Enrichment on Imported Leads

```bash
# Enrich contact (if email available)
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "enrichment",
    "input": {
      "email": "contact@example.com"
    },
    "lead_id": '$LEAD_ID'
  }'
```

## Performance Benchmarks

### Expected Latencies

- **Qualification Agent**: <1000ms (typical: 450-800ms)
- **Enrichment Agent**: <3000ms (typical: 1500-2500ms)
- **Conversation Agent**: <1000ms per turn (typical: 500-900ms)

### Cost Targets

- **Qualification**: <$0.0001 per request (Cerebras)
- **Enrichment**: <$0.01 per request (Apollo + Claude)
- **Conversation**: <$0.01 per turn (Cerebras + Cartesia)

## Streaming Tests

### SSE Streaming

```bash
curl -X POST http://localhost:8001/api/langgraph/stream \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qualification",
    "input": {
      "company_name": "Acme Corp",
      "industry": "SaaS"
    },
    "stream_mode": "messages"
  }'
```

You'll see real-time token streaming:
```
data: {"type":"start","agent_type":"qualification"}

data: {"type":"message","content":"Qualifying lead..."}

data: {"type":"complete","output":{...}}
```

## Troubleshooting

### Error: "Module not found"

**Fix:** Make sure you're in the project root and backend is in Python path:
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

### Error: "Cannot connect to server"

**Fix:** Start the FastAPI server:
```bash
python3 start_server.py
```

### Error: "Redis connection failed"

**Fix:** Start Redis:
```bash
docker-compose up -d redis
```

### Error: "Database connection failed"

**Fix:** Start PostgreSQL:
```bash
docker-compose up -d postgres
```

### Agent Returns Error

**Check logs:**
```bash
# Server logs (if running in foreground)
# Or check terminal output from agent_cli.py
```

**Common issues:**
- Missing API keys (check `.env` file)
- Rate limits exceeded (wait and retry)
- Invalid input format (check API docs)

## Production Testing

### Run Production Test Suite

```bash
cd backend
pytest tests/test_agents_production.py -v
```

### Run CLI Tests

```bash
pytest tests/test_agent_cli.py -v
```

### Performance Benchmarks

```bash
cd backend
pytest tests/test_agents_production.py::TestQualificationAgentProduction -v
```

## Next Steps

After testing agents:

1. **Import CSV** (see `CSV_IMPORT_GUIDE.md`)
2. **Enrich contacts** (see batch enrichment script)
3. **Qualify leads** using Qualification Agent
4. **Create campaigns** for qualified leads

## Additional Resources

- **API Documentation**: http://localhost:8001/api/docs
- **LangSmith Tracing**: https://smith.langchain.com (if enabled)
- **Agent Architecture**: See `LANGGRAPH_GUIDE.md`

