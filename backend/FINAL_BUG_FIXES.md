# Final Bug Fixes - All 6 Critical Issues

## Date: 2025-01-16

This document provides complete fixes for all 6 reported bugs: SQL INSERT statements, migration conflicts, async/sync issues, and migration chain problems.

---

## Bug 1: email_drafts INSERT - Wrong Column Names

### ❌ INCORRECT CODE
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
        ) VALUES (...)
    """)
)
```

**Error**: `column "contact_id" does not exist`, `column "subject_line" does not exist`, etc.

### ✅ CORRECT CODE
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
        "close_activity_id": activity_id,  # Optional
        "subject": "Subject line here",  # NOT subject_line
        "body_html": "<html>Email body</html>",  # NOT email_body
        "research_context": json.dumps({
            "talking_points": ["Point 1", "Point 2"],  # Store in JSON
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
- `talking_points` → Store in `research_context` JSONB
- `status` → Use `sent_at` (NULL = draft, NOT NULL = sent)

---

## Bug 2: email_engagement INSERT - Wrong Column Names

### ❌ INCORRECT CODE
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
        ) VALUES (...)
    """)
)
```

**Error**: `column "email_id" does not exist`, `column "contact_id" does not exist`, etc.

### ✅ CORRECT CODE
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
            "open_count": 1,  # Store in metadata
            "first_opened_at": datetime.now().isoformat(),
            "last_opened_at": datetime.now().isoformat(),
            "checked_at": datetime.now().isoformat(),
            "user_agent": request.headers.get("User-Agent"),
            "ip_address": request.client.host
        })
    }
)
```

**Column Mapping**:
- `email_id` → `email_draft_id`
- `contact_id` → Remove (not needed)
- `open_count` → Store in `metadata` JSONB
- `first_opened_at` → Store in `metadata` JSONB
- `last_opened_at` → Store in `metadata` JSONB
- `checked_at` → Store in `metadata` JSONB

---

## Bug 3: ON CONFLICT Without Unique Constraint

### ❌ INCORRECT CODE
```python
# WRONG - post_url is not a unique constraint
db.execute(
    text("""
        INSERT INTO social_posts (
            platform,
            post_url,
            company_name,
            text_content,
            posted_at
        ) VALUES (...)
        ON CONFLICT (post_url) DO NOTHING
    """)
)
```

**Error**: `there is no unique or exclusion constraint matching the ON CONFLICT specification`

### ✅ SOLUTION A: Add Unique Constraint (Recommended)
```sql
-- Migration to add unique constraint
ALTER TABLE social_posts 
ADD CONSTRAINT unique_post_url UNIQUE (post_url);
```

Then the ON CONFLICT will work:
```python
db.execute(
    text("""
        INSERT INTO social_posts (
            platform,
            post_url,
            company_name,
            text_content,
            posted_at
        ) VALUES (...)
        ON CONFLICT (post_url) DO NOTHING
    """)
)
```

### ✅ SOLUTION B: Remove ON CONFLICT and Check First
```python
from sqlalchemy import text

# Check if exists first
result = db.execute(
    text("SELECT id FROM social_posts WHERE post_url = :post_url"),
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

### ✅ SOLUTION C: Use Existing Unique Constraint
If `platform_post_id` is already unique:
```python
db.execute(
    text("""
        INSERT INTO social_posts (
            platform,
            platform_post_id,
            post_url,
            company_name,
            text_content,
            posted_at
        ) VALUES (...)
        ON CONFLICT (platform_post_id) DO NOTHING
    """)
)
```

---

## Bug 4: Duplicate Migration Files

### ❌ PROBLEM
Two migration files create the same tables:
- `014_add_social_intelligence_tables.py` (Revision ID: `014_social_intelligence`)
- `2025_11_17_social_intelligence_schema.py` (Revision ID: `2025_11_17_social_intelligence`)

Both create `email_drafts` and `email_engagement` tables, causing:
- Migration conflicts
- Schema ambiguity
- Potential data inconsistency

### ✅ SOLUTION

**Step 1: Check Current Migration State**
```bash
cd backend
alembic current
alembic history --verbose
```

**Step 2: Determine Which Migration to Keep**

If `014_add_social_intelligence_tables.py` has CHECK constraint (correct):
- Keep: `014_add_social_intelligence_tables.py`
- Delete: `2025_11_17_social_intelligence_schema.py`

If `2025_11_17_social_intelligence_schema.py` is more complete:
- Keep: `2025_11_17_social_intelligence_schema.py`
- Delete: `014_add_social_intelligence_tables.py`
- Ensure CHECK constraint is added to the kept migration

**Step 3: Delete Duplicate**
```bash
# If keeping 014, delete 2025_11_17
rm backend/alembic/versions/2025_11_17_social_intelligence_schema.py

