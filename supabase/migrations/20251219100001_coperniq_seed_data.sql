-- =============================================================================
-- COPERNIQ SEED DATA (Dec 19, 2025)
-- =============================================================================
-- Seeds the Coperniq schema with:
-- 1. Property categories (10 categories)
-- 2. Property definitions (100+ fields)
-- 3. Sample workflows (Solar, HVAC, Electrical)
-- 4. Sample form templates
-- 5. Links existing dim_companies as potential Coperniq clients
-- =============================================================================

-- =============================================================================
-- 1. PROPERTY CATEGORIES (10)
-- =============================================================================

INSERT INTO dim_cpq_property_categories (name, display_name, display_order, description, icon) VALUES
('standard', 'Standard', 1, 'Core project fields - identifiers, team, communication tracking', 'list'),
('project_charter', 'Project Charter', 2, 'Team assignments and priority', 'users'),
('site_system_info', 'Site & System Info', 3, 'Technical specifications - system size, mount type, angles', 'zap'),
('financial_information', 'Financial Information', 4, 'Pricing, contracts, financing', 'dollar-sign'),
('stakeholder_info', 'Stakeholder Info', 5, 'Lead source, utility, AHJ, dealer info', 'building'),
('stakeholder_portals', 'Stakeholder Portals', 6, 'External portal URLs', 'link'),
('integrations_metadata', 'Integrations Metadata', 7, 'QuickBooks, Stripe, payment tool IDs', 'plug'),
('compliance', 'Compliance', 8, 'Survey and compliance tracking', 'shield'),
('accounting_related', 'Accounting-related', 9, 'Billing preferences', 'file-text'),
('other', 'Other', 10, 'Miscellaneous project properties', 'more-horizontal')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. PROPERTY DEFINITIONS (100+)
-- =============================================================================

-- Helper to get category ID
DO $$
DECLARE
    cat_standard UUID;
    cat_charter UUID;
    cat_site UUID;
    cat_financial UUID;
    cat_stakeholder UUID;
    cat_portals UUID;
    cat_integrations UUID;
    cat_compliance UUID;
    cat_accounting UUID;
    cat_other UUID;
