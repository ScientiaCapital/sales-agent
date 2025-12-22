-- =====================================================
-- COPERNIQ 3.0 - TRADE-SPECIFIC WORKFLOW TEMPLATES
-- =====================================================
-- Best-in-class workflows for Energy + MEP contractors
-- These templates can be added to any Coperniq hub
--
-- Trades Covered:
--   1. SOLAR (Residential + Commercial)
--   2. HVAC (Install + Service + Maintenance)
--   3. ELECTRICAL (Panel Upgrades + EV Chargers + Service)
--   4. PLUMBING (Install + Service)
--
-- Created: 2025-12-19
-- Author: Tim Kipper (GTME)
-- =====================================================

-- =====================================================
-- TRADE CATEGORIES
-- =====================================================
CREATE TABLE IF NOT EXISTS dim_cpq_trade_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    color TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO dim_cpq_trade_categories (code, name, description, icon, color, sort_order) VALUES
('SOLAR', 'Solar', 'Photovoltaic systems, battery storage, solar thermal', '☀️', '#F59E0B', 1),
('HVAC', 'HVAC', 'Heating, ventilation, air conditioning, heat pumps', '❄️', '#3B82F6', 2),
('ELECTRICAL', 'Electrical', 'Panel upgrades, EV chargers, wiring, lighting', '⚡', '#8B5CF6', 3),
('PLUMBING', 'Plumbing', 'Water heaters, pipes, fixtures, drains', '🔧', '#10B981', 4),
('ROOFING', 'Roofing', 'Roof repairs, replacements, solar-ready roofing', '🏠', '#6B7280', 5),
('BATTERY', 'Battery Storage', 'Home batteries, backup systems, microgrids', '🔋', '#EC4899', 6);

-- =====================================================
-- 1. SOLAR WORKFLOW TEMPLATES
-- =====================================================

-- Solar Residential Install Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-solar-res-install',
    'Solar Residential Installation',
    'Complete residential solar PV installation workflow from lead to PTO',
    'SOLAR',
    'PROJECT',
    '[
        {
            "id": "welcome",
            "name": "Welcome",
            "description": "Initial customer contact and qualification",
            "order": 1,
            "required_forms": ["site-info-form", "utility-bill-upload"],
            "automations": ["send-welcome-email", "schedule-site-survey"],
            "sla_days": 2
        },
        {
            "id": "site-survey",
            "name": "Site Survey",
            "description": "On-site assessment, measurements, photos",
            "order": 2,
            "required_forms": ["site-survey-form", "roof-assessment"],
            "work_order_template": "wo-site-survey",
            "sla_days": 5
        },
        {
            "id": "design",
            "name": "System Design",
            "description": "Aurora/Solargraf design, equipment selection",
            "order": 3,
            "required_forms": ["design-specs-form"],
            "integrations": ["aurora", "solargraf"],
            "sla_days": 3
        },
        {
            "id": "proposal",
            "name": "Proposal & Contract",
            "description": "Quote presentation, financing options, contract signing",
            "order": 4,
            "required_forms": ["contract-form", "financing-application"],
            "automations": ["send-proposal-email"],
            "sla_days": 7
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "AHJ permit application, utility interconnection application",
            "order": 5,
            "required_forms": ["permit-application", "interconnection-app"],
            "sla_days": 14
        },
        {
            "id": "procurement",
            "name": "Procurement",
            "description": "Equipment ordering, delivery scheduling",
            "order": 6,
            "required_forms": ["equipment-checklist"],
            "sla_days": 7
        },
        {
            "id": "installation",
            "name": "Installation",
            "description": "Physical installation of solar system",
            "order": 7,
            "required_forms": ["install-checklist", "commissioning-form"],
            "work_order_template": "wo-solar-install",
            "sla_days": 3
        },
        {
            "id": "inspection",
            "name": "Inspection",
            "description": "AHJ final inspection, utility inspection",
            "order": 8,
            "required_forms": ["inspection-checklist"],
            "work_order_template": "wo-inspection",
            "sla_days": 7
        },
        {
            "id": "pto",
            "name": "Permission to Operate",
            "description": "Utility PTO approval, system activation",
            "order": 9,
            "required_forms": ["pto-confirmation"],
            "automations": ["create-asset-record", "start-monitoring"],
            "sla_days": 14
        },
        {
            "id": "closeout",
            "name": "Project Closeout",
            "description": "Final documentation, customer handoff, O&M setup",
            "order": 10,
            "required_forms": ["closeout-checklist", "customer-handoff"],
            "automations": ["send-welcome-kit", "setup-service-plan"],
            "sla_days": 3
        }
    ]'::jsonb,
    60,
    true
);

-- Solar Commercial Install Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-solar-comm-install',
    'Solar Commercial Installation',
    'Commercial/C&I solar installation with engineering and multi-phase construction',
    'SOLAR',
    'PROJECT',
    '[
        {
            "id": "qualification",
            "name": "Qualification",
            "description": "Initial assessment, utility data, site access",
            "order": 1,
            "required_forms": ["commercial-qualification", "utility-data-request"],
            "sla_days": 5
        },
        {
            "id": "site-assessment",
            "name": "Site Assessment",
            "description": "Detailed site survey, structural analysis",
            "order": 2,
            "required_forms": ["commercial-site-survey", "structural-assessment"],
            "work_order_template": "wo-commercial-survey",
            "sla_days": 10
        },
        {
            "id": "engineering",
            "name": "Engineering",
            "description": "Structural engineering, electrical engineering, stamped drawings",
            "order": 3,
            "required_forms": ["engineering-specs", "structural-calcs"],
            "sla_days": 21
        },
        {
            "id": "proposal",
            "name": "Proposal & Contract",
            "description": "Detailed proposal, PPA/lease options, contract negotiation",
            "order": 4,
            "required_forms": ["commercial-contract", "ppa-agreement"],
            "sla_days": 14
        },
        {
            "id": "permitting",
            "name": "Permitting & Interconnection",
            "description": "Building permits, utility interconnection study",
            "order": 5,
            "required_forms": ["commercial-permit-app", "interconnection-study"],
            "sla_days": 30
        },
        {
            "id": "procurement",
            "name": "Procurement",
            "description": "Equipment ordering, racking, inverters, transformers",
            "order": 6,
            "required_forms": ["commercial-bom", "delivery-schedule"],
            "sla_days": 21
        },
        {
            "id": "mobilization",
            "name": "Mobilization",
            "description": "Site prep, staging, safety planning",
            "order": 7,
            "required_forms": ["mobilization-plan", "safety-plan"],
            "sla_days": 5
        },
        {
            "id": "construction",
            "name": "Construction",
            "description": "Multi-phase installation, daily logs",
            "order": 8,
            "required_forms": ["daily-log", "progress-photos"],
            "work_order_template": "wo-commercial-install",
            "sla_days": 30
        },
        {
            "id": "commissioning",
            "name": "Commissioning",
            "description": "System testing, performance verification",
            "order": 9,
            "required_forms": ["commissioning-report", "iv-curves"],
            "sla_days": 5
        },
        {
            "id": "inspection",
            "name": "Final Inspection",
            "description": "AHJ inspection, utility witness test",
            "order": 10,
            "required_forms": ["final-inspection", "witness-test"],
            "sla_days": 14
        },
        {
            "id": "pto",
            "name": "Permission to Operate",
            "description": "Utility PTO, system energization",
            "order": 11,
            "required_forms": ["pto-confirmation", "energization-checklist"],
            "sla_days": 14
        },
        {
            "id": "closeout",
            "name": "Project Closeout",
            "description": "As-builts, O&M manuals, warranty registration",
            "order": 12,
            "required_forms": ["as-built-drawings", "warranty-docs", "om-manual"],
            "sla_days": 7
        }
    ]'::jsonb,
    180,
    true
);

