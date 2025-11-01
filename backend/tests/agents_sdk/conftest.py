"""Test configuration for agents_sdk tests.

This conftest isolates agents_sdk tests from the main app setup.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))
