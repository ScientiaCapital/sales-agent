# Critical Bug Fixes - SQL INSERT, Migrations, and Docker

## Date: 2025-01-16

This document provides fixes for 5 critical bugs related to SQL INSERT statements, conflicting migrations, and Docker build configuration.

---

## Bug 1: email_drafts INSERT - Wrong Column Names

### ❌ INCORRECT CODE (Will Cause Runtime Errors)
```python
# WRONG - These columns don't exist
db.execute(
    text("""
        INSERT INTO email_drafts (
            contact_id,
            subject_line,
            email_body,
            talking_points,
            created_at,
            status
        ) VALUES (
            :contact_id,
            :subject_line,
            :email_body,
            :talking_points,
            :created_at,
            :status
        )
    """),
    {...}
)
```

**Error**: `column "contact_id" does not exist`, `column "subject_line" does not exist`, etc.

### ✅ CORRECT CODE (Fixed)
```python
from sqlalchemy import text
from datetime import datetime
import json

db.execute(
    text("""
        INSERT INTO email_drafts (
            close_lead_id,
            close_contact_id,
            close_activity_id,
            subject,
            body_html,
            research_context,
            created_at
        ) VALUES (
            :close_lead_id,
            :close_contact_id,
            :close_activity_id,
            :subject,
            :body_html,
            :research_context::jsonb,
            :created_at
        )
        RETURNING id
    """),
    {
        "close_lead_id": lead_id,
        "close_contact_id": contact_id,
        "close_activity_id": activity_id,  # Optional, can be None
        "subject": "Subject line here",  # NOT subject_line
        "body_html": "<html>Email body</html>",  # NOT email_body
        "research_context": json.dumps({
            "talking_points": ["Point 1", "Point 2"],  # Store in JSON, not separate column
            "company_research": {...},
            "personalization_data": {...}
        }),
        "created_at": datetime.now()
        # NO status column - use sent_at (NULL = draft, NOT NULL = sent)
    }
)
```

**Column Mapping**:
- `contact_id` → `close_lead_id` OR `close_contact_id`
- `subject_line` → `subject`
- `email_body` → `body_html`
- `talking_points` → Store in `research_context` JSONB field
- `status` → Use `sent_at` (NULL = draft, NOT NULL = sent)

---

## Bug 2: email_engagement INSERT - Wrong Column Names

### ❌ INCORRECT CODE (Will Cause Runtime Errors)
```python
# WRONG - These columns don't exist
db.execute(
    text("""
        INSERT INTO email_engagement (
            email_id,
            contact_id,
            open_count,
            first_opened_at,
            last_opened_at,
            checked_at
        ) VALUES (
            :email_id,
            :contact_id,
            :open_count,
            :first_opened_at,
            :last_opened_at,
            :checked_at
        )
    """),
    {...}
)
```

**Error**: `column "email_id" does not exist`, `column "contact_id" does not exist`, etc.

### ✅ CORRECT CODE (Fixed)
```python
from sqlalchemy import text
from datetime import datetime
import json

# Track email open event
db.execute(
    text("""
        INSERT INTO email_engagement (
            email_draft_id,
            event_type,
            event_timestamp,
            metadata
        ) VALUES (
            :email_draft_id,
            :event_type,
            :event_timestamp,
            :metadata::jsonb
        )
    """),
    {
        "email_draft_id": draft_id,  # NOT email_id
        "event_type": "open",  # Must be: 'open', 'click', 'reply', 'high_intent_detected'
        "event_timestamp": datetime.now(),
        "metadata": json.dumps({
            "open_count": 1,  # Store in metadata JSON
            "first_opened_at": datetime.now().isoformat(),  # Store in metadata
            "last_opened_at": datetime.now().isoformat(),  # Store in metadata
            "checked_at": datetime.now().isoformat(),  # Store in metadata
            "user_agent": request.headers.get("User-Agent"),
            "ip_address": request.client.host
        })
    }
)
```

