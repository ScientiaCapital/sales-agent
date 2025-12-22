-- =============================================================================
-- COPERNIQ 3.0 COMPLETE SCHEMA
-- =============================================================================
-- Purpose: Complete platform schema for Energy + MEP contractors
-- Target: Self-performing, $5-50M, multi-trade, asset-centric
-- Date: 2025-12-19
-- Based on: Market gap analysis - solving real contractor pain points
-- =============================================================================

-- =============================================================================
-- MODULE 1: REQUESTS (Sales Pipeline - Gap #1: Unified Install + Service)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    workflow_id UUID REFERENCES dim_cpq_workflow_templates(workflow_id),

    -- Identity
    title VARCHAR(255) NOT NULL,
    description TEXT,
    request_number VARCHAR(50),

    -- Status
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN (
        'new', 'contacted', 'qualified', 'proposal', 'negotiation', 'won', 'lost'
    )),
    current_phase_id UUID REFERENCES dim_cpq_workflow_phases(phase_id),

    -- Sales Info
    source VARCHAR(100),  -- Referral, Google, Direct, Partner
    referred_by VARCHAR(255),
    estimated_value DECIMAL(12, 2),
    estimated_size_kw DECIMAL(10, 2),  -- For solar
    trades JSONB DEFAULT '[]',  -- ["Solar", "HVAC", "Electrical"]

    -- Assignment
    assigned_to VARCHAR(255),
    team_members JSONB DEFAULT '[]',

    -- Close Info
    won_lost_reason VARCHAR(255),
    won_lost_date DATE,
    competitor_mentioned VARCHAR(100),  -- ServiceTitan, Procore, etc.

    -- Dynamic Properties
    properties JSONB DEFAULT '{}',

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_cpq_requests_client ON dim_cpq_requests(client_id);
CREATE INDEX idx_cpq_requests_status ON dim_cpq_requests(status);
CREATE INDEX idx_cpq_requests_assigned ON dim_cpq_requests(assigned_to);
CREATE INDEX idx_cpq_requests_created ON dim_cpq_requests(created_at DESC);

-- =============================================================================
-- MODULE 2: QUOTES & PROPOSALS (Aurora/OpenSolar Integration)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_quotes (
    quote_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES dim_cpq_requests(request_id),
    client_id UUID REFERENCES dim_cpq_clients(client_id),

    -- Identity
    quote_number VARCHAR(50),
    quote_type VARCHAR(50) DEFAULT 'internal' CHECK (quote_type IN (
        'internal', 'aurora', 'opensolar', 'solargraf', 'helioscope'
    )),

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'sent', 'viewed', 'changes_requested', 'approved', 'declined', 'expired'
    )),

    -- Pricing
    total_price DECIMAL(12, 2),
    system_size_kw DECIMAL(10, 2),
    price_per_watt DECIMAL(6, 2),
    battery_size_kwh DECIMAL(10, 2),

    -- Validity
    valid_until DATE,

    -- External Integration
    external_id VARCHAR(255),  -- Aurora/OpenSolar ID
    external_url VARCHAR(500),  -- Link to external proposal

    -- Documents
    pdf_url VARCHAR(500),

    -- Line Items
    line_items JSONB DEFAULT '[]',  -- [{description, quantity, unit_price, total}]

    -- Notes
    notes TEXT,
    internal_notes TEXT,

    -- Tracking
    sent_at TIMESTAMPTZ,
    viewed_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_quotes_request ON dim_cpq_quotes(request_id);
CREATE INDEX idx_cpq_quotes_client ON dim_cpq_quotes(client_id);
CREATE INDEX idx_cpq_quotes_status ON dim_cpq_quotes(status);

-- =============================================================================
-- MODULE 3: CONTRACTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_contracts (
    contract_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID REFERENCES dim_cpq_quotes(quote_id),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    project_id UUID,  -- Will be set when project created

    -- Identity
    contract_number VARCHAR(50),
    contract_type VARCHAR(50) DEFAULT 'purchase' CHECK (contract_type IN (
        'purchase', 'lease', 'ppa', 'service', 'financing', 'oam'
    )),

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'sent', 'viewed', 'signed', 'cancelled', 'expired'
    )),

    -- Value
    total_value DECIMAL(12, 2),

    -- Financing (for solar)
    financing_provider VARCHAR(100),  -- GoodLeap, Mosaic, Sunlight
    financing_term_months INTEGER,
    financing_apr DECIMAL(5, 2),
    monthly_payment DECIMAL(10, 2),

    -- E-Signature
    docusign_envelope_id VARCHAR(255),

    -- Dates
    signed_date DATE,
    effective_date DATE,
    expiration_date DATE,

    -- Documents
    document_url VARCHAR(500),

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_contracts_quote ON dim_cpq_contracts(quote_id);
CREATE INDEX idx_cpq_contracts_client ON dim_cpq_contracts(client_id);
CREATE INDEX idx_cpq_contracts_status ON dim_cpq_contracts(status);

