# TDD RED Phase Complete: Close Bulk Push Service

## Summary

Created comprehensive TDD test suite for `CloseBulkPushService` that pushes enriched leads from Supabase to Close CRM. Following TDD methodology, **all tests are currently failing** (RED phase) because the implementation doesn't exist yet.

## File Created

- **Test File**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/tests/services/crm/test_close_bulk_push.py`
- **Lines of Code**: 775 lines
- **Test Count**: 18 comprehensive test cases

## Test Coverage

### 1. Core Functionality Tests (4 tests)
- `test_push_leads_creates_lead_with_contacts` - Verify lead creation with ATL contacts
- `test_push_leads_includes_all_contacts_when_atl_only_false` - Test ATL/BTL inclusion
- `test_push_leads_respects_dry_run` - Ensure dry-run mode doesn't write
- `test_dry_run_validates_data_format` - Test validation in dry-run mode

### 2. Duplicate Detection Tests (2 tests)
- `test_push_leads_handles_duplicates` - Skip existing leads
- `test_push_leads_adds_contacts_to_existing_when_update_mode` - Update existing leads

### 3. ATL Filtering Tests (2 tests)
- `test_push_leads_filters_atl_contacts_only` - Only include ATL contacts
- `test_atl_filtering_handles_missing_is_atl_flag` - Handle missing flags

### 4. Error Handling Tests (2 tests)
- `test_push_leads_handles_api_errors_gracefully` - Graceful error handling
- `test_push_leads_retries_on_transient_failures` - Retry with backoff

### 5. Performance Tests (2 tests)
- `test_push_leads_processes_in_batches` - Batch processing
- `test_push_leads_respects_rate_limits` - Rate limiting

### 6. Result Aggregation Tests (2 tests)
- `test_bulk_push_result_provides_comprehensive_summary` - Complete result summary
- `test_lead_push_result_serialization` - JSON serialization
- `test_bulk_push_result_calculates_percentages` - Success/failure rates

### 7. Edge Case Tests (3 tests)
- `test_push_leads_handles_empty_input` - Empty lead list
- `test_push_leads_handles_none_input` - None input validation
- `test_push_leads_handles_malformed_lead_data` - Malformed data handling

## Test Data Structure

```python
sample_leads_data = [{
    "company_name": "Test Electric Co",
    "domain": "testelectric.com",
    "industry": "Electrical Contractors",
    "qualification_score": 85,
    "contacts": [
        {
            "name": "John Owner",
            "first_name": "John",
            "last_name": "Owner",
            "title": "Owner",
            "email": "john@testelectric.com",
            "phone": "555-1234",
            "is_atl": True,  # Above The Line
            "position": "Owner"
        },
        {
            "name": "Bob Tech",
            "title": "Technician",
            "email": "bob@testelectric.com",
            "is_atl": False,  # Below The Line (excluded by default)
        }
    ]
}]
```

## Expected Service Interface

Based on the tests, the `CloseBulkPushService` should implement:

### Constructor
```python
CloseBulkPushService(
    close_provider: CloseProvider,
    db_session: Session
)
```

### Main Method
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

### Data Classes
```python
@dataclass
class LeadPushResult:
    company_name: str
    domain: str
    status: str  # "created", "duplicate", "failed", "would_create", "updated"
    close_lead_id: Optional[str] = None
    existing_lead_id: Optional[str] = None
    contacts_created: int = 0
    error_message: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict"""
        pass

@dataclass
class BulkPushResult:
    total_leads: int
    success_count: int
    failed_count: int
    skipped_duplicates: int
    skipped_no_contacts: int
    dry_run: bool
    would_create_count: int = 0
    batches_processed: int = 0
    results: List[LeadPushResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success percentage"""
        pass

    @property
    def failure_rate(self) -> float:
        """Calculate failure percentage"""
        pass

    @property
    def duplicate_rate(self) -> float:
        """Calculate duplicate percentage"""
        pass
```

### Helper Methods
```python
async def _check_existing_lead(
    self,
    domain: str,
    email: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Check if lead already exists in Close CRM"""
    pass
```

## Test Patterns Used

### 1. AsyncMock for Async Functions
```python
mock_close_provider = AsyncMock()
mock_close_provider.create_lead = AsyncMock(return_value={"id": "lead_123"})
```

### 2. Patch for Internal Methods
```python
with patch.object(
    bulk_push_service,
    '_check_existing_lead',
    new_callable=AsyncMock
) as mock_check:
    mock_check.return_value = {"id": "existing_lead"}
```

### 3. pytest.mark.asyncio for Async Tests
```python
@pytest.mark.asyncio
async def test_something(bulk_push_service):
    result = await bulk_push_service.push_leads(...)
```

### 4. Fixtures for Test Data
```python
@pytest.fixture
def sample_leads_data():
    return [...]

@pytest.fixture
def bulk_push_service(mock_close_provider, mock_db_session):
    return CloseBulkPushService(...)
```

## Verification

**RED Phase Confirmed**: Module import fails as expected
```bash
$ python3 -c "from app.services.crm.close_bulk_push import CloseBulkPushService"
ModuleNotFoundError: No module named 'app.services.crm.close_bulk_push'
```

## Next Steps (GREEN Phase)

1. Create `app/services/crm/close_bulk_push.py`
2. Implement `CloseBulkPushService` class
3. Implement `BulkPushResult` and `LeadPushResult` dataclasses
4. Run tests: `pytest tests/services/crm/test_close_bulk_push.py -v`
5. Fix failing tests until all pass (GREEN phase)
6. Refactor and optimize (REFACTOR phase)

## Integration with Existing Code

The service integrates with:
- **CloseProvider** (`app/services/crm/close.py`) - Uses `create_lead()` method
- **Deduplication Engine** (`app/services/crm/deduplication.py`) - Check existing leads
- **Database Session** - Query Supabase for enriched leads
- **pytest patterns** - Follows existing test patterns from `test_deduplication.py`

## Test Execution Notes

Due to database dependency in conftest, you may need to:
1. Set `DATABASE_URL` environment variable
2. Or run specific tests that don't require DB setup
3. Full test suite will run once implementation is complete

## References

- Existing CloseProvider: `backend/app/services/crm/close.py` (1,153 lines)
- Test patterns: `backend/tests/services/crm/test_deduplication.py`
- pytest config: `backend/pytest.ini` with `asyncio_mode = auto`
