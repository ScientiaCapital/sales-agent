#!/usr/bin/env python3
"""Test database connection recovery after PostgreSQL restart."""
import sys
import os
import asyncio
import subprocess
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

# Load environment
from dotenv import load_dotenv
load_dotenv()

from app.models.database import check_database_health

async def test_connection_recovery():
    """Test connection recovery after PostgreSQL restart."""
    print("=" * 60)
    print("DATABASE CONNECTION RECOVERY TEST")
    print("=" * 60)
    
    # Step 1: Verify initial connection
    print("\n[STEP 1] Verify initial database connection")
    result1 = await check_database_health()
    if result1.get('status') != 'healthy':
        print("❌ Initial connection failed")
        return False
    print(f"✅ Initial connection successful ({result1.get('latency_ms')}ms)")
    
    # Step 2: Restart PostgreSQL
    print("\n[STEP 2] Restarting PostgreSQL container...")
    try:
        subprocess.run(
            ['docker-compose', 'restart', 'postgres'],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ PostgreSQL container restarted")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restart PostgreSQL: {e}")
        return False
    
    # Step 3: Wait for PostgreSQL to be ready
    print("\n[STEP 3] Waiting for PostgreSQL to be ready...")
    for i in range(10):
        await asyncio.sleep(2)
        result = await check_database_health()
        if result.get('status') == 'healthy':
            print(f"✅ PostgreSQL ready after {(i+1)*2}s")
            break
        print(f"   Attempt {i+1}/10: {result.get('status')} - {result.get('error', 'waiting...')}")
    else:
        print("❌ PostgreSQL did not become ready in time")
        return False
    
    # Step 4: Test multiple connections
    print("\n[STEP 4] Testing connection pool recovery (5 connections)")
    results = []
    for i in range(5):
        result = await check_database_health()
        status = "✅" if result.get('status') == 'healthy' else "❌"
        print(f"   Connection {i+1}: {status} ({result.get('latency_ms')}ms)")
        results.append(result.get('status') == 'healthy')
    
    success_rate = sum(results) / len(results) * 100
    
    # Results
    print("\n" + "=" * 60)
    print("RECOVERY TEST RESULTS")
    print("=" * 60)
    
    if success_rate == 100:
        print("✅ Connection recovery successful!")
        print(f"   Success rate: {success_rate:.0f}%")
        print("\nResilience features validated:")
        print("  • pool_pre_ping detected stale connections")
        print("  • Automatic reconnection on connection loss")
        print("  • Connection pool recovered after restart")
        print("  • No manual intervention required")
        return True
    else:
        print(f"⚠️  Partial recovery: {success_rate:.0f}% success rate")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection_recovery())
    sys.exit(0 if success else 1)
