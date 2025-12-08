# Enterprise Bidirectional Sync Architecture

## Overview

This document describes the enterprise-grade bidirectional sync system between Supabase and Close CRM, following LangGraph state management patterns and Supabase RLS best practices.

## Core Principles

### 1. **Zero Data Loss**
- Every field in Close CRM has a corresponding column in Supabase
- JSONB fallback columns for unexpected fields
- Full audit trail for every sync operation

### 2. **Enterprise Security (RLS)**
- Row-level security on all tables
- Service role for sync operations
- Authenticated role for dashboard access
- MFA enforcement for sensitive operations

### 3. **LangGraph State Management**
- Checkpointing for resumable syncs
- Thread-based state isolation
- Conflict detection and resolution queue

---

## Field Parity Matrix

### dim_companies ↔ Close Leads

| Supabase Column | Close CRM Field | Type | Notes |
|-----------------|-----------------|------|-------|
| `id` | `id` | VARCHAR(100) | Primary key |
| `company_name` | `name` | VARCHAR(500) | Required |
| `display_name` | `display_name` | VARCHAR(255) | May differ from name |
| `description` | `description` | TEXT | Notes/description |
| `domain` | `url` | VARCHAR(500) | Website domain |
| `phone` | `contacts[0].phones[0]` | VARCHAR(50) | Primary phone |
| `close_lead_id` | `id` | VARCHAR(100) | FK to Close |
| `close_status_id` | `status_id` | VARCHAR(100) | Status reference |
| `close_status_label` | `status_label` | VARCHAR(100) | Denormalized |
| `address_line1` | `addresses[0].address_1` | VARCHAR(255) | Primary address |
| `address_line2` | `addresses[0].address_2` | VARCHAR(255) | Secondary |
| `city` | `addresses[0].city` | VARCHAR(100) | City |
| `state` | `addresses[0].state` | VARCHAR(100) | State/Province |
| `postal_code` | `addresses[0].zipcode` | VARCHAR(20) | ZIP/Postal |
| `country` | `addresses[0].country` | VARCHAR(100) | Country |
| `close_created_by_id` | `created_by` | VARCHAR(100) | Creator user ID |
| `close_updated_by_id` | `updated_by` | VARCHAR(100) | Last updater |
| `close_created_at` | `date_created` | TIMESTAMPTZ | Creation date |
| `close_updated_at` | `date_updated` | TIMESTAMPTZ | Last update |
| `opportunities_json` | `opportunities` | JSONB | Snapshot array |
| `tasks_json` | `tasks` | JSONB | Snapshot array |
| `close_html_url` | `html_url` | VARCHAR(500) | Dashboard link |
| `integration_links` | `integration_links` | JSONB | Array of links |
| `close_custom_fields` | `custom.cf_*` | JSONB | Custom fields |
| `close_raw_data` | (full response) | JSONB | Complete backup |
| `last_sync_at` | - | TIMESTAMPTZ | Sync metadata |
| `sync_status` | - | VARCHAR(50) | pending/synced/error |
| `sync_error` | - | TEXT | Error message |

### dim_contacts ↔ Close Contacts

| Supabase Column | Close CRM Field | Type | Notes |
|-----------------|-----------------|------|-------|
| `id` | - | UUID | Internal PK |
| `close_contact_id` | `id` | VARCHAR(100) | Close PK |
| `close_lead_id` | `lead_id` | VARCHAR(100) | Parent lead |
| `company_id` | - | UUID | FK to dim_companies |
| `first_name` | `name` (parsed) | VARCHAR(100) | Parsed name |
| `last_name` | `name` (parsed) | VARCHAR(100) | Parsed name |
| `full_name` | `name` | VARCHAR(255) | Original name |
| `title` | `title` | VARCHAR(255) | Job title |
| `email` | `emails[0].email` | VARCHAR(255) | Primary email |
| `email_secondary` | `emails[1].email` | VARCHAR(255) | Secondary |
| `emails_all` | `emails` | JSONB | All emails array |
| `phone` | `phones[0].phone` | VARCHAR(50) | Primary phone |
| `phone_type` | `phones[0].type` | VARCHAR(50) | mobile/office/etc |
| `phone_secondary` | `phones[1].phone` | VARCHAR(50) | Secondary |
| `phones_all` | `phones` | JSONB | All phones array |
| `linkedin_url` | `urls[].url` (type=linkedin) | VARCHAR(500) | LinkedIn profile |
| `twitter_url` | `urls[].url` (type=twitter) | VARCHAR(500) | Twitter profile |
| `urls_all` | `urls` | JSONB | All URLs array |
| `close_created_by_id` | `created_by` | VARCHAR(100) | Creator |
| `close_updated_by_id` | `updated_by` | VARCHAR(100) | Last updater |
| `close_created_at` | `date_created` | TIMESTAMPTZ | Creation |
| `close_updated_at` | `date_updated` | TIMESTAMPTZ | Last update |
| `close_custom_fields` | `custom.cf_*` | JSONB | Custom fields |
| `close_raw_data` | (full response) | JSONB | Complete backup |
| `last_sync_at` | - | TIMESTAMPTZ | Sync metadata |
| `sync_status` | - | VARCHAR(50) | pending/synced/error |

### fact_close_activities ↔ Close Activities

