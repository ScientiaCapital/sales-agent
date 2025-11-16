# SQL Schema Fixes for Email Engagement, Email Drafts, and Social Posts

## Date: 2025-01-16

This document provides correct SQL patterns and schema fixes for the reported bugs in email_engagement, email_drafts, and social_posts tables.

---

## Bug 1: email_engagement Table - Wrong Column Names

### ❌ INCORRECT INSERT (Current - Will Fail)
```sql
INSERT INTO email_engagement (
    email_id,
    contact_id,
    open_count,
    first_opened_at,
    last_opened_at,
    checked_at
) VALUES (...);
```

**Problem**: These columns don't exist in the schema. The actual schema only has:
- `id`
- `email_draft_id`
- `event_type`
- `event_timestamp`
- `metadata`

### ✅ CORRECT INSERT (Fixed)
```sql
INSERT INTO email_engagement (
    email_draft_id,
    event_type,
    event_timestamp,
    metadata
) VALUES (
    :email_draft_id,
    :event_type,  -- Must be: 'open', 'click', 'reply', 'high_intent_detected'
    :event_timestamp,
    :metadata::jsonb  -- Store open_count, first_opened_at, etc. in JSON
);
```

### ✅ CORRECT Python/SQLAlchemy Pattern
```python
from sqlalchemy import text
from datetime import datetime

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
            'open',
            :timestamp,
            :metadata::jsonb
        )
    """),
    {
        "email_draft_id": draft_id,
        "timestamp": datetime.now(),
        "metadata": json.dumps({
            "open_count": 1,
            "first_opened_at": datetime.now().isoformat(),
            "last_opened_at": datetime.now().isoformat(),
            "user_agent": request.headers.get("User-Agent"),
            "ip_address": request.client.host
        })
    }
)
```

### Schema Reference
```sql
CREATE TABLE email_engagement (
    id SERIAL PRIMARY KEY,
    email_draft_id INTEGER NOT NULL REFERENCES email_drafts(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('open', 'click', 'reply', 'high_intent_detected')),
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB,  -- Store additional data like open_count, IP, user_agent, etc.
    
    INDEX idx_email_draft_id (email_draft_id),
    INDEX idx_event_type (event_type),
    INDEX idx_event_timestamp (event_timestamp)
);
```

---

## Bug 2: email_drafts Table - Column Name Mismatches

### ❌ INCORRECT INSERT (Current - Will Fail)
```sql
INSERT INTO email_drafts (
    contact_id,
    subject_line,
    email_body,
    talking_points,
    created_at,
    status
) VALUES (...);
```

**Problem**: Column names don't match schema:
- `contact_id` → Should be `close_lead_id` or `close_contact_id`
- `subject_line` → Should be `subject`
- `email_body` → Should be `body_html`
- `talking_points` → Doesn't exist (should be in `research_context` JSON)
- `status` → Doesn't exist (use `sent_at` to determine status)

### ✅ CORRECT INSERT (Fixed)
```sql
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
);
```

### ✅ CORRECT Python/SQLAlchemy Pattern
```python
from sqlalchemy import text
from datetime import datetime
import json

# Create email draft
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
        "close_activity_id": activity_id,  # Optional
        "subject": "Subject line here",
        "body_html": "<html>Email body</html>",
        "research_context": json.dumps({
            "talking_points": ["Point 1", "Point 2", "Point 3"],
            "company_research": {...},
            "personalization_data": {...}
        }),
        "created_at": datetime.now()
    }
)
```

### Schema Reference
```sql
CREATE TABLE email_drafts (
    id SERIAL PRIMARY KEY,
    close_lead_id VARCHAR(255),  -- Close CRM lead ID
    close_contact_id VARCHAR(255),  -- Close CRM contact ID
    close_activity_id VARCHAR(255),  -- Close CRM activity ID (if sent)
    subject VARCHAR(500) NOT NULL,
    body_html TEXT NOT NULL,
    research_context JSONB,  -- Store talking_points, research data, etc.
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,  -- NULL = draft, NOT NULL = sent
    opens_count INTEGER DEFAULT 0,
    last_opened_at TIMESTAMP WITH TIME ZONE,
    
    INDEX idx_close_lead_id (close_lead_id),
    INDEX idx_close_contact_id (close_contact_id),
    INDEX idx_created_at (created_at),
    INDEX idx_sent_at (sent_at)
);
```

---

## Bug 3 & 4: social_posts Table - ON CONFLICT Without Unique Constraint

### ❌ INCORRECT INSERT (Current - Will Fail)
```sql
INSERT INTO social_posts (
    platform,
    post_url,
    company_name,
    ...
) VALUES (...)
ON CONFLICT (post_url) DO NOTHING;
```

**Problem**: `post_url` is not a UNIQUE constraint. PostgreSQL will raise error:
```
ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification
```

### ✅ SOLUTION A: Create Unique Constraint (Recommended)
```sql
-- Add unique constraint to post_url
ALTER TABLE social_posts 
ADD CONSTRAINT unique_post_url UNIQUE (post_url);

-- Now ON CONFLICT will work
INSERT INTO social_posts (
    platform,
    post_url,
    company_name,
    ...
) VALUES (...)
ON CONFLICT (post_url) DO NOTHING;
```

