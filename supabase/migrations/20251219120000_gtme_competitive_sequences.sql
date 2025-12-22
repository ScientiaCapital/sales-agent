-- Coperniq Competitive Battle Card Sequences for Close CRM
-- Created: 2025-12-19
-- Purpose: GTME sequences for frontline sales when competitors are mentioned

-- Insert competitive battle card sequences
INSERT INTO dim_gtme_sequences (name, description, trigger_type, target_segment, is_active, created_at)
VALUES
  ('vs_servicetitan', 'Battle card sequence when ServiceTitan is mentioned', 'competitor_mention', 'servicetitan_evaluators', true, NOW()),
  ('vs_procore', 'Battle card sequence when Procore is mentioned', 'competitor_mention', 'procore_evaluators', true, NOW()),
  ('vs_buildops', 'Battle card sequence when BuildOps is mentioned', 'competitor_mention', 'buildops_evaluators', true, NOW()),
  ('vs_buildertrend', 'Battle card sequence when Buildertrend is mentioned', 'competitor_mention', 'buildertrend_evaluators', true, NOW()),
  ('coperniq_differentiators', 'General competitive differentiation for all prospects', 'qualification', 'all_qualified', true, NOW())
ON CONFLICT (name) DO UPDATE SET
  description = EXCLUDED.description,
  trigger_type = EXCLUDED.trigger_type,
  target_segment = EXCLUDED.target_segment,
  is_active = EXCLUDED.is_active;

