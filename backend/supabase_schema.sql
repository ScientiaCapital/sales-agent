-- Social Intelligence Database Schema for Supabase
-- Run this in Supabase SQL Editor: https://app.supabase.com/project/YOUR_PROJECT/sql

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Table: social_posts
-- Stores LinkedIn/Twitter posts with AI analysis
-- =============================================================================
CREATE TABLE IF NOT EXISTS social_posts (
    id SERIAL PRIMARY KEY,
    contact_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('linkedin', 'twitter')),
    post_text TEXT,
    post_url VARCHAR(500),
    posted_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    ai_analysis JSONB,  -- Stores: pain_points, urgency, talking_points, business_impact
    quality_score INTEGER CHECK (quality_score >= 1 AND quality_score <= 10)
);

-- Indexes for social_posts
CREATE INDEX idx_social_posts_contact ON social_posts(contact_id);
CREATE INDEX idx_social_posts_scraped ON social_posts(scraped_at DESC);
CREATE INDEX idx_social_posts_platform ON social_posts(platform);
CREATE INDEX idx_social_posts_quality ON social_posts(quality_score DESC);

COMMENT ON TABLE social_posts IS 'LinkedIn and Twitter posts from monitored contacts';
COMMENT ON COLUMN social_posts.ai_analysis IS 'AI-extracted context: pain points, urgency, talking points';
COMMENT ON COLUMN social_posts.quality_score IS '1-10 quality score from AI (7+ = email draft worthy)';

-- =============================================================================
-- Table: contact_monitoring
-- Tracks which contacts are being monitored and their status
-- =============================================================================
CREATE TABLE IF NOT EXISTS contact_monitoring (
    id SERIAL PRIMARY KEY,
    close_contact_id VARCHAR(255) UNIQUE NOT NULL,
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),
    last_linkedin_check TIMESTAMPTZ,
    last_twitter_check TIMESTAMPTZ,
    monitoring_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    total_posts_found INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for contact_monitoring
CREATE INDEX idx_contact_monitoring_enabled ON contact_monitoring(monitoring_enabled) WHERE monitoring_enabled = TRUE;
CREATE INDEX idx_contact_monitoring_last_check ON contact_monitoring(last_linkedin_check DESC);

COMMENT ON TABLE contact_monitoring IS 'Contact monitoring status and social media URLs';
COMMENT ON COLUMN contact_monitoring.close_contact_id IS 'Close CRM contact ID';

-- =============================================================================
-- Table: email_drafts
-- Email drafts created by AI and sent via Close CRM
-- =============================================================================
CREATE TABLE IF NOT EXISTS email_drafts (
    id SERIAL PRIMARY KEY,
    close_lead_id VARCHAR(255) NOT NULL,
    close_contact_id VARCHAR(255) NOT NULL,
    close_activity_id VARCHAR(255),  -- Close CRM Email Activity ID
    subject VARCHAR(500),
    body_html TEXT,
    research_context TEXT,  -- LinkedIn/Twitter context that triggered this email
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    sent_at TIMESTAMPTZ,
    opens_count INTEGER DEFAULT 0 NOT NULL,
    last_opened_at TIMESTAMPTZ
);

-- Indexes for email_drafts
CREATE INDEX idx_email_drafts_lead ON email_drafts(close_lead_id);
CREATE INDEX idx_email_drafts_contact ON email_drafts(close_contact_id);
CREATE INDEX idx_email_drafts_opens ON email_drafts(opens_count DESC);
CREATE INDEX idx_email_drafts_created ON email_drafts(created_at DESC);
CREATE INDEX idx_email_drafts_sent ON email_drafts(sent_at DESC);

COMMENT ON TABLE email_drafts IS 'AI-generated email drafts with engagement tracking';
COMMENT ON COLUMN email_drafts.research_context IS 'Social media insights that triggered this email';
COMMENT ON COLUMN email_drafts.opens_count IS 'Number of times email was opened (3+ = high intent)';

-- =============================================================================
-- Table: email_engagement
-- Detailed email engagement events (opens, clicks, replies)
-- =============================================================================
CREATE TABLE IF NOT EXISTS email_engagement (
    id SERIAL PRIMARY KEY,
    email_draft_id INTEGER NOT NULL REFERENCES email_drafts(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('open', 'click', 'reply', 'high_intent_detected')),
    event_timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    metadata JSONB  -- Additional event data (IP, device, etc.)
);

-- Indexes for email_engagement
CREATE INDEX idx_email_engagement_draft ON email_engagement(email_draft_id);
CREATE INDEX idx_email_engagement_timestamp ON email_engagement(event_timestamp DESC);
CREATE INDEX idx_email_engagement_type ON email_engagement(event_type);

COMMENT ON TABLE email_engagement IS 'Detailed email engagement tracking';
COMMENT ON COLUMN email_engagement.event_type IS 'open, click, reply, or high_intent_detected';

-- =============================================================================
-- Triggers: Auto-update timestamps
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_contact_monitoring_updated_at BEFORE UPDATE ON contact_monitoring
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Views: Analytics queries
-- =============================================================================

-- View: High-intent contacts (3+ email opens in last 7 days)
CREATE OR REPLACE VIEW high_intent_contacts AS
SELECT
    ed.close_contact_id,
    ed.close_lead_id,
    ed.subject,
    ed.opens_count,
    ed.last_opened_at,
    ed.sent_at,
    EXTRACT(EPOCH FROM (ed.last_opened_at - ed.sent_at)) / 3600 AS hours_since_sent
FROM email_drafts ed
WHERE
    ed.opens_count >= 3
    AND ed.sent_at > NOW() - INTERVAL '7 days'
ORDER BY ed.opens_count DESC, ed.last_opened_at DESC;

COMMENT ON VIEW high_intent_contacts IS 'Contacts with 3+ email opens in last 7 days (high buying intent)';

-- View: Daily social intelligence summary
CREATE OR REPLACE VIEW daily_social_summary AS
SELECT
    DATE(scraped_at) AS date,
    platform,
    COUNT(*) AS posts_found,
    COUNT(*) FILTER (WHERE quality_score >= 7) AS high_quality_posts,
    AVG(quality_score) AS avg_quality_score
FROM social_posts
WHERE scraped_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(scraped_at), platform
ORDER BY date DESC, platform;

COMMENT ON VIEW daily_social_summary IS 'Daily summary of social posts scraped by platform';

-- =============================================================================
-- Sample Data (for testing)
-- =============================================================================

-- Insert sample contact monitoring (replace with real Close CRM contact IDs)
INSERT INTO contact_monitoring (close_contact_id, linkedin_url, twitter_handle, monitoring_enabled)
VALUES
    ('cont_sample123', 'https://linkedin.com/in/sampleuser', '@sampleuser', TRUE)
ON CONFLICT (close_contact_id) DO NOTHING;

-- Verify tables created successfully
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
    AND table_name IN ('social_posts', 'contact_monitoring', 'email_drafts', 'email_engagement')
ORDER BY table_name;

-- Show table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN ('social_posts', 'contact_monitoring', 'email_drafts', 'email_engagement')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
