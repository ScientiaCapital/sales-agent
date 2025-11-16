# Security Hardening & CSV Audit System Design

**Date**: 2025-01-16
**Author**: Security & CSV Management Design
**Status**: Approved - Ready for Implementation

## Purpose

Harden security before processing real customer data. Enable comprehensive audit of CSV imports and lead processing. Provide organized CSV file management with 30-day retention.

## Requirements

### Security
- Prevent API key exposure and leakage
- Protect lead data (PII: emails, phones, company info)
- Secure database connections and prevent SQL injection
- Validate environment configuration at startup

### CSV Management
- Organized folder structure for upload/processing/completion
- Track all CSV imports with row counts and costs
- Audit lead processing history
- 30-day retention with automatic archival

### Constraints
- Minimal approach: quick wins only (1-2 days implementation)
- No authentication system yet (file system access only)
- Manual backup and key rotation procedures
- Single-server deployment (no distributed systems)

## Architecture

### CSV Directory Structure

```
backend/data/csv/
├── inbox/              # Drop CSV files here
├── processing/         # Currently enriching
├── completed/          # Success (kept 30 days)
├── failed/             # Errors (kept 30 days)
└── archive/            # Auto-moved after 30 days
```

**File Workflow**:
1. User drops `leads.csv` in `inbox/`
2. System validates format, moves to `processing/`
3. Enrichment pipeline runs (qualification → enrichment → dedup → CRM)
4. Success: moves to `completed/` | Failure: moves to `failed/`
5. After 30 days: moves to `archive/` for cleanup

**File Naming Convention**:
- Original: `{timestamp}_{original_filename}.csv`
- Example: `20250116_143022_contractors.csv`
- Prevents overwrites, enables chronological sorting

### Audit Database Schema

**`csv_imports` Table**:
```sql
CREATE TABLE csv_imports (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- uploaded, processing, completed, failed, archived
    total_rows INTEGER NOT NULL,
    processed_rows INTEGER DEFAULT 0,
    failed_rows INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0.0,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_processing_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    archived_at TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_uploaded_at (uploaded_at)
);
```

**Audit Queries**:
```sql
-- Recent imports
SELECT filename, status, processed_rows, total_cost_usd
FROM csv_imports
WHERE uploaded_at > NOW() - INTERVAL '7 days'
ORDER BY uploaded_at DESC;

-- Monthly spend
SELECT SUM(total_cost_usd) AS total_spend
FROM csv_imports
WHERE uploaded_at >= DATE_TRUNC('month', NOW());

-- Failed imports
SELECT filename, error_message, uploaded_at
FROM csv_imports
WHERE status = 'failed'
ORDER BY uploaded_at DESC;
```

### API Key Security

**Environment Validation** (`backend/app/core/security.py`):
```python
REQUIRED_KEYS = [
    "OPENROUTER_API_KEY",
    "CEREBRAS_API_KEY",
    "HUNTER_API_KEY",
    "DATABASE_URL",
    "REDIS_URL"
]

def validate_environment():
    """Fail fast if required keys missing."""
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")
```

**Key Rotation Procedure** (documented in `docs/API_KEY_ROTATION.md`):
1. Generate new key from provider dashboard
2. Update `.env` file with new key
3. Restart application server
4. Verify functionality with test request
5. Revoke old key from provider
6. Document rotation date in changelog

**Rotation Schedule**: Every 90 days

### Database Security

**SQL Injection Prevention**:
- Use SQLAlchemy ORM (parameterized queries) - ✅ Already implemented
- Validate all inputs with Pydantic schemas - ✅ Already implemented
- Sanitize CSV filenames to prevent path traversal - **NEW**

**Filename Sanitization**:
```python
def sanitize_filename(filename: str) -> str:
    """Remove path traversal attempts and dangerous characters."""
    # Strip path components: "../../etc/passwd.csv" → "passwd.csv"
    safe_name = os.path.basename(filename)

    # Remove dangerous characters
    safe_name = safe_name.replace("..", "")

    # Allow only alphanumeric, dash, underscore, dot
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-")

    return safe_name
```

**Connection Pooling**:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,              # Max 5 concurrent connections
    max_overflow=10,          # Burst to 15 total
    pool_pre_ping=True,       # Verify before use
    pool_recycle=3600         # Recycle after 1 hour
)
```

**Backup Procedure** (documented in `docs/BACKUP_PROCEDURES.md`):
```bash
#!/bin/bash
# Daily backup script
DATE=$(date +%Y%m%d)
pg_dump sales_agent_db > /backups/sales_agent_${DATE}.sql
# Keep last 30 days
find /backups -name "sales_agent_*.sql" -mtime +30 -delete
```

### PII Protection

**Logging Policy**:
- ✅ Log lead IDs only (never emails, phones, names)
- ✅ Mask API keys in logs (show last 4 characters only)
- ✅ Sanitize error messages (no PII in exceptions)

**Example Logging**:
```python
# Bad: logger.info(f"Processing lead {email}")
# Good: logger.info(f"Processing lead_id={lead.id}")

