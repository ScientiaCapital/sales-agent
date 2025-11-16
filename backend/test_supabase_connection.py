"""
Test Supabase Connection and Verify Schema

Run this after creating your Supabase project and running supabase_schema.sql

Usage:
    export SUPABASE_DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"
    python test_supabase_connection.py
"""
import os
import sys
import psycopg
from datetime import datetime

def test_connection():
    """Test basic Supabase connection"""
    print("=" * 80)
    print("Testing Supabase Connection")
    print("=" * 80)

    # Get connection string from environment
    db_url = os.getenv('SUPABASE_DATABASE_URL')

    if not db_url:
        print("❌ ERROR: SUPABASE_DATABASE_URL not set")
        print("\nPlease set it like this:")
        print('export SUPABASE_DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"')
        sys.exit(1)

    try:
        # Connect to Supabase
        print(f"\n[1/5] Connecting to Supabase...")
        conn = psycopg.connect(db_url)
        cur = conn.cursor()
        print("✅ Connection successful!")

        # Test 1: Check tables exist
        print(f"\n[2/5] Verifying tables created...")
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
                AND table_name IN ('social_posts', 'contact_monitoring', 'email_drafts', 'email_engagement')
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        expected_tables = ['contact_monitoring', 'email_drafts', 'email_engagement', 'social_posts']
        found_tables = [t[0] for t in tables]

        if len(found_tables) == 4:
            print(f"✅ All 4 tables created successfully:")
            for table in found_tables:
                print(f"   - {table}")
        else:
            print(f"❌ ERROR: Expected 4 tables, found {len(found_tables)}")
            print(f"   Missing: {set(expected_tables) - set(found_tables)}")
            sys.exit(1)

        # Test 2: Insert test data
        print(f"\n[3/5] Testing data insertion...")
        cur.execute("""
            INSERT INTO contact_monitoring (
                close_contact_id,
                linkedin_url,
                twitter_handle,
                monitoring_enabled
            ) VALUES (
                %s, %s, %s, %s
            )
            ON CONFLICT (close_contact_id) DO UPDATE
            SET updated_at = NOW()
            RETURNING id, close_contact_id
        """, (
            'cont_test_12345',
            'https://linkedin.com/in/testuser',
            '@testuser',
            True
        ))
        result = cur.fetchone()
        conn.commit()
        print(f"✅ Test contact created (ID: {result[0]})")

        # Test 3: Query test data
        print(f"\n[4/5] Testing data retrieval...")
        cur.execute("""
            SELECT
                close_contact_id,
                linkedin_url,
                monitoring_enabled,
                created_at
            FROM contact_monitoring
            WHERE close_contact_id = %s
        """, ('cont_test_12345',))
        row = cur.fetchone()

        if row:
            print(f"✅ Data retrieved successfully:")
            print(f"   Contact ID: {row[0]}")
            print(f"   LinkedIn: {row[1]}")
            print(f"   Monitoring: {row[2]}")
            print(f"   Created: {row[3]}")
        else:
            print(f"❌ ERROR: Could not retrieve test data")
            sys.exit(1)

        # Test 4: Test views
        print(f"\n[5/5] Testing database views...")
        cur.execute("SELECT COUNT(*) FROM high_intent_contacts")
        count = cur.fetchone()[0]
        print(f"✅ high_intent_contacts view working (found {count} contacts)")

        cur.execute("SELECT COUNT(*) FROM daily_social_summary")
        count = cur.fetchone()[0]
        print(f"✅ daily_social_summary view working (found {count} days)")

        # Cleanup test data
        cur.execute("DELETE FROM contact_monitoring WHERE close_contact_id = %s", ('cont_test_12345',))
        conn.commit()

        # Close connection
        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED! Supabase database is ready.")
        print("=" * 80)
        print("\n📋 Next Steps:")
        print("   1. Add SUPABASE_DATABASE_URL to .env file")
        print("   2. Move on to Task 1.3 - RunPod Serverless Setup")
        print("\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Check your connection string format")
        print("2. Ensure you ran supabase_schema.sql in Supabase SQL Editor")
        print("3. Verify your project is not paused (Supabase free tier)")
        sys.exit(1)


if __name__ == "__main__":
    test_connection()