**Column Mapping**:
- `email_id` → `email_draft_id` (foreign key to email_drafts table)
- `contact_id` → Remove (not needed, email_draft_id links to contact)
- `open_count` → Store in `metadata` JSONB
- `first_opened_at` → Store in `metadata` JSONB
- `last_opened_at` → Store in `metadata` JSONB
- `checked_at` → Store in `metadata` JSONB

**Schema**:
```sql
CREATE TABLE email_engagement (
    id SERIAL PRIMARY KEY,
    email_draft_id INTEGER NOT NULL REFERENCES email_drafts(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('open', 'click', 'reply', 'high_intent_detected')),
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB  -- Store all additional data here
);
```

---

## Bug 3: Conflicting Migration Files

### ❌ PROBLEM
Two migration files create the same tables with different schemas:
- `014_add_social_intelligence_tables.py` - Creates `email_engagement` WITH CHECK constraint
- `2025_11_17_social_intelligence_schema.py` - Creates `email_engagement` WITHOUT CHECK constraint

This causes:
- Migration conflicts
- Ambiguity about which schema is correct
- Data inconsistency

### ✅ SOLUTION

**Option 1: Keep One, Delete Other (Recommended)**

1. **Check which migration has been applied**:
```bash
cd backend
alembic current
alembic history
```

2. **If neither applied**: Delete the newer/duplicate one (`2025_11_17_social_intelligence_schema.py`)

3. **If one already applied**: 
   - Keep the applied one
   - Delete the duplicate
   - If schemas differ, create a new migration to align them

**Option 2: Merge Migrations**

If both need to exist (different features):
1. Rename one to have a different revision ID
2. Ensure proper `down_revision` chain
3. Make schemas consistent (both should have CHECK constraint)

**Recommended Action**:
```bash
# 1. Check current state
cd backend
alembic current

# 2. If 014 is applied, delete 2025_11_17
rm alembic/versions/2025_11_17_social_intelligence_schema.py

# 3. If 2025_11_17 is applied, update 014 to match OR delete 014
# (Check which schema is correct first)

# 4. Verify migration chain
alembic history --verbose
```

---

## Bug 4: Missing Index Drops in downgrade()

### ❌ PROBLEM
Migration file `014_add_social_intelligence_tables.py` creates indexes in `upgrade()` but doesn't drop them in `downgrade()`, leaving orphaned indexes.

### ❌ INCORRECT downgrade()
```python
def downgrade() -> None:
    # Missing index drops!
    op.drop_table('email_engagement')
    op.drop_table('email_drafts')
    # Indexes remain in database!
```

### ✅ CORRECT downgrade()
```python
def downgrade() -> None:
    # Drop indexes FIRST (before dropping tables)
    op.drop_index('idx_email_engagement_event_timestamp', table_name='email_engagement')
    op.drop_index('idx_email_engagement_event_type', table_name='email_engagement')
    op.drop_index('idx_email_engagement_email_draft_id', table_name='email_engagement')
    
    op.drop_index('idx_email_drafts_sent_at', table_name='email_drafts')
    op.drop_index('idx_email_drafts_created_at', table_name='email_drafts')
    op.drop_index('idx_email_drafts_close_contact_id', table_name='email_drafts')
    op.drop_index('idx_email_drafts_close_lead_id', table_name='email_drafts')
    
    # Drop CHECK constraint
    op.drop_constraint('check_email_engagement_event_type', table_name='email_engagement', type_='check')
    
    # Now drop tables
    op.drop_table('email_engagement')
    op.drop_table('email_drafts')
```

**Important**: Always drop indexes and constraints BEFORE dropping tables, in reverse order of creation.

---

## Bug 5: Docker Build Context Mismatch

### ❌ INCORRECT Dockerfile.serverless
```dockerfile
# Line 35: Context is workspace root (.)
# But COPY commands expect backend/ directory

FROM python:3.13-slim

WORKDIR /app

# These will FAIL - files don't exist relative to workspace root
COPY app /app/app
COPY social_intelligence_runner.py /app/
COPY check_email_engagement.py /app/
COPY requirements.txt /app/
```

**Error**: `COPY failed: file not found in build context`

### ✅ CORRECT Dockerfile.serverless