-- Solar O&M Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-solar-oam',
    'Solar O&M Service',
    'Operations & Maintenance service workflow for solar systems',
    'SOLAR',
    'WORK_ORDER',
    '[
        {
            "id": "dispatch",
            "name": "Dispatch",
            "description": "Technician assignment, scheduling",
            "order": 1,
            "sla_hours": 4
        },
        {
            "id": "diagnosis",
            "name": "Diagnosis",
            "description": "System assessment, fault identification",
            "order": 2,
            "required_forms": ["oam-diagnostic-form"],
            "sla_hours": 2
        },
        {
            "id": "repair",
            "name": "Repair/Replace",
            "description": "Component repair or replacement",
            "order": 3,
            "required_forms": ["repair-log", "parts-used"],
            "sla_hours": 4
        },
        {
            "id": "verification",
            "name": "Verification",
            "description": "System performance verification post-repair",
            "order": 4,
            "required_forms": ["performance-verification"],
            "sla_hours": 1
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Documentation, customer sign-off",
            "order": 5,
            "required_forms": ["service-report", "customer-signature"],
            "sla_hours": 1
        }
    ]'::jsonb,
    1,
    true
);

-- =====================================================
-- 2. HVAC WORKFLOW TEMPLATES
-- =====================================================

-- HVAC Residential Install Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-hvac-res-install',
    'HVAC Residential Installation',
    'Complete HVAC system installation including load calc, equipment, and commissioning',
    'HVAC',
    'PROJECT',
    '[
        {
            "id": "inquiry",
            "name": "Inquiry",
            "description": "Initial customer contact, basic qualification",
            "order": 1,
            "required_forms": ["hvac-inquiry-form"],
            "sla_days": 1
        },
        {
            "id": "load-calc",
            "name": "Load Calculation",
            "description": "Manual J load calculation, equipment sizing",
            "order": 2,
            "required_forms": ["manual-j-form", "equipment-sizing"],
            "work_order_template": "wo-hvac-assessment",
            "sla_days": 3
        },
        {
            "id": "proposal",
            "name": "Proposal",
            "description": "Equipment options, pricing, rebates",
            "order": 3,
            "required_forms": ["hvac-proposal", "rebate-application"],
            "sla_days": 2
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Contract signing, deposit collection",
            "order": 4,
            "required_forms": ["hvac-contract"],
            "sla_days": 3
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "Mechanical permit application",
            "order": 5,
            "required_forms": ["mechanical-permit"],
            "sla_days": 7
        },
        {
            "id": "equipment-order",
            "name": "Equipment Order",
            "description": "Order equipment, schedule delivery",
            "order": 6,
            "required_forms": ["equipment-order-form"],
            "sla_days": 5
        },
        {
            "id": "installation",
            "name": "Installation",
            "description": "Remove old system, install new equipment",
            "order": 7,
            "required_forms": ["hvac-install-checklist", "refrigerant-log"],
            "work_order_template": "wo-hvac-install",
            "sla_days": 2
        },
        {
            "id": "startup",
            "name": "Start-Up & Commissioning",
            "description": "System startup, airflow balancing, commissioning",
            "order": 8,
            "required_forms": ["commissioning-checklist", "airflow-readings"],
            "sla_days": 1
        },
        {
            "id": "inspection",
            "name": "Inspection",
            "description": "AHJ mechanical inspection",
            "order": 9,
            "required_forms": ["inspection-result"],
            "sla_days": 5
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer training, warranty registration, maintenance plan",
            "order": 10,
            "required_forms": ["customer-training", "warranty-registration"],
            "automations": ["setup-maintenance-plan"],
            "sla_days": 2
        }
    ]'::jsonb,
    30,
    true
);

-- HVAC Service Call Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-hvac-service',
    'HVAC Service Call',
    'Standard HVAC service/repair call workflow',
    'HVAC',
    'WORK_ORDER',
    '[
        {
            "id": "triage",
            "name": "Triage",
            "description": "Customer call, issue identification, scheduling",
            "order": 1,
            "required_forms": ["service-intake-form"],
            "sla_hours": 2
        },
        {
            "id": "dispatch",
            "name": "Dispatch",
            "description": "Technician assignment",
            "order": 2,
            "sla_hours": 1
        },
        {
            "id": "diagnosis",
            "name": "Diagnosis",
            "description": "On-site troubleshooting, fault identification",
            "order": 3,
            "required_forms": ["hvac-diagnostic-form"],
            "sla_hours": 2
        },
        {
            "id": "approval",
            "name": "Customer Approval",
            "description": "Repair estimate, customer authorization",
            "order": 4,
            "required_forms": ["repair-estimate", "customer-approval"],
            "sla_hours": 4
        },
        {
            "id": "repair",
            "name": "Repair",
            "description": "Execute repair, parts replacement",
            "order": 5,
            "required_forms": ["repair-log", "parts-used"],
            "sla_hours": 4
        },
        {
            "id": "verification",
            "name": "Verification",
            "description": "System test, temperature readings",
            "order": 6,
            "required_forms": ["system-verification"],
            "sla_hours": 1
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer sign-off, invoice, recommend maintenance",
            "order": 7,
            "required_forms": ["service-report", "customer-signature"],
            "automations": ["send-invoice", "recommend-maintenance"],
            "sla_hours": 1
        }
    ]'::jsonb,
    1,
    true
);

-- HVAC Maintenance Agreement Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-hvac-maintenance',
    'HVAC Preventive Maintenance',
    'Scheduled maintenance visit workflow for maintenance agreements',
    'HVAC',
    'WORK_ORDER',
    '[
        {
            "id": "schedule",
            "name": "Schedule",
            "description": "Contact customer, schedule visit",
            "order": 1,
            "automations": ["send-reminder-email"],
            "sla_days": 7
        },
        {
            "id": "dispatch",
            "name": "Dispatch",
            "description": "Assign technician",
            "order": 2,
            "sla_hours": 2
        },
        {
            "id": "maintenance",
            "name": "Maintenance",
            "description": "Execute maintenance checklist",
            "order": 3,
            "required_forms": ["hvac-maintenance-checklist", "filter-replacement"],
            "sla_hours": 2
        },
        {
            "id": "report",
            "name": "Report",
            "description": "System health report, recommendations",
            "order": 4,
            "required_forms": ["maintenance-report", "recommendations"],
            "sla_hours": 1
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer sign-off, schedule next visit",
            "order": 5,
            "required_forms": ["customer-signature"],
            "automations": ["schedule-next-visit"],
            "sla_hours": 1
        }
    ]'::jsonb,
    1,
    true
);

