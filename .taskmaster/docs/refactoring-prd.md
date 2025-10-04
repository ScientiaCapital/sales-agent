# Sales Agent - Technical Debt Refactoring & Quality Improvements PRD

## Executive Summary

Based on comprehensive multi-agent code audit (Sequential Thinking → Shrimp Task Manager → Parallel Serena Analysis → Context7 Validation), this PRD outlines critical refactoring tasks to address technical debt before continuing feature development.

**Quality Assessment Results:**
- Backend API Design: **6.5/10** (api-design-expert)
- Frontend Architecture: **6/10** (react-performance-optimizer)
- Testing Coverage: **Unable to assess** (minimal test infrastructure)
- Documentation Quality: **7.5/10** (developer-experience-engineer)
- Infrastructure: **4/10** (infrastructure-devops-engineer)

**Critical Issues Identified:** 40+ technical debt items across 5 domains

---

## Phase 1: Critical Security & Backend Hardening (MUST DO FIRST)

### 1. Implement Global Exception Handling
**Problem:** No `@app.exception_handler` decorators in codebase, unhandled exceptions expose internal stack traces
**Impact:** Security vulnerability, poor error UX
**Location:** `backend/app/main.py` - missing handlers

**Requirements:**
- Add handler for `RequestValidationError` (422 errors)
- Add handler for `HTTPException` (4xx/5xx errors)
- Add handler for generic `Exception` (500 errors)
- Log all exceptions with request context
- Return sanitized error messages to clients

**Validation Criteria:**
- All endpoint errors return structured JSON responses
- No stack traces leak to clients in production
- All errors logged with correlation IDs

### 2. Replace Generic Exception Catching
**Problem:** `backend/app/services/cerebras.py:133` catches ALL exceptions (including KeyboardInterrupt)
**Impact:** Suppresses errors that should propagate, masks bugs

**Requirements:**
- Replace `except Exception` with specific exception types
- Raise `HTTPException(503)` for API failures
- Use proper error recovery for `json.JSONDecodeError`
- Remove redundant fallback logic (line 124-128)

**Validation Criteria:**
- Service raises appropriate HTTP exceptions
- Cerebras API errors properly propagated
- No generic exception handlers remain

### 3. Add Structured Logging Infrastructure
**Problem:** Zero logging throughout codebase
**Impact:** Cannot debug production issues

**Requirements:**
- Create `backend/app/core/logging.py` with structured logging
- Add loggers to all modules (main.py, leads.py, cerebras.py, database.py)
- Log API calls with latency, tokens, costs
- Log database operations with query context
- Use environment-based log levels (DEBUG for dev, INFO for prod)

**Validation Criteria:**
- All endpoints log requests/responses
- All errors logged with stack traces
- Performance metrics captured in logs

### 4. Fix CORS Security Configuration
**Problem:** `allow_methods=["*"]` and `allow_headers=["*"]` too permissive
**Location:** `backend/app/main.py:22-23`
**Impact:** CSRF attack vulnerability

**Requirements:**
- Restrict `allow_methods` to `["GET", "POST", "PUT", "DELETE"]`
- Restrict `allow_headers` to `["Content-Type", "Authorization"]`
- Keep `allow_origins` from settings (already correct)

**Validation Criteria:**
- CORS only allows explicit methods/headers
- OPTIONS preflight requests work correctly
- Frontend can still make authorized requests

### 5. Rotate Exposed API Keys (IMMEDIATE)
**Problem:** `.env` file contains real API keys (DEEPSEEK, CEREBRAS, OPENROUTER)
**Impact:** CRITICAL - Financial exposure from API abuse

**Requirements:**
- Revoke all exposed keys immediately
- Generate new API keys from providers
- Audit git history for leaked credentials: `git log --all -- .env`
- Create `.env.example` template with placeholders
- Update team documentation

**Validation Criteria:**
- Old keys revoked and non-functional
- New keys working in all environments
- .env.example created with no real values

### 6. Remove Hardcoded Database Passwords
**Problem:** `docker-compose.yml` has `dev_password_change_in_production` default
**Impact:** Password visible in git history