**Option 1: Fix Build Context (Recommended)**
```dockerfile
# Dockerfile.serverless should be at: backend/Dockerfile.serverless
# Build command: docker build -f backend/Dockerfile.serverless -t image:tag ./backend

FROM python:3.13-slim

WORKDIR /app

# Now paths are correct (relative to backend/ directory)
COPY app /app/app
COPY social_intelligence_runner.py /app/
COPY check_email_engagement.py /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "social_intelligence_runner.py"]
```

**Build Command**:
```bash
# Build from backend directory with correct context
docker build -f backend/Dockerfile.serverless -t sales-agent-serverless:latest ./backend
```

**Option 2: Fix COPY Paths (If context must be root)**
```dockerfile
# If building from root with context "."
FROM python:3.13-slim

WORKDIR /app

# Adjust paths to match root context
COPY backend/app /app/app
COPY backend/social_intelligence_runner.py /app/
COPY backend/check_email_engagement.py /app/
COPY backend/requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "social_intelligence_runner.py"]
```

**Build Command**:
```bash
# Build from root with context "."
docker build -f backend/Dockerfile.serverless -t sales-agent-serverless:latest .
```

**Recommended**: Use Option 1 (fix build context) - cleaner and more standard.

---

## Verification Checklist

### SQL INSERT Fixes
- [ ] Search codebase for `INSERT INTO email_drafts` - verify column names match schema
- [ ] Search codebase for `INSERT INTO email_engagement` - verify column names match schema
- [ ] Test INSERT statements in development database
- [ ] Verify JSONB metadata storage works correctly

### Migration Fixes
- [ ] Check for duplicate migration files: `014_add_social_intelligence_tables.py` and `2025_11_17_social_intelligence_schema.py`
- [ ] Verify only one migration creates `email_engagement` and `email_drafts` tables
- [ ] Check `downgrade()` functions drop all indexes and constraints
- [ ] Test migration rollback: `alembic downgrade -1`

### Docker Fixes
- [ ] Verify `Dockerfile.serverless` exists at `backend/Dockerfile.serverless`
- [ ] Check build context matches COPY paths
- [ ] Test Docker build: `docker build -f backend/Dockerfile.serverless -t test ./backend`
- [ ] Verify all referenced files exist before COPY commands

---

## Files to Check/Update

1. **Email Drafts Service** (e.g., `backend/app/services/email_drafts_service.py`)
   - Fix INSERT column names
   - Use `close_lead_id`, `subject`, `body_html`, `research_context`

2. **Email Engagement Service** (e.g., `backend/app/services/email_engagement_service.py`)
   - Fix INSERT column names
   - Use `email_draft_id`, `event_type`, `event_timestamp`, `metadata`

3. **Migration Files**:
   - `backend/alembic/versions/014_add_social_intelligence_tables.py` - Check downgrade()
   - `backend/alembic/versions/2025_11_17_social_intelligence_schema.py` - Delete if duplicate

4. **Dockerfile**:
   - `backend/Dockerfile.serverless` - Fix build context or COPY paths

---

## Summary

| Bug | Issue | Fix |
|-----|-------|-----|
| 1 | email_drafts INSERT wrong columns | Use `close_lead_id`, `subject`, `body_html`, `research_context` |
| 2 | email_engagement INSERT wrong columns | Use `email_draft_id`, `event_type`, `event_timestamp`, `metadata` |
| 3 | Conflicting migrations | Delete duplicate, keep one with CHECK constraint |
| 4 | Missing index drops | Add all index drops to `downgrade()` before table drops |
| 5 | Docker context mismatch | Use `./backend` context OR fix COPY paths |

---

## Quick Fix Commands

```bash
# 1. Find files with wrong INSERT statements
cd backend
grep -r "INSERT INTO email_drafts" --include="*.py"
grep -r "INSERT INTO email_engagement" --include="*.py"

# 2. Check for duplicate migrations
ls -la alembic/versions/*social_intelligence*

# 3. Verify migration downgrade functions
grep -A 20 "def downgrade" alembic/versions/014_add_social_intelligence_tables.py

# 4. Test Docker build
docker build -f backend/Dockerfile.serverless -t test ./backend
```