-- =============================================================================
-- MODULE 4: WORK ORDERS (Gap #5: Self-Performing Dispatch)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_work_order_templates (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Type
    work_order_type VARCHAR(50) NOT NULL CHECK (work_order_type IN ('field', 'office')),
    category VARCHAR(100),  -- Install, Service, Inspection, Survey, Maintenance

    -- Defaults
    default_duration_hours DECIMAL(5, 2),
    default_instructions TEXT,
    default_checklist JSONB DEFAULT '[]',
    required_forms JSONB DEFAULT '[]',
    required_skills JSONB DEFAULT '[]',
    default_parts JSONB DEFAULT '[]',
    billable_default BOOLEAN DEFAULT TRUE,

    -- Classification
    trade VARCHAR(100),  -- Solar, HVAC, Electrical, Plumbing

    -- Dynamic Due Date (Jan 2025 feature)
    due_date_offset_days INTEGER,  -- Relative to creation

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_wo_templates_type ON dim_cpq_work_order_templates(work_order_type);
CREATE INDEX idx_cpq_wo_templates_trade ON dim_cpq_work_order_templates(trade);

-- Work Order Instances
CREATE TABLE IF NOT EXISTS dim_cpq_work_orders (
    work_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES dim_cpq_work_order_templates(template_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    request_id UUID REFERENCES dim_cpq_requests(request_id),
    asset_id UUID,  -- FK to assets, added later

    -- Identity
    work_order_number VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Type
    work_order_type VARCHAR(50) NOT NULL CHECK (work_order_type IN ('field', 'office')),
    category VARCHAR(100),

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'scheduled', 'dispatched', 'in_progress', 'on_hold',
        'completed', 'cancelled', 'invoiced'
    )),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN (
        'low', 'normal', 'high', 'urgent'
    )),

    -- Assignment
    assigned_to VARCHAR(255),
    team_members JSONB DEFAULT '[]',

    -- Schedule
    scheduled_start TIMESTAMPTZ,
    scheduled_end TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    estimated_hours DECIMAL(5, 2),
    actual_hours DECIMAL(5, 2),
    due_date DATE,

    -- Location
    site_address_street VARCHAR(255),
    site_address_city VARCHAR(100),
    site_address_state VARCHAR(50),
    site_address_zip VARCHAR(20),

    -- Parts & Materials
    requires_parts BOOLEAN DEFAULT FALSE,
    parts_list JSONB DEFAULT '[]',

    -- Checklist
    checklist_items JSONB DEFAULT '[]',  -- [{item, completed, completed_by, completed_at}]

    -- Field Data
    notes TEXT,
    photos JSONB DEFAULT '[]',
    signature_customer TEXT,  -- Base64 or URL
    signature_tech TEXT,

    -- Billing
    billable BOOLEAN DEFAULT TRUE,
    billed BOOLEAN DEFAULT FALSE,
    invoice_id UUID,  -- FK to invoices

    -- Linked Request (Dec 2025 feature)
    linked_request_id UUID REFERENCES dim_cpq_requests(request_id),

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(255)
);

CREATE INDEX idx_cpq_work_orders_project ON dim_cpq_work_orders(project_id);
CREATE INDEX idx_cpq_work_orders_client ON dim_cpq_work_orders(client_id);
CREATE INDEX idx_cpq_work_orders_status ON dim_cpq_work_orders(status);
CREATE INDEX idx_cpq_work_orders_assigned ON dim_cpq_work_orders(assigned_to);
CREATE INDEX idx_cpq_work_orders_scheduled ON dim_cpq_work_orders(scheduled_start);
CREATE INDEX idx_cpq_work_orders_due ON dim_cpq_work_orders(due_date);