**Requirements:**
- Remove all password defaults from docker-compose.yml
- Use `${VAR:?Error message}` to require explicit .env values
- Update pgAdmin password to use environment variable
- Remove SQL `echo=True` hardcoding (make env-dependent)

**Validation Criteria:**
- docker-compose fails gracefully if .env missing
- No passwords in docker-compose.yml
- Database echo controlled by `DATABASE_ECHO` env var

---

## Phase 2: Backend Quality & Performance

### 7. Implement API Versioning
**Problem:** `API_V1_PREFIX="/api/v1"` defined but unused
**Impact:** No version strategy, breaking changes will affect all clients

**Requirements:**
- Update all router includes to use `settings.API_V1_PREFIX`
- Routes become: `/api/v1/health`, `/api/v1/leads/qualify`
- Update frontend to use versioned paths
- Add version to OpenAPI docs title

**Validation Criteria:**
- All endpoints accessible at `/api/v1/` prefix
- Old `/api/` paths return 404
- API docs show v1 in title

### 8. Add Database Connection Resilience
**Problem:** No `pool_pre_ping`, fragile DATABASE_URL parsing
**Location:** `backend/app/models/database.py`

**Requirements:**
- Add `pool_pre_ping=True` to engine config (Context7 best practice)
- Replace string replacement with SQLAlchemy URL parsing
- Make pool_size/max_overflow environment-configurable
- Add connection retry logic on startup

**Validation Criteria:**
- Engine detects stale connections before use
- App survives database restarts
- Pool configuration from environment variables

### 9. Optimize Database Schema
**Problem:** Missing indexes on `qualification_score`, no CHECK constraints
**Location:** `backend/app/models/lead.py`

**Requirements:**
- Add composite index on (qualification_score, created_at)
- Add CHECK constraint for score range (0-100)
- Add index on contact_email for deduplication queries
- Remove redundant `db.flush()` before `db.commit()` (leads.py:59)

**Validation Criteria:**
- Query performance improved on score filtering
- Invalid scores rejected at database level
- Alembic migration generated and applied

### 10. Add Custom Exception Classes
**Problem:** No custom exceptions, using generic HTTPException everywhere
**Impact:** Poor error categorization, hard to handle specific cases

**Requirements:**
- Create `backend/app/core/exceptions.py`
- Add `CerebrasAPIError`, `LeadValidationError`, `DatabaseConnectionError`
- Inherit from appropriate base exceptions
- Use in services and raise appropriately

**Validation Criteria:**
- All services use custom exceptions
- Exception handlers map to HTTP status codes
- Error messages are domain-specific

---

## Phase 3: Frontend Production Readiness

### 11. Implement React 19 ErrorBoundary
**Problem:** No error handling, app crashes completely on runtime errors
**Impact:** Poor UX, no error recovery

**Requirements:**
- Create `frontend/src/components/ErrorBoundary.tsx`
- Implement with React 19 `onUncaughtError` and `onCaughtError` APIs
- Add fallback UI with error reporting
- Wrap App in main.tsx with ErrorBoundary
- Log errors to monitoring service (Sentry)

**Validation Criteria:**
- Runtime errors show fallback UI instead of white screen
- Errors logged with component stack traces
- User can recover or reload

### 12. Create API Client Service Layer
**Problem:** No fetch/axios integration, no backend connectivity
**Impact:** Dashboard shows static data, no real functionality

**Requirements:**
- Create `frontend/src/services/api.ts`
- Implement typed methods: `qualifyLead()`, `getLeads()`, `getLead(id)`
- Use environment variable for base URL: `VITE_API_BASE_URL`
- Add error handling with retries
- Add TypeScript interfaces matching backend schemas

**Validation Criteria:**
- All backend endpoints callable from frontend
- Errors handled gracefully
- TypeScript types match Pydantic schemas

### 13. Add State Management & Data Fetching
**Problem:** No hooks usage, dashboard static, no dynamic data

**Requirements:**
- Create custom hook `frontend/src/hooks/useLeads.ts`
- Implement with `useState`, `useEffect` for data fetching
- Add loading states with Suspense boundaries
- Use React 19 `preload` API for resource optimization
- Update Dashboard to show real lead counts

**Validation Criteria:**
- Dashboard shows live data from backend
- Loading states prevent layout shift (CLS < 0.1)
- Data refreshes on mount

