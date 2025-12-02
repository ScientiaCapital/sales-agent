#!/usr/bin/env python3
"""
Deep Scrape Prerequisites Validation Script
===========================================

Validates that all required dependencies, directories, and connections
are ready before running the deep scrape on 1,000 companies.

Usage:
    python backend/validate_deep_scrape_prerequisites.py
    ./backend/validate_deep_scrape_prerequisites.py  # if executable

Exit codes:
    0 = All prerequisites met (ready for production)
    1 = Critical failures (cannot run deep scrape)
    2 = Warnings only (can run but may have issues)
"""

import sys
import os
from pathlib import Path
from typing import List, Tuple
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)


class ValidationResult:
    def __init__(self):
        self.critical_failures: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []

    def add_critical(self, message: str):
        self.critical_failures.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_success(self, message: str):
        self.successes.append(message)

    def get_exit_code(self) -> int:
        if self.critical_failures:
            return 1
        if self.warnings:
            return 2
        return 0


def check_directories(result: ValidationResult):
    """Check that all required directories exist."""
    print("\n=== Checking Required Directories ===")

    required_dirs = [
        'backend/data/final_enrichment_output',
        'backend/logs',
        'backend/data/apollo_cache',
        'backend/data/scrape_sessions',
    ]

    for dir_path in required_dirs:
        full_path = Path(dir_path)
        if full_path.exists() and full_path.is_dir():
            if os.access(full_path, os.W_OK):
                result.add_success(f"✓ {dir_path} exists and is writable")
            else:
                result.add_critical(f"✗ {dir_path} exists but is NOT writable")
        else:
            result.add_critical(f"✗ {dir_path} does NOT exist")


def check_playwright(result: ValidationResult):
    """Check Playwright installation and browser availability."""
    print("\n=== Checking Playwright ===")

    try:
        from playwright.sync_api import sync_playwright
        result.add_success("✓ Playwright library installed")

        # Test browser launch
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                browser.close()
            result.add_success("✓ Chromium browser installed and working")
        except Exception as e:
            result.add_critical(f"✗ Chromium browser test failed: {str(e)}")
            result.add_critical("  Run: playwright install chromium")

    except ImportError:
        result.add_critical("✗ Playwright library NOT installed")
        result.add_critical("  Run: pip install playwright && playwright install chromium")


def check_database_connection(result: ValidationResult):
    """Check PostgreSQL database connection."""
    print("\n=== Checking Database Connection ===")

    try:
        import psycopg2
        from urllib.parse import urlparse

        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            result.add_warning("⚠ DATABASE_URL not set in environment")
            return

        # Parse connection string
        parsed = urlparse(database_url)

        try:
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            conn.close()
            result.add_success("✓ PostgreSQL connection successful")
        except Exception as e:
            result.add_critical(f"✗ PostgreSQL connection failed: {str(e)}")

    except ImportError:
        result.add_warning("⚠ psycopg2 not installed (database checks skipped)")


def check_redis_connection(result: ValidationResult):
    """Check Redis connection."""
    print("\n=== Checking Redis Connection ===")

    try:
        import redis

        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

        try:
            r = redis.from_url(redis_url)
            r.ping()
            result.add_success("✓ Redis connection successful")
        except Exception as e:
            result.add_warning(f"⚠ Redis connection failed: {str(e)}")
            result.add_warning("  Deep scrape will work but caching may be limited")

    except ImportError:
        result.add_warning("⚠ redis library not installed (caching checks skipped)")


def check_environment_variables(result: ValidationResult):
    """Check required environment variables."""
    print("\n=== Checking Environment Variables ===")

    # Critical variables (required for deep scrape)
    critical_vars = {
        'BROWSERBASE_API_KEY': 'Browserbase authentication',
        'BROWSERBASE_PROJECT_ID': 'Browserbase project ID',
    }

    # Optional variables (functionality may be limited without them)
    optional_vars = {
        'DATABASE_URL': 'PostgreSQL database connection',
        'REDIS_URL': 'Redis caching',
        'SUPABASE_URL': 'Supabase database',
        'SUPABASE_KEY': 'Supabase authentication',
        'APOLLO_API_KEY': 'Apollo API for contact enrichment',
    }

    for var_name, description in critical_vars.items():
        value = os.getenv(var_name)
        if value:
            result.add_success(f"✓ {var_name} is set ({description})")
        else:
            result.add_critical(f"✗ {var_name} is NOT set ({description})")

    for var_name, description in optional_vars.items():
        value = os.getenv(var_name)
        if value:
            result.add_success(f"✓ {var_name} is set ({description})")
        else:
            result.add_warning(f"⚠ {var_name} is NOT set ({description})")