# Bad: logger.error(f"API key {api_key} invalid")
# Good: logger.error(f"API key ending in {api_key[-4:]} invalid")
```

## Data Retention

**30-Day Automatic Archival**:
- Cleanup script runs daily at 2 AM UTC
- Moves files from `completed/` and `failed/` to `archive/` after 30 days
- Updates `csv_imports.status = 'archived'` and sets `archived_at`
- Does NOT delete - manual cleanup of `archive/` folder

**Retention Script** (`backend/scripts/cleanup_old_csvs.py`):
```python
def archive_old_files():
    """Move CSV files older than 30 days to archive."""
    cutoff_date = datetime.now() - timedelta(days=30)

    old_imports = db.query(CSVImport).filter(
        CSVImport.completed_at < cutoff_date,
        CSVImport.status.in_(['completed', 'failed'])
    ).all()

    for import_record in old_imports:
        # Move file to archive/
        old_path = import_record.file_path
        new_path = old_path.replace('/completed/', '/archive/').replace('/failed/', '/archive/')
        shutil.move(old_path, new_path)

        # Update database
        import_record.status = 'archived'
        import_record.archived_at = datetime.now()
        import_record.file_path = new_path

    db.commit()
```

**Cron Schedule**:
```cron
0 2 * * * cd /app/backend && python scripts/cleanup_old_csvs.py
```

## Implementation Tasks

### Task 1: CSV Directory Setup (30 min)
- Create folder structure: `backend/data/csv/{inbox,processing,completed,failed,archive}/`
- Add `.gitkeep` files (empty files to commit empty folders)
- Add `backend/data/csv/` to `.gitignore` (don't commit CSV files)

### Task 2: Database Migration (30 min)
- Create Alembic migration for `csv_imports` table
- Run migration: `alembic upgrade head`
- Verify table created: `psql -d sales_agent_db -c "\d csv_imports"`

### Task 3: Security Module (1 hour)
- Create `backend/app/core/security.py`
- Implement `validate_environment()`
- Add filename sanitization function
- Call validation in `main.py` startup

### Task 4: CSV Import Service (2 hours)
- Create `backend/app/services/csv_manager.py`
- Implement file upload handler
- Implement status transition logic (inbox → processing → completed/failed)
- Implement audit logging to `csv_imports` table

### Task 5: Retention Script (1 hour)
- Create `backend/scripts/cleanup_old_csvs.py`
- Test with sample old files
- Document cron setup in `docs/DEPLOYMENT.md`

### Task 6: Documentation (1 hour)
- Create `docs/API_KEY_ROTATION.md`
- Create `docs/BACKUP_PROCEDURES.md`
- Update `docs/CSV_IMPORT_GUIDE.md` with new workflow
- Add security section to main `README.md`

**Total Estimated Time**: 6-7 hours (1 working day)

## Testing Plan

### Manual Testing Checklist
- [ ] Drop CSV in `inbox/`, verify moves to `processing/`
- [ ] Check `csv_imports` table created and row inserted
- [ ] Verify successful processing moves file to `completed/`
- [ ] Verify failed processing moves file to `failed/`
- [ ] Test path traversal prevention: `../../etc/passwd.csv`
- [ ] Test environment validation: remove key, verify startup fails
- [ ] Run cleanup script, verify files move to `archive/` after 30 days

### Security Validation
- [ ] Confirm no API keys in logs
- [ ] Confirm no PII (emails/phones) in logs
- [ ] Verify `.env` in `.gitignore`
- [ ] Check database connection pooling limits
- [ ] Test SQL injection with malicious CSV values

## Success Criteria

### Security
- ✅ Server refuses to start if critical API keys missing
- ✅ All API keys loaded from environment only
- ✅ No hardcoded keys in codebase (verified by grep)
- ✅ Database connection pool limits enforced
- ✅ CSV filenames sanitized (no path traversal possible)

### CSV Management
- ✅ CSV files organized by status (inbox/processing/completed/failed/archive)
- ✅ All imports tracked in `csv_imports` table
- ✅ Row counts, costs, timestamps recorded
- ✅ Failed imports logged with error messages
- ✅ Files auto-archived after 30 days

### Audit & Compliance
- ✅ Query last 7 days of imports
- ✅ Calculate monthly AI spend
- ✅ Identify failed imports with errors
- ✅ Track costs per CSV batch
- ✅ No PII in application logs

## Future Enhancements (Out of Scope)

These improvements require more than 1-2 days and are deferred:

- **User Authentication**: OAuth/JWT for multi-user access
- **Encryption at Rest**: Encrypt CSV files and database
- **Automated Backups**: Scheduled pg_dump with cloud storage
- **Real-time Monitoring**: Grafana dashboards for costs and errors
- **Lead Change Tracking**: Detailed audit of field-level changes
- **Secrets Manager**: AWS Secrets Manager or HashiCorp Vault
- **Database Firewall**: Network-level access controls

These features can be added incrementally as the system scales.

## References

- Existing CSV import: `backend/app/services/csv_importer.py`
- Database models: `backend/app/models/lead.py`
- Alembic migrations: `backend/alembic/versions/`
- Environment config: `backend/app/core/config.py`