# OR if keeping 2025_11_17, delete 014
rm backend/alembic/versions/014_add_social_intelligence_tables.py
```

**Step 4: Verify Migration Chain**
```bash
alembic history --verbose
# Ensure no broken links
```

**Step 5: If One Already Applied**
If a migration was already applied to production:
1. **DO NOT DELETE** the applied migration
2. Delete the duplicate that hasn't been applied
3. If schemas differ, create a new migration to align them

---

## Bug 5: Async Methods Using Synchronous Tweepy Calls

### ❌ INCORRECT CODE
```python
# WRONG - async method with blocking synchronous call
async def search_twitter_mentions(
    self,
    company_name: str,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    # This blocks the event loop!
    response = self.twitter_client.search_recent_tweets(
        query=query,
        max_results=max_results
    )
    return tweets
```

**Problem**: Synchronous `tweepy.Client` calls block the async event loop, defeating the purpose of async code.

### ✅ SOLUTION A: Use Executor (Recommended)
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class SocialMediaScraper:
    def __init__(self):
        self.twitter_client = self._init_twitter_client()
        self.executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for sync calls
    
    async def search_twitter_mentions(
        self,
        company_name: str,
        max_results: int = 100,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """Search Twitter for company mentions (non-blocking)"""
        if not self.twitter_client:
            raise HTTPException(
                status_code=501,
                detail="Twitter scraping not configured"
            )
        
        query = f'"{company_name}" -is:retweet lang:en'
        start_time = datetime.utcnow() - timedelta(days=days_back)
        
        # Run synchronous tweepy call in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            self.executor,
            lambda: self.twitter_client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                start_time=start_time,
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
                user_fields=['username', 'name', 'verified']
            )
        )
        
        if not response.data:
            return []
        
        tweets = []
        for tweet in response.data:
            tweets.append({
                "id": tweet.id,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                "metrics": {
                    "retweets": tweet.public_metrics.get('retweet_count', 0),
                    "likes": tweet.public_metrics.get('like_count', 0),
                    "replies": tweet.public_metrics.get('reply_count', 0)
                },
                "platform": "twitter"
            })
        
        return tweets
```

### ✅ SOLUTION B: Make Methods Synchronous
If the methods don't need to be async:
```python
# Remove async - make it synchronous
def search_twitter_mentions(
    self,
    company_name: str,
    max_results: int = 100,
    days_back: int = 7
) -> List[Dict[str, Any]]:
    """Search Twitter for company mentions (synchronous)"""
    if not self.twitter_client:
        raise HTTPException(
            status_code=501,
            detail="Twitter scraping not configured"
        )
    
    # Synchronous call is fine in sync method
    response = self.twitter_client.search_recent_tweets(
        query=query,
        max_results=min(max_results, 100),
        start_time=start_time,
        tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
        user_fields=['username', 'name', 'verified']
    )
    
    # ... rest of code
```

**Recommendation**: Use Solution A (executor) if the methods are called from async contexts. Use Solution B if they're only called from sync contexts.

---

## Bug 6: Migration with down_revision = None and Comment

### ❌ INCORRECT CODE
```python
# WRONG - down_revision = None with comment
revision: str = '2025_11_17_social_intelligence'
down_revision: Union[str, None] = None  # Update this to latest migration if others exist
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Problem**: 
- Creates ambiguity in migration chain
- Doesn't properly link to previous migration
- Comment suggests it's a placeholder, not production-ready

### ✅ SOLUTION

**Option 1: Set Correct down_revision**
```python
# Check what the latest migration is
# alembic history --verbose

# Then set correct down_revision
revision: str = '2025_11_17_social_intelligence'
down_revision: Union[str, None] = '2ebd5747346c'  # Or whatever the latest migration ID is
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Option 2: Delete If Duplicate**
If this migration is a duplicate of `014_add_social_intelligence_tables.py`:
```bash
# Delete the duplicate
rm backend/alembic/versions/2025_11_17_social_intelligence_schema.py

# Keep only 014_add_social_intelligence_tables.py
# Ensure it has correct down_revision
```

**Option 3: Merge Migrations**
If both migrations have unique changes:
1. Keep the one with correct `down_revision`
2. Manually merge any unique changes from the other
3. Delete the duplicate

**Correct Migration Pattern**:
```python
"""Add social intelligence tables

Revision ID: 014_social_intelligence
Revises: 013_document_analysis  # MUST reference previous migration
Create Date: 2025-11-17
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '014_social_intelligence'
down_revision: Union[str, None] = '013_document_analysis'  # Specific revision ID
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create tables with CHECK constraints
    op.create_table(
        'email_engagement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_draft_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['email_draft_id'], ['email_drafts.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "event_type IN ('open', 'click', 'reply', 'high_intent_detected')",
            name='check_email_engagement_event_type'
        )
    )
    # ... create indexes
    op.create_index('idx_email_engagement_email_draft_id', 'email_engagement', ['email_draft_id'])
    op.create_index('idx_email_engagement_event_type', 'email_engagement', ['event_type'])
    op.create_index('idx_email_engagement_event_timestamp', 'email_engagement', ['event_timestamp'])

def downgrade() -> None:
    # Drop indexes FIRST (before dropping tables)
    op.drop_index('idx_email_engagement_event_timestamp', table_name='email_engagement')
    op.drop_index('idx_email_engagement_event_type', table_name='email_engagement')
    op.drop_index('idx_email_engagement_email_draft_id', table_name='email_engagement')
    
    # Drop CHECK constraint
    op.drop_constraint('check_email_engagement_event_type', table_name='email_engagement', type_='check')
    
    # Drop tables
    op.drop_table('email_engagement')
    op.drop_table('email_drafts')
```

---

## Verification Checklist

### SQL INSERT Fixes
- [ ] Search for `INSERT INTO email_drafts` - verify column names
- [ ] Search for `INSERT INTO email_engagement` - verify column names
- [ ] Test INSERT statements in development database
- [ ] Verify JSONB metadata storage works

### ON CONFLICT Fix
- [ ] Check if `post_url` has unique constraint: `\d social_posts` in psql
- [ ] Add constraint OR remove ON CONFLICT clause
- [ ] Test duplicate insert handling

### Migration Fixes
- [ ] Check for duplicate migrations: `ls -la alembic/versions/*social_intelligence*`
- [ ] Verify only one migration creates `email_drafts` and `email_engagement`
- [ ] Check `down_revision` values are correct (not None unless initial migration)
- [ ] Verify `downgrade()` functions drop all indexes and constraints
- [ ] Test migration rollback: `alembic downgrade -1`

### Async/Sync Fixes
- [ ] Find async methods using tweepy: `grep -r "async def.*tweepy" backend/`
- [ ] Wrap sync calls in executor OR make methods synchronous
- [ ] Test async methods don't block event loop

---

## Files to Check/Update

1. **Email Drafts Service** (e.g., `backend/app/services/email_drafts_service.py`)
   - Fix INSERT column names
   - Use `close_lead_id`, `subject`, `body_html`, `research_context`

2. **Email Engagement Service** (e.g., `backend/app/services/email_engagement_service.py`)
   - Fix INSERT column names
   - Use `email_draft_id`, `event_type`, `event_timestamp`, `metadata`

3. **Social Posts Service** (e.g., `backend/app/services/social_intelligence_service.py`)
   - Fix ON CONFLICT clause
   - Add unique constraint OR remove ON CONFLICT

4. **Social Media Scraper** (`backend/app/services/social_media_scraper.py`)
   - Fix async methods using tweepy
   - Wrap in executor OR make synchronous

5. **Migration Files**:
   - `backend/alembic/versions/014_add_social_intelligence_tables.py` - Verify down_revision
   - `backend/alembic/versions/2025_11_17_social_intelligence_schema.py` - Delete if duplicate

---

## Quick Fix Commands

```bash
# 1. Find files with wrong INSERT statements
cd backend
grep -r "INSERT INTO email_drafts" --include="*.py"
grep -r "INSERT INTO email_engagement" --include="*.py"

# 2. Find ON CONFLICT issues
grep -r "ON CONFLICT.*post_url" --include="*.py"

# 3. Check for duplicate migrations
ls -la alembic/versions/*social_intelligence*

# 4. Check migration down_revision values
grep -r "down_revision.*None" alembic/versions/

# 5. Find async methods with tweepy
grep -r "async def.*tweepy\|tweepy.*Client" --include="*.py"

# 6. Verify migration chain
alembic history --verbose
```

---

## Summary

| Bug | Issue | Fix |
|-----|-------|-----|
| 1 | email_drafts INSERT wrong columns | Use `close_lead_id`, `subject`, `body_html`, `research_context` |
| 2 | email_engagement INSERT wrong columns | Use `email_draft_id`, `event_type`, `event_timestamp`, `metadata` |
| 3 | ON CONFLICT without unique constraint | Add `UNIQUE (post_url)` OR remove ON CONFLICT |
| 4 | Duplicate migration files | Delete duplicate, keep one with CHECK constraint |
| 5 | Async methods with sync tweepy | Wrap in executor OR make methods synchronous |
| 6 | Migration down_revision = None | Set correct down_revision OR delete if duplicate |

---

## Next Steps

1. **Locate Files**: Find the actual implementation files (may be in uncommitted changes or different branch)
2. **Apply Fixes**: Use the correct code patterns from this document
3. **Test**: Verify all fixes work in development environment
4. **Verify Migrations**: Ensure migration chain is correct and no duplicates exist