BEGIN
    SELECT category_id INTO cat_standard FROM dim_cpq_property_categories WHERE name = 'standard';
    SELECT category_id INTO cat_charter FROM dim_cpq_property_categories WHERE name = 'project_charter';
    SELECT category_id INTO cat_site FROM dim_cpq_property_categories WHERE name = 'site_system_info';
    SELECT category_id INTO cat_financial FROM dim_cpq_property_categories WHERE name = 'financial_information';
    SELECT category_id INTO cat_stakeholder FROM dim_cpq_property_categories WHERE name = 'stakeholder_info';
    SELECT category_id INTO cat_portals FROM dim_cpq_property_categories WHERE name = 'stakeholder_portals';
    SELECT category_id INTO cat_integrations FROM dim_cpq_property_categories WHERE name = 'integrations_metadata';
    SELECT category_id INTO cat_compliance FROM dim_cpq_property_categories WHERE name = 'compliance';
    SELECT category_id INTO cat_accounting FROM dim_cpq_property_categories WHERE name = 'accounting_related';
    SELECT category_id INTO cat_other FROM dim_cpq_property_categories WHERE name = 'other';

    -- STANDARD PROPERTIES (32)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, is_system, display_order) VALUES
    (cat_standard, 'Trades', 'Trades', 'trades', 'multiple_select', false, 1),
    (cat_standard, 'Status', 'Status', 'status', 'single_select', false, 2),
    (cat_standard, 'Project value', 'Project Value', 'project_value', 'currency', false, 3),
    (cat_standard, 'Project size', 'Project Size', 'project_size', 'numeric', false, 4),
    (cat_standard, 'Sales Rep', 'Sales Rep', 'sales_rep', 'user_reference', false, 5),
    (cat_standard, 'Project Manager', 'Project Manager', 'project_manager', 'user_reference', false, 6),
    (cat_standard, 'Owner', 'Owner', 'owner', 'user_reference', false, 7),
    (cat_standard, 'Description', 'Description', 'description', 'long_text', false, 8),
    (cat_standard, 'Last activity', 'Last Activity', 'last_activity', 'datetime', true, 9),
    (cat_standard, 'Profit', 'Profit', 'profit', 'currency', true, 10),
    (cat_standard, 'Revenue', 'Revenue', 'revenue', 'currency', true, 11),
    (cat_standard, 'Cost', 'Cost', 'cost', 'currency', true, 12),
    (cat_standard, 'Total Inbound Calls', 'Total Inbound Calls', 'total_inbound_calls', 'numeric', true, 13),
    (cat_standard, 'Total Outbound Calls', 'Total Outbound Calls', 'total_outbound_calls', 'numeric', true, 14),
    (cat_standard, 'Last Inbound SMS Date', 'Last Inbound SMS Date', 'last_inbound_sms_date', 'datetime', true, 15),
    (cat_standard, 'Last Outbound SMS Date', 'Last Outbound SMS Date', 'last_outbound_sms_date', 'datetime', true, 16),
    (cat_standard, 'Last Inbound Email Date', 'Last Inbound Email Date', 'last_inbound_email_date', 'datetime', true, 17),
    (cat_standard, 'Last Outbound Email Date', 'Last Outbound Email Date', 'last_outbound_email_date', 'datetime', true, 18),
    (cat_standard, 'Last Inbound Call Disposition', 'Last Inbound Call Disposition', 'last_inbound_call_disposition', 'single_select', true, 19),
    (cat_standard, 'Last Outbound Call Disposition', 'Last Outbound Call Disposition', 'last_outbound_call_disposition', 'single_select', true, 20),
    (cat_standard, 'Last Inbound Call Date', 'Last Inbound Call Date', 'last_inbound_call_date', 'datetime', true, 21),
    (cat_standard, 'Last Outbound Call Date', 'Last Outbound Call Date', 'last_outbound_call_date', 'datetime', true, 22),
    (cat_standard, 'Number', 'Project Number', 'number', 'text', true, 23),
    (cat_standard, 'AHJ', 'AHJ', 'ahj', 'text', false, 24),
    (cat_standard, 'Site Address Zipcode', 'Site Address Zipcode', 'site_address_zipcode', 'text', false, 25),
    (cat_standard, 'Site Address State', 'Site Address State', 'site_address_state', 'text', false, 26),
    (cat_standard, 'Site Address Street', 'Site Address Street', 'site_address_street', 'text', false, 27),
    (cat_standard, 'Site Address City', 'Site Address City', 'site_address_city', 'text', false, 28),
    (cat_standard, 'Primary phone', 'Primary Phone', 'primary_phone', 'phone', false, 29),
    (cat_standard, 'Primary email', 'Primary Email', 'primary_email', 'email', false, 30),
    (cat_standard, 'Created By', 'Created By', 'created_by', 'user_reference', true, 31),
    (cat_standard, 'Created at', 'Created At', 'created_at', 'datetime', true, 32),
    (cat_standard, 'Record ID', 'Record ID', 'record_id', 'text', true, 33)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- PROJECT CHARTER PROPERTIES (6)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_charter, 'PM Assistant', 'PM Assistant', 'pm_assistant', 'user_reference', 1),
    (cat_charter, 'Engineer (3rd party)', 'Engineer (3rd party)', 'engineer_3rd_party', 'user_reference', 2),
    (cat_charter, 'Applications Specialist', 'Applications Specialist', 'applications_specialist', 'user_reference', 3),
    (cat_charter, 'Batteries Issues', 'Batteries Issues', 'batteries_issues', 'single_select', 4),
    (cat_charter, 'Procurement Lead', 'Procurement Lead', 'procurement_lead', 'user_reference', 5),
    (cat_charter, 'Priority', 'Priority', 'priority', 'single_select', 6)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- SITE & SYSTEM INFO PROPERTIES (11)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_site, 'System Size (STC DC kW)', 'System Size (STC DC kW)', 'system_size_stc_dc_kw', 'numeric', 1),
    (cat_site, 'Battery Size (kWh)', 'Battery Size (kWh)', 'battery_size_kwh', 'numeric', 2),
    (cat_site, 'MPU (Yes/No)', 'MPU (Yes/No)', 'mpu_yes_no', 'single_select', 3),
    (cat_site, 'Number Of Stories', 'Number Of Stories', 'number_of_stories', 'numeric', 4),
    (cat_site, 'Mount Type', 'Mount Type', 'mount_type', 'single_select', 5),
    (cat_site, 'Azimuth Angle (deg)', 'Azimuth Angle (deg)', 'azimuth_angle_deg', 'numeric', 6),
    (cat_site, 'Tilt Angle (deg)', 'Tilt Angle (deg)', 'tilt_angle_deg', 'numeric', 7),
    (cat_site, 'Call Webhook', 'Call Webhook', 'call_webhook', 'url', 8),
    (cat_site, 'Utility Bill PDF', 'Utility Bill PDF', 'utility_bill_pdf', 'file', 9),
    (cat_site, 'Roof Work?', 'Roof Work?', 'roof_work', 'single_select', 10),
    (cat_site, 'Domestic Content (Y/N)', 'Domestic Content (Y/N)', 'domestic_content_yn', 'single_select', 11)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- FINANCIAL INFORMATION PROPERTIES (7)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_financial, 'Gross Contract Price ($)', 'Gross Contract Price ($)', 'gross_contract_price', 'currency', 1),
    (cat_financial, 'Gross PPW ($)', 'Gross PPW ($)', 'gross_ppw', 'currency', 2),
    (cat_financial, 'Monthly Utility Bill ($)', 'Monthly Utility Bill ($)', 'monthly_utility_bill', 'currency', 3),
    (cat_financial, 'Contract Signed Date', 'Contract Signed Date', 'contract_signed_date', 'date', 4),
    (cat_financial, 'Contract Date validity', 'Contract Date Validity', 'contract_date_validity', 'text', 5),
    (cat_financial, 'Accounting Onboarding Status', 'Accounting Onboarding Status', 'accounting_onboarding_status', 'single_select', 6),
    (cat_financial, 'Financing Provider', 'Financing Provider', 'financing_provider', 'single_select', 7)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- STAKEHOLDER INFO PROPERTIES (15)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_stakeholder, 'Lead Source', 'Lead Source', 'lead_source', 'single_select', 1),
    (cat_stakeholder, 'Referred By', 'Referred By', 'referred_by', 'text', 2),
    (cat_stakeholder, 'Ownership Type', 'Ownership Type', 'ownership_type', 'single_select', 3),
    (cat_stakeholder, 'Loan Provider', 'Loan Provider', 'loan_provider', 'single_select', 4),
    (cat_stakeholder, 'Utility Company', 'Utility Company', 'utility_company', 'text', 5),
    (cat_stakeholder, 'AHJ', 'AHJ', 'stakeholder_ahj', 'text', 6),
    (cat_stakeholder, 'Dealer Company', 'Dealer Company', 'dealer_company', 'single_select', 7),
    (cat_stakeholder, 'Sales Setter Name', 'Sales Setter Name', 'sales_setter_name', 'text', 8),
    (cat_stakeholder, 'Sales Closer Name', 'Sales Closer Name', 'sales_closer_name', 'text', 9),
    (cat_stakeholder, 'Project Manager Name', 'Project Manager Name', 'project_manager_name', 'text', 10),
    (cat_stakeholder, 'Project Model', 'Project Model', 'project_model', 'single_select', 11),
    (cat_stakeholder, 'Roof Lead', 'Roof Lead', 'roof_lead', 'user_reference', 12),
    (cat_stakeholder, 'Crew Lead', 'Crew Lead', 'crew_lead', 'user_reference', 13),
    (cat_stakeholder, 'Electrician', 'Electrician', 'electrician', 'user_reference', 14),
    (cat_stakeholder, '3rd Party Engineering?', '3rd Party Engineering?', 'third_party_engineering', 'single_select', 15)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- STAKEHOLDER PORTALS PROPERTIES (3)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_portals, 'AHJ Portal', 'AHJ Portal', 'ahj_portal', 'url', 1),
    (cat_portals, 'Utility Portal', 'Utility Portal', 'utility_portal', 'url', 2),
    (cat_portals, 'LightReach Portal', 'LightReach Portal', 'lightreach_portal', 'url', 3)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- INTEGRATIONS METADATA PROPERTIES (15)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_integrations, 'Accounting', 'Accounting', 'accounting', 'text', 1),
    (cat_integrations, 'QuickBooks Online Customer ID', 'QuickBooks Online Customer ID', 'qbo_customer_id', 'text', 2),
    (cat_integrations, 'QuickBooks Online Customer URL', 'QuickBooks Online Customer URL', 'qbo_customer_url', 'url', 3),
    (cat_integrations, 'QuickBooks Online Customer', 'QuickBooks Online Customer', 'qbo_customer', 'text', 4),
    (cat_integrations, 'QuickBooks Online Invoice ID', 'QuickBooks Online Invoice ID', 'qbo_invoice_id', 'text', 5),
    (cat_integrations, 'QuickBooks Online Invoice URL', 'QuickBooks Online Invoice URL', 'qbo_invoice_url', 'url', 6),
    (cat_integrations, 'QuickBooks Online Invoice', 'QuickBooks Online Invoice', 'qbo_invoice', 'text', 7),
    (cat_integrations, 'QuickBooks Online Invoice Itemized', 'QuickBooks Online Invoice Itemized', 'qbo_invoice_itemized', 'single_select', 8),
    (cat_integrations, 'QuickBooks Online Sync Date', 'QuickBooks Online Sync Date', 'qbo_sync_date', 'datetime', 9),
    (cat_integrations, 'QuickBooks Invoice Flag', 'QuickBooks Invoice Flag', 'qbo_invoice_flag', 'single_select', 10),
    (cat_integrations, 'Stripe Customer ID', 'Stripe Customer ID', 'stripe_customer_id', 'text', 11),
    (cat_integrations, 'Stripe Customer URL', 'Stripe Customer URL', 'stripe_customer_url', 'url', 12),
    (cat_integrations, 'Stripe Customer', 'Stripe Customer', 'stripe_customer', 'text', 13),
    (cat_integrations, 'Payments Tool', 'Payments Tool', 'payments_tool', 'text', 14),
    (cat_integrations, 'Project Source', 'Project Source', 'project_source', 'text', 15)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- COMPLIANCE PROPERTIES (2)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_compliance, 'Callpilot Survey Type', 'Callpilot Survey Type', 'callpilot_survey_type', 'single_select', 1),
    (cat_compliance, 'Callpilot Survey Link', 'Callpilot Survey Link', 'callpilot_survey_link', 'url', 2)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- ACCOUNTING RELATED PROPERTIES (1)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_accounting, 'Prefers Lump Sum?', 'Prefers Lump Sum?', 'prefers_lump_sum', 'single_select', 1)
    ON CONFLICT (category_id, slug) DO NOTHING;

    -- OTHER PROPERTIES (20+ of the key ones)
    INSERT INTO dim_cpq_property_definitions (category_id, name, display_name, slug, data_type, display_order) VALUES
    (cat_other, 'Module Model', 'Module Model', 'module_model', 'text', 1),
    (cat_other, 'Module Qty', 'Module Qty', 'module_qty', 'numeric', 2),
    (cat_other, 'Inverter Model', 'Inverter Model', 'inverter_model', 'text', 3),
    (cat_other, 'Inverter Qty', 'Inverter Qty', 'inverter_qty', 'numeric', 4),
    (cat_other, 'System Size (kW DC)', 'System Size (kW DC)', 'system_size_kw_dc', 'numeric', 5),
    (cat_other, 'System Size (kW AC)', 'System Size (kW AC)', 'system_size_kw_ac', 'numeric', 6),
    (cat_other, 'Estimated Annual Production (kWh)', 'Estimated Annual Production (kWh)', 'estimated_annual_production_kwh', 'numeric', 7),
    (cat_other, 'Storage Capacity (kWh)', 'Storage Capacity (kWh)', 'storage_capacity_kwh', 'numeric', 8),
    (cat_other, 'Permit Coordinator', 'Permit Coordinator', 'permit_coordinator', 'user_reference', 9),
    (cat_other, 'HOA (Yes/No)', 'HOA (Yes/No)', 'hoa_yes_no', 'single_select', 10),
    (cat_other, 'Net PPW ($)', 'Net PPW ($)', 'net_ppw', 'currency', 11),
    (cat_other, 'Financing Monthly Payment ($)', 'Financing Monthly Payment ($)', 'financing_monthly_payment', 'currency', 12),
    (cat_other, 'Utility Rate', 'Utility Rate', 'utility_rate', 'text', 13),
    (cat_other, 'Client Sentiment', 'Client Sentiment', 'client_sentiment', 'single_select', 14),
    (cat_other, 'Conditions', 'Conditions', 'conditions', 'single_select', 15),
    (cat_other, 'Engineering Revisions Required', 'Engineering Revisions Required', 'engineering_revisions_required', 'single_select', 16),
    (cat_other, 'Permit Req''d?', 'Permit Req''d?', 'permit_required', 'single_select', 17),
    (cat_other, 'Lead Channel', 'Lead Channel', 'lead_channel', 'text', 18),
    (cat_other, 'PTO Date', 'PTO Date', 'pto_date', 'date', 19),
    (cat_other, 'Installation Date', 'Installation Date', 'installation_date', 'date', 20)
    ON CONFLICT (category_id, slug) DO NOTHING;