-- =====================================================
-- 3. ELECTRICAL WORKFLOW TEMPLATES
-- =====================================================

-- Electrical Panel Upgrade Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-elec-panel-upgrade',
    'Electrical Panel Upgrade',
    'Main service panel upgrade workflow (commonly prerequisite for solar/EV)',
    'ELECTRICAL',
    'PROJECT',
    '[
        {
            "id": "assessment",
            "name": "Assessment",
            "description": "Current panel evaluation, load analysis",
            "order": 1,
            "required_forms": ["panel-assessment", "load-analysis"],
            "work_order_template": "wo-panel-assessment",
            "sla_days": 3
        },
        {
            "id": "proposal",
            "name": "Proposal",
            "description": "Quote for panel upgrade, permit fees",
            "order": 2,
            "required_forms": ["panel-upgrade-proposal"],
            "sla_days": 2
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Contract signing, deposit",
            "order": 3,
            "required_forms": ["electrical-contract"],
            "sla_days": 3
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "Electrical permit application",
            "order": 4,
            "required_forms": ["electrical-permit"],
            "sla_days": 7
        },
        {
            "id": "utility-coord",
            "name": "Utility Coordination",
            "description": "Schedule utility disconnect/reconnect",
            "order": 5,
            "required_forms": ["utility-coordination"],
            "sla_days": 5
        },
        {
            "id": "installation",
            "name": "Installation",
            "description": "Panel replacement, circuit transfer",
            "order": 6,
            "required_forms": ["panel-install-checklist"],
            "work_order_template": "wo-panel-install",
            "sla_days": 1
        },
        {
            "id": "inspection",
            "name": "Inspection",
            "description": "AHJ electrical inspection",
            "order": 7,
            "required_forms": ["inspection-result"],
            "sla_days": 5
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Documentation, customer walkthrough",
            "order": 8,
            "required_forms": ["closeout-checklist"],
            "sla_days": 1
        }
    ]'::jsonb,
    25,
    true
);

-- EV Charger Installation Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-elec-ev-charger',
    'EV Charger Installation',
    'Level 2 EV charger installation workflow',
    'ELECTRICAL',
    'PROJECT',
    '[
        {
            "id": "assessment",
            "name": "Site Assessment",
            "description": "Panel capacity check, charger location, conduit routing",
            "order": 1,
            "required_forms": ["ev-site-assessment", "panel-capacity-check"],
            "work_order_template": "wo-ev-assessment",
            "sla_days": 3
        },
        {
            "id": "proposal",
            "name": "Proposal",
            "description": "Charger options, installation quote, rebates",
            "order": 2,
            "required_forms": ["ev-proposal", "rebate-application"],
            "sla_days": 2
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Contract and deposit",
            "order": 3,
            "required_forms": ["ev-contract"],
            "sla_days": 3
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "Electrical permit for EV charger",
            "order": 4,
            "required_forms": ["ev-permit"],
            "sla_days": 5
        },
        {
            "id": "installation",
            "name": "Installation",
            "description": "Charger mounting, circuit installation, commissioning",
            "order": 5,
            "required_forms": ["ev-install-checklist", "charger-commissioning"],
            "work_order_template": "wo-ev-install",
            "sla_days": 1
        },
        {
            "id": "inspection",
            "name": "Inspection",
            "description": "AHJ electrical inspection",
            "order": 6,
            "required_forms": ["inspection-result"],
            "sla_days": 5
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer training, app setup, warranty",
            "order": 7,
            "required_forms": ["ev-customer-training", "warranty-registration"],
            "sla_days": 1
        }
    ]'::jsonb,
    20,
    true
);

-- Electrical Service Call Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-elec-service',
    'Electrical Service Call',
    'Standard electrical troubleshooting and repair workflow',
    'ELECTRICAL',
    'WORK_ORDER',
    '[
        {
            "id": "triage",
            "name": "Triage",
            "description": "Customer call, issue identification",
            "order": 1,
            "required_forms": ["elec-service-intake"],
            "sla_hours": 2
        },
        {
            "id": "dispatch",
            "name": "Dispatch",
            "description": "Technician assignment",
            "order": 2,
            "sla_hours": 1
        },
        {
            "id": "diagnosis",
            "name": "Diagnosis",
            "description": "Troubleshooting, fault identification",
            "order": 3,
            "required_forms": ["elec-diagnostic-form"],
            "sla_hours": 2
        },
        {
            "id": "approval",
            "name": "Customer Approval",
            "description": "Repair estimate, authorization",
            "order": 4,
            "required_forms": ["repair-estimate", "customer-approval"],
            "sla_hours": 4
        },
        {
            "id": "repair",
            "name": "Repair",
            "description": "Execute repair",
            "order": 5,
            "required_forms": ["elec-repair-log"],
            "sla_hours": 4
        },
        {
            "id": "verification",
            "name": "Verification",
            "description": "Safety verification, testing",
            "order": 6,
            "required_forms": ["safety-verification"],
            "sla_hours": 1
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer sign-off, invoice",
            "order": 7,
            "required_forms": ["service-report", "customer-signature"],
            "sla_hours": 1
        }
    ]'::jsonb,
    1,
    true
);

-- =====================================================
-- 4. PLUMBING WORKFLOW TEMPLATES
-- =====================================================

-- Water Heater Installation Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-plumb-water-heater',
    'Water Heater Installation',
    'Tank or tankless water heater installation workflow',
    'PLUMBING',
    'PROJECT',
    '[
        {
            "id": "assessment",
            "name": "Assessment",
            "description": "Current system evaluation, sizing, location",
            "order": 1,
            "required_forms": ["wh-assessment", "sizing-calc"],
            "work_order_template": "wo-wh-assessment",
            "sla_days": 2
        },
        {
            "id": "proposal",
            "name": "Proposal",
            "description": "Equipment options, installation quote",
            "order": 2,
            "required_forms": ["wh-proposal"],
            "sla_days": 2
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Contract and scheduling",
            "order": 3,
            "required_forms": ["plumbing-contract"],
            "sla_days": 2
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "Plumbing/gas permit if required",
            "order": 4,
            "required_forms": ["plumbing-permit"],
            "sla_days": 5
        },
        {
            "id": "installation",
            "name": "Installation",
            "description": "Remove old, install new, connect plumbing/gas/electric",
            "order": 5,
            "required_forms": ["wh-install-checklist"],
            "work_order_template": "wo-wh-install",
            "sla_days": 1
        },
        {
            "id": "inspection",
            "name": "Inspection",
            "description": "AHJ plumbing inspection if required",
            "order": 6,
            "required_forms": ["inspection-result"],
            "sla_days": 5
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer demo, warranty registration",
            "order": 7,
            "required_forms": ["customer-demo", "warranty-registration"],
            "sla_days": 1
        }
    ]'::jsonb,
    18,
    true
);

