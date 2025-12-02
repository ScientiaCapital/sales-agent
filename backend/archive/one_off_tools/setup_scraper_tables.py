#!/usr/bin/env python3
"""
Setup scraper_imports tables in Supabase for dealer-scraper integration.
Run once to create tables, then dealer-scraper can push directly.
"""

import os
import sys
from dotenv import load_dotenv

# Load from sales-agent .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY required in .env")
    sys.exit(1)

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create tables using Supabase SQL (via RPC if available, else manual)
SETUP_SQL = """
-- Batch tracking table
CREATE TABLE IF NOT EXISTS scraper_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_file VARCHAR(500),
    source_project VARCHAR(100) DEFAULT 'dealer-scraper-mvp',
    total_records INTEGER DEFAULT 0,
    imported_records INTEGER DEFAULT 0,
    duplicate_records INTEGER DEFAULT 0,
    error_records INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',
    file_hash VARCHAR(64)
);

-- Individual imports
CREATE TABLE IF NOT EXISTS scraper_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID REFERENCES scraper_batches(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    phone VARCHAR(50),
    email VARCHAR(255),
    website VARCHAR(500),
    domain VARCHAR(255),
    source VARCHAR(100),
    tier VARCHAR(20),
    oem_brands JSONB,
    license_types JSONB,
    license_number VARCHAR(100),
    license_state VARCHAR(10),
    status VARCHAR(50) DEFAULT 'imported',
    processed_at TIMESTAMPTZ,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_number INTEGER,
    raw_data JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scraper_batches_created ON scraper_batches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_imports_batch ON scraper_imports(batch_id);
CREATE INDEX IF NOT EXISTS idx_scraper_imports_company ON scraper_imports(company_name);
CREATE INDEX IF NOT EXISTS idx_scraper_imports_status ON scraper_imports(status);
CREATE INDEX IF NOT EXISTS idx_scraper_imports_domain ON scraper_imports(domain);
"""

def setup_tables():
    """Create tables using direct inserts to verify connection, then print manual SQL."""
    print("=" * 60)
    print("SUPABASE SCRAPER TABLES SETUP")
    print("=" * 60)
    print(f"\nConnected to: {SUPABASE_URL}")

    # Test connection
    try:
        result = client.table('lead_audit_log').select('id').limit(1).execute()
        print(f"✅ Connection verified (found {len(result.data)} audit records)")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # Check if tables exist
    try:
        result = client.table('scraper_batches').select('id').limit(1).execute()
        print("✅ scraper_batches table exists")
    except Exception as e:
        print(f"⚠️  scraper_batches table doesn't exist yet")
        print("\n📋 Run this SQL in Supabase Dashboard > SQL Editor:\n")
        print(SETUP_SQL)
        return

    try:
        result = client.table('scraper_imports').select('id').limit(1).execute()
        print("✅ scraper_imports table exists")
    except Exception as e:
        print(f"⚠️  scraper_imports table doesn't exist yet")
        print("\n📋 Run this SQL in Supabase Dashboard > SQL Editor:\n")
        print(SETUP_SQL)
        return

    print("\n✅ All tables ready for dealer-scraper integration!")
    print("\n📍 Dealer-scraper needs these in its .env:")
    print(f"   SUPABASE_URL={SUPABASE_URL}")
    print(f"   SUPABASE_SERVICE_KEY={SUPABASE_KEY[:20]}...")


if __name__ == "__main__":
    setup_tables()
