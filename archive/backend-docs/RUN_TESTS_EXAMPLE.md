# How to Run TDD Tests - Close Bulk Push Service

## Current Status: RED Phase (Tests WILL FAIL)

The module `app.services.crm.close_bulk_push` does not exist yet, so all imports will fail.
This is **expected behavior** in the RED phase of TDD.

## Test Execution Commands

### Verify RED Phase (Module Doesn't Exist)

```bash
# This should fail with ModuleNotFoundError
python3 -c "from app.services.crm.close_bulk_push import CloseBulkPushService"

# Expected output:
# ModuleNotFoundError: No module named 'app.services.crm.close_bulk_push'
```

### Run All Tests (will fail in RED phase)

```bash
# From backend directory
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend

# Run all tests in the file
pytest tests/services/crm/test_close_bulk_push.py -v

# Expected output in RED phase:
# ImportError: cannot import name 'CloseBulkPushService' from 'app.services.crm.close_bulk_push'
```

### Run Individual Tests

```bash
# Test dry-run functionality
pytest tests/services/crm/test_close_bulk_push.py::test_push_leads_respects_dry_run -v

# Test ATL filtering
pytest tests/services/crm/test_close_bulk_push.py::test_push_leads_filters_atl_contacts_only -v

# Test duplicate handling
pytest tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_duplicates -v
```

### Run Tests by Category (using -k filter)

```bash
# Run all dry-run tests
pytest tests/services/crm/test_close_bulk_push.py -k "dry_run" -v

# Run all ATL filtering tests
pytest tests/services/crm/test_close_bulk_push.py -k "atl" -v

# Run all error handling tests
pytest tests/services/crm/test_close_bulk_push.py -k "error" -v
```

### After Implementation (GREEN Phase)

Once you implement `app/services/crm/close_bulk_push.py`, run:

```bash
# Run all tests with verbose output
pytest tests/services/crm/test_close_bulk_push.py -v --tb=short

# Run with coverage report
pytest tests/services/crm/test_close_bulk_push.py --cov=app.services.crm.close_bulk_push --cov-report=term-missing

# Run with detailed output for debugging
pytest tests/services/crm/test_close_bulk_push.py -vv --tb=long
```

## Expected Test Output in GREEN Phase

```
tests/services/crm/test_close_bulk_push.py::test_push_leads_creates_lead_with_contacts PASSED              [  5%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_includes_all_contacts_when_atl_only_false PASSED [ 11%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_respects_dry_run PASSED                     [ 16%]
tests/services/crm/test_close_bulk_push.py::test_dry_run_validates_data_format PASSED                   [ 22%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_duplicates PASSED                   [ 27%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_adds_contacts_to_existing_when_update_mode PASSED [ 33%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_filters_atl_contacts_only PASSED            [ 38%]
tests/services/crm/test_close_bulk_push.py::test_atl_filtering_handles_missing_is_atl_flag PASSED       [ 44%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_api_errors_gracefully PASSED        [ 50%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_retries_on_transient_failures PASSED        [ 55%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_processes_in_batches PASSED                 [ 61%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_respects_rate_limits PASSED                 [ 66%]
tests/services/crm/test_close_bulk_push.py::test_bulk_push_result_provides_comprehensive_summary PASSED [ 72%]
tests/services/crm/test_close_bulk_push.py::test_lead_push_result_serialization PASSED                  [ 77%]
tests/services/crm/test_close_bulk_push.py::test_bulk_push_result_calculates_percentages PASSED         [ 83%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_empty_input PASSED                  [ 88%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_none_input PASSED                   [ 94%]
tests/services/crm/test_close_bulk_push.py::test_push_leads_handles_malformed_lead_data PASSED          [100%]

====================================== 18 passed in 0.42s =======================================
```

## Test Fixtures Available

```python
# Automatically available to all tests:
- mock_close_provider: AsyncMock of CloseProvider
- mock_db_session: AsyncMock of database session
- sample_leads_data: Sample enriched leads (2 companies, 4 contacts)
- bulk_push_service: CloseBulkPushService instance with mocks
```

## Debugging Failed Tests

### Check Test Output

```bash
# Show full traceback
pytest tests/services/crm/test_close_bulk_push.py::test_name -vv --tb=long

# Show local variables in traceback
pytest tests/services/crm/test_close_bulk_push.py::test_name -vv --tb=long --showlocals
```

### Use Print Debugging

```python
# In test file, add:
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use pytest's built-in capture:
def test_something(bulk_push_service, caplog):
    result = await bulk_push_service.push_leads(...)
    print(f"Result: {result}")  # Will show in pytest output with -s flag
```

### Run with stdout capture disabled

```bash
# Show all print statements
pytest tests/services/crm/test_close_bulk_push.py -s
```

## Environment Setup

If you get database connection errors:

```bash
# Set test database URL
export DATABASE_URL="postgresql+psycopg://test:test@localhost:5432/test_db"

# Or create .env file in backend directory
echo 'DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/test_db' > .env
```

## Performance Testing

```bash
# Measure test execution time
pytest tests/services/crm/test_close_bulk_push.py --durations=10

# Run with profiling
pytest tests/services/crm/test_close_bulk_push.py --profile
```

## Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/services/crm/test_close_bulk_push.py \
  --cov=app.services.crm.close_bulk_push \
  --cov-report=html

# Open report
open htmlcov/index.html
```

## Continuous Testing (Watch Mode)

```bash
# Install pytest-watch
pip install pytest-watch

# Run in watch mode (re-runs on file changes)
ptw tests/services/crm/test_close_bulk_push.py -- -v
```

## Test Implementation Checklist

- [ ] Module created: `app/services/crm/close_bulk_push.py`
- [ ] CloseBulkPushService class implemented
- [ ] BulkPushResult dataclass implemented
- [ ] LeadPushResult dataclass implemented
- [ ] All 18 tests passing
- [ ] Coverage > 90%
- [ ] No lint errors (ruff)
- [ ] Type checking passes (mypy/pyright)

## Next Steps

1. Create `app/services/crm/close_bulk_push.py`
2. Implement minimal code to fix first failing test
3. Run tests: `pytest tests/services/crm/test_close_bulk_push.py -v`
4. Repeat until all tests pass (GREEN phase)
5. Refactor and optimize (REFACTOR phase)
