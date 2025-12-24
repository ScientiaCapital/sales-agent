-- Campaign Monitoring SQL Queries
-- For use in Supabase SQL Editor or psql
--
-- These queries help monitor the Dec 29 campaign launch
-- Source: docs/CAMPAIGN_MONITORING_DEC29.md

-- ============================================================================
-- CAMPAIGN OVERVIEW
-- ============================================================================

-- Total contacts enrolled in Close CRM
SELECT
    COUNT(*) as total_contacts,
    COUNT(CASE WHEN close_contact_id IS NOT NULL THEN 1 END) as enrolled_in_close,
    COUNT(CASE WHEN close_contact_id IS NULL THEN 1 END) as not_enrolled
FROM dim_contacts
WHERE created_at >= '2025-12-01';

-- Workflow distribution (by company keywords)
SELECT
    CASE
        WHEN co.name ILIKE '%solar%' OR co.name ILIKE '%sunkeeper%' OR co.name ILIKE '%altadena%'
            THEN 'Solar-Pivot-2026'
        ELSE 'ICP-Energy-Multitrade'
    END as workflow,
    COUNT(DISTINCT c.id) as contact_count,
    COUNT(DISTINCT c.close_contact_id) as enrolled_count
FROM dim_contacts c
JOIN dim_companies co ON c.company_id = co.id
WHERE c.created_at >= '2025-12-01'
GROUP BY workflow;

-- ============================================================================
-- DAILY ACTIVITY MONITORING
-- ============================================================================

-- Email activity summary for today
SELECT
    activity_date::date as date,
    activity_type,
    status,
    COUNT(*) as count
FROM fact_close_activities
WHERE activity_date::date = CURRENT_DATE
  AND activity_type = 'email'
GROUP BY activity_date::date, activity_type, status
ORDER BY status;

-- Email activity summary for date range (Week 1)
SELECT
    activity_date::date as date,
    COUNT(*) FILTER (WHERE status = 'sent') as sent,
    COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
    COUNT(*) FILTER (WHERE status = 'bounced') as bounced,
    COUNT(*) FILTER (WHERE status = 'opened') as opened,
    COUNT(*) FILTER (WHERE status = 'replied') as replied,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'delivered')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
        1
    ) as delivery_rate_pct
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'
GROUP BY activity_date::date
ORDER BY date;

-- ============================================================================
-- ENGAGEMENT METRICS
-- ============================================================================

-- Open rate by workflow (requires company join)
SELECT
    CASE
        WHEN co.name ILIKE '%solar%' THEN 'Solar-Pivot-2026'
        ELSE 'ICP-Energy-Multitrade'
    END as workflow,
    COUNT(*) FILTER (WHERE a.status IN ('sent', 'delivered', 'bounced')) as total_sent,
    COUNT(*) FILTER (WHERE a.status = 'delivered') as delivered,
    COUNT(*) FILTER (WHERE a.status = 'opened') as opened,
    COUNT(*) FILTER (WHERE a.status = 'replied') as replied,
    ROUND(
        COUNT(*) FILTER (WHERE a.status = 'opened')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE a.status = 'delivered'), 0) * 100,
        1
    ) as open_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE a.status = 'replied')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE a.status = 'delivered'), 0) * 100,
        1
    ) as reply_rate_pct
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
JOIN dim_companies co ON c.company_id = co.id
WHERE a.activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND a.activity_type = 'email'
GROUP BY workflow;

-- ============================================================================
-- HOT LEADS IDENTIFICATION
-- ============================================================================

-- Find hot leads (interested replies)
-- Note: Requires reply_classifier to populate intent field
SELECT
    c.name as contact_name,
    c.email,
    co.name as company_name,
    a.activity_date,
    a.notes as reply_text,
    a.metadata->>'intent' as reply_intent
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
JOIN dim_companies co ON c.company_id = co.id
WHERE a.activity_type = 'email'
  AND a.status = 'replied'
  AND a.activity_date::date >= '2025-12-29'
  AND (
      a.metadata->>'intent' = 'interested'
      OR a.metadata->>'intent' = 'meeting_request'
  )
ORDER BY a.activity_date DESC;

-- All replies (for manual review if intent not populated)
SELECT
    c.name as contact_name,
    c.email,
    co.name as company_name,
    a.activity_date,
    a.notes as reply_text,
    a.status
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
JOIN dim_companies co ON c.company_id = co.id
WHERE a.activity_type = 'email'
  AND a.status = 'replied'
  AND a.activity_date::date >= '2025-12-29'
ORDER BY a.activity_date DESC;

-- ============================================================================
-- DELIVERY HEALTH CHECKS
-- ============================================================================

-- Bounce rate analysis
SELECT
    activity_date::date as date,
    COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')) as total_sent,
    COUNT(*) FILTER (WHERE status = 'bounced') as bounced,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'bounced')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
        1
    ) as bounce_rate_pct,
    CASE
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'bounced')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
            1
        ) < 5 THEN '🟢 Green'
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'bounced')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
            1
        ) < 10 THEN '🟡 Yellow'
        ELSE '🔴 Red'
    END as health_status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'
GROUP BY activity_date::date
ORDER BY date;

-- Unsubscribe tracking
SELECT
    activity_date::date as date,
    COUNT(*) as unsubscribe_count,
    ROUND(
        COUNT(*)::numeric /
        (SELECT COUNT(*) FROM dim_contacts WHERE close_contact_id IS NOT NULL)
        * 100,
        2
    ) as unsubscribe_rate_pct
