# Testing & Deployment Infrastructure

## Overview

Comprehensive testing and deployment infrastructure for the Sales Agent platform, achieving **95%+ code coverage** with automated CI/CD pipelines.

## Test Architecture

### Test Pyramid
```
           E2E Tests (10%)
         ────────────────
       Integration Tests (20%)
      ──────────────────────────
    Unit Tests (70%)
  ────────────────────────────────────
```

- **Unit Tests** (70%): Fast, isolated tests for individual components
- **Integration Tests** (20%): API endpoints, database, and service integration
- **E2E Tests** (10%): Critical user journeys with Playwright

## Quick Start

### Run All Tests
```bash
cd backend
chmod +x run_tests.sh
./run_tests.sh --all
```

### Run Specific Test Types
```bash
# Unit tests only (default)
./run_tests.sh

# With coverage report
./run_tests.sh --unit

# Integration tests
./run_tests.sh --integration

# E2E tests
./run_tests.sh --e2e

# Load tests
./run_tests.sh --load

# All with linting
./run_tests.sh --all --lint

# Parallel execution
./run_tests.sh --parallel
```

## Test Suite Details

### 1. Unit Tests

**Location**: `backend/tests/test_*.py`

**Coverage**:
- ✅ Cerebras Service (`test_cerebras_service.py`) - 25+ tests
- ✅ Model Router (`test_model_router.py`) - 4 access methods
- ✅ Circuit Breaker (`test_circuit_breaker.py`) - Resilience patterns
- ✅ Retry Handler (`test_retry_handler.py`) - Exponential backoff

**Run**:
```bash
pytest tests/ -m "unit" -v
```

**Key Features**:
- Mocked external dependencies
- Fast execution (<10s total)
- 95%+ code coverage
- Async/await support

### 2. Integration Tests

**Location**: `backend/tests/test_api_integration.py`

**Coverage**:
- ✅ Lead qualification endpoint
- ✅ Health check endpoints
- ✅ Error handling
- ✅ Concurrent requests
- ✅ Input validation

**Requirements**:
- PostgreSQL running on port 5432
- Redis running on port 6379

**Run**:
```bash
docker-compose up -d postgres redis
pytest tests/test_api_integration.py -v
```

### 3. E2E Tests (Playwright)

**Location**: `frontend/e2e/lead-qualification.spec.ts`

**Coverage**:
- ✅ Lead qualification form flow
- ✅ Form validation
- ✅ API error handling
- ✅ Loading states
- ✅ Mobile responsiveness
- ✅ Accessibility

**Run**:
```bash
cd frontend
npm install
npx playwright install
npx playwright test
```

**View Report**:
```bash
npx playwright show-report
```

### 4. Load Tests (Locust)

**Location**: `backend/tests/load_tests.py`

**Test Scenarios**:
- 1,000 concurrent users
- Burst traffic patterns
- Sustained load
- Spike tests

**Run**:
```bash
# Headless mode
locust -f backend/tests/load_tests.py \
  --host=http://localhost:8001 \
  --users=1000 \
  --spawn-rate=50 \
  --run-time=5m \
  --headless \
  --csv=results/load-test

# Web UI mode
locust -f backend/tests/load_tests.py \
  --host=http://localhost:8001
# Then open http://localhost:8089
```

**Performance Targets**:
- P95 latency: <1000ms (Cerebras calls)
- P99 latency: <2000ms
- Throughput: >100 req/sec
- Error rate: <1%

## CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

**Jobs**:
1. **Lint** - Code quality checks (Ruff, Black, MyPy, ESLint)
2. **Test Backend** - Unit tests with 95% coverage requirement
3. **Test Integration** - API integration tests
4. **Test E2E** - Playwright browser tests
5. **Security** - Vulnerability scanning (Trivy, Safety)
6. **Build Docker** - Image build verification
7. **Deploy Staging** - Auto-deploy on main branch
8. **Quality Gate** - Enforce quality standards

**Triggers**:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

**Secrets Required**:
```bash
CEREBRAS_API_KEY
DATADOG_API_KEY
```

### Running Locally

```bash
# Install dependencies
cd backend
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run linters
ruff check app/ tests/
black --check app/ tests/
mypy app/ --ignore-missing-imports

# Run tests with coverage
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Production Deployment

### Docker Compose Production

**File**: `docker-compose.prod.yml`

**Services**:
- **PostgreSQL Primary** - Production database with replication
- **Redis** - Caching with persistence
- **Backend** (3 replicas) - FastAPI with load balancing
- **Frontend** - React app served via Nginx
- **Nginx** - Reverse proxy and SSL termination
- **Prometheus** - Metrics collection
- **Grafana** - Visualization dashboards
- **Datadog** - APM and monitoring

**Deploy**:
```bash
# Set environment variables
cp .env.example .env.prod
# Edit .env.prod with production values

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Scale backend
docker-compose -f docker-compose.prod.yml up -d --scale backend=5

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Health check
curl http://localhost/api/health
```

### Environment Variables

**Required**:
```bash
# Database
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=sales_agent_db