-- =============================================================================
-- MODULE 5: ASSETS & SYSTEMS (Gap #2: Asset Lifecycle - THE DIFFERENTIATOR)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),

    -- Identity
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL CHECK (asset_type IN (
        'solar_system', 'battery', 'hvac_system', 'electrical_panel',
        'ev_charger', 'generator', 'other'
    )),

    -- Equipment Details
    serial_number VARCHAR(255),
    model VARCHAR(255),
    manufacturer VARCHAR(255),

    -- Installation
    install_date DATE,
    warranty_expiration DATE,

    -- System Specs (Solar)
    system_size_kw DECIMAL(10, 2),
    battery_capacity_kwh DECIMAL(10, 2),
    inverter_model VARCHAR(255),
    inverter_count INTEGER,
    panel_model VARCHAR(255),
    panel_count INTEGER,
    panel_wattage INTEGER,
    mount_type VARCHAR(50),  -- Roof, Ground, Carport
    azimuth DECIMAL(5, 2),
    tilt DECIMAL(5, 2),
    annual_production_kwh DECIMAL(12, 2),  -- Expected

    -- Utility Info (Critical for Solar)
    pto_date DATE,  -- Permission to Operate - THE KEY MILESTONE
    utility_company VARCHAR(255),
    utility_account VARCHAR(100),
    meter_number VARCHAR(100),
    rate_schedule VARCHAR(100),

    -- Monitoring Integration (Gap #3: Real-Time Monitoring)
    monitoring_enabled BOOLEAN DEFAULT FALSE,
    monitoring_provider VARCHAR(100),  -- Enphase, SolarEdge, Tesla, Sense
    monitoring_site_id VARCHAR(255),
    monitoring_api_key VARCHAR(255),  -- Encrypted
    last_reading_at TIMESTAMPTZ,

    -- Current Status (Updated by monitoring)
    current_status VARCHAR(50) DEFAULT 'unknown' CHECK (current_status IN (
        'normal', 'warning', 'error', 'offline', 'unknown'
    )),
    lifetime_kwh DECIMAL(15, 2),
    performance_ratio DECIMAL(5, 2),  -- Actual vs expected (%)

    -- Service Plan (O&M - Recurring Revenue)
    service_plan_id UUID,  -- FK to service_plans
    next_service_date DATE,
    oam_contract_value DECIMAL(10, 2),  -- Annual O&M value

    -- Site Info (if different from client)
    site_address_street VARCHAR(255),
    site_address_city VARCHAR(100),
    site_address_state VARCHAR(50),
    site_address_zip VARCHAR(20),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),

    -- Documents
    documents JSONB DEFAULT '[]',  -- [{name, url, type}]

    -- Dynamic Properties
    properties JSONB DEFAULT '{}',

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_cpq_assets_client ON dim_cpq_assets(client_id);
CREATE INDEX idx_cpq_assets_project ON dim_cpq_assets(project_id);
CREATE INDEX idx_cpq_assets_type ON dim_cpq_assets(asset_type);
CREATE INDEX idx_cpq_assets_status ON dim_cpq_assets(current_status);
CREATE INDEX idx_cpq_assets_pto ON dim_cpq_assets(pto_date);
CREATE INDEX idx_cpq_assets_monitoring ON dim_cpq_assets(monitoring_provider);

-- Add FK from work_orders to assets
ALTER TABLE dim_cpq_work_orders
ADD CONSTRAINT fk_work_order_asset
FOREIGN KEY (asset_id) REFERENCES dim_cpq_assets(asset_id);

-- =============================================================================
-- MODULE 6: ASSET MONITORING DATA (Gap #3: Real-Time Energy Monitoring)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_cpq_asset_readings (
    reading_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES dim_cpq_assets(asset_id),

    -- Timestamp
    reading_time TIMESTAMPTZ NOT NULL,

    -- Reading Type
    reading_type VARCHAR(50) NOT NULL CHECK (reading_type IN (
        'production', 'consumption', 'export', 'import',
        'battery_soc', 'status', 'alert'
    )),

    -- Value
    value DECIMAL(15, 4),
    unit VARCHAR(20),  -- kWh, kW, %, etc.

    -- Status (for status readings)
    status VARCHAR(50),

    -- Source
    source VARCHAR(100),  -- Enphase, SolarEdge, Tesla

    -- Raw Data
    raw_data JSONB,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Partition by month for performance (large dataset)
CREATE INDEX idx_cpq_readings_asset_time ON fact_cpq_asset_readings(asset_id, reading_time DESC);
CREATE INDEX idx_cpq_readings_time ON fact_cpq_asset_readings(reading_time DESC);
CREATE INDEX idx_cpq_readings_type ON fact_cpq_asset_readings(reading_type);

-- =============================================================================
-- MODULE 7: FLEET ALERTS (Proactive O&M - Nobody Else Has This)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_fleet_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES dim_cpq_assets(asset_id),
    client_id UUID REFERENCES dim_cpq_clients(client_id),

    -- Alert Info
    alert_type VARCHAR(100) NOT NULL CHECK (alert_type IN (
        'underperformance', 'offline', 'communication_loss',
        'inverter_error', 'panel_issue', 'battery_issue',
        'maintenance_due', 'warranty_expiring', 'pto_missing',
        'custom'
    )),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),

    -- Description
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Thresholds
    threshold_value DECIMAL(15, 4),
    actual_value DECIMAL(15, 4),
    threshold_unit VARCHAR(20),

    -- Status
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN (
        'new', 'acknowledged', 'in_progress', 'resolved', 'ignored'
    )),

    -- Resolution
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Auto-Actions
    created_work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_alerts_asset ON dim_cpq_fleet_alerts(asset_id);
CREATE INDEX idx_cpq_alerts_status ON dim_cpq_fleet_alerts(status);
CREATE INDEX idx_cpq_alerts_severity ON dim_cpq_fleet_alerts(severity);
CREATE INDEX idx_cpq_alerts_created ON dim_cpq_fleet_alerts(created_at DESC);

-- =============================================================================
-- MODULE 8: SERVICE PLANS (O&M Recurring Revenue)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_service_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    asset_id UUID REFERENCES dim_cpq_assets(asset_id),

    -- Plan Info
    plan_type VARCHAR(50) DEFAULT 'standard' CHECK (plan_type IN (
        'basic', 'standard', 'premium', 'custom'
    )),
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Billing
    annual_value DECIMAL(10, 2),
    billing_frequency VARCHAR(20) DEFAULT 'annual' CHECK (billing_frequency IN (
        'monthly', 'quarterly', 'semi_annual', 'annual'
    )),
    payment_amount DECIMAL(10, 2),  -- Per billing period

    -- Term
    start_date DATE NOT NULL,
    end_date DATE,
    auto_renew BOOLEAN DEFAULT TRUE,
    renewal_notice_days INTEGER DEFAULT 30,

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN (
        'pending', 'active', 'cancelled', 'expired', 'suspended'
    )),

    -- Coverage
    included_services JSONB DEFAULT '[]',  -- What's covered
    sla_response_hours INTEGER,  -- Response time SLA

    -- Visits
    visits_per_year INTEGER,
    visits_remaining INTEGER,
    last_visit_date DATE,
    next_visit_date DATE,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_service_plans_client ON dim_cpq_service_plans(client_id);
