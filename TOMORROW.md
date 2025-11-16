# Tomorrow's Action Plan - January 17, 2025

**Current Status**: Production Readiness 85% (up from 78%)
**Last Commit**: c3a83b9 - Fix package.json duplicates and config cleanup
**Branch**: main

---

## 🎯 **PRIORITY 1: Code Quality Fixes** (Est. 2 hours)

### Task 1.1: Fix Deprecated Asyncio Patterns (~30 min)
**Impact**: Python 3.13 compatibility, prevents future deprecation warnings

**Files to Update:**
1. `backend/app/api/enhanced_knowledge.py`
2. `backend/app/services/social_media_scraper.py`

**Change Required:**
```python
# BEFORE (deprecated in Python 3.10+)
loop = asyncio.get_event_loop()
return await loop.run_in_executor(self.executor, func, *args)

# AFTER (modern)
loop = asyncio.get_running_loop()
return await loop.run_in_executor(self.executor, func, *args)
```

**Verification:**
```bash
cd backend
grep -n "get_event_loop" app/api/enhanced_knowledge.py app/services/social_media_scraper.py
python -m pytest tests/ -v
```

---

### Task 1.2: Create GitHub Issues for TODOs (~1 hour)
**Impact**: Visibility, prioritization, team collaboration

**High-Priority TODOs (Create Issues):**

1. **LinkedIn OAuth Security** (8 TODOs in `backend/app/api/linkedin.py`)
   - Lines: 255, 320, 331, 401, 406, 473, 529, 625
   - Issue: `code_verifier` not persisted (PKCE flow incomplete)
   - Priority: **P1** (Security + Blocking Feature)
   - Estimate: 4 hours

2. **Cost Tracking Features** (3 TODOs)
   - `backend/app/api/costs.py:754` - Agent-specific filtering
   - `backend/app/services/cost_optimizer.py:399` - Email alerts
   - `backend/app/services/apollo.py:540` - Credit tracking
   - Priority: **P2** (Product Feature)
   - Estimate: 3 hours

3. **Feature Gaps** (Remaining TODOs)
   - STT integration placeholder
   - Chart support in exports
   - Vector database enablement
   - Priority: **P3** (Nice to Have)

**Template:**
```markdown
Title: [Component] TODO Description
Labels: technical-debt, priority-X
Assignee: (TBD)

## Context
[Line numbers and file path]

## Current State
[What exists today]

## Required Action
[What needs to be implemented]

## Acceptance Criteria
- [ ] Implementation complete
- [ ] Tests added
- [ ] Documentation updated

## Estimate
X hours
```

---

## 🎯 **PRIORITY 2: Testing & Documentation** (Est. 4 hours)

### Task 2.1: Expand Test Coverage 20% → 30% (~3 hours)
**Impact**: Production confidence, bug prevention

**Target Files (Currently Untested):**
1. `backend/app/services/hunter_service.py` - Email discovery fallback
2. `backend/app/services/crm/close.py` - CRM sync
3. `backend/app/services/crm/apollo.py` - Enrichment API
4. `backend/app/services/csv_manager.py` - CSV processing

**Testing Strategy:**
```bash
# Check current coverage
cd backend
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report

# Target: Files with 0% coverage
pytest --cov=app --cov-report=term-missing | grep "0%"

# Write tests for high-risk services first
# Priority: CRM sync (data integrity), Hunter.io (API costs)
```

---

### Task 2.2: Create CONTRIBUTING.md (~30 min)
**Impact**: Developer onboarding, workflow consistency

**Required Sections:**
```markdown
# Contributing to Sales Agent

## Development Setup
- Virtual environment setup
- Docker Compose services
- Environment variables

## Git Worktree Workflow
- Creating feature worktrees
- Testing in isolation
- Merging back to main
- Cleanup after merge

## Code Standards
- Type hints required
- FastAPI patterns
- LangGraph agent structure
- Testing requirements (pytest)

## Pull Request Process
- Branch naming
- Commit message format
- Review checklist
- CI/CD requirements
```

---

### Task 2.3: Document Config Precedence (~15 min)
**Impact**: Reduces configuration errors

**Add to README or CONTRIBUTING.md:**
```markdown
## Configuration Loading Order

1. **CLI Arguments** (highest priority)
2. **Environment Variables** (.env file)
3. **Default Values** (config.py)

Example:
```bash
# .env file
DEBUG=true
DATABASE_URL=postgresql://...

# Overrides config.py defaults
# backend/app/core/config.py:
#   DEBUG: bool = False  # Overridden by .env
```

---

## 🎯 **PRIORITY 3: Optional Enhancements** (Est. 30 min)

### Task 3.1: Update .env.example with DEBUG
```bash
# Add to .env.example
DEBUG=false  # Set to 'true' for development, 'false' for production
```

### Task 3.2: Add Cleanup Script
Create `scripts/cleanup.sh`:
```bash
#!/bin/bash
echo "Cleaning __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "Cleaning .pyc files..."
find . -type f -name "*.pyc" -delete
echo "Done!"
```

---

## 📋 **Pre-Flight Checklist**

Before starting work tomorrow:

- [ ] Pull latest changes: `git pull origin main`
- [ ] Check worktrees: `git worktree list`
- [ ] Activate venv: `source venv/bin/activate`
- [ ] Start services: `docker-compose up -d`
- [ ] Verify Redis: `redis-cli ping`
- [ ] Verify PostgreSQL: `docker-compose ps`
- [ ] Review `.claude/context.md` for latest state

---

## 📊 **Success Metrics**

**Today's Progress:**
- ✅ Production Readiness: 78% → 85% (+7%)
- ✅ Security Score: 85 → 95 (+10)
- ✅ Critical Issues: 2 → 0 (resolved)

**Tomorrow's Goals:**
- 🎯 Test Coverage: 20% → 30% (+10%)
- 🎯 Deprecated Code: 2 files → 0 files
- 🎯 GitHub Issues: 0 → 11 (TODO tracking)
- 🎯 Production Readiness: 85% → 90% (+5%)

---

## 🚀 **Quick Wins** (If Time Permits)

1. **Refactor Large Files** - Split files >800 lines when modifying
2. **Performance Testing** - Validate 633ms qualification target
3. **Security Audit** - Run `bandit -r backend/app/`
4. **Dependency Updates** - Check for outdated packages: `pip list --outdated`

---

## 📝 **Notes**

- **Email Discovery**: Already merged and working ✅
- **Hunter.io**: Integration complete, API key in .env
- **Async Bug**: Fixed and verified ✅
- **Package.json**: Duplicates removed ✅
- **DEBUG Mode**: Now defaults to False (production safe) ✅

**You're starting from a strong position. Focus on P1 tasks for maximum impact!** 💪
