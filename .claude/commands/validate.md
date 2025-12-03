---
description: "Multi-phase validation (lint → types → tests)"
---

# Validation Workflow for sales-agent

Execute all phases in order. Stop on first failure and fix before proceeding.

## Phase 1: Activate Environment

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
source venv/bin/activate
```

## Phase 2: Linting (Python)

```bash
cd backend
# No ruff/flake8 configured - recommend adding ruff to requirements.txt
# For now, check for syntax errors:
python -m py_compile app/main.py
```

## Phase 3: Type Checking

```bash
cd backend
# No mypy configured - recommend adding mypy to requirements.txt
# Skip for now
echo "Type checking: Not configured (add mypy to requirements.txt)"
```

## Phase 4: Unit Tests

```bash
cd backend
source ../venv/bin/activate
pytest tests/ -v --tb=short
```

**Expected**: Tests should pass. If failures, check test output for details.

## Phase 5: Integration Tests

```bash
cd backend
pytest tests/integration/ -v --tb=short
```

## Phase 6: API Health Check (requires running server)

```bash
# Start server first: python start_server.py
curl -s http://localhost:8001/api/health | python -m json.tool
```

**Expected**: `{"status": "healthy", ...}`

---

## Quick Validation (Minimum)

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
pytest tests/ -v --tb=short -x  # Stop on first failure
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- Fix all failures before proceeding to next phase
- All API keys from `.env` only
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)