CREATE INDEX idx_cpq_service_plans_asset ON dim_cpq_service_plans(asset_id);
CREATE INDEX idx_cpq_service_plans_status ON dim_cpq_service_plans(status);

-- Add FK from assets to service_plans
ALTER TABLE dim_cpq_assets
ADD CONSTRAINT fk_asset_service_plan
FOREIGN KEY (service_plan_id) REFERENCES dim_cpq_service_plans(plan_id);

-- =============================================================================
-- MODULE 9: SCHEDULING & DISPATCH
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_schedule_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Event Info
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'work_order', 'meeting', 'time_off', 'training', 'travel', 'other'
    )),
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Time
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    all_day BOOLEAN DEFAULT FALSE,

    -- Assignment
    assignee_id VARCHAR(255),
    team_members JSONB DEFAULT '[]',

    -- Location
    location VARCHAR(255),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),

    -- Status
    status VARCHAR(50) DEFAULT 'scheduled' CHECK (status IN (
        'tentative', 'scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled'
    )),

    -- Display
    color VARCHAR(20),

    -- Recurring
    recurring_rule VARCHAR(255),  -- RRULE format
    parent_event_id UUID REFERENCES dim_cpq_schedule_events(event_id),

    -- Reminders
    reminders JSONB DEFAULT '[]',  -- [{minutes_before, method}]

    -- External Sync
    external_calendar_id VARCHAR(255),  -- Google/Outlook ID

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_events_start ON dim_cpq_schedule_events(start_time);
CREATE INDEX idx_cpq_events_assignee ON dim_cpq_schedule_events(assignee_id);
CREATE INDEX idx_cpq_events_work_order ON dim_cpq_schedule_events(work_order_id);
CREATE INDEX idx_cpq_events_status ON dim_cpq_schedule_events(status);

-- =============================================================================
-- MODULE 10: TIMESHEETS (Labor Tracking for Job Costing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_cpq_time_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),

    -- Entry Type
    entry_type VARCHAR(50) DEFAULT 'work' CHECK (entry_type IN (
        'work', 'travel', 'break', 'training', 'admin', 'pto'
    )),

    -- Time
    clock_in TIMESTAMPTZ NOT NULL,
    clock_out TIMESTAMPTZ,
    duration_hours DECIMAL(5, 2),
    billable_hours DECIMAL(5, 2),

    -- Rates
    hourly_rate DECIMAL(8, 2),
    total_cost DECIMAL(10, 2),

    -- Location (Mobile Geolocation)
    gps_clock_in JSONB,  -- {lat, lng, accuracy}
    gps_clock_out JSONB,

    -- Notes
    notes TEXT,

    -- Approval
    approved BOOLEAN DEFAULT FALSE,
    approved_by VARCHAR(255),
    approved_at TIMESTAMPTZ,

    -- Payroll
    payroll_exported BOOLEAN DEFAULT FALSE,
    payroll_exported_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_time_user ON fact_cpq_time_entries(user_id);
CREATE INDEX idx_cpq_time_work_order ON fact_cpq_time_entries(work_order_id);
CREATE INDEX idx_cpq_time_project ON fact_cpq_time_entries(project_id);
CREATE INDEX idx_cpq_time_date ON fact_cpq_time_entries(clock_in);

-- =============================================================================
-- MODULE 11: INVOICES (AR)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_invoices (
    invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Identity
    invoice_number VARCHAR(50) NOT NULL,
    invoice_type VARCHAR(50) DEFAULT 'standard' CHECK (invoice_type IN (
        'standard', 'progress', 'final', 'service', 'recurring', 'credit_memo'
    )),

    -- Status
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN (
        'draft', 'sent', 'viewed', 'partial', 'paid', 'overdue', 'void', 'disputed'
    )),

    -- Dates
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,

    -- Amounts
    subtotal DECIMAL(12, 2) NOT NULL DEFAULT 0,
    tax_rate DECIMAL(5, 2) DEFAULT 0,
    tax_amount DECIMAL(12, 2) DEFAULT 0,
    discount_amount DECIMAL(12, 2) DEFAULT 0,
    total DECIMAL(12, 2) NOT NULL DEFAULT 0,
    amount_paid DECIMAL(12, 2) DEFAULT 0,
    balance_due DECIMAL(12, 2) NOT NULL DEFAULT 0,

    -- Terms
    payment_terms VARCHAR(50),  -- Net 30, Due on Receipt, etc.

    -- Line Items
    line_items JSONB DEFAULT '[]',  -- [{description, quantity, unit_price, total, tax}]

    -- Notes
    notes TEXT,
    internal_notes TEXT,

    -- Delivery
    sent_at TIMESTAMPTZ,
    viewed_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,

    -- Payment Link (Dec 2025 feature)
    payment_link VARCHAR(500),

    -- Documents
    pdf_url VARCHAR(500),
    attachments JSONB DEFAULT '[]',  -- Invoice email attachments (Dec 2025)

    -- QuickBooks Sync
    quickbooks_id VARCHAR(255),
    quickbooks_synced_at TIMESTAMPTZ,

    -- AI Invoice (Dec 2025 feature)
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_generated_at TIMESTAMPTZ,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_invoices_client ON dim_cpq_invoices(client_id);
CREATE INDEX idx_cpq_invoices_project ON dim_cpq_invoices(project_id);
CREATE INDEX idx_cpq_invoices_status ON dim_cpq_invoices(status);
CREATE INDEX idx_cpq_invoices_due ON dim_cpq_invoices(due_date);
CREATE INDEX idx_cpq_invoices_qb ON dim_cpq_invoices(quickbooks_id);