-- Plumbing Service Call Workflow
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-plumb-service',
    'Plumbing Service Call',
    'Standard plumbing service/repair call workflow',
    'PLUMBING',
    'WORK_ORDER',
    '[
        {
            "id": "triage",
            "name": "Triage",
            "description": "Customer call, issue identification, emergency classification",
            "order": 1,
            "required_forms": ["plumb-service-intake"],
            "sla_hours": 1
        },
        {
            "id": "dispatch",
            "name": "Dispatch",
            "description": "Technician assignment",
            "order": 2,
            "sla_hours": 1
        },
        {
            "id": "diagnosis",
            "name": "Diagnosis",
            "description": "On-site troubleshooting, camera inspection if needed",
            "order": 3,
            "required_forms": ["plumb-diagnostic-form"],
            "sla_hours": 2
        },
        {
            "id": "approval",
            "name": "Customer Approval",
            "description": "Repair options, pricing, authorization",
            "order": 4,
            "required_forms": ["repair-estimate", "customer-approval"],
            "sla_hours": 2
        },
        {
            "id": "repair",
            "name": "Repair",
            "description": "Execute repair",
            "order": 5,
            "required_forms": ["plumb-repair-log"],
            "sla_hours": 4
        },
        {
            "id": "verification",
            "name": "Verification",
            "description": "Leak test, flow test",
            "order": 6,
            "required_forms": ["plumb-verification"],
            "sla_hours": 1
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer sign-off, invoice, maintenance recommendations",
            "order": 7,
            "required_forms": ["service-report", "customer-signature"],
            "sla_hours": 1
        }
    ]'::jsonb,
    1,
    true
);

-- =====================================================
-- 5. MULTI-TRADE WORKFLOW TEMPLATES
-- =====================================================

-- Solar + Panel Upgrade Bundle
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template,
    prerequisites
) VALUES (
    'wf-solar-panel-bundle',
    'Solar + Panel Upgrade Bundle',
    'Combined solar installation with prerequisite panel upgrade',
    'SOLAR',
    'PROJECT',
    '[
        {
            "id": "qualification",
            "name": "Qualification",
            "description": "Assess solar + panel upgrade needs together",
            "order": 1,
            "required_forms": ["bundle-qualification"],
            "sla_days": 3
        },
        {
            "id": "panel-assessment",
            "name": "Panel Assessment",
            "description": "Current panel evaluation, load analysis for solar",
            "order": 2,
            "required_forms": ["panel-assessment", "solar-load-analysis"],
            "trade": "ELECTRICAL",
            "sla_days": 3
        },
        {
            "id": "solar-survey",
            "name": "Solar Site Survey",
            "description": "Roof assessment, system design",
            "order": 3,
            "required_forms": ["site-survey-form", "roof-assessment"],
            "trade": "SOLAR",
            "sla_days": 3
        },
        {
            "id": "combined-proposal",
            "name": "Combined Proposal",
            "description": "Single proposal for panel + solar, financing",
            "order": 4,
            "required_forms": ["bundle-proposal", "financing-application"],
            "sla_days": 5
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Combined contract signing",
            "order": 5,
            "required_forms": ["bundle-contract"],
            "sla_days": 3
        },
        {
            "id": "panel-permitting",
            "name": "Panel Permitting",
            "description": "Electrical permit for panel upgrade",
            "order": 6,
            "required_forms": ["electrical-permit"],
            "trade": "ELECTRICAL",
            "sla_days": 7
        },
        {
            "id": "solar-permitting",
            "name": "Solar Permitting",
            "description": "Solar permit and interconnection",
            "order": 7,
            "required_forms": ["solar-permit", "interconnection-app"],
            "trade": "SOLAR",
            "sla_days": 14
        },
        {
            "id": "panel-install",
            "name": "Panel Installation",
            "description": "Upgrade main service panel (prerequisite)",
            "order": 8,
            "required_forms": ["panel-install-checklist"],
            "trade": "ELECTRICAL",
            "work_order_template": "wo-panel-install",
            "sla_days": 2
        },
        {
            "id": "panel-inspection",
            "name": "Panel Inspection",
            "description": "Electrical inspection for panel",
            "order": 9,
            "required_forms": ["inspection-result"],
            "trade": "ELECTRICAL",
            "sla_days": 5
        },
        {
            "id": "solar-install",
            "name": "Solar Installation",
            "description": "Install solar system (after panel passes)",
            "order": 10,
            "required_forms": ["install-checklist", "commissioning-form"],
            "trade": "SOLAR",
            "work_order_template": "wo-solar-install",
            "sla_days": 3
        },
        {
            "id": "solar-inspection",
            "name": "Solar Inspection",
            "description": "Final solar inspection",
            "order": 11,
            "required_forms": ["inspection-result"],
            "trade": "SOLAR",
            "sla_days": 7
        },
        {
            "id": "pto",
            "name": "Permission to Operate",
            "description": "Utility PTO approval",
            "order": 12,
            "required_forms": ["pto-confirmation"],
            "trade": "SOLAR",
            "sla_days": 14
        },
        {
            "id": "closeout",
            "name": "Bundle Closeout",
            "description": "Combined documentation, warranty, O&M setup",
            "order": 13,
            "required_forms": ["bundle-closeout", "warranty-docs"],
            "sla_days": 3
        }
    ]'::jsonb,
    65,
    true,
    '["wf-elec-panel-upgrade"]'::jsonb
);

