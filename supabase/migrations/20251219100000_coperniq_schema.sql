-- =============================================================================
-- COPERNIQ PLATFORM SCHEMA (Dec 19, 2025)
-- =============================================================================
-- Mirror of Coperniq.io Process Studio for testing, Academy training, and
-- prototyping automations before deploying to production.
--
-- Tables prefixed with `cpq_` to namespace from sales-agent tables.
-- Schema derived from live audit of app.coperniq.io workspace 112.
-- =============================================================================

-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_cpq_property_categories: Property groupings (10 categories)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_property_categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    display_order INTEGER DEFAULT 0,

    -- Metadata
    description TEXT,
    icon VARCHAR(50),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- dim_cpq_property_definitions: The 100+ project properties
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_property_definitions (
    property_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES dim_cpq_property_categories(category_id),

    -- Identity
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,  -- snake_case for API

    -- Type
    data_type VARCHAR(50) NOT NULL CHECK (data_type IN (
        'text', 'long_text', 'numeric', 'currency', 'percentage',
        'single_select', 'multiple_select', 'date', 'datetime',
        'file', 'url', 'email', 'phone', 'user_reference', 'boolean'
    )),

    -- Options (for select types)
    options JSONB DEFAULT '[]',  -- ["Option 1", "Option 2"]

    -- Validation
    is_required BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT FALSE,  -- Auto-populated by Coperniq
    is_calculated BOOLEAN DEFAULT FALSE,  -- Derived fields

    -- UI
    display_order INTEGER DEFAULT 0,
    placeholder TEXT,
    help_text TEXT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(category_id, slug)
);

CREATE INDEX idx_cpq_properties_category ON dim_cpq_property_definitions(category_id);
CREATE INDEX idx_cpq_properties_type ON dim_cpq_property_definitions(data_type);
CREATE INDEX idx_cpq_properties_slug ON dim_cpq_property_definitions(slug);

-- -----------------------------------------------------------------------------
-- dim_cpq_clients: Client records
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    client_type VARCHAR(50) DEFAULT 'residential' CHECK (client_type IN (
        'residential', 'commercial', 'industrial', 'utility'
    )),

    -- Contact
    primary_email VARCHAR(255),
    primary_phone VARCHAR(50),
    secondary_email VARCHAR(255),

    -- Address
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    country VARCHAR(50) DEFAULT 'USA',

    -- Relationships
    referred_by VARCHAR(255),

    -- Portal
    portal_enabled BOOLEAN DEFAULT FALSE,
    portal_last_login TIMESTAMPTZ,

    -- Source tracking
    source VARCHAR(100),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_cpq_clients_name ON dim_cpq_clients(name);
CREATE INDEX idx_cpq_clients_type ON dim_cpq_clients(client_type);
CREATE INDEX idx_cpq_clients_email ON dim_cpq_clients(primary_email);

