-- =============================================================================
-- MIGRATION: Complete ICP Signal Detection for Coperniq GTM
-- =============================================================================
-- Purpose: Comprehensive signal detection for solar/electrical contractor ICP
-- 40+ signals organized by category for precise lead scoring
-- =============================================================================

-- =============================================
-- CATEGORY 1: SERVICE OFFERING SIGNALS (10)
-- What services do they offer?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_commercial BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_industrial BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_residential BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_solar_commercial BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_solar_residential BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_battery_storage BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_ev_charging BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_generators BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_emergency_service BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_maintenance_plans BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 2: CAPABILITY SIGNALS (10)
-- How sophisticated are their operations?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_design_build BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_engineering BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_building_automation BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_medical_specialization BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_multi_location BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_large_service_area BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_project_management BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_permitting_services BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_monitoring BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_utility_scale BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 3: CREDIBILITY SIGNALS (10)
-- Can we trust them? Are they legit?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_awards BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_certifications BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_licensed BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_bonded_insured BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_nabcep BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_reviews_visible BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_project_gallery BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_case_studies BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_testimonials BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_bbb_rating BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 4: PARTNERSHIP SIGNALS (10)
-- Who do they work with?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_oem_partnerships BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_enphase BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_solaredge BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_tesla BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_lg_panels BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_generac BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_sunpower BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_financing_partners BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_utility_partners BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_manufacturer_certified BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 5: GROWTH SIGNALS (5)
-- Are they growing/successful?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_hiring BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_funding BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_expansion_news BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_inc_5000 BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_recent_projects BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 6: FINANCING SIGNALS (5)
-- Do they offer financing?
-- =============================================

ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_financing BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_ppa BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_lease_options BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_loan_programs BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_rebate_assistance BOOLEAN DEFAULT FALSE;

-- =============================================
-- CATEGORY 7: COPERNIQ IDEAL ICP SIGNALS (20)
-- MEP, Multi-Trade, Self-Performing, Asset-Centric
-- THIS IS THE MONEY CATEGORY - $5-50M, 25-200+ employees
-- =============================================

-- MEP Trade Indicators (Mechanical, Electrical, Plumbing)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_electrical_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_mechanical_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_plumbing_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_hvac_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_fire_protection BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_mep_contractor BOOLEAN DEFAULT FALSE;

-- Multi-Trade / Multi-License Indicators
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_multi_trade BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_multi_license BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS trade_count INTEGER DEFAULT 0;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS license_types TEXT[];

-- Multi-OEM Partnerships
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_multi_oem BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS oem_count INTEGER DEFAULT 0;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS oem_brands TEXT[];

-- Self-Performing Indicators (NOT just a GC who subs everything)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_self_performing BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_own_crews BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_in_house_technicians BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_apprenticeship BOOLEAN DEFAULT FALSE;

-- Asset-Centric Indicators (Equipment, Fleet, Tools)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_asset_centric BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_fleet BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_warehouse BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_equipment_yard BOOLEAN DEFAULT FALSE;

-- Size Indicators (ICP Sweet Spot: $5-50M revenue, 25-200+ employees)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS employee_range TEXT;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS revenue_range TEXT;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_in_icp_size_range BOOLEAN DEFAULT FALSE;

-- =============================================
-- COMPUTED SCORES (for easy filtering)
-- =============================================

-- Create a computed ICP score based on signals
-- Coperniq ICP: MEP, Multi-Trade, Self-Performing, Asset-Centric, $5-50M, 25-200+ employees
CREATE OR REPLACE FUNCTION compute_icp_signal_score(company_row dim_companies)
RETURNS INTEGER AS $$
DECLARE
    score INTEGER := 0;
