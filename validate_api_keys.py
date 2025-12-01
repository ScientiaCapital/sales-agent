#!/usr/bin/env python3
"""
API Keys & Security Configuration Validation Report
====================================================
Validates all required API keys for the sales-agent project.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Tuple

# Load environment variables
load_dotenv()

# Define required keys with their importance
REQUIRED_KEYS = {
    # Critical AI Models
    'CEREBRAS_API_KEY': {
        'required': True,
        'description': 'Primary AI model (ultra-fast inference)',
        'pattern': r'^csk-',
    },
    'ANTHROPIC_API_KEY': {
        'required': True,
        'description': 'Fallback AI model (Claude)',
        'pattern': r'^sk-ant-',
    },

    # Web Scraping
    'BROWSERBASE_API_KEY': {
        'required': True,
        'description': 'LinkedIn scraping & web automation',
        'pattern': r'^[a-zA-Z0-9\-_]+$',
    },
    'BROWSERBASE_PROJECT_ID': {
        'required': True,
        'description': 'Browserbase project identifier',
        'pattern': r'^[a-zA-Z0-9\-_]+$',
    },

    # Email Discovery
    'HUNTER_API_KEY': {
        'required': True,
        'description': 'Email discovery fallback',
        'pattern': r'^[a-f0-9]{40}$',
    },

    # CRM Integration
    'CLOSE_API_KEY': {
        'required': True,
        'description': 'Close CRM API access',
        'pattern': r'^api_',
    },

    # Database (Supabase)
    'SUPABASE_URL': {
        'required': True,
        'description': 'Supabase database URL',
        'pattern': r'^https://[a-z0-9]+\.supabase\.co$',
    },
    'SUPABASE_SERVICE_KEY': {
        'required': False,
        'description': 'Supabase service role key (or SUPABASE_ANON_KEY)',
        'pattern': r'^eyJ',
    },
    'SUPABASE_ANON_KEY': {
        'required': False,
        'description': 'Supabase anon key (alternative to service key)',
        'pattern': r'^eyJ',
    },

    # Security
    'CRM_ENCRYPTION_KEY': {
        'required': True,
        'description': 'Fernet encryption key for CRM data',
        'pattern': r'^[A-Za-z0-9\-_=]{44}$',
    },
}

PLACEHOLDER_PATTERNS = [
    'your_',
    'CHANGE_ME',
    'xxxxx',
    'your-',
]


def is_placeholder(value: str) -> bool:
    """Check if value is a placeholder."""
    return any(pattern in value for pattern in PLACEHOLDER_PATTERNS)


def validate_key(key_name: str, config: dict) -> Tuple[str, str]:
    """
    Validate a single API key.

    Returns:
        (status, message) where status is one of: ✅, ❌, ⚠️, ℹ️
    """
    value = os.getenv(key_name)

    # Check if key exists
    if not value:
        if config['required']:
            return '❌', 'MISSING (required)'
        else:
            return 'ℹ️', 'Not set (optional)'

    # Check if placeholder
    if is_placeholder(value):
        if config['required']:
            return '❌', 'PLACEHOLDER (needs real value)'
        else:
            return '⚠️', 'PLACEHOLDER (optional)'

    # Validate pattern if provided
    if 'pattern' in config:
        if not re.match(config['pattern'], value):
            return '⚠️', f'Invalid format (expected: {config["pattern"][:30]}...)'

    # Check minimum length
    if len(value) < 10:
        return '⚠️', f'Too short ({len(value)} chars)'

    return '✅', f'Present ({len(value)} chars)'


def check_supabase_config() -> str:
    """Special check for Supabase: needs URL + (service key OR anon key)."""
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    anon_key = os.getenv('SUPABASE_ANON_KEY')

    if not url or is_placeholder(url):
        return '❌ Missing SUPABASE_URL'

    has_service = service_key and not is_placeholder(service_key)
    has_anon = anon_key and not is_placeholder(anon_key)

    if not has_service and not has_anon:
        return '❌ Missing both SUPABASE_SERVICE_KEY and SUPABASE_ANON_KEY'

    return '✅ Configured correctly'


def generate_crm_encryption_key() -> str:
    """Generate a new Fernet encryption key."""
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except ImportError:
        return 'ERROR: cryptography module not installed'


def print_report():
    """Print full validation report."""
    print("=" * 80)
    print("API KEYS & SECURITY CONFIGURATION REPORT")
    print("=" * 80)
    print()

    # Track statistics
    total_required = sum(1 for cfg in REQUIRED_KEYS.values() if cfg['required'])
    validated = 0
    missing = 0
    warnings = 0

    # Validate each key
    print("KEY VALIDATION STATUS:")
    print("-" * 80)

    for key_name, config in REQUIRED_KEYS.items():
        # Skip individual Supabase keys, we'll check them together
        if key_name in ['SUPABASE_SERVICE_KEY', 'SUPABASE_ANON_KEY']:
            continue

        status, message = validate_key(key_name, config)
        required_marker = " (REQUIRED)" if config['required'] else " (optional)"

        print(f"{status} {key_name:30s} {required_marker:15s} {message}")
        print(f"   └─ {config['description']}")

        if status == '✅':
            validated += 1
        elif status == '❌':
            missing += 1
        elif status == '⚠️':
            warnings += 1

    # Special Supabase check
    print()
    print("-" * 80)
    print("SUPABASE DATABASE CONFIGURATION:")
    print("-" * 80)
    supabase_status = check_supabase_config()
    print(f"{supabase_status}")

    if '❌' in supabase_status:
        missing += 1
    else:
        validated += 1

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"✅ Validated:  {validated}")
    print(f"❌ Missing:    {missing}")
    print(f"⚠️  Warnings:   {warnings}")
    print(f"📊 Total Required: {total_required}")
    print()

    # Generate CRM encryption key if missing
    crm_key = os.getenv('CRM_ENCRYPTION_KEY')
    if not crm_key or is_placeholder(crm_key):
        print("=" * 80)
        print("🔑 GENERATED CRM_ENCRYPTION_KEY (add to .env):")
        print("=" * 80)
        new_key = generate_crm_encryption_key()
        print(f"CRM_ENCRYPTION_KEY={new_key}")
        print()

    # Print recommendations
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)

    if missing > 0:
        print()
        print("❌ CRITICAL: Missing required API keys")
        print("   Action: Add the missing keys to .env file")
        print("   Reference: API_KEYS_SETUP.md for setup instructions")

    if warnings > 0:
        print()
        print("⚠️  WARNING: Some keys have validation issues")
        print("   Action: Review keys marked with ⚠️ above")

    # No OpenAI check
    if os.getenv('OPENAI_API_KEY'):
        print()
        print("⚠️  WARNING: OPENAI_API_KEY found in .env")
        print("   Project policy: This project does not use OpenAI")
        print("   Action: Remove or comment out OPENAI_API_KEY")

    print()
    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print()
    print("1. Add missing API keys to .env file")
    print("2. Replace placeholder values with real credentials")
    print("3. Run test connectivity (see TEST_CONNECTIVITY section below)")
    print("4. Verify database migrations are applied")
    print()

    return validated, missing, warnings


def test_supabase_connection():
    """Test Supabase database connectivity."""
    print("=" * 80)
    print("SUPABASE CONNECTIVITY TEST:")
    print("=" * 80)

    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    anon_key = os.getenv('SUPABASE_ANON_KEY')

    if not url or is_placeholder(url):
        print("❌ Cannot test: SUPABASE_URL not configured")
        return False

    key = service_key if service_key and not is_placeholder(service_key) else anon_key

    if not key or is_placeholder(key):
        print("❌ Cannot test: No valid Supabase key found")
        return False

    try:
        # Try to import supabase client
        try:
            from supabase import create_client
        except ImportError:
            print("⚠️  supabase-py not installed")
            print("   Install with: pip install supabase")
            return False

        # Attempt connection
        print(f"Testing connection to {url}...")
        client = create_client(url, key)

        # Simple query to test connection
        result = client.table('dim_companies').select('company_id').limit(1).execute()

        print("✅ Connection successful!")
        print(f"   Tables accessible: dim_companies")
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Possible causes:")
        print("  - Invalid credentials")
        print("  - Network connectivity issues")
        print("  - Tables not created (run supabase_schema.sql)")
        return False


if __name__ == '__main__':
    import sys

    # Print validation report
    validated, missing, warnings = print_report()

    # Test connectivity if requested
    if '--test-connection' in sys.argv:
        print()
        test_supabase_connection()
        print()

    # Exit code based on validation results
    if missing > 0:
        sys.exit(1)  # Critical issues
    elif warnings > 0:
        sys.exit(2)  # Warnings only
    else:
        sys.exit(0)  # All good
