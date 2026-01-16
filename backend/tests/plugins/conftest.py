"""Pytest configuration for plugin tests.

Handles Python path to allow importing from plugins/ at project root.
"""

import sys
from pathlib import Path

# Add project root to Python path so we can import plugins.sales_tools
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
