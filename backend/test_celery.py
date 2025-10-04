#!/usr/bin/env python3
"""
Test script for Celery task execution

This script tests the Celery infrastructure by:
1. Verifying Redis connection
2. Testing synchronous task execution
3. Testing async task execution with result retrieval

Usage:
    # Start worker in one terminal
    python celery_worker.py
    
    # Run tests in another terminal
    python test_celery.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tasks.agent_tasks import ping_task
from app.celery_app import celery_app
from redis import Redis


def test_redis_connection():
    """Test Redis connection"""
    print("\n1. Testing Redis connection...")
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        print(f"   ✓ Redis connected: {redis_url}")
        return True
    except Exception as e:
        print(f"   ✗ Redis connection failed: {e}")
        return False


def test_sync_task():
    """Test synchronous task execution"""
    print("\n2. Testing synchronous task execution...")
    try:
        result = ping_task()
        print(f"   ✓ Sync task result: {result}")
        return True
    except Exception as e:
        print(f"   ✗ Sync task failed: {e}")
        return False


def test_async_task():
    """Test async task execution with Celery worker"""
    print("\n3. Testing async task execution...")
    print("   (Note: Requires Celery worker to be running)")
    try:
        # Send task to queue
        async_result = ping_task.apply_async()
        print(f"   ✓ Task queued: {async_result.id}")
        
        # Wait for result (timeout after 5 seconds)
        result = async_result.get(timeout=5)
        print(f"   ✓ Task completed: {result}")
        return True
    except Exception as e:
        print(f"   ✗ Async task failed: {e}")
        print("   Make sure Celery worker is running: python celery_worker.py")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Celery Infrastructure Test Suite")
    print("=" * 60)
    
    # Test 1: Redis connection
    redis_ok = test_redis_connection()
    if not redis_ok:
        print("\n❌ Redis not available. Start it with: docker-compose up -d redis")
        sys.exit(1)
    
    # Test 2: Synchronous execution
    sync_ok = test_sync_task()
    
    # Test 3: Async execution (requires worker)
    async_ok = test_async_task()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Redis Connection: {'✓' if redis_ok else '✗'}")
    print(f"  Sync Execution:   {'✓' if sync_ok else '✗'}")
    print(f"  Async Execution:  {'✓' if async_ok else '✗'}")
    print("=" * 60)
    
    if redis_ok and sync_ok and async_ok:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
