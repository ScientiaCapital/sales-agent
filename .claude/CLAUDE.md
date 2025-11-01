# CLAUDE.md - Sales Agent Project Guide

## Project Status & Overview

**Production-ready AI sales automation platform** with 6 specialized LangGraph agents achieving sub-second lead qualification (633ms target). The system processes leads through a complete pipeline: qualification → enrichment → growth analysis → marketing → BDR workflows → voice conversations.

**Current Status**: ✅ Phase 5 Complete - Close CRM + Deduplication | ✅ Email Discovery Sub-Phase 2A Complete | 🚧 Sub-Phase 2B In Progress - Hunter.io Fallback

## Technology Stack

### Core Framework & AI
- **Python 3.13** (Requires specific version for performance optimizations)
- **LangGraph** - Multi-agent orchestration with state graphs
- **FastAPI** - High-performance API framework
- **Cerebras** - Ultra-fast inference engine
- **LCEL Chains** - For simple agent workflows

### Data & Caching
- **PostgreSQL** - Primary data store
- **Redis** - Checkpointing and caching
- **Apollo.io** - Lead enrichment data
- **LinkedIn API** - Company data enrichment

### Infrastructure
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **HTTPX** - Async HTTP client
- **Pytest** - Testing framework

## Development Workflow

### Initial Setup
```bash
# Clone and setup (assuming Python 3.13 is installed)
git clone <repository>
cd sales-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment setup
cp .env.example .env
# Edit .env with your API keys and database URLs
```

### Running the Application
```bash
# Start development server
uvicorn app.main:app --reload --port 8001

# Or use the provided script
python scripts/start_dev.py
```

### Testing the Lead Qualification Agent
```bash
# Test the 633ms lead qualification
curl -X POST http://localhost:8001/api/langgraph/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "qualification",
    "input": {
      "company_name": "TechCorp Inc",
      "industry": "SaaS", 
      "company_size": "50-200"
    }
  }'
```

## Environment Variables

Create a `.env` file with:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/sales_agent
REDIS_URL=redis://localhost:6379/0

# AI Services
OPENAI_API_KEY=your_openai_key
CEREBRAS_API_KEY=your_cerebras_key

# External APIs
APOLLO_API_KEY=your_apollo_key
LINKEDIN_CLIENT_ID=your_linkedin_id
LINKEDIN_CLIENT_SECRET=your_linkedin_secret

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8001

# Performance Tuning
CEREBRAS_ENDPOINT=your_cerebras_endpoint
MAX_CONCURRENT_REQUESTS=100
```

## Key Files & Their Purposes

### Core Architecture
```
src/
├── agents/                    # 6 specialized agents
│   ├── qualification/         # 633ms lead scoring ⚡
│   ├── enrichment/           # Apollo + LinkedIn data
│   ├── growth_analysis/      # Market opportunity research
│   ├── marketing/            # Multi-channel campaigns
│   ├── bdr_workflow/         # Human-in-loop booking
│   └── conversation/         # Voice-enabled AI chat
├── core/
│   ├── langgraph_orchestrator.py  # Multi-agent coordination
│   ├── state_manager.py      # Redis checkpointing
│   └── circuit_breaker.py    # Fault tolerance
├── api/
│   └── routes/
│       └── langgraph.py      # FastAPI endpoints
└── models/
    └── sales_models.py       # Pydantic models
```

### Configuration & Patterns
- `config/agent_factory.py` - Factory pattern for agent creation
- `config/abstract_base.py` - Abstract base classes for agents
- `langgraph/hybrid_pattern.py` - LCEL Chains + StateGraphs architecture

## Testing Approach

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific agent tests
pytest tests/agents/test_qualification.py -v

# Performance testing
pytest tests/performance/ -v --benchmark-only

# With coverage
pytest --cov=src tests/
```

### Test Structure
```python
# Example test for qualification agent
def test_qualification_agent_performance():
    """Verify sub-second response time for qualification"""
    start_time = time.time()
    result = qualification_agent.process(lead_data)
    end_time = time.time()
    
    assert (end_time - start_time) < 1.0  # < 1000ms
    assert result.score >= 0
    assert result.score <= 100
```

### Performance Testing
- **Target**: 633ms for qualification agent
- **Method**: Benchmark tests with real-world payloads
- **Monitoring**: Response time percentiles (p95, p99)

## Deployment Strategy

### Current Architecture
```bash
# No Docker currently - direct Python deployment
# Recommended production setup:

# 1. Process manager (PM2 recommended)
pm2 start ecosystem.config.js

# 2. Reverse proxy (nginx)
# Configure nginx for load balancing and SSL
```

### Production Checklist
- [ ] Configure PostgreSQL connection pooling
- [ ] Set up Redis persistence
- [ ] Enable Cerebras production endpoints
- [ ] Configure monitoring and alerting
- [ ] Set up log aggregation
- [ ] Configure rate limiting