### ✅ SOLUTION B: Remove ON CONFLICT (If duplicates allowed)
```sql
-- Check if exists first, then insert
INSERT INTO social_posts (
    platform,
    post_url,
    company_name,
    ...
)
SELECT 
    :platform,
    :post_url,
    :company_name,
    ...
WHERE NOT EXISTS (
    SELECT 1 FROM social_posts 
    WHERE post_url = :post_url
);
```

### ✅ SOLUTION C: Use platform_post_id (If it's unique)
```sql
-- If platform_post_id is already unique, use that instead
INSERT INTO social_posts (
    platform,
    platform_post_id,
    post_url,
    company_name,
    ...
) VALUES (...)
ON CONFLICT (platform_post_id) DO NOTHING;
```

### ✅ CORRECT Python/SQLAlchemy Pattern
```python
from sqlalchemy import text

# Option 1: With unique constraint on post_url
db.execute(
    text("""
        INSERT INTO social_posts (
            platform,
            post_url,
            company_name,
            text_content,
            posted_at
        ) VALUES (
            :platform,
            :post_url,
            :company_name,
            :text_content,
            :posted_at
        )
        ON CONFLICT (post_url) DO NOTHING
    """),
    {
        "platform": "linkedin",
        "post_url": "https://linkedin.com/posts/...",
        "company_name": "TechCorp",
        "text_content": "Post content...",
        "posted_at": datetime.now()
    }
)

# Option 2: Check before insert (if no unique constraint)
result = db.execute(
    text("""
        SELECT id FROM social_posts 
        WHERE post_url = :post_url
    """),
    {"post_url": post_url}
).first()

if not result:
    db.execute(
        text("""
            INSERT INTO social_posts (
                platform,
                post_url,
                company_name,
                text_content,
                posted_at
            ) VALUES (
                :platform,
                :post_url,
                :company_name,
                :text_content,
                :posted_at
            )
        """),
        {...}
    )
```

### Schema Reference
```sql
CREATE TABLE social_posts (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    platform_post_id VARCHAR(255) UNIQUE,  -- Already has unique constraint
    post_url VARCHAR(1000),  -- Add unique constraint if needed
    company_name VARCHAR(255) NOT NULL,
    lead_id INTEGER REFERENCES leads(id),
    text_content TEXT,
    posted_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_platform (platform),
    INDEX idx_company_name (company_name),
    INDEX idx_posted_at (posted_at)
);

-- Add unique constraint for ON CONFLICT to work
ALTER TABLE social_posts 
ADD CONSTRAINT unique_post_url UNIQUE (post_url);
```

---

## Migration Scripts

### Fix email_engagement Table
```sql
-- Ensure CHECK constraint exists
ALTER TABLE email_engagement
ADD CONSTRAINT check_email_engagement_event_type 
CHECK (event_type IN ('open', 'click', 'reply', 'high_intent_detected'));
```

### Fix email_drafts Table
```sql
-- No migration needed - just use correct column names in INSERT statements
-- Verify schema matches:
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'email_drafts';
```

### Fix social_posts Table
```sql
-- Add unique constraint for ON CONFLICT
ALTER TABLE social_posts 
ADD CONSTRAINT unique_post_url UNIQUE (post_url);

-- Or if using platform_post_id (already unique):
-- No changes needed, just use ON CONFLICT (platform_post_id)
```

---

## Verification Queries

### Check email_engagement schema
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'email_engagement'
ORDER BY ordinal_position;
```

### Check email_drafts schema
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'email_drafts'
ORDER BY ordinal_position;
```

### Check social_posts constraints
```sql
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'social_posts'
AND constraint_type IN ('UNIQUE', 'PRIMARY KEY');
```

---

## Files to Update

When implementing these features, update these files:

1. **Email Engagement Service** (e.g., `backend/app/services/email_engagement_service.py`)
   - Use correct column names: `email_draft_id`, `event_type`, `event_timestamp`, `metadata`
   - Store open_count, timestamps in `metadata` JSONB field

2. **Email Drafts Service** (e.g., `backend/app/services/email_drafts_service.py`)
   - Use correct column names: `close_lead_id`, `close_contact_id`, `subject`, `body_html`
   - Store talking_points in `research_context` JSONB field

3. **Social Posts Service** (e.g., `backend/app/services/social_intelligence_service.py`)
   - Add unique constraint on `post_url` OR remove ON CONFLICT clause
   - Use `platform_post_id` for ON CONFLICT if it's already unique

4. **LinkedIn Scraper** (`backend/app/services/linkedin_scraper.py`)
   - Fix ON CONFLICT clause to use existing unique constraint or add one

---

## Summary

| Bug | Issue | Fix |
|-----|-------|-----|
| 1 | Wrong columns in email_engagement INSERT | Use `email_draft_id`, `event_type`, `event_timestamp`, `metadata` |
| 2 | Wrong columns in email_drafts INSERT | Use `close_lead_id`, `subject`, `body_html`, `research_context` |
| 3 | ON CONFLICT without unique constraint | Add `UNIQUE (post_url)` constraint OR remove ON CONFLICT |
| 4 | Same as Bug 3 in linkedin_scraper.py | Same fix as Bug 3 |