-- =============================================================================
-- MODULE 12: PAYMENTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_cpq_payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES dim_cpq_invoices(invoice_id),
    client_id UUID REFERENCES dim_cpq_clients(client_id),

    -- Payment Info
    payment_method VARCHAR(50) CHECK (payment_method IN (
        'check', 'ach', 'credit_card', 'debit_card', 'cash', 'wire', 'financing', 'other'
    )),
    payment_date DATE NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,

    -- Reference
    reference_number VARCHAR(100),  -- Check #, Transaction ID

    -- Processing
    processor VARCHAR(100),  -- Stripe, Square, etc.
    processor_transaction_id VARCHAR(255),
    processor_fee DECIMAL(8, 2),

    -- Notes
    notes TEXT,

    -- QuickBooks Sync
    quickbooks_id VARCHAR(255),
    quickbooks_synced_at TIMESTAMPTZ,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_payments_invoice ON fact_cpq_payments(invoice_id);
CREATE INDEX idx_cpq_payments_client ON fact_cpq_payments(client_id);
CREATE INDEX idx_cpq_payments_date ON fact_cpq_payments(payment_date);

-- =============================================================================
-- MODULE 13: VENDORS & BILLS (AP)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_vendors (
    vendor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    vendor_type VARCHAR(50) DEFAULT 'supplier' CHECK (vendor_type IN (
        'supplier', 'subcontractor', 'equipment', 'service', 'utility'
    )),

    -- Contact
    contact_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),

    -- Address
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),

    -- Terms
    payment_terms VARCHAR(50),  -- Net 30, etc.

    -- Tax
    tax_id VARCHAR(50),  -- EIN/SSN for 1099
    w9_on_file BOOLEAN DEFAULT FALSE,
    w9_received_date DATE,

    -- Insurance (for subs)
    insurance_company VARCHAR(255),
    insurance_policy VARCHAR(100),
    insurance_expiration DATE,

    -- QuickBooks Sync
    quickbooks_id VARCHAR(255),

    -- Notes
    notes TEXT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_vendors_name ON dim_cpq_vendors(name);
CREATE INDEX idx_cpq_vendors_type ON dim_cpq_vendors(vendor_type);

-- Bills (AP)
CREATE TABLE IF NOT EXISTS dim_cpq_bills (
    bill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID REFERENCES dim_cpq_vendors(vendor_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Identity
    bill_number VARCHAR(100),

    -- Status
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'draft', 'pending', 'approved', 'paid', 'partial', 'void'
    )),

    -- Dates
    bill_date DATE NOT NULL,
    due_date DATE,

    -- Amounts
    subtotal DECIMAL(12, 2) NOT NULL DEFAULT 0,
    tax_amount DECIMAL(12, 2) DEFAULT 0,
    total DECIMAL(12, 2) NOT NULL DEFAULT 0,
    amount_paid DECIMAL(12, 2) DEFAULT 0,

    -- Category
    category VARCHAR(100),  -- Materials, Labor, Equipment, Permit, etc.

    -- Line Items
    line_items JSONB DEFAULT '[]',

    -- Documents
    document_url VARCHAR(500),

    -- QuickBooks Sync
    quickbooks_id VARCHAR(255),
    quickbooks_synced_at TIMESTAMPTZ,

    -- Approval
    approved_by VARCHAR(255),
    approved_at TIMESTAMPTZ,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_bills_vendor ON dim_cpq_bills(vendor_id);
CREATE INDEX idx_cpq_bills_project ON dim_cpq_bills(project_id);
CREATE INDEX idx_cpq_bills_status ON dim_cpq_bills(status);
CREATE INDEX idx_cpq_bills_due ON dim_cpq_bills(due_date);

-- =============================================================================
-- MODULE 14: INVENTORY
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_inventory_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    sku VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Category
    category VARCHAR(100) CHECK (category IN (
        'solar_panel', 'inverter', 'battery', 'racking', 'electrical',
        'hvac', 'plumbing', 'tools', 'consumables', 'other'
    )),

    -- Details
    manufacturer VARCHAR(255),
    model VARCHAR(255),

    -- Pricing
    unit_cost DECIMAL(10, 2),  -- Purchase cost
    unit_price DECIMAL(10, 2),  -- Sell price

    -- Inventory
    quantity_on_hand INTEGER DEFAULT 0,
    quantity_allocated INTEGER DEFAULT 0,  -- Reserved for jobs
    quantity_available INTEGER DEFAULT 0,  -- Calculated
    reorder_point INTEGER,

    -- Units
    unit_of_measure VARCHAR(20) DEFAULT 'each',  -- each, ft, box, etc.

    -- Vendor
    preferred_vendor_id UUID REFERENCES dim_cpq_vendors(vendor_id),

    -- QuickBooks Sync
    quickbooks_id VARCHAR(255),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_inventory_sku ON dim_cpq_inventory_items(sku);
