# Phase 2 Plan 1: Meeting Activities Summary

**Added meeting creation and sync capability, auto-creating meetings from MEETING_REQUEST replies**

## Accomplishments

- Added `create_meeting()` to CloseCallingClient with full API integration
- Extended `get_activities_since()` to include meetings as a default activity type
- Updated reply router to auto-create Close meetings when MEETING_REQUEST replies are detected
- Added intelligent meeting time extraction from email body using regex patterns
- Implemented fallback to next business day 2pm if no time can be extracted
- Added CLOSE_WRITE_DISABLED safety check to meeting creation

## Files Created/Modified

- `backend/app/services/crm/close_calling.py` - Added `create_meeting()` method
  - POST to `/activity/meeting/` endpoint
  - Duration in seconds, starts_at in ISO format
  - CLOSE_WRITE_DISABLED check at start
  - Returns meeting ID, timestamps, title, note

- `backend/app/services/crm/close_email.py` - Extended `get_activities_since()`
  - Default activity_types now includes "meeting"
  - Updated docstring with meeting fields: id, lead_id, contact_id, starts_at, ends_at, duration, title, note

- `backend/app/services/outreach/reply_router.py` - MEETING_REQUEST handling
  - Imported CloseCallingClient
  - Added `_extract_meeting_time()` method with regex patterns for:
    - Day names ("Monday at 2pm")
    - Month names ("January 5th at 2pm")
    - Numeric dates ("12/27 at 2pm")
  - Added `_get_next_business_day_2pm()` helper for fallback
  - Enhanced `_handle_meeting_request()` to:
    - Extract meeting time from email body
    - Create Close meeting activity
    - Return meeting_id and meeting_scheduled_at in response
    - Keep existing Slack notification

## Decisions Made

- Used regex-based time extraction rather than NLP for simplicity and speed
- Default meeting duration set to 30 minutes (standard discovery call)
- Fallback to next business day 2pm UTC when no time found in email
- Meeting title format: "Discovery Call - {company_name}"

## Issues Encountered

None

## Next Step

Ready for 02-02-PLAN.md (Task Activities)