def check_supabase_connection(result: ValidationResult):
    """Check Supabase connection if keys are available."""
    print("\n=== Checking Supabase Connection ===")

    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        result.add_warning("⚠ Supabase credentials not set (skipping connection test)")
        return

    try:
        from supabase import create_client

        try:
            client = create_client(supabase_url, supabase_key)
            # Simple test query
            response = client.table('companies').select('id').limit(1).execute()
            result.add_success("✓ Supabase connection successful")
        except Exception as e:
            result.add_warning(f"⚠ Supabase connection failed: {str(e)}")

    except ImportError:
        result.add_warning("⚠ supabase library not installed (Supabase checks skipped)")


def check_input_files(result: ValidationResult):
    """Check that input files exist."""
    print("\n=== Checking Input Files ===")

    input_dir = Path('backend/data/final_enrichment_output')

    if not input_dir.exists():
        result.add_critical(f"✗ Input directory does not exist: {input_dir}")
        return

    # Look for CSV files
    csv_files = list(input_dir.glob('*.csv'))

    if not csv_files:
        result.add_warning(f"⚠ No CSV files found in {input_dir}")
        result.add_warning("  Deep scrape needs enriched company data to process")
    else:
        result.add_success(f"✓ Found {len(csv_files)} CSV file(s) in input directory")
        for csv_file in csv_files[:3]:  # Show first 3
            result.add_success(f"  - {csv_file.name}")


def check_python_dependencies(result: ValidationResult):
    """Check that all Python dependencies are installed."""
    print("\n=== Checking Python Dependencies ===")

    required_packages = [
        ('pandas', 'Data processing'),
        ('httpx', 'HTTP requests'),
        ('playwright', 'Browser automation'),
        ('dotenv', 'Environment variables'),
    ]

    for package_name, description in required_packages:
        try:
            __import__(package_name)
            result.add_success(f"✓ {package_name} installed ({description})")
        except ImportError:
            result.add_critical(f"✗ {package_name} NOT installed ({description})")
            result.add_critical(f"  Run: pip install {package_name}")


def print_summary(result: ValidationResult):
    """Print validation summary."""
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    if result.successes:
        print(f"\n✓ PASSED ({len(result.successes)} checks)")
        for success in result.successes:
            print(f"  {success}")

    if result.warnings:
        print(f"\n⚠ WARNINGS ({len(result.warnings)} issues)")
        for warning in result.warnings:
            print(f"  {warning}")

    if result.critical_failures:
        print(f"\n✗ CRITICAL FAILURES ({len(result.critical_failures)} issues)")
        for failure in result.critical_failures:
            print(f"  {failure}")

    print("\n" + "="*60)

    exit_code = result.get_exit_code()

    if exit_code == 0:
        print("✓ ALL CHECKS PASSED - Ready for production deep scrape!")
    elif exit_code == 2:
        print("⚠ WARNINGS DETECTED - Can proceed but some features may be limited")
    else:
        print("✗ CRITICAL FAILURES - Cannot run deep scrape until issues are resolved")

    print("="*60 + "\n")

    return exit_code


def main():
    """Run all validation checks."""
    print("="*60)
    print("DEEP SCRAPE PREREQUISITES VALIDATION")
    print("="*60)

    result = ValidationResult()

    # Run all checks
    check_directories(result)
    check_python_dependencies(result)
    check_playwright(result)
    check_environment_variables(result)
    check_database_connection(result)
    check_redis_connection(result)
    check_supabase_connection(result)
    check_input_files(result)

    # Print summary and exit with appropriate code
    exit_code = print_summary(result)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
