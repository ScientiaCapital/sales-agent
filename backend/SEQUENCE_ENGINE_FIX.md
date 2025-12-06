# Fix M1: Complete Due Email Delay Logic

**Status**: ✅ FIXED
**Date**: 2025-12-06
**File**: `backend/app/services/sequences/engine.py`

## Problem Statement

The `process_due_emails()` method had incomplete logic for checking step delays. All pending/active entries were processed immediately rather than respecting the `wait_days` configuration from sequence steps.

### Original Code (Lines 267-323)

```python
async def process_due_emails(self, limit: int = 50) -> Dict[str, Any]:
    try:
        # Find entries due for execution
        query = select(SequenceEntry).where(
            and_(
                SequenceEntry.status.in_(["pending", "active"]),
                or_(
                    SequenceEntry.last_email_sent.is_(None),
                    # Add logic for delay checking here based on sequence steps
                ),
            )
        ).limit(limit)

        result = await self.session.execute(query)
        entries = result.scalars().all()

        # Process all entries without delay checking
        ...
```

## Solution Implemented

### 1. Proper Delay Checking

- **First emails (last_email_sent=None)**: Processed immediately
- **Subsequent emails**: Only processed if `time_since_last >= step.delay_days`

### 2. Input Validation

- Validates `limit` parameter is positive integer
- Caps maximum limit at 1000
- Defaults to 50 if invalid

### 3. Field Name Consistency

Fixed inconsistency where:
- Sequence model uses `delay_days` in JSON steps
- Engine was using `wait_days` (incorrect)

**Changes:**
- Line 244: `step.get("wait_days", 3)` → `step.get("delay_days", 3)`
- Line 687-690: Updated docstring to use `delay_days`

### 4. Enhanced Logging

Added detailed logging for:
- Number of entries found vs. due vs. filtered
- Remaining time for not-yet-due entries
- Execution failures with error details

### 5. Return Value Enhancement

Added `"filtered"` count to return dict to track how many entries were skipped due to delays.

## Code Changes

### Modified Method (Lines 267-387)

```python
async def process_due_emails(self, limit: int = 50) -> Dict[str, Any]:
    """
    Process all due emails (cron job entry point).

    Finds entries that are due for their next step and executes them.
    Respects sequence step delays (delay_days) to avoid sending emails too early.

    Args:
        limit: Maximum number of entries to process in one batch (max 1000)

    Returns:
        Dict with processing statistics
    """
    try:
        # Validate limit parameter
        if not isinstance(limit, int) or limit <= 0:
            logger.warning(f"Invalid limit parameter: {limit}, using default 50")
            limit = 50
        elif limit > 1000:
            logger.warning(f"Limit {limit} exceeds maximum 1000, capping at 1000")
            limit = 1000

        # Find entries that are pending or active
        query = select(SequenceEntry).where(
            SequenceEntry.status.in_(["pending", "active"])
        ).limit(limit * 2)  # Fetch more to account for filtering

        result = await self.session.execute(query)
        all_entries = result.scalars().all()

        # Filter entries that are actually due based on sequence delay_days
        due_entries = []
        filtered_count = 0

        for entry in all_entries:
            if len(due_entries) >= limit:
                break

            # If no email sent yet, it's due immediately (first email)
            if entry.last_email_sent is None:
                due_entries.append(entry)
                continue

            # Get sequence to check step delay
            sequence = await self.session.get(Sequence, entry.sequence_id)
            if not sequence or not sequence.steps:
                logger.warning(f"Entry {entry.id} has invalid sequence, skipping")
                filtered_count += 1
                continue

            # Check if we've completed all steps
            if entry.current_step >= len(sequence.steps):
                logger.debug(f"Entry {entry.id} has completed all steps, skipping")
                filtered_count += 1
                continue

            # Get the current step's delay requirement
            current_step_index = entry.current_step
            if current_step_index > 0 and current_step_index < len(sequence.steps):
                step = sequence.steps[current_step_index]
                delay_days = step.get("delay_days", 0)

                # Calculate if enough time has passed
                time_since_last = datetime.utcnow() - entry.last_email_sent
                required_delay = timedelta(days=delay_days)

                if time_since_last >= required_delay:
                    due_entries.append(entry)
                else:
                    # Not due yet
                    remaining = required_delay - time_since_last
                    logger.debug(
                        f"Entry {entry.id} not due yet, "
                        f"{remaining.total_seconds() / 3600:.1f}h remaining"
                    )
                    filtered_count += 1
            else:
                # Shouldn't happen, but handle gracefully
                due_entries.append(entry)

        logger.info(
            f"Found {len(all_entries)} pending/active entries, "
            f"{len(due_entries)} are due, {filtered_count} filtered by delay"
        )

        processed = 0
        sent = 0
        errors = 0

        for entry in due_entries:
            try:
                exec_result = await self.execute_step(entry.id)
                processed += 1
                if exec_result.get("success"):
                    sent += 1
                else:
                    errors += 1
                    logger.warning(
                        f"Failed to execute step for entry {entry.id}: "
                        f"{exec_result.get('error', 'Unknown error')}"
                    )
            except Exception as e:
                logger.error(f"Error processing entry {entry.id}: {e}")
                errors += 1

        logger.info(
            f"Processed {processed} due emails: {sent} sent, {errors} errors"
        )

        return {
            "processed": processed,
            "sent": sent,
            "errors": errors,
            "filtered": filtered_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to process due emails: {e}")
        return {"processed": 0, "sent": 0, "errors": 1, "error": str(e)}
```

