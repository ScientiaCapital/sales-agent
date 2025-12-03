# Validate

Multi-phase validation: lint → types → tests.

**Usage**: `/validate`

---

## Quick Validation

```bash
cd backend && source ../venv/bin/activate
pytest tests/ -v --tb=short -x  # Stop on first failure
```

---

## Full Validation

### Phase 1: Lint
```bash
ruff check app/
```

### Phase 2: Type Check
```bash
mypy app/ --ignore-missing-imports
```

### Phase 3: Unit Tests
```bash
pytest tests/ -v --tb=short
```

### Phase 4: Integration Tests
```bash
pytest tests/integration/ -v --tb=short
```

### Phase 5: Health Check (if server running)
```bash
curl -s http://localhost:8001/api/health | python -m json.tool
```

---

## Fix on Failure

Stop at first failure, fix, then continue.

---

## Critical Rules

- **NO OpenAI** - Cerebras, Claude, DeepSeek only
- API keys from `.env` only
- Close CRM is read-only
