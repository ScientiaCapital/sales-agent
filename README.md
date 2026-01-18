# Sales Agent

> **B2B sales automation** with Close CRM integration. 3,422 companies, 11,803 contacts.
> Multi-agent pipeline for lead enrichment, ICP scoring, and campaign automation.

---

## What It Does

- **Close CRM integration** - Bidirectional sync with deduplication
- **Lead enrichment pipeline** - Company data, contact discovery, ICP scoring
- **Free-first enrichment** - Website email extraction before paid APIs
- **Campaign automation** - Multi-touch sequences with personalization
- **FastAPI backend** - Sub-second qualification (633ms average)

## Goals

Automate the BDR workflow from lead enrichment to personalized outreach via Close CRM.

## Quick Start

```bash
cd sales-agent
pip install -r requirements.txt
cp .env.example .env  # Add API keys

# Start infrastructure
docker-compose up -d

# Run migrations
cd backend && alembic upgrade head

# Start server
python start_server.py
```

## Current Status

| Component | Status |
|-----------|--------|
| Close CRM sync | Working (3,422 companies, 11,803 contacts) |
| Lead enrichment | Working |
| ICP scoring | Working |
| Free email extraction | Working |
| Campaign sequences | In progress |
| Voice agent | Planned |

## Working Agents

| Agent | Function |
|-------|----------|
| **LeadEnricher** | Company/contact data discovery |
| **ICPScorer** | Fit scoring and tier classification |
| **ResearchAgent** | Deep company research |

*Note: 3 agents implemented. SequenceAgent, PersonalizationAgent, ResponseAgent in progress.*

## API Example

```bash
# Qualify a lead
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "qualification", "input": {"company_name": "TechCorp Inc"}}'

# Response: {"score": 85, "tier": "A", "latency_ms": 647}
```

## GTME Skills Developed

Building toward Go-To-Market Engineer through hands-on projects:

| Skill Area | What I Learned |
|------------|----------------|
| **CRM integration** | Close CRM API with bidirectional sync and deduplication |
| **Lead enrichment** | Multi-source data aggregation (Hunter, Apollo, website scraping) |
| **Cost optimization** | Free-first enrichment strategy ($0 before paid APIs) |
| **ICP scoring** | Multi-factor qualification with tier classification |
| **Pipeline architecture** | LangGraph multi-agent orchestration |
| **Sales operations** | 3,422 companies + 11,803 contacts in CRM |

## Tech Stack

Python, FastAPI, LangGraph, Supabase, Close CRM, Docker

## Data Flow

```
dealer-scraper → Supabase → sales-agent → Close CRM
                              ↓
                         Enrichment → ICP Score → Campaign
```

## Key Results

- **3,422 companies** synced to Close CRM
- **11,803 contacts** with enriched data
- **633ms** average qualification latency
- **$0.002** cost per lead
