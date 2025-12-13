-- ============================================
-- Migration: Prevent Future Duplicates
-- Created: 2025-12-13
-- Purpose: Add UNIQUE constraints and upsert functions to prevent duplicate companies
-- ============================================

-- ============================================
-- Step 1: Populate normalized_name for all existing records
-- ============================================

-- Create function to normalize company names
CREATE OR REPLACE FUNCTION normalize_company_name(name TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    result TEXT;
BEGIN
    IF name IS NULL OR name = '' THEN
        RETURN NULL;
    END IF;

    -- Lowercase and trim
    result := LOWER(TRIM(name));

    -- Remove punctuation except hyphens
    result := REGEXP_REPLACE(result, '[^\w\s-]', '', 'g');

    -- Strip common business suffixes
    result := REGEXP_REPLACE(result, '\s+(inc|llc|ltd|corp|co|company|corporation|incorporated|enterprises?|services?|systems?|solutions?|group|holdings?|pbc|dba\s+.*)\.?$', '', 'gi');

    -- Normalize whitespace
    result := REGEXP_REPLACE(result, '\s+', ' ', 'g');
    result := TRIM(result);

    RETURN result;
END;
$$;

-- Update all existing records with normalized_name
UPDATE dim_companies
SET normalized_name = normalize_company_name(company_name)
WHERE normalized_name IS NULL OR normalized_name = '';

-- ============================================
-- Step 2: Create trigger to auto-populate normalized_name
-- ============================================

DROP TRIGGER IF EXISTS trigger_normalize_company_name ON dim_companies;

CREATE OR REPLACE FUNCTION trigger_normalize_company_name()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.normalized_name := normalize_company_name(NEW.company_name);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trigger_normalize_company_name
    BEFORE INSERT OR UPDATE OF company_name ON dim_companies
    FOR EACH ROW
    EXECUTE FUNCTION trigger_normalize_company_name();

-- ============================================
-- Step 3: Add UNIQUE index on normalized_name
-- (After deduplication is complete)
-- ============================================

-- Create partial unique index (ignores NULL)
-- This prevents new duplicates while allowing NULL normalized_names
DROP INDEX IF EXISTS idx_dim_companies_normalized_name_unique;

CREATE UNIQUE INDEX idx_dim_companies_normalized_name_unique
ON dim_companies (normalized_name)
WHERE normalized_name IS NOT NULL;

-- Also index close_lead_id for sync performance
DROP INDEX IF EXISTS idx_dim_companies_close_lead_id;
CREATE INDEX idx_dim_companies_close_lead_id ON dim_companies (close_lead_id)
WHERE close_lead_id IS NOT NULL;

-- ============================================
-- Step 4: Create upsert function for safe inserts
-- ============================================

CREATE OR REPLACE FUNCTION upsert_company(
    p_company_name TEXT,
    p_close_lead_id TEXT DEFAULT NULL,
    p_domain TEXT DEFAULT NULL,
    p_website TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL,
    p_city TEXT DEFAULT NULL,
    p_state TEXT DEFAULT NULL,
    p_zip TEXT DEFAULT NULL,
    p_icp_score INTEGER DEFAULT NULL,
    p_icp_tier TEXT DEFAULT NULL,
    p_source_type TEXT DEFAULT 'api'
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_normalized TEXT;
    v_company_id UUID;
BEGIN
    -- Normalize the company name
    v_normalized := normalize_company_name(p_company_name);

    -- Check if company exists
    SELECT company_id INTO v_company_id
    FROM dim_companies
    WHERE normalized_name = v_normalized
    LIMIT 1;

    IF v_company_id IS NOT NULL THEN
        -- UPDATE existing record
        UPDATE dim_companies
        SET
            -- Only update if new value is non-null and better
            close_lead_id = COALESCE(p_close_lead_id, close_lead_id),
            domain = COALESCE(p_domain, domain),
            website = COALESCE(p_website, website),
            phone = COALESCE(p_phone, phone),
            city = COALESCE(p_city, city),
            state = COALESCE(p_state, state),
            zip = COALESCE(p_zip, zip),
            icp_score = GREATEST(COALESCE(icp_score, 0), COALESCE(p_icp_score, 0)),
            icp_tier = COALESCE(p_icp_tier, icp_tier),
            updated_at = NOW()
        WHERE company_id = v_company_id;

        RETURN v_company_id;
    ELSE
        -- INSERT new record
        INSERT INTO dim_companies (
            company_id,
            company_name,
            normalized_name,
            close_lead_id,
            domain,
            website,
            phone,
            city,
            state,
            zip,
            icp_score,
            icp_tier,
            source_type,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),
            p_company_name,
            v_normalized,
            p_close_lead_id,
            p_domain,
            p_website,
            p_phone,
            p_city,
            p_state,
            p_zip,
            p_icp_score,
            p_icp_tier,
            p_source_type,
            NOW(),
            NOW()
        )
        RETURNING company_id INTO v_company_id;

        RETURN v_company_id;
    END IF;
END;
$$;

-- ============================================
-- Step 5: Create sync function for Close CRM
-- ============================================

CREATE OR REPLACE FUNCTION sync_company_from_close(
    p_close_lead_id TEXT,
    p_company_name TEXT,
    p_domain TEXT DEFAULT NULL,
    p_website TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL,
    p_city TEXT DEFAULT NULL,
    p_state TEXT DEFAULT NULL,
    p_zip TEXT DEFAULT NULL,
    p_icp_score INTEGER DEFAULT NULL,
    p_icp_tier TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id UUID;
BEGIN
    -- First check if we already have this Close lead
    SELECT company_id INTO v_company_id
    FROM dim_companies
    WHERE close_lead_id = p_close_lead_id
    LIMIT 1;

    IF v_company_id IS NOT NULL THEN
        -- UPDATE existing by close_lead_id
        UPDATE dim_companies
        SET
            company_name = COALESCE(p_company_name, company_name),
            normalized_name = normalize_company_name(COALESCE(p_company_name, company_name)),
            domain = COALESCE(p_domain, domain),
            website = COALESCE(p_website, website),
            phone = COALESCE(p_phone, phone),
            city = COALESCE(p_city, city),
            state = COALESCE(p_state, state),
            zip = COALESCE(p_zip, zip),
            icp_score = COALESCE(p_icp_score, icp_score),
            icp_tier = COALESCE(p_icp_tier, icp_tier),
            updated_at = NOW()
        WHERE company_id = v_company_id;

        RETURN v_company_id;
    ELSE
        -- Check if company exists by normalized name (may not have close_lead_id yet)
        SELECT company_id INTO v_company_id
        FROM dim_companies
        WHERE normalized_name = normalize_company_name(p_company_name)
        LIMIT 1;

        IF v_company_id IS NOT NULL THEN
            -- Link existing company to Close
            UPDATE dim_companies
            SET
                close_lead_id = p_close_lead_id,
                domain = COALESCE(p_domain, domain),
                website = COALESCE(p_website, website),
                phone = COALESCE(p_phone, phone),
                city = COALESCE(p_city, city),
                state = COALESCE(p_state, state),
                zip = COALESCE(p_zip, zip),
                icp_score = COALESCE(p_icp_score, icp_score),
                icp_tier = COALESCE(p_icp_tier, icp_tier),
                updated_at = NOW()
            WHERE company_id = v_company_id;

            RETURN v_company_id;
        ELSE
            -- INSERT new company from Close
            INSERT INTO dim_companies (
                company_id,
                company_name,
                normalized_name,
                close_lead_id,
                domain,
                website,
                phone,
                city,
                state,
                zip,
                icp_score,
                icp_tier,
                source_type,
                created_at,
                updated_at
            ) VALUES (
                gen_random_uuid(),
                p_company_name,
                normalize_company_name(p_company_name),
                p_close_lead_id,
                p_domain,
                p_website,
                p_phone,
                p_city,
                p_state,
                p_zip,
                p_icp_score,
                p_icp_tier,
                'close_crm',
                NOW(),
                NOW()
            )
            RETURNING company_id INTO v_company_id;

            RETURN v_company_id;
        END IF;
    END IF;
END;
$$;

-- ============================================
-- Dependencies: dim_companies table
-- ============================================
