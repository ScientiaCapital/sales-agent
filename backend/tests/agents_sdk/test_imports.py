"""Test that agents_sdk module imports correctly."""
import pytest


def test_agents_sdk_module_imports():
    """Test agents_sdk package can be imported."""
    from app.agents_sdk import __version__
    assert __version__ == "0.1.0"


def test_config_imports():
    """Test config module imports."""
    from app.agents_sdk.config import AgentSDKConfig
    assert AgentSDKConfig is not None
