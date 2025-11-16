#!/usr/bin/env python3
"""
Health Check Endpoint for RunPod Container

Verifies all critical dependencies and services are available:
- Database connectivity (Supabase PostgreSQL)
- API keys configured
- Playwright/Chromium installed
- Python environment healthy

Exit codes:
- 0: Healthy
- 1: Unhealthy (container should be restarted)
"""
import os
import sys
from typing import Dict, Any


def check_environment_variables() -> Dict[str, Any]:
    """Check that all required environment variables are set."""
    required_vars = [
        "SUPABASE_DATABASE_URL",
        "CLOSE_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    return {
        "status": "ok" if not missing else "error",
        "missing_vars": missing
    }


def check_database_connectivity() -> Dict[str, Any]:
    """Check database connection."""
    try:
        import psycopg
        from dotenv import load_dotenv
        load_dotenv()

        db_url = os.getenv("SUPABASE_DATABASE_URL")
        if not db_url:
            return {"status": "error", "message": "SUPABASE_DATABASE_URL not set"}

        # Quick connection test
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                if result and result[0] == 1:
                    return {"status": "ok"}

        return {"status": "error", "message": "Database query failed"}

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }


def check_playwright() -> Dict[str, Any]:
    """Check Playwright and Chromium are installed."""
    try:
        from playwright.sync_api import sync_playwright

        # Check if Chromium is installed
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

        return {"status": "ok"}

    except Exception as e:
        return {
            "status": "error",
            "message": f"Playwright/Chromium not available: {str(e)}"
        }


def check_python_packages() -> Dict[str, Any]:
    """Check critical Python packages are installed."""
    required_packages = [
        "psycopg",
        "httpx",
        "anthropic",
        "tweepy",
        "playwright",
        "runpod",
        "structlog"
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    return {
        "status": "ok" if not missing else "error",
        "missing_packages": missing
    }


def run_health_checks() -> Dict[str, Any]:
    """Run all health checks and return comprehensive status."""
    checks = {
        "environment": check_environment_variables(),
        "database": check_database_connectivity(),
        "playwright": check_playwright(),
        "packages": check_python_packages()
    }

    # Determine overall health
    all_healthy = all(
        check.get("status") == "ok"
        for check in checks.values()
    )

    return {
        "healthy": all_healthy,
        "checks": checks
    }


if __name__ == "__main__":
    try:
        result = run_health_checks()

        if result["healthy"]:
            print("✅ Container is healthy")
            print(f"All checks passed: {list(result['checks'].keys())}")
            sys.exit(0)
        else:
            print("❌ Container is unhealthy")
            for check_name, check_result in result["checks"].items():
                if check_result.get("status") != "ok":
                    print(f"  - {check_name}: {check_result}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health check failed with exception: {e}")
        sys.exit(1)