-- Insert competitive scripts
INSERT INTO dim_gtme_scripts (name, description, script_type, content, tags, is_active, created_at)
VALUES
  -- ServiceTitan Battle Scripts
  ('servicetitan_opener', 'Opening when ServiceTitan mentioned', 'objection_handler',
   'ServiceTitan is great for pure service companies. But you install equipment AND maintain it, right? Let me show you what happens after installation...',
   ARRAY['servicetitan', 'competitor', 'opener'], true, NOW()),

  ('servicetitan_killer_question', 'Killer question for ServiceTitan prospects', 'discovery_question',
   'When a solar system starts underperforming, how does ServiceTitan alert you? (Answer: It doesn''t. You find out when the customer calls angry.)',
   ARRAY['servicetitan', 'competitor', 'killer_question'], true, NOW()),

  ('servicetitan_asset_tracking', 'Asset tracking differentiator vs ServiceTitan', 'value_prop',
   'In ServiceTitan, when a job closes, the record goes cold. In Coperniq, the ASSET lives on - you track production, service history, and O&M billing forever.',
   ARRAY['servicetitan', 'competitor', 'asset_lifecycle'], true, NOW()),

  ('servicetitan_energy_monitoring', 'Energy monitoring differentiator vs ServiceTitan', 'value_prop',
   'ServiceTitan can''t show you real-time kWh production. Coperniq shows you which systems are underperforming BEFORE your customer calls.',
   ARRAY['servicetitan', 'competitor', 'monitoring'], true, NOW()),

  -- Procore Battle Scripts
  ('procore_opener', 'Opening when Procore mentioned', 'objection_handler',
   'Procore is built for general contractors managing subs. You''re self-performing with your own crews, right? And you do service after install?',
   ARRAY['procore', 'competitor', 'opener'], true, NOW()),

  ('procore_killer_question', 'Killer question for Procore prospects', 'discovery_question',
   'When you need to service equipment you installed 2 years ago, how do you find that info in Procore? (Answer: Search through old projects, exports, or the customer calls you.)',
   ARRAY['procore', 'competitor', 'killer_question'], true, NOW()),

  ('procore_self_perform', 'Self-performing differentiator vs Procore', 'value_prop',
   'Procore assumes you''re coordinating subs. Coperniq is built for contractors with their own crews who need mobile field ops.',
   ARRAY['procore', 'competitor', 'self_perform'], true, NOW()),

  ('procore_price', 'Price differentiator vs Procore', 'value_prop',
   'Procore is $500+/user. How big is your team? We''re significantly more affordable for MEP contractors - typically 30-50% less.',
   ARRAY['procore', 'competitor', 'pricing'], true, NOW()),

  -- BuildOps Battle Scripts
  ('buildops_opener', 'Opening when BuildOps mentioned', 'objection_handler',
   'BuildOps is solid for commercial service. But do you also do installations? And do you need ongoing asset monitoring?',
   ARRAY['buildops', 'competitor', 'opener'], true, NOW()),

  ('buildops_killer_question', 'Killer question for BuildOps prospects', 'discovery_question',
   'How do you track system performance over time in BuildOps? (Answer: You don''t - no energy monitoring.)',
   ARRAY['buildops', 'competitor', 'killer_question'], true, NOW()),

  -- Buildertrend Battle Scripts
  ('buildertrend_opener', 'Opening when Buildertrend mentioned', 'objection_handler',
   'Buildertrend is great for residential construction. But do you service what you install? Do you have ongoing maintenance contracts?',
   ARRAY['buildertrend', 'competitor', 'opener'], true, NOW()),

  ('buildertrend_killer_question', 'Killer question for Buildertrend prospects', 'discovery_question',
   'After you finish a solar install in Buildertrend, how do you track the system''s performance for the next 25 years? (Answer: You don''t.)',
   ARRAY['buildertrend', 'competitor', 'killer_question'], true, NOW()),

  -- General Objection Handlers
  ('objection_too_small', 'Handle "we''re too small" objection', 'objection_handler',
   'What''s your annual revenue? And how many trades do you perform? If 5-50M with 2+ trades: That''s actually our sweet spot. We''re built for contractors your size who''ve outgrown spreadsheets but don''t need enterprise tools.',
   ARRAY['objection', 'qualification', 'size'], true, NOW()),

  ('objection_have_competitor', 'Handle "we already have X" objection', 'objection_handler',
   'Got it - what are you using for asset tracking after project completion? (They won''t have a good answer) That''s the gap Coperniq fills. We''re not replacing your whole stack - we''re adding the asset-centric layer nobody else has.',
   ARRAY['objection', 'competitor', 'asset_lifecycle'], true, NOW()),

  ('objection_expensive', 'Handle "it looks expensive" objection', 'objection_handler',
   'What''s the cost of losing an O&M customer because you didn''t know their system was underperforming? Or: How much time does your team spend on manual invoicing? Our AI invoicing saves 25+ hours per month.',
   ARRAY['objection', 'pricing', 'roi'], true, NOW()),

  ('objection_need_to_think', 'Handle "we need to think about it" objection', 'objection_handler',
   'Totally understand. What would need to be true for you to move forward today? (Listen, then address that specific concern) Let me show you [specific feature they care about] - if that solves your concern, we can get you started this week.',
   ARRAY['objection', 'closing', 'discovery'], true, NOW()),

  ('objection_team_adoption', 'Handle "our team won''t adopt it" objection', 'objection_handler',
   'That''s a real concern. Here''s how we solve it: Coperniq Academy. Your team goes through role-based training - field techs learn mobile, office staff learn invoicing, managers learn analytics. Certified in days, not weeks. Can I show you what the training looks like?',
   ARRAY['objection', 'adoption', 'academy'], true, NOW()),

  -- AI Feature Scripts
  ('ai_copilot_pitch', 'AI Copilot feature pitch', 'value_prop',
   'Ask any question in plain English: "Show me projects stuck in permitting over 14 days" - instant answer. No reports, no exports, no waiting for IT. ServiceTitan, Procore, BuildOps - none of them have this.',
   ARRAY['ai', 'copilot', 'differentiator'], true, NOW()),

  ('ai_invoicing_pitch', 'AI Invoicing feature pitch', 'value_prop',
   'Open a completed project, click Generate Invoice, and AI populates line items from project data - labor, materials, milestones. 15-20 minutes saved per invoice. At 100 invoices/month, that''s 25+ hours back.',
   ARRAY['ai', 'invoicing', 'time_savings'], true, NOW()),

  ('ai_workflow_pitch', 'AI Workflow Builder pitch', 'value_prop',
   'Describe your workflow in plain English: "Solar residential with site survey, permitting, install, inspection, PTO" - AI generates the phases, forms, and automations. 5 minutes vs 30+ minutes manual setup.',
   ARRAY['ai', 'workflow', 'time_savings'], true, NOW()),

  -- Asset & Monitoring Scripts
  ('asset_centric_pitch', 'Asset-centric architecture pitch', 'value_prop',
   'Project-centric tools: job done = record goes cold. Asset-centric (Coperniq): the ASSET lives forever. Track production, service history, O&M billing - all connected to the equipment you installed. That''s the difference.',
   ARRAY['asset', 'architecture', 'differentiator'], true, NOW()),

  ('energy_monitoring_pitch', 'Real-time energy monitoring pitch', 'value_prop',
   'Systems dashboard shows status in real-time: Normal (green), Warning (yellow), Error (red). Peak power, performance trends, kWh produced yesterday/week/month/year/lifetime. Know when systems underperform BEFORE customers call.',
   ARRAY['monitoring', 'systems', 'differentiator'], true, NOW()),

  ('pto_tracking_pitch', 'PTO date tracking pitch', 'value_prop',
   'Permission to Operate is THE milestone for solar. Revenue recognition, customer satisfaction, utility approval. Only Coperniq tracks PTO natively. Filter by "Missing PTO Date" = your revenue at risk.',
   ARRAY['pto', 'solar', 'differentiator'], true, NOW()),

  ('fleet_alerts_pitch', 'Fleet management and alerts pitch', 'value_prop',
   'Fleet Management: manage hundreds of systems across multiple sites. Custom Alerts: define thresholds, get notified when systems underperform. You know before your customer. That''s proactive O&M.',
   ARRAY['fleet', 'alerts', 'oam'], true, NOW())

ON CONFLICT (name) DO UPDATE SET
  description = EXCLUDED.description,
  script_type = EXCLUDED.script_type,
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  is_active = EXCLUDED.is_active;

