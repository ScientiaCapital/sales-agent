# Bug Fixes Documentation

## Date: 2025-01-16

This document consolidates all bug fix information from the January 16, 2025 bug fix session.

---

## ✅ Bug 5: Async Methods with Synchronous Tweepy/PRAW Calls - FIXED

### Issue Found
The `SocialMediaScraper` class had synchronous methods (`search_twitter_mentions`, `search_reddit_mentions`) that made blocking API calls using `tweepy.Client` and `praw.Reddit`. These methods were being called from async contexts, which blocked the event loop.

### Solution Applied
1. **Added ThreadPoolExecutor** for running blocking calls in thread pool
2. **Created async methods**:
   - `search_twitter_mentions_async()`
   - `search_reddit_mentions_async()`
   - `scrape_company_social_async()`
3. **Updated call sites**:
   - `backend/app/api/contacts.py` - uses `scrape_company_social_async()`
   - `backend/app/services/langgraph/tools/social_media_tools.py` - uses async method
4. **Maintained backward compatibility** - original sync methods still work

### Files Modified
- `backend/app/services/social_media_scraper.py`
- `backend/app/api/contacts.py`
- `backend/app/services/langgraph/tools/social_media_tools.py`

### Implementation Pattern
```python
# Before (blocking)
async def endpoint():
    scraper = SocialMediaScraper()
    result = scraper.search_twitter_mentions(...)  # Blocks event loop!

# After (non-blocking)
async def endpoint():
    scraper = SocialMediaScraper()
    result = await scraper.search_twitter_mentions_async(...)  # Uses thread pool
```

---

## ✅ Bug 5 (Version Mismatch): FIXED

**Issue**: Version mismatch between `requirements.txt` and `venv_requirements.txt` for `anthropic` package.

**Fix**: Updated `backend/requirements.txt`:
- Changed: `anthropic==0.41.0`
- To: `anthropic==0.69.0` (aligned with `venv_requirements.txt`)

---

## ❌ Bugs NOT Found in Current Codebase

The following bugs were reported but **do not exist** in the current working branch. These are documented for reference when implementing future features:

### Bug 1 & 2: SQL INSERT with Wrong Column Names
- **Status**: Not found
- **Reason**: No `email_drafts` or `email_engagement` tables exist in current schema
- **When Implementing**: See SQL patterns below

### Bug 3: ON CONFLICT Without Unique Constraint
- **Status**: Not found
- **Reason**: No `social_posts` table with `ON CONFLICT (post_url)` in current code
- **When Implementing**: Add `UNIQUE (post_url)` constraint OR remove ON CONFLICT clause

### Bug 4: Duplicate Migration Files
- **Status**: Not found
- **Reason**: No duplicate `*social_intelligence*.py` migration files exist
- **Action**: Migration chain verified - all migrations have correct `down_revision` values

### Bug 6: Migration with `down_revision = None`
- **Status**: Not found
- **Reason**: Only the initial migration has `down_revision = None`, which is correct
- **Action**: Migration chain verified - all migrations properly linked

---

## SQL Schema Patterns (For Future Implementation)

When implementing `email_drafts` and `email_engagement` tables, use these correct patterns:

### email_drafts Table
```python
# CORRECT column names
INSERT INTO email_drafts (
    close_lead_id,
    close_contact_id,
    subject,              # NOT subject_line
    body_html,            # NOT email_body
    research_context,     # Store talking_points in JSONB here
    created_at
) VALUES (...)
# NO status column - use sent_at (NULL = draft, NOT NULL = sent)
```

### email_engagement Table
```python
# CORRECT column names
INSERT INTO email_engagement (
    email_draft_id,       # NOT email_id
    event_type,           # Must be: 'open', 'click', 'reply', 'high_intent_detected'
    event_timestamp,
    metadata              # Store open_count, first_opened_at, etc. in JSONB
) VALUES (...)
```

### social_posts Table (ON CONFLICT)
```sql
-- Option 1: Add unique constraint (recommended)
ALTER TABLE social_posts 
ADD CONSTRAINT unique_post_url UNIQUE (post_url);

-- Then ON CONFLICT will work:
INSERT INTO social_posts (...) VALUES (...)
ON CONFLICT (post_url) DO NOTHING;

-- Option 2: Check before insert (if duplicates allowed)
INSERT INTO social_posts (...)
SELECT ... WHERE NOT EXISTS (
    SELECT 1 FROM social_posts WHERE post_url = :post_url
);
```

---

## Verification Commands

```bash
# Verify async fix
grep -r "search_twitter_mentions_async\|scrape_company_social_async" backend/app/

# Verify no SQL bugs exist
grep -r "INSERT INTO email_drafts\|INSERT INTO email_engagement" backend/app/
# Should return no results

# Verify migration chain
cd backend && alembic history | head -20
```

---

## Status Summary

✅ **Fixed**: Bug 5 (async/sync), Bug 5 (version mismatch)  
❌ **Not Found**: Bugs 1-4, 6 (documented for future implementation)