END $$;

-- =============================================================================
-- 3. WORKFLOW TEMPLATES
-- =============================================================================

INSERT INTO dim_cpq_workflow_templates (name, description, workflow_type, trade, client_segment, is_default) VALUES
('Resi-Retrofit Solar', 'Residential rooftop solar installation workflow', 'project', 'Solar', 'Residential', true),
('Commercial Solar', 'Commercial and industrial solar projects', 'project', 'Solar', 'Commercial', false),
('HVAC Residential Install', 'Residential HVAC system installation', 'project', 'HVAC', 'Residential', false),
('HVAC Service', 'HVAC maintenance and service workflow', 'project', 'HVAC', 'Residential', false),
('Electrical Service', 'Electrical repair and upgrade workflow', 'project', 'Electrical', 'Residential', false),
('Sales Request Triage', 'Inbound lead qualification workflow', 'request', 'All', 'All', true)
ON CONFLICT DO NOTHING;

-- Add phases for Solar Residential workflow
DO $$
DECLARE
    solar_workflow_id UUID;
BEGIN
    SELECT workflow_id INTO solar_workflow_id
    FROM dim_cpq_workflow_templates
    WHERE name = 'Resi-Retrofit Solar' LIMIT 1;

    IF solar_workflow_id IS NOT NULL THEN
        INSERT INTO dim_cpq_workflow_phases (workflow_id, name, phase_type, phase_order, sla_yellow_days, sla_red_days) VALUES
        (solar_workflow_id, 'Welcome / Onboarding', 'initiation', 1, 3, 5),
        (solar_workflow_id, 'Site Survey', 'design', 2, 5, 10),
        (solar_workflow_id, 'Engineering / Design', 'engineering', 3, 7, 14),
        (solar_workflow_id, 'Permitting', 'permitting', 4, 14, 30),
        (solar_workflow_id, 'Procurement', 'procurement', 5, 7, 14),
        (solar_workflow_id, 'Installation', 'construction', 6, 3, 7),
        (solar_workflow_id, 'Inspection', 'inspection', 7, 7, 14),
        (solar_workflow_id, 'PTO / Interconnection', 'closeout', 8, 14, 30),
        (solar_workflow_id, 'O&M', 'operation_maintenance', 9, NULL, NULL)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- =============================================================================