BEGIN
    -- ===========================================
    -- PLATINUM SIGNALS (5 points each) - Coperniq Core ICP
    -- MEP + Multi-Trade + Self-Performing + Asset-Centric
    -- ===========================================
    IF company_row.is_mep_contractor THEN score := score + 5; END IF;
    IF company_row.is_multi_trade THEN score := score + 5; END IF;
    IF company_row.is_multi_license THEN score := score + 5; END IF;
    IF company_row.is_multi_oem THEN score := score + 5; END IF;
    IF company_row.is_self_performing THEN score := score + 5; END IF;
    IF company_row.is_asset_centric THEN score := score + 5; END IF;
    IF company_row.is_in_icp_size_range THEN score := score + 5; END IF;

    -- ===========================================
    -- HIGH-VALUE SIGNALS (3 points each)
    -- Capability indicators
    -- ===========================================
    IF company_row.has_commercial THEN score := score + 3; END IF;
    IF company_row.has_design_build THEN score := score + 3; END IF;
    IF company_row.has_engineering THEN score := score + 3; END IF;
    IF company_row.has_solar_commercial THEN score := score + 3; END IF;
    IF company_row.has_battery_storage THEN score := score + 3; END IF;
    IF company_row.has_multi_location THEN score := score + 3; END IF;
    IF company_row.has_own_crews THEN score := score + 3; END IF;
    IF company_row.has_fleet THEN score := score + 3; END IF;

    -- Trade-specific (2 points each for individual trades)
    IF company_row.has_electrical_trade THEN score := score + 2; END IF;
    IF company_row.has_mechanical_trade THEN score := score + 2; END IF;
    IF company_row.has_plumbing_trade THEN score := score + 2; END IF;
    IF company_row.has_hvac_trade THEN score := score + 2; END IF;
    IF company_row.has_fire_protection THEN score := score + 2; END IF;

    -- ===========================================
    -- MEDIUM-VALUE SIGNALS (2 points each)
    -- ===========================================
    IF company_row.has_industrial THEN score := score + 2; END IF;
    IF company_row.has_ev_charging THEN score := score + 2; END IF;
    IF company_row.has_certifications THEN score := score + 2; END IF;
    IF company_row.has_oem_partnerships THEN score := score + 2; END IF;
    IF company_row.has_financing THEN score := score + 2; END IF;
    IF company_row.has_project_gallery THEN score := score + 2; END IF;
    IF company_row.has_in_house_technicians THEN score := score + 2; END IF;
    IF company_row.has_warehouse THEN score := score + 2; END IF;

    -- ===========================================
    -- STANDARD SIGNALS (1 point each)
    -- ===========================================
    IF company_row.has_residential THEN score := score + 1; END IF;
    IF company_row.has_generators THEN score := score + 1; END IF;
    IF company_row.has_awards THEN score := score + 1; END IF;
    IF company_row.has_reviews_visible THEN score := score + 1; END IF;
    IF company_row.is_hiring THEN score := score + 1; END IF;
    IF company_row.has_apprenticeship THEN score := score + 1; END IF;

    -- Bonus: Add trade_count and oem_count (1 point per additional)
    score := score + COALESCE(company_row.trade_count, 0);
    score := score + COALESCE(company_row.oem_count, 0);

    RETURN score;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================
-- INDEXES for signal-based queries
-- =============================================

-- Category 1-6 indexes (existing)
CREATE INDEX IF NOT EXISTS idx_companies_commercial ON dim_companies(has_commercial) WHERE has_commercial = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_design_build ON dim_companies(has_design_build) WHERE has_design_build = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_engineering ON dim_companies(has_engineering) WHERE has_engineering = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_solar_commercial ON dim_companies(has_solar_commercial) WHERE has_solar_commercial = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_battery ON dim_companies(has_battery_storage) WHERE has_battery_storage = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_multi_location ON dim_companies(has_multi_location) WHERE has_multi_location = TRUE;

-- Category 7: Coperniq ICP indexes (CRITICAL for sales prioritization)
CREATE INDEX IF NOT EXISTS idx_companies_mep ON dim_companies(is_mep_contractor) WHERE is_mep_contractor = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_multi_trade ON dim_companies(is_multi_trade) WHERE is_multi_trade = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_multi_license ON dim_companies(is_multi_license) WHERE is_multi_license = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_multi_oem ON dim_companies(is_multi_oem) WHERE is_multi_oem = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_self_performing ON dim_companies(is_self_performing) WHERE is_self_performing = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_asset_centric ON dim_companies(is_asset_centric) WHERE is_asset_centric = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_icp_size ON dim_companies(is_in_icp_size_range) WHERE is_in_icp_size_range = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_trade_count ON dim_companies(trade_count) WHERE trade_count > 1;

-- =============================================
-- VIEW: ICP Prioritized Companies (Coperniq Focus)
-- =============================================