-- Solar + Battery + EV Bundle (Electrification Bundle)
INSERT INTO dim_cpq_workflow_templates (
    id, name, description, trade_type, workflow_type,
    phases, estimated_duration_days, is_system_template
) VALUES (
    'wf-electrification-bundle',
    'Home Electrification Bundle',
    'Complete home electrification: Solar + Battery + EV Charger',
    'SOLAR',
    'PROJECT',
    '[
        {
            "id": "consultation",
            "name": "Electrification Consultation",
            "description": "Whole-home energy assessment, electrification roadmap",
            "order": 1,
            "required_forms": ["electrification-assessment", "energy-audit"],
            "sla_days": 5
        },
        {
            "id": "design",
            "name": "System Design",
            "description": "Solar + battery + EV charger integrated design",
            "order": 2,
            "required_forms": ["integrated-design", "load-analysis"],
            "sla_days": 5
        },
        {
            "id": "proposal",
            "name": "Proposal",
            "description": "Bundled proposal with rebates, financing",
            "order": 3,
            "required_forms": ["electrification-proposal", "rebate-apps"],
            "sla_days": 5
        },
        {
            "id": "contract",
            "name": "Contract",
            "description": "Master contract for all components",
            "order": 4,
            "required_forms": ["electrification-contract"],
            "sla_days": 3
        },
        {
            "id": "permitting",
            "name": "Permitting",
            "description": "All permits: electrical, solar, battery",
            "order": 5,
            "required_forms": ["combined-permits"],
            "sla_days": 14
        },
        {
            "id": "procurement",
            "name": "Procurement",
            "description": "Order all equipment",
            "order": 6,
            "required_forms": ["combined-bom"],
            "sla_days": 10
        },
        {
            "id": "panel-work",
            "name": "Panel Upgrade (if needed)",
            "description": "Upgrade panel for additional loads",
            "order": 7,
            "required_forms": ["panel-upgrade-checklist"],
            "trade": "ELECTRICAL",
            "sla_days": 2
        },
        {
            "id": "solar-install",
            "name": "Solar Installation",
            "description": "Install PV system",
            "order": 8,
            "required_forms": ["solar-install-checklist"],
            "trade": "SOLAR",
            "sla_days": 2
        },
        {
            "id": "battery-install",
            "name": "Battery Installation",
            "description": "Install battery storage",
            "order": 9,
            "required_forms": ["battery-install-checklist"],
            "trade": "BATTERY",
            "sla_days": 1
        },
        {
            "id": "ev-install",
            "name": "EV Charger Installation",
            "description": "Install EV charger",
            "order": 10,
            "required_forms": ["ev-install-checklist"],
            "trade": "ELECTRICAL",
            "sla_days": 1
        },
        {
            "id": "commissioning",
            "name": "System Commissioning",
            "description": "Commission all systems, verify integration",
            "order": 11,
            "required_forms": ["integrated-commissioning"],
            "sla_days": 1
        },
        {
            "id": "inspection",
            "name": "Final Inspection",
            "description": "All inspections",
            "order": 12,
            "required_forms": ["combined-inspection"],
            "sla_days": 7
        },
        {
            "id": "pto",
            "name": "PTO",
            "description": "Permission to Operate",
            "order": 13,
            "required_forms": ["pto-confirmation"],
            "sla_days": 14
        },
        {
            "id": "closeout",
            "name": "Closeout",
            "description": "Customer training on all systems, monitoring setup",
            "order": 14,
            "required_forms": ["electrification-training", "monitoring-setup"],
            "sla_days": 2
        }
    ]'::jsonb,
    70,
    true
);

-- =====================================================
-- 6. WORK ORDER TEMPLATES
-- =====================================================

INSERT INTO dim_cpq_work_order_templates (id, name, description, trade_type, work_order_type, default_duration_hours, required_skills, checklist_items, is_system_template) VALUES

-- Solar Work Orders
('wo-site-survey', 'Solar Site Survey', 'Residential solar site survey work order', 'SOLAR', 'FIELD', 2,
 '["solar-sales", "site-assessment"]'::jsonb,
 '[
    {"item": "Verify customer home", "required": true},
    {"item": "Take roof photos (all planes)", "required": true},
    {"item": "Measure roof dimensions", "required": true},
    {"item": "Check shading obstructions", "required": true},
    {"item": "Inspect electrical panel", "required": true},
    {"item": "Note panel make/model/amps", "required": true},
    {"item": "Check attic access", "required": false},
    {"item": "Review utility meter location", "required": true},
    {"item": "Collect utility bill", "required": true},
    {"item": "Discuss homeowner goals", "required": true}
 ]'::jsonb, true),

('wo-solar-install', 'Solar Installation', 'Residential solar PV installation', 'SOLAR', 'FIELD', 8,
 '["solar-installer", "electrician"]'::jsonb,
 '[
    {"item": "Review safety plan", "required": true},
    {"item": "Install roof attachments", "required": true},
    {"item": "Install racking/rails", "required": true},
    {"item": "Install microinverters/optimizers", "required": true},
    {"item": "Install modules", "required": true},
    {"item": "Run conduit", "required": true},
    {"item": "Install inverter (if string)", "required": false},
    {"item": "Install disconnect", "required": true},
    {"item": "Connect to panel", "required": true},
    {"item": "Commission system", "required": true},
    {"item": "Clean up site", "required": true},
    {"item": "Take completion photos", "required": true}
 ]'::jsonb, true),

('wo-inspection', 'Solar Inspection', 'Schedule and attend AHJ inspection', 'SOLAR', 'FIELD', 2,
 '["solar-installer"]'::jsonb,
 '[
    {"item": "Confirm inspection time with AHJ", "required": true},
    {"item": "Ensure permit card visible", "required": true},
    {"item": "Have plans on site", "required": true},
    {"item": "Attend inspection", "required": true},
    {"item": "Document inspection result", "required": true},
    {"item": "Address any corrections", "required": false}
 ]'::jsonb, true),

-- HVAC Work Orders
('wo-hvac-assessment', 'HVAC Load Calc Visit', 'On-site visit for Manual J load calculation', 'HVAC', 'FIELD', 2,
 '["hvac-sales", "hvac-tech"]'::jsonb,
 '[
    {"item": "Measure square footage", "required": true},
    {"item": "Count windows/doors", "required": true},
    {"item": "Note insulation levels", "required": true},
    {"item": "Check existing equipment", "required": true},
    {"item": "Note ductwork condition", "required": true},
    {"item": "Review thermostat location", "required": true},
    {"item": "Discuss comfort issues", "required": true}
 ]'::jsonb, true),

('wo-hvac-install', 'HVAC Installation', 'Full HVAC system installation', 'HVAC', 'FIELD', 8,
 '["hvac-installer", "electrician"]'::jsonb,
 '[
    {"item": "Remove old equipment", "required": true},
    {"item": "Prepare equipment pad/stand", "required": true},
    {"item": "Install new equipment", "required": true},
    {"item": "Connect refrigerant lines", "required": true},
    {"item": "Connect electrical", "required": true},
    {"item": "Connect thermostat", "required": true},
    {"item": "Evacuate and charge system", "required": true},
    {"item": "Start up system", "required": true},
    {"item": "Balance airflow", "required": true},
    {"item": "Program thermostat", "required": true},
    {"item": "Clean up site", "required": true}
 ]'::jsonb, true),

-- Electrical Work Orders
('wo-panel-assessment', 'Panel Assessment', 'Electrical panel evaluation', 'ELECTRICAL', 'FIELD', 1,
 '["electrician"]'::jsonb,
 '[
    {"item": "Remove panel cover", "required": true},
    {"item": "Photo panel interior", "required": true},
    {"item": "Note panel make/model", "required": true},
    {"item": "Count available spaces", "required": true},
    {"item": "Calculate current load", "required": true},
    {"item": "Check grounding", "required": true},
    {"item": "Note any issues", "required": true}
 ]'::jsonb, true),

('wo-panel-install', 'Panel Upgrade', 'Main service panel replacement', 'ELECTRICAL', 'FIELD', 6,
 '["master-electrician"]'::jsonb,
 '[
    {"item": "Verify utility disconnect complete", "required": true},
    {"item": "Remove old panel", "required": true},
    {"item": "Install new panel", "required": true},
    {"item": "Transfer circuits", "required": true},
    {"item": "Install new breakers", "required": true},
    {"item": "Test all circuits", "required": true},
    {"item": "Verify grounds/neutrals", "required": true},
    {"item": "Label all circuits", "required": true},
    {"item": "Request utility reconnect", "required": true}
 ]'::jsonb, true),