-- 4. SAMPLE FORM TEMPLATES
-- =============================================================================

INSERT INTO dim_cpq_form_templates (name, description, category, trade, is_active) VALUES
('[BP] Site Survey (Roof Mount)', 'Comprehensive residential rooftop site assessment', 'Site Survey', 'Solar', true),
('[BP] Customer Onboarding', 'New customer welcome and info collection', 'Onboarding', 'All', true),
('[BP] AHJ Permit Application', 'Authority Having Jurisdiction permit application form', 'Permitting', 'Solar', true),
('[BP] AHJ Inspection', 'Final AHJ inspection checklist', 'Inspection', 'Solar', true),
('[BP] PTO/Interconnection', 'Permission to Operate tracking form', 'Closeout', 'Solar', true),
('[BP] MPU / Electrical', 'Main Panel Upgrade documentation', 'Electrical', 'Electrical', true),
('HVAC Load Calculation', 'HVAC system sizing and load calculation', 'Design', 'HVAC', true),
('HVAC Maintenance Checklist', 'Routine HVAC maintenance form', 'Service', 'HVAC', true)
ON CONFLICT DO NOTHING;

-- Add form groups and fields for Site Survey
DO $$
DECLARE
    site_survey_id UUID;
    group_customer UUID;
    group_electrical UUID;
    group_roof UUID;