## Coding Standards

### Agent Development Pattern
```python
class BaseSalesAgent(ABC):
    @abstractmethod
    async def process(self, input_data: SalesInput) -> SalesOutput:
        """All agents must implement this interface"""
        pass

class QualificationAgent(BaseSalesAgent):
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
    
    async def process(self, input_data: SalesInput) -> QualificationOutput:
        # Implement 633ms qualification logic
        pass
```

### Performance Requirements
- **Qualification Agent**: Must complete under 1000ms
- **All API endpoints**: Response time monitoring required
- **Database queries**: Use connection pooling
- **External API calls**: Implement circuit breakers

### Code Organization
- Use abstract base classes for all agents
- Implement factory pattern for agent creation
- All external calls must have timeout and retry logic
- State management through Redis checkpointing

## Common Tasks & Commands

### Development
```bash
# Start development server
uvicorn app.main:app --reload --port 8001

# Run specific agent locally
python -m src.agents.qualification.test_local

# Check performance metrics
python scripts/check_performance.py
```

### Testing & Quality
```bash
# Run all tests with performance checks
pytest tests/ --benchmark-skip=False

# Code formatting
black src/ tests/

# Type checking
mypy src/

# Security audit
bandit -r src/
```

### Database Operations
```bash
# Run migrations
alembic upgrade head

# Seed test data
python scripts/seed_test_data.py

# Check database performance
python scripts/db_performance.py
```

## Email Discovery System (NEW ✅)

### Automatic Contact Email Extraction - Sub-Phase 2A Complete
**Feature**: Automatically discovers contact emails when not provided, enabling enrichment of incomplete leads.

**Components**:
1. **EmailExtractor Service** (`backend/app/services/email_extractor.py`) - 185 lines
   - Multi-pattern detection (mailto links, standard format, obfuscated)
   - Smart prioritization: Personal names > Business roles > Generic
   - Spam filtering (noreply@, info@, admin@, etc.)
   - Multi-page crawling (/contact, /contact-us, /about)
   - Graceful failure handling (non-blocking)

2. **QualificationAgent Integration** (lines 487-507, 694)
   - Email extraction during qualification
   - Metadata propagation to pipeline

3. **Pipeline Orchestrator Wiring** (lines 97-102, 187)
   - Complete data flow: extraction → metadata → enrichment

**Performance**:
- Latency: +2-4 seconds per lead (non-blocking)
- Cost: $0 (web scraping, no API costs)
- Success Rate: ~80% for contractor/SMB leads
- Caching: Redis qualification cache prevents redundant scraping

**Test Coverage**:
- ✅ 185 lines of unit tests
- ✅ 139 lines of integration tests
- ✅ End-to-end pipeline verified

**Testing Commands**:
```bash
# Email extractor unit tests
pytest tests/services/test_email_extractor.py -v

# Integration tests
pytest tests/services/langgraph/test_qualification_email_integration.py -v

# End-to-end pipeline test
python test_sample_leads.py
```

**Next: Sub-Phase 2B** (Hunter.io Fallback - 5 tasks remaining)
- Task 7: Create HunterService class (~1-2 hours)
- Task 8: Add Hunter.io fallback after scraping (~1 hour)
- Task 9: Track Hunter.io API costs (~30 min)
- Task 10: Full pipeline test (~30 min)
- Task 11: Documentation and PR (~1 hour)

See `HANDOFF_EMAIL_DISCOVERY.md` for complete implementation details.

## Troubleshooting Tips

### Performance Issues
**Problem**: Qualification agent > 1000ms
```bash
# Check Cerebras endpoint latency
python scripts/check_cerebras_latency.py

# Verify Redis connection
redis-cli ping

# Check database query performance
python scripts/analyze_queries.py
```

### Agent Failures
**Problem**: Circuit breaker triggered
```bash
# Reset circuit breakers
python scripts/reset_circuit_breakers.py

# Check external API status
python scripts/check_apis.py

# View agent logs
tail -f logs/agent_errors.log
```

### Common Errors & Solutions

**Redis Connection Issues**
```python
# Check in Python console
import redis
r = redis.from_url(os.getenv('REDIS_URL'))
r.ping()  # Should return True
```

**Cerebras Timeouts**
```bash
# Increase timeout in agent config
export CEREBRAS_TIMEOUT=30
```

**Database Connection Pool**
```bash
# Check current connections
python scripts/db_connections.py
```

### Monitoring & Debugging
```bash
# Real-time performance monitoring
python scripts/monitor_performance.py

# Agent-specific debugging
export LOG_LEVEL=DEBUG

# Memory usage analysis
python scripts/memory_profiler.py
```

This guide reflects the current state of the sales-agent project. Update sections as the project evolves, particularly when Docker support is added or when new agents are implemented.