CREATE INDEX idx_cpq_inventory_category ON dim_cpq_inventory_items(category);

-- =============================================================================
-- MODULE 15: COMMUNICATIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_cpq_communications (
    communication_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),
    request_id UUID REFERENCES dim_cpq_requests(request_id),
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Channel
    channel VARCHAR(50) NOT NULL CHECK (channel IN (
        'call', 'email', 'sms', 'portal', 'in_person', 'other'
    )),
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('inbound', 'outbound')),

    -- Status
    status VARCHAR(50) CHECK (status IN (
        'completed', 'missed', 'voicemail', 'bounced', 'delivered', 'opened', 'clicked'
    )),

    -- Content
    from_address VARCHAR(255),  -- Email/phone
    to_address VARCHAR(255),
    subject VARCHAR(255),
    body TEXT,

    -- Call Specific
    duration_seconds INTEGER,
    recording_url VARCHAR(500),  -- Call Recording Disclosure (Dec 2025)
    disposition VARCHAR(100),  -- Answered, No Answer, Left VM, etc.

    -- AI Analysis
    sentiment VARCHAR(20),  -- Positive, Negative, Neutral
    summary TEXT,  -- AI-generated summary

    -- User
    user_id VARCHAR(255),

    -- External
    external_id VARCHAR(255),  -- Nylas/Twilio ID

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_comms_client ON fact_cpq_communications(client_id);
CREATE INDEX idx_cpq_comms_project ON fact_cpq_communications(project_id);
CREATE INDEX idx_cpq_comms_channel ON fact_cpq_communications(channel);
CREATE INDEX idx_cpq_comms_created ON fact_cpq_communications(created_at DESC);

-- =============================================================================
-- MODULE 16: DOCUMENTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES dim_cpq_clients(client_id),
    project_id UUID REFERENCES dim_cpq_projects(project_id),
    asset_id UUID REFERENCES dim_cpq_assets(asset_id),
    work_order_id UUID REFERENCES dim_cpq_work_orders(work_order_id),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- File Info
    file_type VARCHAR(100),  -- MIME type
    file_size INTEGER,  -- Bytes
    storage_url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),

    -- Category
    category VARCHAR(100) CHECK (category IN (
        'contract', 'permit', 'photo', 'form', 'manual', 'warranty',
        'invoice', 'report', 'drawing', 'other'
    )),
    folder VARCHAR(255),  -- Virtual folder path

    -- Form Folders (Oct 2025 feature)
    form_id UUID,
    form_section VARCHAR(100),

    -- Access
    is_public BOOLEAN DEFAULT FALSE,  -- Visible in client portal

    -- Audit
    uploaded_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_docs_client ON dim_cpq_documents(client_id);
CREATE INDEX idx_cpq_docs_project ON dim_cpq_documents(project_id);
CREATE INDEX idx_cpq_docs_category ON dim_cpq_documents(category);

-- =============================================================================
-- MODULE 17: USERS & TEAMS
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,

    -- Role
    role VARCHAR(50) DEFAULT 'member' CHECK (role IN (
        'admin', 'manager', 'office', 'field', 'sales', 'read_only'
    )),

    -- Contact
    phone VARCHAR(50),

    -- Rates
    hourly_rate DECIMAL(8, 2),  -- Cost/pay rate
    billable_rate DECIMAL(8, 2),  -- Bill rate to customers

    -- Dispatch
    can_dispatch BOOLEAN DEFAULT FALSE,
    skills JSONB DEFAULT '[]',  -- Certifications, capabilities
    trades JSONB DEFAULT '[]',  -- Solar, HVAC, Electrical

    -- Schedule
    availability JSONB DEFAULT '{}',  -- Weekly schedule
    calendar_color VARCHAR(20),

    -- Mobile
    mobile_geolocation_enabled BOOLEAN DEFAULT FALSE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,

    -- External
    supabase_user_id UUID,  -- Link to auth.users

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_users_email ON dim_cpq_users(email);
CREATE INDEX idx_cpq_users_role ON dim_cpq_users(role);
CREATE INDEX idx_cpq_users_active ON dim_cpq_users(is_active);