BEGIN
    SELECT form_id INTO site_survey_id
    FROM dim_cpq_form_templates
    WHERE name = '[BP] Site Survey (Roof Mount)' LIMIT 1;

    IF site_survey_id IS NOT NULL THEN
        -- Create groups
        INSERT INTO dim_cpq_form_groups (form_id, title, group_order) VALUES
        (site_survey_id, 'Customer', 1) RETURNING group_id INTO group_customer;

        INSERT INTO dim_cpq_form_groups (form_id, title, group_order) VALUES
        (site_survey_id, 'Electrical', 2) RETURNING group_id INTO group_electrical;

        INSERT INTO dim_cpq_form_groups (form_id, title, group_order) VALUES
        (site_survey_id, 'Roof', 3) RETURNING group_id INTO group_roof;

        -- Customer fields
        INSERT INTO dim_cpq_form_fields (form_id, group_id, name, label, field_type, is_required, field_order) VALUES
        (site_survey_id, group_customer, 'customer_name', 'Customer Name', 'text', true, 1),
        (site_survey_id, group_customer, 'is_hoa', 'Is this home part of an HOA?', 'single_select', false, 2),
        (site_survey_id, group_customer, 'photo_address', 'Photo of address from street', 'file', true, 3),
        (site_survey_id, group_customer, 'ahj', 'AHJ', 'single_select', false, 4),
        (site_survey_id, group_customer, 'is_modular', 'Is this a modular or manufactured home?', 'single_select', false, 5),
        (site_survey_id, group_customer, 'stories', 'How many stories is the building', 'numeric', false, 6);

        -- Electrical fields
        INSERT INTO dim_cpq_form_fields (form_id, group_id, name, label, field_type, is_required, field_order) VALUES
        (site_survey_id, group_electrical, 'panel_year', 'Year of manufacture', 'text', false, 1),
        (site_survey_id, group_electrical, 'feed_type', 'Type of feed', 'single_select', false, 2),
        (site_survey_id, group_electrical, 'meter_pic', 'Pic of meter SN', 'file', true, 3),
        (site_survey_id, group_electrical, 'main_breaker_pic', 'Clear pic of main breaker', 'file', true, 4),
        (site_survey_id, group_electrical, 'panel_closed', 'Main panel Closed', 'file', true, 5),
        (site_survey_id, group_electrical, 'panel_open', 'Main panel open', 'file', true, 6);

        -- Roof fields
        INSERT INTO dim_cpq_form_fields (form_id, group_id, name, label, field_type, is_required, field_order) VALUES
        (site_survey_id, group_roof, 'roof_type', 'Roof type', 'single_select', true, 1),
        (site_survey_id, group_roof, 'roof_a_tilt', 'Roof A tilt', 'numeric', false, 2),
        (site_survey_id, group_roof, 'roof_a_pic', 'Picture of Roof plane A', 'file', true, 3),
        (site_survey_id, group_roof, 'rafter_width', 'Rafter measurement (width)', 'numeric', false, 4),
        (site_survey_id, group_roof, 'rafter_spacing', 'Rafter measurement (spacing)', 'numeric', false, 5),
        (site_survey_id, group_roof, 'roof_damage', 'Pics of any visible roof damage', 'file', false, 6);
    END IF;