## Testing

### Validation Script

Created `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/tests/test_process_due_simple.py` which validates:

1. ✅ Delay logic implementation
2. ✅ Input validation
3. ✅ First email handling (immediate)
4. ✅ Subsequent email delay checking
5. ✅ Field name consistency (delay_days)

**Test Results**: All tests passed ✓

### Test Scenarios Covered

| Scenario | Expected Behavior | Status |
|----------|------------------|--------|
| First email (last_email_sent=None) | Process immediately | ✅ Pass |
| 1 day passed, need 3 days | Skip (not due) | ✅ Pass |
| 4 days passed, need 3 days | Process (is due) | ✅ Pass |
| Exactly at boundary (3 days) | Process (is due) | ✅ Pass |
| Zero delay required | Process immediately | ✅ Pass |
| Invalid limit (-5) | Default to 50 | ✅ Pass |
| Limit exceeds max (5000) | Cap at 1000 | ✅ Pass |

## Acceptance Criteria

- [x] Entries with `last_email_sent = None` processed immediately
- [x] Entries with `last_email_sent != None` respect `delay_days` from sequence steps
- [x] Input validation for `limit` parameter (positive int, max 1000)
- [x] Logging for filtered entries
- [x] No breaking changes to existing functionality
- [x] Consistent use of `delay_days` (not `wait_days`)
- [x] Return value includes `filtered` count

## Files Modified

1. `/Users/tmkipper/Desktop/tk_projects/sales-agent/backend/app/services/sequences/engine.py`
   - Lines 267-387: Complete rewrite of `process_due_emails()`
   - Line 244: Fixed `wait_days` → `delay_days`
   - Lines 687-690: Updated docstring

## API Impact

### Response Schema Change (Non-Breaking)

Added new optional field to `ProcessDueResponse`:

```python
{
    "processed": int,
    "sent": int,
    "errors": int,
    "filtered": int,  # NEW: Number of entries filtered by delay
    "timestamp": str
}
```

This is a non-breaking change as it adds a new field (existing code will ignore it).

## Performance Considerations

- **Database queries**: Fetches `limit * 2` entries to account for filtering
- **N+1 query issue**: Loads sequence for each entry individually
  - **Optimization opportunity**: Could use joinedload for better performance
  - **Current approach**: Acceptable for typical batch sizes (50-100 entries)

## Next Steps

### Recommended (Not Required)

1. **Performance optimization**: Use SQLAlchemy eager loading to reduce queries
2. **Unit tests**: Add full integration tests once test environment is configured
3. **Monitoring**: Add metrics for filtered_count to track delay effectiveness

### Example Optimization (Future)

```python
from sqlalchemy.orm import joinedload

query = select(SequenceEntry).options(
    joinedload(SequenceEntry.sequence)
).where(...)
```

## Verification

Run the validation script:

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
python3 tests/test_process_due_simple.py
```

Expected output: `✓ ALL TESTS PASSED`
