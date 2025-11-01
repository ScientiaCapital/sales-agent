"""Test configuration for agents_sdk tests - ISOLATED from main app."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# CRITICAL: Mock problematic dependencies FIRST, before ANY imports
# Pytest loads parent conftest before this one, so we need to intercept
# the imports at the module level

# Mock OpenAI and all its submodules
mock_openai = MagicMock()
mock_openai.AsyncOpenAI = MagicMock()
mock_openai.OpenAI = MagicMock()
sys.modules['openai'] = mock_openai

# Mock Cerebras SDK
mock_cerebras = MagicMock()
sys.modules['cerebras_cloud_sdk'] = mock_cerebras

# Mock tenacity
mock_tenacity = MagicMock()
sys.modules['tenacity'] = mock_tenacity

# Mock MCP and Claude Agent SDK (for base_agent.py)
mock_mcp = MagicMock()
sys.modules['mcp'] = mock_mcp
mock_claude_sdk = MagicMock()
sys.modules['claude_agent_sdk'] = mock_claude_sdk

# Add backend to path AFTER mocking
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

# Prevent pytest from loading parent conftest by manipulating conftest lookup
# This is a pytest hook that runs before conftest collection
def pytest_configure(config):
    """Prevent parent conftest from loading by isolating this test suite."""
    # Mark this configuration as isolated
    config._agents_sdk_isolated = True