-- Hubs (Teams/Departments)
CREATE TABLE IF NOT EXISTS dim_cpq_hubs (
    hub_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Type
    hub_type VARCHAR(50) CHECK (hub_type IN (
        'department', 'region', 'trade', 'team'
    )),

    -- Members
    members JSONB DEFAULT '[]',  -- User IDs
    managers JSONB DEFAULT '[]',  -- Manager user IDs

    -- Smart Views
    smart_views JSONB DEFAULT '[]',  -- Saved filters

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_hubs_name ON dim_cpq_hubs(name);
CREATE INDEX idx_cpq_hubs_type ON dim_cpq_hubs(hub_type);

-- =============================================================================
-- MODULE 18: INTEGRATIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_integrations (
    integration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Type
    integration_type VARCHAR(100) NOT NULL CHECK (integration_type IN (
        'quickbooks_online', 'quickbooks_desktop',
        'aurora', 'opensolar', 'solargraf', 'helioscope',
        'enphase', 'solaredge', 'tesla', 'sense',
        'nylas', 'twilio',
        'google_calendar', 'outlook_calendar',
        'docusign', 'pandadoc',
        'goodleap', 'mosaic', 'sunlight',
        'stripe', 'square',
        'custom_webhook'
    )),

    -- Status
    status VARCHAR(50) DEFAULT 'disconnected' CHECK (status IN (
        'connected', 'disconnected', 'error', 'pending'
    )),

    -- Account
    external_account_id VARCHAR(255),
    external_account_name VARCHAR(255),

    -- Auth (encrypted)
    credentials JSONB DEFAULT '{}',  -- Tokens, API keys

    -- Sync
    last_sync_at TIMESTAMPTZ,
    last_error TEXT,
    sync_settings JSONB DEFAULT '{}',  -- What to sync, frequency

    -- Webhook
    webhook_url VARCHAR(500),
    webhook_secret VARCHAR(255),

    -- Audit
    connected_by VARCHAR(255),
    connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_integrations_type ON dim_cpq_integrations(integration_type);
CREATE INDEX idx_cpq_integrations_status ON dim_cpq_integrations(status);

-- =============================================================================
-- MODULE 19: ANALYTICS DASHBOARDS
-- =============================================================================

CREATE TABLE IF NOT EXISTS dim_cpq_dashboards (
    dashboard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name VARCHAR(255) NOT NULL,
    description TEXT,
    emoji VARCHAR(10),  -- Dashboard icon

    -- Ownership
    owner_id VARCHAR(255),

    -- Access
    access_level VARCHAR(50) DEFAULT 'private' CHECK (access_level IN (
        'private', 'team', 'company'
    )),
    shared_with JSONB DEFAULT '[]',  -- User/team/role IDs

    -- Hub
    hub_id UUID REFERENCES dim_cpq_hubs(hub_id),

    -- Layout
    layout JSONB DEFAULT '[]',  -- Widget positions

    -- Status
    is_default BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_dashboards_owner ON dim_cpq_dashboards(owner_id);

-- Widgets
CREATE TABLE IF NOT EXISTS dim_cpq_widgets (
    widget_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id UUID REFERENCES dim_cpq_dashboards(dashboard_id) ON DELETE CASCADE,

    -- Identity
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),

    -- Type
    widget_type VARCHAR(50) NOT NULL CHECK (widget_type IN (
        'kpi', 'bar', 'line', 'funnel', 'timeline',
        'pipeline', 'pie', 'doughnut', 'leaderboard'
    )),

    -- Data Source
    module VARCHAR(50) NOT NULL CHECK (module IN (
        'clients', 'requests', 'projects', 'work_orders', 'assets', 'invoices'
    )),

    -- Measure
    measure VARCHAR(100) NOT NULL,  -- Count, Sum(field), Avg(field)
    aggregation VARCHAR(20),  -- count, sum, avg, min, max

    -- Grouping
    group_by VARCHAR(100),

    -- Filters
    filters JSONB DEFAULT '[]',

    -- Time
    time_range VARCHAR(50),  -- this_week, this_month, this_quarter, this_year
    trend_enabled BOOLEAN DEFAULT FALSE,

    -- Position
    position JSONB DEFAULT '{}',  -- {x, y, w, h}

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpq_widgets_dashboard ON dim_cpq_widgets(dashboard_id);

-- =============================================================================
-- ADD MISSING FKs TO EXISTING TABLES
-- =============================================================================

-- Add request_id, quote_id, contract_id to projects
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'dim_cpq_projects' AND column_name = 'request_id') THEN
        ALTER TABLE dim_cpq_projects ADD COLUMN request_id UUID REFERENCES dim_cpq_requests(request_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'dim_cpq_projects' AND column_name = 'quote_id') THEN
        ALTER TABLE dim_cpq_projects ADD COLUMN quote_id UUID REFERENCES dim_cpq_quotes(quote_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'dim_cpq_projects' AND column_name = 'contract_id') THEN
        ALTER TABLE dim_cpq_projects ADD COLUMN contract_id UUID REFERENCES dim_cpq_contracts(contract_id);
    END IF;
END $$;

-- Add invoice_id FK to work_orders
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.constraints
                   WHERE constraint_name = 'fk_work_order_invoice') THEN
        ALTER TABLE dim_cpq_work_orders
        ADD CONSTRAINT fk_work_order_invoice
        FOREIGN KEY (invoice_id) REFERENCES dim_cpq_invoices(invoice_id);
    END IF;
END $$;

-- Add client fields for billing
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'dim_cpq_clients' AND column_name = 'quickbooks_id') THEN
        ALTER TABLE dim_cpq_clients
        ADD COLUMN quickbooks_id VARCHAR(255),
        ADD COLUMN payment_terms VARCHAR(50),
        ADD COLUMN tax_exempt BOOLEAN DEFAULT FALSE,
        ADD COLUMN tags JSONB DEFAULT '[]';
    END IF;