FROM fact_close_activities
WHERE activity_type = 'unsubscribe'
  AND activity_date::date >= '2025-12-29'
GROUP BY activity_date::date
ORDER BY date;

-- ============================================================================
-- SEQUENCE HEALTH (if sequence subscriptions synced to Supabase)
-- ============================================================================

-- Note: This assumes you have a sequences table syncing Close subscriptions
-- If not, use the Close CRM API directly via campaign_health_check.py

-- Active vs stopped sequences (if synced)
-- SELECT
--     status,
--     COUNT(*) as count,
--     ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM sequence_subscriptions) * 100, 1) as pct
-- FROM sequence_subscriptions
-- WHERE created_at >= '2025-12-01'
-- GROUP BY status;

-- ============================================================================
-- WEEK 1 SUMMARY (Run on Jan 5, 2026)
-- ============================================================================

-- Complete Week 1 metrics
SELECT
    'Total Sent' as metric,
    COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced'))::text as value,
    '' as target,
    '' as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Total Delivered' as metric,
    COUNT(*) FILTER (WHERE status = 'delivered')::text as value,
    '>1078 (95%)' as target,
    CASE
        WHEN COUNT(*) FILTER (WHERE status = 'delivered') > 1078 THEN '✅'
        WHEN COUNT(*) FILTER (WHERE status = 'delivered') > 1020 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Delivery Rate' as metric,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'delivered')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
        1
    )::text || '%' as value,
    '>95%' as target,
    CASE
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'delivered')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
            1
        ) >= 95 THEN '✅'
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'delivered')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')), 0) * 100,
            1
        ) >= 90 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Total Bounced' as metric,
    COUNT(*) FILTER (WHERE status = 'bounced')::text as value,
    '<57 (5%)' as target,
    CASE
        WHEN COUNT(*) FILTER (WHERE status = 'bounced') < 57 THEN '✅'
        WHEN COUNT(*) FILTER (WHERE status = 'bounced') < 113 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Total Opened' as metric,
    COUNT(*) FILTER (WHERE status = 'opened')::text as value,
    '170-269 (15-25%)' as target,
    CASE
        WHEN COUNT(*) FILTER (WHERE status = 'opened') >= 170 THEN '✅'
        WHEN COUNT(*) FILTER (WHERE status = 'opened') >= 100 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Open Rate' as metric,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'opened')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
        1
    )::text || '%' as value,
    '15-25%' as target,
    CASE
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'opened')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
            1
        ) >= 15 THEN '✅'
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'opened')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
            1
        ) >= 10 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Total Replied' as metric,
    COUNT(*) FILTER (WHERE status = 'replied')::text as value,
    '22-54 (2-5%)' as target,
    CASE
        WHEN COUNT(*) FILTER (WHERE status = 'replied') >= 22 THEN '✅'
        WHEN COUNT(*) FILTER (WHERE status = 'replied') >= 11 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email'

UNION ALL

SELECT
    'Reply Rate' as metric,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'replied')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
        1
    )::text || '%' as value,
    '2-5%' as target,
    CASE
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'replied')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
            1
        ) >= 2 THEN '✅'
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'replied')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status = 'delivered'), 0) * 100,
            1
        ) >= 1 THEN '⚠️'
        ELSE '❌'
    END as status
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email';

-- ============================================================================
-- CONTACT QUALITY CHECK
-- ============================================================================

-- Verify no duplicate contacts enrolled
SELECT
    email,
    COUNT(*) as count
FROM dim_contacts
WHERE close_contact_id IS NOT NULL
GROUP BY email
HAVING COUNT(*) > 1;

-- Companies with multiple contacts enrolled (should be normal)
SELECT
    co.name as company_name,
    COUNT(c.id) as contact_count,
    STRING_AGG(c.name, ', ') as contacts
FROM dim_companies co
JOIN dim_contacts c ON co.id = c.company_id
WHERE c.close_contact_id IS NOT NULL
GROUP BY co.name
HAVING COUNT(c.id) > 1
ORDER BY COUNT(c.id) DESC
LIMIT 20;

-- ============================================================================
-- TROUBLESHOOTING QUERIES
-- ============================================================================

-- Find contacts with no activity (might indicate enrollment issue)
SELECT
    c.name,
    c.email,
    co.name as company_name,
    c.close_contact_id,
    c.created_at
FROM dim_contacts c
JOIN dim_companies co ON c.company_id = co.id
WHERE c.close_contact_id IS NOT NULL
  AND c.created_at >= '2025-12-01'
  AND NOT EXISTS (
      SELECT 1
      FROM fact_close_activities a
      WHERE a.contact_id = c.close_contact_id
  )
ORDER BY c.created_at DESC;

-- Check for suspicious bounce patterns (same domain bouncing)
SELECT
    SUBSTRING(c.email FROM '@(.*)$') as domain,
    COUNT(*) as bounce_count,
    ROUND(
        COUNT(*)::numeric /
        (SELECT COUNT(*) FROM dim_contacts WHERE email LIKE '%' || SUBSTRING(c.email FROM '@(.*)$')) * 100,
        1
    ) as domain_bounce_rate_pct
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
WHERE a.status = 'bounced'
  AND a.activity_date::date >= '2025-12-29'
GROUP BY domain
HAVING COUNT(*) >= 3
ORDER BY bounce_count DESC;
