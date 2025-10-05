-- Apply comprehensive database indexes migration (007)
-- This file contains all the index creation statements from the migration

-- ============================================================================
-- HIGH PRIORITY: Foreign Key Indexes
-- PostgreSQL does NOT automatically index foreign keys!
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_social_media_activity_lead_id
ON social_media_activity (lead_id);

CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_lead_id
ON contact_social_profiles (lead_id);

CREATE INDEX IF NOT EXISTS ix_organization_charts_lead_id
ON organization_charts (lead_id);

-- ============================================================================
-- MEDIUM PRIORITY: Timestamp and Status Columns
-- For time-range queries and status filtering
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_leads_qualified_at
ON leads (qualified_at DESC);

CREATE INDEX IF NOT EXISTS ix_leads_updated_at
ON leads (updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_executions_started_at
ON agent_executions (started_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_executions_completed_at
ON agent_executions (completed_at DESC);

CREATE INDEX IF NOT EXISTS ix_social_media_activity_posted_at
ON social_media_activity (posted_at DESC);

CREATE INDEX IF NOT EXISTS ix_social_media_activity_scraped_at
ON social_media_activity (scraped_at DESC);

CREATE INDEX IF NOT EXISTS ix_social_media_activity_sentiment
ON social_media_activity (sentiment);

CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_decision_maker_score
ON contact_social_profiles (decision_maker_score DESC);

CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_contact_priority
ON contact_social_profiles (contact_priority);

CREATE INDEX IF NOT EXISTS ix_voice_session_logs_completed_at
ON voice_session_logs (completed_at DESC);

-- ============================================================================
-- LOW PRIORITY: Composite Indexes for Advanced Query Patterns
-- Column order is critical: most selective column first
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_leads_score_created
ON leads (qualification_score DESC, created_at DESC)
WHERE qualification_score IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_agent_executions_status_created
ON agent_executions (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_executions_lead_status
ON agent_executions (lead_id, status);

CREATE INDEX IF NOT EXISTS ix_social_media_activity_platform_posted
ON social_media_activity (platform, posted_at DESC);

CREATE INDEX IF NOT EXISTS ix_contact_profiles_company_score
ON contact_social_profiles (company_name, decision_maker_score DESC);

CREATE INDEX IF NOT EXISTS ix_voice_sessions_status_created
ON voice_session_logs (status, created_at DESC);

-- Update alembic version
UPDATE alembic_version SET version_num = '007_comprehensive_indexes';
