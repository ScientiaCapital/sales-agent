# Sales Agent - Claude Code Development Guidelines

## Project Overview

AI-powered sales automation platform leveraging Cerebras ultra-fast inference for real-time lead qualification and intelligent outreach.

**Current Status**: ✅ Walking Skeleton Complete - Working FastAPI backend with Cerebras integration, PostgreSQL database, and React frontend scaffolding.

## Architecture Principles

### Ultra-Fast Inference First
- **Primary**: Cerebras Inference API (~945ms latency for lead qualification)
- **Model**: llama3.1-8b via Cerebras Cloud API
- **Cost**: $0.000016 per qualification
- **Pattern**: OpenAI SDK compatible with custom base_url

### Current Working Stack
```
Backend: FastAPI + SQLAlchemy + PostgreSQL + Redis
Frontend: React 18 + TypeScript + Vite + Tailwind CSS v4
AI: Cerebras Cloud API (llama3.1-8b)
Infrastructure: Docker Compose
Testing: pytest with 96% coverage
```

### Cost-Effective AI Stack
```
Development: Claude Sonnet 4.5 (premium quality)
Research: DeepSeek v3 ($0.27/1M tokens via OpenRouter)
Production: Cerebras ($0.000016 per call)
Local: Ollama for simple queries
```

## Development Workflow

### Daily Routine
1. Start infrastructure: `docker-compose up -d`
2. Start server: `python start_server.py`
3. Run tests: `python test_api.py`
4. Implement features following existing patterns
5. Update Task Master if using project management

### Feature Development
1. **Plan** - Review roadmap in README.md
2. **Research** - Use DeepSeek for cost-effective research if needed
3. **Implement** - Follow existing FastAPI patterns in `backend/app/`
4. **Test** - Add tests in `backend/tests/`
5. **Document** - Update README and tasks

## Technical Stack

### Core Dependencies
- **FastAPI 0.115.0** - REST API framework
- **SQLAlchemy** - ORM for PostgreSQL
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **OpenAI SDK** - Cerebras integration (via custom base_url)
- **psycopg3** - PostgreSQL adapter
- **Python 3.13.7** - Runtime
- **Docker** - Infrastructure orchestration

### Cerebras Integration

The Cerebras service is already implemented in `backend/app/services/cerebras.py`:

```python
from openai import OpenAI
import os

# Cerebras uses OpenAI SDK with custom base_url
client = OpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

# Ultra-fast inference call
response = client.chat.completions.create(
    model="llama3.1-8b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=500,
    temperature=0.7
)
```

## Code Organization

### Current Directory Structure
```
sales-agent/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI endpoints
│   │   │   ├── health.py     # Health checks
│   │   │   └── leads.py      # Lead management
│   │   ├── core/             # Configuration
│   │   │   └── config.py     # Settings
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── database.py   # DB setup
│   │   │   ├── lead.py       # Lead model
│   │   │   └── api_call.py   # API call tracking
│   │   ├── schemas/          # Pydantic schemas
│   │   │   └── lead.py       # Lead validation
│   │   └── services/         # Business logic
│   │       └── cerebras.py   # Cerebras integration
│   ├── alembic/              # Database migrations
│   ├── tests/                # Test suite
│   └── requirements.txt
├── frontend/                 # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/       # React components
│   │   └── pages/           # Page components
│   └── package.json
├── .taskmaster/             # Task management
├── .claude/                 # Claude Code config
├── .env                     # API keys (DO NOT COMMIT)
├── docker-compose.yml       # PostgreSQL + Redis
├── start_server.py          # Server launcher
├── test_api.py             # Integration tests
└── README.md
```

### API Endpoints

Current working endpoints:

```
GET  /                      # Root endpoint
GET  /api/health           # Health check with service status
POST /api/leads/qualify    # Qualify a lead with Cerebras
GET  /api/leads/           # List all leads
GET  /api/docs             # OpenAPI documentation
```

## MCP Server Usage

### Task Master AI
```bash
# Project management with AI assistance
task-master list
task-master next
task-master show <id>
task-master set-status --id=<id> --status=done
```

### Serena (Code Intelligence)
```bash
# Use for codebase navigation
# Automatically invoked by Claude Code
# Focus on symbolic tools for Python modules
```

### Sequential Thinking
```bash
# Use for complex problem solving
# Break down multi-step implementations
```

### Memory MCP
```bash
# Save project knowledge
# Store architectural decisions
```

### Shrimp Task Manager
```bash
# Detailed planning and verification
# Track multi-phase features
```

## Coding Standards

### Python (FastAPI Backend)
```python
# Follow existing patterns in backend/app/
# Use type hints
# Document with docstrings
# Keep functions focused and testable

from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadResponse
from app.services.cerebras import CerebrasService

@router.post("/leads/qualify", response_model=LeadResponse, status_code=201)
async def qualify_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db)
) -> LeadResponse:
    """
    Qualify a lead using Cerebras AI inference.

    Args:
        lead: Lead data for qualification
        db: Database session

    Returns:
        Lead with qualification score and reasoning
    """
    # Implementation following existing pattern
```