CREATE OR REPLACE VIEW v_icp_prioritized AS
SELECT
    company_id,
    company_name,
    website,
    domain,
    icp_tier,
    icp_score,
    -- Coperniq ICP Core Signals (THE MONEY SIGNALS)
    is_mep_contractor,
    is_multi_trade,
    is_multi_license,
    is_multi_oem,
    is_self_performing,
    is_asset_centric,
    is_in_icp_size_range,
    trade_count,
    oem_count,
    employee_range,
    revenue_range,
    -- Trade breakdown
    has_electrical_trade,
    has_mechanical_trade,
    has_plumbing_trade,
    has_hvac_trade,
    has_fire_protection,
    -- Capability signals
    has_commercial,
    has_design_build,
    has_engineering,
    has_solar_commercial,
    has_battery_storage,
    has_multi_location,
    has_own_crews,
    has_fleet,
    -- Count of ALL active ICP signals
    (
        -- Core ICP signals (7)
        COALESCE(is_mep_contractor::int, 0) +
        COALESCE(is_multi_trade::int, 0) +
        COALESCE(is_multi_license::int, 0) +
        COALESCE(is_multi_oem::int, 0) +
        COALESCE(is_self_performing::int, 0) +
        COALESCE(is_asset_centric::int, 0) +
        COALESCE(is_in_icp_size_range::int, 0) +
        -- Trade signals (5)
        COALESCE(has_electrical_trade::int, 0) +
        COALESCE(has_mechanical_trade::int, 0) +
        COALESCE(has_plumbing_trade::int, 0) +
        COALESCE(has_hvac_trade::int, 0) +
        COALESCE(has_fire_protection::int, 0) +
        -- Capability signals (10)
        COALESCE(has_commercial::int, 0) +
        COALESCE(has_industrial::int, 0) +
        COALESCE(has_design_build::int, 0) +
        COALESCE(has_engineering::int, 0) +
        COALESCE(has_solar_commercial::int, 0) +
        COALESCE(has_battery_storage::int, 0) +
        COALESCE(has_ev_charging::int, 0) +
        COALESCE(has_oem_partnerships::int, 0) +
        COALESCE(has_certifications::int, 0) +
        COALESCE(has_multi_location::int, 0)
    ) AS signal_count,
    enrichment_status,
    last_enriched_at
FROM dim_companies
WHERE website IS NOT NULL
ORDER BY
    -- Priority 1: In ICP size range
    is_in_icp_size_range DESC NULLS LAST,
    -- Priority 2: Core ICP signals
    (COALESCE(is_mep_contractor::int, 0) + COALESCE(is_multi_trade::int, 0) +
     COALESCE(is_self_performing::int, 0) + COALESCE(is_asset_centric::int, 0)) DESC,
    -- Priority 3: Tier
    CASE icp_tier
        WHEN 'PLATINUM' THEN 1
        WHEN 'GOLD' THEN 2
        WHEN 'SILVER' THEN 3
        WHEN 'BRONZE' THEN 4
        ELSE 5
    END,
    -- Priority 4: ICP score
    icp_score DESC NULLS LAST;

-- =============================================
-- VIEW: Perfect Coperniq ICP Matches
-- Companies that hit ALL core criteria
-- =============================================

CREATE OR REPLACE VIEW v_coperniq_perfect_icp AS
SELECT *
FROM v_icp_prioritized
WHERE
    is_in_icp_size_range = TRUE
    AND (is_multi_trade = TRUE OR trade_count >= 2)
    AND is_self_performing = TRUE
ORDER BY signal_count DESC, icp_score DESC NULLS LAST;

-- =============================================
-- SIGNAL KEYWORDS (for reference)
-- Used by VLM and BeautifulSoup scrapers
-- =============================================

-- Category 1-6: Service/Capability/Credibility
COMMENT ON COLUMN dim_companies.has_commercial IS 'Keywords: commercial, business, office, retail, warehouse';
COMMENT ON COLUMN dim_companies.has_industrial IS 'Keywords: industrial, manufacturing, factory, plant';
COMMENT ON COLUMN dim_companies.has_design_build IS 'Keywords: design-build, turnkey, full-service, start to finish';
COMMENT ON COLUMN dim_companies.has_engineering IS 'Keywords: engineering, PE, professional engineer, in-house design, CAD';
COMMENT ON COLUMN dim_companies.has_solar_commercial IS 'Keywords: commercial solar, C&I, ground mount, carport';
COMMENT ON COLUMN dim_companies.has_battery_storage IS 'Keywords: battery, storage, powerwall, backup, ESS';
COMMENT ON COLUMN dim_companies.has_ev_charging IS 'Keywords: EV charger, electric vehicle, charging station, EVSE';
COMMENT ON COLUMN dim_companies.has_certifications IS 'Keywords: NABCEP, OSHA, certified, accredited';
COMMENT ON COLUMN dim_companies.has_multi_location IS 'Keywords: locations, offices, branches, serving [multiple cities]';
COMMENT ON COLUMN dim_companies.has_oem_partnerships IS 'Keywords: authorized dealer, certified installer, partner, preferred';

-- =============================================
-- CATEGORY 7: COPERNIQ ICP KEYWORDS (CRITICAL)
-- =============================================