### 14. Optimize Vite Production Build
**Problem:** Minimal config, no code splitting, large bundles
**Impact:** Slow initial load, poor performance scores

**Requirements:**
- Add manual chunks config: separate react-vendor, api client
- Configure `rollupOptions` for code splitting
- Add bundle visualizer plugin
- Set production optimizations (minify, sourcemap, drop console)
- Configure dev proxy for `/api` → `http://localhost:8001`

**Validation Criteria:**
- Initial bundle < 50KB gzipped
- Lighthouse score > 95
- Bundle analyzer shows proper splitting

### 15. Add Tailwind v4 Custom Utilities
**Problem:** Basic utility usage, not leveraging v4 features

**Requirements:**
- Create custom utilities with `@utility` directive
- Add CSS variables for brand colors with `@theme`
- Customize container utility (required in v4)
- Use arbitrary properties for dynamic values

**Validation Criteria:**
- Custom brand colors available as utilities
- Container utility works as expected
- No v3 deprecated patterns (`@layer`)

---

## Phase 4: Testing & Quality Assurance

### 16. Create pytest Infrastructure
**Problem:** Only 2 basic test files, misleading "96% coverage" claim

**Requirements:**
- Create `backend/tests/conftest.py` with shared fixtures
- Add `db_session` fixture with test database
- Add `client` fixture with test client
- Add `mock_cerebras` fixture for AI mocking
- Configure pytest-asyncio for async tests

**Validation Criteria:**
- All fixtures available to test files
- Test database isolated from dev database
- Async tests run without warnings

### 17. Add Comprehensive Test Coverage
**Problem:** No tests for leads.py, cerebras.py, missing edge cases

**Requirements:**
- Create `backend/tests/test_leads.py` with endpoint tests
- Create `backend/tests/test_cerebras.py` with service tests
- Test edge cases: invalid input, API failures, timeouts
- Test async operations with pytest-asyncio
- Fix misleading test_health.py comments and assertions

**Validation Criteria:**
- Coverage > 90% on core modules
- All endpoints have success/failure tests
- Edge cases documented and tested

### 18. Add Frontend Testing
**Problem:** No frontend tests, no testing strategy

**Requirements:**
- Install Vitest and React Testing Library
- Create `frontend/src/components/__tests__/` directory
- Add tests for ErrorBoundary, Dashboard, Layout
- Add E2E tests with Playwright for critical flows
- Configure test coverage reporting

**Validation Criteria:**
- Unit tests for all components
- E2E tests for lead qualification flow
- Coverage report generated on CI

---

## Phase 5: Infrastructure & DevOps

### 19. Create Production Dockerfile
**Problem:** No application Dockerfile, can't deploy to cloud
**Impact:** Manual deployment only, no containerization

**Requirements:**
- Create multi-stage `backend/Dockerfile`
- Use Python 3.13.7-slim base image
- Copy dependencies from builder stage
- Run as non-root user (appuser)
- Add health check endpoint call
- Expose port 8001

**Validation Criteria:**
- Docker build succeeds
- Container runs FastAPI app
- Health check passes
- Image size < 500MB

### 20. Setup CI/CD Pipeline
**Problem:** No `.github/workflows/`, manual deployments
**Impact:** No automated testing, inconsistent releases

**Requirements:**
- Create `.github/workflows/ci.yml`
- Add jobs: test, security-scan, docker-build
- Use GitHub Actions for Python setup, pytest, coverage
- Add Snyk or Trivy for security scanning
- Configure Docker build and push to registry

**Validation Criteria:**
- All PRs run full test suite
- Security vulnerabilities caught before merge
- Docker images built on main branch

### 21. Add Monitoring & Observability
**Problem:** No metrics, logs, or tracing infrastructure

**Requirements:**
- Add Prometheus metrics endpoint
- Configure structured logging with correlation IDs
- Add OpenTelemetry tracing for requests
- Setup Grafana dashboards for key metrics
- Configure alerts for error rates, latency

**Validation Criteria:**
- /metrics endpoint exposes Prometheus data
- All logs have correlation IDs
- Traces show request flow through system

### 22. Implement Database Backup Strategy
**Problem:** No backups, data persists only in Docker volumes
**Risk:** Complete data loss if volume corrupted