### Error Handling
```python
# Always handle API errors gracefully
from fastapi import HTTPException

try:
    response = cerebras_service.qualify_lead(lead_data)
except Exception as e:
    logger.error(f"Cerebras API error: {e}")
    raise HTTPException(status_code=500, detail="Lead qualification failed")
```

### Database Operations
```python
# Use SQLAlchemy ORM
from app.models.lead import Lead

# Create
db_lead = Lead(**lead_data)
db.add(db_lead)
db.commit()
db.refresh(db_lead)

# Query
leads = db.query(Lead).filter(Lead.status == "qualified").all()

# Update
db_lead.qualification_score = new_score
db.commit()
```

## Testing Strategy

### Current Tests
```bash
# Run all tests
cd backend
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

### Test Structure
```python
# backend/tests/test_health.py - Health endpoint tests
# backend/tests/test_leads.py - Lead management tests (to be added)
# Use TestClient from fastapi.testclient
# Mock Cerebras API calls for unit tests
```

## Environment Variables

Required in `.env` (already configured):
```bash
# Cerebras (primary)
CEREBRAS_API_KEY=csk-...
CEREBRAS_API_BASE=https://api.cerebras.ai/v1

# DeepSeek (research) - NEVER hardcode!
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-...

# Database (Docker)
DATABASE_URL=postgresql+psycopg://sales_agent:dev_password_change_in_production@localhost:5433/sales_agent_db
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=dev_password_change_in_production
POSTGRES_DB=sales_agent_db

# Redis (Docker)
REDIS_URL=redis://localhost:6379/0

# Optional
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## Database Schema

### Current Tables

**leads**
- id (Integer, primary key)
- company_name (String)
- company_website (String, nullable)
- company_size (String, nullable)
- industry (String, nullable)
- contact_name (String, nullable)
- contact_email (String, nullable)
- contact_title (String, nullable)
- notes (Text, nullable)
- qualification_score (Float, nullable)
- qualification_reasoning (Text, nullable)
- qualification_latency_ms (Integer, nullable)
- status (String, default="pending")
- created_at (DateTime)
- updated_at (DateTime)

**cerebras_api_calls**
- id (Integer, primary key)
- lead_id (Integer, foreign key)
- model (String)
- prompt_tokens (Integer)
- completion_tokens (Integer)
- total_tokens (Integer)
- latency_ms (Integer)
- cost (Float)
- created_at (DateTime)

## Performance Requirements

Current metrics:
- **Cerebras latency**: ~945ms per lead qualification
- **Cost**: $0.000016 per qualification
- **Database**: <50ms query time
- **API response**: <1000ms total (including Cerebras call)

## Best Practices

### DO
✅ Follow existing FastAPI patterns
✅ Use type hints everywhere
✅ Write tests for new endpoints
✅ Log all API calls and errors
✅ Use environment variables for config
✅ Update database via Alembic migrations
✅ Cache repeated queries in Redis
✅ Use DeepSeek for research (cost-effective)

### DON'T
❌ Hardcode API keys anywhere
❌ Skip database migrations
❌ Commit `.env` files
❌ Modify models without migrations
❌ Skip error handling
❌ Use expensive models for simple queries
❌ Bypass the ORM with raw SQL

## Debugging

### Backend Issues
```bash
# Check server logs
python start_server.py
# Look for startup errors

# Test database connection
docker-compose ps
# Verify PostgreSQL is running

# Test Cerebras API
python backend/tests/test_cerebras.py
```

### Database Issues
```bash
# Check migrations
cd backend
alembic current
alembic history

# Reset database (DANGER)
alembic downgrade base
alembic upgrade head
```

### Frontend Issues
```bash
cd frontend
npm run dev
# Check console for errors
```

## Development Roadmap

### Phase 1: Core Foundation (In Progress)
- [x] Lead qualification engine with Cerebras AI
- [ ] Multi-agent search and report generation
- [ ] Document analysis with gist memory
- [ ] Real-time conversation intelligence

### Phase 2: Advanced Capabilities
- [ ] Automated outreach campaigns
- [ ] CRM integration
- [ ] Performance analytics and dashboards

## Quick Reference

### Start Development
```bash
# Start infrastructure
docker-compose up -d

# Start backend
python start_server.py

# Start frontend (separate terminal)
cd frontend && npm run dev

# Run tests
python test_api.py
```

### Common Commands
```bash
# Database migrations
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head

# Install dependencies
cd backend && pip install -r requirements.txt
cd frontend && npm install

# Run tests
cd backend && pytest -v
```

### API Testing
```bash
# Health check
curl http://localhost:8001/api/health

# Qualify lead
curl -X POST http://localhost:8001/api/leads/qualify \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Test Corp", "industry": "SaaS"}'

# List leads
curl http://localhost:8001/api/leads/
```

## Resources

- **API Docs**: http://localhost:8001/api/docs (when running)
- **Cerebras Docs**: https://inference-docs.cerebras.ai
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org
- **Task Master Guide**: .taskmaster/CLAUDE.md

---

**Remember**: This is a working sales agent system with a complete FastAPI backend, PostgreSQL database, and Cerebras integration. Every new feature should follow existing patterns and maintain the <1s response time target.

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines from the main CLAUDE.md file.**
@.taskmaster/CLAUDE.md