-- MEP Trade Detection
COMMENT ON COLUMN dim_companies.has_electrical_trade IS 'Keywords: electrical contractor, electrician, electrical services, wiring, panel, circuits';
COMMENT ON COLUMN dim_companies.has_mechanical_trade IS 'Keywords: mechanical contractor, mechanical services, piping, ductwork, mechanical systems';
COMMENT ON COLUMN dim_companies.has_plumbing_trade IS 'Keywords: plumbing, plumber, piping, water heater, drains, fixtures';
COMMENT ON COLUMN dim_companies.has_hvac_trade IS 'Keywords: HVAC, heating, cooling, air conditioning, ventilation, furnace, heat pump';
COMMENT ON COLUMN dim_companies.has_fire_protection IS 'Keywords: fire protection, sprinkler, fire alarm, fire suppression, fire safety';
COMMENT ON COLUMN dim_companies.is_mep_contractor IS 'Keywords: MEP, mechanical electrical plumbing, full MEP, MEP services, M/E/P';

-- Multi-Trade/Multi-License Detection
COMMENT ON COLUMN dim_companies.is_multi_trade IS 'Keywords: multiple trades, full-service, one-stop, comprehensive, electrical and mechanical, electrical and plumbing';
COMMENT ON COLUMN dim_companies.is_multi_license IS 'Keywords: multiple licenses, licensed in, license #, contractor license, state license';
COMMENT ON COLUMN dim_companies.trade_count IS 'Derived: Count of trades offered (electrical + mechanical + plumbing + hvac + fire + solar)';
COMMENT ON COLUMN dim_companies.license_types IS 'Derived: Array of license types found (e.g. C-10, C-46, A, B)';

-- Multi-OEM Detection
COMMENT ON COLUMN dim_companies.is_multi_oem IS 'Keywords: authorized dealer for multiple brands, certified installer for, partners with';
COMMENT ON COLUMN dim_companies.oem_count IS 'Derived: Count of OEM partnerships (Enphase, SolarEdge, Tesla, Generac, etc.)';
COMMENT ON COLUMN dim_companies.oem_brands IS 'Derived: Array of OEM brands found';

-- Self-Performing Detection (NOT just a GC who subs out)
COMMENT ON COLUMN dim_companies.is_self_performing IS 'Keywords: self-performing, in-house teams, own technicians, we perform, our crews do';
COMMENT ON COLUMN dim_companies.has_own_crews IS 'Keywords: our team, our technicians, our electricians, in-house crews, field crews';
COMMENT ON COLUMN dim_companies.has_in_house_technicians IS 'Keywords: in-house, on-staff, employed technicians, W-2 employees, not subcontractors';
COMMENT ON COLUMN dim_companies.has_apprenticeship IS 'Keywords: apprenticeship, apprentice program, training program, IBEW, union';

-- Asset-Centric Detection (Equipment, Fleet, Tools)
COMMENT ON COLUMN dim_companies.is_asset_centric IS 'Keywords: equipment, fleet, tools, vehicles, assets, inventory, warehouse';
COMMENT ON COLUMN dim_companies.has_fleet IS 'Keywords: fleet, trucks, vans, vehicles, service vehicles, fully stocked trucks';
COMMENT ON COLUMN dim_companies.has_warehouse IS 'Keywords: warehouse, inventory, parts, materials, stock, supply';
COMMENT ON COLUMN dim_companies.has_equipment_yard IS 'Keywords: equipment yard, staging, heavy equipment, material storage';

-- Size Detection (ICP Sweet Spot: $5-50M, 25-200+ employees)
COMMENT ON COLUMN dim_companies.employee_range IS 'Derived: Buckets like 1-10, 11-25, 26-50, 51-100, 101-200, 200+';
COMMENT ON COLUMN dim_companies.revenue_range IS 'Derived: Buckets like <1M, 1-5M, 5-10M, 10-25M, 25-50M, 50-100M, 100M+';
COMMENT ON COLUMN dim_companies.is_in_icp_size_range IS 'Derived: TRUE if 25-200+ employees AND $5-50M revenue';

-- =============================================================================
-- DONE: 70 ICP signals added (50 original + 20 Coperniq ICP)
-- Total categories: 7
--
-- COPERNIQ IDEAL ICP DEFINITION:
-- - MEP (Mechanical, Electrical, Plumbing) contractor
-- - Multi-trade (2+ trades)
-- - Multi-license (multiple state/specialty licenses)
-- - Multi-OEM (partnerships with 2+ manufacturers)
-- - Self-performing (own crews, not just GC who subs out)
-- - Asset-centric (fleet, warehouse, equipment)
-- - Size: $5-50M revenue, 25-200+ employees
-- =============================================================================