END $$;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all new tables
ALTER TABLE dim_cpq_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_work_order_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_cpq_asset_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_fleet_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_service_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_schedule_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_cpq_time_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_cpq_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_inventory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_cpq_communications ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_hubs ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_cpq_widgets ENABLE ROW LEVEL SECURITY;

-- Service role full access
CREATE POLICY "cpq_requests_service" ON dim_cpq_requests FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_quotes_service" ON dim_cpq_quotes FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_contracts_service" ON dim_cpq_contracts FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_wo_templates_service" ON dim_cpq_work_order_templates FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_work_orders_service" ON dim_cpq_work_orders FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_assets_service" ON dim_cpq_assets FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_readings_service" ON fact_cpq_asset_readings FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_alerts_service" ON dim_cpq_fleet_alerts FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_service_plans_service" ON dim_cpq_service_plans FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_events_service" ON dim_cpq_schedule_events FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_time_service" ON fact_cpq_time_entries FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_invoices_service" ON dim_cpq_invoices FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_payments_service" ON fact_cpq_payments FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_vendors_service" ON dim_cpq_vendors FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_bills_service" ON dim_cpq_bills FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_inventory_service" ON dim_cpq_inventory_items FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_comms_service" ON fact_cpq_communications FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_docs_service" ON dim_cpq_documents FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_users_service" ON dim_cpq_users FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_hubs_service" ON dim_cpq_hubs FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_integrations_service" ON dim_cpq_integrations FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_dashboards_service" ON dim_cpq_dashboards FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "cpq_widgets_service" ON dim_cpq_widgets FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Anon/authenticated read access (for Academy)
CREATE POLICY "cpq_requests_read" ON dim_cpq_requests FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_quotes_read" ON dim_cpq_quotes FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_contracts_read" ON dim_cpq_contracts FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_wo_templates_read" ON dim_cpq_work_order_templates FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_work_orders_read" ON dim_cpq_work_orders FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_assets_read" ON dim_cpq_assets FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_readings_read" ON fact_cpq_asset_readings FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_alerts_read" ON dim_cpq_fleet_alerts FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_service_plans_read" ON dim_cpq_service_plans FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_events_read" ON dim_cpq_schedule_events FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_invoices_read" ON dim_cpq_invoices FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_vendors_read" ON dim_cpq_vendors FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_inventory_read" ON dim_cpq_inventory_items FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_users_read" ON dim_cpq_users FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_hubs_read" ON dim_cpq_hubs FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_dashboards_read" ON dim_cpq_dashboards FOR SELECT TO anon, authenticated USING (TRUE);
CREATE POLICY "cpq_widgets_read" ON dim_cpq_widgets FOR SELECT TO anon, authenticated USING (TRUE);

-- =============================================================================
-- SUMMARY
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '=== COPERNIQ 3.0 COMPLETE SCHEMA ===' ;
    RAISE NOTICE 'New Tables Created: 21';
    RAISE NOTICE '';
    RAISE NOTICE 'SALES PIPELINE:';
    RAISE NOTICE '  - dim_cpq_requests (leads, opportunities)';
    RAISE NOTICE '  - dim_cpq_quotes (proposals, Aurora integration)';
    RAISE NOTICE '  - dim_cpq_contracts (signed agreements)';
    RAISE NOTICE '';
    RAISE NOTICE 'FIELD OPERATIONS:';
    RAISE NOTICE '  - dim_cpq_work_order_templates';
    RAISE NOTICE '  - dim_cpq_work_orders';
    RAISE NOTICE '  - dim_cpq_schedule_events';
    RAISE NOTICE '  - fact_cpq_time_entries';
    RAISE NOTICE '';
    RAISE NOTICE 'ASSETS & MONITORING (THE DIFFERENTIATOR):';
    RAISE NOTICE '  - dim_cpq_assets (installed equipment)';
    RAISE NOTICE '  - fact_cpq_asset_readings (real-time data)';
    RAISE NOTICE '  - dim_cpq_fleet_alerts (proactive alerts)';
    RAISE NOTICE '  - dim_cpq_service_plans (O&M contracts)';
    RAISE NOTICE '';
    RAISE NOTICE 'FINANCIAL:';
    RAISE NOTICE '  - dim_cpq_invoices';
    RAISE NOTICE '  - fact_cpq_payments';
    RAISE NOTICE '  - dim_cpq_vendors';
    RAISE NOTICE '  - dim_cpq_bills';
    RAISE NOTICE '  - dim_cpq_inventory_items';
    RAISE NOTICE '';
    RAISE NOTICE 'COMMUNICATIONS:';
    RAISE NOTICE '  - fact_cpq_communications';
    RAISE NOTICE '  - dim_cpq_documents';
    RAISE NOTICE '';
    RAISE NOTICE 'TEAM & ANALYTICS:';
    RAISE NOTICE '  - dim_cpq_users';
    RAISE NOTICE '  - dim_cpq_hubs';
    RAISE NOTICE '  - dim_cpq_integrations';
    RAISE NOTICE '  - dim_cpq_dashboards';
    RAISE NOTICE '  - dim_cpq_widgets';
    RAISE NOTICE '';
    RAISE NOTICE 'TOTAL COPERNIQ 3.0 TABLES: 32';
    RAISE NOTICE '======================================';
END $$;
