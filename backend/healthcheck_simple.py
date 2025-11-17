#!/usr/bin/env python3
"""
Simplified Health Check for RunPod Container

Only verifies container basics - doesn't block on external services.
This allows workers to become healthy even if env vars aren't fully configured.

Exit codes:
- 0: Healthy (basic checks pass)
- 1: Unhealthy (critical import failure)
"""
import sys


def check_critical_imports():
    """Check that handler.py can be imported (verifies all dependencies)."""
    try:
        # This will fail if any critical dependency is missing
        import runpod
        import httpx
        import anthropic

        # Try importing our handler module to verify it loads
        import handler

        print("✅ Container is healthy - all critical imports successful")
        return True

    except ImportError as e:
        print(f"❌ Container is unhealthy - import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Container is unhealthy - unexpected error: {e}")
        return False


if __name__ == "__main__":
    try:
        if check_critical_imports():
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health check failed with exception: {e}")
        sys.exit(1)
