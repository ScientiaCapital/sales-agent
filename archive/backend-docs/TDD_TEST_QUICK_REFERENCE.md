# TDD Test Quick Reference - Close Bulk Push Service

## Test File
`backend/tests/services/crm/test_close_bulk_push.py` (775 lines, 18 tests)

## Test Matrix

| # | Test Name | Category | Purpose | Key Assertions |
|---|-----------|----------|---------|----------------|
| 1 | `test_push_leads_creates_lead_with_contacts` | Core | Lead creation with ATL contacts | success_count=2, only ATL contacts included |
| 2 | `test_push_leads_includes_all_contacts_when_atl_only_false` | Core | Include BTL contacts | All 3 contacts (ATL+BTL) when atl_only=False |
| 3 | `test_push_leads_respects_dry_run` | Core | Dry-run mode | create_lead NOT called, dry_run=True |
| 4 | `test_dry_run_validates_data_format` | Core | Validation in dry-run | Detects invalid leads without writing |
| 5 | `test_push_leads_handles_duplicates` | Deduplication | Skip existing leads | skipped_duplicates=1, create_lead called once |
| 6 | `test_push_leads_adds_contacts_to_existing_when_update_mode` | Deduplication | Update existing leads | matched_lead_id passed, status="updated" |
| 7 | `test_push_leads_filters_atl_contacts_only` | ATL Filtering | Filter ATL contacts | Only ATL contacts, BTL-only leads skipped |
| 8 | `test_atl_filtering_handles_missing_is_atl_flag` | ATL Filtering | Missing is_atl flag | Treats missing flag as BTL (excluded) |
| 9 | `test_push_leads_handles_api_errors_gracefully` | Error Handling | Graceful error handling | failed_count=1, error message captured |
| 10 | `test_push_leads_retries_on_transient_failures` | Error Handling | Retry with backoff | create_lead called 3 times, eventually succeeds |
| 11 | `test_push_leads_processes_in_batches` | Performance | Batch processing | 25 leads in 3 batches (10+10+5) |
| 12 | `test_push_leads_respects_rate_limits` | Performance | Rate limiting | 500ms delay between calls |
| 13 | `test_bulk_push_result_provides_comprehensive_summary` | Results | Comprehensive summary | All stats correct, results by status |
| 14 | `test_lead_push_result_serialization` | Results | JSON serialization | to_dict() works correctly |
| 15 | `test_bulk_push_result_calculates_percentages` | Results | Success/failure rates | success_rate=0.8, failure_rate=0.1 |
| 16 | `test_push_leads_handles_empty_input` | Edge Cases | Empty input | total_leads=0, no errors |
| 17 | `test_push_leads_handles_none_input` | Edge Cases | None input | Raises ValueError |
| 18 | `test_push_leads_handles_malformed_lead_data` | Edge Cases | Malformed data | success_count=1, failed_count≥1 |

## Test Categories

- **Core Functionality**: 4 tests
- **Deduplication**: 2 tests
- **ATL Filtering**: 2 tests
- **Error Handling**: 2 tests
- **Performance**: 2 tests
- **Results**: 3 tests
- **Edge Cases**: 3 tests

## Key Test Fixtures

```python
@pytest.fixture
def mock_close_provider():
    """Mock CloseProvider with AsyncMock"""

@pytest.fixture
def mock_db_session():
    """Mock database session"""

@pytest.fixture
def sample_leads_data():
    """Sample enriched leads (2 companies, 4 contacts)"""

@pytest.fixture
def bulk_push_service(mock_close_provider, mock_db_session):
    """CloseBulkPushService instance"""
```

## Expected Method Signatures

### push_leads()
```python
async def push_leads(
    leads_data: List[Dict[str, Any]],
    dry_run: bool = False,
    atl_only: bool = True,
    update_existing: bool = False,
    max_retries: int = 2,
    batch_size: int = 50,
    rate_limit_delay: float = 0.0
) -> BulkPushResult
```

### _check_existing_lead()
```python
async def _check_existing_lead(
    domain: str,
    email: Optional[str] = None
) -> Optional[Dict[str, Any]]
```

## Run Tests

```bash
# All tests (will fail in RED phase)
pytest tests/services/crm/test_close_bulk_push.py -v

# Specific test
pytest tests/services/crm/test_close_bulk_push.py::test_push_leads_respects_dry_run -v

# With coverage
pytest tests/services/crm/test_close_bulk_push.py --cov=app.services.crm.close_bulk_push

# Verbose output
pytest tests/services/crm/test_close_bulk_push.py -vv --tb=short
```

## Current Status

**✅ RED PHASE COMPLETE**
- 18 comprehensive tests written
- Module doesn't exist yet (expected)
- All imports will fail (expected)
- Ready for GREEN phase implementation

## Next: GREEN Phase

Create `app/services/crm/close_bulk_push.py` and implement until tests pass.