END $$;

-- =============================================================================
-- 5. IMPORT EXISTING COMPANIES AS COPERNIQ CLIENTS
-- =============================================================================
-- These are MEP contractors who SHOULD USE Coperniq.io
-- We're creating them as clients so we can demo the platform

INSERT INTO dim_cpq_clients (
    name,
    client_type,
    primary_email,
    primary_phone,
    street,
    city,
    state,
    zip,
    source,
    portal_enabled
)
SELECT
    company_name,
    'commercial',  -- These are businesses, not homeowners
    NULL,  -- Will need to enrich later
    phone,
    street,
    city,
    state,
    zip,
    'dealer_scraper',
    false
FROM dim_companies
WHERE company_name IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM dim_cpq_clients
    WHERE dim_cpq_clients.name = dim_companies.company_name
  )
LIMIT 500;  -- Import first 500 companies

-- =============================================================================
-- 6. SAMPLE AUTOMATION TEMPLATES
-- =============================================================================

INSERT INTO dim_cpq_automation_templates (name, description, trigger_type, trigger_config, action_type, action_config, is_active) VALUES
(
    'Welcome Email on Project Create',
    'Send welcome email when new project is created',
    'project_phase_started',
    '{"phase_name": "Welcome / Onboarding"}'::jsonb,
    'send_email',
    '{"template": "welcome_email", "to": "client"}'::jsonb,
    true
),
(
    'SLA Alert - Permitting Delay',
    'Send SMS to PM when permitting exceeds SLA',
    'project_phase_sla_violation',
    '{"phase_name": "Permitting", "sla_type": "yellow"}'::jsonb,
    'send_sms',
    '{"to": "project_manager", "message": "Permitting SLA at risk"}'::jsonb,
    true
),
(
    'Create Inspection WO on Install Complete',
    'Auto-create inspection work order when installation phase completes',
    'project_phase_completed',
    '{"phase_name": "Installation"}'::jsonb,
    'create_task',
    '{"task_name": "Schedule AHJ Inspection", "assignee": "permit_coordinator"}'::jsonb,
    true
),
(
    'Update Status on PTO',
    'Mark project complete when PTO phase completes',
    'project_phase_completed',
    '{"phase_name": "PTO / Interconnection"}'::jsonb,
    'update_property',
    '{"property": "status", "value": "completed"}'::jsonb,
    true
)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify seed data
DO $$
DECLARE
    cat_count INTEGER;
    prop_count INTEGER;
    workflow_count INTEGER;
    phase_count INTEGER;
    form_count INTEGER;
    client_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cat_count FROM dim_cpq_property_categories;
    SELECT COUNT(*) INTO prop_count FROM dim_cpq_property_definitions;
    SELECT COUNT(*) INTO workflow_count FROM dim_cpq_workflow_templates;
    SELECT COUNT(*) INTO phase_count FROM dim_cpq_workflow_phases;
    SELECT COUNT(*) INTO form_count FROM dim_cpq_form_templates;
    SELECT COUNT(*) INTO client_count FROM dim_cpq_clients;

    RAISE NOTICE '=== COPERNIQ SEED DATA SUMMARY ===';
    RAISE NOTICE 'Property Categories: %', cat_count;
    RAISE NOTICE 'Property Definitions: %', prop_count;
    RAISE NOTICE 'Workflow Templates: %', workflow_count;
    RAISE NOTICE 'Workflow Phases: %', phase_count;
    RAISE NOTICE 'Form Templates: %', form_count;
    RAISE NOTICE 'Clients (from dim_companies): %', client_count;
    RAISE NOTICE '==================================';
END $$;