-- Insert sequence touches (email/call cadences)
INSERT INTO dim_gtme_campaigns (name, description, sequence_id, channel, day_offset, subject_line, body_template, is_active, created_at)
SELECT
  'vs_st_day0_email',
  'Day 0: ServiceTitan battle card email',
  s.id,
  'email',
  0,
  'ServiceTitan vs Coperniq: What They Can''t Do',
  E'Hi {{first_name}},\n\nI noticed you''re evaluating ServiceTitan. Great platform for pure service companies.\n\nBut here''s what ServiceTitan CAN''T do:\n\n❌ Real-time energy monitoring\n❌ Asset lifecycle tracking after project completion\n❌ AI-powered queries ("Show me stuck projects")\n❌ Native PTO date tracking\n❌ Fleet management with custom alerts\n\nIf you install AND maintain equipment, these gaps matter.\n\nWant to see what you''re missing? 15 minutes, I''ll show you the difference.\n\n{{signature}}',
  true,
  NOW()
FROM dim_gtme_sequences s WHERE s.name = 'vs_servicetitan'
ON CONFLICT DO NOTHING;

INSERT INTO dim_gtme_campaigns (name, description, sequence_id, channel, day_offset, subject_line, body_template, is_active, created_at)
SELECT
  'vs_st_day3_email',
  'Day 3: How ServiceTitan customers switch',
  s.id,
  'email',
  3,
  'How Solar Contractors Switch from ServiceTitan',
  E'Hi {{first_name}},\n\nQuick follow-up on my last email.\n\nWe''ve helped dozens of solar/MEP contractors make the switch from ServiceTitan. Common pattern:\n\n1. They realize ServiceTitan can''t track assets post-project\n2. They''re using spreadsheets for PTO dates (risky)\n3. O&M customers churn because they can''t see performance\n\nCoperniq fixes all three. One platform for install AND service.\n\nWorth a 15-minute demo?\n\n{{signature}}',
  true,
  NOW()
FROM dim_gtme_sequences s WHERE s.name = 'vs_servicetitan'
ON CONFLICT DO NOTHING;

INSERT INTO dim_gtme_campaigns (name, description, sequence_id, channel, day_offset, subject_line, body_template, is_active, created_at)
SELECT
  'vs_procore_day0_email',
  'Day 0: Procore battle card email',
  s.id,
  'email',
  0,
  'Procore vs Coperniq: Built for Different Contractors',
  E'Hi {{first_name}},\n\nProcore is excellent for GCs managing subcontractors.\n\nBut you''re self-performing, right? Your own crews, your own equipment?\n\nHere''s where Procore falls short for MEP contractors:\n\n❌ $500+/user pricing (we''re 30-50% less)\n❌ No energy monitoring for solar/HVAC\n❌ Batch QuickBooks sync (we''re real-time)\n❌ No asset lifecycle after project closes\n❌ Separate service module (we''re unified)\n\nIf you install AND maintain, Coperniq is built for you.\n\n15 minutes to see the difference?\n\n{{signature}}',
  true,
  NOW()
FROM dim_gtme_sequences s WHERE s.name = 'vs_procore'
ON CONFLICT DO NOTHING;

-- Add competitive tracking fields to dim_companies if not exists
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'dim_companies'
                 AND column_name = 'competitor_mentioned') THEN
    ALTER TABLE dim_companies ADD COLUMN competitor_mentioned TEXT;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'dim_companies'
                 AND column_name = 'battle_card_used') THEN
    ALTER TABLE dim_companies ADD COLUMN battle_card_used BOOLEAN DEFAULT FALSE;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'dim_companies'
                 AND column_name = 'demo_features_shown') THEN
    ALTER TABLE dim_companies ADD COLUMN demo_features_shown TEXT[];
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'dim_companies'
                 AND column_name = 'objection_raised') THEN
    ALTER TABLE dim_companies ADD COLUMN objection_raised TEXT;
  END IF;
END $$;

-- Create view for competitive intelligence
CREATE OR REPLACE VIEW v_competitive_intel AS
SELECT
  competitor_mentioned,
  COUNT(*) as mention_count,
  COUNT(*) FILTER (WHERE battle_card_used = true) as battle_card_uses,
  COUNT(*) FILTER (WHERE icp_tier = 'A') as tier_a_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE battle_card_used = true) / NULLIF(COUNT(*), 0), 1) as battle_card_rate
FROM dim_companies
WHERE competitor_mentioned IS NOT NULL
GROUP BY competitor_mentioned
ORDER BY mention_count DESC;

-- Summary
DO $$
BEGIN
  RAISE NOTICE '=== GTME COMPETITIVE SEQUENCES SUMMARY ===';
  RAISE NOTICE 'Sequences: 5 (vs_servicetitan, vs_procore, vs_buildops, vs_buildertrend, differentiators)';
  RAISE NOTICE 'Scripts: 20+ (openers, killer questions, value props, objection handlers)';
  RAISE NOTICE 'Campaigns: 3 email templates';
  RAISE NOTICE 'New company fields: competitor_mentioned, battle_card_used, demo_features_shown, objection_raised';
  RAISE NOTICE '==========================================';
END $$;
