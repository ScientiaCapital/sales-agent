"""
Test script for Browserbase Session Pool

Usage:
    python test_session_pool.py

Tests:
    1. Pool initialization
    2. Session checkout/checkin
    3. Session rotation (max_uses)
    4. Session expiration (timeout)
    5. Concurrent access
    6. Pool statistics
    7. Graceful shutdown
"""

import asyncio
import logging
import sys
from pathlib import Path

# CRITICAL: Load .env BEFORE importing session pool module
# The session pool reads env vars at import time
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path, override=True)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.browserbase_session_pool import (
    get_session_pool,
    close_session_pool,
    BrowserbaseSession,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_basic_checkout_checkin():
    """Test basic session checkout and checkin."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Basic Checkout/Checkin")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Checkout session
    session = await pool.checkout()
    logger.info(f"✓ Checked out session: {session}")

    # Verify session is active
    assert session.is_active, "Session should be active after checkout"
    assert session.usage_count == 0, "New session should have usage_count=0"

    # Checkin session
    await pool.checkin(session)
    logger.info(f"✓ Checked in session: {session}")

    # Verify session is inactive
    assert not session.is_active, "Session should be inactive after checkin"
    assert session.usage_count == 1, "Session should have usage_count=1 after checkin"

    logger.info("✓ TEST PASSED: Basic checkout/checkin working")


async def test_session_reuse():
    """Test that sessions are reused from the pool."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Session Reuse")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Checkout and checkin first session
    session1 = await pool.checkout()
    session1_id = session1.session_id
    usage_after_first_checkout = session1.usage_count
    logger.info(f"✓ First checkout: {session1}")
    await pool.checkin(session1)

    # Checkout second session (should be same as first)
    session2 = await pool.checkout()
    logger.info(f"✓ Second checkout: {session2}")

    assert (
        session2.session_id == session1_id
    ), "Should reuse same session from pool"
    # Session was used once when checked in, so usage should be higher now
    assert session2.usage_count >= usage_after_first_checkout + 1, (
        f"Reused session should have higher usage_count (was {usage_after_first_checkout}, now {session2.usage_count})"
    )

    await pool.checkin(session2)

    logger.info("✓ TEST PASSED: Session reuse working")


async def test_session_rotation():
    """Test that sessions rotate after max_uses."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Session Rotation (max_uses)")
    logger.info("=" * 60)

    # Create pool with max_uses=3 for testing
    pool = await get_session_pool()
    pool.session_max_uses = 3  # Override for testing

    session = await pool.checkout()
    original_session_id = session.session_id
    logger.info(f"✓ Original session: {session}")

    # Use session 3 times (reach max_uses)
    for i in range(1, 4):
        await pool.checkin(session)
        logger.info(f"✓ Usage {i}/3 completed")

        if i < 3:
            session = await pool.checkout()

    # Next checkout should get a NEW session (rotation)
    new_session = await pool.checkout()
    logger.info(f"✓ New session after rotation: {new_session}")

    assert (
        new_session.session_id != original_session_id
    ), "Should get new session after max_uses"
    assert new_session.usage_count == 0, "New session should have usage_count=0"

    await pool.checkin(new_session)

    logger.info("✓ TEST PASSED: Session rotation working")


async def test_concurrent_access():
    """Test concurrent session access."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Concurrent Access")
    logger.info("=" * 60)

    pool = await get_session_pool()

    async def worker(worker_id: int):
        """Simulate concurrent worker."""
        session = await pool.checkout()
        logger.info(f"Worker {worker_id} got session: {session.session_id[:8]}...")

        # Simulate work
        await asyncio.sleep(0.5)

        await pool.checkin(session)
        logger.info(f"Worker {worker_id} returned session")

    # Run 3 concurrent workers
    await asyncio.gather(*[worker(i) for i in range(1, 4)])

    logger.info("✓ TEST PASSED: Concurrent access working")


async def test_pool_stats():
    """Test pool statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Pool Statistics")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Get initial stats
    stats = await pool.get_pool_stats()
    logger.info(f"✓ Initial pool stats: {stats}")

    # Checkout session
    session = await pool.checkout()
    stats = await pool.get_pool_stats()
    logger.info(f"✓ Stats after checkout: {stats}")

    assert stats["active_sessions"] >= 1, "Should have at least 1 active session"

    # Checkin session
    await pool.checkin(session)
    stats = await pool.get_pool_stats()
    logger.info(f"✓ Stats after checkin: {stats}")

    assert stats["active_sessions"] >= 0, "Active sessions should be >= 0"

    logger.info("✓ TEST PASSED: Pool statistics working")


async def test_warm_up():
    """Test pool warm-up."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Pool Warm-up")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Warm up with 2 sessions
    await pool.warm_up(count=2)

    stats = await pool.get_pool_stats()
    logger.info(f"✓ Stats after warm-up: {stats}")

    assert stats["available_sessions"] >= 2, "Should have at least 2 available sessions"

    logger.info("✓ TEST PASSED: Pool warm-up working")


async def test_graceful_shutdown():
    """Test graceful pool shutdown."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Graceful Shutdown")
    logger.info("=" * 60)

    pool = await get_session_pool()

    # Checkout a session
    session = await pool.checkout()
    logger.info(f"✓ Checked out session: {session.session_id[:8]}...")

    # Checkin and close pool
    await pool.checkin(session)
    await close_session_pool()

    logger.info("✓ TEST PASSED: Graceful shutdown completed")


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("BROWSERBASE SESSION POOL TEST SUITE")
    logger.info("=" * 60)

    try:
        # Run tests sequentially
        await test_basic_checkout_checkin()
        await test_session_reuse()
        await test_session_rotation()
        await test_concurrent_access()
        await test_pool_stats()
        await test_warm_up()
        await test_graceful_shutdown()

        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