('wo-ev-assessment', 'EV Charger Assessment', 'Site assessment for EV charger', 'ELECTRICAL', 'FIELD', 1,
 '["electrician"]'::jsonb,
 '[
    {"item": "Check panel capacity", "required": true},
    {"item": "Identify charger location", "required": true},
    {"item": "Measure conduit run", "required": true},
    {"item": "Note any obstacles", "required": true},
    {"item": "Discuss vehicle specs", "required": true}
 ]'::jsonb, true),

('wo-ev-install', 'EV Charger Installation', 'Level 2 EV charger installation', 'ELECTRICAL', 'FIELD', 4,
 '["electrician"]'::jsonb,
 '[
    {"item": "Turn off main breaker", "required": true},
    {"item": "Install circuit breaker", "required": true},
    {"item": "Run conduit/wire", "required": true},
    {"item": "Mount charger", "required": true},
    {"item": "Connect wiring", "required": true},
    {"item": "Test charger", "required": true},
    {"item": "Setup app/wifi", "required": true},
    {"item": "Train customer", "required": true}
 ]'::jsonb, true),

-- Plumbing Work Orders
('wo-wh-assessment', 'Water Heater Assessment', 'Assess for water heater replacement', 'PLUMBING', 'FIELD', 1,
 '["plumber"]'::jsonb,
 '[
    {"item": "Check current unit specs", "required": true},
    {"item": "Note fuel type (gas/elec)", "required": true},
    {"item": "Check venting type", "required": true},
    {"item": "Measure space available", "required": true},
    {"item": "Discuss usage patterns", "required": true},
    {"item": "Check code requirements", "required": true}
 ]'::jsonb, true),

('wo-wh-install', 'Water Heater Installation', 'Tank or tankless water heater install', 'PLUMBING', 'FIELD', 4,
 '["plumber", "gas-tech"]'::jsonb,
 '[
    {"item": "Turn off water supply", "required": true},
    {"item": "Drain old tank", "required": true},
    {"item": "Disconnect old unit", "required": true},
    {"item": "Remove old unit", "required": true},
    {"item": "Position new unit", "required": true},
    {"item": "Connect water lines", "required": true},
    {"item": "Connect gas/electric", "required": true},
    {"item": "Install expansion tank", "required": false},
    {"item": "Fill and purge air", "required": true},
    {"item": "Check for leaks", "required": true},
    {"item": "Set temperature", "required": true},
    {"item": "Test hot water at fixture", "required": true}
 ]'::jsonb, true);

-- =====================================================
-- 7. FORM TEMPLATES BY TRADE
-- =====================================================

INSERT INTO dim_cpq_form_templates (id, name, description, trade_type, form_type, fields, is_system_template) VALUES

-- Solar Forms
('form-site-survey', 'Solar Site Survey', 'Residential solar site survey form', 'SOLAR', 'ASSESSMENT',
 '[
    {"name": "roof_type", "label": "Roof Type", "type": "select", "options": ["Composition Shingle", "Tile", "Metal", "Flat/TPO", "Wood Shake"], "required": true},
    {"name": "roof_age", "label": "Roof Age (years)", "type": "number", "required": true},
    {"name": "roof_condition", "label": "Roof Condition", "type": "select", "options": ["Excellent", "Good", "Fair", "Poor"], "required": true},
    {"name": "azimuth", "label": "Primary Azimuth", "type": "number", "required": true},
    {"name": "pitch", "label": "Roof Pitch (degrees)", "type": "number", "required": true},
    {"name": "shading", "label": "Shading", "type": "select", "options": ["None", "Minimal", "Moderate", "Heavy"], "required": true},
    {"name": "panel_amps", "label": "Main Panel Amps", "type": "select", "options": ["100A", "125A", "150A", "200A", "320A", "400A"], "required": true},
    {"name": "panel_spaces", "label": "Available Panel Spaces", "type": "number", "required": true},
    {"name": "attic_access", "label": "Attic Access", "type": "boolean", "required": true},
    {"name": "photos", "label": "Site Photos", "type": "file", "multiple": true, "required": true},
    {"name": "notes", "label": "Additional Notes", "type": "textarea", "required": false}
 ]'::jsonb, true),

('form-solar-install-checklist', 'Solar Installation Checklist', 'Installation completion checklist', 'SOLAR', 'CHECKLIST',
 '[
    {"name": "attachments_torqued", "label": "All attachments torqued to spec", "type": "boolean", "required": true},
    {"name": "flashing_sealed", "label": "All flashings sealed", "type": "boolean", "required": true},
    {"name": "modules_grounded", "label": "All modules properly grounded", "type": "boolean", "required": true},
    {"name": "wiring_secured", "label": "All wiring secured and protected", "type": "boolean", "required": true},
    {"name": "conduit_complete", "label": "Conduit run complete", "type": "boolean", "required": true},
    {"name": "disconnect_installed", "label": "AC disconnect installed", "type": "boolean", "required": true},
    {"name": "inverter_mounted", "label": "Inverter properly mounted", "type": "boolean", "required": true},
    {"name": "monitoring_configured", "label": "Monitoring configured", "type": "boolean", "required": true},
    {"name": "completion_photos", "label": "Completion Photos", "type": "file", "multiple": true, "required": true}
 ]'::jsonb, true),

('form-commissioning', 'System Commissioning', 'Solar system commissioning form', 'SOLAR', 'COMMISSIONING',
 '[
    {"name": "voc_string1", "label": "Voc String 1 (V)", "type": "number", "required": true},
    {"name": "voc_string2", "label": "Voc String 2 (V)", "type": "number", "required": false},
    {"name": "vmp_string1", "label": "Vmp String 1 (V)", "type": "number", "required": true},
    {"name": "imp_string1", "label": "Imp String 1 (A)", "type": "number", "required": true},
    {"name": "ac_voltage", "label": "AC Voltage (V)", "type": "number", "required": true},
    {"name": "ac_power", "label": "AC Power (W)", "type": "number", "required": true},
    {"name": "ground_resistance", "label": "Ground Resistance (ohms)", "type": "number", "required": true},
    {"name": "monitoring_verified", "label": "Monitoring Verified Working", "type": "boolean", "required": true}
 ]'::jsonb, true),

-- HVAC Forms
('form-manual-j', 'Manual J Load Calculation', 'HVAC load calculation inputs', 'HVAC', 'ASSESSMENT',
 '[
    {"name": "square_footage", "label": "Conditioned Square Footage", "type": "number", "required": true},
    {"name": "ceiling_height", "label": "Ceiling Height (ft)", "type": "number", "required": true},
    {"name": "num_windows", "label": "Number of Windows", "type": "number", "required": true},
    {"name": "insulation_walls", "label": "Wall Insulation R-Value", "type": "select", "options": ["R-11", "R-13", "R-15", "R-19", "R-21", "Unknown"], "required": true},
    {"name": "insulation_attic", "label": "Attic Insulation R-Value", "type": "select", "options": ["R-19", "R-30", "R-38", "R-49", "Unknown"], "required": true},
    {"name": "duct_location", "label": "Duct Location", "type": "select", "options": ["Conditioned Space", "Attic", "Crawlspace", "Basement"], "required": true},
    {"name": "cooling_load", "label": "Cooling Load (BTU)", "type": "number", "required": true},
    {"name": "heating_load", "label": "Heating Load (BTU)", "type": "number", "required": true},
    {"name": "recommended_tonnage", "label": "Recommended Tonnage", "type": "number", "required": true}
 ]'::jsonb, true),