| Supabase Column | Close CRM Field | Type | Notes |
|-----------------|-----------------|------|-------|
| `id` | - | UUID | Internal PK |
| `close_activity_id` | `id` | VARCHAR(100) | Close activity ID |
| `activity_type` | `_type` | VARCHAR(50) | email/sms/call/note |
| `close_lead_id` | `lead_id` | VARCHAR(100) | Parent lead |
| `close_contact_id` | `contact_id` | VARCHAR(100) | Related contact |
| `close_user_id` | `user_id` | VARCHAR(100) | Performing user |
| `direction` | `direction` | VARCHAR(20) | inbound/outbound |
| `status` | `status` | VARCHAR(50) | Activity status |
| `subject` | `subject` | VARCHAR(500) | Email subject |
| `body_text` | `body_text` | TEXT | Plain text body |
| `body_html` | `body_html` | TEXT | HTML body |
| `note_content` | `note` | TEXT | Note content |
| `note_content_html` | `note_html` | TEXT | HTML note |
| `email_envelope` | `envelope` | JSONB | Email metadata |
| `email_template_id` | `template_id` | VARCHAR(100) | Template used |
| `email_attachments` | `attachments` | JSONB | Attachment list |
| `call_duration` | `duration` | INTEGER | Call length (sec) |
| `call_recording_url` | `recording_url` | VARCHAR(500) | Recording link |
| `call_transferred_from` | `transferred_from` | VARCHAR(100) | Transfer source |
| `call_transferred_to` | `transferred_to` | VARCHAR(100) | Transfer dest |
| `sms_text` | `text` | TEXT | SMS content |
| `meeting_title` | `title` | VARCHAR(255) | Meeting title |
| `meeting_starts_at` | `starts_at` | TIMESTAMPTZ | Meeting start |
| `meeting_ends_at` | `ends_at` | TIMESTAMPTZ | Meeting end |
| `meeting_attendees` | `attendees` | JSONB | Attendee list |
| `meeting_calendar_link` | `calendar_event_link` | VARCHAR(500) | Calendar link |
| `sequence_id` | `sequence_id` | VARCHAR(100) | Sequence reference |
| `sequence_subscription_id` | `sequence_subscription_id` | VARCHAR(100) | Subscription |
| `activity_at` | `date_created` | TIMESTAMPTZ | Activity time |
| `close_created_at` | `date_created` | TIMESTAMPTZ | Creation |
| `close_updated_at` | `date_updated` | TIMESTAMPTZ | Last update |
| `close_raw_data` | (full response) | JSONB | Complete backup |

---

## Sync Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BIDIRECTIONAL SYNC FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐        ┌──────────────┐        ┌──────────┐      │
│  │  Close   │◄──────►│  SyncAgent   │◄──────►│ Supabase │      │
│  │   CRM    │        │  (LangGraph) │        │          │      │
│  └──────────┘        └──────────────┘        └──────────┘      │
│       │                     │                      │            │
│       │                     ▼                      │            │
│       │            ┌──────────────┐               │            │
│       │            │  Checkpoint  │               │            │
│       │            │    Store     │               │            │
│       │            └──────────────┘               │            │
│       │                     │                      │            │
│       ▼                     ▼                      ▼            │
│  ┌──────────┐        ┌──────────────┐        ┌──────────┐      │
│  │ Webhooks │───────►│ ConflictQueue│◄───────│   RLS    │      │
│  └──────────┘        └──────────────┘        │ Policies │      │
│                             │                 └──────────┘      │
│                             ▼                                   │
│                      ┌──────────────┐                          │
│                      │  AuditLog    │                          │
│                      └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## LangGraph State Schema

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages

class SyncState(TypedDict):
    """State for bidirectional sync agent."""
    
    # Core state
    messages: Annotated[list, add_messages]
    thread_id: str
    
    # Sync direction
    direction: Literal["close_to_supabase", "supabase_to_close", "bidirectional"]
    
    # Entity being synced
    entity_type: Literal["lead", "contact", "activity"]
    
    # Cursors for resumable sync
    close_cursor: str | None
    supabase_cursor: str | None
    
    # Counters
    processed_count: int
    error_count: int
    conflict_count: int
    
    # Conflict queue
    pending_conflicts: list[dict]
    
    # Status
    status: Literal["pending", "running", "paused", "completed", "error"]
    error_message: str | None
    
    # Timestamps
    started_at: str
    last_checkpoint_at: str
```

---

## RLS Policy Structure

### Enterprise Security Levels

1. **service_role**: Full access (sync operations)
2. **authenticated**: Read + limited write (dashboard users)
3. **anon**: No access

### Policy Template

```sql
-- Enable RLS
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

-- Service role: Full access
CREATE POLICY "{table}_service_full_access"
ON {table_name}
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Authenticated: Read access
CREATE POLICY "{table}_auth_read"
ON {table_name}
FOR SELECT
TO authenticated
USING (true);

-- Authenticated: Write own records (where applicable)
CREATE POLICY "{table}_auth_write_own"
ON {table_name}
FOR ALL
TO authenticated
USING ((SELECT auth.uid()) = created_by_user_id)
WITH CHECK ((SELECT auth.uid()) = created_by_user_id);
```

---

## Conflict Resolution

### Detection Rules

1. **Timestamp Conflict**: Both sides updated since last sync
2. **Delete Conflict**: One side deleted, other modified
3. **Schema Conflict**: Field type mismatch

### Resolution Strategies

```python
RESOLUTION_STRATEGIES = {
    "close_wins": "Always use Close CRM value",
    "supabase_wins": "Always use Supabase value", 
    "newer_wins": "Use most recently updated value",
    "manual": "Queue for manual resolution",
    "merge": "Attempt to merge non-conflicting fields"
}
```

---

## Implementation Checklist

- [ ] Apply field parity migration
- [ ] Create comprehensive RLS policies
- [ ] Implement SyncAgent with LangGraph
- [ ] Set up conflict resolution queue
- [ ] Configure audit logging
- [ ] Test bidirectional sync
- [ ] Set up monitoring/alerts

---

## References

- [Close API Documentation](https://developer.close.com/resources/)
- [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [LangGraph Persistence](https://docs.langchain.com/langgraph-platform/use-remote-graph)