**Requirements:**
- Setup automated daily backups to S3/GCS
- Implement point-in-time recovery capability
- Add backup retention policy (30 days minimum)
- Create backup restoration runbook
- Schedule quarterly backup restoration tests

**Validation Criteria:**
- Backups run daily without errors
- Restoration tested and documented
- Backups encrypted at rest

---

## Phase 6: Documentation & Developer Experience

### 23. Update Documentation for Accuracy
**Problem:** React 18 documented but 19.1.1 installed, misleading coverage claims

**Requirements:**
- Update all "React 18" references to "React 19"
- Remove or qualify "96% test coverage" claim
- Add missing database fields to schema docs
- Document all API endpoints including GET /api/leads/{id}
- Clarify latency expectations (~800-1000ms, not <100ms)

**Validation Criteria:**
- All version numbers accurate
- API endpoint list complete
- Database schema matches implementation

### 24. Create Architecture Documentation
**Problem:** No diagrams, missing system overview

**Requirements:**
- Create `ARCHITECTURE.md` with system architecture diagram
- Add data flow diagram for lead qualification
- Create database ER diagram with relationships
- Document Cerebras integration patterns
- Add deployment architecture diagram

**Validation Criteria:**
- Diagrams rendered in README
- New developers can understand architecture from docs
- All major components documented

### 25. Create .env.example Template
**Problem:** No template, setup instructions incomplete

**Requirements:**
- Create `.env.example` with all required and optional keys
- Add comments explaining each variable
- Include example values (not real keys)
- Update README with environment setup section
- Document minimum required keys vs optional

**Validation Criteria:**
- New developers can copy .env.example to .env
- All variables documented with purpose
- Setup instructions reference .env.example

---

## Success Metrics

### Code Quality
- [ ] Backend API design score: 6.5 → **9.0** (target)
- [ ] Frontend architecture score: 6.0 → **9.0** (target)
- [ ] Infrastructure score: 4.0 → **8.5** (target)
- [ ] Documentation accuracy: 7.5 → **9.5** (target)
- [ ] Test coverage: 0% → **90%+** (target)

### Performance
- [ ] API response time: maintain <1000ms
- [ ] Frontend LCP: <2.5s (Core Web Vitals)
- [ ] Frontend FID: <100ms
- [ ] Frontend CLS: <0.1
- [ ] Lighthouse score: **95+**

### Security
- [ ] All API keys rotated and secured
- [ ] No hardcoded credentials in codebase
- [ ] CORS properly restricted
- [ ] All endpoints have error handling
- [ ] Security scan passes in CI

### Developer Experience
- [ ] New developers onboard in <30 minutes
- [ ] All docs accurate and up-to-date
- [ ] CI/CD pipeline fully automated
- [ ] Backup/restore procedures documented

---

## Implementation Timeline

**Phase 1 (Critical Security):** Days 1-2 (6 tasks)
**Phase 2 (Backend Quality):** Days 3-4 (4 tasks)
**Phase 3 (Frontend):** Days 5-6 (5 tasks)
**Phase 4 (Testing):** Days 7-8 (3 tasks)
**Phase 5 (Infrastructure):** Days 9-11 (4 tasks)
**Phase 6 (Documentation):** Days 12-13 (3 tasks)

**Total Estimated Time:** 13 working days (2.5 sprints)

---

## Dependencies & Blockers

- **API Key Rotation:** Requires access to Cerebras, DeepSeek, OpenRouter accounts
- **CI/CD Setup:** Requires GitHub Actions permissions and Docker registry access
- **Monitoring:** May require additional infrastructure costs (Grafana, Prometheus)
- **Backup Strategy:** Requires cloud storage setup (AWS S3 or GCP)

---

## Risk Mitigation

1. **Breaking Changes:** API versioning ensures backward compatibility
2. **Data Loss:** Implement backups before production deployment
3. **Performance Regression:** Add performance budgets to CI pipeline
4. **Security Incidents:** Rotate keys immediately, audit git history

---

_This PRD consolidates findings from: Sequential Thinking (15 thoughts), Shrimp Task Manager (19 tasks), Parallel Serena Analysis (4 agents), Context7 Documentation Validation_