('form-hvac-install-checklist', 'HVAC Installation Checklist', 'HVAC install completion checklist', 'HVAC', 'CHECKLIST',
 '[
    {"name": "old_equipment_removed", "label": "Old equipment removed", "type": "boolean", "required": true},
    {"name": "refrigerant_recovered", "label": "Refrigerant recovered (if applicable)", "type": "boolean", "required": false},
    {"name": "equipment_leveled", "label": "Equipment properly leveled", "type": "boolean", "required": true},
    {"name": "electrical_connected", "label": "Electrical properly connected", "type": "boolean", "required": true},
    {"name": "refrigerant_charged", "label": "System charged to spec", "type": "boolean", "required": true},
    {"name": "refrigerant_lbs", "label": "Refrigerant Added (lbs)", "type": "number", "required": true},
    {"name": "static_pressure", "label": "Static Pressure (in WC)", "type": "number", "required": true},
    {"name": "supply_temp", "label": "Supply Air Temp (°F)", "type": "number", "required": true},
    {"name": "return_temp", "label": "Return Air Temp (°F)", "type": "number", "required": true},
    {"name": "delta_t", "label": "Delta T (°F)", "type": "number", "required": true},
    {"name": "thermostat_programmed", "label": "Thermostat programmed", "type": "boolean", "required": true}
 ]'::jsonb, true),

-- Electrical Forms
('form-panel-assessment', 'Electrical Panel Assessment', 'Panel evaluation form', 'ELECTRICAL', 'ASSESSMENT',
 '[
    {"name": "panel_make", "label": "Panel Make", "type": "text", "required": true},
    {"name": "panel_model", "label": "Panel Model", "type": "text", "required": true},
    {"name": "main_breaker_amps", "label": "Main Breaker Amps", "type": "select", "options": ["100A", "125A", "150A", "200A", "320A", "400A"], "required": true},
    {"name": "service_voltage", "label": "Service Voltage", "type": "select", "options": ["120/240V Single Phase", "120/208V Three Phase", "277/480V Three Phase"], "required": true},
    {"name": "total_spaces", "label": "Total Spaces", "type": "number", "required": true},
    {"name": "used_spaces", "label": "Used Spaces", "type": "number", "required": true},
    {"name": "available_spaces", "label": "Available Spaces", "type": "number", "required": true},
    {"name": "grounding_electrode", "label": "Grounding Electrode Type", "type": "select", "options": ["Rod", "Plate", "UFER", "Water Pipe", "Unknown"], "required": true},
    {"name": "panel_condition", "label": "Panel Condition", "type": "select", "options": ["Good", "Fair", "Poor", "Needs Replacement"], "required": true},
    {"name": "panel_photos", "label": "Panel Photos", "type": "file", "multiple": true, "required": true}
 ]'::jsonb, true),

-- Plumbing Forms
('form-wh-assessment', 'Water Heater Assessment', 'Water heater evaluation form', 'PLUMBING', 'ASSESSMENT',
 '[
    {"name": "current_type", "label": "Current Type", "type": "select", "options": ["Tank Gas", "Tank Electric", "Tankless Gas", "Tankless Electric", "Heat Pump"], "required": true},
    {"name": "current_capacity", "label": "Current Capacity (gallons)", "type": "number", "required": true},
    {"name": "current_age", "label": "Estimated Age (years)", "type": "number", "required": true},
    {"name": "fuel_type", "label": "Available Fuel Types", "type": "multiselect", "options": ["Natural Gas", "Propane", "Electric"], "required": true},
    {"name": "venting_type", "label": "Current Venting", "type": "select", "options": ["Atmospheric", "Power Vent", "Direct Vent", "None (Electric)", "Condensing"], "required": true},
    {"name": "location", "label": "Unit Location", "type": "select", "options": ["Garage", "Basement", "Utility Room", "Closet", "Outdoor"], "required": true},
    {"name": "household_size", "label": "Household Size", "type": "number", "required": true},
    {"name": "recommended_type", "label": "Recommended Type", "type": "select", "options": ["Tank Gas", "Tank Electric", "Tankless Gas", "Tankless Electric", "Heat Pump"], "required": true},
    {"name": "recommended_capacity", "label": "Recommended Capacity", "type": "text", "required": true}
 ]'::jsonb, true);

-- =====================================================
-- 8. TRADE-SPECIFIC PROPERTIES
-- =====================================================

INSERT INTO dim_cpq_property_definitions (id, name, label, description, property_type, data_type, trade_type, options, is_system_property) VALUES

-- Solar Properties
('prop-system-size', 'system_size_kw', 'System Size (kW)', 'Total DC system size in kilowatts', 'ASSET', 'number', 'SOLAR', NULL, true),
('prop-module-count', 'module_count', 'Module Count', 'Number of solar modules', 'ASSET', 'number', 'SOLAR', NULL, true),
('prop-module-wattage', 'module_wattage', 'Module Wattage', 'Wattage per module', 'ASSET', 'number', 'SOLAR', NULL, true),
('prop-inverter-type', 'inverter_type', 'Inverter Type', 'Type of inverter', 'ASSET', 'select', 'SOLAR', '["String", "Microinverter", "DC Optimizer", "Hybrid"]'::jsonb, true),
('prop-battery-kwh', 'battery_capacity_kwh', 'Battery Capacity (kWh)', 'Battery storage capacity', 'ASSET', 'number', 'BATTERY', NULL, true),
('prop-pto-date', 'pto_date', 'PTO Date', 'Permission to Operate date', 'PROJECT', 'date', 'SOLAR', NULL, true),
('prop-utility', 'utility_company', 'Utility Company', 'Electric utility provider', 'CLIENT', 'text', 'SOLAR', NULL, true),
('prop-rate-schedule', 'rate_schedule', 'Rate Schedule', 'Utility rate schedule', 'CLIENT', 'text', 'SOLAR', NULL, true),