-- -----------------------------------------------------------------------------
-- dim_cpq_workflow_templates: Project/Request workflows
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_workflow_templates (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,
    workflow_type VARCHAR(50) NOT NULL CHECK (workflow_type IN (
        'project', 'request'
    )),

    -- Classification
    trade VARCHAR(100),  -- Solar, HVAC, Electrical, Plumbing
    client_segment VARCHAR(50),  -- Residential, Commercial

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_workflows_type ON dim_cpq_workflow_templates(workflow_type);
CREATE INDEX idx_cpq_workflows_trade ON dim_cpq_workflow_templates(trade);

-- -----------------------------------------------------------------------------
-- dim_cpq_workflow_phases: Phases within workflows
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_workflow_phases (
    phase_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES dim_cpq_workflow_templates(workflow_id) ON DELETE CASCADE,

    -- Identity
    name VARCHAR(255) NOT NULL,
    phase_type VARCHAR(50) NOT NULL CHECK (phase_type IN (
        'initiation', 'design', 'engineering', 'permitting', 'procurement',
        'construction', 'commissioning', 'inspection', 'closeout',
        'operation_maintenance', 'custom'
    )),

    -- Order
    phase_order INTEGER NOT NULL,

    -- SLA
    sla_yellow_days INTEGER,  -- Warning threshold
    sla_red_days INTEGER,  -- Critical threshold

    -- Attachments (IDs of linked templates)
    work_order_templates JSONB DEFAULT '[]',
    form_templates JSONB DEFAULT '[]',
    payment_structures JSONB DEFAULT '[]',

    -- Automations
    automations_on_enter JSONB DEFAULT '[]',
    automations_on_exit JSONB DEFAULT '[]',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_phases_workflow ON dim_cpq_workflow_phases(workflow_id);
CREATE INDEX idx_cpq_phases_type ON dim_cpq_workflow_phases(phase_type);
CREATE INDEX idx_cpq_phases_order ON dim_cpq_workflow_phases(workflow_id, phase_order);

-- -----------------------------------------------------------------------------
-- dim_cpq_form_templates: Form template definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_form_templates (
    form_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Linked Work Order
    linked_work_order_id UUID,
    linked_work_order_name VARCHAR(255),
    linked_work_order_type VARCHAR(50) CHECK (linked_work_order_type IN ('field', 'office')),

    -- Settings
    due_date_relative VARCHAR(50),  -- e.g., "+7 days"
    labels JSONB DEFAULT '[]',

    -- Classification
    category VARCHAR(100),  -- Site Survey, Inspection, Permitting, etc.
    trade VARCHAR(100),  -- Solar, HVAC, Electrical

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_template BOOLEAN DEFAULT TRUE,  -- vs instance

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_forms_name ON dim_cpq_form_templates(name);
CREATE INDEX idx_cpq_forms_category ON dim_cpq_form_templates(category);
CREATE INDEX idx_cpq_forms_trade ON dim_cpq_form_templates(trade);

-- -----------------------------------------------------------------------------
-- dim_cpq_form_groups: Form sections/groups
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_form_groups (
    group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES dim_cpq_form_templates(form_id) ON DELETE CASCADE,

    -- Identity
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Order
    group_order INTEGER NOT NULL,

    -- Settings
    is_collapsible BOOLEAN DEFAULT TRUE,
    is_collapsed_default BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_form_groups_form ON dim_cpq_form_groups(form_id);
CREATE INDEX idx_cpq_form_groups_order ON dim_cpq_form_groups(form_id, group_order);

-- -----------------------------------------------------------------------------
-- dim_cpq_form_fields: Individual form fields
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_form_fields (
    field_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES dim_cpq_form_templates(form_id) ON DELETE CASCADE,
    group_id UUID REFERENCES dim_cpq_form_groups(group_id) ON DELETE CASCADE,

    -- Identity
    name VARCHAR(255) NOT NULL,
    label VARCHAR(255) NOT NULL,

    -- Type
    field_type VARCHAR(50) NOT NULL CHECK (field_type IN (
        'text', 'numeric', 'single_select', 'multiple_select', 'file', 'group'
    )),

    -- Options (for select types)
    options JSONB DEFAULT '[]',

    -- Linked Property
    linked_property_id UUID REFERENCES dim_cpq_property_definitions(property_id),
    linked_property_name VARCHAR(255),

    -- Validation
    is_required BOOLEAN DEFAULT FALSE,
    validation_rules JSONB DEFAULT '{}',

    -- Order
    field_order INTEGER NOT NULL,

    -- Settings
    placeholder TEXT,
    help_text TEXT,
    default_value TEXT,

    -- Mobile
    show_on_mobile BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_fields_form ON dim_cpq_form_fields(form_id);
CREATE INDEX idx_cpq_fields_group ON dim_cpq_form_fields(group_id);
CREATE INDEX idx_cpq_fields_type ON dim_cpq_form_fields(field_type);
CREATE INDEX idx_cpq_fields_linked ON dim_cpq_form_fields(linked_property_id);
CREATE INDEX idx_cpq_fields_order ON dim_cpq_form_fields(form_id, field_order);

-- -----------------------------------------------------------------------------
-- dim_cpq_automation_templates: Automation rules
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_automation_templates (
    automation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Trigger
    trigger_type VARCHAR(100) NOT NULL CHECK (trigger_type IN (
        'work_order_status_updated', 'work_order_completed',
        'project_phase_started', 'project_phase_completed',
        'project_phase_sla_violation', 'project_status_updated',
        'project_property_updated', 'request_phase_started',
        'request_created', 'task_created', 'deal_phase_sla_violation'
    )),
    trigger_config JSONB DEFAULT '{}',  -- Specific conditions

    -- Action
    action_type VARCHAR(100) NOT NULL CHECK (action_type IN (
        'update_property', 'replace_assignee', 'assign_task',
        'create_task', 'create_project', 'create_reminder',
        'send_email', 'send_sms', 'call_webhook'
    )),
    action_config JSONB DEFAULT '{}',  -- Action parameters

    -- Conditions
    conditions JSONB DEFAULT '[]',  -- Filter conditions

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_automations_trigger ON dim_cpq_automation_templates(trigger_type);
CREATE INDEX idx_cpq_automations_action ON dim_cpq_automation_templates(action_type);
CREATE INDEX idx_cpq_automations_active ON dim_cpq_automation_templates(is_active);

-- =============================================================================
-- FACT TABLES (For tracking/testing)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_cpq_projects: Project records (fact-like but dimension for testing)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cpq_projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    workflow_id UUID REFERENCES dim_cpq_workflow_templates(workflow_id),

    -- Identity
    title VARCHAR(255) NOT NULL,
    number VARCHAR(50),  -- Project number (auto-generated)

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN (
        'draft', 'active', 'on_hold', 'completed', 'cancelled', 'archived'
    )),
    current_phase_id UUID REFERENCES dim_cpq_workflow_phases(phase_id),
    current_phase_name VARCHAR(255),

    -- Properties (JSONB for flexibility - key: property_slug, value: data)
    properties JSONB DEFAULT '{}',

    -- Team
    sales_rep VARCHAR(255),
    project_manager VARCHAR(255),
    owner VARCHAR(255),

    -- Site (denormalized for quick access)
    site_address_street VARCHAR(255),
    site_address_city VARCHAR(100),
    site_address_state VARCHAR(50),
    site_address_zip VARCHAR(20),
    ahj VARCHAR(255),  -- Authority Having Jurisdiction

    -- System (solar/HVAC specific)
    system_size_kw DECIMAL(10, 2),
    battery_size_kwh DECIMAL(10, 2),
    mount_type VARCHAR(50),

    -- Financial
    contract_price DECIMAL(12, 2),
    gross_ppw DECIMAL(6, 2),  -- Price per watt

    -- Dates
    contract_signed_date DATE,
    pto_date DATE,  -- Permission to Operate

    -- Source
    source VARCHAR(100),
    referred_by VARCHAR(255),

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_cpq_projects_client ON dim_cpq_projects(client_id);
CREATE INDEX idx_cpq_projects_workflow ON dim_cpq_projects(workflow_id);
CREATE INDEX idx_cpq_projects_status ON dim_cpq_projects(status);
CREATE INDEX idx_cpq_projects_phase ON dim_cpq_projects(current_phase_id);
CREATE INDEX idx_cpq_projects_created ON dim_cpq_projects(created_at DESC);
CREATE INDEX idx_cpq_projects_properties ON dim_cpq_projects USING GIN (properties);

-- -----------------------------------------------------------------------------
-- fact_cpq_form_submissions: Form submission instances (for testing)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_cpq_form_submissions (
    submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES dim_cpq_form_templates(form_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),

    -- Data
    field_values JSONB NOT NULL DEFAULT '{}',  -- field_id -> value

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'submitted', 'approved', 'rejected'
    )),

    -- Completion
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(255),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_submissions_form ON fact_cpq_form_submissions(form_id);
CREATE INDEX idx_cpq_submissions_project ON fact_cpq_form_submissions(project_id);
CREATE INDEX idx_cpq_submissions_status ON fact_cpq_form_submissions(status);
CREATE INDEX idx_cpq_submissions_values ON fact_cpq_form_submissions USING GIN (field_values);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all Coperniq tables
ALTER TABLE dim_cpq_property_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_property_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_workflow_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_workflow_phases ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_form_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_form_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_form_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_automation_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_cpq_form_submissions ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY "cpq_categories_service" ON dim_cpq_property_categories FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_properties_service" ON dim_cpq_property_definitions FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_clients_service" ON dim_cpq_clients FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_workflows_service" ON dim_cpq_workflow_templates FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_phases_service" ON dim_cpq_workflow_phases FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_forms_service" ON dim_cpq_form_templates FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_groups_service" ON dim_cpq_form_groups FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_fields_service" ON dim_cpq_form_fields FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_automations_service" ON dim_cpq_automation_templates FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_projects_service" ON dim_cpq_projects FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_submissions_service" ON fact_cpq_form_submissions FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Anon/authenticated can read dimension tables (for Academy)
CREATE POLICY "cpq_categories_read" ON dim_cpq_property_categories FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_properties_read" ON dim_cpq_property_definitions FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_workflows_read" ON dim_cpq_workflow_templates FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_phases_read" ON dim_cpq_workflow_phases FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_forms_read" ON dim_cpq_form_templates FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_groups_read" ON dim_cpq_form_groups FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_fields_read" ON dim_cpq_form_fields FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_automations_read" ON dim_cpq_automation_templates FOR SELECT TO anon, authenticated USING (TRUE);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-update updated_at timestamps
CREATE OR REPLACE FUNCTION update_cpq_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_cpq_categories_updated
    BEFORE UPDATE ON dim_cpq_property_categories
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_properties_updated
    BEFORE UPDATE ON dim_cpq_property_definitions
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_clients_updated
    BEFORE UPDATE ON dim_cpq_clients
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_workflows_updated
    BEFORE UPDATE ON dim_cpq_workflow_templates
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_phases_updated
    BEFORE UPDATE ON dim_cpq_workflow_phases
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_forms_updated
    BEFORE UPDATE ON dim_cpq_form_templates
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_fields_updated
    BEFORE UPDATE ON dim_cpq_form_fields
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_automations_updated
    BEFORE UPDATE ON dim_cpq_automation_templates
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_projects_updated
    BEFORE UPDATE ON dim_cpq_projects
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

CREATE TRIGGER trg_cpq_submissions_updated
    BEFORE UPDATE ON fact_cpq_form_submissions
    FOR EACH ROW EXECUTE FUNCTION update_cpq_updated_at();

-- =============================================================================
-- COMMENTS (Documentation)
-- =============================================================================

COMMENT ON TABLE dim_cpq_property_categories IS 'Coperniq Project Property categories (Standard, Financial, Site & System, etc.)';
COMMENT ON TABLE dim_cpq_property_definitions IS 'The 100+ project properties from Coperniq platform';
COMMENT ON TABLE dim_cpq_clients IS 'Client records mirroring Coperniq Clients module';
COMMENT ON TABLE dim_cpq_workflow_templates IS 'Project and Request workflow definitions';
COMMENT ON TABLE dim_cpq_workflow_phases IS 'Workflow phases with SLA settings';
COMMENT ON TABLE dim_cpq_form_templates IS 'Form template definitions from Process Studio';
COMMENT ON TABLE dim_cpq_form_groups IS 'Form sections/groups for organizing fields';
COMMENT ON TABLE dim_cpq_form_fields IS 'Individual form fields with types and validation';
COMMENT ON TABLE dim_cpq_automation_templates IS 'Automation rules (triggers + actions)';
COMMENT ON TABLE dim_cpq_projects IS 'Project records for testing workflows';
COMMENT ON TABLE fact_cpq_form_submissions IS 'Form submission instances for testing';