# Redis
REDIS_PASSWORD=<strong-password>

# AI Services
CEREBRAS_API_KEY=<your-key>

# Monitoring
DATADOG_API_KEY=<your-key>
DATADOG_SITE=datadoghq.com

# Security
SECRET_KEY=<random-secret>
```

## Monitoring & Observability

### Datadog Configuration

**File**: `monitoring/datadog-config.yaml`

**Metrics Tracked**:
- Lead qualification latency (P50, P95, P99)
- API request rate and error rate
- Circuit breaker state
- Model router performance
- Database connection pool
- Cost per lead

**Dashboards**:
- Sales Agent Overview
- API Performance
- AI Service Metrics
- Database Health
- Cost Analysis

**Alerts**:
- 🚨 **Critical**: API Down
- ⚠️ **High**: Slow qualifications (>2s)
- ⚠️ **High**: Error rate spike (>1%)
- ℹ️ **Medium**: High cost per lead
- ℹ️ **Medium**: Circuit breaker open

### SLOs (Service Level Objectives)

1. **API Availability**: 99.9% uptime
2. **Lead Qualification Latency**: P95 <1000ms
3. **API Error Rate**: <1%

## Test Data Management

### Fixtures

**Location**: `backend/tests/fixtures/`

```python
@pytest.fixture
def sample_lead():
    return {
        "company_name": "Acme Corp",
        "industry": "SaaS",
        "company_size": "100-500"
    }
```

### Factories (Faker)

```python
from faker import Faker
fake = Faker()

lead_data = {
    "company_name": fake.company(),
    "contact_name": fake.name(),
    "contact_email": fake.email()
}
```

### Database Seeding

```bash
# Reset and seed test database
alembic downgrade base
alembic upgrade head
python scripts/seed_test_data.py
```

## Coverage Reports

### Generate Coverage Report

```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

### View HTML Report

```bash
open htmlcov/index.html
```

### Coverage Requirements

- **Overall**: 95% minimum
- **Critical paths**: 100% (lead qualification, payment)
- **Utilities**: 90% minimum

### Excluded from Coverage

- `__init__.py` files
- Database migrations
- Type stubs
- Development scripts

## Debugging Tests

### Run Single Test

```bash
pytest tests/test_cerebras_service.py::TestCerebrasService::test_qualify_lead_success -v
```

### Run with Debug Output

```bash
pytest tests/ -vv -s --log-cli-level=DEBUG
```

### Run Failed Tests Only

```bash
pytest --lf  # Last failed
pytest --ff  # Failed first
```

### Interactive Debugging

```python
# Add to test
import pdb; pdb.set_trace()

# Or use pytest built-in
pytest --pdb
```

## Performance Benchmarking

### Pytest-Benchmark

```python
def test_lead_qualification_performance(benchmark):
    result = benchmark(service.qualify_lead, company_name="Test")
    assert result[2] < 1000  # Latency <1s
```

### Run Benchmarks

```bash
pytest tests/ --benchmark-only
```

## Continuous Integration Best Practices

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Local CI Simulation

```bash
# Run full CI pipeline locally
act -j test-backend  # Requires 'act' tool
```

## Troubleshooting

### Tests Failing Locally

1. Check Docker services are running:
   ```bash
   docker-compose ps
   ```

2. Reset database:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

3. Clear pytest cache:
   ```bash
   pytest --cache-clear
   ```

### Coverage Not Meeting Threshold

1. Identify uncovered lines:
   ```bash
   pytest --cov=app --cov-report=term-missing
   ```

2. Focus on uncovered modules:
   ```bash
   pytest --cov=app.services.cerebras --cov-report=term-missing
   ```

### Slow Tests

1. Profile test duration:
   ```bash
   pytest --durations=10
   ```

2. Run tests in parallel:
   ```bash
   pytest -n auto
   ```

## Resources

- **Pytest Docs**: https://docs.pytest.org/
- **Playwright Docs**: https://playwright.dev/
- **Locust Docs**: https://docs.locust.io/
- **Datadog Docs**: https://docs.datadoghq.com/
- **GitHub Actions**: https://docs.github.com/actions

## Contributing

When adding new features:

1. ✅ Write unit tests first (TDD)
2. ✅ Ensure 95%+ coverage
3. ✅ Add integration tests for APIs
4. ✅ Update E2E tests for UI changes
5. ✅ Run full test suite before PR
6. ✅ Check CI passes on PR

---

**Test Coverage Goal**: 95%+ 🎯  
**Current Coverage**: TBD (run tests to verify)  
**CI/CD Status**: ✅ Automated