-- HVAC Properties
('prop-hvac-tonnage', 'hvac_tonnage', 'System Tonnage', 'Cooling capacity in tons', 'ASSET', 'number', 'HVAC', NULL, true),
('prop-hvac-seer', 'hvac_seer', 'SEER Rating', 'Seasonal Energy Efficiency Ratio', 'ASSET', 'number', 'HVAC', NULL, true),
('prop-hvac-hspf', 'hvac_hspf', 'HSPF Rating', 'Heating Seasonal Performance Factor', 'ASSET', 'number', 'HVAC', NULL, true),
('prop-hvac-type', 'hvac_system_type', 'System Type', 'Type of HVAC system', 'ASSET', 'select', 'HVAC', '["Split System", "Package Unit", "Mini Split", "Heat Pump", "Furnace Only", "AC Only"]'::jsonb, true),
('prop-refrigerant', 'refrigerant_type', 'Refrigerant Type', 'Refrigerant used', 'ASSET', 'select', 'HVAC', '["R-410A", "R-32", "R-22 (Legacy)", "R-454B"]'::jsonb, true),
('prop-filter-size', 'filter_size', 'Filter Size', 'Air filter dimensions', 'ASSET', 'text', 'HVAC', NULL, true),

-- Electrical Properties
('prop-panel-amps', 'panel_amperage', 'Panel Amperage', 'Main panel amperage', 'ASSET', 'select', 'ELECTRICAL', '["100A", "125A", "150A", "200A", "320A", "400A"]'::jsonb, true),
('prop-service-type', 'service_type', 'Service Type', 'Electrical service type', 'ASSET', 'select', 'ELECTRICAL', '["Single Phase", "Three Phase"]'::jsonb, true),
('prop-ev-charger-amps', 'ev_charger_amps', 'EV Charger Amps', 'EV charger circuit amperage', 'ASSET', 'select', 'ELECTRICAL', '["30A", "40A", "48A", "50A", "60A", "80A"]'::jsonb, true),
('prop-ev-charger-type', 'ev_charger_type', 'EV Charger Type', 'EV charger brand/model', 'ASSET', 'text', 'ELECTRICAL', NULL, true),

-- Plumbing Properties
('prop-wh-type', 'water_heater_type', 'Water Heater Type', 'Type of water heater', 'ASSET', 'select', 'PLUMBING', '["Tank Gas", "Tank Electric", "Tankless Gas", "Tankless Electric", "Heat Pump"]'::jsonb, true),
('prop-wh-capacity', 'water_heater_capacity', 'Capacity (Gallons)', 'Water heater tank capacity', 'ASSET', 'number', 'PLUMBING', NULL, true),
('prop-wh-btu', 'water_heater_btu', 'BTU Rating', 'Water heater BTU input', 'ASSET', 'number', 'PLUMBING', NULL, true),
('prop-wh-uef', 'water_heater_uef', 'UEF Rating', 'Uniform Energy Factor', 'ASSET', 'number', 'PLUMBING', NULL, true);

-- =====================================================
-- 9. SERVICE PLAN TEMPLATES
-- =====================================================

INSERT INTO dim_cpq_service_plan_templates (id, name, description, trade_type, billing_frequency, visits_per_year, price_per_year, included_services, is_system_template) VALUES

-- Solar Service Plans
('sp-solar-basic', 'Solar Basic Care', 'Annual monitoring and inspection', 'SOLAR', 'ANNUAL', 1, 199.00,
 '[
    "Annual system inspection",
    "Performance monitoring",
    "Annual production report",
    "Priority scheduling"
 ]'::jsonb, true),

('sp-solar-premium', 'Solar Premium Care', 'Comprehensive O&M coverage', 'SOLAR', 'ANNUAL', 2, 399.00,
 '[
    "Bi-annual inspections",
    "24/7 monitoring with alerts",
    "Panel cleaning (2x/year)",
    "Inverter diagnostics",
    "Performance guarantee",
    "Priority emergency service",
    "Annual production report"
 ]'::jsonb, true),

-- HVAC Service Plans
('sp-hvac-basic', 'HVAC Comfort Plan', 'Basic maintenance agreement', 'HVAC', 'ANNUAL', 2, 199.00,
 '[
    "Spring AC tune-up",
    "Fall heating tune-up",
    "Filter included (standard size)",
    "15% parts discount",
    "Priority scheduling"
 ]'::jsonb, true),

('sp-hvac-premium', 'HVAC Premium Plan', 'Comprehensive coverage', 'HVAC', 'ANNUAL', 2, 349.00,
 '[
    "Spring AC tune-up",
    "Fall heating tune-up",
    "Filters included (all visits)",
    "25% parts discount",
    "No overtime charges",
    "Priority emergency service",
    "Refrigerant top-off included",
    "Duct inspection"
 ]'::jsonb, true),

-- Electrical Service Plans
('sp-elec-safety', 'Electrical Safety Plan', 'Annual electrical safety inspection', 'ELECTRICAL', 'ANNUAL', 1, 149.00,
 '[
    "Annual panel inspection",
    "Outlet/switch testing",
    "GFCI/AFCI testing",
    "Smoke detector battery replacement",
    "15% repair discount",
    "Priority scheduling"
 ]'::jsonb, true),

-- Plumbing Service Plans
('sp-plumb-basic', 'Plumbing Care Plan', 'Annual plumbing maintenance', 'PLUMBING', 'ANNUAL', 1, 149.00,
 '[
    "Annual plumbing inspection",
    "Water heater flush",
    "Drain inspection",
    "15% repair discount",
    "Priority scheduling"
 ]'::jsonb, true);

-- =====================================================
-- 10. INDEXES FOR PERFORMANCE
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_workflow_templates_trade ON dim_cpq_workflow_templates(trade_type);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_type ON dim_cpq_workflow_templates(workflow_type);
CREATE INDEX IF NOT EXISTS idx_wo_templates_trade ON dim_cpq_work_order_templates(trade_type);
CREATE INDEX IF NOT EXISTS idx_form_templates_trade ON dim_cpq_form_templates(trade_type);
CREATE INDEX IF NOT EXISTS idx_property_defs_trade ON dim_cpq_property_definitions(trade_type);
CREATE INDEX IF NOT EXISTS idx_service_plan_templates_trade ON dim_cpq_service_plan_templates(trade_type);

-- =====================================================
-- SUMMARY
-- =====================================================
-- This migration creates best-in-class workflow templates for:
--
-- SOLAR:
--   - Residential Installation (10 phases, 60 days)
--   - Commercial Installation (12 phases, 180 days)
--   - O&M Service (5 phases, 1 day)
--
-- HVAC:
--   - Residential Installation (10 phases, 30 days)
--   - Service Call (7 phases, 1 day)
--   - Preventive Maintenance (5 phases, 1 day)
--
-- ELECTRICAL:
--   - Panel Upgrade (8 phases, 25 days)
--   - EV Charger Installation (7 phases, 20 days)
--   - Service Call (7 phases, 1 day)
--
-- PLUMBING:
--   - Water Heater Installation (7 phases, 18 days)
--   - Service Call (7 phases, 1 day)
--
-- MULTI-TRADE BUNDLES:
--   - Solar + Panel Upgrade (13 phases, 65 days)
--   - Home Electrification: Solar + Battery + EV (14 phases, 70 days)
--
-- WORK ORDER TEMPLATES: 12
-- FORM TEMPLATES: 9
-- PROPERTY DEFINITIONS: 20
-- SERVICE PLAN TEMPLATES: 6
-- =====================================================
